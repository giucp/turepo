"""og.jpg brutalista: logo + 'Tu Repo' + frase en TARJETA + chips CON iconos.
Los iconos se rasterizan con resvg (mismos SVG que usa la app).
"""
from PIL import Image, ImageDraw, ImageFont
import resvg_py

W, H = 1200, 630
BG = (243, 241, 234)
INK = (17, 17, 17)
BLUE = (45, 91, 255)
GREY = (74, 74, 74)

img = Image.new('RGB', (W, H), BG)
d = ImageDraw.Draw(img)

# marco brutalista
bw = 14
d.rectangle([bw // 2, bw // 2, W - bw // 2 - 1, H - bw // 2 - 1], outline=INK, width=bw)

# logo azul (icono crisp)
logo = Image.open('icon-512.png').convert('RGBA').resize((300, 300), Image.LANCZOS)
img.paste(logo, (92, 162), logo)

F = 'C:/Windows/Fonts/'
black = ImageFont.truetype(F + 'ariblk.ttf', 118)
bold = ImageFont.truetype(F + 'arialbd.ttf', 40)
small = ImageFont.truetype(F + 'arialbd.ttf', 30)

x = 446
d.text((x, 150), 'Tu Repo', font=black, fill=INK)

# --- frase en tarjeta brutalista (estilo .post: borde negro + sombra dura) ---
def rrect(draw, box, r, **kw):
    draw.rounded_rectangle(box, radius=r, **kw)

line1, line2 = 'Lo que pasa en tu ciudad,', 'reportado por su gente.'
pad_x, pad_y, lh, radius, bdr, shadow = 30, 26, 50, 20, 5, 7
tw = max(d.textlength(line1, font=bold), d.textlength(line2, font=bold))
card_w = int(tw + pad_x * 2)
card_h = pad_y * 2 + lh * 2 - 8
cx0, cy0 = x, 300
# sombra dura
rrect(d, [cx0 + shadow, cy0 + shadow, cx0 + card_w + shadow, cy0 + card_h + shadow], radius, fill=INK)
# tarjeta blanca con borde negro
rrect(d, [cx0, cy0, cx0 + card_w, cy0 + card_h], radius, fill=(255, 255, 255), outline=INK, width=bdr)
d.text((cx0 + pad_x, cy0 + pad_y), line1, font=bold, fill=INK)
d.text((cx0 + pad_x, cy0 + pad_y + lh), line2, font=bold, fill=GREY)

# --- chips de categoria CON icono (estilo .post .pic) ---
INNER = {
 'bolt': '<path d="M13 2 4.1 12.5h6L9.9 22 19 11.5h-6L13 2z"/>',
 'pump': '<path d="M5 21V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v16"/><path d="M3 21h14"/><path d="M15 9h2.5a2 2 0 0 1 2 2v5a1.5 1.5 0 0 0 3 0V9.5L19 7"/>',
 'traffic': '<rect x="9" y="2" width="6" height="20" rx="2.4"/><circle cx="12" cy="6.4" r="1.25" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.25" fill="currentColor" stroke="none"/><circle cx="12" cy="17.6" r="1.25" fill="currentColor" stroke="none"/>',
 'alert': '<path d="M10.3 3.3 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.3a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
 'cart': '<circle cx="9" cy="21" r="1.6"/><circle cx="19" cy="21" r="1.6"/><path d="M1.5 2.5h3l3.1 13.4a2 2 0 0 0 2 1.6h8.9a2 2 0 0 0 2-1.6L22.5 7H6"/>',
 'camera': '<path d="M14.5 4h-5L7.8 6.2H4a2 2 0 0 0-2 2V18a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8.2a2 2 0 0 0-2-2h-3.8L14.5 4z"/><circle cx="12" cy="13" r="3.6"/>',
}

def icon_png(name, px, color='#111'):
    inner = INNER[name].replace('currentColor', color)
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 24 24" fill="none" stroke="%s" stroke-width="2" '
           'stroke-linecap="round" stroke-linejoin="round">%s</svg>' % (px*3, px*3, color, inner))
    raw = bytes(resvg_py.svg_to_bytes(svg_string=svg))
    im = Image.open(__import__('io').BytesIO(raw)).convert('RGBA')
    return im.resize((px, px), Image.LANCZOS)

chips = [((255,210,63),'bolt'), ((156,198,255),'pump'), ((255,178,77),'traffic'),
         ((255,138,138),'alert'), ((108,229,176),'cart'), ((255,158,207),'camera')]
sz, gap, ic = 66, 16, 38
cx, cy = x, 490
for col, name in chips:
    rrect(d, [cx, cy, cx + sz, cy + sz], 15, fill=col, outline=INK, width=4)
    ico = icon_png(name, ic)
    img.paste(ico, (cx + (sz - ic)//2, cy + (sz - ic)//2), ico)
    cx += sz + gap

d.text((x + sz * 6 + gap * 5 + 26, 514), 'turepo.com', font=small, fill=BLUE)

img.save('og.jpg', 'JPEG', quality=92)
print('og.jpg generado', img.size)
