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

    # --- Layout: Left (inputs) | Right (maps) ---
    col_left, col_right = st.columns([0.35, 0.65])

    with col_left:
        st.markdown("### ⚙️ Compare Seasons")

        aoi_name = st.selectbox("AOI", list(AOI_OPTIONS.keys()), key="compare_aoi")
        aoi = ee.FeatureCollection(AOI_OPTIONS[aoi_name]).geometry()

        season_left = st.selectbox("Left Season", season_df["display_name"].tolist(), key="left_season")
        season_right = st.selectbox("Right Season", season_df["display_name"].tolist(), key="right_season")

        run = st.button("Run Comparison", use_container_width=True)

    if run:
        with st.spinner("🛰️ Generating rice maps... please wait a few minutes."):

            CONSTANT_OUTLIER_PARAMS = {
                "q3_start": 5000,
                "q1_peak": 6000,
                "diff_start_peak": 2000,
                "diff_peak_harvest": 1000,
            }

            left_row = season_df.loc[season_df["display_name"] == season_left].iloc[0]
            right_row = season_df.loc[season_df["display_name"] == season_right].iloc[0]

            # --- Prepare date dictionaries ---
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

            # --- Get mosaics ---
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

            # --- Map center ---
            center = aoi.centroid().coordinates().getInfo()

            # --- Create maps separately ---
            left_map = geemap.Map(center=[center[1], center[0]], zoom=11)
            left_map.add_basemap("HYBRID")
            left_map.addLayer(paddy_left, {"min": 0, "max": 1, "palette": ["red", "green"]}, season_left)

            right_map = geemap.Map(center=[center[1], center[0]], zoom=11)
            right_map.add_basemap("HYBRID")
            right_map.addLayer(paddy_right, {"min": 0, "max": 1, "palette": ["red", "green"]}, season_right)

            # --- Render both maps side-by-side inside the right column ---
            with col_right:
                st.markdown(f"### 🌾 {season_left} vs {season_right}")

                map_html_left = left_map.to_html(width="100%", height="520px")
                map_html_right = right_map.to_html(width="100%", height="520px")

                # Create two map containers using HTML side-by-side
                st.components.v1.html(
                    f"""
                    <div style="display:flex; gap:10px;">
                        <div style="flex:1; border-radius:8px; overflow:hidden;">{map_html_left}</div>
                        <div style="flex:1; border-radius:8px; overflow:hidden;">{map_html_right}</div>
                    </div>
                    """,
                    height=540,
                )

                st.caption("Green = Rice")
