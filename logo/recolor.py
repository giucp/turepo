from PIL import Image, ImageDraw

src = Image.open('icon-512.png').convert('RGBA')
W, H = src.size
px = src.load()

BLUE = (45, 91, 255)
WHITE = (255, 255, 255)
GREEN = (46, 207, 107)

def lum(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b

# --- detectar el punto verde (fuerte) para centro y radio ---
sx = sy = n = 0
minx = W; miny = H; maxx = maxy = 0
for y in range(H):
    for x in range(W):
        r, g, b, a = px[x, y]
        if a > 150 and g > 120 and (g - (r + b) // 2) > 45:
            sx += x; sy += y; n += 1
            minx = min(minx, x); maxx = max(maxx, x)
            miny = min(miny, y); maxy = max(maxy, y)
gcx, gcy = sx // n, sy // n
grad = (max(maxx - minx, maxy - miny) // 2)
print('punto verde centro', gcx, gcy, 'radio', grad)

out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
op = out.load()
for y in range(H):
    for x in range(W):
        r, g, b, a = px[x, y]
        if a < 8:
            op[x, y] = (0, 0, 0, 0); continue
        # verde (punto + halo) -> tratar como fondo (azul)
        if g > 90 and (g - (r + b) // 2) > 20:
            op[x, y] = (BLUE[0], BLUE[1], BLUE[2], a); continue
        L = lum(r, g, b)
        t = (L - 90) / (200 - 90)
        t = 0.0 if t < 0 else (1.0 if t > 1 else t)
        rr = int(BLUE[0] + (WHITE[0] - BLUE[0]) * t)
        gg = int(BLUE[1] + (WHITE[1] - BLUE[1]) * t)
        bb = int(BLUE[2] + (WHITE[2] - BLUE[2]) * t)
        op[x, y] = (rr, gg, bb, a)

# punto verde nuevo, plano, sin borde
d = ImageDraw.Draw(out)
rad = grad + 3
d.ellipse([gcx - rad, gcy - rad, gcx + rad, gcy + rad], fill=GREEN + (255,))

out.save('logo/icon-512-blue.png')
print('guardado logo/icon-512-blue.png')
