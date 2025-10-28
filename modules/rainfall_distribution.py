import ee
import folium
import streamlit as st

def show_rainfall(leaflet_map, selected_geom, start_date, end_date, method):
    """Add GPM rainfall layer to a Folium map (Streamlit-safe)."""

    # --- Convert AOI ---
    geojson = selected_geom.__geo_interface__
    aoi = ee.Geometry(geojson["features"][0]["geometry"])

    # --- Fetch GPM IMERG ---
    gpm = ee.ImageCollection("NASA/GPM_L3/IMERG_V06") \
        .filterDate(start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d")) \
        .select("precipitationCal")

    # --- Aggregate by user-selected method ---
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

    # --- Safe conversion to Folium tile layer ---
    try:
        map_id = gpm_img.getMapId(vis_params)
        folium.TileLayer(
            tiles=map_id["tile_fetcher"].url_format,
            attr="NASA GPM IMERG",
            name=f"GPM {method} ({start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')})",
            overlay=True,
            control=True,
            opacity=0.8
        ).add_to(leaflet_map)

        # --- Optional legend ---
        legend_html = """
        <div style="
            position: fixed; 
            bottom: 50px; left: 50px; width: 150px; height: 120px; 
            background-color: white; border:2px solid grey; z-index:9999; font-size:12px;
            text-align:center;">
            <b>Rainfall (mm)</b><br>
            <i style="background:#f7fbff;width:20px;height:10px;display:inline-block;"></i> 0<br>
            <i style="background:#c6dbef;width:20px;height:10px;display:inline-block;"></i> 50<br>
            <i style="background:#6baed6;width:20px;height:10px;display:inline-block;"></i> 100<br>
            <i style="background:#2171b5;width:20px;height:10px;display:inline-block;"></i> 200<br>
            <i style="background:#08306b;width:20px;height:10px;display:inline-block;"></i> 300+
        </div>
        """
        leaflet_map.get_root().html.add_child(folium.Element(legend_html))

    except Exception as e:
        st.error(f"⚠️ Unable to render rainfall layer: {e}")

    return leaflet_map
