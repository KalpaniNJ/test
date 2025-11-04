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

# ---------- Static layers: load once ----------
@st.cache_resource(show_spinner=False)
def get_static_layers():
    """Load static GEE layers only once for speed."""
    worldcover = (
        ee.ImageCollection("ESA/WorldCover/v200")
        .first()
        .select("Map")
        .clip(_get_sri_lanka_geometry())
    )

    srtm = ee.Image("USGS/SRTMGL1_003").clip(_get_sri_lanka_geometry())

    water = (
        ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
        .select("occurrence")
        .gt(90)
        .updateMask(ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence").gt(90))
        .clip(_get_sri_lanka_geometry())
    )

    return {"worldcover": worldcover, "srtm": srtm, "water": water}
    
# ---------- Rainfall (GPM IMERG V07) ----------
def _rainfall_aggregate(start_date: str, end_date: str, temporal_method: str, aoi=None) -> ee.Image:
    """Aggregate GPM rainfall over time.
    - Sum: total rainfall (mm) from 30-min data
    - Mean: mean rainfall rate (mm/hr)
    - Max: maximum rainfall rate (mm/hr)
    """

    # Load IMERG 30-minute precipitation rate (mm/hr)
    ic = (
        ee.ImageCollection("NASA/GPM_L3/IMERG_V07")
        .filterBounds(aoi)
        .filterDate(ee.Date(start_date), ee.Date(end_date))
        .select("precipitation")
    )
    
    if aoi:
        ic = ic.map(lambda img: img.clip(aoi))

    method = temporal_method.lower()

    if method == "mean":
        # Mean rainfall rate (mm/hr) across period
        img = ic.mean()

    elif method == "max":
        # Maximum rainfall rate (mm/hr) observed in period
        img = ic.max()

    else:
        # Total rainfall (mm): each image represents 0.5 hour of rate (mm/hr)
        img = ic.sum().multiply(0.5)

    # Mask very small or invalid values
    img = img.updateMask(img.gt(0.1))

    return img

# MAIN FUNCTION
def show(params: dict):
    Map = geemap.Map(center=[7.8, 80.7], zoom=7)
    static_layers = get_static_layers()

    # ---- Add static GEE layers ----
    Map.addLayer(static_layers["worldcover"], {"min": 10, "max": 100,
            "palette": [
                "#006400", "#ffbb22", "#ffff4c", "#f096ff", "#fa0000",
                "#b4b4b4", "#f0f0f0", "#0064c8", "#0096a0", "#00cf75",
                "#fae6a0", "#000000", "#f0ffa0", "#a0dcff"
            ],
        }, 
        "LULC (ESA WorldCover 2021)", False
    )

    Map.addLayer(static_layers["srtm"], {"min": 0, "max": 3000,
            "palette": [
                "#2E8B57", "#9ACD32", "#EEE8AA", "#CD853F", "#D2691E", "#A0522D", "#FFFFFF"
            ],
        }, 
        "Elevation (SRTM)", False
    )
    
    Map.addLayer(static_layers["water"], {"palette": ["#0000FF"], "opacity": 0.6}, "Permanent Water (JRC)", False)

    # ---- Build AOI ----
    aoi = None
    aoi_label = None

    if params["analysis_type"] == "Administrative":
        # --- Administrative level: District only ---
        dist_gdf = _read_vector(_safe_path(DATA_DIR, "lka_districts.shp"))

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

    # Main rainfall analysis
    if params.get("run_forecast") and aoi is not None:
        start_date = params["start_date"]
        end_date = params["end_date"]
        temporal_method = params.get("temporal_method", "Sum")
    
        # --- Load and display entire shapefile ---
        if params["analysis_type"] == "Administrative":
            full_gdf = _read_vector(_safe_path(DATA_DIR, "lka_districts.shp")).to_crs(4326)
            layer_name = "District Boundaries"
            aoi_gdf = full_gdf[full_gdf[COL_DISTRICT] == params["district"]]
        else:
            full_gdf = _read_vector(_safe_path(DATA_DIR, "lka_basins.shp")).to_crs(4326)
            layer_name = "River Basins"
            aoi_gdf = full_gdf[full_gdf[COL_BASIN] == params["basin"]]
    
        Map.add_gdf(
            full_gdf,
            layer_name=layer_name,
            style={"color": "#333333", "weight": 0.8, "fillOpacity": 0}
        )
    
        # --- Zoom to AOI bounds only ---
        if not aoi_gdf.empty:
            bounds = aoi_gdf.total_bounds  # [minx, miny, maxx, maxy]
            Map.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        else:
            st.warning(f"Could not find {aoi_label} in shapefile for zooming.")
    
        # --- Proceed with rainfall analysis ---
        with st.spinner(
            f"Computing {temporal_method} rainfall for {aoi_label} ({start_date}→{end_date})..."
        ):
            # --- Choose palette and range dynamically ---
            if temporal_method.lower() == "sum":
                rain_vis = {
                    "min": 0,
                    "max": 500,
                    "palette": ["#ffffff", "#00ffef", "#66b2ff", "#0066ff", "#001f66"],
                }
                legend_label = "Total Rainfall [mm]"
            
            elif temporal_method.lower() == "mean":
                rain_vis = {
                    "min": 0,
                    "max": 10,
                    "palette": ["ffffff", "#f7fcf0", "#ccece6", "#66c2a4", "#238b45", "#00441b"],
                }
                legend_label = "Mean Rainfall Rate [mm/hr]"
            
            elif temporal_method.lower() == "max":
                rain_vis = {
                    "min": 0,
                    "max": 50,
                    "palette": ["ffffff", "#ffffcc", "#ffeda0", "#feb24c", "#f03b20", "#bd0026"],
                }
                legend_label = "Maximum Rainfall Rate [mm/hr]"
            
            else:
                # fallback default
                rain_vis = {
                    "min": 0,
                    "max": 500,
                    "palette": ["#ffffff", "#cce5ff", "#66b2ff", "#0066ff", "#001f66"],
                }
                legend_label = "GPM Rainfall [mm]"
    
            # --- Compute rainfall image ---
            rain_img = _rainfall_aggregate(start_date, end_date, temporal_method, aoi)
    
            Map.addLayer(rain_img, rain_vis, f"GPM Rainfall ({temporal_method})")
            Map.add_colorbar(
                vis_params=rain_vis,
                label=legend_label,
                layer_name=f"GPM Rainfall ({temporal_method})",
                font_size=16,
                label_font_size=18
            )
    
    with st.spinner("Loading map and layers... Please wait."):
        Map.addLayerControl()
        Map.to_streamlit()
