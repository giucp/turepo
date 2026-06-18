import os
import sys
import time
import datetime
import statistics
import requests

# API P2P de Binance: ofertas reales USDT/VES (la fuente más fresca de la tasa "binance")
BINANCE_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MAX_INTENTOS = 3
ESPERA = 4          # backoff progresivo: 4s, 8s
TIMEOUT = 30
ROWS = 20           # ofertas a considerar para la mediana


def obtener_tasa_binance():
    body = {"asset": "USDT", "fiat": "VES", "tradeType": "SELL",
            "page": 1, "rows": ROWS, "payTypes": [], "publisherType": None}
    ultimo = None
    for intento in range(1, MAX_INTENTOS + 1):
        try:
            r = requests.post(BINANCE_URL, json=body, timeout=TIMEOUT,
                              headers={"User-Agent": UA, "Content-Type": "application/json"})
            r.raise_for_status()
            data = r.json().get("data", [])
            precios = [float(x["adv"]["price"]) for x in data
                       if x.get("adv", {}).get("price")]
            if not precios:
                raise RuntimeError("Binance no devolvió ofertas")
            # mediana de las ofertas SELL: robusta frente a outliers
            return round(statistics.median(precios), 2)
        except Exception as e:
            ultimo = e
            print(f"Intento {intento}/{MAX_INTENTOS} falló: {e}", file=sys.stderr)
            if intento < MAX_INTENTOS:
                time.sleep(ESPERA * intento)
    raise RuntimeError(f"Binance no respondió tras {MAX_INTENTOS} intentos: {ultimo}")


def subir_a_supabase(valor):
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    endpoint = f"{url}/rest/v1/tasa_binance?on_conflict=id"
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
    resp = requests.post(endpoint, json=payload, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    try:
        valor = obtener_tasa_binance()
        data = subir_a_supabase(valor)
        print(f"OK · Binance USDT/VES = {valor} Bs · fila actualizada: {data}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
