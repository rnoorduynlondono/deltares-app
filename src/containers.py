import streamlit as st

import os
from datetime import timedelta, datetime

import pydeck as pdk
import matplotlib.pyplot as plt

import utils
import loaders

from dataclasses import dataclass


@dataclass
class Result:
    userid: int
    min_date: datetime
    max_date: datetime
    min_meas: int
    show_mnlso: bool
    mnlso_threshold: float


MAX_DATE = datetime(year=2022, month=12, day=1)
MIN_DATE = datetime(year=2017, month=1, day=1)


def make_line():
    st.write("-------")


def sidebar():
    user_choice = st.container()

    with st.sidebar:
        # determine the minimum number of measurements
        min_meas = st.slider("Minimum measurements", min_value=1, max_value=50, value=5)

        # number of days to look back for the app
        lookback_days = st.slider("Number of days to look back", 14, 150)

        usage = loaders.get_usage_dates(lookback_days=lookback_days, min_meas=min_meas)

        st.caption(
            f"The following shows the number of unique users with at least {min_meas}"
            f" measurements in the last {lookback_days} days"
        )

        st.area_chart(usage.rename("# users"))

        make_line()

        st.caption(
            "Use the date picker below to choose what 'Today' "
            "should be for the purposes of the demo"
        )

        today_demo = st.slider(
            "Today",
            min_value=MIN_DATE,
            max_value=MAX_DATE,
            value=MAX_DATE,
        )

        max_date = today_demo
        min_date = max_date - timedelta(days=lookback_days)

        make_line()

        user_counts = loaders.get_user_ids(min_date, max_date, min_meas)

        userid = user_choice.selectbox("userid", user_counts.index)

        make_line()

        # add options to filter MNLSO data
        show_mnlso = st.checkbox("Show MNLSO data")
        mnlso_threshold = st.slider("Distance to MNLSO", 0.1, 5.0, step=0.05)

        make_line()

    return Result(
        userid,
        min_date,
        max_date,
        min_meas,
        show_mnlso,
        mnlso_threshold,
    )


def interactive_map(result):
    with st.container():
        user_meas = loaders.get_user_measurements(
            result.userid,
            result.min_date,
            result.max_date,
        )

        mean_lon = user_meas.longitude.mean()
        mean_lat = user_meas.latitude.mean()

        parcel_data = loaders.get_parcel_data(result.userid)

        INITIAL_VIEW_STATE = pdk.ViewState(
            longitude=mean_lon,
            latitude=mean_lat,
            zoom=16,
        )

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
            radius_scale=10,
            radius_min_pixels=5,
            radius_max_pixels=10,
            pickable=True,
        )

        locations = loaders.get_locations(
            mean_lat, mean_lon, thres=result.mnlso_threshold
        )

        mnlso_layer = pdk.Layer(
            "ScatterplotLayer",
            locations,
            filled=True,
            opacity=0.5,
            get_position=["lon", "lat"],
            get_fill_color="color",
            radius_min_pixels=10,
            radius_max_pixels=20,
            pickable=True,
        )

        layers = [
            parcel_layer,
            meas_layer,
        ]

        if result.show_mnlso:
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


def metrics(result):
    user_meas = loaders.get_user_measurements(
        result.userid,
        result.min_date,
        result.max_date,
    )
    with st.container():
        last_measurement = user_meas.iloc[-1].copy()
        prev_measurement = last_measurement
        if len(user_meas) > 1:
            prev_measurement = user_meas.iloc[-2].copy()

        st.metric(
            label="Nitrate (User)",
            value=last_measurement.value,
            delta=last_measurement.value - prev_measurement.value,
        )

        st.metric(
            label="Measurement Date",
            value=f"{last_measurement.timestamp:%Y-%m-%d %H:%M:%S}",
        )


def measures(result):
    parcel_data = loaders.get_parcel_data(result.userid)

    with st.container():
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

        col1, col2 = st.columns(2)
        tup = [
            ("Surface Water Management", fields_surface, col1),
            ("Ground Water Management", fields_ground, col2),
        ]

        for subtitle, fields, col in tup:
            with col:
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


def weather(result):
    control, plots = st.columns([2, 5])
    layers = loaders.get_weather_layers()
    layers_to_show = []

    with control:

        show_precipitation = st.checkbox("Show precipitation")
        resolution = None

        if show_precipitation:
            resolution = st.radio(
                "Precipitation resolution:",
                ["1 h", "6 h", "24 h"],
            )
            show_snowfall = st.checkbox("Show snowfall")

        show_temperature = st.checkbox("Show temperature")

    with plots:
        n_axes = 1 + int(show_precipitation) + int(show_temperature)

        weather_data = loaders.get_weather_data(
            result.userid,
            result.min_date,
            result.max_date,
        )

        nitrate_data = loaders.get_user_measurements(
            result.userid,
            result.min_date,
            result.max_date,
        )

        fig, axes = plt.subplots(
            figsize=(10, 3 * n_axes),
            nrows=n_axes,
            sharex=True,
        )

        if n_axes > 1:
            nitrate_ax, *others = axes
            others = iter(others)
        else:
            nitrate_ax = axes
            others = []

        category_to_marker = {
            utils.SURFACE_WATER: "^",
            utils.GROUND_WATER: "v",
            utils.OTHER: "*",
        }

        for category, marker in category_to_marker.items():
            sub = nitrate_data.loc[nitrate_data.category == category]
            nitrate_ax.scatter(
                sub.timestamp, sub.value, marker=marker, color="tab:blue"
            )

        nitrate_ax.set_xlim([result.min_date, result.max_date])
        nitrate_ax.set_ylabel("NO3")

        if show_precipitation:
            ax = next(others)

            layer = f"Precip past {resolution}"
            sub = weather_data.loc[weather_data.layer_name == layer]
            ax.plot(sub.timestamp, sub.value)

            if show_snowfall:
                sub = weather_data.loc[weather_data.layer_name == "Snow past 24 h"]
                ax.plot(sub.timestamp, sub.value, color="grey")

            ax.set_ylabel(layer)

        if show_temperature:
            ax = next(others)

            min_temp_layer = "Minimum temperature past 24 h"
            max_temp_layer = "Maximum temperature past 24 h"

            sub_min = weather_data.loc[weather_data.layer_name == min_temp_layer]
            sub_max = weather_data.loc[weather_data.layer_name == max_temp_layer]

            ax.plot(sub_min.timestamp, sub_min.value, color="tab:blue")
            ax.plot(sub_max.timestamp, sub_max.value, color="tab:red")

            ax.set_ylabel("Temperature (K)")

        st.pyplot(fig)

    # meetpunt, *_ = user_meas["meetpunt_code_ihw"].unique()
    # mnlso_meas = loaders.get_mnlso_measurements(meetpunt, min_time=min_date)
