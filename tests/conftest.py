import pytest

from processes.utils import boplikt_db


@pytest.fixture(autouse=True)
def nullstill_db_pool():
    """Nullstiller connection pool-en mellom hver test."""
    yield

    if boplikt_db._db_pool is not None:
        boplikt_db._db_pool.closeall()
        boplikt_db._db_pool = None
