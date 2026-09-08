"""Ícones da PWA + favicon, a partir de uma forma única (folha de ácer sobre
quadrado roxo). Roxo = #663399, a cor da marca Squadrats (o logótipo deles é
fill='#639'); NÃO o roxo da Xeira (#9c46d8).

Contexto da folha: o projecto começou como folha de cálculo no Google Sheets
("folha do clube").

Desenha com Pillow (sem rasterizador de SVG na máquina). A mesma forma está
à mão em icon.svg, que serve de favicon vectorial. Re-executar depois de
mexer na forma:  py pipeline/gen_icons.py

Escreve na raiz do repo:
  icon.svg                  vector (favicon + manifest)
  icon-192.png              maskable=any, cantos arredondados, fundo transparente
  icon-512.png              idem
  icon-maskable-512.png     roxo até à borda, folha dentro da zona segura
  apple-touch-icon.png      180x180, sem transparência (iOS arredonda sozinho)
  favicon-16.png / -32.png  + favicon.ico (16+32)
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(HERE)

ROXO = (0x66, 0x33, 0x99, 255)   # #663399 rebeccapurple, marca Squadrats
FOLHA = (0xff, 0xff, 0xff, 255)  # branco

# Folha de ácer estilizada (5 lóbulos + pecíolo). Metade direita, centro x=100,
# caixa 0..200, y para baixo: do bico central, no sentido dos ponteiros, pelo
# lado direito até ao pé; a esquerda é o espelho. Sinus (entalhes) fundos e
# perto do centro; lóbulo central o mais comprido.
_META = [
    (100, 20),                 # bico do lóbulo central
    (126, 60),                 # ombro direito do central (largo)
    (130, 78),                 # sinus central|superior (raso)
    (144, 66),                 # ombro do lóbulo superior
    (160, 44),                 # bico do lóbulo superior
    (164, 78),                 # ombro inferior do superior
    (150, 102),                # sinus superior|lateral (raso)
    (170, 98),                 # ombro do lóbulo lateral
    (196, 110),                # bico do lóbulo lateral (ponto mais largo)
    (164, 130),                # ombro inferior do lateral
    (140, 134),                # sinus lateral|inferior
    (152, 150),                # ombro do lóbulo inferior
    (146, 178),                # bico do lóbulo inferior
    (118, 156),                # sinus inferior|pecíolo
    (108, 170),                # a lâmina encontra o pecíolo
    (108, 202),                # base do pecíolo, lado direito
    (100, 202),                # base do pecíolo, no eixo
]
MAPLE = _META + [(200 - x, y) for x, y in reversed(_META[1:-1])]


def _folha_pontos(tam, margem):
    """MAPLE reescalado para um quadrado `tam`, com `margem` (fracção) livre."""
    util = tam * (1 - 2 * margem)
    off = tam * margem
    return [(off + x / 200 * util, off + y / 200 * util) for x, y in MAPLE]


def _rrect(draw, box, raio, fill):
    draw.rounded_rectangle(box, radius=raio, fill=fill)


def _png(caminho, tam, *, fundo, margem, raio_frac=None, ss=4, rgb=False):
    """Desenha num canvas ss vezes maior e reduz (anti-alias). `rgb`: grava
    sem canal alfa (apple-touch-icon, que o iOS compõe sobre preto)."""
    big = tam * ss
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if fundo == "rrect":
        _rrect(d, [0, 0, big - 1, big - 1], big * (raio_frac or 0.22), ROXO)
    elif fundo == "cheio":
        d.rectangle([0, 0, big, big], fill=ROXO)
    d.polygon(_folha_pontos(big, margem), fill=FOLHA)
    im = im.resize((tam, tam), Image.LANCZOS)
    if rgb:
        fundo_rgb = Image.new("RGB", im.size, ROXO[:3])
        fundo_rgb.paste(im, mask=im.split()[3])
        im = fundo_rgb
    im.save(caminho)
    print("escrito:", os.path.relpath(caminho, RAIZ))


def _svg(caminho):
    m = 0.13                       # mesma margem que icon-192/512.png
    util, off = 512 * (1 - 2 * m), 512 * m
    pts = " ".join(f"{off + x/200*util:.1f},{off + y/200*util:.1f}" for x, y in MAPLE)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" '
        'viewBox="0 0 512 512">\n'
        '  <rect width="512" height="512" rx="112" fill="#663399"/>\n'
        f'  <polygon points="{pts}" fill="#fff"/>\n'
        '</svg>\n'
    )
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    print("escrito:", os.path.relpath(caminho, RAIZ))


def main():
    _svg(os.path.join(RAIZ, "icon.svg"))
    # ícone normal: quadrado arredondado, folha com margem folgada
    _png(os.path.join(RAIZ, "icon-192.png"), 192, fundo="rrect", margem=0.13)
    _png(os.path.join(RAIZ, "icon-512.png"), 512, fundo="rrect", margem=0.13)
    # maskable: roxo até à borda; folha dentro de ~66% (Android corta a ~80%)
    _png(os.path.join(RAIZ, "icon-maskable-512.png"), 512, fundo="cheio", margem=0.20)
    # iOS: 180x180, sem transparência (o SO arredonda)
    _png(os.path.join(RAIZ, "apple-touch-icon.png"), 180, fundo="cheio", margem=0.18, rgb=True)
    # favicon
    _png(os.path.join(RAIZ, "favicon-32.png"), 32, fundo="rrect", margem=0.12, raio_frac=0.18)
    _png(os.path.join(RAIZ, "favicon-16.png"), 16, fundo="rrect", margem=0.10, raio_frac=0.16)
    ico16 = Image.open(os.path.join(RAIZ, "favicon-16.png"))
    ico32 = Image.open(os.path.join(RAIZ, "favicon-32.png"))
    ico32.save(os.path.join(RAIZ, "favicon.ico"), sizes=[(16, 16), (32, 32)],
               append_images=[ico16])
    print("escrito: favicon.ico")


if __name__ == "__main__":
    main()
