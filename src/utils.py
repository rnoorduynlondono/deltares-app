import numpy as np
import matplotlib as mpl
from scipy.stats import boxcox

SURFACE_WATER = "surface water"
GROUND_WATER = "ground water"
OTHER = "other"

category_mappings = {
    "oppervlaktewater": SURFACE_WATER,
    "grondwater": GROUND_WATER,
    "groundwater": GROUND_WATER,
    "surface water": SURFACE_WATER,
}


def map_category(category):
    return category_mappings.get(category.lower(), OTHER)


def add_color(
    df,
    lambda_=0.3,
    add_opacity=False,
    color_map=mpl.colormaps["coolwarm"],
):
    """Add color column to dataframe based on 'value' column"""

    if df.empty:
        return df.assign(color=[])

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
        return [
            255,
        ]

    max_range = (latest_time - earliest_time).total_seconds()

    return [
        int((((x - earliest_time).total_seconds() / max_range) ** 0.25) * 255)
        for x in df.timestamp
    ]
