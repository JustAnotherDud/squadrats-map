// Página de um país (regioes/pais-<cc>.html). Constrói tudo no browser a
// partir de dois ficheiros já publicados na branch `data`: club_regioes.json
// (capturado por atleta + união por país) e stats.json (totais). Sem passo de
// pipeline próprio, sem JSON novo. shared.js dá PAIS_NOME / fmtDataHora /
// slugify; nav.js à parte.
(function () {
  'use strict';

  const RAW = 'https://raw.githubusercontent.com/JustAnotherDud/squadrats-map/';
  const LOCAL = ['localhost', '127.0.0.1', ''].includes(location.hostname);
  const U_CR = LOCAL ? '../data/club_regioes.json' : RAW + 'data/data/club_regioes.json';
  const U_STATS = LOCAL ? '../data/stats.json' : RAW + 'data/data/stats.json';
  const U_CORES = LOCAL ? '../data/membros_cores.json' : RAW + 'main/data/membros_cores.json';
  const NC = { cache: 'no-cache' };

  const alvo = document.getElementById('pais');
  const CC = (alvo.dataset.cc || '').toUpperCase();

  const COR_FB = { 'Zé': '#e03131', 'Xeira': '#9c46d8', 'Carolina': '#c99a00', 'Inês S.': '#e8710a', 'Pedro': '#2f5fd0' };
  let CORES = { ...COR_FB };
  const cor = n => CORES[n] || '#7d8598';
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const nfmt = n => (n || 0).toLocaleString('pt-PT');
  // % contra o total de um país inteiro é sempre minúsima: 2 casas, e um piso
  // "<0,01%" em vez de "0,00%" que não diz nada.
  const pctfmt = p => (p == null ? '' : (p > 0 && p < 0.005 ? '<0,01%' : p.toFixed(2) + '%'));
  const dot = n => `<span class="dot" style="background:${cor(n)}"></span>`;
  const atl = n => `<a class="atl" href="../atletas/${slugify(n)}.html">${esc(n)}</a>`;

  // chave do bloco de totais do país em stats.json
  const statKeyPais = cc => (cc === 'PT' ? 'country_pt' : 'country_' + cc.toLowerCase());
  const statKeyRegioes = cc => (cc === 'PT' ? 'by_distrito' : 'by_region_' + cc.toLowerCase());

  function rankingPais(cr, cc) {
    const uni = cr.uniao || {};
    const exc = ((uni.exclusivos || {}).by_pais || {})[cc] || {};
    const pares = [];
    for (const [nome, info] of Object.entries(cr.atletas || {})) {
      const n = ((info.country || {})[cc]) || 0;
      if (n > 0) pares.push([nome, n]);
    }
    pares.sort((a, b) => (b[1] - a[1]) || a[0].localeCompare(b[0], 'pt'));
    return { pares, exc, uniPais: (uni.by_pais || {})[cc] || 0 };
  }

  // ES e outros não-PT: províncias/regiões com actividade. Sem união por
  // região no estrangeiro (não é calculada), mostra-se o líder do clube em
  // cada uma e o que ele capturou. Fonte: club_regioes.atletas[*].by_region.
  function regioesEstrangeiras(cr, stats, cc) {
    const ccl = cc.toLowerCase();
    const totais = stats[statKeyRegioes(cc)] || {};
    const uniReg = ((cr.uniao || {}).by_region || {})[ccl] || {};
    const porRegiao = {}; // regiao -> {atleta: captured}
    for (const [nome, info] of Object.entries(cr.atletas || {})) {
      const br = (info.by_region || {})[ccl] || {};
      for (const [reg, n] of Object.entries(br)) {
        if (n > 0) (porRegiao[reg] = porRegiao[reg] || {})[nome] = n;
      }
    }
    const linhas = Object.entries(porRegiao).map(([reg, porAtl]) => {
      const ord = Object.entries(porAtl).sort((a, b) => b[1] - a[1]);
      const lider = ord[0][0];
      const uni = uniReg[reg] || 0;
      const tot = ((totais[reg] || {}).z17 || {}).total || null;
      return { reg, lider, uni, n: ord.length, tot, pct: tot ? 100 * uni / tot : null };
    });
    linhas.sort((a, b) => (b.uni - a.uni) || a.reg.localeCompare(b.reg, 'pt'));
    return linhas;
  }

  function pintar(cr, stats) {
    const nome = PAIS_NOME[CC] || CC;
    document.title = `${nome} · Squadrats Club`;

    const tot = stats[statKeyPais(CC)] || {};
    const z17 = (tot.z17 || {}).total || null;
    const q = fmtDataHora(cr.atualizado);

    const { pares, exc, uniPais } = rankingPais(cr, CC);
    const temExc = ((cr.uniao || {}).exclusivos || {}).by_pais != null;
    const rankRows = pares.map(([n, cap], i) => {
      const pct = z17 ? (100 * cap / z17) : null;
      return `<tr>
        <td class="pos${i === 0 ? ' p1' : ''}">${i + 1}º</td>
        <td><span class="nome">${dot(n)}${atl(n)}</span></td>
        <td class="num">${nfmt(cap)}</td>
        ${temExc ? `<td class="uni">${exc[n] ? nfmt(exc[n]) : '·'}</td>` : ''}
        <td class="pct">${pctfmt(pct)}</td>
      </tr>`;
    }).join('');
    const rankHead = `<thead><tr>
      <th></th><th class="h-nome">atleta</th>
      <th title="squadratinhos do atleta no país, partilhados incluídos">total</th>
      ${temExc ? '<th title="squadratinhos que mais nenhum membro do clube tem">únicos</th>' : ''}
      <th>%</th></tr></thead>`;

    const uniLinha = uniPais
      ? ` O clube cobre <b>${nfmt(uniPais)}</b>${z17 ? ` (${(100 * uniPais / z17).toFixed(2)}%)` : ''}.`
      : '';

    let extra = '';
    if (CC === 'PT') {
      extra = `<section class="reg-sec">
        <p class="reg-tl-so">Detalhe por distrito e concelho no
          <a href="index.html">índice de regiões</a>.</p>
      </section>`;
    } else {
      const linhas = regioesEstrangeiras(cr, stats, CC);
      const rows = linhas.length ? linhas.map(l => `
        <tr>
          <td><span class="nome">${esc(l.reg)}</span></td>
          <td class="num">${nfmt(l.uni)}</td>
          <td class="uni">${dot(l.lider)}${esc(l.lider)}${l.n > 1 ? ` <span class="pct">+${l.n - 1}</span>` : ''}</td>
          <td class="pct">${pctfmt(l.pct)}</td>
        </tr>`).join('') : '<tr><td colspan="4" class="reg-vazio">Sem regiões com actividade.</td></tr>';
      extra = `<section class="reg-sec"><h2>Por região</h2>
        <table class="reg-rank">
          <thead><tr><th class="h-nome">região</th>
            <th title="squadratinhos que o clube cobre nessa região, união dos membros">cobre</th>
            <th>líder</th><th>%</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
        <p class="reg-viz-nota">Regiões estrangeiras não têm página própria (sem
          ranking nem eventos). "+N" = outros membros também presentes.</p>
      </section>`;
    }

    alvo.innerHTML = `
      <div class="reg-cab">
        <h1>${esc(nome)}</h1>
        <p class="sub">país</p>
      </div>
      <p class="reg-meta">Actualizado ${esc(q)}</p>

      <section class="reg-sec"><h2>Ranking do clube</h2>
        ${pares.length
          ? `<table class="reg-rank">${rankHead}<tbody>${rankRows}</tbody></table>`
          : '<p class="reg-vazio">Nenhum membro do clube tem squadratinhos aqui.</p>'}
        <p class="reg-totais" style="margin-top:8px">País com
          <b>${z17 != null ? nfmt(z17) : '?'}</b> squadratinhos.${uniLinha}</p>
      </section>

      ${extra}

      <p class="reg-rodape"><a href="index.html">← todas as regiões</a> ·
        ranking e % são de <b>squadratinhos</b> (zoom 17, ~201 m); <b>únicos</b> =
        sem mais nenhum membro do clube. Dados actualizados 6×/dia pelo mesmo
        processo que gera o <a href="../club.html">mapa do clube</a>.</p>`;
  }

  async function carregar() {
    try {
      const rc = await fetch(U_CORES, NC);
      if (rc.ok) { const j = await rc.json(); CORES = { ...COR_FB, ...(j.cores || {}) }; }
    } catch (e) { /* fallback */ }
    let cr, stats;
    try {
      const [r1, r2] = await Promise.all([fetch(U_CR, NC), fetch(U_STATS, NC)]);
      if (!r1.ok) throw new Error('club_regioes ' + r1.status);
      if (!r2.ok) throw new Error('stats ' + r2.status);
      cr = await r1.json();
      stats = await r2.json();
    } catch (e) {
      alvo.innerHTML = `<p class="reg-estado reg-erro">Não consegui carregar
        ${esc(PAIS_NOME[CC] || CC)} (${esc(e.message)}).</p>`;
      return;
    }
    pintar(cr, stats);
  }
  carregar();
})();
