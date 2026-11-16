# AgroAlerta — inteligência climática para o produtor rural

Plataforma que **integra dados climáticos de uma API pública com o cadastro das propriedades e com parâmetros
agronômicos de cada cultura**, e transforma tudo em **alertas acionáveis** (geada, calor, déficit hídrico, excesso de
chuva) e **janelas de pulverização** para os próximos 7 dias.

## Problema
Pequenos e médios produtores da região (café, cana, milho, citros) decidem irrigação, pulverização e colheita olhando
previsão genérica de cidade. Uma geada de 2 °C ou 70 mm em um dia causam perdas grandes, mas o limite que importa
**depende da cultura**. O AgroAlerta cruza previsão por coordenada da propriedade × limites da cultura × histórico local.

## Arquitetura

```
 Open-Meteo (API REST)                      data/culturas.csv
 previsão + histórico                       limites agronômicos
        │                                          │
        ▼  coletar (Python)                        │
 ┌───────────────┐  consolidar (Apache Hop ou Python)
 │   MongoDB     │ ───────────────────────────┐    │
 │ raw_weather   │   JSON bruto               ▼    │
 └───────────────┘                    ┌────────────────┐
                                      │  PostgreSQL    │  propriedades, weather_daily,
                                      │ (dados mestres │  alertas, risco_propriedade
                                      │  + consolidado)│
                                      └───────┬────────┘
                                   histórico  │   ▲ avaliar (regras de risco)
                                              ▼   │
                                      ┌────────────────┐
                                      │    DuckDB      │◄── lê o CSV de culturas (read_csv_auto)
                                      │ clima_historico│    climatologia / anomalias
                                      └────────────────┘
                                              │
                         FastAPI (Python) ◄───┘───► React (Vite + Recharts)
```

| Camada | Tecnologia | Papel |
|---|---|---|
| Dados brutos | **MongoDB** | guarda a resposta JSON original da API (auditoria e reprocessamento) |
| Dados mestres e consolidados | **PostgreSQL** | propriedades, clima diário, alertas, score |
| Analítico | **DuckDB** | histórico de 5 anos, climatologia, leitura do CSV de culturas |
| Integração | **Apache Hop** | pipeline Mongo → Postgres + workflow que orquestra tudo (`docs/TUTORIAL_HOP.md`) |
| API externa | **Open-Meteo** | previsão (7 dias) e arquivo histórico; sem chave de API |
| Backend | **Python / FastAPI** | ETL, motor de regras, endpoints |
| Frontend | **React / Vite / Recharts** | painel por propriedade |

## Checklist dos requisitos
- [x] 3 tecnologias de armazenamento: MongoDB, PostgreSQL, DuckDB
- [x] Ferramenta de integração: Apache Hop (tutorial em `docs/TUTORIAL_HOP.md`; o Python faz a mesma etapa como alternativa)
- [x] API externa: Open-Meteo
- [x] Backend Python, frontend React
- [x] Integração/consolidação: `backend/app/etl.py`
- [x] Interface de visualização: `frontend/`
- [ ] Demonstração e apresentação: roteiro em `docs/APRESENTACAO.md`

## Como executar

Pré-requisitos: Docker, Python 3.11+, Node 18+.

```bash
# 1) Bancos (PostgreSQL já sobe com as tabelas e 5 propriedades de exemplo)
docker compose up -d postgres mongo

# 2) Backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.etl backfill      # carrega 5 anos de histórico no DuckDB (uma vez; leva ~1 min)
python -m app.etl tudo          # coleta -> consolida -> histórico -> avalia
uvicorn app.main:app --reload --port 8000

# 3) Frontend (outro terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

No painel, o botão **Atualizar dados** reexecuta o pipeline. A área “fontes” mostra o que cada banco guarda.

## Endpoints
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/resumo` | propriedades com score e nível de risco |
| GET | `/api/propriedades/{id}/clima` | 7 dias passados + 7 futuros |
| GET | `/api/propriedades/{id}/alertas` | alertas e ações recomendadas |
| GET | `/api/propriedades/{id}/climatologia` | média mensal histórica (DuckDB) |
| GET | `/api/fontes` | contagem de registros por banco |
| POST | `/api/propriedades` | cadastra nova propriedade |
| POST | `/api/etl/executar` | roda o pipeline em Python |
| POST | `/api/etl/hop` | roda o workflow do Apache Hop |

Documentação interativa: http://localhost:8000/docs

## Regras de risco (resumo)
Para cada propriedade, os limites vêm de `data/culturas.csv`:
- **Geada**: mínima ≤ limite da cultura (alta) ou até 2 °C acima (média)
- **Calor**: máxima ≥ limite − 1 °C (média) ou ≥ limite + 2 °C (alta)
- **Déficit hídrico**: chuva − (ET₀ × Kc) em 7 dias abaixo do limite da cultura
- **Excesso de chuva**: chuva diária ≥ limite da cultura
- **Janela de pulverização**: sem chuva (≤ 1 mm) e vento ≤ 15 km/h
- **Score** = 100 − penalidade do pior alerta de cada tipo (alta 30, média 15)

> Os limites do CSV são ilustrativos. Em uso real, devem ser calibrados com um engenheiro agrônomo (Embrapa/IAC).

## Estrutura
```
backend/app/   config.py, db.py, etl.py, risk.py, main.py
frontend/src/  App.jsx, api.js, styles.css
database/      init.sql
data/          culturas.csv
hop/           (pipeline e workflow do Apache Hop, criados seguindo docs/TUTORIAL_HOP.md)
docs/          TUTORIAL_HOP.md, APRESENTACAO.md
```
