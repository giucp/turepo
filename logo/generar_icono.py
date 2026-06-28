"""Genera el icono de Tu Repo NITIDO replicando EXACTO el logo actual.
Traza (vectoriza) el 'tr' del icon-512.png existente con potrace y lo
redibuja a alta resolucion con las medidas y colores exactos medidos:
  - azul  #2D5BFF (45,91,255)
  - verde #2ECF6B (46,207,107)
  - 'tr'  en su posicion nativa (bbox medido del logo actual)
  - punto verde centro (411,183) radio 30
  - esquina squircle radio 116 (en espacio 512)
Render con supersampling 4x -> bordes limpios.
"""
import numpy as np
import potrace
from PIL import Image, ImageDraw

BLUE  = (45, 91, 255, 255)
WHITE = (255, 255, 255, 255)
GREEN = (46, 207, 107, 255)
SS = 4                       # supersampling
SRC = "icon-512.png"         # logo actual = fuente de verdad (512 espacio)
DOT_C = (411.0, 183.0)       # centro punto verde (medido)
DOT_R = 30.0                 # radio punto verde (medido)
CORNER = 116.0               # radio esquina squircle (medido)
GROUP_C = (279.0, 256.0)     # centro del grupo tr+punto (para maskable)

def _trace_letters(bezier_steps=24):
    """Devuelve la lista de poligonos (la 't' y la 'r') en espacio 512."""
    import os
    base = os.path.join(os.path.dirname(__file__), "..", SRC)
    a = np.asarray(Image.open(base).convert("RGBA"))
    r, g, b, al = (a[..., 0].astype(int), a[..., 1].astype(int),
                   a[..., 2].astype(int), a[..., 3])
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    white = (al > 100) & (lum > 170) & (abs(r - g) < 40) & (abs(g - b) < 40)
    path = potrace.Bitmap(white).trace(turdsize=2, opttolerance=0.2)
    P = lambda p: (p.x, p.y)
    polys = []
    for curve in path:
        pts = [P(curve.start_point)]
        for s in curve.segments:
            if s.is_corner:
                pts.append(P(s.c)); pts.append(P(s.end_point))
            else:
                x0, y0 = pts[-1]
                (x1, y1), (x2, y2), (x3, y3) = P(s.c1), P(s.c2), P(s.end_point)
                for i in range(1, bezier_steps + 1):
                    t = i / bezier_steps; mt = 1 - t
                    x = mt**3*x0 + 3*mt**2*t*x1 + 3*mt*t**2*x2 + t**3*x3
                    y = mt**3*y0 + 3*mt**2*t*y1 + 3*mt*t**2*y2 + t**3*y3
                    pts.append((x, y))
        xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
        # descartar el marco espurio de todo el lienzo
        if max(xs) - min(xs) > 500 and max(ys) - min(ys) > 500:
            continue
        polys.append(pts)
    return polys

_LETTERS = None

def make_icon(size, maskable=False):
    global _LETTERS
    if _LETTERS is None:
        _LETTERS = _trace_letters()
    S = 512 * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if maskable:
        d.rectangle([0, 0, S, S], fill=BLUE)   # full-bleed: identico al "any", solo el fondo a sangre
        cs = 1.0
        def tf(p):
            return (p[0] * SS, p[1] * SS)        # posiciones nativas: mismo tamano y lugar que el any
        dr = DOT_R * SS
    else:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=CORNER * SS, fill=BLUE)
        cs = 1.0
        def tf(p):
            return (p[0] * SS, p[1] * SS)
        dr = DOT_R * SS

    for poly in _LETTERS:
        d.polygon([tf(q) for q in poly], fill=WHITE)

    dc = tf(DOT_C)
    d.ellipse([dc[0] - dr, dc[1] - dr, dc[0] + dr, dc[1] + dr], fill=GREEN)

    return img.resize((size, size), Image.LANCZOS)

if __name__ == "__main__":
    for size in (1024, 512, 192):
        make_icon(size, maskable=False).save(f"out-icon-{size}.png")
        print("out-icon", size)
    for size in (512, 192):
        make_icon(size, maskable=True).save(f"out-icon-{size}-maskable.png")
        print("out-icon", size, "maskable")
