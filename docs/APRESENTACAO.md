# Roteiro da apresentação — 5 minutos

**Título:** AgroAlerta — do dado climático à decisão na lavoura

| # | Slide | Tempo | O que falar |
|---|---|---|---|
| 1 | Capa + problema | 0:40 | Produtores da região (café, cana, milho, citros) decidem irrigação e pulverização com previsão genérica de cidade. Uma geada de 2 °C ou 70 mm em um dia causam perda grande, e o limite crítico depende da cultura. |
| 2 | Solução | 0:30 | Cruzamos previsão por coordenada da propriedade × limites da cultura × histórico local, e entregamos alertas com ação recomendada para os próximos 7 dias. |
| 3 | Arquitetura (diagrama do README) | 1:00 | Open-Meteo → MongoDB (bruto) → Apache Hop → PostgreSQL (consolidado) → DuckDB (histórico) → FastAPI → React. Cada banco tem um papel diferente, não é só para cumprir requisito. |
| 4 | Integrações | 0:50 | 3 fontes: API externa (clima), cadastro de propriedades (PostgreSQL), parâmetros agronômicos (CSV lido pelo DuckDB). Mostrar a consulta de anomalia: previsão vs. média histórica do mês. |
| 5 | Demonstração ao vivo | 1:30 | Ver roteiro abaixo. |
| 6 | Próximos passos e fechamento | 0:30 | Alertas por WhatsApp, mais culturas, dados de solo, calibração com agrônomo. Valor: menos perda e aplicações no momento certo. |

## Roteiro da demonstração (1:30)
1. Abrir o painel: propriedades ordenadas do maior para o menor risco.
2. Clicar em uma propriedade: mostrar a faixa de 14 dias (cor = tipo de alerta, base = chuva) e a lista “O que fazer”.
3. Clicar em **Atualizar dados**: mostrar o contador de “fontes” mudando (MongoDB ganha novas respostas brutas).
4. Mostrar a climatologia (DuckDB) e a métrica “vs. média histórica do mês”.
5. (Opcional) Abrir o Hop GUI com o pipeline `pl_mongo_para_postgres` e o workflow rodando.

## Perguntas prováveis da banca
- **Por que 3 bancos?** Mongo guarda o JSON bruto (reprocessável), Postgres guarda dados mestres e o resultado consolidado, DuckDB faz análise histórica sem sobrecarregar o transacional.
- **Onde está a integração?** Pipeline `coletar → consolidar → historico → avaliar`, juntando API + cadastro + CSV agronômico + histórico.
- **Os limites são confiáveis?** São ilustrativos e ficam em CSV editável; em produção seriam calibrados com agrônomo.
- **Se a API cair?** O dado bruto anterior permanece no Mongo e o painel continua mostrando o último resultado.
