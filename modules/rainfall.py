import ee

def get_sri_lanka_geometry():
    """Return Sri Lanka boundary as ee.Geometry."""
    return ee.FeatureCollection("FAO/GAUL_SIMPLIFIED_500m/2015") \
        .filter(ee.Filter.eq("ADM0_NAME", "Sri Lanka")) \
        .geometry()


def get_gpm_rainfall(start_date, end_date, aggregation="Sum"):
    """Fetch and aggregate GPM IMERG rainfall."""
    dataset = ee.ImageCollection("NASA/GPM_L3/IMERG_V07") \
        .filterDate(start_date, end_date) \
        .select("precipitation")

    if aggregation == "Sum":
        image = dataset.sum()
    elif aggregation == "Mean":
        image = dataset.mean()
    elif aggregation == "Median":
        image = dataset.median()
    else:
        image = dataset.sum()

    vis_params = {"min": 0, "max": 300, "palette": ["white", "lightblue", "blue", "darkblue"]}
    return image.clip(get_sri_lanka_geometry()), vis_params
