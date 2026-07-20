from src.config.settings import get_settings
from src.database.connection import Database
from src.database.init_db import initialize_database

settings = get_settings()
database = Database(settings.database_url)
database.open()
try:
    initialize_database(database)
    print("Database initialized")
finally:
    database.close()

