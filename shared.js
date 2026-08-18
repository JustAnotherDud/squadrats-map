// Vocabulário comum ao index.html (vista pessoal) e ao club.html (vista do
// clube). SÓ constantes e matemática pura: zero DOM, zero estado, zero Leaflet.
//
// Porquê existir (2026-08-18): as duas páginas partilham o vocabulário — os
// mesmos 5 países, as mesmas bandeiras, os mesmos nomes de nível, a mesma
// grelha XYZ — mas nada do resto. Enquanto isto estava duplicado, cada mudança
// de vocabulário tinha de ser feita duas vezes e uma delas esquecia-se: já
// aconteceu com o renomear de "Nível 1/2/3" para "País/Região/Zona" e com o
// círculo amarelo da bandeira portuguesa.
//
// O que NÃO deve entrar aqui: render, estado, handlers, nada de Leaflet. As
// duas páginas divergem em tudo isso de propósito — o club.html desenha em
// canvas (L.GridLayer, bitmask de vários atletas), o index.html desenha
// rectângulo a rectângulo com choropleth, troféus e sugestões. Fundir as
// páginas foi considerado e recusado: zero reutilização no render, modelos de
// estado incompatíveis, e passava a acoplar duas vistas que se querem
// independentes.

// Códigos de país por ordem de apresentação. Acrescentar um país é acrescentar
// aqui + a bandeira em BANDEIRA_PATHS; o resto (toggles, tabelas, pills) lê
// destas tabelas em vez de ter a lista escrita à mão.
const PAIS_NOME = {
  PT: 'Portugal',
  ES: 'Espanha',
  AD: 'Andorra',
  DE: 'Alemanha',
  MA: 'Marrocos',
};

// Interior do <svg> de cada bandeira, sempre no mesmo viewBox 15x11 — o tamanho
// final é escolhido por quem chama (o index usa 15x11, o club 13x10).
// SVG e não emoji (🇵🇹/🇪🇸) de propósito: o emoji depende da fonte do sistema e
// em vários ambientes (Linux/Chrome headless, algumas versões mobile) cai para
// as letras "PT"/"ES". Simplificadas, sem brasão — servem para identificar o
// país num relance, não para serem exactas.
const BANDEIRA_PATHS = {
  PT: '<rect width="15" height="11" fill="#da020e"/><rect width="6" height="11" fill="#046a38"/><circle cx="6" cy="5.5" r="2" fill="#ffd400"/>',
  ES: '<rect width="15" height="11" fill="#aa151b"/><rect y="2.75" width="15" height="5.5" fill="#f1bf00"/>',
  AD: '<rect width="15" height="11" fill="#fcdd09"/><rect width="5" height="11" fill="#0018a8"/><rect x="10" width="5" height="11" fill="#d50032"/>',
  DE: '<rect width="15" height="3.67" y="0" fill="#000000"/><rect width="15" height="3.67" y="3.67" fill="#dd0000"/><rect width="15" height="3.67" y="7.33" fill="#ffce00"/>',
  MA: '<rect width="15" height="11" fill="#c1272d"/><polygon points="7.5,2.5 8.2,4.53 10.35,4.57 8.64,5.87 9.26,7.93 7.5,6.7 5.74,7.93 6.36,5.87 4.65,4.57 6.8,4.53" fill="#006233"/>',
};

function bandeiraSvg(cc, largura, altura) {
  const inner = BANDEIRA_PATHS[cc];
  if (!inner) return '';
  return `<svg width="${largura}" height="${altura}" viewBox="0 0 15 11" class="bandeira">${inner}</svg>`;
}

// Tabela de bandeiras já dimensionada, para quem só quer indexar por código.
function bandeiras(largura, altura) {
  const t = {};
  for (const cc of Object.keys(BANDEIRA_PATHS)) t[cc] = bandeiraSvg(cc, largura, altura);
  return t;
}

// Nomes dos três níveis geográficos. Antes eram "Nível 1/2/3" (renomeado
// 2026-08-16): "distrito/concelho" só está certo em Portugal — Espanha tem
// província/município, a Alemanha Land/Gemeinde, Marrocos região/cercle.
// "País/Região/Zona" é neutro e funciona nos cinco.
const NIVEL_LABEL = { pais: 'País', regiao: 'Região', zona: 'Zona' };

// lat/lng -> tile x/y da grelha XYZ, para um dado zoom. Mesma convenção do
// pipeline (pipeline/kml_parse.py lonlat_to_tile) — se um dia divergirem, os
// squares desenhados deixam de bater com os capturados.
function lonlatParaTile(lat, lng, zoom) {
  const n = Math.pow(2, zoom);
  const rad = lat * Math.PI / 180;
  return [
    Math.floor((lng + 180) / 360 * n),
    Math.floor((1 - Math.asinh(Math.tan(rad)) / Math.PI) / 2 * n),
  ];
}

// canto noroeste de um tile -> [lat, lon]. Inverso do lonlatParaTile.
function tileNoroeste(x, y, z) {
  const n = Math.pow(2, z);
  return [
    Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n))) * 180 / Math.PI,
    x / n * 360 - 180,
  ];
}
