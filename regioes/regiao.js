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

  // --- timeline: SVG de degraus, uma linha por atleta ---
  function timelineSvg(tl, gerado, cabecalhoRanking) {
    // {atleta: [[dataISO, valor], ...]} — carrega o último valor até `gerado`
    const fimIso = (gerado || '').slice(0, 10) || tl[tl.length - 1].data;
    const nomes = new Set();
    tl.forEach(p => p.ranking.forEach(([n]) => nomes.add(n)));
    cabecalhoRanking.forEach(r => nomes.add(r.nome));
    const serie = {};
    for (const n of nomes) serie[n] = [];
    for (const p of tl) {
      const m = Object.fromEntries(p.ranking);
      for (const n of nomes) serie[n].push([p.data, m[n] || 0]);
    }
    // filtrar quem esteve sempre a 0
    for (const n of [...nomes]) if (serie[n].every(([, v]) => v === 0)) { delete serie[n]; nomes.delete(n); }
    if (!nomes.size) return '';

    const datas = [...new Set(tl.map(p => p.data)).add(fimIso)].sort();
    const t0 = Date.parse(datas[0]), t1 = Date.parse(fimIso) || Date.parse(datas[datas.length - 1]);
    const maxV = Math.max(1, ...Object.values(serie).flat().map(([, v]) => v));
    const W = 620, H = 120, pl = 4, pr = 4, pt = 8, pb = 16;
    const x = iso => pl + (t1 === t0 ? 0.5 : (Date.parse(iso) - t0) / (t1 - t0)) * (W - pl - pr);
    const y = v => pt + (1 - v / maxV) * (H - pt - pb);

    let paths = '';
    for (const [n, pts] of Object.entries(serie)) {
      const ext = pts.concat([[fimIso, pts[pts.length - 1][1]]]);
      let d = '';
      ext.forEach(([iso, v], i) => {
        const px = x(iso).toFixed(1), py = y(v).toFixed(1);
        if (i === 0) d += `M${px} ${py}`;
        else { const prevY = y(ext[i - 1][1]).toFixed(1); d += `L${px} ${prevY}L${px} ${py}`; }
      });
      paths += `<path d="${d}" fill="none" stroke="${cor(n)}" stroke-width="1.6" opacity="0.9"/>`;
    }
    return `<svg class="reg-tl" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
      <line class="base" x1="${pl}" y1="${H - pb}" x2="${W - pr}" y2="${H - pb}"/>
      ${paths}
      <text x="${pl}" y="${H - 3}">${dCurta(datas[0])}</text>
      <text x="${W - pr}" y="${H - 3}" text-anchor="end">${dCurta(fimIso)}</text>
      <text x="${pl}" y="${pt + 8}">${nfmt(maxV)}</text>
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

    const tl = (d.timeline && d.timeline.length)
      ? timelineSvg(d.timeline, d.gerado, d.ranking) +
        `<p class="reg-tl-nota">Squadratinhos capturados por atleta ao longo do tempo — as linhas a cruzar-se são mudanças de posição.</p>`
      : '<p class="reg-vazio">Sem histórico suficiente.</p>';

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

      <section class="reg-sec"><h2>Evolução</h2>${tl}</section>

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
