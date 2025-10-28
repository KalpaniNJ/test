import ee
import folium
import streamlit as st

# Initialize Earth Engine (safe for Streamlit Cloud)
if "ee_initialized" not in st.session_state:
    try:
        ee.Initialize()
    except Exception:
        ee.Authenticate()
        ee.Initialize()
    st.session_state["ee_initialized"] = True


def show_rainfall_v7(leaflet_map, selected_date):
    """
    Display GPM V7 30-minute precipitation data (max over day)
    for the given date on the provided Folium map.
    """
    try:
        # Define Sri Lanka bounding box
        sri_lanka = ee.Geometry.Rectangle([79.6, 5.8, 81.9, 9.9])

        # ---- Load GPM V7 IMERG data ----
        date_range = ee.Date(selected_date).getRange("day")
        dataset = ee.ImageCollection("NASA/GPM_L3/IMERG_V07") \
            .filter(ee.Filter.date(date_range))

        # ---- Process precipitation ----
        precipitation = dataset.select("precipitation").max()
        mask = precipitation.gt(0.5)
        precipitation = precipitation.updateMask(mask).clip(sri_lanka)

        # ---- Visualization parameters ----
        palette = [
            "000096", "0064ff", "00b4ff", "33db80", "9beb4a",
            "ffeb00", "ffb300", "ff6400", "eb1e00", "af0000"
        ]
        vis_params = {"min": 0, "max": 15, "palette": palette}

        # ---- Create Earth Engine Tile Layer ----
        map_id_dict = ee.data.getMapId({
            "image": precipitation.visualize(**vis_params)
        })
        tile_url = map_id_dict["tile_fetcher"]["url_format"]

        # ---- Add GPM layer to map ----
        folium.TileLayer(
            tiles=tile_url,
            name=f"GPM IMERG V7 Precipitation ({selected_date})",
            attr="NASA GPM IMERG (via Google Earth Engine)",
            overlay=True,
            control=True,
            opacity=0.85
        ).add_to(leaflet_map)

        # Center map on Sri Lanka
        leaflet_map.fit_bounds([[5.8, 79.6], [9.9, 81.9]])

        st.success(f"✅ Displaying GPM IMERG V7 data for {selected_date}")
        return leaflet_map

    except Exception as e:
        st.error(f"⚠️ Unable to load GPM data: {e}")
        return leaflet_map
