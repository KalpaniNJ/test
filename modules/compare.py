import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
from utils import rice_algorithms
from utils.config import load_assets


def show():
    # -------------------- Load AOI and Season Inputs --------------------
    aoi_choice = st.selectbox("📍 Select AOI", list(AOI_OPTIONS.keys()))
    aoi_path = AOI_OPTIONS[aoi_choice]
    aoi = ee.FeatureCollection(aoi_path).geometry()  # ✅ matches monitoring.py pattern

    # CSV containing seasonal dates
    SEASON_CSV = "data/season_dates.csv"
    season_df = pd.read_csv(SEASON_CSV)
    
    col_aoi, col1, col2 = st.columns(3)
    
    with col1:
            aoi_option = st.selectbox("Select AOI", list(AOI_OPTIONS.keys()), key="aoi_cmp")
    
    with col1:
        season1 = st.selectbox("🌿 Select Season 1", season_df["season"].unique(), index=0)
    
    with col2:
        season2 = st.selectbox("🌾 Select Season 2", season_df["season"].unique(), index=1)
    
    
    # ---------------------------------------------------------
    # FIXED PARAMETERS
    # ---------------------------------------------------------
    outlier_params = {
        "diff_start_peak": 0.08,
        "diff_peak_harvest": 0.06,
        "q3_start": 0.45,
        "q1_peak": 0.55
    }
    
    # Load your Sentinel-1 mosaic and dekad list
    mosaicCollectionUInt16 = ee.ImageCollection("projects/ricemapping-475407/assets/mRVI_dekadal_mosaic")
    filteredDekadList = mosaicCollectionUInt16.aggregate_array("dekad")
    
    # ---------------------------------------------------------
    # HELPER: Get Dates for Selected Season
    # ---------------------------------------------------------
    def get_dates_for_season(season_name):
        row = season_df.loc[season_df["season"] == season_name].iloc[0]
        return {
            "start": pd.to_datetime(row["season_start"]).strftime("%Y-%m-%d"),
            "peak": pd.to_datetime(row["peak_date"]).strftime("%Y-%m-%d"),
            "harvest": pd.to_datetime(row["harvest_date"]).strftime("%Y-%m-%d"),
            "end": pd.to_datetime(row["end_date"]).strftime("%Y-%m-%d"),
        }
    
    dates1 = get_dates_for_season(season1)
    dates2 = get_dates_for_season(season2)
    
    # ---------------------------------------------------------
    # EXECUTE RICE MAPPING
    # ---------------------------------------------------------
    run_button = st.button("🚀 Run Seasonal Comparison")
    
    if run_button:
        with st.spinner("Running rice classification for both seasons..."):
    
            maskedPaddyClassification_left = rice_algorithms.perform_rice_mapping_onlyrice(
                aoi, mosaicCollectionUInt16, filteredDekadList, outlier_params, dates1
            )
    
            maskedPaddyClassification_right = rice_algorithms.perform_rice_mapping_onlyrice(
                aoi, mosaicCollectionUInt16, filteredDekadList, outlier_params, dates2
            )
    
        st.success("✅ Classification complete! Visualizing results...")
    
        # ---------------------------------------------------------
        # VISUALIZATION
        # ---------------------------------------------------------
        st.markdown("### 🗺️ Paddy Map Comparison")
    
        col_map1, col_map2 = st.columns(2)
    
        with col_map1:
            st.subheader(f"🟢 {season1} ({aoi_choice})")
            Map1 = geemap.Map(height=500)
            Map1.centerObject(aoi, 10)
            Map1.addLayer(
                maskedPaddyClassification_left,
                {"palette": ["#ffff99", "#33cc33"], "min": 0, "max": 1},
                f"{season1} Rice"
            )
            Map1.addLayer(aoi, {"color": "black"}, "AOI")
            Map1.add_colorbar_branca(
                colors=["#ffff99", "#33cc33"],
                vmin=0,
                vmax=1,
                caption="Rice Probability"
            )
            Map1.to_streamlit(width=500, height=500)
    
        with col_map2:
            st.subheader(f"🔵 {season2} ({aoi_choice})")
            Map2 = geemap.Map(height=500)
            Map2.centerObject(aoi, 10)
            Map2.addLayer(
                maskedPaddyClassification_right,
                {"palette": ["#ff9999", "#0066ff"], "min": 0, "max": 1},
                f"{season2} Rice"
            )
            Map2.addLayer(aoi, {"color": "black"}, "AOI")
            Map2.add_colorbar_branca(
                colors=["#ff9999", "#0066ff"],
                vmin=0,
                vmax=1,
                caption="Rice Probability"
            )
            Map2.to_streamlit(width=500, height=500)
    
        # ---------------------------------------------------------
        # FOOTER
        # ---------------------------------------------------------
        st.markdown(f"""
        ---
        #### 📘 Notes
        - AOI selected: **{aoi_choice}**
        - Seasons compared: **{season1}** vs **{season2}**
        - Thresholds used:  
          - `diff_start_peak`: {outlier_params["diff_start_peak"]}  
          - `diff_peak_harvest`: {outlier_params["diff_peak_harvest"]}  
          - `q3_start`: {outlier_params["q3_start"]}  
          - `q1_peak`: {outlier_params["q1_peak"]}
        """)

    else:
        st.info("👈 Select AOI and two seasons, then click **Run Seasonal Comparison** to begin.")
