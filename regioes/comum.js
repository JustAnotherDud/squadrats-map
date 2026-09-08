// Vocabulário e componentes partilhados pelas páginas de regiões: o índice
// (index.html), as páginas de região (regiao.js) e as de país (pais.js).
// Carregar SEMPRE depois de shared.js e antes desses. Não é um módulo:
// define no scope global do <script>, como o shared.js.

/* eslint-disable no-unused-vars */

const COR_FB = {
  'Zé': '#e03131', 'Xeira': '#9c46d8', 'Carolina': '#c99a00',
  'Inês S.': '#e8710a', 'Pedro': '#2f5fd0',
};
let CORES = { ...COR_FB };
const cor = n => CORES[n] || '#7d8598';

const esc = s => String(s).replace(/[&<>"]/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const nfmt = n => (n == null ? '·' : n.toLocaleString('pt-PT'));
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
const dot = n => `<span class="dot" style="background:${cor(n)}"></span>`;
const atl = n => `<a class="atl" href="../atletas/${slugify(n)}.html">${esc(n)}</a>`;

// Carrega e funde as cores dos membros (membros_cores.json). Falha em
// silêncio, fica com COR_FB.
async function carregarCores(url, nc) {
  try {
    const r = await fetch(url, nc);
    if (r.ok) { const j = await r.json(); CORES = { ...COR_FB, ...(j.cores || {}) }; }
  } catch (e) { /* fallback */ }
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
    const lid = x.lider
      ? `${dot(x.lider)}${esc(x.lider)}${x.n > 1 ? ` <span class="pct">+${x.n - 1}</span>` : ''}`
      : '·';
    const linha = `<tr class="sr-row${exp ? ' exp' : ''}"${exp ? ` data-i="${i}"` : ''}>
      <td>${exp ? '<span class="sr-tri">▸</span>' : ''}${nomeCel}</td>
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

// Liga o clique de expansão numa tabela do tabelaSubRegioes({detalheHtml}).
function ligarExpansao(tabela) {
  if (!tabela) return;
  tabela.addEventListener('click', e => {
    const row = e.target.closest('.sr-row.exp');
    if (!row || !tabela.contains(row)) return;
    const det = tabela.querySelector(`.sr-det[data-i="${row.dataset.i}"]`);
    if (!det) return;
    det.hidden = !det.hidden;
    row.classList.toggle('aberto', !det.hidden);
  });
}
