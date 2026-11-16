import { useCallback, useEffect, useMemo, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api";

const COR_TIPO = { geada: "#3B6FD1", calor: "#D1782A", deficit_hidrico: "#B58A1E", excesso_chuva: "#2A8C8C" };
const NOME_TIPO = {
  geada: "Geada", calor: "Calor extremo", deficit_hidrico: "Déficit hídrico",
  excesso_chuva: "Excesso de chuva", janela_pulverizacao: "Janela de pulverização",
};
const NOME_CULTURA = {
  cafe_arabica: "Café arábica", milho: "Milho", soja: "Soja", cana_de_acucar: "Cana-de-açúcar", citros: "Citros",
};
const NOME_MES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const NIVEL = { baixo: "Risco baixo", moderado: "Risco moderado", alto: "Risco alto", critico: "Risco crítico" };

const fmtDia = (iso) => {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
};
const hojeISO = () => new Date().toLocaleDateString("sv-SE"); // AAAA-MM-DD no fuso local

/* Faixa de 14 dias: cada coluna mostra a amplitude de temperatura (barra), a chuva (base)
   e a cor do pior alerta daquele dia. É o elemento central da tela. */
function Faixa({ clima, alertas }) {
  const hoje = hojeISO();
  const dias = clima.slice(-14);
  const temps = dias.flatMap((d) => [d.tmax, d.tmin]).filter((t) => t != null);
  if (!temps.length) return null;
  const topo = Math.ceil(Math.max(...temps)) + 1;
  const base = Math.floor(Math.min(...temps)) - 1;
  const H = 170;
  const y = (t) => ((topo - t) / (topo - base)) * H;

  const porDia = {};
  alertas.filter((a) => a.severidade !== "info").forEach((a) => {
    const k = a.data_ref?.slice(0, 10);
    if (!k || a.tipo === "deficit_hidrico") return;
    if (!porDia[k] || a.severidade === "alta") porDia[k] = a;
  });

  return (
    <div className="faixa" role="img" aria-label="Temperatura mínima, máxima e chuva dos últimos 7 e próximos 7 dias">
      {dias.map((d) => {
        const al = porDia[d.data];
        const passado = d.data < hoje;
        const cor = al ? COR_TIPO[al.tipo] : "var(--campo)";
        const chuva = Math.min(d.precip || 0, 40);
        return (
          <div key={d.data} className={`dia ${passado ? "passado" : ""} ${d.data === hoje ? "hoje" : ""}`}>
            <div className="coluna" style={{ height: H }} title={`${fmtDia(d.data)}: ${d.tmin}°–${d.tmax}°C, ${d.precip ?? 0} mm`}>
              <div className="chuva" style={{ height: (chuva / 40) * 60 }} />
              {d.tmax != null && d.tmin != null && (
                <div className="amplitude" style={{ top: y(d.tmax), height: Math.max(6, y(d.tmin) - y(d.tmax)), background: cor }}>
                  <span className="tmax">{Math.round(d.tmax)}°</span>
                  <span className="tmin">{Math.round(d.tmin)}°</span>
                </div>
              )}
            </div>
            <div className="rotulo">{d.data === hoje ? "hoje" : fmtDia(d.data)}</div>
          </div>
        );
      })}
    </div>
  );
}

function Alertas({ alertas }) {
  if (!alertas.length) return <p className="vazio">Nenhum alerta para os próximos 7 dias.</p>;
  return (
    <ul className="alertas">
      {alertas.map((a) => (
        <li key={a.id} className={`alerta ${a.severidade}`}>
          <div className="alerta-topo">
            <strong>{NOME_TIPO[a.tipo] || a.tipo}</strong>
            <span>{a.data_ref ? fmtDia(a.data_ref.slice(0, 10)) : ""}</span>
          </div>
          <p>{a.mensagem}</p>
          <p className="acao">{a.acao}</p>
        </li>
      ))}
    </ul>
  );
}

function Climatologia({ dados }) {
  if (!dados.length) return <p className="vazio">Histórico ainda não carregado. Rode o backfill (veja o README).</p>;
  const serie = dados.map((d) => ({ ...d, mes: NOME_MES[d.mes - 1] }));
  return (
    <ResponsiveContainer width="100%" height={220}>
      <ComposedChart data={serie} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid stroke="#d6dcd2" vertical={false} />
        <XAxis dataKey="mes" tickLine={false} />
        <YAxis yAxisId="c" unit=" mm" tickLine={false} axisLine={false} />
        <YAxis yAxisId="t" orientation="right" unit="°" tickLine={false} axisLine={false} />
        <Tooltip />
        <Bar yAxisId="c" dataKey="chuva_mm" name="Chuva média (mm)" fill="#2A8C8C" opacity={0.55} />
        <Line yAxisId="t" dataKey="tmed" name="Temperatura média (°C)" stroke="#D1782A" strokeWidth={2} dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function Fontes({ fontes }) {
  if (!fontes) return null;
  return (
    <div className="fontes">
      <div><h4>MongoDB</h4><p>{fontes.mongodb.raw_weather} respostas brutas da API</p></div>
      <div><h4>PostgreSQL</h4><p>{fontes.postgres.weather_daily} dias de clima · {fontes.postgres.alertas} alertas</p></div>
      <div><h4>DuckDB</h4><p>{fontes.duckdb.clima_historico} dias de histórico</p></div>
    </div>
  );
}

export default function App() {
  const [lista, setLista] = useState([]);
  const [selId, setSelId] = useState(null);
  const [clima, setClima] = useState([]);
  const [alertas, setAlertas] = useState([]);
  const [climatologia, setClimatologia] = useState([]);
  const [fontes, setFontes] = useState(null);
  const [erro, setErro] = useState("");
  const [rodando, setRodando] = useState(false);

  const carregarLista = useCallback(async () => {
    try {
      const r = await api.resumo();
      setLista(r);
      setSelId((atual) => atual ?? r[0]?.id ?? null);
      setErro("");
      api.fontes().then(setFontes).catch(() => setFontes(null));
    } catch (e) {
      setErro("Não foi possível falar com o servidor. Confirme que o backend está rodando na porta 8000.");
    }
  }, []);

  useEffect(() => { carregarLista(); }, [carregarLista]);

  useEffect(() => {
    if (!selId) return;
    Promise.all([api.clima(selId), api.alertas(selId), api.climatologia(selId)])
      .then(([c, a, k]) => { setClima(c); setAlertas(a); setClimatologia(k); })
      .catch(() => setErro("Falha ao carregar os dados da propriedade."));
  }, [selId, lista]);

  const atualizar = async () => {
    setRodando(true);
    setErro("");
    try {
      await api.executarEtl();
      await carregarLista();
    } catch (e) {
      setErro(`A atualização falhou: ${e.message}`);
    } finally {
      setRodando(false);
    }
  };

  const sel = useMemo(() => lista.find((p) => p.id === selId), [lista, selId]);
  const r = sel?.resumo;

  return (
    <div className="app">
      <aside className="lateral">
        <h1>AgroAlerta</h1>
        <p className="sub">Clima e risco por propriedade, nos próximos 7 dias</p>
        <ul className="props">
          {lista.map((p) => (
            <li key={p.id}>
              <button className={p.id === selId ? "ativa" : ""} onClick={() => setSelId(p.id)}>
                <span className={`score ${p.nivel || "nenhum"}`}>{p.score ?? "–"}</span>
                <span className="info">
                  <strong>{p.nome}</strong>
                  <small>{p.municipio} · {NOME_CULTURA[p.cultura] || p.cultura}</small>
                </span>
              </button>
            </li>
          ))}
        </ul>
        <button className="atualizar" onClick={atualizar} disabled={rodando}>
          {rodando ? "Atualizando dados…" : "Atualizar dados"}
        </button>
        <Fontes fontes={fontes} />
      </aside>

      <main className="principal">
        {erro && <div className="erro" role="alert">{erro}</div>}
        {!sel && !erro && <p className="vazio">Carregando propriedades…</p>}
        {sel && (
          <>
            <header className="cab">
              <div>
                <h2>{sel.nome}</h2>
                <p>{sel.municipio}/{sel.uf} · {NOME_CULTURA[sel.cultura] || sel.cultura} · {sel.area_ha} ha · {sel.produtor}</p>
              </div>
              {sel.nivel && <span className={`selo ${sel.nivel}`}>{NIVEL[sel.nivel]} ({sel.score}/100)</span>}
            </header>

            {sel.score == null ? (
              <p className="vazio">Esta propriedade ainda não foi avaliada. Clique em “Atualizar dados”.</p>
            ) : (
              <>
                <section>
                  <h3>7 dias para trás e 7 para frente</h3>
                  <Faixa clima={clima} alertas={alertas} />
                  <div className="legenda">
                    {Object.entries(COR_TIPO).filter(([k]) => k !== "deficit_hidrico").map(([k, c]) => (
                      <span key={k}><i style={{ background: c }} />{NOME_TIPO[k]}</span>
                    ))}
                    <span><i style={{ background: "var(--campo)" }} />Sem alerta</span>
                    <span><i className="gota" />Chuva</span>
                  </div>
                </section>

                {r && (
                  <section className="metricas">
                    <div><b>{r.chuva_7d} mm</b><span>chuva prevista (7 dias)</span></div>
                    <div><b>{r.balanco_hidrico > 0 ? "+" : ""}{r.balanco_hidrico} mm</b><span>balanço hídrico (chuva − demanda)</span></div>
                    <div><b>{r.tmin_prevista}° / {r.tmax_prevista}°</b><span>mínima e máxima previstas</span></div>
                    <div>
                      <b>{r.anomalia_temperatura == null ? "–" : `${r.anomalia_temperatura > 0 ? "+" : ""}${r.anomalia_temperatura}°C`}</b>
                      <span>vs. média histórica do mês</span>
                    </div>
                  </section>
                )}

                <section>
                  <h3>O que fazer</h3>
                  <Alertas alertas={alertas} />
                </section>
              </>
            )}

            <section>
              <h3>Clima típico da região (histórico de 5 anos)</h3>
              <Climatologia dados={climatologia} />
            </section>
          </>
        )}
      </main>
    </div>
  );
}
