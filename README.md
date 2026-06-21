# Tu Repo

App comunitaria de información local en tiempo real para **Venezuela**: la gente reporta el
estatus de servicios (luz, agua, gasolina, vías), precios/ofertas, fotos y comentarios de su
zona. Todo el contenido lo genera la comunidad. En vivo en **https://turepo.com**.

## Stack

- **Frontend:** una sola página (`index.html`) — PWA, sin framework ni build. HTML + CSS + JS
  vanilla. Tema claro/oscuro elegible.
- **Hosting:** GitHub → **Vercel** (deploy automático en cada push a `main`).
- **Backend:** **Supabase** (PostgreSQL + Auth + Storage). La app habla directo con Supabase
  desde el navegador con la **anon key** (pública por diseño); la seguridad real está en
  **RLS + funciones RPC** (ver `db/`).
- **Tareas programadas:** GitHub Actions (Python) disparadas por **cron-job.org** (el cron
  nativo de GitHub es poco fiable). Ver más abajo.
- **App Android:** TWA (Trusted Web Activity) empaquetada con Bubblewrap (proyecto fuera de
  este repo, en `~/turepo-android`); carga turepo.com adentro.

## Estructura del repo

```
index.html              La app entera (UI + lógica). Es el corazón del proyecto.
manifest.json           Manifest PWA.
sw.js                   Service worker.
icon-*.png, og.jpg      Íconos y open-graph.
.well-known/            assetlinks.json (verificación del TWA con Play).
privacidad/             Política de privacidad (turepo.com/privacidad).
terminos/               Términos de uso (turepo.com/terminos).
dmca/                   Política de derechos de autor (turepo.com/dmca).
eliminar-cuenta/        Página para solicitar borrado de cuenta.
db/                     Esquema SQL versionado de Supabase (ver db/README.md).
scripts/                Scripts Python de las tareas programadas.
.github/workflows/      Workflows que corren esos scripts.
vercel.json             Config de Vercel.
```

## Modelo de datos (resumen — detalle en `db/schema.sql`)

Tablas principales en `public`:
- **reportes** — reportes de la comunidad (tipo, zona, estado, precio, lat/lng, votos, autor…).
- **fotos** — fotos subidas (estado pendiente/aprobada; con moderación).
- **comentarios** — comentarios sobre reportes o fotos.
- **perfiles** — 1 fila por usuario (username, puntos, es_admin, posts_ilimitados…). Se crea
  por trigger al registrarse.
- **lugares** — diccionario de lugares mencionados (autocompletado).
- **noticias** — titulares RSS agregados.
- **tasa_bcv / tasa_binance** — tasa del dólar (1 fila c/u, id=1).
- **rate_limit** — registro para anti-spam (se autolimpia).

Vistas **`reportes_activos`** y **`fotos_activas`**: filtran el contenido "activo" de las
últimas 12 horas (es lo único que la app muestra). Lo más viejo lo borra el script de limpieza.

Toda mutación sensible va por **funciones RPC `SECURITY DEFINER`** (votar, comentar, borrar,
moderar, puntos, etc.), que validan `auth.uid()`/`es_admin` por dentro. El cliente nunca
escribe directo salvo insertar reportes/fotos, donde un trigger fija el `autor` real.

## Tareas programadas (GitHub Actions + cron-job.org)

| Script | Workflow | Qué hace | Frecuencia |
|---|---|---|---|
| `actualizar_bcv.py` | `bcv.yml` | Tasa BCV desde bcv.org.ve → `tasa_bcv` | ~3h |
| `actualizar_binance.py` | `binance.yml` | Tasa Binance P2P → `tasa_binance` | ~30min |
| `actualizar_noticias.py` | `noticias.yml` | RSS → `noticias` (dedup, limpia >30d) | ~2h |
| `moderar_fotos.py` | `moderar_fotos.yml` | Modera fotos pendientes con IA (Groq) | ~5min |
| `limpiar_viejos.py` | `limpiar.yml` | Borra reportes/fotos/comentarios >2 días (+ archivos) | diario |

Todas usan los secrets `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` (la `service_role` solo
vive en GitHub Secrets, nunca en el código). El disparo fiable lo hace **cron-job.org** con un
token fino `turepo-cron` que llama a la API `workflow_dispatch` de GitHub.

## Decisiones de diseño (por qué es así)

- **Una sola página (`index.html`):** simplicidad y carga rápida; un dev solo lo mantiene mejor.
- **Mapa sin GPS:** el usuario marca el punto (mira de centro + buscador Nominatim); la zona se
  autocompleta por geocoding inverso. Privacidad y simplicidad.
- **Email sintético `usuario@users.eldato.app`:** el login usuario/clave usa un email interno
  (nombre heredado del proyecto original "el dato"). No cambiar sin migrar cuentas existentes.
- **Pipeline propio del dólar:** las APIs públicas no daban bien el BCV, así que se lee de
  bcv.org.ve y Binance P2P con scripts propios.
- **Moderación con IA permisiva:** aprueba por defecto; solo rechaza lo claramente prohibido.

## Correr en local

Servir la carpeta como estática y abrir la **raíz** (no `/index.html`):

```bash
python -m http.server 5050
# luego abrir http://localhost:5050/
```

La anon key está en `index.html`, así que en local se cargan datos reales de Supabase.

## Deploy

Push a `main` → Vercel despliega solo. Para revertir un deploy, usar el panel de Vercel
(Deployments → un deploy previo → "Promote to Production").

**Dominio canónico:** `turepo.com` sirve 200 directo; `www` redirige a turepo.com (no
invertir: rompería la verificación del TWA de Android).

## Editar `index.html`

Es UTF-8 con CRLF. Al tocar el JS embebido, validar extrayendo los `<script>` sin `src` y
corriendo `node --check` en cada bloque antes de dar por hecho el cambio.
