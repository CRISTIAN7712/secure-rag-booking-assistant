import argparse

from src.api.dependencies import get_service, set_database
from src.config.settings import get_settings
from src.database.connection import Database

parser = argparse.ArgumentParser()
parser.add_argument("query")
parser.add_argument("--top-k", type=int, default=5)
args = parser.parse_args()
database = Database(get_settings().database_url)
database.open()
set_database(database)
try:
    for result in get_service().search(args.query, args.top_k):
        print(f"{result.score:.4f} {result.document_id} {result.text}")
finally:
    database.close()

