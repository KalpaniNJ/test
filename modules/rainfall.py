# Rainfall.py
import streamlit as st
import ee
import geemap.foliumap as geemap
import geopandas as gpd
import pandas as pd
import os, json
from shapely.geometry import mapping

# =====================================
# RAINFALL DISTRIBUTION MODULE
# =====================================
def rainfall_module():
    st.markdown("### 🌧️ Rainfall Distribution")

    # Initialize Earth Engine
    try:
        ee.Initialize()
    except Exception:
        ee.Authenticate()
        ee.Initialize()

    # ---------- Sidebar / Left Controls ----------
    col1, col2 = st.columns([0.9, 3.1])

    with col1:
        analysis_type = st.radio(
            "Select Analysis Type",
            ["Administrative", "Hydrological"],
            horizontal=True
        )

        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

        # Load shapefile based on selection
        if analysis_type == "Administrative":
            shp_path = os.path.join(data_dir, "lka_dis.shp")
            gdf = gpd.read_file(shp_path)
            names = sorted(gdf["ADM2_EN"].unique())
            selected_name = st.selectbox("Select District", names)
            filter_field = "ADM2_EN"
            color = "red"
        else:
            shp_path = os.path.join(data_dir, "lka_basins.shp")
            gdf = gpd.read_file(shp_path)
            names = sorted(gdf["WSHD_NAME"].unique())
            selected_name = st.selectbox("Select Basin", names)
            filter_field = "WSHD_NAME"
            color = "blue"

        temporal_method = st.radio(
            "Temporal Aggregation",
            ["Sum", "Mean", "Median"],
            horizontal=True
        )

        wea_start_date = st.date_input("From", pd.to_datetime("2025-01-01"))
        wea_end_date = st.date_input("To", pd.to_datetime("2025-01-31"))

        run_rainfall = st.button("Apply Layers")

    # ---------- Map Display (Right Side) ----------
    with col2:
        # Create a geemap map (faster than folium for EE)
        Map = geemap.Map(center=[7.8731, 80.7718], zoom=7)
        Map.add_basemap("HYBRID")
        Map.add_basemap("OpenStreetMap")

        if run_rainfall:
            selected_geom = gdf[gdf[filter_field] == selected_name]

            with st.spinner("Fetching and rendering GPM rainfall data..."):
                # Convert shapely polygon to EE geometry
                region = ee.Geometry.Polygon(mapping(selected_geom.geometry.values[0])["coordinates"])

                # Load GPM IMERG V07 dataset
                dataset = ee.ImageCollection("NASA/GPM_L3/IMERG_V07") \
                    .filterDate(str(wea_start_date), str(wea_end_date)) \
                    .select("precipitationCal")

                # Apply temporal aggregation
                if temporal_method == "Sum":
                    rainfall_img = dataset.sum()
                elif temporal_method == "Mean":
                    rainfall_img = dataset.mean()
                else:
                    rainfall_img = dataset.median()

                rainfall_img = rainfall_img.clip(region)

                vis_params = {
                    "min": 0,
                    "max": 200,
                    "palette": ["white", "lightblue", "blue", "green", "yellow", "orange", "red"]
                }

                # Add the rainfall layer to the map
                Map.addLayer(rainfall_img, vis_params, f"GPM Rainfall ({temporal_method})")
                Map.add_colorbar(vis_params, label="Rainfall (mm)", orientation="horizontal")

                # Add boundary overlay
                Map.add_gdf(selected_geom, layer_name=selected_name, style={"color": color, "fillOpacity": 0.0})
                Map.centerObject(region, zoom=8)

        # Render the map in Streamlit
        Map.to_streamlit(height=650)
