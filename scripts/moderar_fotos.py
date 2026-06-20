import os
import sys
import json
import time
import base64
import datetime
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
GEMINI_KEY   = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
# Por seguridad arranca en SIMULACRO. Para moderar de verdad: DRY_RUN=false
DRY_RUN = os.environ.get("DRY_RUN", "true").strip().lower() != "false"

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
TIMEOUT = 45
MAX_FOTOS = 25            # por corrida (respeta la capa gratis de Gemini)

SB = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json"}

PROMPT = (
    "Eres moderador de Tu Repo, una app comunitaria venezolana donde la gente sube fotos de "
    "situaciones de su ciudad: colas de gasolina, estado de la luz, calles y vías, precios y "
    "ofertas, comercios, etc.\n\n"
    "Evalúa la imagen y responde SOLO un JSON válido (sin texto extra) con la forma:\n"
    '{"veredicto":"aprobar|rechazar|dudoso","razon":"motivo breve"}\n\n'
    "Reglas:\n"
    "- rechazar: contenido sexual o desnudez, violencia gráfica o gore, símbolos de odio, "
    "o spam/publicidad sin relación con la comunidad.\n"
    "- aprobar: foto real de una situación cotidiana o comunitaria, un lugar, una cola, un "
    "comercio, precios, calles, etc. (aunque sea de baja calidad).\n"
    "- dudoso: si no puedes determinarlo con confianza.\n"
    'Ante la duda usa "dudoso": un humano la revisará.'
)

SAFETY = [
    {"category": c, "threshold": "BLOCK_NONE"} for c in (
        "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
        "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT",
    )
]


def pendientes():
    r = requests.get(f"{SUPABASE_URL}/rest/v1/fotos", headers=SB, timeout=TIMEOUT,
                     params={"select": "id,storage_path,region,categoria,descripcion",
                             "estado": "eq.pendiente", "order": "created_at.asc",
                             "limit": str(MAX_FOTOS)})
    r.raise_for_status()
    return r.json()


def bajar_imagen(storage_path):
    url = f"{SUPABASE_URL}/storage/v1/object/public/fotos/{storage_path}"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    ct = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    if not ct.startswith("image/"):
        ct = "image/jpeg"
    return ct, base64.b64encode(r.content).decode("ascii")


def gemini_call(body):
    """POST a Gemini con reintentos ante 429/503; en error muestra el cuerpo real."""
    esperas = [8, 20, 40]   # backoff entre reintentos
    ultimo = None
    for intento in range(len(esperas) + 1):
        r = requests.post(GEMINI_URL, params={"key": GEMINI_KEY}, json=body, timeout=TIMEOUT)
        if r.status_code in (429, 503):
            ultimo = r
            if intento < len(esperas):
                print(f"    {r.status_code} de Gemini, reintento en {esperas[intento]}s...", file=sys.stderr)
                time.sleep(esperas[intento])
                continue
        if not r.ok:
            raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:400]}")
        return r.json()
    raise RuntimeError(f"Gemini HTTP {ultimo.status_code} tras reintentos: {ultimo.text[:400]}")


def moderar(ct, b64):
    body = {
        "contents": [{"parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": ct, "data": b64}},
        ]}],
        "safetySettings": SAFETY,
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    cands = gemini_call(body).get("candidates") or []
    if not cands:
        return "dudoso", "Gemini no devolvió veredicto (posible bloqueo)"
    txt = cands[0]["content"]["parts"][0]["text"]
    data = json.loads(txt)
    v = (data.get("veredicto") or "").strip().lower()
    if v not in ("aprobar", "rechazar", "dudoso"):
        v = "dudoso"
    return v, (data.get("razon") or "").strip()


def aprobar(fid):
    payload = {"estado": "aprobada",
               "aprobada_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/fotos", headers={**SB, "Prefer": "return=minimal"},
                       params={"id": f"eq.{fid}"}, json=payload, timeout=TIMEOUT)
    r.raise_for_status()


def rechazar(fid, storage_path):
    r = requests.patch(f"{SUPABASE_URL}/rest/v1/fotos", headers={**SB, "Prefer": "return=minimal"},
                       params={"id": f"eq.{fid}"}, json={"estado": "rechazada"}, timeout=TIMEOUT)
    r.raise_for_status()
    try:  # borra el archivo del bucket (no crítico si falla)
        requests.delete(f"{SUPABASE_URL}/storage/v1/object/fotos/{storage_path}",
                        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"},
                        timeout=TIMEOUT)
    except Exception:
        pass


if __name__ == "__main__":
    modo = "SIMULACRO (no cambia nada)" if DRY_RUN else "EN VIVO"
    print(f"Moderación de fotos · modo {modo} · modelo {GEMINI_MODEL}")
    try:
        fotos = pendientes()
    except Exception as e:
        print(f"ERROR leyendo pendientes: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"{len(fotos)} foto(s) pendiente(s)")

    ap = rc = du = 0
    for f in fotos:
        fid = f["id"]
        try:
            ct, b64 = bajar_imagen(f["storage_path"])
            v, razon = moderar(ct, b64)
        except Exception as e:
            print(f"  {fid}: ERROR ({e}) -> se deja pendiente", file=sys.stderr)
            du += 1
            continue
        print(f"  {fid}: {v.upper()} -- {razon}")
        if DRY_RUN:
            continue
        try:
            if v == "aprobar":
                aprobar(fid); ap += 1
            elif v == "rechazar":
                rechazar(fid, f["storage_path"]); rc += 1
            else:
                du += 1
        except Exception as e:
            print(f"  {fid}: ERROR aplicando '{v}' ({e})", file=sys.stderr)

    if DRY_RUN:
        print("Simulacro: no se modificó ninguna foto.")
    else:
        print(f"OK - aprobadas={ap} rechazadas={rc} dudosas/pendientes={du}")
