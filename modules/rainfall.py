import requests
import pandas as pd
import folium
import streamlit as st

def show_rainfall_api(map_obj, geom_json, start_date, end_date, method, 
                      country_name, state_name, basin_name=None, version=0):
    """
    Fetch rainfall data from the public POST API and visualize results.
    Dynamically uses user inputs from the Streamlit dashboard.
    """

    # API endpoint
    api_url = "http://dmsdemo.iwmi.org:8443/flood/extreme_rainfall/map"

    # Build dynamic payload from user selections
    payload = {
        "country_name": country_name,
        "state_name": state_name if state_name else "",
        "basin_name": basin_name if basin_name else "",
        "version": version,
        "palette": ["Blues"],
        "temporal_aggregation": method.lower(),  # sum, mean, max
        "precipitation_threshold": "0.01",
        "start_date": str(start_date),
        "end_date": str(end_date)
    }

    try:
        # Send the POST request
        response = requests.post(api_url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()

        # Show the raw response (for debugging or user info)
        st.subheader("📤 API Request Sent")
        st.json(payload)
        st.subheader("📥 API Response Received")
        st.json(data)

        # Add a simple marker for now (visual confirmation)
        folium.Marker(
            [7.8731, 80.7718],
            popup=f"Rainfall data retrieved for {state_name}",
            tooltip="API response received",
            icon=folium.Icon(color="blue", icon="cloud")
        ).add_to(map_obj)

        return map_obj, pd.DataFrame([data])

    except Exception as e:
        st.error(f"Error fetching rainfall data: {e}")
        return map_obj, pd.DataFrame()
