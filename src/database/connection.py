from contextlib import contextmanager
from typing import Iterator

from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg_pool import ConnectionPool


class Database:
    """Owns the PostgreSQL connection pool."""

    def __init__(self, url: str) -> None:
        self._pool = ConnectionPool(url, min_size=1, max_size=10, open=False)

    def open(self) -> None:
        self._pool.open(wait=True)
        with self.connection() as conn:
            register_vector(conn)

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        with self._pool.connection() as conn:
            register_vector(conn)
            yield conn

