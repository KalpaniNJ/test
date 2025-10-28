# rainfall_distribution.py

import ee
import geemap
import geopandas as gpd
import pandas as pd

# Initialize GEE (make sure authentication is done)
try:
    ee.Initialize()
except Exception:
    ee.Authenticate()
    ee.Initialize()


# ==============================
# RAINFALL DISTRIBUTION FUNCTION
# ==============================

def get_rainfall_distribution(aoi, start_date, end_date, method="Mean"):
    """
    Fetch and aggregate GPM rainfall over the AOI.

    Parameters:
        aoi (ee.Geometry): Area of interest (district or basin)
        start_date (str): Start date (YYYY-MM-DD)
        end_date (str): End date (YYYY-MM-DD)
        method (str): 'Sum', 'Mean', or 'Median'

    Returns:
        ee.Image: Aggregated rainfall image
        float: Aggregated rainfall value over AOI
    """

    # Load GPM dataset
    gpm = ee.ImageCollection("NASA/GPM_L3/IMERG_V06") \
        .filterDate(start_date, end_date) \
        .select("precipitationCal")

    # Temporal aggregation
    if method == "Sum":
        rainfall_image = gpm.sum()
    elif method == "Median":
        rainfall_image = gpm.median()
    else:  # Default Mean
        rainfall_image = gpm.mean()

    # Clip to AOI
    rainfall_image = rainfall_image.clip(aoi)

    # Compute mean rainfall value for AOI (for chart/stats)
    stats = rainfall_image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=10000,
        maxPixels=1e13
    ).getInfo()

    mean_value = stats.get("precipitationCal", None)

    return rainfall_image, mean_value


def aoi_from_shapefile(shapefile_path, filter_field, filter_value):
    """Read GeoDataFrame, filter to feature, and convert to ee.Geometry."""
    gdf = gpd.read_file(shapefile_path)
    geom = gdf[gdf[filter_field] == filter_value].geometry.iloc[0]
    aoi = geemap.geopandas_to_ee(gpd.GeoDataFrame(geometry=[geom]))
    return aoi.geometry()
