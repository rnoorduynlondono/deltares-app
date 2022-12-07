from datetime import date
import streamlit as st
import pandas as pd
from utils import add_color, map_category
from connect import get_db2_engine, get_cloudant_client


@st.experimental_singleton
def get_db2_connection():
    engine = get_db2_engine()
    return engine


@st.experimental_singleton
def get_cloudant_connection():
    return get_cloudant_client()


@st.cache
def load_measuremaps():
    """Load mapping file from maatregelen value to actual measure"""

    measure_map = {}
    with open("measuremap.csv") as f:
        for line in f:
            meas_id, meas = line.strip().split(";")
            measure_map[int(meas_id)] = meas

    return measure_map


@st.cache
def get_user_counts():
    """Get user counts from the database"""
    eng = get_db2_connection()
    user_counts = (
        pd.read_sql(
            """
            SELECT
                parcel_id as userid,
                total_nitrate_meas as cnt
            FROM USER_DATA
            ORDER BY cnt
            """,
            con=eng,
        )
        .set_index("userid")
        .squeeze()
        .astype(int)
    )

    return user_counts


@st.cache(allow_output_mutation=True)
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
            ORDER BY n."timestamp"
            """,
            con=eng,
        )
        .sort_values(by=["timestamp"])
        .dropna()
        .rename(columns=str.lower)
        .assign(timestamp_str=lambda f: f.timestamp.dt.strftime("%Y-%m-%d"))
        .pipe(add_color, add_opacity=True)
        .assign(category=lambda f: f.category.map(map_category))
    )


@st.cache
def get_all_values():
    eng = get_db2_connection()

    return pd.read_sql(
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
        con=eng,
    ).squeeze()


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
            con=eng,
        )
        .rename(columns=str.lower)
        .assign(timestamp=lambda f: pd.to_datetime(f.timestamp))
        .dropna()
    )


@st.cache
def get_parcel_data(parcel_id):
    client = get_cloudant_connection()
    database = client["parcels"]

    docs = database.get_query_result({"properties.OBJECTID": {"$eq": parcel_id}})

    head, *_ = docs
    return head


@st.cache
def get_locations(lat, lon, thres=0.3):
    connection = get_db2_connection()

    return (
        pd.read_sql(
            f"""
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
            WHERE
                abs(CAST(lat as DOUBLE) - {lat}) < {thres} AND
                abs(CAST(lon as DOUBLE) - {lon}) < {thres}
            """,
            con=connection,
        )
        .dropna()
        .rename(columns=str.lower)
        .assign(timestamp=lambda f: pd.to_datetime(f.timestamp))
        .assign(timestamp_str=lambda f: f.timestamp.dt.strftime("%Y-%m-%d"))
        .pipe(add_color)
    )
