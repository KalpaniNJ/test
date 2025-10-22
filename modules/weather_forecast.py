import os
from datetime import datetime
import ee
import streamlit as st
import geemap.foliumap as geemap
import geopandas as gpd
from shapely.geometry import shape


# ---------- CONFIG ----------
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))

COL_DISTRICT = "ADM2_EN"
COL_BASIN    = "WSHD_NAME"

# ---------- HELPERS ----------
@st.cache_data(show_spinner=False)
def _read_vector(path: str) -> gpd.GeoDataFrame:
    """Read shapefile with caching."""
    return gpd.read_file(path)


def _safe_path(*parts):
    path = os.path.normpath(os.path.join(*parts))
    if not os.path.exists(path):
        st.warning(f"Missing file: {path}")
    return path


def _to_ee_geometry(gdf: gpd.GeoDataFrame) -> ee.Geometry:
    """Convert GeoDataFrame to ee.Geometry (merged)."""
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    return ee.Geometry(gdf.unary_union.__geo_interface__)


def _get_sri_lanka_geometry() -> ee.Geometry:
    """Sri Lanka boundary from GAUL."""
    return (
        ee.FeatureCollection("FAO/GAUL/2015/level0")
        .filter(ee.Filter.eq("ADM0_NAME", "Sri Lanka"))
        .geometry()
    )

# ---------- Rainfall (GPM IMERG V07) ----------
def _rainfall_aggregate(start_date: str, end_date: str, temporal_method: str) -> ee.Image:
    """Aggregate GPM rainfall over time using Sum, Mean, or Median."""
    ic = (
        ee.ImageCollection("NASA/GPM_L3/IMERG_V07")
        .filterDate(ee.Date(start_date), ee.Date(end_date))
        .select("precipitation")
    )

    method = temporal_method.lower()
    if method == "mean":
        img = ic.mean()
    elif method == "median":
        img = ic.median()
    else:
        img = ic.sum()  # default (total rainfall)
    return img

# ---------- Sentinel-1 SAR median for user period ----------
def _sentinel1_period_vv(start_date: str, end_date: str) -> ee.Image:
    """Median VV backscatter over user-defined period."""
    sl = _get_sri_lanka_geometry()
    s1 = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterDate(ee.Date(start_date), ee.Date(end_date))
        .filterBounds(sl)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select("VV")
        .median()
        .clip(sl)
    )
    return s1


# ---------- ESA/WorldCover (LULC) ----------
def _worldcover_2021():
    return ee.ImageCollection("ESA/WorldCover/v200").first().select("Map").clip(_get_sri_lanka_geometry())

# ---------- SRTM-DEM ----------
def _srtm_dem():
    return ee.Image("USGS/SRTMGL1_003").clip(_get_sri_lanka_geometry())

# ---------- JRC Permanent Water ----------
def _jrc_permanent_water():
    """Return permanent water mask (1 = permanent water, 0 = non-water)."""
    dataset = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
    permanent = dataset.select("occurrence").gt(90)  # >90% occurrence = permanent
    return permanent.updateMask(permanent).clip(_get_sri_lanka_geometry())

# MAIN FUNCTION
def show(params: dict):
    # st.title("Accumulated Rainfall")

    Map = geemap.Map(center=[7.8, 80.7], zoom=8)

    # ---- Add static local layers ----
    layer_options = {
        "Rivers": "lka_rivers.shp",
        "Roads": "lka_roads.shp",
        "Basins": "lka_basins.shp",
        "Districts": "lka_dis.shp",
        "GNDs": "lka_gnd.shp"
    }

    layer_styles = {
        "Rivers": {"color": "#1E90FF", "weight": 1.2, "fillOpacity": 0},
        "Roads": {"color": "#ECFA22", "weight": 0.8, "fillOpacity": 0},
        "Basins": {"color": "#419490", "weight": 1.0, "fillOpacity": 0},
        "Districts": {"color": "#070606", "weight": 0.8, "fillOpacity": 0},
        "GNDs": {"color": "#A9A9A9", "weight": 0.6, "fillOpacity": 0}
    }

    selected_layers = st.sidebar.multiselect(
        "Select Layers to Display",
        options=list(layer_options.keys()),
        default=["Districts"]
    )

    for lname in selected_layers:
        fpath = _safe_path(DATA_DIR, layer_options[lname])
        if os.path.exists(fpath):
            Map.add_shapefile(
                fpath,
                layer_name=lname,
                style=layer_styles.get(lname, {"color": "#555555", "weight": 0.8, "fillOpacity": 0}),
                shown=True,
            )

    # ---- Add static GEE layers ----
    Map.addLayer(
        _worldcover_2021(),
        {
            "min": 10, "max": 100,
            "palette": [
                "#006400", "#ffbb22", "#ffff4c", "#f096ff", "#fa0000",
                "#b4b4b4", "#f0f0f0", "#0064c8", "#0096a0", "#00cf75",
                "#fae6a0", "#000000", "#f0ffa0", "#a0dcff"
            ],
        },
        "LULC (ESA WorldCover 2021)", False
    )

    Map.addLayer(
        _srtm_dem(),
        {"min": 0, "max": 3000, "palette": ["#000000", "#ffffff"]},
        "Elevation (SRTM)", False
    )

    Map.addLayer(
    _jrc_permanent_water(), 
    {"palette": ["#0000FF"], "opacity": 0.6},
    "Permanent Water (JRC)", False
    )

    # ---- Build AOI ----
    aoi = None
    aoi_label = None

    if params["analysis_type"] == "Administrative":
        # --- Administrative level: District only ---
        dist_gdf = _read_vector(_safe_path(DATA_DIR, "lka_dis.shp"))

        dist_sel = dist_gdf[dist_gdf[COL_DISTRICT] == params.get("district")]
        if not dist_sel.empty:
            aoi = _to_ee_geometry(dist_sel)
            aoi_label = f"{params['district']} District"
        else:
            st.error(f"District '{params.get('district')}' is not found.")

    elif params["analysis_type"] == "Hydrological":
        # --- Hydrological level: Basin only ---
        basins_gdf = _read_vector(_safe_path(DATA_DIR, "lka_basins.shp"))

        basin_sel = basins_gdf[basins_gdf[COL_BASIN] == params.get("basin")]
        if not basin_sel.empty:
            aoi = _to_ee_geometry(basin_sel)
            aoi_label = f"{params['basin']} Basin"
        else:
            st.error(f"Basin '{params.get('basin')}' is not found.")

    # ---- Main analysis ----
    if params.get("run_forecast") and aoi is not None:
        start_date = params["start_date"]
        end_date = params["end_date"]
        temporal_method = params.get("temporal_method", "Sum")

        with st.spinner(
            f"Computing {temporal_method} rainfall for {aoi_label} ({start_date}→{end_date})..."
        ):
            
            Map.addLayer(
                _sentinel1_period_vv(start_date, end_date).clip(aoi),
                {"min": -20, "max": 5, "palette": ["#000000", "#ffffff"]},
                f"Sentinel-1 VV Median ({start_date}–{end_date})",
                False
            )
            
            # ---- Temporal aggregation ----
            rain_img = _rainfall_aggregate(start_date, end_date, temporal_method).clip(aoi)

            # ---- Fixed visualization range ----
            rain_vis = {
                "min": 0,
                "max": 500,  # adjust this range based on expected rainfall intensity
                "palette": ["#ffffff", "#cce5ff", "#66b2ff", "#0066ff", "#001f66"],
            }

            # ---- Add rainfall layer ----
            Map.addLayer(rain_img, rain_vis, f"GPM Rainfall ({temporal_method})")

            # ---- AOI outline ----
            Map.addLayer(
                ee.FeatureCollection(ee.Feature(aoi)).style(
                    color="red", width=1, fillColor="00000000"
                ),
                {},
                f"AOI – {aoi_label}",
            )

            # ---- Static colorbar legend ----
            Map.add_colorbar(
                vis_params=rain_vis,
                label=f"GPM Rainfall ({temporal_method}) [mm]",
                layer_name=f"GPM Rainfall ({temporal_method})",
            )

    # ---- Final map ----
    Map.addLayerControl()
    Map.to_streamlit(height=720)
