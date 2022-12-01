import matplotlib.pyplot as plt

from datetime import datetime, timedelta, date

import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk

from connect import get_db2_engine, get_cloudant_client

st.header("Deltares Nitrate APP")


@st.cache(allow_output_mutation=True)
def get_db2_connection():
    engine = get_db2_engine()
    return engine


@st.cache(allow_output_mutation=True)
def get_cloudant_connection():
    return get_cloudant_client()


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

    return pd.read_sql(
        f"""
        SELECT
            *
        FROM NITRATEAPP_NL_WITH_LOC_ID as n
        INNER JOIN NITRATE_ID_MAPPING as m
        ON n.id = m.nitrate_id
        WHERE m.parcel_id = {user_id}
        """,
        con=eng
    ).sort_values(by=['timestamp'])


@st.cache
def get_mnlso_measurements(meetpunt, min_time=date(year=1900, month=1, day=1)):
    eng = get_db2_connection()

    return (
        pd.read_sql(
            f"""
            SELECT
                datum as dtime,
                groeiseizoen as season,
                waarde as val,
                meetpunt_code
            FROM MNLSO
            WHERE meetpunt_code = '{meetpunt}' AND parameter_code = 'NO3'
            AND datum > '{min_time:%Y-%m-%d}'
            ORDER BY datum
            """,
            con=eng
        )
        .assign(dtime=lambda f: pd.to_datetime(f.dtime))
    )

@st.cache
def get_parcel_data(parcel_id):
    client = get_cloudant_connection()
    database = client['parcels']

    docs = database.get_query_result({'properties.OBJECTID': {'$eq': parcel_id}})

    head, *_ = docs
    return head



user_counts = get_user_counts()
min_meas, max_meas = user_counts.min(), user_counts.max()

# -----------SIDE BAR------------

# first let the user choose the minimum amount of measurmeents per user
number  = st.sidebar.slider( 'minimum measurements', int(min_meas), int(max_meas))

# filter by the number
user_counts_filtered = user_counts.loc[user_counts >= number]
userid = st.sidebar.selectbox("userid", user_counts_filtered.index)

user_data = get_user_data(userid)
user_meas = get_user_measurements(userid)

min_time = user_meas['timestamp'].min()
st.write(min_time)
st.write(min_time - timedelta(days=30))

meetpunt, *_ = user_meas['meetpunt_code_ihw'].unique()
mnlso_meas = get_mnlso_measurements(meetpunt, min_time=min_time)

st.write(user_data)
# st.write(type(user_data['first_nitrate_meas_date']))
# st.table(user_meas)
st.table(user_meas.dtypes)
st.table(mnlso_meas.dtypes)

fig, ax  = plt.subplots()

ax.plot(user_meas['timestamp'], user_meas['value'])
ax.plot(mnlso_meas['dtime'], mnlso_meas['val'], alpha=0.5, linewidth=2)
st.pyplot(fig)

st.table(mnlso_meas)
parcel_data = get_parcel_data(user_data['parcel_id'])


coordinates, *_ = parcel_data['geometry']['coordinates']


INITIAL_VIEW_STATE = pdk.ViewState(
    longitude=np.mean([lon for lon, _ in coordinates]),
    latitude=np.mean([lat for _, lat in coordinates]),
    zoom=16
)

st.pydeck_chart(
    pdk.Deck(
        layers=[
            pdk.Layer(
                "GeoJsonLayer",
                parcel_data,
                opacity=0.7,
                filled=True,
                wireframe=True,
                get_fill_color=[255, 255, 255],
            )
        ],
        initial_view_state=INITIAL_VIEW_STATE
    )
)



