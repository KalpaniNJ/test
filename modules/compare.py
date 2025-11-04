import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
from utils import gee_helpers, rice_algorithms
from utils.config import AOI_OPTIONS


def show(params):
    # --- Load season CSV ---
    season_df = pd.read_csv(
        "data/season_dates.csv",
        parse_dates=["start_date", "season_start", "peak_date", "harvest_date", "end_date"]
    )
    season_df["display_name"] = season_df["season"].apply(lambda x: x.replace("-", " ") if isinstance(x, str) else x)

    # --- Layout ---
    col1, col2 = st.columns([0.4, 1.6])
    with col1:
        st.subheader("Select seasons to compare")

        aoi_name = st.selectbox("Select AOI", list(AOI_OPTIONS.keys()), key="compare_aoi")
        aoi = ee.FeatureCollection(AOI_OPTIONS[aoi_name]).geometry()

        season_left = st.selectbox("Select Season", season_df["display_name"].tolist(), key="left_season")
        season_right = st.selectbox("Select Season to compare", season_df["display_name"].tolist(), key="right_season")

    left_row = season_df.loc[season_df["display_name"] == season_left].iloc[0]
    right_row = season_df.loc[season_df["display_name"] == season_right].iloc[0]

    # --- Run comparison ---
    if st.button("Run Season Comparison"):
        with col2:
            with st.spinner("Generating paddy maps for both seasons... this may take several minutes."):

                # Prepare date dictionaries
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

                # --- Left season processing ---
                df_line_left, df_points_left = gee_helpers.get_time_series(
                    aoi=aoi,
                    start_date=str(left_row["start_date"].date()),
                    end_date=str(left_row["end_date"].date())
                )
                outlier_params_left = rice_algorithms.detect_outliers(df_points_left, left_dates)
                mosaic_left, dekads_left = gee_helpers.get_mosaic_collection(
                    aoi=aoi,
                    start_date=str(left_row["start_date"].date()),
                    end_date=str(left_row["end_date"].date())
                )
                paddy_left = rice_algorithms.perform_rice_mapping_onlyrice(
                    aoi=aoi,
                    mosaicCollectionUInt16=mosaic_left,
                    filteredDekadList=dekads_left,
                    outlier_params=outlier_params_left,
                    dates=left_dates
                )

                # --- Right season processing ---
                df_line_right, df_points_right = gee_helpers.get_time_series(
                    aoi=aoi,
                    start_date=str(right_row["start_date"].date()),
                    end_date=str(right_row["end_date"].date())
                )
                outlier_params_right = rice_algorithms.detect_outliers(df_points_right, right_dates)
                mosaic_right, dekads_right = gee_helpers.get_mosaic_collection(
                    aoi=aoi,
                    start_date=str(right_row["start_date"].date()),
                    end_date=str(right_row["end_date"].date())
                )
                paddy_right = rice_algorithms.perform_rice_mapping_onlyrice(
                    aoi=aoi,
                    mosaicCollectionUInt16=mosaic_right,
                    filteredDekadList=dekads_right,
                    outlier_params=outlier_params_right,
                    dates=right_dates
                )

                # --- Create two maps (side-by-side) ---
                aoi_center = aoi.centroid().coordinates().getInfo()

                left_map = geemap.Map(center=[aoi_center[1], aoi_center[0]], zoom=11)
                left_map.add_basemap("SATELLITE")
                left_map.addLayer(paddy_left, {"min": 0, "max": 1, "palette": ["red", "green"]}, season_left)

                right_map = geemap.Map(center=[aoi_center[1], aoi_center[0]], zoom=11)
                right_map.add_basemap("SATELLITE")
                right_map.addLayer(paddy_right, {"min": 0, "max": 1, "palette": ["red", "green"]}, season_right)

                # --- Display maps side-by-side ---
                map_col1, map_col2 = st.columns(2)
                with map_col1:
                    st.markdown(f"### 🌾 {season_left}")
                    left_map.to_streamlit(height=500)
                with map_col2:
                    st.markdown(f"### 🌾 {season_right}")
                    right_map.to_streamlit(height=500)
