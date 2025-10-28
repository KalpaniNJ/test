# modules/rainfall_distribution.py
import folium
import ee
import streamlit as st

def show_rainfall(
    leaflet_map,
    selected_geom,
    wea_start_date,
    wea_end_date,
    temporal_method="Sum"
):
    """
    Fetches and displays GPM rainfall data on the Folium map.

    Args:
        leaflet_map (folium.Map): The existing Folium map object.
        selected_geom (geopandas.GeoDataFrame): The selected administrative/hydrological geometry.
        wea_start_date (datetime.date): Start date for rainfall data.
        wea_end_date (datetime.date): End date for rainfall data.
        temporal_method (str): Aggregation method ('Sum', 'Mean', 'Median').

    Returns:
        folium.Map: The updated Folium map with rainfall layer.
    """

    # --- Convert dates to strings ---
    start_date_str = str(wea_start_date)[:10]
    end_date_str = str(wea_end_date)[:10]

    # --- Load GPM IMERG collection ---
    gpm_collection = ee.ImageCollection("NASA/GPM_L3/IMERG_V06") \
        .filterDate(start_date_str, end_date_str) \
        .select("precipitationCal")

    # --- Define Area of Interest (AOI) ---
    if not selected_geom.empty:
        aoi_geojson = selected_geom.geometry.iloc[0].__geo_interface__
        ee_aoi = ee.Geometry(aoi_geojson)
    else:
        st.info("No specific region selected — showing rainfall for Sri Lanka.")
        ee_aoi = ee.Geometry.Rectangle([79.6, 5.8, 81.9, 9.9])  # Sri Lanka extent

    # --- Aggregate based on temporal method ---
    if temporal_method == "Sum":
        rainfall_image = gpm_collection.sum()
        vis_params = {"min": 0, "max": 500, "palette": ["white", "blue", "purple", "red"]}
        label = "Sum"
    elif temporal_method == "Mean":
        rainfall_image = gpm_collection.mean()
        vis_params = {"min": 0, "max": 20, "palette": ["white", "lightblue", "blue", "darkblue"]}
        label = "Mean"
    elif temporal_method == "Median":
        rainfall_image = gpm_collection.median()
        vis_params = {"min": 0, "max": 20, "palette": ["white", "lightgreen", "green", "darkgreen"]}
        label = "Median"
    else:
        st.error("Invalid aggregation method selected.")
        return leaflet_map

    # --- Clip and visualize ---
    rainfall_image = rainfall_image.clip(ee_aoi)

    try:
        map_id_dict = rainfall_image.getMapId(vis_params)
        tile_url = map_id_dict["tile_fetcher"].url_format

        folium.TileLayer(
            tiles=tile_url,
            attr="NASA GPM IMERG (GEE)",
            name=f"GPM {label} ({start_date_str} → {end_date_str})",
            overlay=True,
            control=True,
            opacity=0.8,
        ).add_to(leaflet_map)

        # --- Optional legend ---
        legend_html = """
        <div style="position: fixed; bottom: 50px; left: 50px; width: 150px; height: 120px;
                    background-color: white; border: 2px solid grey; z-index: 9999;
                    font-size: 12px; text-align: center;">
            <b>Rainfall (mm)</b><br>
            <i style="background:white;width:20px;height:10px;display:inline-block;"></i> 0<br>
            <i style="background:lightblue;width:20px;height:10px;display:inline-block;"></i> 50<br>
            <i style="background:blue;width:20px;height:10px;display:inline-block;"></i> 100<br>
            <i style="background:darkblue;width:20px;height:10px;display:inline-block;"></i> 200+
        </div>
        """
        leaflet_map.get_root().html.add_child(folium.Element(legend_html))

    except Exception as e:
        st.warning(f"⚠️ Could not render GPM rainfall layer: {e}")

    return leaflet_map
