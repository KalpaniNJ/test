import streamlit as st
import ee
import geemap.foliumap as geemap
from utils import gee_helpers, plot_utils, rice_algorithms
from utils.config import AOI_OPTIONS
import geemap.foliumap as geemap
from streamlit_folium import folium_static



def run_time_series(params):
    aoi_name = params["aoi"]
    aoi = ee.FeatureCollection(AOI_OPTIONS[aoi_name]).geometry()

    with st.spinner(f"Running Time Series Analysis for {aoi_name} "
                    f"({params['start_date']} → {params['end_date']})..."):
        df_line, df_points = gee_helpers.get_time_series(
            aoi=aoi,
            start_date=params["start_date"],
            end_date=params["end_date"]
        )

        st.session_state["ts_df_line"] = df_line
        st.session_state["ts_df_points"] = df_points

    # --- Display results ---
    st.subheader("Mean mRVI Time Series")
    plot_utils.plot_time_series(df_line)
    plot_utils.plot_point_series(df_points)


    
def run_outlier(params):
    if "ts_df_points" not in st.session_state:
        st.error("Please run the Time Series Analysis first.")
        return

    with st.spinner("Running Outlier Analysis..."):
        fig_box = plot_utils.plot_outlier_boxplot(st.session_state["ts_df_points"])
        st.session_state["outlier_boxplot"] = fig_box

    st.subheader("mRVI Dispersion and Outlier Analysis")
    st.pyplot(fig_box)



def run_rice_mapping(params):
    if "ts_df_points" not in st.session_state:
        st.error("Please complete Time Series and Outlier Analysis first.")
        return

    aoi_name = params["aoi"]
    aoi = ee.FeatureCollection(AOI_OPTIONS[aoi_name]).geometry()
    dates = params["season_dates"]

    df_points = st.session_state["ts_df_points"]
    outlier_params = rice_algorithms.detect_outliers(df_points, dates)

    with st.spinner("Running Rice Mapping..."):
        mosaicCollectionUInt16, filteredDekadList = gee_helpers.get_mosaic_collection(
            aoi=aoi,
            start_date=params["start_date"],
            end_date=params["end_date"]
        )

        (maskedPaddyClassification, growingSeason, maskedStartMonth, maskedStartMonthDay) = rice_algorithms.perform_rice_mapping(
            aoi=aoi,
            mosaicCollectionUInt16=mosaicCollectionUInt16,
            filteredDekadList=filteredDekadList,
            outlier_params=outlier_params,
            dates=dates
        )

        st.session_state["maskedPaddyClassification"] = maskedPaddyClassification
        st.session_state["maskedStartMonth"] = maskedStartMonth
        st.session_state["maskedStartMonthDay"] = maskedStartMonthDay

        # --- Map display ---
        aoi_centroid = aoi.centroid().coordinates().getInfo()
        Map = geemap.Map(center=[aoi_centroid[1], aoi_centroid[0]], zoom=12)
        Map.add_basemap("SATELLITE")
        Map.addLayer(maskedPaddyClassification, {"min": 0, "max": 1, "palette": ["red", "green"]}, "Paddy Map")
        Map.addLayer(growingSeason, {"min": 0, "max": 2, "palette": ["blue", "green", "orange"]}, "Growing Season")
        Map.addLayer(maskedStartMonth, {"min": 1, "max": 12}, "Start Month")
        Map.addLayerControl()
        Map.to_streamlit(height=500)

  

def run_statistics(params):
    import streamlit as st
    from utils import gee_helpers, plot_utils
    from utils.config import AOI_OPTIONS
    import ee

    aoi_name = params["aoi"]
    aoi = ee.FeatureCollection(AOI_OPTIONS[aoi_name]).geometry()

    st.subheader("Statistical Analysis")

    if not all(k in st.session_state for k in [
        "maskedPaddyClassification", "maskedStartMonth", "maskedStartMonthDay"
    ]):
        st.warning("Please run the Rice Mapping step before calculating statistics.")
        return

    with st.spinner("Calculating rice statistics..."):
        # --- Retrieve stored layers ---
        maskedPaddyClassification = st.session_state["maskedPaddyClassification"]
        maskedStartMonth = st.session_state["maskedStartMonth"]
        maskedStartMonthDay = st.session_state["maskedStartMonthDay"]

        # --- Compute statistics ---
        total_area_ha, month_stats, mmdd_stats = gee_helpers.compute_statistics(
            aoi,
            maskedPaddyClassification,
            maskedStartMonth,
            maskedStartMonthDay
        )

        # --- Store results in session_state for reuse ---
        st.session_state["total_area_ha"] = total_area_ha
        st.session_state["month_stats"] = month_stats
        st.session_state["mmdd_stats"] = mmdd_stats

        # --- Plot and store charts ---
        plots = plot_utils.plot_statistics(month_stats, mmdd_stats)
        # (Assuming plot_utils.plot_statistics internally sets session_state plots like before)

        st.subheader(f"🌾 Total Paddy Extent: {total_area_ha:,.2f} ha")

    # --- Display charts in 3x2 layout if available ---
    if any(k in st.session_state for k in [
        "stats_bar_month", "stats_bar_day",
        "stats_pie_month", "stats_pie_day",
        "stats_combo_month", "stats_combo_day"
    ]):
        st.markdown("---")
        st.markdown("### Visual Summaries")

        # Row 1
        c1, c2 = st.columns(2)
        with c1:
            if "stats_combo_month" in st.session_state:
                st.subheader("Monthly & Cumulative Paddy Area")
                st.pyplot(st.session_state["stats_combo_month"])
        with c2:
            if "stats_combo_day" in st.session_state:
                st.subheader("Dekadal & Cumulative Paddy Area")
                st.pyplot(st.session_state["stats_combo_day"])

        # Row 2
        c3, c4 = st.columns(2)
        with c3:
            if "stats_bar_month" in st.session_state:
                st.subheader("Paddy Area by Month")
                st.pyplot(st.session_state["stats_bar_month"])
        with c4:
            if "stats_bar_day" in st.session_state:
                st.subheader("Paddy Area by Start Date (MM-DD)")
                st.pyplot(st.session_state["stats_bar_day"])

        # Row 3
        c5, c6 = st.columns(2)
        with c5:
            if "stats_pie_month" in st.session_state:
                st.subheader("Paddy Area % by Month")
                st.pyplot(st.session_state["stats_pie_month"])
        with c6:
            if "stats_pie_day" in st.session_state:
                st.subheader("Paddy Area % by Start Date (MM-DD)")
                st.pyplot(st.session_state["stats_pie_day"])

    else:
        st.markdown("<p style='color:gray;'>No statistics available yet. Please run the analysis.</p>", unsafe_allow_html=True)

