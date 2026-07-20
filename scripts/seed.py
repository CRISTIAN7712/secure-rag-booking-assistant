from pathlib import Path
from tempfile import TemporaryDirectory

from src.api.dependencies import get_service, set_database
from src.config.settings import get_settings
from src.database.connection import Database

samples = {
    "postgres.txt": "PostgreSQL es una base de datos relacional extensible y robusta.",
    "rag.md": "# RAG\nRetrieval-Augmented Generation combina recuperación de contexto con generación.",
}
database = Database(get_settings().database_url)
database.open()
set_database(database)
try:
    with TemporaryDirectory() as directory:
        for name, text in samples.items():
            path = Path(directory) / name
            path.write_text(text, encoding="utf-8")
            print(get_service().ingest(path, {"category": "example"}))
finally:
    database.close()

