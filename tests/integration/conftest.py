from pathlib import Path

import psycopg2
import pytest
from testcontainers.community.postgres import PostgresContainer

from processes.utils import boplikt_db

ROT = Path(__file__).parents[2]
SEED = ROT / "dev" / "init-db.sql"
POSTGIS_IMAGE = "postgis/postgis:18-3.6"
DB_SCHEMA = "inndelinger"
DB_NAME = "boplikt_db"
DB_USER = "boplikt_user"
DB_PASSWORD = "boplikt_pass"


@pytest.fixture(scope="session", autouse=True)
def postgis():
    """Starter PostGIS, laster dev/init-db.sql og peker boplikt_db mot containeren."""
    with (
        PostgresContainer(
            POSTGIS_IMAGE,
            username=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME,
        ) as container,
        pytest.MonkeyPatch.context() as mp,
    ):
        host = container.get_container_host_ip()
        port = str(container.get_exposed_port(5432))

        _last_seed(host, port, container)

        mp.setenv("INNDELINGER_DB_HOST", host)
        mp.setenv("DB_PORT", port)
        mp.setenv("DB_NAME", container.dbname)
        mp.setenv("INNDELINGER_DB_USER", container.username)
        mp.setenv("INNDELINGER_DB_PASSWORD", container.password)
        mp.setattr(boplikt_db, "_DB_SCHEMA", DB_SCHEMA)

        yield container


def _last_seed(host, port, container):
    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=container.dbname,
        user=container.username,
        password=container.password,
    )
    try:
        with conn, conn.cursor() as cur:
            cur.execute(SEED.read_text())
    finally:
        conn.close()
