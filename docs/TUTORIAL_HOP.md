# Tutorial — Integração com Apache Hop

Esta é a parte que não dá para entregar como código pronto: pipelines do Hop são desenhados na interface gráfica
(`hop-gui`) e salvos como `.hpl`/`.hwf`. Siga o passo a passo; leva cerca de 30 minutos.

**O que o Hop faz no sistema:** lê os JSONs brutos do **MongoDB**, achata a estrutura (um documento por propriedade → uma linha
por dia) e grava/atualiza a tabela `weather_daily` no **PostgreSQL**. Um workflow orquestra as etapas Python antes e depois.

```
wf_agroalerta.hwf
 Start → [Shell] coletar → [Pipeline] pl_mongo_para_postgres → [Shell] historico → [Shell] avaliar
          (Python)          (Apache Hop)                         (Python)           (Python)
```

## 1. Instalação
1. Instale o **Java 17** (`java -version` deve mostrar 17).
2. Baixe o **Apache Hop 2.x** em https://hop.apache.org/download/ e descompacte.
3. Abra a interface: `hop-gui.sh` (Linux/Mac) ou `hop-gui.bat` (Windows).
4. Suba os bancos: `docker compose up -d postgres mongo` e rode `python -m app.etl coletar` ao menos uma vez
   (para existir dado na coleção `raw_weather`).

## 2. Projeto e conexão com o PostgreSQL
1. No Hop GUI: **File → New project** (ou o ícone de projetos) → nome `agroalerta`, pasta = a pasta `hop/` do repositório.
2. **File → New → Relational Database Connection** (ou aba *Metadata*):
   - Name: `pg_agroalerta` · Type: PostgreSQL · Host: `localhost` · Port: `5432`
   - Database: `agroalerta` · User: `agro` · Password: `agro`
   - Clique em **Test**; deve aparecer “connection successful”. Salve.

## 3. Pipeline `pl_mongo_para_postgres`
Crie com **File → New → Pipeline** e salve como `pl_mongo_para_postgres.hpl` dentro de `hop/`.
Adicione e ligue (hops) os três transforms nesta ordem:

### 3.1 `MongoDB Input`
- Aba **Input options**: Host `localhost`, Port `27017`, Database `agroalerta`, Collection `raw_weather`.
- Aba **Query**: marque **Query is aggregation pipeline** e cole o pipeline abaixo.
  Ele pega o documento mais recente de cada propriedade e transforma os arrays paralelos da API em uma linha por dia:

```json
[
  {"$match": {"tipo": "forecast"}},
  {"$sort": {"coletado_em": -1}},
  {"$group": {"_id": "$propriedade_id", "doc": {"$first": "$$ROOT"}}},
  {"$project": {"propriedade_id": "$_id", "dias": {"$zip": {"inputs": [
    "$doc.payload.daily.time",
    "$doc.payload.daily.temperature_2m_max",
    "$doc.payload.daily.temperature_2m_min",
    "$doc.payload.daily.precipitation_sum",
    "$doc.payload.daily.et0_fao_evapotranspiration",
    "$doc.payload.daily.wind_speed_10m_max"]}}}},
  {"$unwind": "$dias"},
  {"$project": {"_id": 0, "propriedade_id": 1,
    "data": {"$arrayElemAt": ["$dias", 0]},
    "tmax": {"$arrayElemAt": ["$dias", 1]},
    "tmin": {"$arrayElemAt": ["$dias", 2]},
    "precip": {"$arrayElemAt": ["$dias", 3]},
    "et0": {"$arrayElemAt": ["$dias", 4]},
    "vento_max": {"$arrayElemAt": ["$dias", 5]}}}
]
```
> Se o Hop reclamar do JSON, remova os colchetes externos `[` `]` e deixe só os estágios separados por vírgula
> (a forma aceita varia entre versões do plugin).

- Aba **Fields**: desmarque *Output single JSON field* e use **Get fields**, ou crie manualmente:

| Name | Path | Type |
|---|---|---|
| propriedade_id | `$.propriedade_id` | Integer |
| data | `$.data` | String |
| tmax | `$.tmax` | Number |
| tmin | `$.tmin` | Number |
| precip | `$.precip` | Number |
| et0 | `$.et0` | Number |
| vento_max | `$.vento_max` | Number |

Clique em **Preview**: devem aparecer ~14 linhas por propriedade (7 dias passados + 7 futuros).

### 3.2 `Select values` (conversão de tipos)
- Aba **Meta-data**: campo `data` → Type `Date`, Format `yyyy-MM-dd`.

### 3.3 `Insert / Update`
- Connection: `pg_agroalerta` · Target table: `weather_daily`
- **The key(s) to look up the value(s)**: `propriedade_id = propriedade_id` e `data = data`
- **Update fields**: `tmax`, `tmin`, `precip`, `et0`, `vento_max` (todos com *Update* = Y)
- Execute o pipeline (▶, run configuration *local*). Confirme no banco:
  `SELECT count(*) FROM weather_daily;` → ~70 linhas para 5 propriedades.

## 4. Workflow `wf_agroalerta`
**File → New → Workflow**, salve como `hop/wf_agroalerta.hwf`, e ligue as ações nesta ordem:

1. **Start**
2. **Shell** — nome `coletar`
   - Linux/Mac: marque *Insert script* e use:
     ```bash
     cd /CAMINHO/DO/REPO/backend && . .venv/bin/activate && python -m app.etl coletar
     ```
   - Windows (script `.bat`): `cd C:\CAMINHO\repo\backend && .venv\Scripts\python -m app.etl coletar`
3. **Pipeline** — nome `consolidar (Hop)`, arquivo `${PROJECT_HOME}/pl_mongo_para_postgres.hpl`, run configuration *local*
4. **Shell** — nome `historico`, mesmo script trocando `coletar` por `historico`
5. **Shell** — nome `avaliar`, mesmo script trocando por `avaliar`
6. Cada hop deve estar no caminho de sucesso (seta verde). Execute (▶) e verifique no painel de log se todas as ações terminaram verdes.

## 5. Integrar ao sistema (rodar o Hop pelo backend)
1. Descubra o caminho do executável: `<pasta-do-hop>/hop-run.sh` (ou `hop-run.bat`).
2. Antes de iniciar o backend, exporte as variáveis:
   ```bash
   export HOP_RUN=/opt/hop/hop-run.sh
   export HOP_PROJECT=agroalerta
   export HOP_WORKFLOW=wf_agroalerta.hwf
   uvicorn app.main:app --port 8000
   ```
   (No Windows: `set HOP_RUN=C:\hop\hop-run.bat`.)
3. Teste: `curl -X POST http://localhost:8000/api/etl/hop` → `{"ok": true}`.
4. O mesmo workflow pode rodar direto no terminal, sem a interface:
   ```bash
   /opt/hop/hop-run.sh -j agroalerta -f wf_agroalerta.hwf -r local
   ```
5. Para agendar (ex.: todo dia às 6h), use o cron: `0 6 * * * /opt/hop/hop-run.sh -j agroalerta -f wf_agroalerta.hwf -r local`

> Para a demonstração, o botão “Atualizar dados” do painel usa o pipeline em Python (`/api/etl/executar`), que faz
> a mesma consolidação. Mostre o Hop rodando no `hop-gui` e explique que o resultado é idêntico.

## 6. Problemas comuns
| Sintoma | Causa provável | Solução |
|---|---|---|
| Preview do MongoDB vem vazio | coleção `raw_weather` vazia | rodar `python -m app.etl coletar` |
| “Connection refused” no Mongo/Postgres | containers parados | `docker compose up -d postgres mongo` |
| Erro de JSON no Mongo Input | formato do pipeline | remover colchetes externos (passo 3.1) |
| Shell não acha `python` | venv não ativado | usar o caminho completo do python do venv |
| Erro de tipo ao gravar `data` | campo ainda como String | conferir o `Select values` (3.2) |

## 7. Alternativa: KNIME
O requisito aceita Hop **ou** KNIME. Se a equipe preferir KNIME, o fluxo equivalente é: `MongoDB Reader` → `Ungroup`
(para abrir os arrays) → `Column Expressions`/`Table Creator` → `DB Writer` (PostgreSQL). A lógica é a mesma do pipeline acima.
