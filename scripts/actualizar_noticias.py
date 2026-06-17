import os
import sys
import datetime
import calendar
import requests
import feedparser

# Lista de feeds (fuente, url, categoria por defecto). Ajustable luego.
FEEDS = [
    {"fuente": "El Nacional", "url": "https://www.elnacional.com/feed/", "categoria": "nacional"},
    {"fuente": "El Diario",   "url": "https://eldiario.com/feed/",       "categoria": "nacional"},
    {"fuente": "Runrun.es",   "url": "https://runrun.es/feed/",          "categoria": "nacional"},
]

MAX_POR_FEED = 20            # solo las últimas N por feed (no llenar infinito)
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
        # ignora duplicados por enlace: no toca filas ya guardadas (conserva 'creado')
        "Prefer": "resolution=ignore-duplicates,return=minimal",
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

    n = upsert(todos)
    print(f"OK · {n} noticias enviadas (duplicados ignorados por enlace)")
    limpiar_viejas()
