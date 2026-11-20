"""Baixa e prepara os dados da análise a partir das APIs oficiais.

Fontes:
  - Pix: BCB "Estatísticas do Pix" (Olinda OData), recurso
    TransacoesPixPorMunicipio, mês a mês (o $skip da API não funciona).
  - População: IBGE "Estimativas da População", agregado 6579, variável 9324,
    período 2026, nível município (N6).

Salva em:
  - data/transacoes_pix_municipio.csv   (raw: só as 4 colunas usadas, meses completos)
  - data/populacao_municipios_2026.csv  (raw: população 2026 por município)

Requer: requests, pandas
Usage: python download_data.py
"""
import sys
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DATA.mkdir(parents=True, exist_ok=True)

# --- Pix (BCB) -------------------------------------------------------------
BASE = "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata"
RES = "TransacoesPixPorMunicipio"
COLS = ["AnoMes", "Municipio_Ibge", "QT_RecebedorPF", "VL_RecebedorPF"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "Chrome/120 Safari/537.36",
    "Accept": "application/json",
}


def fetch(url, tries=4):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=300)
            r.raise_for_status()
            return r.json().get("value", [])
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"    tentativa {i + 1} falhou: {e}")
            import time
            time.sleep(5 * (i + 1))
    raise RuntimeError(f"falhou: {url}: {last}")


def download_pix():
    today = pd.Timestamp.today()
    cur = int(today.strftime("%Y%m"))  # mês atual (parcial, será descartado)

    # de nov/2020 (lançamento do Pix) até o mês atual
    start = 2020 * 12 + 11 - 1
    end = today.year * 12 + today.month
    months = [f"{k // 12}{k % 12 + 1:02d}" for k in range(start, end + 1)]

    frames = []
    for m in months:
        # TransacoesPixPorMunicipio é um "function import": exige o parâmetro DataBase
        url = (f"{BASE}/{RES}(DataBase=@DataBase)?@DataBase='{m}'"
               f"&$top=2000000&$filter=AnoMes eq {m}&$format=json")
        rows = fetch(url)
        if rows:
            frames.append(pd.DataFrame(rows)[COLS])
        print(f"  {m}: {len(rows)} linhas")

    df = pd.concat(frames, ignore_index=True)
    df = df[df["AnoMes"] < cur]  # descarta o mês atual (parcial)
    out = DATA / "transacoes_pix_municipio.csv"
    df.to_csv(out, index=False)
    print(f"salvo {out}  ({len(df)} linhas)")


# --- População (IBGE) ------------------------------------------------------
IBGE_URL = ("https://servicodados.ibge.gov.br/api/v3/agregados/6579/"
            "periodos/2026/variaveis/9324?localidades=N6[all]")


def download_ibge():
    r = requests.get(IBGE_URL, timeout=300)
    r.raise_for_status()
    d = r.json()
    series = d[0]["resultados"][0]["series"]
    rows = []
    for s in series:
        loc = s["localidade"]
        codigo = loc["id"].zfill(7)
        municipio = loc["nome"].rsplit(" - ", 1)[0]
        uf = loc["nome"].rsplit(" - ", 1)[-1]
        pop = int(s["serie"]["2026"])
        rows.append((codigo, municipio, uf, pop))
    df = pd.DataFrame(rows, columns=["codigo_ibge", "municipio", "uf", "populacao_2026"])
    df = df.sort_values("codigo_ibge")
    out = DATA / "populacao_municipios_2026.csv"
    df.to_csv(out, index=False)
    print(f"salvo {out}  ({len(df)} municípios, total {df.populacao_2026.sum():,} hab.)")


if __name__ == "__main__":
    print("Baixando Pix (BCB)...")
    download_pix()
    print("\nBaixando população (IBGE)...")
    download_ibge()
