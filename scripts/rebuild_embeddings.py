import argparse
from uuid import UUID

from src.api.dependencies import get_service, set_database
from src.config.settings import get_settings
from src.database.connection import Database

parser = argparse.ArgumentParser()
parser.add_argument("--document-id", type=UUID)
args = parser.parse_args()
database = Database(get_settings().database_url)
database.open()
set_database(database)
try:
    print(f"Updated {get_service().rebuild_embeddings(args.document_id)} embeddings")
finally:
    database.close()

