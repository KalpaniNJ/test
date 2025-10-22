import streamlit as st
import ee
import geemap.foliumap as geemap
from utils import gee_helpers, plot_utils, rice_algorithms
from utils.config import AOI_OPTIONS
import geemap.foliumap as geemap
from streamlit_folium import folium_static


def show(params):
    st.title("Seasonal Analysis")

    aoi_name = params["aoi"]
    aoi_path = AOI_OPTIONS[aoi_name]
    aoi = ee.FeatureCollection(aoi_path).geometry()

    tab1, tab2, tab3, tab4 = st.tabs([
        "1️⃣ Time Series Analysis",
        "2️⃣ Outlier Analysis",
        "3️⃣ Rice Mapping",
        "4️⃣ Statistical Analysis"
    ])

    with tab1:
        if params["run_ts"]:
            with st.spinner(f"Running Time Series Analysis for {params['aoi']} "
                            f"({params['start_date']} → {params['end_date']})..."):
                df_line, df_points = gee_helpers.get_time_series(
                    aoi=aoi,
                    start_date=params["start_date"],
                    end_date=params["end_date"]
                )
                st.session_state.update({
                    "ts_df_line": df_line,
                    "ts_df_points": df_points
                })
        else:
            st.markdown(
                "<span style='font-size:16px; color:gray;'>"
                "Analyze rice growth over time using <b>mean mRVI</b> at sample points. "
                "Select an AOI and date range to generate the time series chart."
                "</span>", unsafe_allow_html=True
            )

        # Always (re)draw plots if data exists
        if "ts_df_line" in st.session_state and "ts_df_points" in st.session_state:
            plot_utils.plot_time_series(st.session_state["ts_df_line"])
            plot_utils.plot_point_series(st.session_state["ts_df_points"])


    with tab2:
        if params["run_outlier"]:
            if "ts_df_points" not in st.session_state:
                st.error("Please run the Time Series Analysis first.")
            else:
                with st.spinner("Running Outlier Analysis..."):
                    # Create and save the boxplot figure
                    fig_box = plot_utils.plot_outlier_boxplot(st.session_state["ts_df_points"])
                    st.session_state["outlier_boxplot"] = fig_box
                    st.subheader("mRVI Dispersion and Outlier Analysis at Sample Points")
                    st.pyplot(fig_box)

        else:
            st.markdown(
                "<span style='font-size:16px; color:gray;'>"
                "Visualize dispersion of mRVI values and detect potential outliers at sample points."
                "</span>",
                unsafe_allow_html=True
            )

        # Re-display previously generated plot (without recomputing)
        if "outlier_boxplot" in st.session_state and not params["run_outlier"]:
            st.subheader("mRVI Dispersion and Outlier Analysis at Sample Points")
            st.pyplot(st.session_state["outlier_boxplot"])


    with tab3:
        if params["run_paddy"]:
            with st.spinner("Visualizing maps..."):

                # Ensure time series and outlier results exist
                if "ts_df_points" not in st.session_state:
                    st.error("Please run Time Series and Outlier Analysis first.")
                else:
                    # Retrieve the necessary data
                    df_points = st.session_state["ts_df_points"]
                    dates = params["season_dates"]
                    outlier_params = rice_algorithms.detect_outliers(df_points, dates)

                    # Get mosaic & dekad list (from gee_helpers)
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

                    aoi_centroid = aoi.centroid().coordinates().getInfo()
                    Map_SA = geemap.Map(center=[aoi_centroid[1], aoi_centroid[0]], zoom=12)
                    Map_SA.add_basemap("SATELLITE")
                    
                    # --- Add AOI boundary (red outline) ---
                    Map_SA.addLayer(ee.FeatureCollection(aoi).style(**{
                            "color": "black",
                            "width": 1,
                            "fillColor": "00000000"  # transparent
                        }),
                        {},
                        "AOI Boundary",
                        False
                    )

                    Map_SA.addLayer(maskedPaddyClassification,
                                {"min": 0, "max": 1, "palette": ['red', 'green']},
                                "Paddy Map")
                    Map_SA.addLayer(growingSeason,
                                {"min": 0, "max": 2, "palette": ["#00008b", 'green', '#FE9900']},
                                "Growing Season", False)
                    Map_SA.addLayer(maskedStartMonth,
                                {"min": 1, "max": 12, "palette": ["blue", "cyan", "green", "lime", "yellow", "orange", "red", "pink", "purple", "brown", "gray", "black"]},
                                "Start Month", False)
                    Map_SA.addLayer(maskedStartMonthDay,
                                {"min": 101, "max": 1231, "palette": ["blue", "cyan", "green", "yellow", "orange", "red"]},
                                "Start Month–Day", False)

                    Map_SA.addLayerControl()
                    # Map_SA.to_streamlit(height=500)
                    st.session_state["map_SA"] = Map_SA

        else:
            st.markdown(
                "<span style='font-size:16px; color:gray;'>"
                "Visualizes the spatial distribution of paddy fields within the area of interest including the paddy map and start of rice cropping (by month and day)."
                "</span>", unsafe_allow_html=True)

        if "map_SA" in st.session_state:
                # Re-display previously generated map
                st.session_state["map_SA"].to_streamlit()

    with tab4:
        if params["run_stats"]:
            with st.spinner("Calculating statistics..."):
                if not all(k in st.session_state for k in [
                    "maskedPaddyClassification", "maskedStartMonth", "maskedStartMonthDay"
                ]):
                    st.error("Please run the Rice Mapping first before calculating statistics.")
                else:
                    # Use stored images
                    maskedPaddyClassification = st.session_state["maskedPaddyClassification"]
                    maskedStartMonth = st.session_state["maskedStartMonth"]
                    maskedStartMonthDay = st.session_state["maskedStartMonthDay"]

                    # Compute statistics from GEE
                    total_area_ha, month_stats, mmdd_stats = gee_helpers.compute_statistics(
                        aoi, maskedPaddyClassification, maskedStartMonth, maskedStartMonthDay
                    )

                    # Display total area
                    st.subheader(f"🌾 Total Paddy Extent: {total_area_ha:,.2f} ha")

                    # Plot all charts
                    plot_utils.plot_statistics(month_stats, mmdd_stats)

        else:
            st.markdown(
                "<span style='font-size:16px; color:gray;'>"
                "Calculates total paddy extent and cropping start distributions."
                "</span>",
                unsafe_allow_html=True
            )

        if any(k in st.session_state for k in [
            "stats_bar_month", "stats_bar_day",
            "stats_pie_month", "stats_pie_day",
            "stats_combo_month", "stats_combo_day"
        ]):
            
            col1, col2 = st.columns(2)
            with col1:
                if "stats_combo_month" in st.session_state:
                    st.subheader("Monthly & Cumulative Paddy Area")
                    st.pyplot(st.session_state["stats_combo_month"])
            with col2:
                if "stats_combo_day" in st.session_state:
                    st.subheader("Dekadal & Cumulative Paddy Area")
                    st.pyplot(st.session_state["stats_combo_day"])

            col3, col4 = st.columns(2)
            with col3:
                if "stats_bar_month" in st.session_state:
                    st.subheader("Paddy Area by Month")
                    st.pyplot(st.session_state["stats_bar_month"])
            with col4:
                if "stats_bar_day" in st.session_state:
                    st.subheader("Paddy Area by Start Date (MM-DD)")
                    st.pyplot(st.session_state["stats_bar_day"])

            col5, col6 = st.columns(2)
            with col5:
                if "stats_pie_month" in st.session_state:
                    st.subheader("Paddy Area Percentage by Month")
                    st.pyplot(st.session_state["stats_pie_month"])
            with col6:
                if "stats_pie_day" in st.session_state:
                    st.subheader("Paddy Area Percentage by Start Date (MM-DD)")
                    st.pyplot(st.session_state["stats_pie_day"])
