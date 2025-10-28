# modules/rainfall_distribution.py

import ee
import folium
import geopandas as gpd
import streamlit as st


def show(params):
    """
    Display GPM IMERG V07 rainfall for the selected AOI and time range.
    Handles aggregation options: Sum, Mean, or Median.
    """

    analysis_type = params.get("analysis_type")
    district = params.get("district")
    basin = params.get("basin")
    temporal_method = params.get("temporal_method")
    start_date = params.get("start_date")
    end_date = params.get("end_date")

    # -----------------------------
    # Base map setup
    # -----------------------------
    leaflet_map = folium.Map(location=[7.8731, 80.7718], zoom_start=7, tiles=None)
    folium.TileLayer("OpenStreetMap", name="OSM Streets").add_to(leaflet_map)
    folium.TileLayer("Stamen Terrain", name="Terrain").add_to(leaflet_map)
    folium.TileLayer("Esri.WorldImagery", name="Satellite", show=False).add_to(leaflet_map)

    # -----------------------------
    # Load AOI geometry
    # -----------------------------
    data_dir = "data"  # adjust if needed
    selected_geom = None
    color = "red"

    try:
        if analysis_type == "Administrative" and district:
            gdf = gpd.read_file(f"{data_dir}/lka_dis.shp")
            selected_geom = gdf[gdf["ADM2_EN"] == district]
            color = "red"
        elif analysis_type == "Hydrological" and basin:
            gdf = gpd.read_file(f"{data_dir}/lka_basins.shp")
            selected_geom = gdf[gdf["WSHD_NAME"] == basin]
            color = "blue"
    except Exception as e:
        st.error(f"⚠️ Could not load shapefile: {e}")
        return None

    # -----------------------------
    # Fetch and process GPM data
    # -----------------------------
    try:
        # Load GPM IMERG V07 (30-minute precipitation)
        gpm = ee.ImageCollection("NASA/GPM_L3/IMERG_V07") \
            .filterDate(start_date, end_date) \
            .select("precipitation")

        # ----- Temporal aggregation -----
        if temporal_method == "Sum":
            # Sum of all 30-minute rainfall values in period
            rainfall_img = gpm.sum()
            agg_label = "Total Rainfall (mm)"
        elif temporal_method == "Mean":
            # Average of daily rainfall (mean)
            rainfall_img = gpm.mean()
            agg_label = "Mean Daily Rainfall (mm)"
        elif temporal_method == "Median":
            # Median daily rainfall
            rainfall_img = gpm.median()
            agg_label = "Median Daily Rainfall (mm)"
        else:
            rainfall_img = gpm.mean()
            agg_label = "Mean Daily Rainfall (mm)"

        # Clip to AOI if available
        if selected_geom is not None:
            ee_geom = ee.Geometry.Polygon(selected_geom.geometry.values[0].exterior.coords[:])
            rainfall_img = rainfall_img.clip(ee_geom)
        else:
            ee_geom = None

        # Visualization
        vis_params = {
            "min": 0,
            "max": 100 if temporal_method == "Sum" else 50,
            "palette": ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]
        }

        # Get tile URL
        map_id_dict = rainfall_img.getMapId(vis_params)
        tile_url = map_id_dict["tile_fetcher"].url_format

        # Add GPM overlay
        folium.TileLayer(
            tiles=tile_url,
            name=f"GPM {agg_label} ({start_date} → {end_date})",
            attr="NASA GPM IMERG V07",
            overlay=True,
            control=True,
            opacity=0.75,
        ).add_to(leaflet_map)

        # Add AOI boundary overlay
        if selected_geom is not None:
            folium.GeoJson(
                selected_geom.__geo_interface__,
                name=f"{district or basin}",
                style_function=lambda x: {"color": color, "weight": 2, "fillOpacity": 0.05},
            ).add_to(leaflet_map)
            leaflet_map.fit_bounds(selected_geom.total_bounds.tolist())

        # Add layer control
        folium.LayerControl(position="topright", collapsed=False).add_to(leaflet_map)

        # ----- Compute summary statistic -----
        if ee_geom is not None:
            stats = rainfall_img.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=ee_geom,
                scale=10000,
                maxPixels=1e13
            ).get("precipitation").getInfo()

            if stats is not None:
                st.success(f"🌧️ {agg_label} over {district or basin}: {stats:.2f} mm")

        return leaflet_map

    except Exception as e:
        st.error(f"⚠️ Error loading GPM rainfall data: {e}")
        return None
