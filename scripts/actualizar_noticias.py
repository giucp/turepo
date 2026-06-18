import os
import sys
import datetime
import calendar
import requests
import feedparser

# Feeds por categoria: cada uno trae su categoria fija (se guarda en 'categoria').
FEEDS = [
    # El Nacional (~100 items/feed; el tope de MAX_POR_FEED evita que domine)
    {"fuente": "El Nacional", "url": "https://www.elnacional.com/venezuela/feed/", "categoria": "nacional"},
    {"fuente": "El Nacional", "url": "https://www.elnacional.com/mundo/feed/",     "categoria": "internacional"},
    {"fuente": "El Nacional", "url": "https://www.elnacional.com/economia/feed/",  "categoria": "economia"},
    {"fuente": "El Nacional", "url": "https://www.elnacional.com/deportes/feed/",  "categoria": "deportes"},
    # El Diario (categorias completas, via /categoria/<slug>/feed/)
    {"fuente": "El Diario", "url": "https://eldiario.com/categoria/venezuela/feed/", "categoria": "nacional"},
    {"fuente": "El Diario", "url": "https://eldiario.com/categoria/mundo/feed/",     "categoria": "internacional"},
    {"fuente": "El Diario", "url": "https://eldiario.com/categoria/economia/feed/",  "categoria": "economia"},
    {"fuente": "El Diario", "url": "https://eldiario.com/categoria/deportes/feed/",  "categoria": "deportes"},
    {"fuente": "El Diario", "url": "https://eldiario.com/categoria/sucesos/feed/",   "categoria": "sucesos"},
    # Runrun.es (solo Nacional e Internacional disponibles)
    {"fuente": "Runrun.es", "url": "https://runrun.es/nacional/feed/",      "categoria": "nacional"},
    {"fuente": "Runrun.es", "url": "https://runrun.es/internacional/feed/", "categoria": "internacional"},
]

MAX_POR_FEED = 8             # max 8 por feed: equilibra la mezcla (El Nacional ~100 vs El Diario ~12)
DIAS_RETENCION = 30          # limpieza: borra lo guardado hace más de N días
TIMEOUT = 25
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def fecha_iso(entry):
    # feedparser normaliza la fecha a UTC en *_parsed (struct_time)
    for campo in ("published_parsed", "updated_parsed"):
        t = entry.get(campo)
        if t:
            return datetime.datetime.fromtimestamp(
                calendar.timegm(t), datetime.timezone.utc).isoformat()
    return None


def leer_feed(feed):
    """Devuelve lista de registros. Si el feed se cae, devuelve [] sin romper."""
    try:
        r = requests.get(feed["url"], timeout=TIMEOUT, headers={"User-Agent": UA})
        r.raise_for_status()
        parsed = feedparser.parse(r.content)
        registros = []
        for e in parsed.entries[:MAX_POR_FEED]:
            titulo = (e.get("title") or "").strip()
            enlace = (e.get("link") or "").strip()
            if not titulo or not enlace:
                continue
            # SOLO titular + enlace + metadatos. NUNCA el contenido del artículo.
            registros.append({
                "titulo": titulo[:500],
                "enlace": enlace,
                "fuente": feed["fuente"],
                "categoria": feed["categoria"],
                "publicado": fecha_iso(e),
            })
        print(f"  {feed['fuente']}: {len(registros)} noticias")
        return registros
    except Exception as ex:
        print(f"  {feed['fuente']}: FALLO ({ex})", file=sys.stderr)
        return []


def upsert(registros):
    if not registros:
        return 0
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    endpoint = f"{url}/rest/v1/noticias?on_conflict=enlace"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # merge por enlace: sin filas duplicadas y re-categoriza las ya guardadas.
        # 'creado' se preserva porque no va en el payload (solo se setea al insertar).
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    resp = requests.post(endpoint, json=registros, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return len(registros)


def limpiar_viejas():
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    corte = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(days=DIAS_RETENCION)).isoformat()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "return=minimal"}
    try:
        resp = requests.delete(
            f"{url}/rest/v1/noticias",
            params={"creado": f"lt.{corte}"},   # requests url-encodea el timestamp
            headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        print(f"Limpieza OK: borradas noticias con creado < {corte}")
    except Exception as ex:
        print(f"Limpieza fallo (no critico): {ex}", file=sys.stderr)


if __name__ == "__main__":
    print("Leyendo feeds...")
    todos = []
    for feed in FEEDS:
        todos.extend(leer_feed(feed))      # cada feed aislado: uno cae, los demás siguen

    if not todos:
        print("ERROR: ningun feed devolvio noticias", file=sys.stderr)
        sys.exit(1)                         # solo falla si TODOS cayeron

    # Dedup por enlace dentro del lote: un mismo articulo puede aparecer en dos
    # feeds (WordPress permite varias categorias). Conserva la 1ra aparicion y
    # evita el error de upsert "cannot affect row a second time".
    vistos = set()
    unicos = []
    for r in todos:
        if r["enlace"] in vistos:
            continue
        vistos.add(r["enlace"])
        unicos.append(r)

    n = upsert(unicos)
    print(f"OK · {n} noticias enviadas de {len(todos)} leidas (merge por enlace)")
    limpiar_viejas()
