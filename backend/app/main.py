from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import etl
from .db import duck, mongo, pg

app = FastAPI(title="AgroAlerta API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])


class NovaPropriedade(BaseModel):
    nome: str
    produtor: str | None = None
    municipio: str
    uf: str = "SP"
    lat: float
    lon: float
    cultura: str
    area_ha: float | None = None


@app.get("/api/resumo")
def resumo():
    with pg() as c:
        return c.execute("""SELECT p.*, r.score, r.nivel, r.resumo, r.atualizado_em,
                                   (SELECT count(*) FROM alertas a WHERE a.propriedade_id=p.id
                                      AND a.severidade <> 'info') AS n_alertas
                            FROM propriedades p LEFT JOIN risco_propriedade r ON r.propriedade_id=p.id
                            ORDER BY r.score NULLS LAST, p.nome""").fetchall()


@app.get("/api/propriedades/{pid}/clima")
def clima(pid: int):
    with pg() as c:
        return c.execute("""SELECT * FROM weather_daily WHERE propriedade_id=%s
                            ORDER BY data""", (pid,)).fetchall()


@app.get("/api/propriedades/{pid}/alertas")
def alertas(pid: int):
    with pg() as c:
        return c.execute("""SELECT * FROM alertas WHERE propriedade_id=%s
                            ORDER BY CASE severidade WHEN 'alta' THEN 0 WHEN 'media' THEN 1 ELSE 2 END, data_ref""",
                         (pid,)).fetchall()


@app.get("/api/propriedades/{pid}/climatologia")
def climatologia(pid: int):
    con = duck()
    try:
        cur = con.execute("""SELECT month(data) AS mes, round(avg((tmax+tmin)/2),1) AS tmed,
                                    round(sum(precip)/count(DISTINCT year(data)),0) AS chuva_mm
                             FROM clima_historico WHERE propriedade_id=? GROUP BY 1 ORDER BY 1""", [pid])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()


@app.post("/api/propriedades", status_code=201)
def criar(p: NovaPropriedade):
    with pg() as c:
        row = c.execute("""INSERT INTO propriedades (nome,produtor,municipio,uf,lat,lon,cultura,area_ha)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (p.nome, p.produtor, p.municipio, p.uf, p.lat, p.lon, p.cultura, p.area_ha)).fetchone()
    return row


@app.post("/api/etl/executar")
def executar(pular_consolidar: bool = False):
    """Roda o pipeline completo. Use pular_consolidar=true quando o Apache Hop faz essa etapa."""
    try:
        return etl.tudo(pular_consolidar)
    except Exception as e:  # erro de API externa, banco fora do ar, etc.
        raise HTTPException(502, f"Falha no pipeline: {e}")


@app.get("/api/fontes")
def fontes():
    """Mostra o que cada armazenamento guarda: evidência da integração entre fontes."""
    out = {}
    with pg() as c:
        out["postgres"] = {
            "propriedades": c.execute("SELECT count(*) n FROM propriedades").fetchone()["n"],
            "weather_daily": c.execute("SELECT count(*) n FROM weather_daily").fetchone()["n"],
            "alertas": c.execute("SELECT count(*) n FROM alertas").fetchone()["n"]}
    m = mongo()
    ultimo = m.raw_weather.find_one(sort=[("coletado_em", -1)], projection={"coletado_em": 1})
    out["mongodb"] = {"raw_weather": m.raw_weather.count_documents({}),
                      "ultima_coleta": ultimo["coletado_em"].isoformat() if ultimo else None}
    con = duck()
    out["duckdb"] = {"clima_historico": con.execute("SELECT count(*) FROM clima_historico").fetchone()[0]}
    con.close()
    return out


@app.post("/api/etl/hop")
def executar_hop():
    """Dispara o workflow do Apache Hop (coleta -> Hop consolida -> histórico -> avaliação).
    Requer a variável HOP_RUN apontando para o executável hop-run (veja docs/TUTORIAL_HOP.md)."""
    import os
    import subprocess

    run = os.getenv("HOP_RUN")
    if not run:
        raise HTTPException(501, "Defina HOP_RUN com o caminho do hop-run para usar o Apache Hop.")
    cmd = [run, "-j", os.getenv("HOP_PROJECT", "agroalerta"),
           "-f", os.getenv("HOP_WORKFLOW", "wf_agroalerta.hwf"), "-r", "local"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        raise HTTPException(502, (r.stdout + r.stderr)[-1200:])
    return {"ok": True}
