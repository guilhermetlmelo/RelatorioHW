#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
experimento_paralelismo.py
==========================

Mede o escalonamento de uma carga CPU-bound em funcao do numero de processos
trabalhadores, com rigor estatistico (>= 30 repeticoes por condicao, descarte de
warm-up, media +/- desvio-padrao, intervalo de confianca 95% e teste de hipotese).

Pergunta de pesquisa
--------------------
Existe um numero de processos alem do qual o tempo medio de execucao de uma carga
CPU-bound AUMENTA (escalonamento negativo / ponto de saturacao)?

  H0: aumentar o numero de processos NAO aumenta o tempo medio de execucao.
  H1: existe um numero de processos alem do qual o tempo medio AUMENTA.

Saidas geradas (em --outdir):
  - dados_brutos.csv      : uma linha por repeticao (condicao, rep, tempo_s)
  - resumo.csv            : por condicao -> n, media, desvio, IC95, speedup, eficiencia
  - estatistica.txt       : resultado dos testes de hipotese (t de Welch e Mann-Whitney)
  - fig_tempo.png         : tempo medio x processos (barras de erro = IC95%)
  - fig_speedup.png       : speedup observado x ideal
  - fig_eficiencia.png    : eficiencia (%) x processos
  - ambiente.txt          : metadados do ambiente (CPU, kernel, governor, swap)
  - perf_<n>.txt          : (opcional, --perf) contadores de hardware por condicao

Uso tipico (na maquina do experimento):
  python3 experimento_paralelismo.py --reps 35 --warmup 5 --carga 6000000 \
      --threads 1 2 4 8 12 --perf --outdir resultados

Autoria: harness preparado para a disciplina Infraestrutura de Hardware (CESAR School).
"""

import argparse
import csv
import math
import multiprocessing as mp
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime

# Dependencias cientificas
try:
    import numpy as np
    from scipy import stats
except ImportError:
    sys.exit("Faltam dependencias. Instale com: pip install numpy scipy matplotlib")

# matplotlib sem display (servidor/WSL)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ----------------------------------------------------------------------------
# Carga CPU-bound
# ----------------------------------------------------------------------------
def _carga_cpu(n_iteracoes):
    """Trabalho puramente CPU-bound (sem I/O, sem alocacao grande).

    Acumula uma soma de raizes/senos para evitar que o compilador/interpretador
    descarte o laco. Roda em Python puro de proposito: e o cenario do relatorio
    de 40% (multiprocessing real, processos pesados), nao threads.
    """
    acc = 0.0
    for i in range(1, n_iteracoes + 1):
        acc += math.sqrt(i) * math.sin(i)
    return acc


def _executa_condicao(n_procs, carga_total):
    """Executa UMA repeticao com n_procs processos e devolve o tempo de parede.

    A carga total e dividida igualmente entre os processos, de modo que o
    trabalho agregado seja constante entre as condicoes (comparacao justa).
    """
    carga_por_proc = max(1, carga_total // n_procs)
    chunks = [carga_por_proc] * n_procs

    inicio = time.perf_counter()
    with mp.Pool(processes=n_procs) as pool:
        pool.map(_carga_cpu, chunks)
    fim = time.perf_counter()
    return fim - inicio


# ----------------------------------------------------------------------------
# Coleta de metadados do ambiente (reprodutibilidade)
# ----------------------------------------------------------------------------
def _coleta_ambiente(outdir):
    linhas = []
    linhas.append(f"Data/hora ......: {datetime.now().isoformat(timespec='seconds')}")
    linhas.append(f"Hostname .......: {platform.node()}")
    linhas.append(f"SO .............: {platform.platform()}")
    linhas.append(f"Kernel .........: {platform.release()}")
    linhas.append(f"Python .........: {platform.python_version()}")
    linhas.append(f"CPUs logicas ...: {os.cpu_count()}")

    def _cmd(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout.strip()
        except Exception as e:
            return f"(indisponivel: {e})"

    if shutil.which("lscpu"):
        linhas.append("\n--- lscpu ---\n" + _cmd(["lscpu"]))
    gov_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
    if os.path.exists(gov_path):
        with open(gov_path) as f:
            linhas.append("\nGovernor (cpu0) : " + f.read().strip())
    else:
        linhas.append("\nGovernor (cpu0) : (nao exposto - comum em WSL2; registrar como ameaca a validade)")
    if shutil.which("free"):
        linhas.append("\n--- free -h ---\n" + _cmd(["free", "-h"]))

    texto = "\n".join(linhas)
    with open(os.path.join(outdir, "ambiente.txt"), "w") as f:
        f.write(texto + "\n")
    return texto


def _captura_perf(n_procs, carga_total, outdir):
    """Captura contadores de hardware (perf stat) para UMA execucao da condicao.

    Nao entra na estatistica: serve de evidencia para a Discussao (por que mais
    processos pioram -> context-switches, cpu-migrations).
    """
    if not shutil.which("perf"):
        return False
    eventos = "task-clock,context-switches,cpu-migrations,page-faults,instructions,cycles"
    saida = os.path.join(outdir, f"perf_{n_procs}.txt")
    try:
        cmd = [
            "perf", "stat", "-e", eventos, "-o", saida,
            sys.executable, "-c",
            f"import experimento_paralelismo as e; e._executa_condicao({n_procs}, {carga_total})",
        ]
        env = dict(os.environ, PYTHONPATH=os.getcwd())
        subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------------
# Estatistica
# ----------------------------------------------------------------------------
def _ic95(amostra):
    """Intervalo de confianca de 95% pela distribuicao t."""
    n = len(amostra)
    if n < 2:
        return 0.0
    sem = statistics.stdev(amostra) / math.sqrt(n)
    t = stats.t.ppf(0.975, df=n - 1)
    return t * sem


def _resume(dados):
    """dados: dict {n_procs: [tempos]} -> lista de dicts por condicao."""
    base_threads = min(dados.keys())
    media_base = statistics.mean(dados[base_threads])

    resumo = []
    for n in sorted(dados.keys()):
        amostra = dados[n]
        media = statistics.mean(amostra)
        desvio = statistics.stdev(amostra) if len(amostra) > 1 else 0.0
        speedup = media_base / media if media > 0 else 0.0
        eficiencia = 100.0 * speedup / n
        resumo.append({
            "processos": n,
            "n": len(amostra),
            "media_s": media,
            "desvio_s": desvio,
            "ic95_s": _ic95(amostra),
            "speedup": speedup,
            "eficiencia_pct": eficiencia,
        })
    return resumo


def _testa_hipotese(dados, outdir):
    """Compara a condicao de MENOR tempo medio (melhor) com a de MAIOR numero
    de processos. Se o tempo no maximo for significativamente MAIOR, rejeitamos
    H0 (ha escalonamento negativo)."""
    medias = {n: statistics.mean(t) for n, t in dados.items()}
    n_melhor = min(medias, key=medias.get)
    n_max = max(dados.keys())

    a = np.array(dados[n_melhor])
    b = np.array(dados[n_max])

    linhas = []
    linhas.append("TESTE DE HIPOTESE - escalonamento negativo")
    linhas.append("=" * 55)
    linhas.append("H0: o tempo medio no numero maximo de processos NAO e maior")
    linhas.append("    que o tempo medio na melhor condicao.")
    linhas.append("H1: o tempo medio no numero maximo de processos E maior")
    linhas.append("    (escalonamento negativo / saturacao).")
    linhas.append("")
    linhas.append(f"Melhor condicao  : {n_melhor} processo(s)  "
                  f"(media = {a.mean():.4f}s, n = {len(a)})")
    linhas.append(f"Condicao maxima  : {n_max} processo(s)  "
                  f"(media = {b.mean():.4f}s, n = {len(b)})")
    linhas.append("")

    # t de Welch (variancias desiguais), unilateral: b > a
    t_stat, p_two = stats.ttest_ind(b, a, equal_var=False)
    p_one = p_two / 2 if t_stat > 0 else 1 - (p_two / 2)
    linhas.append("[t de Student / Welch, unilateral b>a]")
    linhas.append(f"  t = {t_stat:.4f}   p = {p_one:.3e}")

    # Mann-Whitney U (alternativa nao-parametrica, familia Wilcoxon), unilateral
    u_stat, p_mw = stats.mannwhitneyu(b, a, alternative="greater")
    linhas.append("[Mann-Whitney U (Wilcoxon rank-sum), unilateral b>a]")
    linhas.append(f"  U = {u_stat:.1f}   p = {p_mw:.3e}")
    linhas.append("")

    alpha = 0.05
    rejeita = (p_one < alpha) and (p_mw < alpha)
    if rejeita:
        linhas.append(f"CONCLUSAO: p < {alpha} nos dois testes -> REJEITA-SE H0.")
        linhas.append("Ha evidencia de escalonamento negativo (ponto de saturacao).")
    else:
        linhas.append(f"CONCLUSAO: nao foi possivel rejeitar H0 (p >= {alpha} em ao menos um teste).")

    # Tamanho de efeito (Cohen's d)
    pooled = math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2) or 1e-12
    d = (b.mean() - a.mean()) / pooled
    linhas.append(f"\nTamanho de efeito (Cohen's d) = {d:.3f}")

    texto = "\n".join(linhas)
    with open(os.path.join(outdir, "estatistica.txt"), "w") as f:
        f.write(texto + "\n")
    return texto


# ----------------------------------------------------------------------------
# Graficos
# ----------------------------------------------------------------------------
def _graficos(resumo, outdir):
    xs = [r["processos"] for r in resumo]
    medias = [r["media_s"] for r in resumo]
    erros = [r["ic95_s"] for r in resumo]
    speedups = [r["speedup"] for r in resumo]
    efs = [r["eficiencia_pct"] for r in resumo]

    # 1) Tempo medio x processos (barras de erro = IC95)
    plt.figure(figsize=(7, 4.5))
    plt.errorbar(xs, medias, yerr=erros, fmt="o-", capsize=5, linewidth=1.8)
    plt.xlabel("Numero de processos")
    plt.ylabel("Tempo medio de execucao (s)")
    plt.title("Tempo de execucao x paralelismo (IC 95%)")
    plt.grid(True, alpha=0.3)
    plt.xticks(xs)
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "fig_tempo.png"), dpi=150)
    plt.close()

    # 2) Speedup observado x ideal
    plt.figure(figsize=(7, 4.5))
    plt.plot(xs, speedups, "o-", linewidth=1.8, label="Observado")
    plt.plot(xs, xs, "--", color="gray", label="Ideal (linear)")
    plt.xlabel("Numero de processos")
    plt.ylabel("Speedup")
    plt.title("Speedup observado x ideal")
    plt.grid(True, alpha=0.3)
    plt.xticks(xs)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "fig_speedup.png"), dpi=150)
    plt.close()

    # 3) Eficiencia
    plt.figure(figsize=(7, 4.5))
    plt.plot(xs, efs, "o-", color="#c0392b", linewidth=1.8)
    plt.axhline(100, linestyle="--", color="gray", alpha=0.7)
    plt.xlabel("Numero de processos")
    plt.ylabel("Eficiencia (%)")
    plt.title("Eficiencia do paralelismo")
    plt.grid(True, alpha=0.3)
    plt.xticks(xs)
    plt.tight_layout()
    plt.savefig(os.path.join(outdir, "fig_eficiencia.png"), dpi=150)
    plt.close()


# ----------------------------------------------------------------------------
# Persistencia
# ----------------------------------------------------------------------------
def _salva_brutos(dados, outdir):
    with open(os.path.join(outdir, "dados_brutos.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["processos", "repeticao", "tempo_s"])
        for n in sorted(dados.keys()):
            for i, t in enumerate(dados[n], start=1):
                w.writerow([n, i, f"{t:.6f}"])


def _salva_resumo(resumo, outdir):
    with open(os.path.join(outdir, "resumo.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["processos", "n", "media_s", "desvio_s", "ic95_s",
                    "speedup", "eficiencia_pct"])
        for r in resumo:
            w.writerow([r["processos"], r["n"], f"{r['media_s']:.6f}",
                        f"{r['desvio_s']:.6f}", f"{r['ic95_s']:.6f}",
                        f"{r['speedup']:.4f}", f"{r['eficiencia_pct']:.2f}"])


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Experimento de escalonamento de paralelismo (CPU-bound).")
    ap.add_argument("--threads", type=int, nargs="+", default=[1, 2, 4, 8, 12],
                    help="Numeros de processos a testar (default: 1 2 4 8 12).")
    ap.add_argument("--reps", type=int, default=35,
                    help="Repeticoes por condicao, ja incluindo o warm-up (default: 35).")
    ap.add_argument("--warmup", type=int, default=5,
                    help="Repeticoes iniciais descartadas por condicao (default: 5).")
    ap.add_argument("--carga", type=int, default=6_000_000,
                    help="Iteracoes TOTAIS da carga CPU-bound por repeticao (default: 6.000.000).")
    ap.add_argument("--outdir", default="resultados",
                    help="Diretorio de saida (default: resultados).")
    ap.add_argument("--perf", action="store_true",
                    help="Captura contadores de hardware com perf stat (Linux nativo).")
    args = ap.parse_args()

    if args.reps - args.warmup < 30:
        print(f"[AVISO] reps - warmup = {args.reps - args.warmup} (< 30). "
              f"A norma da disciplina exige >= 30 medicoes validas. Aumente --reps.")

    os.makedirs(args.outdir, exist_ok=True)

    print(">> Coletando metadados do ambiente...")
    _coleta_ambiente(args.outdir)

    dados = {}
    for n in args.threads:
        print(f">> Condicao: {n} processo(s) | {args.reps} reps ({args.warmup} de warm-up descartadas)")
        tempos = []
        for r in range(1, args.reps + 1):
            t = _executa_condicao(n, args.carga)
            marca = "warm-up" if r <= args.warmup else "valida"
            if r > args.warmup:
                tempos.append(t)
            print(f"   rep {r:>3}/{args.reps}  {t:8.4f}s  ({marca})")
        dados[n] = tempos
        if args.perf:
            ok = _captura_perf(n, args.carga, args.outdir)
            print(f"   perf: {'capturado' if ok else 'indisponivel (perf nao encontrado/erro)'}")

    print(">> Resumindo e gerando estatistica...")
    resumo = _resume(dados)
    _salva_brutos(dados, args.outdir)
    _salva_resumo(resumo, args.outdir)
    print("\n" + _testa_hipotese(dados, args.outdir) + "\n")
    _graficos(resumo, args.outdir)

    print("RESUMO POR CONDICAO")
    print(f"{'proc':>5} {'n':>4} {'media(s)':>10} {'desvio':>8} {'IC95':>8} {'speedup':>8} {'efic%':>7}")
    for r in resumo:
        print(f"{r['processos']:>5} {r['n']:>4} {r['media_s']:>10.4f} "
              f"{r['desvio_s']:>8.4f} {r['ic95_s']:>8.4f} "
              f"{r['speedup']:>8.3f} {r['eficiencia_pct']:>7.1f}")
    print(f"\nArquivos salvos em: {os.path.abspath(args.outdir)}")


if __name__ == "__main__":
    main()