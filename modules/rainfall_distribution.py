import streamlit as st
import ee
import geemap.foliumap as geemap

st.set_page_config(page_title="Rainfall Data", layout="wide")

st.title("🌧️ GPM Rainfall Visualization")

# --- User inputs ---
date = st.date_input("Select a Date", value=None)
if date:
    date_range = ee.Date(str(date)).getRange('day')

    # Load GPM IMERG V07
    dataset = ee.ImageCollection('NASA/GPM_L3/IMERG_V07') \
        .filter(ee.Filter.date(date_range))

    precipitation = dataset.select('precipitationCal').max() \
        .updateMask(dataset.select('precipitationCal').max().gt(1))

    vis_params = {
        'min': 0,
        'max': 50,
        'palette': ['white', 'blue', 'cyan', 'green', 'yellow', 'red']
    }

    Map = geemap.Map(center=[7.8, 80.7], zoom=7)
    Map.addLayer(precipitation, vis_params, f"GPM Precipitation ({date})")
    Map.add_colorbar(vis_params, label="mm/hr")
    Map.to_streamlit(height=600)

else:
    st.info("👈 Please select a date to display rainfall.")
