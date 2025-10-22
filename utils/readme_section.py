import streamlit as st
import os

def show_readme():
    """Displays About section with text on left and image on right."""
    
    st.markdown(
        """
        <style>
        .readme-box {
            background: linear-gradient(135deg, #f0fff0 0%, #e6f9e6 100%);
            border-left: 5px solid #2E8B57;
            padding: 20px 25px;
            # border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin: 20px auto;
            width: 90%;
        }
        .readme-title {
            color: #2E8B57;
            font-size: 26px;
            font-weight: 800;
            text-align: center;
            margin-bottom: 15px;
        }
        .readme-text {
            font-size: 16px;
            color: #333;
            line-height: 1.7;
            text-align: justify;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # st.markdown("<div class='readme-title'>About This Dashboard</div>", unsafe_allow_html=True)

    # --- Create two columns ---
    col1, col2 = st.columns([2, 1])  # Wider text column, narrower image column

    with col1:
        st.markdown(
            """
            <div class="readme-box">
                <div class="readme-title">Data and Methods Used</div>
                <div class="readme-text">
                    The Rice Mapping Dashboard is a user-friendly tool developed by the <b>International Water Management Institute (IWMI)</b> 
                    for analyzing Sentinel-1 based rice growth patterns, built with Python and Streamlit, and integrated with 
                    Google Earth Engine (GEE) for remote sensing data processing. It offers functionalities 
                    to visualize time-series data, detect seasonal trends, and map the extent of rice cultivation.
                    The dashboard features a sidebar for inputs and controls, which is organized into five expandable sections: Time Series Analysis, 
                    Outlier Analysis, Rice Mapping, Statistical Analysis, and Monitoring. <br>It has three main operational tabs:
                    <br>
                    <ol>
                        <li><b>Seasonal Analysis:</b> Used for retrospective studies of completed rice seasons, offering detailed time-series, 
                        outlier detection, and statistical modules to analyze historical growth patterns, map paddy areas, 
                        and compute area statistics based on user-defined Start, Peak, and Harvest dates.</li>
                        <li><b>Seasonal Monitoring:</b> Employed for near real-time tracking of ongoing or recent seasons. 
                        It automatically detects key growth stages like the Start of Season (SOS) and peak periods, 
                        monitors mRVI variations for current growth trends, maps active paddy fields, and calculates current-season paddy area.</li>
                        <li><b>About this Dashboard</b></li>
                    </ol>
                    The workflow integrates several modules for:
                    <ul>
                        <li><b>Preprocessing</b> Sentinel-1 SAR data</li>
                        <li><b>Time Series</b> generation & outlier detection</li>
                        <li><b>Rice Growth Phase</b> classification</li>
                        <li><b>Spatial Mapping</b> & area statistics</li>
                    </ul>
                    The dashboard's capabilities are particularly valuable in contexts like Sri Lanka, which experiences two primary cropping seasons for paddy: 
                    the Maha season (main season, typically from September/October to March/April) and the Yala season (secondary season, typically from April/May 
                    to August/September). Accordingly, our analysis season starting from October would align with the beginning of Sri Lanka's Maha season, allowing 
                    for comprehensive monitoring and analysis of this major cropping period. 
                </div>
            </div>
            """,
                unsafe_allow_html=True
            )

    with col2:
        img_path = os.path.join(os.path.dirname(__file__), "methodology.png")
        if os.path.exists(img_path):
            st.markdown("<br>", unsafe_allow_html=True)
            st.image(img_path, use_container_width=True)
            st.markdown('<div class="img-caption" style="text-align:center;">Workflow: Rice Mapping Process</div>', unsafe_allow_html=True)
        else:
            st.info("Methodology image not found.")

