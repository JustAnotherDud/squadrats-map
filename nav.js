// Barra de navegação partilhada por todas as páginas do site (menos o mapa
// detalhado pessoal, que fica de fora da navegação de propósito).
//
// Injecta-se a si própria: cada página só precisa de <script src="nav.js">
// (ou "../nav.js" a partir de atletas/). Sem dependências.
//
// Páginas de mapa em ecrã cheio (club.html) põem <body data-nav="overlay">:
// a barra fica `position:fixed` e a página trata do offset do #map/#topbar.
// As outras usam `position:sticky` e não precisam de mais nada.
(function () {
  'use strict';

  var atSub = location.pathname.indexOf('/atletas/') !== -1;
  var P = atSub ? '../' : '';
  var file = (location.pathname.split('/').pop() || '').toLowerCase();

  var atual = 'hub';
  if (atSub) atual = 'perfis';
  else if (file === 'club.html') atual = 'clube';
  else if (file === 'historico.html') atual = 'historico';

  var DEST = [
    { id: 'clube', label: 'Clube', href: P + 'club.html' },
    { id: 'perfis', label: 'Perfis', href: P + 'atletas/' },
    { id: 'historico', label: 'Histórico', href: P + 'historico.html' },
  ];

  var CSS = [
    '#site-nav{position:sticky;top:0;z-index:3000;display:flex;align-items:center;',
    'gap:14px;padding:0 14px;height:38px;background:#12141a;',
    'border-bottom:1px solid #262b38;box-sizing:border-box;',
    'font:13px/1 -apple-system,"Segoe UI",Roboto,sans-serif}',
    '#site-nav.overlay{position:fixed;left:0;right:0}',
    '#site-nav .marca{font-weight:700;color:#9aa2b1;text-decoration:none;letter-spacing:.02em}',
    '#site-nav .marca:hover{color:#e7e9ee}',
    '#site-nav .marca[aria-current]{color:#fff}',
    '#site-nav .links{display:flex;gap:4px;margin-left:auto}',
    '#site-nav .links a{color:#9aa2b1;text-decoration:none;padding:6px 9px;border-radius:7px}',
    '#site-nav .links a:hover{color:#e7e9ee;background:#1b1f2b}',
    '#site-nav .links a[aria-current]{color:#fff;background:#3d7bf5}',
    '@media(max-width:480px){#site-nav{gap:8px;padding:0 10px}',
    '#site-nav .links{gap:2px}#site-nav .links a{padding:6px 7px;font-size:12px}}',
  ].join('');

  var links = DEST.map(function (d) {
    return '<a href="' + d.href + '"' + (d.id === atual ? ' aria-current="page"' : '') + '>' + d.label + '</a>';
  }).join('');
  var html =
    '<a class="marca" href="' + P + 'index.html"' + (atual === 'hub' ? ' aria-current="page"' : '') + '>Squadrats</a>' +
    '<span class="links">' + links + '</span>';

  function montar() {
    var st = document.createElement('style');
    st.textContent = CSS;
    document.head.appendChild(st);
    var nav = document.createElement('nav');
    nav.id = 'site-nav';
    if (document.body.dataset.nav === 'overlay') nav.className = 'overlay';
    nav.innerHTML = html;
    document.body.insertBefore(nav, document.body.firstChild);
  }
  if (document.body) montar();
  else document.addEventListener('DOMContentLoaded', montar);
})();
