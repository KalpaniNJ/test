import ee
import geopandas as gpd

def _to_ee_geometry(gdf: gpd.GeoDataFrame) -> ee.Geometry:
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    return ee.Geometry(gdf.unary_union.__geo_interface__)

def _rainfall_aggregate(start_date: str, end_date: str, temporal_method: str) -> ee.Image:
    ic = ee.ImageCollection("NASA/GPM_L3/IMERG_V07") \
        .filterDate(ee.Date(start_date), ee.Date(end_date)) \
        .select("precipitation")

    method = temporal_method.lower()

    def daily_sum(date):
        date = ee.Date(date)
        next_day = date.advance(1, "day")
        daily = ic.filterDate(date, next_day).sum()
        return daily.set("system:time_start", date.millis())

    n_days = ee.Date(end_date).difference(ee.Date(start_date), "day").round()
    daily_ic = ee.ImageCollection(
        ee.List.sequence(0, n_days.subtract(1))
        .map(lambda d: daily_sum(ee.Date(start_date).advance(d, "day")))
    )

    if method == "sum":
        img = ic.sum()
    elif method == "mean":
        img = daily_ic.mean()
    elif method == "median":
        img = daily_ic.median()
    else:
        img = ic.sum()

    return img
