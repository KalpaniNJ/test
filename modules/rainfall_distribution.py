# rainfall_distribution.py
import ee
import geopandas as gpd

# ---------- Helper ----------
def _to_ee_geometry(gdf: gpd.GeoDataFrame) -> ee.Geometry:
    """Convert GeoDataFrame to ee.Geometry (merged)."""
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)
    return ee.Geometry(gdf.unary_union.__geo_interface__)

# ---------- GPM Rainfall Aggregation ----------
def _rainfall_aggregate(start_date: str, end_date: str, temporal_method: str) -> ee.Image:
    """
    Aggregate GPM rainfall over time:
    - Sum: total rainfall (30-min data)
    - Mean: mean of daily totals
    - Median: median of daily totals
    """
    ic = (
        ee.ImageCollection("NASA/GPM_L3/IMERG_V07")
        .filterDate(ee.Date(start_date), ee.Date(end_date))
        .select("precipitation")
    )

    method = temporal_method.lower()

    # Compute daily rainfall totals
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


# ---------- function for app.py ----------
def get_rainfall_layer(start_date: str, end_date: str, temporal_method: str, aoi_gdf: gpd.GeoDataFrame):
    """
    Returns a Tile URL for Folium (GEE map tiles).
    """
    aoi = _to_ee_geometry(aoi_gdf)
    rain_img = _rainfall_aggregate(start_date, end_date, temporal_method).clip(aoi)

    vis = {
        "min": 0,
        "max": 500,
        "palette": ["#ffffff", "#cce5ff", "#66b2ff", "#0066ff", "#001f66"],
    }

    map_id_dict = ee.Image(rain_img).getMapId(vis)
    tile_url = map_id_dict["tile_fetcher"].url_format

    return tile_url, f"GPM Rainfall ({temporal_method})"
