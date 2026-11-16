import os

PG_DSN = os.getenv("PG_DSN", "postgresql://agro:agro@localhost:5432/agroalerta")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "agroalerta")
DUCKDB_PATH = os.getenv("DUCKDB_PATH", "../data/analytics.duckdb")
CULTURAS_CSV = os.getenv("CULTURAS_CSV", "../data/culturas.csv")
