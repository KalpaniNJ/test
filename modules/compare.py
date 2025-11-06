import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
from utils import gee_helpers, rice_algorithms
from utils.config import AOI_OPTIONS


def show(params=None):
    # st.subheader("🌾 Compare Seasonal Rice Maps (Side-by-Side)")

    # --- Load season CSV ---
    season_df = pd.read_csv(
        "data/season_dates.csv",
        parse_dates=["start_date", "season_start", "peak_date", "harvest_date", "end_date"]
    )
    season_df["display_name"] = season_df["season"].apply(
        lambda x: x.replace("-", " ") if isinstance(x, str) else x
    )

    # --- Layout controls ---
    col1, _ = st.columns([0.4, 1.6])
    with col1:
        st.markdown("#### Select Seasons")

        aoi_name = st.selectbox("AOI", list(AOI_OPTIONS.keys()), key="compare_aoi")
        aoi = ee.FeatureCollection(AOI_OPTIONS[aoi_name]).geometry()

        season_left = st.selectbox("Left Season", season_df["display_name"].tolist(), key="left_season")
        season_right = st.selectbox("Right Season", season_df["display_name"].tolist(), key="right_season")

    left_row = season_df.loc[season_df["display_name"] == season_left].iloc[0]
    right_row = season_df.loc[season_df["display_name"] == season_right].iloc[0]

    if st.button("Run Comparison"):
        with st.spinner("Generating maps... this may take a few minutes."):

            # --- Prepare constants ---
            CONSTANT_OUTLIER_PARAMS = {
                "q3_start": 5000,
                "q1_peak": 6000,
                "diff_start_peak": 2000,
                "diff_peak_harvest": 1000,
            }

            # --- Prepare dates ---
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

            # --- Left Season ---
            mosaic_left, dekads_left = gee_helpers.get_mosaic_collection(
                aoi=aoi,
                start_date=str(left_row["start_date"].date()),
                end_date=str(left_row["end_date"].date())
            )
            paddy_left = rice_algorithms.perform_rice_mapping_onlyrice(
                aoi=aoi,
                mosaicCollectionUInt16=mosaic_left,
                filteredDekadList=dekads_left,
                outlier_params=CONSTANT_OUTLIER_PARAMS,
                dates=left_dates
            )

            # --- Right Season ---
            mosaic_right, dekads_right = gee_helpers.get_mosaic_collection(
                aoi=aoi,
                start_date=str(right_row["start_date"].date()),
                end_date=str(right_row["end_date"].date())
            )
            paddy_right = rice_algorithms.perform_rice_mapping_onlyrice(
                aoi=aoi,
                mosaicCollectionUInt16=mosaic_right,
                filteredDekadList=dekads_right,
                outlier_params=CONSTANT_OUTLIER_PARAMS,
                dates=right_dates
            )

            # --- Center point for both maps ---
            center = aoi.centroid().coordinates().getInfo()

            # --- Left Map ---
            left_map = geemap.Map(center=[center[1], center[0]], zoom=11)
            left_map.add_basemap("SATELLITE")
            left_map.addLayer(paddy_left, {"min": 0, "max": 1, "palette": ["red", "green"]}, season_left)

            # --- Right Map ---
            right_map = geemap.Map(center=[center[1], center[0]], zoom=11)
            right_map.add_basemap("SATELLITE")
            right_map.addLayer(paddy_right, {"min": 0, "max": 1, "palette": ["red", "green"]}, season_right)

            # --- Display maps side-by-side ---
            map_col1, map_col2 = st.columns(2)
            with map_col1:
                st.markdown(f"### 🌾 {season_left}")
                left_map.to_streamlit(height=550)
            with map_col2:
                st.markdown(f"### 🌾 {season_right}")
                right_map.to_streamlit(height=550)

        st.caption("Green = Rice | Red = Non-rice")
