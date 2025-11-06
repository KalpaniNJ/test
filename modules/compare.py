import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
from utils import gee_helpers, rice_algorithms
from utils.config import AOI_OPTIONS


def show(params=None):
    # --- Load season CSV ---
    season_df = pd.read_csv(
        "data/season_dates.csv",
        parse_dates=["start_date", "season_start", "peak_date", "harvest_date", "end_date"]
    )
    season_df["display_name"] = season_df["season"].apply(
        lambda x: x.replace("-", " ") if isinstance(x, str) else x
    )

    # --- Layout ---
    col1, col2 = st.columns([0.4, 1.3])

    with col1:
        st.markdown("### Add Seasons to compare")

        aoi_name = st.selectbox("AOI", list(AOI_OPTIONS.keys()), key="compare_aoi")
        aoi = ee.FeatureCollection(AOI_OPTIONS[aoi_name]).geometry()

        season_left = st.selectbox("Add a Season", season_df["display_name"].tolist(), key="left_season")
        season_right = st.selectbox("Add a Season to compare", season_df["display_name"].tolist(), key="right_season")

        run = st.button("Run Comparison", use_container_width=True)

    if run:
        with col2:
            with st.spinner("Generating rice maps for comparison... please wait..."):
    
                # --- Constants ---
                CONSTANT_OUTLIER_PARAMS = {
                    "q3_start": 5000,
                    "q1_peak": 6000,
                    "diff_start_peak": 2000,
                    "diff_peak_harvest": 1000,
                }
    
                # --- Select season info ---
                left_row = season_df.loc[season_df["display_name"] == season_left].iloc[0]
                right_row = season_df.loc[season_df["display_name"] == season_right].iloc[0]
    
                left_dates = {
                    "start": str(left_row["season_start"].date()),
                    "peak": str(left_row["peak_date"].date()),
                    "harvest": str(left_row["harvest_date"].date())
                }
                right_dates = {
                    "start": str(right_row["season_start"].date()),
                    "peak": str(right_row["peak_date"].date()),
                    "harvest": str(right_row["harvest_date"].date())
                }
    
                # --- Retrieve mosaics ---
                mosaic_left, dekads_left = gee_helpers.get_mosaic_collection(
                    aoi=aoi,
                    start_date=str(left_row["start_date"].date()),
                    end_date=str(left_row["end_date"].date())
                )
                mosaic_right, dekads_right = gee_helpers.get_mosaic_collection(
                    aoi=aoi,
                    start_date=str(right_row["start_date"].date()),
                    end_date=str(right_row["end_date"].date())
                )
    
                # --- Perform rice mapping ---
                paddy_left = rice_algorithms.perform_rice_mapping_onlyrice(
                    aoi=aoi,
                    mosaicCollectionUInt16=mosaic_left,
                    filteredDekadList=dekads_left,
                    outlier_params=CONSTANT_OUTLIER_PARAMS,
                    dates=left_dates
                )
    
                paddy_right = rice_algorithms.perform_rice_mapping_onlyrice(
                    aoi=aoi,
                    mosaicCollectionUInt16=mosaic_right,
                    filteredDekadList=dekads_right,
                    outlier_params=CONSTANT_OUTLIER_PARAMS,
                    dates=right_dates
                )
    
                # --- Create single map ---
                center = aoi.centroid().coordinates().getInfo()
                m = geemap.Map(center=[center[1], center[0]], zoom=11)
                m.add_basemap("HYBRID")
    
                # --- Add both season layers ---
                m.addLayer(paddy_left, {"min": 0, "max": 1, "palette": ["#008200"]}, f"{season_left}")
                m.addLayer(paddy_right, {"min": 0, "max": 1, "palette": ["#FFA500"]}, f"{season_right}")
    
                # --- Add a visual overlay of differences ---
                diff = paddy_right.subtract(paddy_left).rename("change_map")
                vis_diff = {"min": -1, "max": 1, "palette": ["red", "gray", "green"]}
                m.addLayer(diff, vis_diff, "Change (Right - Left)")
    
                m.addLayerControl()
    
                st.markdown(f"### 🌿 {season_left} & {season_right} Overlaid")
                m.to_streamlit(height=600)
    
                st.caption("🟩 Green = Left season rice | 🟧 Orange = Right season rice | 🟥/🟩 = change areas | ⬜ = No change")

    else:
        with col2:
            st.markdown("<p style='color:gray;'>Results will appear here after running the analysis.</p>",
                        unsafe_allow_html=True)
