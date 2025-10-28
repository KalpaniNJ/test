import ee
import geemap
import streamlit as st

def show_rainfall(leaflet_map, selected_geom, start_date, end_date, method):
    """Add GPM rainfall data to a Folium map inside Streamlit."""

    # --- Convert selected AOI (GeoDataFrame) to EE geometry ---
    geojson = selected_geom.__geo_interface__
    aoi = ee.Geometry(geojson["features"][0]["geometry"])

    # --- Load and aggregate GPM rainfall ---
    gpm = ee.ImageCollection("NASA/GPM_L3/IMERG_V06") \
        .filterDate(start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d")) \
        .select("precipitationCal")

    if method == "Sum":
        gpm_img = gpm.sum()
    elif method == "Median":
        gpm_img = gpm.median()
    else:
        gpm_img = gpm.mean()

    gpm_img = gpm_img.clip(aoi)

    # --- Visualization parameters ---
    vis_params = {
        "min": 0,
        "max": 300,
        "palette": ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]
    }

    # --- Add image layer safely using geemap's folium_add() ---
    try:
        geemap.folium_add(
            ee_object=gpm_img,
            map_object=leaflet_map,
            vis_params=vis_params,
            name=f"GPM {method} ({start_date}–{end_date})"
        )
    except Exception as e:
        st.error(f"⚠️ Unable to render rainfall layer: {e}")
        return leaflet_map

    # --- Add legend (optional) ---
    try:
        legend_dict = {
            "0 mm": "#f7fbff",
            "50 mm": "#c6dbef",
            "100 mm": "#6baed6",
            "200 mm": "#2171b5",
            "300+ mm": "#08306b"
        }
        leaflet_map.add_child(geemap.folium_legend(legend_dict=legend_dict, position="bottomright"))
    except Exception:
        pass

    return leaflet_map
