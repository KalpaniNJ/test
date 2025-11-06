import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
from utils import rice_algorithms
from utils.config import AOI_OPTIONS, load_assets   # import AOI_OPTIONS just like in monitoring.py

def show():
    ee.Initialize()

    st.markdown("## 🌾 Rice Mapping - Compare Two Seasons")

    # ---------------- AOI SELECTION ----------------
    aoi_choice = st.selectbox("📍 Select AOI", list(AOI_OPTIONS.keys()))
    aoi_path = AOI_OPTIONS[aoi_choice]
    aoi = ee.FeatureCollection(aoi_path).geometry()   # same pattern as monitoring.py

    # ---------------- SEASON INPUT ----------------
    season_csv = "data/season_dates.csv"
    season_df = pd.read_csv(season_csv)

    col1, col2 = st.columns(2)
    with col1:
        season_left = st.selectbox("🌿 Select Season 1", season_df["season"].unique(), index=0)
    with col2:
        season_right = st.selectbox("🌾 Select Season 2", season_df["season"].unique(), index=1)

    if st.button("Generate Rice Maps"):
        st.info(f"Processing {season_left} and {season_right} for {aoi_choice}...")

        # --- Thresholds (constants for now) ---
        outlier_params = {
            "diff_start_peak": 0.15,
            "diff_peak_harvest": 0.1,
            "q3_start": 0.3,
            "q1_peak": 0.2,
        }

        # --- Season dates lookup ---
        def extract_dates(season_name):
            row = season_df.loc[season_df["season"] == season_name].iloc[0]
            return {"start": row["season_start"], "peak": row["peak_date"], "harvest": row["harvest_date"]}

        dates_left = extract_dates(season_left)
        dates_right = extract_dates(season_right)

        # --- Load assets (roads, water, etc.) ---
        assets = load_assets()

        # Here you would build mosaicCollectionUInt16 and filteredDekadList exactly as in your monitoring.py logic
        # For example:
        # mosaicCollectionUInt16, filteredDekadList = build_mosaic(aoi, dates_left["start"], dates_left["harvest"])

        # --- Run rice mapping for each season ---
        masked_left = rice_algorithms.perform_rice_mapping_onlyrice(aoi, mosaicCollectionUInt16, filteredDekadList, outlier_params, dates_left)
        masked_right = rice_algorithms.perform_rice_mapping_onlyrice(aoi, mosaicCollectionUInt16, filteredDekadList, outlier_params, dates_right)

        # ---------------- SIDE-BY-SIDE MAP DISPLAY ----------------
        col1, col2 = st.columns(2)

        with col1:
            st.subheader(f"{season_left}")
            Map1 = geemap.Map(height=500)
            Map1.addLayer(masked_left, {"palette": ["yellow", "green"], "min": 0, "max": 1}, f"{season_left} Rice")
            Map1.addLayer(aoi, {}, "AOI")
            Map1.to_streamlit(width=500, height=500)

        with col2:
            st.subheader(f"{season_right}")
            Map2 = geemap.Map(height=500)
            Map2.addLayer(masked_right, {"palette": ["yellow", "green"], "min": 0, "max": 1}, f"{season_right} Rice")
            Map2.addLayer(aoi, {}, "AOI")
            Map2.to_streamlit(width=500, height=500)
