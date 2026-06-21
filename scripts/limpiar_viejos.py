import os
import sys
import datetime
import requests

# Limpia datos viejos para que las tablas no crezcan para siempre.
# La app solo muestra contenido "activo" (vistas de 12h); estas filas viejas
# ya no se ven y solo ocupan espacio. Las fotos además dejan archivos en Storage.
#
# Borra (más viejos que RETENTION_DAYS, por created_at):
#   - reportes  (filas)
#   - comentarios (filas; quedaron huérfanos al expirar su reporte/foto)
#   - fotos     (filas + su archivo del bucket "fotos")
# NO toca: lugares (diccionario de autocompletado), noticias (su propio script
# limpia >30d), rate_limit (se autolimpia), tasa_bcv/tasa_binance (1 fila).

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
# Por seguridad arranca en SIMULACRO. Para borrar de verdad: DRY_RUN=false
DRY_RUN = os.environ.get("DRY_RUN", "true").strip().lower() != "false"
RETENTION_DAYS = float(os.environ.get("RETENTION_DAYS", "2"))  # > 12h (ventana activa)

TIMEOUT = 45
MAX_FOTOS = 1000   # fotos por corrida (requieren borrar el archivo del Storage)
CHUNK = 100        # tamaño de lote para storage/delete por id

SB      = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json"}
SB_AUTH = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"}


def cutoff_iso():
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=RETENTION_DAYS)
    return dt.isoformat()


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def contar(tabla, cutoff):
    """Cuántas filas viejas hay (solo para informar)."""
    r = requests.get(f"{SUPABASE_URL}/rest/v1/{tabla}",
                     headers={**SB, "Prefer": "count=exact", "Range": "0-0"},
                     params={"select": "id", "created_at": f"lt.{cutoff}"}, timeout=TIMEOUT)
    cr = r.headers.get("content-range", "*/?")
    try:
        return int(cr.split("/")[-1])
    except Exception:
        return -1


def fotos_viejas(cutoff):
    r = requests.get(f"{SUPABASE_URL}/rest/v1/fotos", headers=SB, timeout=TIMEOUT,
                     params={"select": "id,storage_path", "created_at": f"lt.{cutoff}",
                             "order": "created_at.asc", "limit": str(MAX_FOTOS)})
    r.raise_for_status()
    return r.json()


def borrar_archivos(paths):
    paths = [p for p in paths if p]
    if not paths:
        return
    # API de borrado múltiple del Storage: DELETE /object/{bucket} con {"prefixes":[...]}
    requests.delete(f"{SUPABASE_URL}/storage/v1/object/fotos", headers=SB,
                    json={"prefixes": paths}, timeout=TIMEOUT)


def borrar_filas_por_id(tabla, ids):
    if not ids:
        return
    r = requests.delete(f"{SUPABASE_URL}/rest/v1/{tabla}",
                        headers={**SB, "Prefer": "return=minimal"},
                        params={"id": f"in.({','.join(ids)})"}, timeout=TIMEOUT)
    r.raise_for_status()


def borrar_filas_por_fecha(tabla, cutoff):
    r = requests.delete(f"{SUPABASE_URL}/rest/v1/{tabla}",
                        headers={**SB, "Prefer": "return=minimal"},
                        params={"created_at": f"lt.{cutoff}"}, timeout=TIMEOUT)
    r.raise_for_status()


if __name__ == "__main__":
    modo = "SIMULACRO (no borra nada)" if DRY_RUN else "EN VIVO"
    cutoff = cutoff_iso()
    print(f"Limpieza de datos viejos · modo {modo} · retención {RETENTION_DAYS} días (antes de {cutoff})")

    try:
        n_rep = contar("reportes", cutoff)
        n_com = contar("comentarios", cutoff)
        n_fot = contar("fotos", cutoff)
    except Exception as e:
        print(f"ERROR contando: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Por borrar -> reportes:{n_rep}  comentarios:{n_com}  fotos:{n_fot}")

    if DRY_RUN:
        print("Simulacro: no se borró nada.")
        sys.exit(0)

    # 1) Fotos (archivo del Storage + fila), por lotes
    fotos_borradas = 0
    try:
        fotos = fotos_viejas(cutoff)
        for lote in chunks(fotos, CHUNK):
            borrar_archivos([f.get("storage_path") for f in lote])
            borrar_filas_por_id("fotos", [f["id"] for f in lote])
            fotos_borradas += len(lote)
    except Exception as e:
        print(f"ERROR borrando fotos: {e}", file=sys.stderr)

    # 2) Reportes y comentarios viejos (sin archivos)
    try:
        borrar_filas_por_fecha("reportes", cutoff)
    except Exception as e:
        print(f"ERROR borrando reportes: {e}", file=sys.stderr)
    try:
        borrar_filas_por_fecha("comentarios", cutoff)
    except Exception as e:
        print(f"ERROR borrando comentarios: {e}", file=sys.stderr)

    sufijo = " (quedan más para la próxima corrida)" if fotos_borradas >= MAX_FOTOS else ""
    print(f"OK - fotos borradas:{fotos_borradas}{sufijo}  reportes/comentarios viejos: borrados")
