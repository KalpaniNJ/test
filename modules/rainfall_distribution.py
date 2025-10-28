import ee
import streamlit as st

def calculate_rainfall_sum(selected_geom, start_date, end_date):
    """
    Calculate total rainfall (mm) over the selected AOI and period using GPM IMERG.
    """
    # Convert AOI to EE geometry
    if selected_geom is None or selected_geom.empty:
        st.warning("⚠️ No region selected — cannot calculate rainfall.")
        return None

    geojson = selected_geom.to_json()
    aoi = ee.Geometry(geojson["features"][0]["geometry"])

    # Load GPM IMERG Daily data
    gpm = ee.ImageCollection("NASA/GPM_L3/IMERG_V06") \
        .filterDate(str(start_date)[:10], str(end_date)[:10]) \
        .select("precipitationCal")

    # Compute total rainfall sum (in mm)
    rainfall_sum = gpm.sum().clip(aoi)

    # Reduce to a single value (mean rainfall over area)
    stats = rainfall_sum.reduceRegion(
        reducer=ee.Reducer.mean(),  # Mean rainfall in AOI (mm)
        geometry=aoi,
        scale=10000,                # 10 km resolution
        maxPixels=1e9
    )

    # Convert to client-side value
    result = stats.getInfo()

    if result and "precipitationCal" in result:
        total_mm = result["precipitationCal"]
        return round(total_mm, 2)
    else:
        st.warning("⚠️ Could not compute rainfall. Try a different period or AOI.")
        return None
