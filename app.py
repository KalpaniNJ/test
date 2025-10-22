import streamlit as st
import streamlit as st
import os
import base64

st.set_page_config(page_title="RiceWater Analytics Hub", layout="wide", initial_sidebar_state="collapsed")

# --- Helper: Convert local logo to base64 ---
def load_logo_as_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# --- Fixed Header with Local Logos and Title ---
def display_fixed_header():
    base_path = os.path.join(os.path.dirname(__file__), "logo")
    # Update these filenames to match your actual logo files
    logos = {
        "left1": os.path.join(base_path, "1.png"),
        "left2": os.path.join(base_path, "4.png"),
        "right1": os.path.join(base_path, "2.png"),
        "right2": os.path.join(base_path, "3.png"),
    }

    # Convert existing logos to base64 if available
    logo_left1 = load_logo_as_base64(logos["left1"]) if os.path.exists(logos["left1"]) else ""
    logo_left2 = load_logo_as_base64(logos["left2"]) if os.path.exists(logos["left2"]) else ""
    logo_right1 = load_logo_as_base64(logos["right1"]) if os.path.exists(logos["right1"]) else ""
    logo_right2 = load_logo_as_base64(logos["right2"]) if os.path.exists(logos["right2"]) else ""

    st.markdown(f"""
        <style>
            .fixed-header {{
                position: fixed;
                top: 35px;
                left: 0;
                width: 100%;
                height: 90px;
                background-color: #FFFFFF;
                color: black;
                z-index: 999;
                border-bottom: 1px solid #333;
                display: flex;
                align-items: flex-end;
                justify-content: space-between;
                flex-wrap: nowrap;
                padding: 0.5rem 2rem;
            }}

            .header-left, .header-right {{
                display: flex;
                align-items: center;
                gap: 10px;
                flex-shrink: 0;
            }}

            .header-logo {{
                height: 55px;
                width: auto;
                border-radius: 4px;
            }}

            .header-title {{
                font-size: 1.2rem;
                font-weight: 600;
                letter-spacing: 1px;
                margin: 0;
                white-space: nowrap;
            }}

            /* Adjust main page spacing */
            .block-container {{
                padding-top: 90px !important;
            }}

        /* -------------------- RESPONSIVE DESIGN -------------------- */
        @media (max-width: 1100px) {{
            .header-title {{
                font-size: 1.1rem;
            }}
            .header-logo {{
                height: 45px;
            }}
        }}

        @media (max-width: 900px) {{
            .header-logo {{
                height: 35px;
            }}
            .header-title {{
                display: none;
            }}
        }}
                
        @media (max-width: 600px) {{
            .fixed-header {{
                justify-content: space-around;
                padding: 0 1rem;
            }}
            .header-left, .header-right {{
                gap: 4px;
            }}
            .header-logo {{
                height: 35px;
            }}
            .header-title {{
                display: none;
            }}
        }}
        </style>

        <div class="fixed-header">
            <div class="header-left">
                {'<img src="data:image/png;base64,' + logo_left1 + '" class="header-logo">' if logo_left1 else ''}
                {'<img src="data:image/png;base64,' + logo_left2 + '" class="header-logo">' if logo_left2 else ''}
                <h2 class="header-title">RiceWater Analytics Hub</h2>
            </div>
            <div class="header-right">
                {'<img src="data:image/png;base64,' + logo_right1 + '" class="header-logo">' if logo_right1 else ''}
                {'<img src="data:image/png;base64,' + logo_right2 + '" class="header-logo">' if logo_right2 else ''}
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- Call the header function ---
display_fixed_header()

# --- Adjust sidebar position below header ---
st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            margin-top: 125px; /* Push sidebar content below the fixed header */
        }
    </style>
""", unsafe_allow_html=True)


import ee
import os
import base64
from sidebar import sidebar_controls
import pandas as pd
import geopandas as gpd
from modules import analysis, monitoring, weather_forecast, water_productivity
from utils.readme_section import show_readme


# ee.Authenticate()
# ee.Initialize(project='rice-mapping-472904')

if "gee_initialized" not in st.session_state:
    with st.spinner("Initializing Google Earth Engine..."):
        service_account = st.secrets["earthengine"]["service_account"]
        private_key = st.secrets["earthengine"]["private_key"]

        credentials = ee.ServiceAccountCredentials(service_account, key_data=private_key)
        ee.Initialize(credentials)
    
    st.session_state["gee_initialized"] = True


st.markdown(
    f"""
    <style>
    .title-container {{
        background-image: url('https://cdn.pixabay.com/photo/2021/05/25/08/13/paddy-field-6281737_960_720.jpg');
        background-size: cover;
        background-position: bottom;
        text-align: center;
        color: white;
        padding: 5vh 0;
        height: 25vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        position: relative;
    }}
    .title-container h1 {{
        font-size: 5vw;
        text-shadow: 4px 4px 7px #000000;
        margin: 0;
    }}
    .image-credit {{
        position: absolute;
        bottom: 5px;
        right: 12px;
        color: #fff;
        font-size: 12px;
        padding: 3px 3px;
        border-radius: 5px;
        font-style: italic;
    }}
    </style>

    <div class="title-container">
        <h1>RiceWater Analytics Hub</h1>
        <div class="image-credit">
            Photo © Pixabay / <a href="https://pixabay.com" target="_blank" style="color:#aee;">Pixabay License</a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("<hr style='border:2px solid #0d6efd'>", unsafe_allow_html=True)

params = sidebar_controls()

# Page selector
page = st.sidebar.selectbox(
    "Select Module",
    ["Weather Forecast", "Paddy Mapping", "Water Productivity"],
    key="main_page_select"
)
st.sidebar.markdown("<br>", unsafe_allow_html=True)


# ==============================
# WEATHER FORECAST MODULE
# ==============================
if page == "Weather Forecast":
    data_dir = os.path.join(os.path.dirname(__file__), "data")

    # Sidebar options
    with st.sidebar.expander("View Rainfall"):
        st.info("Visualize GPM rainfall aggregated by basin or administrative boundaries.")

        analysis_type = st.radio("Select Analysis Type", ["Administrative", "Hydrological"], horizontal=True)

        # --- Administrative: District only ---
        if analysis_type == "Administrative":
            districts_path = os.path.join(data_dir, "lka_dis.shp")

            if not os.path.exists(districts_path):
                st.error(f"District shapefile not found at: {districts_path}")
            else:
                districts = gpd.read_file(districts_path)
                district_names = sorted(districts["ADM2_EN"].unique())
                selected_district = st.selectbox("Select District", district_names)

        # --- Hydrological: Basin only ---
        else:
            basins_path = os.path.join(data_dir, "lka_basins.shp")

            if not os.path.exists(basins_path):
                st.error(f"Basin shapefile not found at: {basins_path}")
            else:
                basins = gpd.read_file(basins_path)
                basin_names = sorted(basins["WSHD_NAME"].unique())
                selected_basin = st.selectbox("Select Basin", basin_names)

        # --- Temporal settings ---
        temporal_method = st.radio(
            "Temporal Aggregation",
            ["Sum", "Mean", "Median"],
            horizontal=True
        )
        wea_start_date = st.date_input("Start Date", pd.to_datetime("2025-01-01"))
        wea_end_date = st.date_input("End Date", pd.to_datetime("2025-01-31"))
        run_forecast = st.button("Run Analysis")

    # --- Build params for processing ---
    params = {
        "analysis_type": analysis_type,
        "district": selected_district if analysis_type == "Administrative" else None,
        "basin": selected_basin if analysis_type == "Hydrological" else None,
        "temporal_method": temporal_method,
        "start_date": str(wea_start_date),
        "end_date": str(wea_end_date),
        "run_forecast": run_forecast,
    }

    # --- Run the forecast analysis ---
    weather_forecast.show(params)


# ==============================
# PADDY MAPPING MODULE
# ==============================
elif page == "Paddy Mapping":
    # Select sub-section under Paddy Mapping
    subpage = st.sidebar.radio(
        "Select Subsection",
        ["Seasonal Analysis", "Seasonal Monitoring", "About me"],
        key="paddy_subpage"
    )

    # SEASONAL ANALYSIS CONTROLS
    if subpage == "Seasonal Analysis":
        with st.sidebar.expander("Time Series Analysis"):
            st.info("Plotting sample points over several years may be heavy. Use a limited date range (e.g., a single season).")

            aoi_option = st.selectbox(
                "Select AOI",
                ["MahaKanadarawa Water Influence Zone", "MahaKanadarawa Irrigable Area"],
                key="aoi_select_tab1"
            )

            start_date = st.date_input("Start Date", pd.to_datetime("2021-12-01"))
            end_date = st.date_input("End Date", pd.to_datetime("2022-05-31"))
            run_ts = st.button("Run Time Series Analysis")

        with st.sidebar.expander("Outlier Analysis"):
            st.info("Perform Time Series analysis before Outlier analysis.")
            run_outlier = st.button("Run Outlier Analysis")

        with st.sidebar.expander("Rice Mapping"):
            st.info("Select the Start, Peak, and Harvest dates. These will be used for further analysis.")
            season_start_date = st.date_input("Start of Season", value=pd.to_datetime("2021-12-13"))
            peak_date = st.date_input("Peak of Season", value=pd.to_datetime("2022-02-25"))
            harvest_date = st.date_input("Harvest Date", value=pd.to_datetime("2022-04-01"))
            run_paddy = st.button("Run Paddy Season Analysis")

        with st.sidebar.expander("Statistical Analysis"):
            st.info("Calculate total paddy area, area by month, and area by start date.")
            run_stats = st.button("Run Statistical Analysis")

        params = {
            "aoi": aoi_option,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "run_ts": run_ts,
            "run_outlier": run_outlier,
            "run_paddy": run_paddy,
            "run_stats": run_stats,
            "season_dates": {
                "start": str(season_start_date),
                "peak": str(peak_date),
                "harvest": str(harvest_date)
            }
        }
        analysis.show(params)

    # SEASONAL MONITORING CONTROLS
    elif subpage == "Seasonal Monitoring":
        with st.sidebar.expander("Monitoring"):
            st.info("Monitor seasonal rice growth. Select the period and run the analysis")

            aoi_option_mnt = st.selectbox(
                "Select AOI",
                ["MahaKanadarawa Water Influence Zone", "MahaKanadarawa Irrigable Area"],
                key="aoi_select_tab2"
            )

            start_date_mnt = st.date_input("Start Date", pd.to_datetime("2023-11-01"), key="start_tab2")
            end_date_mnt = st.date_input("End Date", pd.to_datetime("2024-01-31"), key="end_tab2")
            run_monitor = st.button("Run Analysis")

        params = {
            "aoi_mnt": aoi_option_mnt,
            "start_date_mnt": str(start_date_mnt),
            "end_date_mnt": str(end_date_mnt),
            "run_monitor": run_monitor
        }
        monitoring.show(params)

    # ABOUT SECTION
    elif subpage == "About me":
        from utils.readme_section import show_readme
        show_readme()


# ==============================
# WATER PRODUCTIVITY MODULE
# ==============================
elif page == "Water Productivity":
    st.markdown("""
        <div style="
            background-color:#fef8e7;
            border-left: 6px solid #f7c948;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            margin-top: 40px;
        ">
            <h3 style="color:#b58900;">Module Under Development</h3>
            <p style="color:#555; font-size:16px;">
                The <b>Water Productivity</b> module is currently under development.  
                It will soon include interactive tools to analyze crop water use efficiency,  
                evapotranspiration trends, and productivity indicators based on remote sensing data.
            </p>
            <p style="color:#777; font-size:14px;">
                Please check back in future updates.
            </p>
        </div>
    """, unsafe_allow_html=True)



def add_footer():
    """Displays footer information with IWMI property note and working manual download."""
    manual_path = os.path.join(os.path.dirname(__file__), "Dashboard Training Manual.pdf")

    st.markdown(
        """
        <hr style="border:0.5px solid #ccc; margin-top:40px; margin-bottom:10px;">
        <div style="text-align:center; font-size:14px; color:gray;">
            <p>
                <b>This work is not yet published.</b><br>
                <span style="color:#0d6efd;">Property of <b>International Water Management Institute (IWMI)</b>.</span>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("""
        <style>
        div.stDownloadButton > button:first-child {
            color: #2E8B57 !important;     /* Text color (green) */
            font-size: 16px !important;    /* Label size */
            font-weight: bold !important;  /* Optional bold text */
            background: none !important;   /* Keep default Streamlit background */
            border: none !important; /* Optional subtle border */
        }
        div.stDownloadButton > button:hover {
            color: #228B22 !important;     /* Darker on hover */
        }
        </style>
    """, unsafe_allow_html=True)

    if os.path.exists(manual_path):
        with open(manual_path, "rb") as file:
            st.download_button(
                label="Download Training Manual",
                data=file,
                file_name="Dashboard_Training_Manual.pdf",
                mime="application/pdf",
                width='stretch'
            )
    else:
        st.warning("Training manual not found.")

if __name__ == "__main__":
    add_footer()

