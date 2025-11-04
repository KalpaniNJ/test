import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
from utils import gee_helpers, rice_algorithms
from utils.config import AOI_OPTIONS
from modules.analysis import _get_aoi


# --- Helper: Generate Paddy Map (with outlier detection) ---
def generate_paddy_map(aoi, start_date, end_date, season_dates):
    """Run outlier detection + rice mapping to produce final paddy map."""
    # Time-series extraction for AOI points
    df_line, df_points = gee_helpers.get_time_series(
        aoi=aoi,
        start_date=start_date,
        end_date=end_date
    )

    # Outlier detection (get thresholds, no plots)
    outlier_params = rice_algorithms.detect_outliers(df_points, season_dates)

    # Mosaic generation
    mosaicCollectionUInt16, filteredDekadList = gee_helpers.get_mosaic_collection(
        aoi=aoi,
        start_date=start_date,
        end_date=end_date
    )

    # Perform rice mapping
    maskedPaddyClassification, _, _, _ = rice_algorithms.perform_rice_mapping(
        aoi=aoi,
        mosaicCollectionUInt16=mosaicCollectionUInt16,
        filteredDekadList=filteredDekadList,
        outlier_params=outlier_params,
        dates=season_dates
    )

    return maskedPaddyClassification


# --- Helper: Generate SAR Stack ---
def generate_sar_stack(aoi, start_date, season_start, peak_date, end_date):
    """Generate a 3-band VV SAR stack."""
    collectionVV = (
        ee.ImageCollection('COPERNICUS/S1_GRD')
        .filterBounds(aoi)
        .filter(ee.Filter.eq('instrumentMode', 'IW'))
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
        .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING'))
        .select(['VV'])
    )

    im1 = ee.Image(collectionVV.filterDate(start_date, season_start).mean())
    im2 = ee.Image(collectionVV.filterDate(season_start, peak_date).mean())
    im3 = ee.Image(collectionVV.filterDate(peak_date, end_date).mean())

    return im1.addBands(im2).addBands(im3)


# --- Main Function ---
def show(params):
    st.markdown("""
    <div style="background-color:#fff8e6; border-left:6px solid #f7c948;
    padding:20px; border-radius:8px; margin-top:20px;">
    <h3 style="color:#b58900;">Compare Seasons</h3>
    <p style="color:#555; font-size:16px;">
    Compare rice extent between seasons using paddy maps derived from Sentinel-1 time series.
    Each map is generated with automatic outlier detection and thresholding.
    </p>
    </div>
    """, unsafe_allow_html=True)

    # Load season CSV
    season_df = pd.read_csv(
        "data/season_dates.csv",
        parse_dates=["start_date", "season_start", "peak_date", "harvest_date", "end_date"]
    )

    # Create clean display names (e.g. "2023 Yala")
    season_df["display_name"] = season_df["season"].apply(
        lambda x: x.replace("-", " ") if isinstance(x, str) else x
    )

    col1, col2 = st.columns([0.4, 1.3])
    # Season selection
    with col1:
        season_left = st.selectbox(
            "Select Season",
            season_df["display_name"].tolist(),
            key="season_left"
        )
        
        season_right = st.selectbox(
            "Select Season to compare",
            season_df["display_name"].tolist(),
            key="season_right"
        )

        # Find corresponding rows for selected seasons
        left_row = season_df.loc[season_df["display_name"] == season_left].iloc[0]
        right_row = season_df.loc[season_df["display_name"] == season_right].iloc[0]
    
        # AOI selection
        aoi_name = st.selectbox("Select AOI", list(AOI_OPTIONS.keys()), key="compare_aoi")
        aoi = ee.FeatureCollection(AOI_OPTIONS[aoi_name]).geometry()


    if st.button("Run Comparison"):
        with col2:
            with st.spinner("Generating paddy maps for both seasons..."):
    
                # Define date sets for each selected season
                left_dates = {
                    "start": str(left_row["season_start"]),
                    "peak": str(left_row["peak_date"]),
                    "harvest": str(left_row["harvest_date"])
                }
                right_dates = {
                    "start": str(right_row["season_start"]),
                    "peak": str(right_row["peak_date"]),
                    "harvest": str(right_row["harvest_date"])
                }
    
                # Generate Paddy Maps (with outlier analysis)
                paddy_left = generate_paddy_map(
                    aoi,
                    str(left_row["start_date"]),
                    str(left_row["end_date"]),
                    left_dates
                )
                paddy_right = generate_paddy_map(
                    aoi,
                    str(right_row["start_date"]),
                    str(right_row["end_date"]),
                    right_dates
                )
    
                # Generate SAR Stacks
                sar_left = generate_sar_stack(
                    aoi,
                    str(left_row["start_date"]),
                    str(left_row["season_start"]),
                    str(left_row["peak_date"]),
                    str(left_row["end_date"])
                )
                sar_right = generate_sar_stack(
                    aoi,
                    str(right_row["start_date"]),
                    str(right_row["season_start"]),
                    str(right_row["peak_date"]),
                    str(right_row["end_date"])
                )
    
                # Visualization setup
                aoi_center = aoi.centroid().coordinates().getInfo()
                Map = geemap.Map(center=[aoi_center[1], aoi_center[0]], zoom=12)
                Map.add_basemap("SATELLITE")
    
                # Visualize layers
                left_layer = paddy_left.visualize(min=0, max=1, palette=["red", "green"]) \
                    .blend(sar_left.visualize(min=-25, max=0))
                right_layer = paddy_right.visualize(min=0, max=1, palette=["red", "green"]) \
                    .blend(sar_right.visualize(min=-25, max=0))
    
                # Split map control
                split_control = geemap.SplitMapControl(
                    left_layer=left_layer,
                    right_layer=right_layer,
                    left_label=season_left,
                    right_label=season_right
                )
    
                Map.add(split_control)
                Map.to_streamlit(height=600)
    
