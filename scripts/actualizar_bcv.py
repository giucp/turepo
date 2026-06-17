import os
import sys
import time
import datetime
import requests
from bs4 import BeautifulSoup
import urllib3

# El BCV usa un cert SSL que no valida; silenciamos el warning de verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BCV_URL = "https://www.bcv.org.ve/"

# Headers de un Chrome real: el BCV devuelve 500 a clientes que no parecen navegador
NAVEGADOR_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "es-VE,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# El BCV es inestable: a veces la 1ra falla con 500 pero la 2da responde
MAX_INTENTOS = 4
ESPERA_BASE = 5   # segundos; la espera crece 5, 10, 15... (backoff progresivo)


def descargar_html():
    sesion = requests.Session()
    sesion.headers.update(NAVEGADOR_HEADERS)
    ultimo_error = None
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            r = sesion.get(
                BCV_URL,
                verify=False,               # <-- clave: ignora el cert UnknownIssuer
                timeout=30,
            )
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            ultimo_error = e
            print(f"Intento {intento}/{MAX_INTENTOS} falló: {e}", file=sys.stderr)
            if intento < MAX_INTENTOS:
                time.sleep(ESPERA_BASE * intento)   # 5s, 10s, 15s...
    raise RuntimeError(f"BCV no respondió tras {MAX_INTENTOS} intentos: {ultimo_error}")


def obtener_tasa_dolar():
    html = descargar_html()
    soup = BeautifulSoup(html, "html.parser")
    div = soup.find(id="dolar")
    if div is None:
        raise RuntimeError("No se encontró id='dolar' en el HTML del BCV")

    strong = div.find("strong")
    if strong is None:
        raise RuntimeError("No se encontró <strong> dentro de id='dolar'")

    crudo = strong.get_text(strip=True)          # ej. "36,42810000"
    # formato venezolano -> float: el punto es miles, la coma es decimal
    limpio = crudo.replace(".", "").replace(",", ".")
    valor = round(float(limpio), 2)
    if valor <= 0:
        raise RuntimeError(f"Valor inválido parseado del BCV: '{crudo}'")
    return valor


def subir_a_supabase(valor):
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    # upsert sobre la fila id=1 (PostgREST: on_conflict + merge-duplicates)
    endpoint = f"{url}/rest/v1/tasa_bcv?on_conflict=id"
    payload = {
        "id": 1,
        "valor": valor,
        "actualizado": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    try:
        valor = obtener_tasa_dolar()
        data = subir_a_supabase(valor)
        print(f"OK · Dólar BCV = {valor} Bs · fila actualizada: {data}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)   # falla el job en GitHub para que se note en el panel
