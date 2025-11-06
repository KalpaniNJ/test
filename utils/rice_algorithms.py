import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
import streamlit.components.v1 as components
from utils import gee_helpers, rice_algorithms
from utils.config import AOI_OPTIONS

# =============================
# CONSTANT OUTLIER PARAMETERS
# =============================
CONSTANT_OUTLIER_PARAMS = {
    "q3_start": 5000,
    "q1_peak": 6000,
    "diff_start_peak": 2000,
    "diff_peak_harvest": 1000
}

# =============================
# SPLIT MAP VIEWER
# =============================
def show_dual_maps(aoi, paddy_left, paddy_right, season_left, season_right):
    # Get AOI center
    center = aoi.centroid().coordinates().getInfo()

    # Create single map
    m = geemap.Map(center=[center[1], center[0]], zoom=11)
    m.add_basemap("SATELLITE")

    # Add split comparison
    m.split_map(
        left_layer=paddy_left.visualize(min=0, max=1, palette=["red", "green"]),
        right_layer=paddy_right.visualize(min=0, max=1, palette=["red", "green"]),
        left_label=season_left,
        right_label=season_right
    )

    # Render as HTML for full reliability in Streamlit
    map_html = m.to_html(width="100%", height="600px")
    components.html(map_html, height=600)

    st.caption(f"⬅️ {season_left} | {season_right} ➡️")


# =============================
# MAIN STREAMLIT FUNCTION
# =============================
def show(params):
    # --- Load season CSV ---
    season_df = pd.read_csv(
        "data/season_dates.csv",
        parse_dates=["start_date", "season_start", "peak_date", "harvest_date", "end_date"]
    )
    season_df["display_name"] = season_df["season"].apply(
        lambda x: x.replace("-", " ") if isinstance(x, str) else x
    )

    # --- Layout ---
    col1, _ = st.columns([0.4, 1.6])
    with col1:
        st.subheader("Select seasons to compare")

        # Select AOI
        aoi_name = st.selectbox("Select AOI", list(AOI_OPTIONS.keys()), key="compare_aoi")
        aoi = ee.FeatureCollection(AOI_OPTIONS[aoi_name]).geometry()

        # Select two seasons
        season_left = st.selectbox("Select Season", season_df["display_name"].tolist(), key="left_season")
        season_right = st.selectbox("Select Season to compare", season_df["display_name"].tolist(), key="right_season")

    # Extract selected season metadata
    left_row = season_df.loc[season_df["display_name"] == season_left].iloc[0]
    right_row = season_df.loc[season_df["display_name"] == season_right].iloc[0]

    # --- Run comparison ---
    if st.button("Run Season Comparison"):
        with st.spinner("Generating paddy maps for both seasons..."):

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

            # --- LEFT SEASON PROCESSING ---
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

            # --- RIGHT SEASON PROCESSING ---
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

            # --- SHOW SINGLE SPLIT MAP ---
            show_dual_maps(aoi, paddy_left, paddy_right, season_left, season_right)
