import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
from utils.config import AOI_OPTIONS

# --- HELPER: Get SAR stack image ---
def get_sar_stack(aoi, start_date, season_start, peak_date, end_date):
    """Generate a 3-band VV SAR stack (pre, mid, post season)."""
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


# --- HELPER: Create comparison map ---
def create_comparison_map(aoi, season_row):
    """Create map with both Paddy Map and SAR stack for a given season."""
    st_date = season_row["start_date"]
    s_start = season_row["season_start"]
    s_peak = season_row["peak_date"]
    e_date = season_row["end_date"]

    # Create SAR stack
    sar_stack = get_sar_stack(aoi, st_date, s_start, s_peak, e_date)

    # Replace below with ee.Image("your/paddy/classification/asset") if available
    paddy_map = sar_stack.select(0).gt(-15).rename("paddy_map")
  
    Map = geemap.Map(add_google_map=False)
    Map.add_basemap("SATELLITE")
    Map.addLayer(sar_stack, {"min": -25, "max": 0}, "SAR VV Stack")
    Map.addLayer(paddy_map, {"min": 0, "max": 1, "palette": ["red", "green"]}, "Paddy Map", False)
    Map.addLayerControl()
    return Map


# ---------- MAIN FUNCTION ----------
def show(params):
    st.markdown("""
    <div style="background-color:#fff8e6; border-left:6px solid #f7c948;
    padding:20px; border-radius:8px; margin-top:20px;">
    <h3 style="color:#b58900;">🔁 Compare Seasons</h3>
    <p style="color:#555; font-size:16px;">
    Compare seasonal mRVI patterns, paddy extent, and crop dynamics side-by-side.
    Select two seasons from the list to visualize their SAR stacks and paddy maps.
    </p>
    </div>
    """, unsafe_allow_html=True)

    # --- Load season info CSV ---
    season_df = pd.read_csv("data/season_dates.csv", parse_dates=[
        "start_date", "season_start", "peak_date", "harvest_date", "end_date"
    ])

    col1, col2 = st.columns(2)

    with col1:
        season_left = st.selectbox(
            "Select Left Season",
            [f"{row.year} {row.season}" for _, row in season_df.iterrows()],
            key="season_left"
        )

    with col2:
        season_right = st.selectbox(
            "Select Right Season",
            [f"{row.year} {row.season}" for _, row in season_df.iterrows()],
            key="season_right"
        )

    # Get selected season data
    left_row = season_df.loc[
        (season_df["year"].astype(str) + " " + season_df["season"]) == season_left
    ].iloc[0]
    right_row = season_df.loc[
        (season_df["year"].astype(str) + " " + season_df["season"]) == season_right
    ].iloc[0]

    # Select AOI
    aoi_name = st.selectbox("Select AOI", list(AOI_OPTIONS.keys()), key="compare_aoi")
    aoi = ee.FeatureCollection(AOI_OPTIONS[aoi_name]).geometry()

    # Generate maps
    Map_left = create_comparison_map(aoi, left_row)
    Map_right = create_comparison_map(aoi, right_row)

    # Split Panel
    split_map = geemap.SplitMapControl(
        left_layer=Map_left.layers[1],
        right_layer=Map_right.layers[1],
        left_label=season_left,
        right_label=season_right
    )

    # Display map
    st.markdown("### Split View: SAR & Paddy Maps Comparison")
    Map = geemap.Map(center=[7.8, 80.7], zoom=10)
    Map.add(split_map)
    Map.to_streamlit(height=600)
