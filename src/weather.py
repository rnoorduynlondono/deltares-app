import connect
import streamlit as st
import requests
from datetime import timedelta
from operator import methodcaller
import math

import ibmpairs.query as query

layers = [
    {"id": "49250"},  # yes
    # {"id": "49255"}, # maybe
    {"id": "49309"},  # yes
    # {"id": "49251"},
    {"id": "49308"},  # yes
    # {"id": "49249"},
]

date_to_str = methodcaller("strftime", "%Y-%m-%dT%H:%M:%SZ")


def get_days_between(start_date, end_date, delta=timedelta(days=1)):
    cur = start_date
    while cur < end_date:
        yield cur
        cur += delta
    yield end_date


def get_intervals(start_date, end_date, max_points=30):
    day_diff = (end_date - start_date).total_seconds() / (60 * 60 * 24)
    delta = day_diff / max_points

    if delta < 1:
        return [{"start": date_to_str(start_date), "end": date_to_str(end_date)}]

    delta = math.ceil(delta)
    days = get_days_between(start_date, end_date, delta=timedelta(days=delta))

    return [{"snapshot": date_to_str(d)} for d in days]


@st.cache
def get_weather_data(lat, lon, start_date, end_date):
    client = connect.get_eis_client()

    query_json = {
        "layers": layers,
        "spatial": {
            "type": "point",
            "coordinates": [f"{lat}", f"{lon}"],
        },
        "temporal": {"intervals": get_intervals(start_date, end_date)},
    }

    query_res = query.submit(query_json)
    return query_res.point_data_as_dataframe()
