// Perfil de atleta — lê data/atletas/<slug>.json (branch `data`) e desenha
// tudo numa página só. Sem Leaflet, sem dependências além do shared.js
// (bandeiras, PAIS_NOME, NIVEL_LABEL). O build (pipeline/build_profiles.py)
// já juntou e pivotou os dados; aqui é só render.
//
// Duas entradas: #perfil[data-slug] (um atleta) e #perfil-indice (a lista,
// que só precisa das cores).

(function () {
  'use strict';

  const RAW = 'https://raw.githubusercontent.com/JustAnotherDud/squadrats-map/';
  // Em produção lê da branch `data` via raw (o mesmo que club.html faz). Em
  // localhost/ficheiro lê da cópia local (`git checkout origin/data -- data/`),
  // para dar para testar sem publicar nada.
  const LOCAL = ['localhost', '127.0.0.1', ''].includes(location.hostname);
  const DATA_ATLETAS = LOCAL ? '../data/atletas/' : RAW + 'data/data/atletas/';
  const CORES_URL = LOCAL ? '../data/membros_cores.json' : RAW + 'main/data/membros_cores.json';

  const BANDEIRA = bandeiras(15, 11); // shared.js
  const NIVEL_NOME = {
    pais: NIVEL_LABEL.pais, regiao: NIVEL_LABEL.regiao, zona: NIVEL_LABEL.zona,
  };
  const NIVEL_ORDEM = ['pais', 'regiao', 'zona'];

  // linha de cima = grelha squadrats (1609 m); linha de baixo = squadratinhos
  // (201 m). A grelha do CSS é 3 por linha, por isso a ordem aqui é a ordem
  // visual: os 3 "grandes" primeiro, os 3 "-inhos" a seguir.
  const METRICAS = [
    ['squadrats', 'Squadrats', 'Nº de squares de 1609 m visitados.'],
    ['yard', 'Yard', 'Nº de squares do maior cluster fechado — cada square com os 4 vizinhos também visitados.'],
    ['ubersquadrat', 'Übersquadrat', 'Lado do maior quadrado NxN totalmente preenchido, em squadrats.'],
    ['squadratinhos', 'Squadratinhos', 'Nº de squares de 201 m visitados.'],
    ['yardinho', 'Yardinho', 'Igual ao Yard, na grelha fina dos squadratinhos.'],
    ['ubersquadratinho', 'Übersquadratinho', 'Lado do maior quadrado NxN totalmente preenchido, em squadratinhos.'],
  ];

  const CACHE_BUST = { cache: 'no-cache' };

  function esc(s) {
    return String(s).replace(/[&<>"]/g, c => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]
    ));
  }
  const nfmt = n => (n || 0).toLocaleString('pt-PT');
  const paisNome = cc => PAIS_NOME[cc] || cc;
  const flag = cc => BANDEIRA[cc] || '';

  async function carregarCores() {
    try {
      const r = await fetch(CORES_URL, CACHE_BUST);
      if (r.ok) return (await r.json()).cores || {};
    } catch (e) { /* offline: sem cor, não é fatal */ }
    return {};
  }

  // ---------- índice ----------
  async function renderIndice() {
    const cores = await carregarCores();
    INDICE.querySelectorAll('.perfil-cor').forEach(el => {
      const c = cores[el.dataset.nome];
      if (c) el.style.background = c;
    });
  }

  // ---------- perfil ----------
  const alvo = document.getElementById('perfil');
  const INDICE = document.getElementById('perfil-indice');

  function seccao(titulo, corpoHtml) {
    return `<section class="perfil-seccao"><h2>${esc(titulo)}</h2>${corpoHtml}</section>`;
  }

  function blocoTotais(totais) {
    const cards = METRICAS.map(([k, rotulo, tip]) => `
      <div class="perfil-num">
        <div class="v">${nfmt(totais[k])}</div>
        <div class="k" data-tip="${esc(tip)}" tabindex="0">${esc(rotulo)}</div>
      </div>`).join('');
    return `<div class="perfil-grid">${cards}</div>`;
  }

  function blocoSobreposicao(s, cor) {
    if (!s || !s.total) {
      return '<p class="perfil-vazio">Sem conta Squadrats ou sem squadratinhos capturados.</p>';
    }
    const ex = s.exclusivos, pa = s.partilhados, tot = s.total;
    const pex = (100 * ex / tot).toFixed(0), ppa = (100 * pa / tot).toFixed(0);
    return `<div class="perfil-barra">
      <div class="perfil-barra-faixa">
        <i style="width:${pex}%;background:${cor || '#7d8598'}"></i>
        <i style="width:${ppa}%;background:#4a5568"></i>
      </div>
      <div class="perfil-barra-legenda">
        <span class="p"><span class="dot" style="background:${cor || '#7d8598'}"></span>
          só deste atleta <b>${nfmt(ex)}</b> (${pex}%)</span>
        <span class="p"><span class="dot" style="background:#4a5568"></span>
          partilhados <b>${nfmt(pa)}</b> (${ppa}%)</span>
        <span class="p">total <b>${nfmt(tot)}</b></span>
      </div>
    </div>`;
  }

  // Tabela geográfica de squadratinhos: uma coluna por dado, todas ordenáveis,
  // todas as divisões de uma vez (sem "mostrar mais" — o scroll da página trata).
  // acima = capturado de quem está uma posição à FRENTE (falta para subir);
  // abaixo = capturado de quem está uma posição ATRÁS (folga que se tem).
  const COLS = [
    { k: 'divisao', label: 'Divisão', num: false, val: r => r.cc === r.nome ? paisNome(r.cc) : r.nome },
    { k: 'captured', label: 'Capturados', num: true, val: r => r.captured },
    { k: 'total', label: 'Total', num: true, val: r => r.total },
    { k: 'pct', label: '%', num: true, val: r => r.pct },
    { k: 'posicao', label: 'Posição', num: true, val: r => r.posicao },
    // squares que faltam para passar a posição de cima (null = já é 1º)
    { k: 'subir', label: 'Subir', num: true, val: r => r.acima != null ? r.acima - r.captured : null },
    // quanto está à frente da posição de baixo (null = já é último)
    { k: 'folga', label: 'Folga', num: true, val: r => r.abaixo != null ? r.captured - r.abaixo : null },
  ];

  function ordenar(linhas, sort) {
    const col = COLS.find(c => c.k === sort.k) || COLS[1];
    const dir = sort.dir === 'asc' ? 1 : -1;
    return [...linhas].sort((a, b) => {
      let va = col.val(a), vb = col.val(b);
      if (col.num) {
        va = va == null ? -Infinity : va;
        vb = vb == null ? -Infinity : vb;
        return (va - vb) * dir;
      }
      return String(va).localeCompare(String(vb), 'pt') * dir;
    });
  }

  const traco = '<span class="fraco">—</span>';

  function linhaGeo(r) {
    const nome = r.cc === r.nome ? paisNome(r.cc) : esc(r.nome);
    const cls = r.posicao <= 3 && r.de > 1 ? ` p${r.posicao}` : '';
    const subir = r.acima != null ? `<span class="mg-neg">${nfmt(r.acima - r.captured)}</span>` : traco;
    const folga = r.abaixo != null ? `<span class="mg-pos">${nfmt(r.captured - r.abaixo)}</span>` : traco;
    return `<tr>
      <td><span class="nome">${flag(r.cc)}<span>${nome}</span></span></td>
      <td class="n"><b>${nfmt(r.captured)}</b></td>
      <td class="n fraco">${r.total != null ? nfmt(r.total) : '—'}</td>
      <td class="n">${r.pct != null ? r.pct.toFixed(1) + '%' : traco}</td>
      <td class="n"><span class="perfil-pos${cls}">${r.posicao}º</span><span class="fraco"> / ${r.de}</span></td>
      <td class="n mg">${subir}</td>
      <td class="n mg">${folga}</td>
    </tr>`;
  }

  function tabelaGeo(id, linhas, sort) {
    if (!linhas.length) return '<p class="perfil-vazio">Sem squares neste nível.</p>';
    const ord = ordenar(linhas, sort);
    const cabecas = COLS.map(c => {
      const activa = c.k === sort.k;
      const seta = activa ? (sort.dir === 'asc' ? ' ▲' : ' ▼') : '';
      return `<th data-sort="${c.k}"${activa ? ' class="ord"' : ''}>${c.label}${seta}</th>`;
    }).join('');
    return `<div class="perfil-scroll"><table class="perfil-tabela geo">
      <thead><tr>${cabecas}</tr></thead>
      <tbody>${ord.map(linhaGeo).join('')}</tbody>
    </table></div>`;
  }

  function blocoGeo(geo, soDisputadas, sort) {
    const btn = `<button class="perfil-toggle${soDisputadas ? ' on' : ''}" data-geo-filtro>Só disputadas (2+)</button>`;
    const corpo = NIVEL_ORDEM.map(nivel => {
      let linhas = geo[nivel] || [];
      if (soDisputadas) linhas = linhas.filter(r => r.disputada);
      return `<h3 class="perfil-nivel">${esc(NIVEL_NOME[nivel])}</h3>${tabelaGeo(nivel, linhas, sort)}`;
    }).join('');
    return btn + corpo;
  }

  function blocoSpark(dias) {
    const vals = (dias || []).map(d => ({ data: d.data, v: d.squadratinhos || 0 }));
    if (!vals.length || vals.every(d => !d.v)) return '';
    const w = 600, h = 90, pad = 14;
    const max = Math.max(...vals.map(d => d.v), 1);
    const bw = (w - pad * 2) / vals.length;
    const barras = vals.map((d, i) => {
      const bh = (h - pad * 2) * d.v / max;
      const x = pad + i * bw;
      return `<rect x="${x.toFixed(1)}" y="${(h - pad - bh).toFixed(1)}"
        width="${Math.max(bw - 1.5, 1).toFixed(1)}" height="${bh.toFixed(1)}">
        <title>${d.data}: +${d.v} squadratinhos</title></rect>`;
    }).join('');
    const primeiro = vals[0].data, ultimo = vals[vals.length - 1].data;
    return `<svg class="perfil-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
      ${barras}
      <text x="${pad}" y="${h - 2}">${primeiro}</text>
      <text x="${w - pad}" y="${h - 2}" text-anchor="end">${ultimo}</text>
    </svg>`;
  }

  function blocoGanhos(dias) {
    if (!dias || !dias.length) {
      return '<p class="perfil-vazio">Sem ganhos registados desde que o registo diário começou.</p>';
    }
    const campos = METRICAS.map(m => m[0]).filter(c => dias.some(d => d[c]));
    const cab = campos.map(c => `<th>${esc(METRICAS.find(m => m[0] === c)[1])}</th>`).join('');
    const linhas = [...dias].reverse().slice(0, 30).map(d => `
      <tr><td>${esc(d.data)}</td>${campos.map(c => {
        const v = d[c] || 0;
        return `<td class="n">${v > 0 ? '+' + v : (v < 0 ? v : '·')}</td>`;
      }).join('')}</tr>`).join('');
    return blocoSpark(dias) + `<div class="perfil-scroll"><table class="perfil-tabela">
      <thead><tr><th>Dia</th>${cab}</tr></thead><tbody>${linhas}</tbody></table></div>`;
  }

  function pintar(d, cor) {
    const mapaUrl = `https://squadrats.com/map/${encodeURIComponent(d.uid)}/17`;
    const quando = (d.atualizado || '').replace('T', ' ').replace('Z', ' UTC');
    let estado = { soDisputadas: false, sort: { k: 'captured', dir: 'desc' } };

    function desenhar() {
      alvo.innerHTML = `
        <p class="perfil-topo"><a href="index.html">← perfis</a> · <a href="../club.html">mapa do clube</a></p>
        <div class="perfil-cabeca">
          <span class="perfil-cor" style="background:${cor || 'var(--suave)'}"></span>
          <h1>${esc(d.nome)}</h1>
        </div>
        <p class="perfil-meta">Actualizado ${esc(quando)} ·
          <a href="${mapaUrl}" target="_blank" rel="noopener">mapa no squadrats.com ↗</a></p>

        ${seccao('Contagens', blocoTotais(d.totais || {}))}
        ${seccao('Sobreposição de squadratinhos', blocoSobreposicao(d.sobreposicao, cor))}
        ${seccao('Ganhos diários', blocoGanhos(d.ganhos_diarios))}
        ${seccao('Squadratinhos', blocoGeo(d.geo || {}, estado.soDisputadas, estado.sort))}

        <p class="perfil-nota">
          Só <b>squadratinhos</b> (zoom 17, ~201 m): na grelha dos squadrats os quadrados
          são grandes demais para a comparação dizer alguma coisa. <b>Capturados</b> pelo atleta,
          <b>Total</b> da divisão (o mesmo para toda a gente, partilhado com o
          <a href="../index.html">mapa detalhado</a>). <b>Posição</b> = ranking por squares
          capturados dentro da divisão. <b class="mg-neg">Subir</b> = squares que
          faltam para passar a posição de cima; <b class="mg-pos">Folga</b> = quanto
          está à frente da posição de baixo. Clica num cabeçalho para ordenar.
          Dados actualizados 6×/dia.
        </p>`;

      alvo.querySelectorAll('.perfil-tabela.geo th[data-sort]').forEach(th => {
        th.onclick = () => {
          const k = th.dataset.sort;
          if (estado.sort.k === k) {
            estado.sort.dir = estado.sort.dir === 'asc' ? 'desc' : 'asc';
          } else {
            // "mais é melhor" arranca em desc; divisão/posição/subir em asc
            estado.sort = { k, dir: ['captured', 'total', 'pct', 'folga'].includes(k) ? 'desc' : 'asc' };
          }
          desenhar();
        };
      });
      const filtro = alvo.querySelector('[data-geo-filtro]');
      if (filtro) filtro.onclick = () => {
        estado.soDisputadas = !estado.soDisputadas;
        desenhar();
      };
    }
    desenhar();
  }

  async function renderPerfil() {
    const slug = alvo.dataset.slug;
    let dados;
    try {
      const r = await fetch(DATA_ATLETAS + encodeURIComponent(slug) + '.json', CACHE_BUST);
      if (!r.ok) throw new Error(r.status);
      dados = await r.json();
    } catch (e) {
      alvo.innerHTML = `<p class="perfil-topo"><a href="index.html">← perfis</a></p>
        <p class="perfil-estado perfil-erro">Não consegui carregar o perfil (${esc(e.message)}).
        Talvez o build ainda não tenha corrido para este atleta.</p>`;
      return;
    }
    const cores = await carregarCores();
    document.title = `${dados.nome} — Squadrats Club`;
    pintar(dados, cores[dados.nome]);
  }

  if (alvo && alvo.dataset.slug) renderPerfil();
  else if (INDICE) renderIndice();
})();
