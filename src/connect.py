import os
import requests
from cloudant.client import Cloudant
from urllib.parse import quote
from sqlalchemy import create_engine

import ibmpairs.authentication as authentication
import ibmpairs.client as client


AUTH_PROVIDER_BASE = "https://auth-b2b-twc.ibm.com"


def get_cloudant_client():
    client = Cloudant(
        os.environ["CLOUDANT_USERNAME"],
        os.environ["CLOUDANT_PASSWORD"],
        url=os.environ["CLOUDANT_URL"],
    )

    client.connect()

    return client


def get_db2_engine():
    uri = "{username}:{password}@{host}:{port}/{database};{extra}".format(
        username=os.environ["DB2_USERNAME"],
        password=quote(os.environ["DB2_PASSWORD"]),
        database=os.environ["DB2_DATABASE"],
        host=os.environ["DB2_HOST"],
        port=os.environ["DB2_PORT"],
        extra="PROTOCOL=TCPIP;SECURITY=SSL",
    )

    return create_engine(f"db2+ibm_db://{uri}")


def get_eis_client():
    return client.Client(
        authentication=authentication.OAuth2(
            username=os.environ["EIS_USERNAME"], api_key=os.environ["EIS_APIKEY"]
        )
    )


def get_eis_access_token():
    auth_response = requests.post(
        AUTH_PROVIDER_BASE + "/connect/token",
        headers={"Context-Type": "application/x-www-form-urlencoded"},
        data=[
            ("client_id", "ibm-pairs"),
            ("grant_type", "apikey"),
            ("apikey", os.environ["EIS_APIKEY"]),
        ],
    ).json()

    return auth_response.get("access_token")
