import streamlit as st
import ee
import geemap.foliumap as geemap
from utils import gee_helpers, plot_utils, rice_algorithms
from utils.config import AOI_OPTIONS
from streamlit_folium import folium_static


# Helper: safely fetch AOI from params or session state
def _get_aoi(params):
    """Safely fetch AOI geometry and name."""
    aoi_name = params.get("aoi") or st.session_state.get("aoi")
    if not aoi_name:
        st.error("Please select an AOI before running this analysis.")
        st.stop()
    if aoi_name not in AOI_OPTIONS:
        st.error(f"Invalid AOI: {aoi_name}. Please check config.py.")
        st.stop()
    return ee.FeatureCollection(AOI_OPTIONS[aoi_name]).geometry(), aoi_name


# TIME SERIES ANALYSIS
def run_time_series(params):
    aoi, aoi_name = _get_aoi(params)

    if params.get("run_ts"):
        with st.spinner(f"Running Time Series Analysis for {aoi_name} "
                        f"({params['start_date']} → {params['end_date']})..."):
            df_line, df_points = gee_helpers.get_time_series(
                aoi=aoi,
                start_date=params["start_date"],
                end_date=params["end_date"],
                aoi_name=aoi_name
            )

            st.session_state.update({
                "aoi": aoi_name,
                "ts_df_line": df_line,
                "ts_df_points": df_points
            })

    # --- Always re-display stored results ---
    if "ts_df_line" in st.session_state and "ts_df_points" in st.session_state:
        plot_utils.plot_time_series(st.session_state["ts_df_line"])
        plot_utils.plot_point_series(st.session_state["ts_df_points"])
    else:
        st.markdown("<p style='color:gray;'>No results yet. Run the Time Series Analysis.</p>",
                    unsafe_allow_html=True)


# OUTLIER ANALYSIS
def run_outlier(params):
    if "ts_df_points" not in st.session_state:
        st.error("Please run the Time Series Analysis first.")
        return

    if params.get("run_outlier"):
        with st.spinner("Running Outlier Analysis..."):
            fig_box = plot_utils.plot_outlier_boxplot(st.session_state["ts_df_points"])
            st.session_state["outlier_boxplot"] = fig_box

    # --- Always show stored plot if available ---
    if "outlier_boxplot" in st.session_state:
        st.pyplot(st.session_state["outlier_boxplot"])
    else:
        st.markdown("<p style='color:gray;'>Results will be displayed here after analysis.</p>",
                    unsafe_allow_html=True)


# RICE MAPPING
def run_rice_mapping(params):
    if "ts_df_points" not in st.session_state:
        st.error("Please complete Time Series and Outlier Analysis first.")
        return

    aoi, aoi_name = _get_aoi(params)
    dates = params.get("season_dates") or st.session_state.get("season_dates")

    if not dates:
        st.warning("Please specify season dates before running the mapping.")
        return

    st.session_state["season_dates"] = dates
    show_growing_season = params.get("show_growing_season", False)

    if params.get("run_paddy"):
        df_points = st.session_state["ts_df_points"]
        try:
            outlier_params = rice_algorithms.detect_outliers(df_points, dates)
        except ValueError as e:
            st.error(str(e))
            return

        with st.spinner("Running Rice Mapping..."):
            mosaicCollectionUInt16, filteredDekadList = gee_helpers.get_mosaic_collection(
                aoi=aoi,
                start_date=params["start_date"],
                end_date=params["end_date"],
                aoi_name=aoi_name
            )

            (maskedPaddyClassification,
             growingSeason,
             maskedStartMonth,
             maskedStartMonthDay) = rice_algorithms.perform_rice_mapping(
                aoi=aoi,
                mosaicCollectionUInt16=mosaicCollectionUInt16,
                filteredDekadList=filteredDekadList,
                outlier_params=outlier_params,
                dates=dates
            )

            st.session_state.update({
                "aoi": aoi_name,
                "maskedPaddyClassification": maskedPaddyClassification,
                "growingSeason": growingSeason,
                "maskedStartMonth": maskedStartMonth,
                "maskedStartMonthDay": maskedStartMonthDay
            })
            # New run invalidates any previously-rendered map, including
            # whether the (expensive) Growing Season layer is on it.
            st.session_state["_growing_season_on_map"] = False

    # (Re)build the map on a fresh run, or when the Growing Season toggle
    # was just switched on and isn't on the current map yet. The Growing
    # Season layer requires an AOI-wide reduceRegion that dominates Rice
    # Mapping's runtime (~20-30s of a ~30s run) — everything else here is
    # cheap (~1-2s total) — so it's only computed/added when asked for,
    # instead of on every run regardless of whether it's even shown.
    needs_rebuild = params.get("run_paddy") or (
        show_growing_season and not st.session_state.get("_growing_season_on_map")
    )
    if needs_rebuild and "maskedPaddyClassification" in st.session_state:
        with st.spinner("Rendering map..."):
            aoi_centroid = aoi.centroid().coordinates().getInfo()
            Map = geemap.Map(center=[aoi_centroid[1], aoi_centroid[0]], zoom=12)
            Map.add_basemap("SATELLITE")
            Map.addLayer(st.session_state["maskedPaddyClassification"],
                         {"min": 0, "max": 1, "palette": ["red", "green"]}, "Paddy Map")
            if show_growing_season:
                Map.addLayer(st.session_state["growingSeason"],
                             {"min": 0, "max": 2, "palette": ["blue", "green", "orange"]},
                             "Growing Season", False)
                st.session_state["_growing_season_on_map"] = True
            Map.addLayer(st.session_state["maskedStartMonth"],
                         {"min": 1, "max": 12,
                          "palette": ["blue", "cyan", "green", "lime", "yellow", "orange",
                                      "red", "pink", "purple", "brown", "gray", "black"]},
                         "Start Month", False)
            Map.addLayer(st.session_state["maskedStartMonthDay"],
                         {"min": 101, "max": 1231,
                          "palette": ["blue", "cyan", "green", "yellow", "orange", "red"]},
                         "Start Month–Day", False)
            Map.addLayerControl()
            st.session_state["map_SA"] = Map

    # --- Always show map if available ---
    if "map_SA" in st.session_state:
        st.subheader("Rice Mapping Results")
        st.session_state["map_SA"].to_streamlit(height=600)
        if not show_growing_season:
            st.caption("Enable \"Show Growing Season layer\" (left panel) to also compute it — adds ~20-30s.")
    else:
        st.markdown("<p style='color:gray;'>Results will appear here after running the analysis.</p>",
                    unsafe_allow_html=True)


# STATISTICAL ANALYSIS
def run_statistics(params):
    aoi, aoi_name = _get_aoi(params)

    # Check if rice mapping results exist
    if not all(k in st.session_state for k in [
        "maskedPaddyClassification", "maskedStartMonth", "maskedStartMonthDay"
    ]):
        st.warning("Please run the Rice Mapping step before calculating statistics.")
        return

    # Only compute if button was pressed
    if params.get("run_stats"):
        with st.spinner("Calculating rice statistics..."):
            maskedPaddyClassification = st.session_state["maskedPaddyClassification"]
            maskedStartMonth = st.session_state["maskedStartMonth"]
            maskedStartMonthDay = st.session_state["maskedStartMonthDay"]

            total_area_ha, month_stats, mmdd_stats = gee_helpers.compute_statistics(
                aoi,
                maskedPaddyClassification,
                maskedStartMonth,
                maskedStartMonthDay
            )

            # Save results for reuse
            st.session_state.update({
                "total_area_ha": total_area_ha,
                "month_stats": month_stats,
                "mmdd_stats": mmdd_stats
            })

            plots = plot_utils.plot_statistics(month_stats, mmdd_stats)

            # If function returns figures (not stored internally)
            if isinstance(plots, dict):
                st.session_state.update(plots)

            st.success("Rice statistics successfully calculated!")

    # --- Always show stored results if available ---
    if "total_area_ha" in st.session_state:
        st.subheader(f"🌾 Total Paddy Extent: {st.session_state['total_area_ha']:,.2f} ha")

    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
    
    # --- Always display charts if any available ---
    if any(k in st.session_state for k in [
        "stats_bar_month", "stats_bar_day",
        "stats_pie_month", "stats_pie_day",
        "stats_combo_month", "stats_combo_day"
    ]):
        c1, c2 = st.columns(2)
        with c1:
            if "stats_combo_month" in st.session_state:
                st.pyplot(st.session_state["stats_combo_month"])
        with c2:
            if "stats_combo_day" in st.session_state:
                st.pyplot(st.session_state["stats_combo_day"])

        c3, c4 = st.columns(2)
        with c3:
            if "stats_bar_month" in st.session_state:
                st.pyplot(st.session_state["stats_bar_month"])
        with c4:
            if "stats_bar_day" in st.session_state:
                st.pyplot(st.session_state["stats_bar_day"])

        c5, c6 = st.columns(2)
        with c5:
            if "stats_pie_month" in st.session_state:
                st.pyplot(st.session_state["stats_pie_month"])
        with c6:
            if "stats_pie_day" in st.session_state:
                st.pyplot(st.session_state["stats_pie_day"])
    else:
        st.markdown(
            "<p style='color:gray;'>No statistics available yet. Please run the analysis.</p>",
            unsafe_allow_html=True
        )
