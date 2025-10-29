import folium
import streamlit as st

def add_weather_layers(map_obj, api_key):
    """Add OpenWeather map layers to a Folium map."""

    base_url = "https://tile.openweathermap.org/map"
    
    weather_layers = {
        "Temperature": f"{base_url}/temp_new/{{z}}/{{x}}/{{y}}.png?appid={325b2939eac475787bf1a3e9656ccb67}",
        "Clouds": f"{base_url}/clouds_new/{{z}}/{{x}}/{{y}}.png?appid={325b2939eac475787bf1a3e9656ccb67}",
        "Precipitation": f"{base_url}/precipitation_new/{{z}}/{{x}}/{{y}}.png?appid={325b2939eac475787bf1a3e9656ccb67}",
        "Wind Speed": f"{base_url}/wind_new/{{z}}/{{x}}/{{y}}.png?appid={325b2939eac475787bf1a3e9656ccb67}",
        "Pressure": f"{base_url}/pressure_new/{{z}}/{{x}}/{{y}}.png?appid={325b2939eac475787bf1a3e9656ccb67}"
    }

    for name, url in weather_layers.items():
        folium.TileLayer(
            tiles=url,
            name=name,
            attr="OpenWeatherMap",
            overlay=True,
            control=True,
            opacity=0.8
        ).add_to(map_obj)

    return map_obj
