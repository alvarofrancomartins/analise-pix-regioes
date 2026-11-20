"""Pix recebidos por PF per capita, por região (número e valor, per capita com intervalo interquartílico).

Script autocontido: lê os CSVs locais em `data/` e gera o gráfico em `output/`.
Não depende de nada fora desta pasta.

Requer: pandas, numpy, matplotlib  (pip install -r requirements.txt)

Usage: python pix_regioes_recebidos.py
"""
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent

REGIAO = {
    "Norte": ["RO", "AC", "AM", "RR", "PA", "AP", "TO"],
    "Nordeste": ["MA", "PI", "CE", "RN", "PB", "PE", "AL", "SE", "BA"],
    "Centro-Oeste": ["MS", "MT", "GO", "DF"],
    "Sudeste": ["MG", "ES", "RJ", "SP"],
    "Sul": ["PR", "SC", "RS"],
}
UF_REGIAO = {uf: r for r, ufs in REGIAO.items() for uf in ufs}
CORES = {
    "Norte": "#e41a1c",
    "Nordeste": "#377eb8",
    "Centro-Oeste": "#4daf4a",
    "Sudeste": "#984ea3",
    "Sul": "#ff7f00",
}
INK = "#0b0b0b"

mun = pd.read_csv(HERE / "data" / "transacoes_pix_municipio.csv",
                  dtype={"Municipio_Ibge": str})
pop = pd.read_csv(HERE / "data" / "populacao_municipios_2026.csv",
                  dtype={"codigo_ibge": str})

d = mun[["Municipio_Ibge", "AnoMes", "QT_RecebedorPF", "VL_RecebedorPF"]].merge(
    pop[["codigo_ibge", "uf", "populacao_2026"]].rename(
        columns={"codigo_ibge": "Municipio_Ibge"}), on="Municipio_Ibge")
d["regiao"] = d["uf"].map(UF_REGIAO)

# Só perde as linhas com Município sem código (agregado "não informado" do BCB).
assert len(d) == mun["Municipio_Ibge"].notna().sum(), "merge descartou municípios"


def _wquantile(values, weights, q):
    """Quantil ponderado (peso = população) da razão per capita."""
    order = np.argsort(values)
    cw = np.cumsum(weights[order]) / weights.sum()
    return values[order][np.searchsorted(cw, q)]


def agg(num_col):
    """Per capita da região = razão de somas (soma do numerador / soma da população).

    Acompanha o intervalo interquartílico (P25-P75) ponderado pela população
    entre os municípios, a dispersão típica, robusta a valores extremos.
    """
    rows = []
    for (regiao, mes), g in d.groupby(["regiao", "AnoMes"]):
        pop = g["populacao_2026"].to_numpy()
        num = g[num_col].to_numpy()
        ratio = num.sum() / pop.sum()
        r = num / pop
        rows.append((regiao, mes, ratio,
                     _wquantile(r, pop, 0.25), _wquantile(r, pop, 0.75)))
    out = pd.DataFrame(rows, columns=["regiao", "AnoMes", "mean", "lo", "hi"])
    out["t"] = pd.to_datetime(out["AnoMes"].astype(str), format="%Y%m")
    return out


gc = agg("QT_RecebedorPF")
gv = agg("VL_RecebedorPF")


def fmt_brl(x, pos):
    if x >= 1e6:
        return f"{x/1e6:.0f}M"
    if x >= 1e3:
        return f"{x/1e3:.0f}k"
    return f"{x:.0f}"


fig, axes = plt.subplots(1, 2, figsize=(16, 6.5))
fig.patch.set_facecolor("white")

for ax, g, metrica in [(axes[0], gc, "count"), (axes[1], gv, "value")]:
    ax.set_facecolor("white")
    for regiao in REGIAO:
        r = g[g["regiao"] == regiao].sort_values("t")
        cor = CORES[regiao]
        ax.plot(r["t"], r["mean"], linewidth=2.0, color=cor, alpha=0.95)
        ax.fill_between(r["t"], r["lo"], r["hi"],
                        color=cor, alpha=0.20, linewidth=0)
        ax.annotate(regiao, (r["t"].iloc[-1], r["mean"].iloc[-1]),
                    xytext=(5, 0), textcoords="offset points",
                    fontsize=14, color=cor, va="center", fontweight="bold")
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(colors=INK, labelsize=16)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#c3c2b7")
    if metrica == "value":
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(fmt_brl))
        ax.set_ylabel("Valor recebido (R$) / per capita / mês", fontsize=16, color=INK)
        ax.set_title("Valor (per capita, IQR entre municípios)", fontsize=15,
                     fontweight="bold", color=INK, loc="left")
    else:
        ax.yaxis.set_major_locator(mtick.MaxNLocator(integer=True))
        ax.set_ylabel("Pix recebidos / per capita / mês", fontsize=16, color=INK)
        ax.set_title("Número (per capita, IQR entre municípios)", fontsize=15,
                     fontweight="bold", color=INK, loc="left")

fig.suptitle("Pix recebidos por PF per capita, por região",
             fontsize=20, fontweight="bold", color=INK, y=1.03)
fig.tight_layout(rect=(0, 0, 1, 1.0))

out = HERE / "output" / "pix_regioes_recebidos.png"
out.parent.mkdir(parents=True, exist_ok=True)
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
plt.close()
print(f"salvo {out}")

# Salva os dados plotados em CSV (uma linha por métrica × região × mês).
csv_df = pd.concat([gc.assign(metrica="numero"), gv.assign(metrica="valor")],
                   ignore_index=True)
csv_df["iqr"] = csv_df["hi"] - csv_df["lo"]
csv_df = (csv_df[["metrica", "regiao", "AnoMes", "mean", "lo", "hi", "iqr"]]
          .rename(columns={"AnoMes": "ano_mes", "mean": "per_capita",
                           "lo": "p25", "hi": "p75"})
          .sort_values(["metrica", "regiao", "ano_mes"]))
csv_df[["per_capita", "p25", "p75", "iqr"]] = \
    csv_df[["per_capita", "p25", "p75", "iqr"]].round(4)
csv_out = HERE / "output" / "pix_regioes_recebidos.csv"
csv_df.to_csv(csv_out, index=False)
print(f"salvo {csv_out}")
