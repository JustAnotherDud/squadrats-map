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

  // cor / esc / nfmt / pctfmt / dot / atl / carregarCores / tabelaSubRegioes: comum.js
  const PCT_PAIS = { casas: 2, piso: true };  // % contra um país inteiro é minúscula

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

  // ES e outros não-PT: províncias/regiões com actividade. União do clube por
  // província (classify_uniao.by_region), total de stats.by_region_<cc>,
  // líder de club_regioes.atletas[*].by_region. Mesma forma que os concelhos
  // de uma página de distrito -> tabelaSubRegioes.
  function subRegioesPais(cr, stats, cc) {
    const ccl = cc.toLowerCase();
    const totais = stats[statKeyRegioes(cc)] || {};
    const uniReg = ((cr.uniao || {}).by_region || {})[ccl] || {};
    const porRegiao = {}; // regiao -> {atleta: captured}
    for (const [nome, info] of Object.entries(cr.atletas || {})) {
      for (const [reg, n] of Object.entries((info.by_region || {})[ccl] || {})) {
        if (n > 0) (porRegiao[reg] = porRegiao[reg] || {})[nome] = n;
      }
    }
    return Object.entries(porRegiao).map(([reg, porAtl]) => {
      const ord = Object.entries(porAtl).sort((a, b) => b[1] - a[1]);
      const uni = uniReg[reg] || 0;
      const tot = ((totais[reg] || {}).z17 || {}).total || null;
      return { nome: reg, uniao: uni, n: ord.length, lider: ord[0][0],
               pct: tot ? 100 * uni / tot : null };
    }).sort((a, b) => (b.uniao - a.uniao) || a.nome.localeCompare(b.nome, 'pt'));
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
        <td class="pct">${pctfmt(pct, PCT_PAIS)}</td>
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
      const linhas = subRegioesPais(cr, stats, CC);
      const tab = linhas.length
        ? tabelaSubRegioes(linhas, { rotulo: 'cobre', pctOpts: PCT_PAIS })
        : '<p class="reg-vazio">Sem regiões com actividade.</p>';
      extra = `<section class="reg-sec"><h2>Por região</h2>
        ${tab}
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
    await carregarCores(U_CORES, NC);
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
