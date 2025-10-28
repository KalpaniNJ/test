import os
from datetime import datetime
import ee
import streamlit as st
import geemap.foliumap as geemap
import geopandas as gpd

# ---------- CONFIG ----------
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
COL_DISTRICT = "ADM2_EN"
COL_BASIN = "WSHD_NAME"

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

# ---------- GPM Rainfall Aggregation ----------
def _rainfall_aggregate(start_date: str, end_date: str, temporal_method: str) -> ee.Image:
    """
    Aggregate GPM IMERG rainfall:
      - Sum: total rainfall (mm)
      - Mean: average of daily rainfall
      - Median: median of daily rainfall
    """
    ic_30min = (
        ee.ImageCollection("NASA/GPM_L3/IMERG_V07")
        .filterDate(ee.Date(start_date), ee.Date(end_date))
        .select("precipitation")
    )

    # Convert to daily sums
    daily = ic_30min.map(
        lambda img: img.set(
            "date", img.date().format("YYYY-MM-dd")
        )
    ).map(
        lambda img: ee.ImageCollection(ic_30min.filterDate(img.date(), img.date().advance(1, "day"))).sum()
        .set("system:time_start", img.date().millis())
    )

    # Flatten to one collection
    daily = ee.ImageCollection(daily)

    method = temporal_method.lower()
    if method == "mean":
        img = daily.mean()
    elif method == "median":
        img = daily.median()
    else:
        img = ic_30min.sum()  # total rainfall from all 30-min steps

    return img

# ---------- MAIN FUNCTION ----------
def show(params: dict):
    Map = geemap.Map(center=[7.8, 80.7], zoom=8)

    # ---- Build AOI ----
    aoi = None
    aoi_label = None

    if params["analysis_type"] == "Administrative":
        dist_gdf = _read_vector(_safe_path(DATA_DIR, "lka_dis.shp"))
        dist_sel = dist_gdf[dist_gdf[COL_DISTRICT] == params.get("district")]
        if not dist_sel.empty:
            aoi = _to_ee_geometry(dist_sel)
            aoi_label = f"{params['district']} District"
            Map.add_shapefile(_safe_path(DATA_DIR, "lka_dis.shp"),
                              layer_name="Districts",
                              style={"color": "#3A3B3C", "weight": 0.8, "fillOpacity": 0},
                              shown=True)
        else:
            st.error(f"District '{params.get('district')}' not found.")

    elif params["analysis_type"] == "Hydrological":
        basins_gdf = _read_vector(_safe_path(DATA_DIR, "lka_basins.shp"))
        basin_sel = basins_gdf[basins_gdf[COL_BASIN] == params.get("basin")]
        if not basin_sel.empty:
            aoi = _to_ee_geometry(basin_sel)
            aoi_label = f"{params['basin']} Basin"
            Map.add_shapefile(_safe_path(DATA_DIR, "lka_basins.shp"),
                              layer_name="Basins",
                              style={"color": "#9B5DE0", "weight": 0.8, "fillOpacity": 0},
                              shown=True)
        else:
            st.error(f"Basin '{params.get('basin')}' not found.")

    # ---- Main analysis ----
    if params.get("run_forecast") and aoi is not None:
        start_date = params["start_date"]
        end_date = params["end_date"]
        temporal_method = params.get("temporal_method", "Sum")

        with st.spinner(f"Computing {temporal_method} rainfall for {aoi_label} ({start_date} → {end_date})..."):
            rain_img = _rainfall_aggregate(start_date, end_date, temporal_method).clip(aoi)

            # Visualization parameters
            rain_vis = {
                "min": 0,
                "max": 500,
                "palette": ["#ffffff", "#cce5ff", "#66b2ff", "#0066ff", "#001f66"],
            }

            Map.addLayer(rain_img, rain_vis, f"GPM Rainfall ({temporal_method})")

            # Add colorbar
            Map.add_colorbar(
                vis_params=rain_vis,
                label=f"GPM Rainfall ({temporal_method}) [mm]",
                layer_name=f"GPM Rainfall ({temporal_method})",
                font_size=14,
                label_font_size=16
            )

    Map.addLayerControl()
    Map.to_streamlit(height=720)
