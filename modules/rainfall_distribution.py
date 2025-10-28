# modules/rainfall_distribution.py

import ee
import folium
import geopandas as gpd
import streamlit as st
import geemap.foliumap as geemap


def show(params):
    """
    Display GPM IMERG V07 rainfall for selected AOI and period.
    Uses geemap.ee_tile_layer() for fast rendering.
    """

    analysis_type = params.get("analysis_type")
    district = params.get("district")
    basin = params.get("basin")
    temporal_method = params.get("temporal_method")
    start_date = params.get("start_date")
    end_date = params.get("end_date")

    # -----------------------------
    # Base map setup (no default tiles)
    # -----------------------------
    leaflet_map = folium.Map(location=[7.8731, 80.7718], zoom_start=7, tiles=None)
    folium.TileLayer("OpenStreetMap", name="OSM Streets").add_to(leaflet_map)
    folium.TileLayer("Esri.WorldImagery", name="Satellite", show=False).add_to(leaflet_map)

    # -----------------------------
    # Load AOI geometry
    # -----------------------------
    data_dir = "data"
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

        # Handle MultiPolygon or empty geometry safely
        if selected_geom.empty:
            st.warning("⚠️ Selected AOI not found in shapefile.")
            return None
        geom = selected_geom.geometry.values[0]
        if geom.geom_type == "MultiPolygon":
            geom = list(geom.geoms)[0]
        ee_geom = ee.Geometry.Polygon(geom.exterior.coords[:])
    except Exception as e:
        st.error(f"Error reading AOI: {e}")
        return None

    # -----------------------------
    # Fetch and aggregate GPM data
    # -----------------------------
    try:
        gpm = ee.ImageCollection("NASA/GPM_L3/IMERG_V07") \
            .filterDate(start_date, end_date) \
            .select("precipitation")

        # Apply temporal aggregation
        if temporal_method == "Sum":
            rainfall_img = gpm.sum()
            agg_label = "Total Rainfall (mm)"
        elif temporal_method == "Mean":
            rainfall_img = gpm.mean()
            agg_label = "Mean Daily Rainfall (mm)"
        elif temporal_method == "Median":
            rainfall_img = gpm.median()
            agg_label = "Median Daily Rainfall (mm)"
        else:
            rainfall_img = gpm.mean()
            agg_label = "Mean Daily Rainfall (mm)"

        # Clip to AOI
        rainfall_img = rainfall_img.clip(ee_geom)

        # Visualization parameters
        vis_params = {
            "min": 0,
            "max": 100 if temporal_method == "Sum" else 50,
            "palette": ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"]
        }

        # -----------------------------
        # ✅ Use geemap.ee_tile_layer() (faster than getMapId)
        # -----------------------------
        rainfall_layer = geemap.ee_tile_layer(
            rainfall_img, vis_params, f"GPM {agg_label} ({start_date} → {end_date})"
        )
        rainfall_layer.add_to(leaflet_map)

        # Add boundary overlay
        folium.GeoJson(
            selected_geom.to_json(),
            name=f"{district or basin}",
            style_function=lambda x: {"color": color, "weight": 2, "fillOpacity": 0.05},
        ).add_to(leaflet_map)
        leaflet_map.fit_bounds(selected_geom.total_bounds.tolist())

        # Add layer control
        folium.LayerControl(position="topright", collapsed=False).add_to(leaflet_map)

        # Optional: mean rainfall summary
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
        st.error(f"⚠️ Error fetching rainfall data: {e}")
        return None
