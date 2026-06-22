from PIL import Image

base = Image.open('logo/icon-512-blue.png').convert('RGBA')  # squircle, esquinas transparentes
BLUE = (45, 91, 255, 255)

# --- iconos "any" (mantienen la forma squircle con esquinas transparentes) ---
base.save('icon-512.png')
base.resize((192, 192), Image.LANCZOS).save('icon-192.png')

# --- maskable: azul a sangre (cuadrado lleno) + contenido al 92% para la zona segura ---
def maskable(size):
    canvas = Image.new('RGBA', (size, size), BLUE)
    s = int(size * 0.92)
    content = base.resize((s, s), Image.LANCZOS)
    off = (size - s) // 2
    canvas.alpha_composite(content, (off, off))
    return canvas

maskable(512).save('icon-512-maskable.png')
maskable(192).save('icon-192-maskable.png')

print('OK: icon-192/512 (any) + icon-192/512-maskable')
