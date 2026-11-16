async function req(path, opts) {
  const r = await fetch(`/api${path}`, opts);
  if (!r.ok) {
    let detalhe = "";
    try { detalhe = (await r.json()).detail; } catch { /* sem corpo JSON */ }
    throw new Error(detalhe || `Erro ${r.status}`);
  }
  return r.json();
}

export const api = {
  resumo: () => req("/resumo"),
  clima: (id) => req(`/propriedades/${id}/clima`),
  alertas: (id) => req(`/propriedades/${id}/alertas`),
  climatologia: (id) => req(`/propriedades/${id}/climatologia`),
  fontes: () => req("/fontes"),
  executarEtl: (pularConsolidar = false) =>
    req(`/etl/executar?pular_consolidar=${pularConsolidar}`, { method: "POST" }),
};
