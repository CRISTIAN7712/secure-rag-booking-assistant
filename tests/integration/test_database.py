import os

import pytest

from src.database.connection import Database
from src.database.init_db import initialize_database


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"), reason="Set RUN_INTEGRATION=1")
def test_pgvector_extension() -> None:
    database = Database(os.environ["DATABASE_URL"])
    database.open()
    try:
        initialize_database(database)
        with database.connection() as conn:
            assert conn.execute("SELECT extname FROM pg_extension WHERE extname='vector'").fetchone()[0] == "vector"
    finally:
        database.close()

