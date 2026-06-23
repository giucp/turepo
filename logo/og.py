from PIL import Image, ImageDraw, ImageFont

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

# logo azul
logo = Image.open('icon-512.png').convert('RGBA').resize((300, 300), Image.LANCZOS)
img.paste(logo, (92, 162), logo)

F = 'C:/Windows/Fonts/'
black = ImageFont.truetype(F + 'ariblk.ttf', 118)
bold = ImageFont.truetype(F + 'arialbd.ttf', 43)
small = ImageFont.truetype(F + 'arialbd.ttf', 30)

x = 446
d.text((x, 168), 'Tu Repo', font=black, fill=INK)
d.text((x, 318), 'Lo que pasa en tu ciudad,', font=bold, fill=GREY)
d.text((x, 370), 'reportado por su gente.', font=bold, fill=GREY)

# chips de color (las 6 categorias)
cols = [(255, 210, 63), (156, 198, 255), (255, 178, 77), (255, 138, 138), (108, 229, 176), (255, 158, 207)]
cx, cy, sz, gap = x, 448, 50, 13
for c in cols:
    d.rounded_rectangle([cx, cy, cx + sz, cy + sz], radius=12, fill=c, outline=INK, width=4)
    cx += sz + gap

d.text((x, 532), 'turepo.com', font=small, fill=BLUE)

img.save('og.jpg', 'JPEG', quality=90)
print('og.jpg generado', img.size)
