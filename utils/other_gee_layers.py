import ee
import geopandas as gpd
import os

def get_sri_lanka_geometry():
    return ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015") \
        .filter(ee.Filter.eq("ADM0_NAME", "Sri Lanka")) \
        .geometry()

# ---------- Earth Engine Layers ----------

def get_worldcover():
    lulc = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
    vis_params = {"min": 10, "max": 100, "palette": ["006400", "00FF00", "ADFF2F", "FFFF00", "FF0000"]}
    return lulc.clip(get_sri_lanka_geometry()), vis_params

def get_dem():
    dem = ee.Image("USGS/SRTMGL1_003")
    vis_params = {"min": 0, "max": 2500, "palette": ["blue", "green", "brown", "white"]}
    return dem.clip(get_sri_lanka_geometry()), vis_params


# ---------- Local Vector Layers ----------

def get_roads_layer(data_dir):
    path = os.path.join(data_dir, "lka_roads.shp")
    return gpd.read_file(path) if os.path.exists(path) else None

def get_rivers_layer(data_dir):
    path = os.path.join(data_dir, "lka_rivers.shp")
    return gpd.read_file(path) if os.path.exists(path) else None

def get_surface_water_layer(data_dir):
    path = os.path.join(data_dir, "surface_water.shp")
    return gpd.read_file(path) if os.path.exists(path) else None

def get_admin_layer(data_dir, analysis_type):
    """Load either district or basin shapefile."""
    if analysis_type == "Administrative":
        shp_path = os.path.join(data_dir, "lka_dis.shp")
        gdf = gpd.read_file(shp_path)
        field = "ADM2_EN"
        color = "red"
    else:
        shp_path = os.path.join(data_dir, "lka_basins.shp")
        gdf = gpd.read_file(shp_path)
        field = "WSHD_NAME"
        color = "blue"
    return gdf, field, color
