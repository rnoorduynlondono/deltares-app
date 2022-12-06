import os
import matplotlib.pyplot as plt

from datetime import timedelta, date

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk
import matplotlib as mpl
from scipy.stats import boxcox

from connect import get_db2_engine, get_cloudant_client

st.set_page_config(layout='wide')
st.header("Deltares Nitrate APP")

color_map = mpl.colormaps['coolwarm']

@st.cache
def load_measuremaps():
    measure_map = {}
    with open('measuremap.csv') as f:
        for line in f:
            meas_id, meas = line.strip().split(';')
            measure_map[int(meas_id)] = meas

    return measure_map

@st.experimental_singleton
def get_db2_connection():
    engine = get_db2_engine()
    return engine

@st.experimental_singleton
def get_cloudant_connection():
    return get_cloudant_client()

def add_color(df, lambda_=0.3, add_opacity=False):
    data_normed = np.clip((boxcox(df.value, lambda_) + 2) / 8, 0, 1)

    rgb_values = color_map(data_normed, bytes=True)

    if not add_opacity:
        return df.assign(color=[x.tolist() for x in rgb_values])

    opacities = get_opacity(df)

    for i, opacity in enumerate(opacities):
        rgb_values[i, -1] = opacity

    return df.assign(color=[x.tolist() for x in rgb_values])


def get_opacity(df):
    earliest_time = df.timestamp.min()
    latest_time = df.timestamp.max()

    if earliest_time == latest_time:
        return [255,]

    max_range = (latest_time - earliest_time).total_seconds()

    return [
        int((((x - earliest_time).total_seconds() / max_range) ** 0.25) * 255)
        for x in df.timestamp
    ]


@st.cache
def get_user_counts():
    eng = get_db2_connection()
    user_counts = (
        pd.read_sql(
            f"""
            SELECT
                parcel_id as userid,
                total_nitrate_meas as cnt
            FROM USER_DATA
            ORDER BY cnt
            """,
            con=eng
        )
        .set_index('userid')
        .squeeze()
        .astype(int)
    )

    return user_counts

@st.cache
def get_user_data(user_id):
    eng = get_db2_connection()

    user_data = pd.read_sql(
        f"""
        SELECT
            *
        FROM USER_DATA
        WHERE parcel_id = {user_id}
        """,
        con=eng
    ).iloc[0]

    return user_data.to_dict()

@st.cache
def get_user_measurements(user_id):
    eng = get_db2_connection()

    return (
        pd.read_sql(
            f"""
            SELECT
                n."timestamp",
                n."value",
                n.latitude,
                n.longitude,
                n.category,
                n.confidence,
                n.meetpunt_code_ihw
            FROM NITRATEAPP_NL_WITH_LOC_ID as n
            INNER JOIN NITRATE_ID_MAPPING as m
            ON n.id = m.nitrate_id
            WHERE m.parcel_id = {user_id}
            """,
            con=eng
        )
        .sort_values(by=['timestamp'])
        .dropna()
        .rename(columns=str.lower)
        .assign(timestamp_str=lambda f: f.timestamp.dt.strftime("%Y-%m-%d"))
        .pipe(add_color, add_opacity=True)
    )

@st.cache
def get_all_values():
    eng = get_db2_connection()

    return (
        pd.read_sql(
            """
            select
                *
            from (
                select
                    n."value" as val
                from NITRATEAPP as n
                UNION
                select
                    m.waarde as val
                from MNLSO as m
            )
            where val < 100
            """,
            con=eng
        )
        .squeeze()
    )



@st.cache
def get_mnlso_measurements(meetpunt, min_time=date(year=1900, month=1, day=1)):
    eng = get_db2_connection()

    return (
        pd.read_sql(
            f"""
            SELECT
                datum as timestamp,
                groeiseizoen as season,
                waarde as value,
                meetpunt_code,
                'MNLSO' as category
            FROM MNLSO
            WHERE meetpunt_code = '{meetpunt}' AND parameter_code = 'NO3'
            AND datum > '{min_time:%Y-%m-%d}'
            ORDER BY datum
            """,
            con=eng
        )
        .rename(columns=str.lower)
        .assign(timestamp=lambda f: pd.to_datetime(f.timestamp))
        .dropna()
    )

@st.cache
def get_parcel_data(parcel_id):
    client = get_cloudant_connection()
    database = client['parcels']

    docs = database.get_query_result({'properties.OBJECTID': {'$eq': parcel_id}})

    head, *_ = docs
    return head

@st.cache
def get_locations():
    connection = get_db2_connection()

    return (
        pd.read_sql(
            """
            WITH recent_mnlso as (
                SELECT
                    MEETPUNT_CODE,
                    DATUM,
                    WAARDE
                FROM MNLSO as m
                WHERE m.PARAMETER_CODE = 'NO3' and m.DATUM = (
                    SELECT max(mm.DATUM)
                    FROM MNLSO as mm
                    WHERE m.MEETPUNT_CODE = mm.MEETPUNT_CODE
                )
            )
            SELECT
                r.MEETPUNT_CODE,
                r.DATUM as timestamp,
                r.WAARDE as value,
                CAST(lat as DOUBLE) as lat,
                CAST(lon as DOUBLE) as lon,
                'MNLSO' as category
            FROM recent_mnlso as r
            INNER JOIN LOCATIONS as l
            ON l.MEETPUNT_CODE_IHW = r.MEETPUNT_CODE
            """,
            con=connection
        )
        .dropna()
        .rename(columns=str.lower)
        .assign(timestamp=lambda f: pd.to_datetime(f.timestamp))
        .assign(timestamp_str=lambda f: f.timestamp.dt.strftime("%Y-%m-%d"))
        .pipe(add_color)
    )


col1, col2 = st.columns([4, 1])

# -----------SIDE BAR------------
with st.sidebar:
    user_counts = get_user_counts()
    min_meas, max_meas = user_counts.min(), user_counts.max()

    # first let the user choose the minimum amount of measurmeents per user
    number = st.slider( 'minimum measurements', int(min_meas), int(max_meas))

    # filter by the number
    user_counts_filtered = user_counts.loc[user_counts >= number]
    userid = st.selectbox("userid", user_counts_filtered.index)

user_data = get_user_data(userid)
user_meas = get_user_measurements(userid)

min_time = user_meas['timestamp'].min() - timedelta(days=100)

meetpunt, *_ = user_meas['meetpunt_code_ihw'].unique()
mnlso_meas = get_mnlso_measurements(meetpunt, min_time=min_time)

with col1:

    fig, ax  = plt.subplots(figsize=(10, 4))

    ax.scatter(user_meas['timestamp'], user_meas['value'], marker='x')
    ax.plot(
        mnlso_meas['timestamp'],
        mnlso_meas['value'],
        alpha=0.5,
        linewidth=2,
        color='tab:orange',
    )

    st.pyplot(fig)
    parcel_data = get_parcel_data(user_data['parcel_id'])

    INITIAL_VIEW_STATE = pdk.ViewState(
        longitude=user_meas.longitude.mean(),
        latitude=user_meas.latitude.mean(),
        zoom=16
    )

    parcel_layer = pdk.Layer(
        "GeoJsonLayer",
        parcel_data,
        opacity=0.7,
        filled=True,
        get_fill_color=[255, 255, 255],
    )

    meas_data = pdk.Layer(
        "ScatterplotLayer",
        user_meas,
        get_opacity="opacity",
        get_position=['longitude', 'latitude'],
        get_fill_color="color",
        get_radius=5,
        pickable=True,
    )

    locations = get_locations()

    loc_layer = pdk.Layer(
        "ScatterplotLayer",
        locations,
        filled=True,
        opacity=0.5,
        get_position=['lon', 'lat'],
        get_radius=3000,
        get_fill_color="color",
        pickable=True,
    )

    deck = pdk.Deck(
            layers=[
                parcel_layer,
                meas_data,
                loc_layer
            ],
            initial_view_state=INITIAL_VIEW_STATE,
            api_keys={'mapbox': os.environ['MAPBOX_TOKEN']},
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


with col2:
    fields = [
        'ow_Bodem',
        'ow_LandMgm',
        'ow_NutBnut',
        'ow_WatrBhr',
        'ow_ZuivRou',
        'ow_top5',
        'gw_Bodem',
        'gw_LandMgm',
        'gw_NutBnut',
        'gw_WatrBhr',
        'gw_ZuivRou',
        'gw_top5',
    ]

    measure_map = load_measuremaps()
    for f in fields:
        measures = parcel_data['properties'].get(f)

        if not measures:
            continue

        with st.expander(f):
            for m in measures:
                if m in measure_map:
                    st.write(measure_map[v])






