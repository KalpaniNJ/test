# rainfall_distribution.py

import ee
import geemap
import geopandas as gpd
import pandas as pd

# ==========================================================
# 1️⃣ Convert Shapefile AOI to Earth Engine Geometry
# ==========================================================
def get_ee_aoi(geojson_feature):
    """Convert a GeoJSON feature to ee.Geometry."""
    geom = ee.Geometry(geojson_feature["features"][0]["geometry"])
    return geom


# ==========================================================
# 2️⃣ Fetch and Aggregate GPM Rainfall Data
# ==========================================================
def get_gpm_rainfall(aoi, start_date, end_date, method="Mean"):
    """
    Fetches and aggregates NASA GPM IMERG rainfall for the AOI and date range.

    Parameters:
        aoi (ee.Geometry): Area of interest
        start_date (str): Start date (YYYY-MM-DD)
        end_date (str): End date (YYYY-MM-DD)
        method (str): 'Sum', 'Mean', or 'Median'

    Returns:
        ee.Image: Aggregated rainfall image (mm)
    """
    gpm = ee.ImageCollection("NASA/GPM_L3/IMERG_V06") \
        .filterDate(start_date, end_date) \
        .select("precipitationCal")

    if method == "Sum":
        img = gpm.sum()
    elif method == "Median":
        img = gpm.median()
    else:
        img = gpm.mean()

    img = img.clip(aoi)
    return img


# ==========================================================
# 3️⃣ Add Rainfall Layer to Folium Map
# ==========================================================
def show_rainfall(leaflet_map, selected_geom, start_date, end_date, method):
    """
    Adds GPM rainfall layer on the given Folium map.

    Parameters:
        leaflet_map (folium.Map): Map object from Streamlit
        selected_geom (GeoDataFrame): Selected district or basin (single feature)
        start_date, end_date (datetime.date): User-selected range
        method (str): 'Sum', 'Mean', or 'Median'
    """

    # Convert GeoDataFrame to EE geometry
    geojson = selected_geom.__geo_interface__
    aoi = get_ee_aoi(geojson)

    # Prepare GPM image
    gpm_img = get_gpm_rainfall(
        aoi,
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
        method
    )

    # Visualization style
    vis_params = {
        "min": 0,
        "max": 300,
        "palette": ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]
    }

    # Add to Folium map
    geemap.ee_tile_layer(
        gpm_img,
        vis_params,
        name=f"GPM {method} ({start_date}–{end_date})"
    ).add_to(leaflet_map)

    return leaflet_map

