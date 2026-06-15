# Existe um ponto de saturação? Escalonamento de cargas CPU-bound com multiprocessing em um Intel Core i5-13420H

[![Disciplina](https://img.shields.io/badge/CESAR%20School-Infraestrutura%20de%20Hardware%202026-green)](https://cesar.school)

Artigo científico produzido para a 2ª Unidade da disciplina **Infraestrutura de Hardware**
(CESAR School, 2026, Prof. Ronierison Maciel).
Autor: **Guilherme Tolentino Leitão de Melo** — trabalho individual (sem submissão).

---

## Pergunta de pesquisa

> Existe um número de processos além do qual o tempo médio de execução de uma
> carga CPU-bound **aumenta** (escalonamento negativo / ponto de saturação)?

|        | Hipótese                                                                            |
| ------ | ----------------------------------------------------------------------------------- |
| **H0** | Aumentar o número de processos **não** aumenta o tempo médio de execução (p ≥ 0,05).|
| **H1** | Existe um número de processos além do qual o tempo médio **aumenta** (p < 0,05).     |

---

## Hardware

| Componente   | Especificação                                          |
| ------------ | ------------------------------------------------------ |
| CPU          | Intel Core i5-13420H — Raptor Lake-H (13ª geração)     |
| Arquitetura  | 8 núcleos físicos / 12 threads lógicas                 |
| Cache L3     | 12 MiB                                                  |
| RAM          | 8 GB DDR5                                               |
| SO           | _(preencher: ex. Ubuntu via WSL2 — ver dados/ambiente.txt)_ |
| Python       | 3.12                                                   |

---

## Como reproduzir

```bash
# 1. Ambiente
python3 -m pip install numpy scipy matplotlib

# 2. Calibrar a carga (~1s por repetição na sua máquina)
python3 scripts/experimento_paralelismo.py --threads 1 --reps 4 --warmup 1 --carga 6000000 --outdir /tmp/cal

# 3. Experimento completo (>= 30 repetições válidas por condição)
python3 scripts/experimento_paralelismo.py --threads 1 2 4 8 12 --reps 35 --warmup 5 --carga 6000000 --outdir dados
```

(Adicione `--perf` para capturar contadores de hardware, se o `perf` estiver disponível.)

---

## Estrutura

```
.
├── artigo/
│   ├── artigo_paralelismo.docx     # Manuscrito (IMRaD)
│   └── artigo_paralelismo.pdf      # Versão final para entrega
├── scripts/
│   └── experimento_paralelismo.py  # Experimento + estatística + gráficos
├── dados/                          # CSVs brutos, resumo e testes (gerados)
├── graficos/                       # Figuras PNG (geradas)
└── README.md
```

---

## Metodologia (resumo)

- Carga **CPU-bound** em Python puro, distribuída via `multiprocessing.Pool`.
- Trabalho agregado **constante** entre condições (comparação justa).
- Condições: **1, 2, 4, 8 e 12 processos**; **≥ 30 repetições válidas** por condição; warm-up descartado.
- **Média ± desvio-padrão** e **IC 95%** (distribuição t).
- Testes de hipótese: **t de Welch** e **Mann–Whitney U**, unilaterais (α = 0,05); tamanho de efeito (Cohen's d).

---

## Uso de IA

Ferramentas de IA foram utilizadas como apoio à redação e à construção dos scripts,
em conformidade com a política da disciplina. Os experimentos, os dados e a análise
referem-se ao hardware do autor.# Existe um ponto de saturação? Escalonamento de cargas CPU-bound com multiprocessing em um Intel Core i5-13420H

[![Disciplina](https://img.shields.io/badge/CESAR%20School-Infraestrutura%20de%20Hardware%202026-green)](https://cesar.school)

Artigo científico produzido para a 2ª Unidade da disciplina **Infraestrutura de Hardware**
(CESAR School, 2026, Prof. Ronierison Maciel).
Autor: **Guilherme Tolentino Leitão de Melo** — trabalho individual (sem submissão).

---

## Pergunta de pesquisa

> Existe um número de processos além do qual o tempo médio de execução de uma
> carga CPU-bound **aumenta** (escalonamento negativo / ponto de saturação)?

|        | Hipótese                                                                            |
| ------ | ----------------------------------------------------------------------------------- |
| **H0** | Aumentar o número de processos **não** aumenta o tempo médio de execução (p ≥ 0,05).|
| **H1** | Existe um número de processos além do qual o tempo médio **aumenta** (p < 0,05).     |

---

## Hardware

| Componente   | Especificação                                          |
| ------------ | ------------------------------------------------------ |
| CPU          | Intel Core i5-13420H — Raptor Lake-H (13ª geração)     |
| Arquitetura  | 8 núcleos físicos / 12 threads lógicas                 |
| Cache L3     | 12 MiB                                                  |
| RAM          | 8 GB DDR5                                               |
| SO           | _(preencher: ex. Ubuntu via WSL2 — ver dados/ambiente.txt)_ |
| Python       | 3.12                                                   |

---

## Como reproduzir

```bash
# 1. Ambiente
python3 -m pip install numpy scipy matplotlib

# 2. Calibrar a carga (~1s por repetição na sua máquina)
python3 scripts/experimento_paralelismo.py --threads 1 --reps 4 --warmup 1 --carga 6000000 --outdir /tmp/cal

# 3. Experimento completo (>= 30 repetições válidas por condição)
python3 scripts/experimento_paralelismo.py --threads 1 2 4 8 12 --reps 35 --warmup 5 --carga 6000000 --outdir dados
```

(Adicione `--perf` para capturar contadores de hardware, se o `perf` estiver disponível.)

---

## Estrutura

```
.
├── artigo/
│   ├── artigo_paralelismo.docx     # Manuscrito (IMRaD)
│   └── artigo_paralelismo.pdf      # Versão final para entrega
├── scripts/
│   └── experimento_paralelismo.py  # Experimento + estatística + gráficos
├── dados/                          # CSVs brutos, resumo e testes (gerados)
├── graficos/                       # Figuras PNG (geradas)
└── README.md
```

---

## Metodologia (resumo)

- Carga **CPU-bound** em Python puro, distribuída via `multiprocessing.Pool`.
- Trabalho agregado **constante** entre condições (comparação justa).
- Condições: **1, 2, 4, 8 e 12 processos**; **≥ 30 repetições válidas** por condição; warm-up descartado.
- **Média ± desvio-padrão** e **IC 95%** (distribuição t).
- Testes de hipótese: **t de Welch** e **Mann–Whitney U**, unilaterais (α = 0,05); tamanho de efeito (Cohen's d).

