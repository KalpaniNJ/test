import requests
import pandas as pd
import folium
import streamlit as st

def show_rainfall_api(
    map_obj, geom_json, start_date, end_date, method,
    country_name, state_name, basin_name=None, version=0
):
    """
    Fetch rainfall data from the public POST API and visualize results.
    Dynamically uses user inputs from the Streamlit dashboard.
    """

    # API endpoint (replace with your real link)
    api_url = "https://dmsdemo.iwmi.org:8443/flood/extreme_rainfall/map"

    # Build payload matching the API's required schema exactly
    payload = {
        "country_name": str(country_name),
        "state_name": str(state_name) if state_name else "string",
        "basin_name": str(basin_name) if basin_name else "string",
        "version": int(version),
        "palette": ["string"],  # API expects an array of strings
        "temporal_aggregation": str(method),  # string (not lowercase)
        "precipitation_threshold": "0.01",  # must be string
        "start_date": str(start_date),
        "end_date": str(end_date)
    }

    try:
        # TEST BLOCK: Ignore SSL verification for now
        response = requests.post(api_url, json=payload, timeout=60, verify=False)

        # Print status and response directly in Streamlit for debugging
        st.write("API URL:", api_url)
        st.write("Payload Sent:", payload)
        st.write("Status Code:", response.status_code)
        st.write("Response Text:")
        st.text(response.text)


        # Show status and possible API message
        if response.status_code != 200:
            st.error(f"API Error {response.status_code}: {response.text}")
            return map_obj, pd.DataFrame()

        data = response.json()

        # Show debugging info
        st.subheader("API Request Sent")
        st.json(payload)
        st.subheader("API Response Received")
        st.json(data)

        # Simple visual confirmation on map
        folium.Marker(
            [7.8731, 80.7718],
            popup=f"Rainfall data retrieved for {state_name or basin_name}",
            tooltip="API response received",
            icon=folium.Icon(color="blue", icon="cloud")
        ).add_to(map_obj)

        # Return as DataFrame for table display
        return map_obj, pd.DataFrame([data])

    except requests.exceptions.RequestException as e:
        st.error(f"⚠️ Request failed: {e}")
        return map_obj, pd.DataFrame()
