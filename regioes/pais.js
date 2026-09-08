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
  const U_ADJ = LOCAL ? '../data/adjacency.json' : RAW + 'main/data/adjacency.json';
  const U_CORES = LOCAL ? '../data/membros_cores.json' : RAW + 'main/data/membros_cores.json';
  const NC = { cache: 'no-cache' };

  const alvo = document.getElementById('pais');
  const CC = (alvo.dataset.cc || '').toUpperCase();

  // cor / esc / nfmt / pctfmt / dot / atl / carregarCores / tabelaSubRegioes
  // / ligarExpansao: comum.js
  const PCT_PAIS = { casas: 2, piso: true };  // % contra um país inteiro é minúscula

  // chaves em stats.json / adjacency.json por país
  const statKeyPais = cc => (cc === 'PT' ? 'country_pt' : 'country_' + cc.toLowerCase());
  const statKeyRegioes = cc => (cc === 'PT' ? 'by_distrito' : 'by_region_' + cc.toLowerCase());
  const adjKeyRegioes = { ES: 'provincias_es', DE: 'laender_de', MA: 'regioes_ma', AD: 'paroquias_ad' };

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
               pares: ord, tot, pct: tot ? 100 * uni / tot : null };
    }).sort((a, b) => (b.uniao - a.uniao) || a.nome.localeCompare(b.nome, 'pt'));
  }

  // Expansão de uma província: ranking por atleta (capturado, únicos, %) e
  // os vizinhos (adjacency.json). Sem página própria, os vizinhos são texto;
  // a cheio os que também têm actividade do clube.
  function detalheProvincia(x, cr, cc, adjReg, comAtividade) {
    const ccl = cc.toLowerCase();
    const excR = ((((cr.uniao || {}).exclusivos || {}).by_region || {})[ccl] || {})[x.nome] || {};
    const lider = x.pares.length ? x.pares[0][1] : 0;
    const linhas = x.pares.map(([n, cap], i) => `<tr>
      <td class="pos">${i + 1}</td>
      <td><span class="nome">${dot(n)}${atl(n)}</span></td>
      <td class="tira-td">${tira(cor(n), lider ? cap / lider : 0)}</td>
      <td class="num">${nfmt(cap)}</td>
      <td class="uni">${excR[n] ? nfmt(excR[n]) : ''}</td>
      <td class="pct">${pctfmt(x.tot ? 100 * cap / x.tot : null, PCT_PAIS)}</td>
    </tr>`).join('');
    const vz = ((adjReg[x.nome] || {}).neighbors || []);
    const vizTxt = vz.map(v => comAtividade.has(v) ? `<b>${esc(v)}</b>` : esc(v)).join(', ');
    return `<table class="reg-rank"><thead><tr><th></th><th class="h-nome">atleta</th>
      <th class="h-nome">quota</th><th>total</th><th>únicos</th><th>%</th></tr></thead>
      <tbody>${linhas}</tbody></table>
      ${vizTxt ? `<p class="reg-viz-nota">Faz fronteira com ${vizTxt}. A cheio, os que também têm actividade do clube.</p>` : ''}`;
  }

  function pintar(cr, stats, adj) {
    const nome = PAIS_NOME[CC] || CC;
    document.title = `${nome} · Squadrats Club`;
    let ns = 0;
    const sec = t => `<div class="sec"><span class="n">${String(++ns).padStart(2, '0')}</span><span class="t">${t}</span></div>`;

    const tot = stats[statKeyPais(CC)] || {};
    const z17 = (tot.z17 || {}).total || null;
    const q = fmtDataHora(cr.atualizado);

    const { pares, exc, uniPais } = rankingPais(cr, CC);
    const temExc = ((cr.uniao || {}).exclusivos || {}).by_pais != null;
    const lider = pares.length ? pares[0][1] : 0;
    const rankRows = pares.map(([n, cap], i) => {
      const pct = z17 ? (100 * cap / z17) : null;
      return `<tr>
        <td class="pos">${i + 1}</td>
        <td><span class="nome">${dot(n)}${atl(n)}</span></td>
        <td class="tira-td">${tira(cor(n), lider ? cap / lider : 0)}</td>
        <td class="num">${nfmt(cap)}</td>
        ${temExc ? `<td class="uni">${exc[n] ? nfmt(exc[n]) : ''}</td>` : ''}
        <td class="pct">${pctfmt(pct, PCT_PAIS)}</td>
      </tr>`;
    }).join('');
    const rankHead = `<thead><tr>
      <th></th><th class="h-nome">atleta</th><th class="h-nome">quota</th>
      <th title="squadratinhos do atleta no país, partilhados incluídos">total</th>
      ${temExc ? '<th title="squadratinhos que mais nenhum membro do clube tem">únicos</th>' : ''}
      <th>%</th></tr></thead>`;

    const cobre = `<p class="reg-cobre">País com <b>${z17 != null ? nfmt(z17) : '?'}</b> squadratinhos`
      + (uniPais ? `, o clube cobre <b>${nfmt(uniPais)}</b>${z17 ? ` (${(100 * uniPais / z17).toFixed(2)}%)` : ''}` : '')
      + '.</p>';

    let extra = '';
    if (CC === 'PT') {
      extra = `<p class="reg-cobre">Detalhe por distrito e concelho no <a href="index.html">índice de regiões</a>.</p>`;
    } else {
      const linhas = subRegioesPais(cr, stats, CC);
      const adjReg = (adj || {})[adjKeyRegioes[CC]] || {};
      const comAtividade = new Set(linhas.map(l => l.nome));
      const tab = linhas.length
        ? tabelaSubRegioes(linhas, {
            rotulo: 'cobre', pctOpts: PCT_PAIS,
            detalheHtml: x => detalheProvincia(x, cr, CC, adjReg, comAtividade),
          })
        : '<p class="reg-vazio">Sem regiões com actividade.</p>';
      extra = sec('Por região') + tab
        + `<p class="reg-viz-nota">Regiões estrangeiras não têm página própria.
           Carrega numa linha para o ranking por atleta e os vizinhos dessa
           província.</p>`;
    }

    alvo.innerHTML = `
      <div class="reg-cab">
        <h1>${esc(nome)}</h1>
        <p class="sub">país</p>
        <dl class="meta"><dt>actualizado</dt><dd>${esc(q)}</dd></dl>
      </div>

      ${sec('Ranking do clube')}
      ${pares.length
        ? `<table class="reg-rank">${rankHead}<tbody>${rankRows}</tbody></table>`
        : '<p class="reg-vazio">Nenhum membro do clube tem squadratinhos aqui.</p>'}
      ${cobre}

      ${extra}

      <p class="reg-rodape">
        <a class="voltar" href="index.html">todas as regiões</a><br>
        ranking e % são de <b>squadratinhos</b> (zoom 17, ~201 m). <b>únicos</b> =
        sem mais nenhum membro do clube. Dados 6×/dia, mesmo processo que o
        <a href="../club.html">mapa do clube</a>.</p>`;

    ligarExpansao(alvo.querySelector('.sr-exp'));
  }

  async function carregar() {
    await carregarCores(U_CORES, NC);
    let cr, stats, adj = {};
    try {
      const pedidos = [fetch(U_CR, NC), fetch(U_STATS, NC)];
      if (CC !== 'PT') pedidos.push(fetch(U_ADJ, NC));
      const [r1, r2, r3] = await Promise.all(pedidos);
      if (!r1.ok) throw new Error('club_regioes ' + r1.status);
      if (!r2.ok) throw new Error('stats ' + r2.status);
      cr = await r1.json();
      stats = await r2.json();
      if (r3 && r3.ok) adj = await r3.json();
    } catch (e) {
      alvo.innerHTML = `<p class="reg-estado reg-erro">Não consegui carregar
        ${esc(PAIS_NOME[CC] || CC)} (${esc(e.message)}).</p>`;
      return;
    }
    pintar(cr, stats, adj);
  }
  carregar();
})();
