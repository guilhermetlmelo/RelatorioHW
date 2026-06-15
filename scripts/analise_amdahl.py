#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analise_amdahl.py
=================
Le dados/resumo.csv (gerado por experimento_paralelismo.py), ajusta a Lei de
Amdahl a regiao de escalonamento positivo, estima a fracao paralelizavel e o
teto teorico de speedup, calcula o coeficiente de variacao por condicao e
gera a figura graficos/fig_amdahl.png.

Uso:
    python3 analise_amdahl.py --csv dados/resumo.csv --out graficos/fig_amdahl.png
"""
import argparse
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit


def amdahl(n, p):
    return 1.0 / ((1 - p) + p / n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="dados/resumo.csv")
    ap.add_argument("--out", default="graficos/fig_amdahl.png")
    args = ap.parse_args()

    proc, media, desvio, speed = [], [], [], []
    with open(args.csv, newline="") as f:
        for row in csv.DictReader(f):
            proc.append(int(row["processos"]))
            media.append(float(row["media_s"]))
            desvio.append(float(row["desvio_s"]))
            speed.append(float(row["speedup"]))
    proc = np.array(proc); media = np.array(media)
    desvio = np.array(desvio); speed = np.array(speed)

    # Coeficiente de variacao
    cv = 100 * desvio / media
    print("Coeficiente de variacao (%):")
    for n, c in zip(proc, cv):
        print(f"  {n:2d} processos: {c:.1f}%")

    # Ajuste de Amdahl na regiao monotonica crescente (ate o pico de speedup)
    pico = int(np.argmax(speed))
    nm, sm = proc[: pico + 1], speed[: pico + 1]
    (p,), _ = curve_fit(amdahl, nm, sm, p0=[0.9], bounds=(0, 1))
    print(f"\nFracao paralelizavel estimada p = {p:.4f} ({100*p:.1f}%)")
    print(f"Fracao sequencial (1-p)       = {1-p:.4f} ({100*(1-p):.1f}%)")
    print(f"Speedup maximo teorico        = {1/(1-p):.2f}x")
    print(f"Amdahl previsto no maximo de processos ({proc[-1]}) = {amdahl(proc[-1], p):.2f}x")
    print(f"Speedup observado no maximo de processos        = {speed[-1]:.2f}x")

    # Figura
    xs = np.linspace(proc.min(), proc.max(), 200)
    plt.figure(figsize=(7, 4.3))
    plt.plot(xs, amdahl(xs, p), "-", color="#2e8b57", linewidth=1.8,
             label=f"Modelo de Amdahl (p={p:.2f})")
    plt.plot(proc, speed, "o", color="#1f5fa8", markersize=7, label="Observado")
    plt.plot([proc.min(), proc.max()], [proc.min(), proc.max()], "--",
             color="gray", alpha=0.6, label="Ideal (linear)")
    plt.xlabel("Numero de processos"); plt.ylabel("Speedup")
    plt.title("Speedup observado x modelo de Amdahl ajustado")
    plt.grid(True, alpha=0.3); plt.xticks(proc); plt.legend(); plt.tight_layout()
    import os
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    plt.savefig(args.out, dpi=300); plt.close()
    print(f"\nFigura salva em: {args.out}")


if __name__ == "__main__":
    main()
