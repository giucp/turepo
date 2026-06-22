from PIL import Image, ImageDraw

src = Image.open('icon-512.png.bak' if False else 'logo/_orig.png') if False else Image.open('icon-512-blue.png') if False else None
# usamos el ORIGINAL (dark) como fuente; lo guardamos antes
src = Image.open('logo/_orig-512.png').convert('RGBA')
W, H = src.size
px = src.load()

WHITEBG = (255, 255, 255)
BLUE = (45, 91, 255)
GREEN = (46, 207, 107)

def lum(r, g, b):
    return 0.299 * r + 0.587 * g + 0.114 * b

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

out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
op = out.load()
for y in range(H):
    for x in range(W):
        r, g, b, a = px[x, y]
        if a < 8:
            op[x, y] = (0, 0, 0, 0); continue
        if g > 90 and (g - (r + b) // 2) > 20:
            op[x, y] = (WHITEBG[0], WHITEBG[1], WHITEBG[2], a); continue
        L = lum(r, g, b)
        t = (L - 90) / (200 - 90)
        t = 0.0 if t < 0 else (1.0 if t > 1 else t)
        rr = int(WHITEBG[0] + (BLUE[0] - WHITEBG[0]) * t)
        gg = int(WHITEBG[1] + (BLUE[1] - WHITEBG[1]) * t)
        bb = int(WHITEBG[2] + (BLUE[2] - WHITEBG[2]) * t)
        op[x, y] = (rr, gg, bb, a)

d = ImageDraw.Draw(out)
rad = grad + 3
d.ellipse([gcx - rad, gcy - rad, gcx + rad, gcy + rad], fill=GREEN + (255,))
out.save('logo/turepo-blanco-512.png')
print('respaldo blanco guardado: logo/turepo-blanco-512.png')
