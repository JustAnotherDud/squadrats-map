// Vocabulário e componentes partilhados pelas páginas de regiões: o índice
// (index.html), as páginas de região (regiao.js) e as de país (pais.js).
// Carregar SEMPRE depois de shared.js e antes desses. Não é um módulo:
// define no scope global do <script>, como o shared.js.

/* eslint-disable no-unused-vars */

// cor / esc / nfmt / tile / atl / tira / carregarCores / COR_FALLBACK / CORES:
// shared.js (carregado antes deste ficheiro).

// % de squadratinhos: 1 casa em geral. Opções:
//   piso      "<0,01%" em vez de "0,00%" (páginas de país, % de um país inteiro)
//   casas     nº de casas decimais (default 1; país usa 2)
//   compacto  >= 9,5% mostra inteiro ("20%" em vez de "20,0%"), no índice
const pctfmt = (p, opts) => {
  if (p == null) return '';
  opts = opts || {};
  if (opts.piso && p > 0 && p < 0.005) return '<0,01%';
  if (opts.compacto && p >= 9.5) return Math.round(p) + '%';
  return p.toFixed(opts.casas != null ? opts.casas : 1) + '%';
};
// Medidor de profundidade da cobertura do clube numa região (a primitiva
// .cobertura do site.css). NÃO é uma barra proporcional: das 100 regiões com
// actividade, 61 estão abaixo de 1% e 47 abaixo de 0,5%, uma barra linear de
// 0 a 100% estaria quase sempre vazia. É uma escada de patamares ~x3, cada
// célula acesa = passou esse patamar. Com estes seis, a contagem de células
// espalha-se bem pela distribuição real (0..6 células, todas povoadas).
const COBERTURA_PATAMARES = [0.05, 0.2, 0.7, 2, 6, 18];
function barraCobertura(pct) {
  if (pct == null) return '';
  const n = COBERTURA_PATAMARES.filter(t => pct >= t).length;
  const cels = COBERTURA_PATAMARES
    .map((_, i) => `<i class="${i < n ? 'on' : ''}"></i>`).join('');
  return `<span class="cobertura" role="img" aria-label="profundidade da `
    + `cobertura: ${n} de ${COBERTURA_PATAMARES.length}" style="grid-template-`
    + `columns:repeat(${COBERTURA_PATAMARES.length},6px);color:var(--ganho)">`
    + `${cels}</span>`;
}

// Tabela de sub-regiões: nome (link opcional) | união do clube | líder | %.
// É o mesmo componente nos concelhos de uma página de distrito e nas
// províncias de uma página de país.
//   linhas: [{nome, key?, uniao, pct, lider, n?, disp?}], já ordenada
//   opts.rotulo      cabeçalho da coluna da união (default "cobre")
//   opts.linkKey     se true e a linha tem `key`, o nome liga a <key>.html
//   opts.pctOpts     passado a pctfmt (ex. {casas:2, piso:true} nas províncias)
//   opts.detalheHtml fn(linha) -> html: torna cada linha expansível (▸),
//                    com esse html numa linha por baixo. Ligar com
//                    ligarExpansao() depois de inserir no DOM.
function tabelaSubRegioes(linhas, opts) {
  opts = opts || {};
  const rot = opts.rotulo || 'cobre';
  const exp = typeof opts.detalheHtml === 'function';
  const corpo = linhas.map((x, i) => {
    const nomeCel = (opts.linkKey && x.key)
      ? `<a class="idx-nome${x.disp ? ' disp' : ''}" href="${x.key}.html">${esc(x.nome)}</a>`
      : `<span class="sr-nome">${esc(x.nome)}</span>`;
    const lid = x.lider ? `${tile(x.lider)}${esc(x.lider)}` : '';
    // linha expansível: o ▸ é um <button> real, para o teclado lá chegar e o
    // Enter/Espaço dispararem o mesmo clique. aria-label leva o nome porque a
    // célula do nome pode ser só um <span> (províncias, sem página).
    const tri = exp
      ? `<button type="button" class="sr-tri" aria-expanded="false" aria-label="detalhe de ${esc(x.nome)}">▸</button>`
      : '';
    const linha = `<tr class="sr-row${exp ? ' exp' : ''}"${exp ? ` data-i="${i}"` : ''}>
      <td>${tri}${nomeCel}</td>
      <td class="num">${nfmt(x.uniao)}</td>
      <td class="uni">${lid}</td>
      <td class="pct">${pctfmt(x.pct, opts.pctOpts)}</td>
    </tr>`;
    const det = exp
      ? `<tr class="sr-det" data-i="${i}" hidden><td colspan="4">${opts.detalheHtml(x)}</td></tr>`
      : '';
    return linha + det;
  }).join('');
  return `<table class="reg-rank${exp ? ' sr-exp' : ''}">
    <thead><tr><th class="h-nome">região</th><th>${esc(rot)}</th>
      <th>líder</th><th>%</th></tr></thead>
    <tbody>${corpo}</tbody></table>`;
}

// Liga a expansão numa tabela do tabelaSubRegioes({detalheHtml}). O clique
// vale na linha toda (rato) e o <button.sr-tri> trata do teclado (Enter/Espaço
// disparam clique nativo, que borbulha para aqui).
function ligarExpansao(tabela) {
  if (!tabela) return;
  tabela.addEventListener('click', e => {
    // clique num link dentro da linha (ex: o nome do distrito, que também
    // liga à página) navega, não expande.
    if (e.target.closest('a')) return;
    const row = e.target.closest('.sr-row.exp');
    if (!row || !tabela.contains(row)) return;
    const det = tabela.querySelector(`.sr-det[data-i="${row.dataset.i}"]`);
    if (!det) return;
    det.hidden = !det.hidden;
    row.classList.toggle('aberto', !det.hidden);
    const tri = row.querySelector('.sr-tri');
    if (tri) tri.setAttribute('aria-expanded', String(!det.hidden));
  });
}
