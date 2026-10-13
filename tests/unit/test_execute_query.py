"""Enhetstester for feilhåndtering i databaseoppslag."""

from unittest.mock import MagicMock

import pytest
from psycopg2 import OperationalError
from pygeoapi.process.base import ProcessorExecuteError

from processes.utils import boplikt_db


def test_feil_ved_aapning_av_tilkobling_gir_generell_feil(monkeypatch, caplog):
    pool = MagicMock()
    pool.getconn.side_effect = OperationalError(
        'could not translate host name "db" to address'
    )
    monkeypatch.setattr(boplikt_db, "_get_pool", lambda: pool)

    with pytest.raises(ProcessorExecuteError) as feil:
        boplikt_db.sjekk_kommune_boplikt("0301")

    assert feil.value.message == "En feil oppstod, prøv igjen senere."
    assert pool.getconn.call_count == 2
    pool.putconn.assert_not_called()
    assert any(post.levelname == "ERROR" for post in caplog.records)
