import argparse
import json
from pathlib import Path

from src.api.dependencies import get_service, set_database
from src.config.settings import get_settings
from src.database.connection import Database

parser = argparse.ArgumentParser(description="Ingest PDF, TXT and Markdown documents")
parser.add_argument("paths", nargs="+", type=Path)
parser.add_argument("--metadata", default="{}")
args = parser.parse_args()
settings = get_settings()
database = Database(settings.database_url)
database.open()
set_database(database)
try:
    for source in args.paths:
        paths = source.rglob("*") if source.is_dir() else [source]
        for path in paths:
            if path.is_file() and path.suffix.lower() in {".pdf", ".txt", ".md", ".markdown"}:
                print(f"{path}: {get_service().ingest(path, json.loads(args.metadata))}")
finally:
    database.close()

