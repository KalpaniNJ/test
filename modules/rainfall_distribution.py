import ee
import folium
import streamlit as st
from datetime import date

def show_rainfall(leaflet_map, start_date, end_date):
    """
    Compute total rainfall (mm) over Sri Lanka for the selected period
    and visualize it on the Folium map.

    Args:
        leaflet_map (folium.Map): base map object
        start_date (date): start date
        end_date (date): end date
    """

    # Define Sri Lanka boundary (rough bounding box)
    sri_lanka = ee.Geometry.Rectangle([79.6, 5.8, 81.9, 9.9])

    # Load GPM IMERG Daily data
    gpm = ee.ImageCollection("NASA/GPM_L3/IMERG_V06") \
        .filterDate(str(start_date), str(end_date)) \
        .select("precipitationCal")

    # Compute total rainfall (sum) for the period
    total_rainfall = gpm.sum().clip(sri_lanka)

    # Visualization parameters
    vis_params = {
        "min": 0,
        "max": 800,
        "palette": [
            "white", "lightblue", "blue",
            "purple", "magenta", "red", "darkred"
        ]
    }

    # Create tile layer from Earth Engine
    map_id = total_rainfall.getMapId(vis_params)
    tile_url = map_id["tile_fetcher"].url_format

    # Add to Folium map
    folium.TileLayer(
        tiles=tile_url,
        name=f"GPM Total Rainfall ({start_date} → {end_date})",
        attr="NASA GPM IMERG via Google Earth Engine",
        overlay=True,
        control=True,
        opacity=0.85
    ).add_to(leaflet_map)

    # Center map on Sri Lanka
    leaflet_map.fit_bounds([[5.8, 79.6], [9.9, 81.9]])

    # ---- Calculate and display summary ----
    stats = total_rainfall.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=sri_lanka,
        scale=10000,
        maxPixels=1e9
    ).getInfo()

    if stats and "precipitationCal" in stats:
        mean_rainfall = stats["precipitationCal"]
        st.success(f"🌧️ **Average Rainfall (mm):** {mean_rainfall:.2f}")
    else:
        st.warning("⚠️ Could not compute rainfall statistics.")

    return leaflet_map
