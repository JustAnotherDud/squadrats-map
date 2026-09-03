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
  function pctTxt(p) { return p == null ? '' : ` <span class="pct">${p.toFixed(1)}%</span>`; }

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

  // lista geográfica com "mostrar todas" quando é longa
  const LIMITE = 12;
  function tabelaGeo(id, linhas) {
    if (!linhas.length) return '<p class="perfil-vazio">Sem squares nesta divisão.</p>';
    const linha = r => {
      const nome = r.cc === r.nome ? paisNome(r.cc) : esc(r.nome);
      return `<tr>
        <td><span class="nome">${flag(r.cc)}<span>${nome}</span></span></td>
        <td class="n">${nfmt(r.captured)}${pctTxt(r.pct)}</td>
      </tr>`;
    };
    const visiveis = linhas.slice(0, LIMITE).map(linha).join('');
    const resto = linhas.slice(LIMITE).map(linha).join('');
    const maisBtn = resto
      ? `<button class="perfil-toggle" data-mais="${id}">mostrar todas (${linhas.length})</button>`
      : '';
    return `${maisBtn}<div class="perfil-scroll"><table class="perfil-tabela">
      <thead><tr><th>Divisão</th><th>Squares</th></tr></thead>
      <tbody>${visiveis}</tbody>
      <tbody hidden id="geo-${id}-resto">${resto}</tbody>
    </table></div>`;
  }

  function blocoGeo(geo) {
    return NIVEL_ORDEM.map(nivel => `
      <div class="perfil-sub">${esc(NIVEL_NOME[nivel])}</div>
      ${tabelaGeo(nivel, geo[nivel] || [])}
    `).join('');
  }

  function blocoRanking(ranking, soDisputadas) {
    let linhas = ranking || [];
    if (soDisputadas) linhas = linhas.filter(r => r.disputada);
    if (!linhas.length) {
      return `<button class="perfil-toggle${soDisputadas ? ' on' : ''}" data-rank-filtro>Só disputadas (2+)</button>
        <p class="perfil-vazio">Nenhuma região ${soDisputadas ? 'disputada' : 'registada'}.</p>`;
    }
    const porNivel = {};
    linhas.forEach(r => { (porNivel[r.nivel] = porNivel[r.nivel] || []).push(r); });
    const corpo = NIVEL_ORDEM.filter(n => porNivel[n]).map(nivel => {
      const rows = porNivel[nivel].map(r => {
        const cls = r.posicao <= 3 ? ` p${r.posicao}` : '';
        const nome = r.cc === r.nome ? paisNome(r.cc) : esc(r.nome);
        return `<tr>
          <td><span class="nome">${flag(r.cc)}<span>${nome}</span></span></td>
          <td class="n"><span class="perfil-pos${cls}">${r.posicao}º</span>
            <span class="perfil-pos"> de ${r.de}</span></td>
          <td class="n">${nfmt(r.captured)}</td>
        </tr>`;
      }).join('');
      return `<div class="perfil-sub">${esc(NIVEL_NOME[nivel])}</div>
        <div class="perfil-scroll"><table class="perfil-tabela">
          <thead><tr><th>Região</th><th>Posição</th><th>Squares</th></tr></thead>
          <tbody>${rows}</tbody>
        </table></div>`;
    }).join('');
    return `<button class="perfil-toggle${soDisputadas ? ' on' : ''}" data-rank-filtro>Só disputadas (2+)</button>${corpo}`;
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
    let estado = { rankSoDisputadas: true };

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
        ${seccao('Onde anda (squadratinhos)', blocoGeo(d.geo || {}))}
        ${seccao('Posição por região', blocoRanking(d.ranking, estado.rankSoDisputadas))}

        <p class="perfil-nota">
          O detalhe geográfico e a sobreposição são só de <b>squadratinhos</b> (zoom 17, ~201 m):
          na grelha dos squadrats os quadrados são grandes demais para a comparação dizer
          alguma coisa. As percentagens usam o total da divisão (o mesmo para toda a gente,
          partilhado com o <a href="../index.html">mapa detalhado</a>). A "posição por região"
          é o ranking por squares capturados dentro de cada divisão, não por percentagem.
          Dados actualizados 6×/dia pelo mesmo processo que gera o mapa.
        </p>`;

      alvo.querySelectorAll('[data-mais]').forEach(b => {
        b.onclick = () => {
          const resto = document.getElementById('geo-' + b.dataset.mais + '-resto');
          if (resto) { resto.hidden = false; b.remove(); }
        };
      });
      const filtro = alvo.querySelector('[data-rank-filtro]');
      if (filtro) filtro.onclick = () => {
        estado.rankSoDisputadas = !estado.rankSoDisputadas;
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
