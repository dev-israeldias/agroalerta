"""Pipeline de dados do AgroAlerta.

  coletar     API Open-Meteo  ->  MongoDB (raw_weather, JSON bruto)
  consolidar  MongoDB         ->  PostgreSQL (weather_daily)      [pode ser feito pelo Apache Hop]
  historico   PostgreSQL      ->  DuckDB (clima_historico)
  avaliar     PostgreSQL + DuckDB + CSV de culturas -> PostgreSQL (alertas, risco_propriedade)
  backfill    API de arquivo Open-Meteo -> DuckDB (histórico de anos anteriores)

Uso:  python -m app.etl [coletar|consolidar|historico|avaliar|backfill|tudo]
"""
import datetime as dt
import logging
import sys

import requests
from psycopg.types.json import Jsonb

from . import risk
from .config import CULTURAS_CSV
from .db import duck, mongo, pg

log = logging.getLogger("etl")
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY = "temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration,wind_speed_10m_max"


def propriedades():
    with pg() as c:
        return c.execute("SELECT * FROM propriedades ORDER BY id").fetchall()


def _linhas(payload):
    d = payload["daily"]
    return list(zip(d["time"], d["temperature_2m_max"], d["temperature_2m_min"],
                    d["precipitation_sum"], d["et0_fao_evapotranspiration"], d["wind_speed_10m_max"]))


def coletar():
    db, n = mongo(), 0
    for p in propriedades():
        r = requests.get(FORECAST_URL, timeout=30, params={
            "latitude": p["lat"], "longitude": p["lon"], "daily": DAILY,
            "past_days": 7, "forecast_days": 7, "timezone": "America/Sao_Paulo"})
        r.raise_for_status()
        db.raw_weather.insert_one({
            "propriedade_id": p["id"], "tipo": "forecast", "fonte": "open-meteo",
            "coletado_em": dt.datetime.now(dt.timezone.utc), "payload": r.json()})
        n += 1
    log.info("coletar: %s documentos gravados no MongoDB", n)
    return n


def consolidar():
    db, total = mongo(), 0
    with pg() as c:
        for p in propriedades():
            doc = db.raw_weather.find_one({"propriedade_id": p["id"], "tipo": "forecast"},
                                          sort=[("coletado_em", -1)])
            if not doc:
                continue
            for row in _linhas(doc["payload"]):
                c.execute("""INSERT INTO weather_daily (propriedade_id,data,tmax,tmin,precip,et0,vento_max)
                             VALUES (%s,%s,%s,%s,%s,%s,%s)
                             ON CONFLICT (propriedade_id,data) DO UPDATE SET
                               tmax=EXCLUDED.tmax, tmin=EXCLUDED.tmin, precip=EXCLUDED.precip,
                               et0=EXCLUDED.et0, vento_max=EXCLUDED.vento_max""", (p["id"], *row))
                total += 1
    log.info("consolidar: %s linhas no PostgreSQL", total)
    return total


def historico():
    with pg() as c:
        rows = c.execute("""SELECT propriedade_id,data,tmax,tmin,precip,et0,vento_max
                            FROM weather_daily""").fetchall()
    con = duck()
    con.executemany("INSERT OR REPLACE INTO clima_historico VALUES (?,?,?,?,?,?,?)",
                    [tuple(r.values()) for r in rows])
    con.close()
    return len(rows)


def backfill(anos=5):
    fim = dt.date.today() - dt.timedelta(days=7)
    ini = fim.replace(year=fim.year - anos)
    con, total = duck(), 0
    for p in propriedades():
        r = requests.get(ARCHIVE_URL, timeout=90, params={
            "latitude": p["lat"], "longitude": p["lon"], "daily": DAILY,
            "start_date": ini.isoformat(), "end_date": fim.isoformat(), "timezone": "America/Sao_Paulo"})
        r.raise_for_status()
        con.executemany("INSERT OR REPLACE INTO clima_historico VALUES (?,?,?,?,?,?,?)",
                        [(p["id"], *row) for row in _linhas(r.json())])
        total += len(r.json()["daily"]["time"])
    con.close()
    log.info("backfill: %s dias históricos no DuckDB", total)
    return total


def _culturas(con):
    cur = con.execute("SELECT * FROM read_csv_auto(?, header=true)", [CULTURAS_CSV])
    cols = [d[0] for d in cur.description]
    return {r[0]: dict(zip(cols, r)) for r in cur.fetchall()}


def avaliar():
    con, hoje, n = duck(), dt.date.today(), 0
    culturas = _culturas(con)
    with pg() as c:
        for p in propriedades():
            dias = c.execute("SELECT * FROM weather_daily WHERE propriedade_id=%s AND data>=%s ORDER BY data",
                             (p["id"], hoje)).fetchall()
            if not dias or p["cultura"] not in culturas:
                continue
            media = con.execute("""SELECT avg((tmax+tmin)/2) FROM clima_historico
                                   WHERE propriedade_id=? AND month(data)=? AND data < ?""",
                                [p["id"], hoje.month, hoje - dt.timedelta(days=7)]).fetchone()[0]
            res = risk.avaliar(dias, culturas[p["cultura"]], media)
            c.execute("DELETE FROM alertas WHERE propriedade_id=%s", (p["id"],))
            for a in res["alertas"]:
                c.execute("""INSERT INTO alertas (propriedade_id,tipo,severidade,data_ref,mensagem,acao)
                             VALUES (%s,%s,%s,%s,%s,%s)""",
                          (p["id"], a["tipo"], a["severidade"], a["data_ref"], a["mensagem"], a["acao"]))
            c.execute("""INSERT INTO risco_propriedade (propriedade_id,score,nivel,atualizado_em,resumo)
                         VALUES (%s,%s,%s,now(),%s)
                         ON CONFLICT (propriedade_id) DO UPDATE SET score=EXCLUDED.score,
                           nivel=EXCLUDED.nivel, atualizado_em=now(), resumo=EXCLUDED.resumo""",
                      (p["id"], res["score"], res["nivel"], Jsonb(res["resumo"])))
            n += 1
    con.close()
    log.info("avaliar: %s propriedades avaliadas", n)
    return n


def tudo(pular_consolidar=False):
    r = {"coletar": coletar()}
    if not pular_consolidar:
        r["consolidar"] = consolidar()
    r["historico"] = historico()
    r["avaliar"] = avaliar()
    return r


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    etapa = sys.argv[1] if len(sys.argv) > 1 else "tudo"
    print({"coletar": coletar, "consolidar": consolidar, "historico": historico,
           "avaliar": avaliar, "backfill": backfill, "tudo": tudo}[etapa]())
