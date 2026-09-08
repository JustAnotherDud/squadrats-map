// Página de uma região (concelho/distrito PT). Lê data/regioes/<key>.json +
// data/events.json da branch `data`. Sem dependências (nav.js à parte).
(function () {
  'use strict';

  const RAW = 'https://raw.githubusercontent.com/JustAnotherDud/squadrats-map/';
  const LOCAL = ['localhost', '127.0.0.1', ''].includes(location.hostname);
  const U_REG = k => (LOCAL ? '../data/regioes/' : RAW + 'data/data/regioes/') + k + '.json';
  const U_EVENTS = LOCAL ? '../data/events.json' : RAW + 'data/data/events.json';
  const U_CORES = LOCAL ? '../data/membros_cores.json' : RAW + 'main/data/membros_cores.json';
  const NC = { cache: 'no-cache' };

  const alvo = document.getElementById('regiao');
  const KEY = alvo.dataset.key, NIVEL = alvo.dataset.nivel, NOME = alvo.dataset.nome;

  const COR_FB = { 'Zé': '#e03131', 'Xeira': '#9c46d8', 'Carolina': '#c99a00', 'Inês S.': '#e8710a', 'Pedro': '#2f5fd0' };
  let CORES = { ...COR_FB };
  const cor = n => CORES[n] || '#7d8598';
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const nfmt = n => (n || 0).toLocaleString('pt-PT');
  const dot = n => `<span class="dot" style="background:${cor(n)}"></span>`;
  // slugify vem do shared.js (= pipeline/slugs.py), sem mapa nome->slug à mão
  const atl = n => `<a class="atl" href="../atletas/${slugify(n)}.html">${esc(n)}</a>`;

  const ICO = { ultrapassagem: '⇅', novo_lider: '👑', primeira_presenca: '📍', marco: '🚩' };
  function frase(e) {
    const v = e.valores;
    if (e.tipo === 'ultrapassagem')
      return `${dot(e.quem)}${atl(e.quem)} passou ${dot(e.sobre)}${atl(e.sobre)}
        <span class="num">· ${nfmt(v[0])} vs ${nfmt(v[1])}</span>`;
    if (e.tipo === 'novo_lider')
      return `${dot(e.quem)}${atl(e.quem)} assumiu a liderança, passou ${dot(e.sobre)}${atl(e.sobre)}
        <span class="num">· ${nfmt(v[0])} vs ${nfmt(v[1])}</span>`;
    if (e.tipo === 'primeira_presenca')
      return `${dot(e.quem)}${atl(e.quem)} estreou-se aqui
        <span class="num">· ${nfmt(v[0])} squadratinho${v[0] === 1 ? '' : 's'}</span>`;
    return `${dot(e.quem)}${atl(e.quem)} passou os <b>${nfmt(v[0])}</b> squadratinhos
      <span class="num">· agora ${nfmt(v[1])}</span>`;
  }

  // vizinho "disputado" = com evento de troca (ultrapassagem / novo líder),
  // mesma definição da fila "Regiões disputadas" do historico.html. Uma
  // estreia (📍) mexe na ordem mas não é passar ninguém, não conta.
  function temEventoTroca(eventos, d) {
    return eventos.some(e =>
      (e.tipo === 'ultrapassagem' || e.tipo === 'novo_lider') &&
      e.nivel === d.nivel && e.regiao === d.regiao);
  }

  function pintar(d, eventos) {
    const q = fmtDataHora(d.gerado);
    const sub = d.nivel === 'concelho'
      ? `concelho${d.distrito_pai ? ` · distrito de <a href="${d.distrito_pai_key}.html">${esc(d.distrito_pai)}</a>` : ''}`
      : 'distrito';

    const temExc = d.ranking.some(r => r.exclusivos != null);
    const rankRows = d.ranking.map((r, i) => `
      <tr>
        <td class="pos${i === 0 ? ' p1' : ''}">${i + 1}º</td>
        <td><span class="nome">${dot(r.nome)}${atl(r.nome)}</span></td>
        <td class="num">${nfmt(r.captured)}</td>
        ${temExc ? `<td class="uni">${r.exclusivos ? nfmt(r.exclusivos) : '·'}</td>` : ''}
        <td class="pct">${r.pct != null ? r.pct.toFixed(1) + '%' : ''}</td>
      </tr>`).join('');
    const rankHead = `<thead><tr>
      <th></th><th class="h-nome">atleta</th>
      <th title="squadratinhos do atleta na região, partilhados incluídos">total</th>
      ${temExc ? '<th title="squadratinhos que mais nenhum membro do clube tem aqui">únicos</th>' : ''}
      <th>%</th></tr></thead>`;

    const evReg = eventos.filter(e => e.nivel === d.nivel && e.regiao === d.regiao)
      .sort((a, b) => b.data.localeCompare(a.data));
    const evHtml = evReg.length ? evReg.map(e => `
      <div class="reg-ev">
        <span class="tag ${e.nivel}">${e.nivel}</span>
        <span class="ico">${ICO[e.tipo] || ''}</span>
        <span class="corpo">${frase(e)}</span>
      </div>`).join('') : '<p class="reg-vazio">Sem eventos registados nesta região.</p>';

    // vizinho com página e com troca de posição registada -> chip a dourado
    // (não um 5.º emoji ao lado de 👑 ⇅ 📍 🚩, cor + nota, para não confundir)
    const vizDisp = v => v.tem_pagina && temEventoTroca(eventos, { nivel: d.nivel, regiao: v.nome });
    const viz = d.vizinhos.length ? d.vizinhos.map(v => {
      if (!v.tem_pagina) return `<span>${esc(v.nome)}</span>`;
      const dp = vizDisp(v);
      return `<a class="${dp ? 'viz-disp' : ''}" href="${v.key}.html"${dp ? ' title="troca de posição no ranking desde 26 jul"' : ''}>${esc(v.nome)}</a>`;
    }).join('') : '<p class="reg-vazio">·</p>';
    const algumVizDisp = d.vizinhos.some(vizDisp);

    const uni = d.uniao && d.uniao.z17 != null ? d.uniao : null;

    alvo.innerHTML = `
      <div class="reg-cab">
        <h1>${esc(d.regiao)}</h1>
        <p class="sub">${sub}</p>
      </div>
      <p class="reg-meta">Actualizado ${esc(q)} · eventos desde 26 jul 2026</p>

      <section class="reg-sec"><h2>Ranking</h2>
        <table class="reg-rank">${rankHead}<tbody>${rankRows}</tbody></table>
        <p class="reg-totais" style="margin-top:8px">Região com
          <b>${nfmt(d.totais.z17)}</b> squadratinhos.${uni ? ` O clube cobre
          <b>${nfmt(uni.z17)}</b>${uni.pct != null ? ` (${uni.pct.toFixed(1)}%)` : ''}.` : ''}</p>
      </section>

      <section class="reg-sec"><h2>Eventos nesta região</h2>${evHtml}</section>

      <section class="reg-sec"><h2>Faz fronteira com</h2>
        <div class="reg-viz">${viz}</div>
        ${algumVizDisp ? '<p class="reg-viz-nota">A dourado: vizinhos com troca de posição no ranking desde 26 jul.</p>' : ''}
      </section>

      <p class="reg-rodape"><a href="index.html">← todas as regiões</a> ·
        ranking e % são de <b>squadratinhos</b> (zoom 17, ~201 m); <b>únicos</b> =
        sem mais nenhum membro do clube. Dados actualizados 6×/dia pelo mesmo
        processo que gera o <a href="../club.html">mapa do clube</a>. O
        <a href="../historico.html">histórico</a> tem o feed completo do clube.</p>`;
  }

  async function carregar() {
    try {
      const rc = await fetch(U_CORES, NC);
      if (rc.ok) { const j = await rc.json(); CORES = { ...COR_FB, ...(j.cores || {}) }; }
    } catch (e) { /* fallback */ }
    let d, eventos = [];
    try {
      const [rr, re] = await Promise.all([fetch(U_REG(KEY), NC), fetch(U_EVENTS, NC)]);
      if (!rr.ok) throw new Error(rr.status);
      d = await rr.json();
      if (re.ok) eventos = (await re.json()).eventos || [];
    } catch (e) {
      alvo.innerHTML = `<p class="reg-estado reg-erro">Não consegui carregar
        ${esc(NOME || KEY)} (${esc(e.message)}).</p>`;
      return;
    }
    document.title = `${d.regiao} · Squadrats Club`;
    pintar(d, eventos);
  }
  carregar();
})();
