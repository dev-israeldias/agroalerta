"""Acesso aos 3 armazenamentos: PostgreSQL (dados mestres/consolidados),
MongoDB (dados brutos das APIs) e DuckDB (histórico analítico)."""
import duckdb
import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient

from .config import DUCKDB_PATH, MONGO_DB, MONGO_URI, PG_DSN


def pg():
    # uso: with pg() as c: c.execute(...)  -> commit automático ao sair do bloco
    return psycopg.connect(PG_DSN, row_factory=dict_row)


def mongo():
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)[MONGO_DB]


def duck():
    con = duckdb.connect(DUCKDB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS clima_historico (
             propriedade_id INTEGER, data DATE,
             tmax DOUBLE, tmin DOUBLE, precip DOUBLE, et0 DOUBLE, vento_max DOUBLE,
             PRIMARY KEY (propriedade_id, data))"""
    )
    return con
