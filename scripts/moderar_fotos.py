import os
import sys
import re
import json
import time
import base64
import datetime
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
GROQ_KEY     = os.environ["GROQ_API_KEY"]
# Modelo de visión de Groq (configurable por si cambia el nombre)
GROQ_MODEL   = os.environ.get("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
# Por seguridad arranca en SIMULACRO. Para moderar de verdad: DRY_RUN=false
DRY_RUN = os.environ.get("DRY_RUN", "true").strip().lower() != "false"

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
TIMEOUT = 45
MAX_FOTOS = 25            # por corrida

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


def groq_call(messages):
    """POST a Groq (API estilo OpenAI) con reintentos ante 429/503."""
    body = {"model": GROQ_MODEL, "messages": messages, "temperature": 0, "max_tokens": 200}
    headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
    esperas = [8, 20, 40]
    ultimo = None
    for intento in range(len(esperas) + 1):
        r = requests.post(GROQ_URL, headers=headers, json=body, timeout=TIMEOUT)
        if r.status_code in (429, 503):
            ultimo = r
            if intento < len(esperas):
                print(f"    {r.status_code} de Groq, reintento en {esperas[intento]}s...", file=sys.stderr)
                time.sleep(esperas[intento])
                continue
        if not r.ok:
            raise RuntimeError(f"Groq HTTP {r.status_code}: {r.text[:400]}")
        return r.json()
    raise RuntimeError(f"Groq HTTP {ultimo.status_code} tras reintentos: {ultimo.text[:400]}")


def parse_veredicto(txt):
    # extrae el primer objeto JSON aunque venga con texto o ```fences``` alrededor
    m = re.search(r"\{.*\}", txt, re.S)
    data = json.loads(m.group(0)) if m else {}
    v = (data.get("veredicto") or "").strip().lower()
    if v not in ("aprobar", "rechazar", "dudoso"):
        v = "dudoso"
    return v, (data.get("razon") or "").strip()


def moderar(ct, b64):
    messages = [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:{ct};base64,{b64}"}},
    ]}]
    j = groq_call(messages)
    txt = j["choices"][0]["message"]["content"]
    return parse_veredicto(txt)


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
    print(f"Moderación de fotos · modo {modo} · modelo {GROQ_MODEL}")
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
