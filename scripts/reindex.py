import argparse

from src.config.settings import get_settings
from src.database.connection import Database

parser = argparse.ArgumentParser()
parser.add_argument("--type", choices=["hnsw", "ivfflat"], default="hnsw")
parser.add_argument("--lists", type=int, default=100)
args = parser.parse_args()
database = Database(get_settings().database_url)
database.open()
try:
    with database.connection() as conn:
        conn.execute("DROP INDEX IF EXISTS idx_embeddings_hnsw_cosine")
        conn.execute("DROP INDEX IF EXISTS idx_embeddings_ivfflat_cosine")
        if args.type == "hnsw":
            conn.execute("CREATE INDEX idx_embeddings_hnsw_cosine ON embeddings USING hnsw (embedding vector_cosine_ops)")
        else:
            conn.execute(
                f"CREATE INDEX idx_embeddings_ivfflat_cosine ON embeddings USING ivfflat "
                f"(embedding vector_cosine_ops) WITH (lists = {args.lists})"
            )
            conn.execute("ANALYZE embeddings")
    print(f"Created {args.type} index")
finally:
    database.close()

