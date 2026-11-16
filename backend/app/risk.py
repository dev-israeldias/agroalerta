"""Motor de regras agroclimáticas. Limiares vêm de data/culturas.csv
(valores ilustrativos: calibrar com um agrônomo / Embrapa / IAC)."""

VENTO_MAX_PULVERIZACAO = 15.0   # km/h
CHUVA_MAX_PULVERIZACAO = 1.0    # mm


def _nivel(score):
    return "baixo" if score >= 80 else "moderado" if score >= 60 else "alto" if score >= 35 else "critico"


def avaliar(dias, p, clima_media_mes=None):
    """dias: lista de dicts (data, tmax, tmin, precip, et0, vento_max) – dias futuros.
    p: parâmetros da cultura. clima_media_mes: temperatura média histórica do mês (DuckDB)."""
    alertas = []

    def add(tipo, sev, data, msg, acao):
        alertas.append(dict(tipo=tipo, severidade=sev, data_ref=data, mensagem=msg, acao=acao))

    janelas = []
    for d in dias:
        tmin, tmax, chuva, vento = d["tmin"], d["tmax"], d["precip"], d["vento_max"]
        if tmin is not None and tmin <= p["tmin_critica"] + 2:
            sev = "alta" if tmin <= p["tmin_critica"] else "media"
            add("geada", sev, d["data"], f"Mínima prevista de {tmin:.1f}°C (limite da cultura: {p['tmin_critica']}°C).",
                "Preparar irrigação/aceiros e proteger mudas e áreas baixas na véspera.")
        if tmax is not None and tmax >= p["tmax_critica"] - 1:
            sev = "alta" if tmax >= p["tmax_critica"] + 2 else "media"
            add("calor", sev, d["data"], f"Máxima prevista de {tmax:.1f}°C (limite: {p['tmax_critica']}°C).",
                "Evitar operações no horário mais quente; reforçar irrigação.")
        if chuva is not None and chuva >= p["chuva_max_dia"]:
            add("excesso_chuva", "alta" if chuva >= p["chuva_max_dia"] * 1.5 else "media", d["data"],
                f"Chuva prevista de {chuva:.0f} mm em um dia.",
                "Checar drenagem e adiar colheita/aplicações; atenção a erosão.")
        if chuva is not None and vento is not None and chuva <= CHUVA_MAX_PULVERIZACAO and vento <= VENTO_MAX_PULVERIZACAO:
            janelas.append(d["data"])

    precip = sum(d["precip"] or 0 for d in dias)
    et_c = sum((d["et0"] or 0) * p["kc"] for d in dias)
    balanco = precip - et_c
    if dias and balanco <= p["balanco_alerta"]:
        sev = "alta" if balanco <= 2 * p["balanco_alerta"] else "media"
        add("deficit_hidrico", sev, dias[0]["data"],
            f"Balanço hídrico de {len(dias)} dias: {balanco:.0f} mm (chuva {precip:.0f} mm − demanda {et_c:.0f} mm).",
            "Planejar irrigação suplementar nos próximos dias.")

    if janelas:
        add("janela_pulverizacao", "info", janelas[0],
            f"{len(janelas)} dia(s) com boa janela de pulverização (sem chuva, vento ≤ {VENTO_MAX_PULVERIZACAO:.0f} km/h).",
            "Concentrar aplicações nesses dias.")

    # penaliza o pior alerta de cada tipo (evita zerar o score só por vários dias seguidos de calor)
    pesos = {"alta": 30, "media": 15, "info": 0}
    pior = {}
    for a in alertas:
        pior[a["tipo"]] = max(pior.get(a["tipo"], 0), pesos[a["severidade"]])
    score = max(0, 100 - sum(pior.values()))

    tmed = [(d["tmax"] + d["tmin"]) / 2 for d in dias if d["tmax"] is not None and d["tmin"] is not None]
    anomalia = None
    if tmed and clima_media_mes is not None:
        anomalia = round(sum(tmed) / len(tmed) - clima_media_mes, 1)

    resumo = dict(
        chuva_7d=round(precip, 1), balanco_hidrico=round(balanco, 1),
        tmin_prevista=min((d["tmin"] for d in dias if d["tmin"] is not None), default=None),
        tmax_prevista=max((d["tmax"] for d in dias if d["tmax"] is not None), default=None),
        dias_janela_pulverizacao=len(janelas), anomalia_temperatura=anomalia,
    )
    return dict(score=score, nivel=_nivel(score), alertas=alertas, resumo=resumo)
