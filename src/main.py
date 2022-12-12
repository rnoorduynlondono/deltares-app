import os
import matplotlib.pyplot as plt

from datetime import timedelta, datetime

import pandas as pd
import streamlit as st
import pydeck as pdk

import loaders
import utils
import weather


import containers


def main():
    st.header("Deltares Nitrate APP")

    result = containers.sidebar()

    if result.userid is None:
        st.error(
            f"No user ids found with at least {result.min_meas} measurements, "
            f"between {result.min_date:%Y-%m-%d} - {result.max_date:%Y-%m-%d}."
        )
        st.warning("Try choosing a wider window or a different number of measurements!")
        return

    containers.interactive_map(result)
    containers.metrics(result)
    containers.weather(result)
    containers.measures(result)


main()
