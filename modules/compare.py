import streamlit as st
import folium
from streamlit_folium import st_folium

def show():
    st.title("🌾 Season Comparison")

    # --- Sidebar Inputs ---
    col1, col2 = st.columns(2)
    with col1:
        season_left = st.selectbox("Select Left Season", ["Maha 2023/24", "Yala 2024", "Maha 2024/25"], key="left_season")
    with col2:
        season_right = st.selectbox("Select Right Season", ["Maha 2023/24", "Yala 2024", "Maha 2024/25"], key="right_season")

    # --- Run button ---
    if st.button("Run Comparison"):
        st.success(f"Showing {season_left} vs {season_right}")

        # --- Create two folium maps ---
        map_left = folium.Map(location=[7.9, 80.7], zoom_start=8, tiles="OpenStreetMap")
        map_right = folium.Map(location=[7.9, 80.7], zoom_start=8, tiles="OpenStreetMap")

        # --- Add simple labels to each map ---
        folium.Marker([7.9, 80.7], popup=f"{season_left}").add_to(map_left)
        folium.Marker([7.9, 80.7], popup=f"{season_right}").add_to(map_right)

        # --- Display two maps side-by-side ---
        left_col, right_col = st.columns(2)

        with left_col:
            st.markdown(f"### 🌾 {season_left}")
            st_folium(map_left, width=350, height=400)

        with right_col:
            st.markdown(f"### 🌾 {season_right}")
            st_folium(map_right, width=350, height=400)

        st.caption("Use this view to visually compare two maps side-by-side.")
    else:
        st.info("👈 Select two seasons and click **Run Comparison** to see maps side-by-side.")
