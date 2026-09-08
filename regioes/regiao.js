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
  const SLUG = { 'Zé': 'ze', 'Xeira': 'xeira', 'Carolina': 'carolina', 'Inês S.': 'ines-s', 'Pedro': 'pedro' };
  let CORES = { ...COR_FB };
  const cor = n => CORES[n] || '#7d8598';
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const nfmt = n => (n || 0).toLocaleString('pt-PT');
  const dot = n => `<span class="dot" style="background:${cor(n)}"></span>`;
  const atl = n => `<a class="atl" href="../atletas/${SLUG[n] || ''}.html">${esc(n)}</a>`;
  const MES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
  const dLonga = iso => { const [y, m, d] = iso.split('-').map(Number); return `${d} ${MES[m - 1]} ${y}`; };
  const dCurta = iso => { const [, m, d] = iso.split('-').map(Number); return `${d} ${MES[m - 1]}`; };

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

  // --- timeline do ranking ---
  // O eixo Y é a POSIÇÃO (1º no topo), não o valor absoluto. Com valores como
  // 3916 vs 376 vs 327 nenhuma escala (linear ou log) separa a sub-corrida — e a
  // magnitude já está na tabela por cima. Aqui só interessa quem passou quem.
  // Só se desenha onde há um evento de troca (ultrapassagem / novo líder) —
  // mesma definição da fila "Regiões disputadas" do historico.html. Uma estreia
  // (📍) mexe na ordem mas não é passar ninguém, por isso não conta.

  function temEventoTroca(eventos, d) {
    return eventos.some(e =>
      (e.tipo === 'ultrapassagem' || e.tipo === 'novo_lider') &&
      e.nivel === d.nivel && e.regiao === d.regiao);
  }

  // Maior subida em squadratinhos entre o 1.º e o último ponto (regiões que
  // mexeram em valor mas sem trocar ninguém de lugar).
  function maiorGanho(tl) {
    if (!tl || tl.length < 2) return null;
    const ini = Object.fromEntries(tl[0].ranking);
    const fim = Object.fromEntries(tl[tl.length - 1].ranking);
    let best = null;
    for (const n of Object.keys(fim)) {
      const delta = (fim[n] || 0) - (ini[n] || 0);
      if (delta > 0 && (!best || delta > best.delta)) best = { nome: n, delta };
    }
    return best;
  }

  function timelineRankSvg(tl, gerado) {
    const fimIso = (gerado || '').slice(0, 10) || tl[tl.length - 1].data;
    const nomes = [];
    tl.forEach(p => p.ranking.forEach(([n]) => { if (!nomes.includes(n)) nomes.push(n); }));
    const NR = Math.max(nomes.length, 2);

    // série de posições por atleta: [[dataISO, rank], ...]. Ausente nesse dia =
    // uma linha abaixo do último classificado (entrou de fora).
    const serie = {};
    for (const n of nomes) serie[n] = [];
    for (const p of tl) {
      const idx = {};
      p.ranking.forEach(([n], i) => { idx[n] = i + 1; });
      for (const n of nomes) serie[n].push([p.data, idx[n] || Math.min(p.ranking.length + 1, NR)]);
    }

    const datas = [...new Set(tl.map(p => p.data)).add(fimIso)].sort();
    const t0 = Date.parse(datas[0]);
    const t1 = Date.parse(fimIso) || Date.parse(datas[datas.length - 1]);
    const W = 620, H = 120, pl = 18, pr = 74, pt = 12, pb = 16;
    const x = iso => pl + (t1 === t0 ? 0.5 : (Date.parse(iso) - t0) / (t1 - t0)) * (W - pl - pr);
    const y = r => pt + (NR === 1 ? 0.5 : (r - 1) / (NR - 1)) * (H - pt - pb);

    let grid = '';
    for (let r = 1; r <= NR; r++)
      grid += `<line class="grid" x1="${pl}" y1="${y(r).toFixed(1)}" x2="${W - pr}" y2="${y(r).toFixed(1)}"/>`;

    let paths = '', labels = '';
    for (const n of nomes) {
      const pts = serie[n].concat([[fimIso, serie[n][serie[n].length - 1][1]]]);
      let d = '';
      pts.forEach(([iso, r], i) => {
        const px = x(iso).toFixed(1), py = y(r).toFixed(1);
        if (i === 0) d += `M${px} ${py}`;
        else { const prevY = y(pts[i - 1][1]).toFixed(1); d += `L${px} ${prevY}L${px} ${py}`; }
      });
      paths += `<path d="${d}" fill="none" stroke="${cor(n)}" stroke-width="1.8" opacity="0.9"/>`;
      const ly = y(pts[pts.length - 1][1]).toFixed(1);
      labels += `<text class="lbl" x="${W - pr + 5}" y="${ly}" dominant-baseline="middle" fill="${cor(n)}">${esc(n)}</text>`;
    }

    return `<svg class="reg-tl" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      ${grid}${paths}${labels}
      <text x="${pl - 13}" y="${y(1).toFixed(1)}" dominant-baseline="middle">1º</text>
      <text x="${pl - 13}" y="${y(NR).toFixed(1)}" dominant-baseline="middle">${NR}º</text>
      <text x="${pl}" y="${H - 3}">${dCurta(datas[0])}</text>
      <text x="${W - pr}" y="${H - 3}" text-anchor="end">${dCurta(fimIso)}</text>
    </svg>`;
  }

  function pintar(d, eventos) {
    const q = (d.gerado || '').replace('T', ' ').replace('Z', ' UTC');
    const sub = d.nivel === 'concelho'
      ? `concelho${d.distrito_pai ? ` · distrito de <a href="${d.distrito_pai_key}.html">${esc(d.distrito_pai)}</a>` : ''}`
      : 'distrito';

    const rankRows = d.ranking.map((r, i) => `
      <tr>
        <td class="pos${i === 0 ? ' p1' : ''}">${i + 1}º</td>
        <td><span class="nome">${dot(r.nome)}${atl(r.nome)}</span></td>
        <td class="n">${nfmt(r.captured)}${r.pct != null ? `<span class="pct">${r.pct.toFixed(1)}%</span>` : ''}</td>
      </tr>`).join('');

    const evReg = eventos.filter(e => e.nivel === d.nivel && e.regiao === d.regiao)
      .sort((a, b) => b.data.localeCompare(a.data));
    const evHtml = evReg.length ? evReg.map(e => `
      <div class="reg-ev">
        <span class="tag ${e.nivel}">${e.nivel}</span>
        <span class="ico">${ICO[e.tipo] || ''}</span>
        <span class="corpo">${frase(e)}</span>
      </div>`).join('') : '<p class="reg-vazio">Sem eventos registados nesta região.</p>';

    const viz = d.vizinhos.length ? d.vizinhos.map(v => v.tem_pagina
      ? `<a href="${v.key}.html">${esc(v.nome)}</a>`
      : `<span>${esc(v.nome)}</span>`).join('') : '<p class="reg-vazio">—</p>';

    const tlData = (d.timeline && d.timeline.length) ? d.timeline : [];
    let evolSec;
    if (temEventoTroca(eventos, d) && tlData.length >= 2) {
      evolSec = `<section class="reg-sec"><h2>Evolução</h2>
        ${timelineRankSvg(tlData, d.gerado)}
        <p class="reg-tl-nota">Posição no ranking ao longo do tempo — as linhas a cruzar-se são trocas de lugar. Os totais estão na tabela em cima.</p>
      </section>`;
    } else {
      const g = maiorGanho(tlData);
      const linha = g
        ? `${atl(g.nome)} somou <b>${nfmt(g.delta)}</b> squadratinho${g.delta === 1 ? '' : 's'} no período, sem trocar de posição.`
        : 'Sem trocas de posição no ranking desde 15 ago 2026.';
      evolSec = `<section class="reg-sec"><p class="reg-tl-so">${linha}</p></section>`;
    }

    alvo.innerHTML = `
      <div class="reg-cab">
        <h1>${esc(d.regiao)}</h1>
        <p class="sub">${sub}</p>
      </div>
      <p class="reg-meta">Actualizado ${esc(q)} · evolução e eventos desde 15 ago 2026</p>

      <section class="reg-sec"><h2>Ranking</h2>
        <table class="reg-rank"><tbody>${rankRows}</tbody></table>
        <p class="reg-totais" style="margin-top:8px">Região com
          <b>${nfmt(d.totais.z17)}</b> squadratinhos${d.totais.z14 != null ? ` · <b>${nfmt(d.totais.z14)}</b> squadrats` : ''}
          no total.</p>
      </section>

      ${evolSec}

      <section class="reg-sec"><h2>Eventos nesta região</h2>${evHtml}</section>

      <section class="reg-sec"><h2>Faz fronteira com</h2><div class="reg-viz">${viz}</div></section>

      <p class="reg-rodape">Ranking e % são de <b>squadratinhos</b> (zoom 17, ~201 m); o
        total inclui o de squadrats (1609 m). Dados actualizados 6×/dia pelo mesmo
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
    document.title = `${d.regiao} — Squadrats Club`;
    pintar(d, eventos);
  }
  carregar();
})();
