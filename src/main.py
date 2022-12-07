import os
import matplotlib.pyplot as plt

from datetime import timedelta

import streamlit as st
import pydeck as pdk

import loaders
import utils


st.set_page_config(layout="wide")
st.header("Deltares Nitrate APP")


metric_col, data_col, measure_col = st.columns([1, 4, 2])

# -----------SIDE BAR------------
with st.sidebar:
    user_counts = loaders.get_user_counts()
    min_meas, max_meas = user_counts.min(), user_counts.max()

    # first let the user choose the minimum amount of measurmeents per user
    number = st.slider("minimum measurements", int(min_meas), int(max_meas))

    # filter by the number
    user_counts_filtered = user_counts.loc[user_counts >= number]
    userid = st.selectbox("userid", user_counts_filtered.index)

    st.write("---------")

    # add options to filter MNLSO data
    show_mnlso = st.checkbox("Show MNLSO data")
    mnlso_threshold = st.slider("Distance to MNLSO", 0.1, 1.0, step=0.05)


user_meas = loaders.get_user_measurements(userid)
min_time = user_meas["timestamp"].min() - timedelta(days=100)

meetpunt, *_ = user_meas["meetpunt_code_ihw"].unique()
mnlso_meas = loaders.get_mnlso_measurements(meetpunt, min_time=min_time)

with data_col:

    fig, ax = plt.subplots(figsize=(10, 4))

    category_to_marker = {
        utils.SURFACE_WATER: "^",
        utils.GROUND_WATER: "v",
        utils.OTHER: "*",
    }

    for category, marker in category_to_marker.items():
        data = user_meas.loc[user_meas.category == category]
        ax.scatter(data["timestamp"], data["value"], c="tab:blue", marker=marker)

    ax.plot(
        mnlso_meas["timestamp"],
        mnlso_meas["value"],
        alpha=0.5,
        linewidth=2,
        color="tab:orange",
    )

    st.pyplot(fig)
    parcel_data = loaders.get_parcel_data(userid)

    mean_lon = user_meas.longitude.mean()
    mean_lat = user_meas.latitude.mean()

    INITIAL_VIEW_STATE = pdk.ViewState(longitude=mean_lon, latitude=mean_lat, zoom=16)

    parcel_layer = pdk.Layer(
        "GeoJsonLayer",
        parcel_data,
        opacity=0.7,
        filled=True,
        get_fill_color=[255, 255, 255],
    )

    meas_layer = pdk.Layer(
        "ScatterplotLayer",
        user_meas,
        get_opacity="opacity",
        get_position=["longitude", "latitude"],
        get_fill_color="color",
        get_radius=5,
        pickable=True,
    )

    locations = loaders.get_locations(mean_lat, mean_lon, thres=mnlso_threshold)

    mnlso_layer = pdk.Layer(
        "ScatterplotLayer",
        locations,
        filled=True,
        opacity=0.5,
        get_position=["lon", "lat"],
        get_radius=3000,
        get_fill_color="color",
        pickable=True,
    )

    layers = [
        parcel_layer,
        meas_layer,
    ]

    if show_mnlso:
        layers.append(mnlso_layer)

    deck = pdk.Deck(
        initial_view_state=INITIAL_VIEW_STATE,
        layers=layers,
        api_keys={"mapbox": os.environ["MAPBOX_TOKEN"]},
        tooltip={
            "html": (
                "<b>Nitrate</b>: {value} <br>"
                "Measurement Date: {timestamp_str} <br>"
                "Category: {category} <br>"
            )
        },
        map_style=pdk.map_styles.LIGHT,
    )

    deck.to_html()
    st.pydeck_chart(deck)


with measure_col:
    fields_surface = [
        "ow_Bodem",
        "ow_LandMgm",
        "ow_NutBnut",
        "ow_WatrBhr",
        "ow_ZuivRou",
        "ow_top5",
    ]

    fields_ground = [
        "gw_Bodem",
        "gw_LandMgm",
        "gw_NutBnut",
        "gw_WatrBhr",
        "gw_ZuivRou",
        "gw_top5",
    ]

    measure_map = loaders.load_measuremaps()
    map_column = {
        "Bodem": "Bodemverbetering",
        "LandMgm": "LandManagement",
        "NutBnut": "Nutrientenbenutting",
        "WatrBhr": "Waterbeheer",
    }

    tup = [
        ("Surface Water Management", fields_surface),
        ("Ground Water Management", fields_ground),
    ]

    for subtitle, fields in tup:
        st.subheader(subtitle)
        for f in fields_surface:
            _, column_name = f.split("_")
            measures = parcel_data["properties"].get(f)

            if not measures:
                continue

            with st.expander(map_column.get(column_name, column_name)):
                for m in measures:
                    if m in measure_map:
                        st.write(measure_map[m])

with metric_col:
    last_measurement = user_meas.iloc[-1].copy().value
    prev_measurement = last_measurement
    if len(user_meas) > 1:
        prev_measurement = user_meas.iloc[-2].copy().value

    st.metric(
        label="Nitrate (User)",
        value=last_measurement,
        delta=last_measurement - prev_measurement,
    )
