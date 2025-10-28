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
    logos = {
        "left1": os.path.join(base_path, "1.png"),
        "left2": os.path.join(base_path, "4.png"),
        "right1": os.path.join(base_path, "2.png"),
        "right2": os.path.join(base_path, "3.png"),
    }

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
from modules import analysis, monitoring, rainfall_distribution, weather_forecast, water_productivity
from utils.readme_section import show_readme
from streamlit_folium import st_folium
import folium


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

# --- Home icon button in the sidebar ---
st.sidebar.markdown("""
    <div style="text-align:left; margin-bottom:15px;">
        <a href="?main_page_select=Rainfall+Distribution" title="Go to Home" target="_self">
            <img src="https://cdn-icons-png.flaticon.com/512/25/25694.png" width="32" style="margin-bottom:5px;">
        </a>
    </div>
""", unsafe_allow_html=True)

params = sidebar_controls()

# Page selector
page = st.sidebar.selectbox(
    "Select Module",
    ["Rainfall Distribution", "Weather Forecast", "Paddy Mapping", "Water Productivity"],
    key="main_page_select"
)
st.sidebar.markdown("<br>", unsafe_allow_html=True)


# ==============================
# RAINFALL DISTRIBUTION MODULE
# ==============================
if page == "Rainfall Distribution":
    st.markdown("### 🌧️ Rainfall Distribution")

    col1, col2 = st.columns([0.9, 3.1])

    with col1:
        analysis_type = st.radio("Select Analysis Type", ["Administrative", "Hydrological"], horizontal=True)
        data_dir = os.path.join(os.path.dirname(__file__), "data")

        if analysis_type == "Administrative":
            districts_path = os.path.join(data_dir, "lka_dis.shp")
            districts = gpd.read_file(districts_path)
            district_names = sorted(districts["ADM2_EN"].unique())
            selected_district = st.selectbox("Select District", district_names)
            selected_basin = None

        else:
            basins_path = os.path.join(data_dir, "lka_basins.shp")
            basins = gpd.read_file(basins_path)
            basin_names = sorted(basins["WSHD_NAME"].unique())
            selected_basin = st.selectbox("Select Basin", basin_names)
            selected_district = None

        temporal_method = st.radio("Temporal Aggregation", ["Sum", "Mean", "Median"], horizontal=True)
        wea_start_date = st.date_input("From", pd.to_datetime("2025-01-01"))
        wea_end_date = st.date_input("To", pd.to_datetime("2025-01-31"))
        run_forecast = st.button("Apply Layers")

    with col2:
        if not run_forecast:
            leaflet_map = folium.Map(location=[7.8731, 80.7718], zoom_start=7, tiles="OpenStreetMap")
            folium.TileLayer("Esri.WorldImagery", name="Satellite", show=False).add_to(leaflet_map)
            folium.LayerControl(position="topright", collapsed=False).add_to(leaflet_map)
            st_folium(leaflet_map, use_container_width=True, height=650)

        # After Apply Layers is clicked
        else:
            leaflet_map = folium.Map(location=[7.8731, 80.7718], zoom_start=7, tiles="OpenStreetMap")
            folium.TileLayer("Esri.WorldImagery", name="Satellite", show=False).add_to(leaflet_map)

            # --- Show only the selected district or basin ---
            if selected_district:
                selected_geom = districts[districts["ADM2_EN"] == selected_district]
                folium.GeoJson(
                    selected_geom.__geo_interface__,
                    name=f"{selected_district} District",
                    style_function=lambda x: {"color": "red", "weight": 2, "fillOpacity": 0.05}
                ).add_to(leaflet_map)
                leaflet_map.fit_bounds(selected_geom.total_bounds.tolist())

            elif selected_basin:
                selected_geom = basins[basins["WSHD_NAME"] == selected_basin]
                folium.GeoJson(
                    selected_geom.__geo_interface__,
                    name=f"{selected_basin} Basin",
                    style_function=lambda x: {"color": "blue", "weight": 2, "fillOpacity": 0.05}
                ).add_to(leaflet_map)
                leaflet_map.fit_bounds(selected_geom.total_bounds.tolist())

        # ---- Add rainfall layer after "Apply Layers" ----
        if run_forecast and selected_geom is not None:
            with st.spinner("Loading rainfall layer..."):
                tile_url, layer_name = rainfall.get_rainfall_layer(
                    wea_start_date.strftime("%Y-%m-%d"),
                    wea_end_date.strftime("%Y-%m-%d"),
                    temporal_method,
                    selected_geom
                )

                folium.raster_layers.TileLayer(
                    tiles=tile_url,
                    attr="GPM IMERG",
                    name=layer_name,
                    overlay=True,
                    opacity=0.85,
                    show=True
                ).add_to(leaflet_map)

        folium.LayerControl(position="topright", collapsed=False).add_to(leaflet_map)
        st_folium(leaflet_map, use_container_width=True, height=650)


            # 🔹 You can now later overlay GPM data here:
            # rainfall_distribution.show(params)


# ==============================
# WEATHER FORECAST MODULE
# ==============================
elif page == "Weather Forecast":
    st.markdown("""
        <div style="
            background-color:#e7f4fe;
            border-left: 6px solid #2b7de9;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
            margin-top: 40px;
        ">
            <h3 style="color:#1a73e8;">Module Under Development</h3>
            <p style="color:#333; font-size:16px;">
                The <b>Weather Forecast</b> module is currently under development.  
                It will soon provide interactive tools for monitoring and analyzing 
                rainfall forecasts, precipitation anomalies, and near-real-time weather data 
                from satellite and global climate models.
            </p>
            <p style="color:#555; font-size:14px;">
                Stay tuned for updates — upcoming versions will support short-term and seasonal forecasts,
                including rainfall outlooks and temperature trends for decision support.
            </p>
        </div>
    """, unsafe_allow_html=True)


# ==============================
# PADDY MAPPING MODULE
# ==============================
elif page == "Paddy Mapping":
    # Select sub-section under Paddy Mapping
    subpage = st.sidebar.radio(
        "Select Subsection",
        ["Seasonal Analysis", "Seasonal Monitoring", "Data and Methods"],
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
    elif subpage == "Data and Methods":
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

