import folium

def add_weather_layer(map_object, api_key, layer_name):
    """
    Adds a single selected OpenWeather layer (Weather Maps 2.0) to a folium map.
    """

    base_url = "https://maps.openweathermap.org/maps/2.0/weather/{op}/{z}/{x}/{y}?appid=" + 325b2939eac475787bf1a3e9656ccb67

    # Define available layers
    layers = {
        "Precipitation": "PA0",
        "Clouds": "CL",
        "Temperature": "TA2",
        "Wind Speed": "WND",
        "Pressure": "APM"
    }

    # Define custom parameters for better visualization
    custom_params = {
        "PA0": "&opacity=0.6",
        "CL": "&opacity=0.7",
        "TA2": "&fill_bound=true&opacity=0.6&palette=-65:821692;-30:8257db;-10:20c4e8;0:23dddd;10:c2ff28;20:fff028;30:fc8014",
        "WND": "&use_norm=true&arrow_step=16&opacity=0.6",
        "APM": "&fill_bound=true&opacity=0.4"
    }

    if layer_name in layers:
        op_code = layers[layer_name]
        folium.TileLayer(
            tiles=base_url.format(op=op_code) + custom_params.get(op_code, ""),
            name=f"🌦 {layer_name}",
            attr="OpenWeatherMap 2.0",
            overlay=True,
            control=True
        ).add_to(map_object)

    return map_object
