// Página de uma região (concelho/distrito PT). Lê data/regioes/<key>.json +
// data/events.json da branch `data`. Sem dependências (nav.js à parte).
(function () {
  'use strict';

  const RAW = 'https://raw.githubusercontent.com/JustAnotherDud/squadrats-map/';
  const LOCAL = ['localhost', '127.0.0.1', ''].includes(location.hostname);
  const U_REG = k => (LOCAL ? '../data/regioes/' : RAW + 'data/data/regioes/') + k + '.json';
  const U_EVENTS = LOCAL ? '../data/events.json' : RAW + 'data/data/events.json';
  const U_IDX = LOCAL ? '../data/regioes_index.json' : RAW + 'data/data/regioes_index.json';
  const U_CORES = LOCAL ? '../data/membros_cores.json' : RAW + 'main/data/membros_cores.json';
  const NC = { cache: 'no-cache' };

  const alvo = document.getElementById('regiao');
  const KEY = alvo.dataset.key, NIVEL = alvo.dataset.nivel, NOME = alvo.dataset.nome;

  // cor / esc / nfmt / tile / atl / tira / carregarCores: shared.js
  // pctfmt / tabelaSubRegioes: comum.js

  const ICO = { ultrapassagem: '⇅', novo_lider: '👑', primeira_presenca: '📍', marco: '🚩' };
  function frase(e) {
    const v = e.valores;
    if (e.tipo === 'ultrapassagem')
      return `${tile(e.quem)}${atl(e.quem)} passou ${tile(e.sobre)}${atl(e.sobre)}
        <span class="num">${nfmt(v[0])} vs ${nfmt(v[1])}</span>`;
    if (e.tipo === 'novo_lider')
      return `${tile(e.quem)}${atl(e.quem)} assumiu a liderança, passou ${tile(e.sobre)}${atl(e.sobre)}
        <span class="num">${nfmt(v[0])} vs ${nfmt(v[1])}</span>`;
    if (e.tipo === 'primeira_presenca')
      return `${tile(e.quem)}${atl(e.quem)} estreou-se aqui
        <span class="num">${nfmt(v[0])} squadratinho${v[0] === 1 ? '' : 's'}</span>`;
    return `${tile(e.quem)}${atl(e.quem)} passou os <b>${nfmt(v[0])}</b> squadratinhos,
      <span class="num">agora ${nfmt(v[1])}</span>`;
  }

  // vizinho "disputado" = com evento de troca (ultrapassagem / novo líder),
  // mesma definição da fila "Regiões disputadas" do historico.html. Uma
  // estreia (📍) mexe na ordem mas não é passar ninguém, não conta.
  function temEventoTroca(eventos, d) {
    return eventos.some(e =>
      (e.tipo === 'ultrapassagem' || e.tipo === 'novo_lider') &&
      e.nivel === d.nivel && e.regiao === d.regiao);
  }

  // "8 set 2026" -> "8 set" para a coluna de data do feed
  const diaCurto = iso => fmtData(iso).replace(/\s\d{4}$/, '');

  function pintar(d, eventos, filhos) {
    const q = fmtDataHora(d.gerado);
    let ns = 0;
    const sec = t => `<div class="sec"><span class="n">${String(++ns).padStart(2, '0')}</span><span class="t">${t}</span></div>`;

    // hierarquia acima, sem setas: só a palavra do nível debaixo do nome; os
    // pais (distrito, país) vão para linhas com rótulo no bloco de meta. Todas
    // as regiões com página são PT (uma estrangeira usaria pais-<cc>.html).
    const paisRow = '<dt>país</dt><dd><a href="pais-pt.html">Portugal</a></dd>';
    const paiRows = d.nivel === 'concelho'
      ? (d.distrito_pai ? `<dt>distrito</dt><dd><a href="${d.distrito_pai_key}.html">${esc(d.distrito_pai)}</a></dd>` : '') + paisRow
      : paisRow;

    const temExc = d.ranking.some(r => r.exclusivos != null);
    const lider = d.ranking.length ? d.ranking[0].captured : 0;
    const rankRows = d.ranking.map((r, i) => `
      <tr class="${i === 0 ? 'p1' : ''}">
        <td class="pos${i === 0 ? ' p1' : ''}">${i + 1}</td>
        <td><span class="nome">${tile(r.nome)}${atl(r.nome)}</span></td>
        <td class="tira-td">${tira(cor(r.nome), lider ? r.captured / lider : 0)}</td>
        <td class="num">${nfmt(r.captured)}</td>
        ${temExc ? `<td class="uni">${r.exclusivos ? nfmt(r.exclusivos) : ''}</td>` : ''}
        <td class="pct">${r.pct != null ? r.pct.toFixed(1) + '%' : ''}</td>
      </tr>`).join('');
    const rankHead = `<thead><tr>
      <th></th><th class="h-nome">atleta</th><th class="h-nome">quota</th>
      <th title="squadratinhos do atleta na região, partilhados incluídos">total</th>
      ${temExc ? '<th title="squadratinhos que mais nenhum membro do clube tem aqui">únicos</th>' : ''}
      <th>%</th></tr></thead>`;

    const uni = d.uniao && d.uniao.z17 != null ? d.uniao : null;
    const cobre = `<p class="reg-cobre">Região com <b>${nfmt(d.totais.z17)}</b>
      squadratinhos${uni ? `, o clube cobre <b>${nfmt(uni.z17)}</b>${uni.pct != null ? ` (${pctfmt(uni.pct)})` : ''}` : ''}.</p>`;

    const evReg = eventos.filter(e => e.nivel === d.nivel && e.regiao === d.regiao)
      .sort((a, b) => b.data.localeCompare(a.data));
    const evHtml = evReg.length ? evReg.map((e, i) => `
      <div class="reg-ev">
        <span class="dia">${diaCurto(e.data)}</span>
        <span class="ico">${ICO[e.tipo] || ''}</span>
        <span class="corpo">${frase(e)}</span>
      </div>`).join('') : '<p class="reg-vazio">Nada registado nesta região.</p>';

    const vizDisp = v => v.tem_pagina && temEventoTroca(eventos, { nivel: d.nivel, regiao: v.nome });
    const viz = d.vizinhos.length ? d.vizinhos.map(v => {
      if (!v.tem_pagina) return `<span>${esc(v.nome)}</span>`;
      const dp = vizDisp(v);
      return `<a class="${dp ? 'viz-disp' : ''}" href="${v.key}.html"${dp ? ' title="troca de posição no ranking desde 26 jul"' : ''}>${esc(v.nome)}</a>`;
    }).join(' ') : '<span class="reg-vazio">sem vizinhos com página</span>';
    const algumVizDisp = d.vizinhos.some(vizDisp);

    const temFilhos = filhos && filhos.length;
    const filhosTabela = temFilhos
      ? tabelaSubRegioes(filhos, { rotulo: 'cobre', linkKey: true })
        + `<p class="reg-viz-nota">União do clube em cada concelho e a fracção que
           representa, por ordem de união. A ouro: concelho com troca de posição
           no ranking.</p>`
      : '';

    alvo.innerHTML = `
      <div class="reg-cab">
        <h1>${esc(d.regiao)}</h1>
        <p class="sub">${d.nivel}</p>
        <dl class="meta">
          ${paiRows}
          <dt>actualizado</dt><dd>${esc(q)}</dd>
          <dt>eventos desde</dt><dd>26 jul 2026</dd>
        </dl>
      </div>

      ${sec('Ranking')}
      <table class="reg-rank">${rankHead}<tbody>${rankRows}</tbody></table>
      ${cobre}

      ${temFilhos ? sec('Concelhos') + filhosTabela : ''}

      ${sec('Eventos')}
      ${evHtml}

      ${sec('Faz fronteira com')}
      <div class="reg-viz">${viz}</div>
      ${algumVizDisp ? '<p class="reg-viz-nota">A ouro: vizinhos com troca de posição no ranking desde 26 jul.</p>' : ''}

      <p class="reg-rodape">
        <a class="voltar" href="index.html">todas as regiões</a><br>
        ranking e % são de <b>squadratinhos</b> (zoom 17, ~201 m). <b>únicos</b> =
        sem mais nenhum membro do clube. Dados 6×/dia, mesmo processo que o
        <a href="../club.html">mapa do clube</a>. O
        <a href="../historico.html">histórico</a> tem o feed completo.</p>`;
  }

  async function carregar() {
    await carregarCores(U_CORES, NC);
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

    // distrito: buscar os concelhos filhos ao índice agregado
    let filhos = [];
    if (NIVEL === 'distrito') {
      try {
        const ri = await fetch(U_IDX, NC);
        if (ri.ok) {
          filhos = ((await ri.json()).regioes || [])
            .filter(x => x.nivel === 'concelho' && x.pai_key === KEY)
            .map(x => ({ nome: x.regiao, key: x.key, uniao: x.uniao,
                         pct: x.uniao_pct, lider: x.lider, n: x.n, disp: x.disp }))
            .sort((a, b) => (b.uniao - a.uniao) || a.nome.localeCompare(b.nome, 'pt'));
        }
      } catch (e) { /* sem concelhos, secção não aparece */ }
    }

    document.title = `${d.regiao} · Squadrats Club`;
    pintar(d, eventos, filhos);
  }
  carregar();
})();
