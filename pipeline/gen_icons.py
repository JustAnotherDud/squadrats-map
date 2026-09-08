"""Ícones da PWA + favicon, a partir de uma forma única: a folha de ácer do
emoji 🍁 (silhueta do Twemoji, um path só, CC-BY 4.0) recolorida de laranja,
sobre um quadrado roxo #663399 (a cor da marca Squadrats; o logótipo deles é
fill='#639'), NÃO o roxo #9c46d8 da Xeira.

Contexto da folha: o projecto começou como folha de cálculo no Google Sheets
("folha do clube").

Rasteriza os SVG com PyMuPDF (não há rasterizador de sistema).
Re-executar:  py -m pip install pymupdf pillow  &&  py pipeline/gen_icons.py

Escreve na raiz do repo:
  icon.svg                  vector (favicon + manifest)
  icon-192.png              cantos arredondados, fundo transparente
  icon-512.png              idem
  icon-maskable-512.png     roxo até à borda, folha na zona segura
  apple-touch-icon.png      180x180, sem transparência (iOS arredonda sozinho)
  favicon-16.png / -32.png  + favicon.ico (16+32)
"""
import os

import pymupdf
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(HERE)

ROXO = "#663399"      # rebeccapurple, marca Squadrats
LARANJA = "#ef7722"   # laranja de Outono (não é cor de atleta)

# Silhueta da folha de ácer do Twemoji (assets/svg/1f341.svg), viewBox 36x36,
# um path só. https://github.com/jdecked/twemoji  (CC-BY 4.0)
FOLHA_D = (
    "M36 20.917c0-.688-2.895-.5-3.125-1s3.208-4.584 2.708-5.5-5.086 1.167-5.375"
    ".708c-.288-.458.292-3.5-.208-3.875s-5.25 4.916-5.917 4.292c-.666-.625 1.542"
    "-10.5 1.086-10.698-.456-.198-3.419 1.365-3.793 1.282C21.002 6.042 18.682 0 "
    "18 0s-3.002 6.042-3.376 6.125c-.374.083-3.337-1.48-3.793-1.282-.456.198 "
    "1.752 10.073 1.085 10.698C11.25 16.166 6.5 10.875 6 11.25s.08 3.417-.208 "
    "3.875c-.289.458-4.875-1.625-5.375-.708s2.939 5 2.708 5.5-3.125.312-3.125 "
    "1 8.438 5.235 9 5.771c.562.535-2.914 2.802-2.417 3.229.576.496 3.839-.83 "
    "10.417-.957V35c0 .553.448 1 1 1 .553 0 1-.447 1-1v-6.04c6.577.127 9.841 "
    "1.453 10.417.957.496-.428-2.979-2.694-2.417-3.229.562-.536 9-5.084 9-5.771z"
)
VB = 36


def _svg(tam, *, fundo, margem, rx=None):
    """SVG completo `tam`x`tam`: fundo (roxo arredondado ou cheio) + folha
    laranja centrada com `margem` (fracção) livre à volta."""
    esc = tam * (1 - 2 * margem) / VB      # escala da folha
    off = tam * margem
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{tam}" '
              f'height="{tam}" viewBox="0 0 {tam} {tam}">']
    if fundo == "rrect":
        partes.append(f'<rect width="{tam}" height="{tam}" rx="{rx or tam*0.22:.0f}" '
                      f'fill="{ROXO}"/>')
    elif fundo == "cheio":
        partes.append(f'<rect width="{tam}" height="{tam}" fill="{ROXO}"/>')
    partes.append(f'<path transform="translate({off:.1f} {off:.1f}) scale({esc:.4f})" '
                  f'fill="{LARANJA}" d="{FOLHA_D}"/>')
    partes.append('</svg>')
    return "\n".join(partes)


def _raster(tam, *, fundo, margem, rx=None, ss=4):
    """SVG -> PIL RGBA, renderizado a ss vezes o tamanho e reduzido (LANCZOS)."""
    svg = _svg(tam * ss, fundo=fundo, margem=margem, rx=rx and rx * ss)
    doc = pymupdf.open(stream=svg.encode("utf-8"), filetype="svg")
    pix = doc[0].get_pixmap(alpha=True)
    im = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
    if im.size != (tam * ss, tam * ss):
        im = im.resize((tam * ss, tam * ss), Image.LANCZOS)
    return im.resize((tam, tam), Image.LANCZOS)


def _png(nome, tam, *, fundo, margem, rx=None, rgb=False):
    im = _raster(tam, fundo=fundo, margem=margem, rx=rx)
    if rgb:
        base = Image.new("RGB", im.size, ROXO)
        base.paste(im, mask=im.split()[3])
        im = base
    caminho = os.path.join(RAIZ, nome)
    im.save(caminho)
    print("escrito:", nome)


def main():
    with open(os.path.join(RAIZ, "icon.svg"), "w", encoding="utf-8", newline="\n") as f:
        f.write(_svg(512, fundo="rrect", margem=0.14, rx=112) + "\n")
    print("escrito: icon.svg")

    _png("icon-192.png", 192, fundo="rrect", margem=0.14)
    _png("icon-512.png", 512, fundo="rrect", margem=0.14)
    _png("icon-maskable-512.png", 512, fundo="cheio", margem=0.26)
    _png("apple-touch-icon.png", 180, fundo="cheio", margem=0.16, rgb=True)
    _png("favicon-32.png", 32, fundo="rrect", margem=0.10, rx=6)
    _png("favicon-16.png", 16, fundo="rrect", margem=0.08, rx=3)

    ico16 = Image.open(os.path.join(RAIZ, "favicon-16.png"))
    ico32 = Image.open(os.path.join(RAIZ, "favicon-32.png"))
    ico32.save(os.path.join(RAIZ, "favicon.ico"), sizes=[(16, 16), (32, 32)],
               append_images=[ico16])
    print("escrito: favicon.ico")


if __name__ == "__main__":
    main()
