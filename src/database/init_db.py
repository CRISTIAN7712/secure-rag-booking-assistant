from pathlib import Path

from src.database.connection import Database


def initialize_database(database: Database, sql_path: Path | None = None) -> None:
    paths = [sql_path] if sql_path else sorted(
        (Path(__file__).parents[2] / "sql").glob("[0-9][0-9][0-9]_*.sql")
    )
    with database.connection() as conn:
        for path in paths:
            conn.execute(path.read_text(encoding="utf-8"))
