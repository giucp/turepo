import os
import sys
import datetime
import requests
from bs4 import BeautifulSoup
import urllib3

# El BCV usa un cert SSL que no valida; silenciamos el warning de verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BCV_URL = "https://www.bcv.org.ve/"


def obtener_tasa_dolar():
    r = requests.get(
        BCV_URL,
        verify=False,                       # <-- clave: ignora el cert UnknownIssuer
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0 (turepo-bcv-bot)"},
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
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
