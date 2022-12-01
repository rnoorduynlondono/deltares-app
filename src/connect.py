import os
from cloudant.client import Cloudant
from urllib.parse import quote

from sqlalchemy import create_engine

def get_cloudant_client():
    client = Cloudant(
        os.environ['CLOUDANT_USERNAME'],
        os.environ['CLOUDANT_PASSWORD'],
        url=os.environ['CLOUDANT_URL'],
    )

    client.connect()

    return client


def get_db2_engine():
    uri = (
        "{username}:{password}@{host}:{port}/{database};"
        "PROTOCOL=TCPIP;SECURITY=SSL"
    ).format(
        username=os.environ["DB2_USERNAME"],
        password=quote(os.environ["DB2_PASSWORD"]),
        database=os.environ["DB2_DATABASE"],
        host=os.environ["DB2_HOST"],
        port=os.environ["DB2_PORT"],
    )

    return create_engine(f"db2+ibm_db://{uri}")
