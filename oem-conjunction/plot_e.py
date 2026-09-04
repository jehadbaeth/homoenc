"""Render Approach E report figures from the benchmark CSVs."""
import csv
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
FIG = RESULTS / "e_figures"

INK = "#131a1f"
SOFT = "#55636a"
ACCENT = "#2f6f7a"
GOOD = "#2f7d4f"
BAD = "#a8412a"
WARN = "#a5741e"
RULE = "#c7d1cd"
SURFACE = "#ffffff"
ALT = "#e3e9e6"

CLUSTER_LABELS = {
    0: "61.9 km",
    1: "28.9 km",
    2: "37.5 km",
    3: "5.43 km",
    4: "13.3 km",
    5: "20.4 km",
    6: "11.7 km",
}
# Highlight: violation, two near-boundary, one far-safe.
FOCUS = (3, 6, 4, 0)
FOCUS_COLOR = {3: BAD, 6: WARN, 4: WARN, 0: GOOD}


def style():
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.edgecolor": RULE,
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "text.color": INK,
        "xtick.color": SOFT,
        "ytick.color": SOFT,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.grid": True,
        "grid.color": ALT,
        "grid.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    path = FIG / name
    fig.savefig(path, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    print(f"wrote {path}")


def read_csv(name):
    with open(RESULTS / name) as f:
        return list(csv.DictReader(f))


def plot_saturation():
    rows = read_csv("e_saturation.csv")
    by_cluster = defaultdict(lambda: defaultdict(list))
    for r in rows:
        ci = int(r["cluster_index"])
        k = int(r["composition"])
        # keep the candidate closest to that cluster's CPA (min plaintext d)
        by_cluster[ci][k].append((float(r["plaintext_distance_km"]), float(r["raw_flag"])))

    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    for ci in FOCUS:
        xs, ys = [], []
        for k in sorted(by_cluster[ci]):
            best = min(by_cluster[ci][k], key=lambda t: t[0])
            xs.append(k)
            ys.append(best[1])
        ax.plot(xs, ys, color=FOCUS_COLOR[ci], lw=2.2, marker="o", ms=4.5,
                label=f"cluster {ci} · {CLUSTER_LABELS[ci]}")
    ax.axhline(0, color=RULE, lw=1)
    ax.axhline(1, color=GOOD, lw=0.8, ls="--", alpha=0.7)
    ax.axhline(-1, color=BAD, lw=0.8, ls="--", alpha=0.7)
    ax.set_xlabel("sign-polynomial compositions (bootstrapped when depth runs out)")
    ax.set_ylabel("encrypted flag at the cluster CPA")
    ax.set_title("Saturation under real miss-distance pressure")
    ax.set_xticks(range(1, 12))
    ax.set_ylim(-1.25, 1.25)
    ax.legend(frameon=False, loc="lower right")
    save(fig, "saturation.svg")


def plot_cluster_pressure():
    rows = read_csv("e_cluster_pressure.csv")
    rows = sorted(rows, key=lambda r: float(r["ground_truth_miss_km"]))
    misses = [float(r["ground_truth_miss_km"]) for r in rows]
    flags = [float(r["final_flag"]) for r in rows]
    colors = [BAD if float(r["ground_truth_miss_km"]) < 10 else GOOD for r in rows]

    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    ax.axvline(10, color=BAD, ls="--", lw=1.2, label="10 km screening threshold")
    ax.axhline(0, color=RULE, lw=1)
    ax.scatter(misses, flags, c=colors, s=70, zorder=3, edgecolors=INK, linewidths=0.4)
    for r, x, y in zip(rows, misses, flags):
        ax.annotate(f"c{r['cluster_index']}", (x, y), textcoords="offset points",
                    xytext=(6, 6), fontsize=9, color=SOFT)
    ax.set_xlabel("true miss distance (km) — dense SGP4 CPA, real TLEs")
    ax.set_ylabel("final encrypted flag after 11 compositions")
    ax.set_title("Seven real close approaches, one ciphertext")
    ax.set_ylim(-1.35, 1.35)
    ax.legend(frameon=False, loc="lower right")
    save(fig, "cluster_pressure.svg")


def plot_load_scaling():
    rows = read_csv("e_load_scaling.csv")
    n = [int(r["n_clusters"]) for r in rows]
    boot = [float(r["t_bootstrap_s"]) for r in rows]
    dist = [float(r["t_dist_s"]) for r in rows]
    compose = [float(r["t_compose_s"]) for r in rows]
    total = [float(r["t_total_s"]) for r in rows]

    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    ax.plot(n, total, color=INK, lw=2.2, marker="o", label="end-to-end")
    ax.plot(n, boot, color=ACCENT, lw=1.8, marker="o", label="bootstraps")
    ax.plot(n, compose, color=WARN, lw=1.8, marker="o", label="sign-poly EvalPoly")
    ax.plot(n, dist, color=SOFT, lw=1.8, marker="o", label="distance² + scale")
    ax.set_xlabel("real events packed into one ciphertext (hardest first)")
    ax.set_ylabel("seconds")
    ax.set_title("Cost as more real conjunctions share the same ciphertext")
    ax.set_xticks(n)
    ax.legend(frameon=False)
    save(fig, "load_scaling.svg")


def plot_timing():
    rows = read_csv("e_timing_breakdown.csv")
    order = [
        "context_keygen_bootstrap_setup",
        "encrypt_both_oems",
        "distance_sq_and_scale",
        "sign_poly_compositions",
        "bootstraps",
        "masked_sum_decrypt",
    ]
    labels = {
        "context_keygen_bootstrap_setup": "context + keygen",
        "encrypt_both_oems": "encrypt both OEMs",
        "distance_sq_and_scale": "distance² + scale",
        "sign_poly_compositions": "11× EvalPoly",
        "bootstraps": "3× EvalBootstrap",
        "masked_sum_decrypt": "masked sum + decrypt",
    }
    by_name = {r["stage"]: float(r["seconds"]) for r in rows}
    names = [labels[s] for s in order]
    vals = [by_name[s] for s in order]
    colors = [ALT, ALT, ACCENT, WARN, BAD, GOOD]

    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.barh(names[::-1], vals[::-1], color=colors[::-1], height=0.62)
    for name, v in zip(names[::-1], vals[::-1]):
        ax.text(v + max(vals) * 0.02, name, f"{v:.2f}s", va="center", fontsize=10, color=SOFT)
    ax.set_xlabel("seconds  ·  7 real events, 63 packed times, OMP_NUM_THREADS=8")
    ax.set_title("Where the 7-event run actually spends time")
    ax.grid(axis="y", visible=False)
    save(fig, "timing.svg")


def plot_threads():
    rows = read_csv("e_thread_scaling.csv")
    t = [int(r["omp_threads"]) for r in rows]
    boot = [float(r["t_bootstrap_s"]) for r in rows]
    total = [
        float(r["t_ctx_s"]) + float(r["t_enc_s"]) + float(r["t_dist_s"])
        + float(r["t_compose_s"]) + float(r["t_bootstrap_s"]) + float(r["t_sum_s"])
        for r in rows
    ]
    fig, ax = plt.subplots(figsize=(8.4, 4.2))
    ax.plot(t, total, color=INK, lw=2.2, marker="o", label="end-to-end")
    ax.plot(t, boot, color=ACCENT, lw=1.8, marker="o", label="3 bootstraps")
    ax.set_xlabel("OMP_NUM_THREADS (physical cores on this host: 16)")
    ax.set_ylabel("seconds")
    ax.set_title("OpenMP scaling on the single-event 61-point ciphertext")
    ax.set_xticks(t)
    ax.legend(frameon=False)
    save(fig, "threads.svg")


def plot_attack_surface():
    """Who sees what — the only 'attack vector' figure that belongs in an E-only report."""
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6.2)
    ax.axis("off")
    ax.set_title("What each party actually sees", loc="left", pad=8)

    boxes = [
        (0.2, 4.4, 2.6, 1.4, "Operator A", "encrypts OEM A\nkeeps secret key", ACCENT),
        (0.2, 2.4, 2.6, 1.4, "Operator B", "encrypts OEM B\nkeeps secret key", ACCENT),
        (0.2, 0.4, 2.6, 1.4, "Public metadata", "query times\nthreshold, sample times", WARN),
        (3.6, 1.6, 3.0, 3.2, "Infrastructure", "ciphertexts only\nno decryption key\ninterpolation, distance²,\nbootstrap, masked sum", ALT),
        (7.3, 2.3, 2.5, 1.8, "Key holder", "decrypts one scalar:\ncount of violations", GOOD),
    ]
    for x, y, w, h, title, body, face in boxes:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.08",
                                    facecolor=face, edgecolor=RULE, linewidth=1))
        ax.text(x + 0.12, y + h - 0.28, title, fontsize=11, fontweight="600", color=INK)
        ax.text(x + 0.12, y + 0.18, body, fontsize=9.5, color=SOFT, va="bottom")

    arrows = [
        ((2.8, 5.1), (3.6, 4.2)),
        ((2.8, 3.1), (3.6, 3.4)),
        ((2.8, 1.1), (3.6, 2.2)),
        ((6.6, 3.2), (7.3, 3.2)),
    ]
    for (x1, y1), (x2, y2) in arrows:
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=12, color=SOFT, lw=1.2))
    save(fig, "attack_surface.svg")


def plot_attack_status():
    labels = [
        "Honest-but-curious host",
        "Over-disclosure of the answer",
        "CKKS misclassification",
        "Public candidate times",
        "Demo-grade parameters",
        "Malicious / tampering host",
        "Collusion, one owner + host",
    ]
    status = ["handled", "handled", "measured", "acknowledged", "disclosed", "out of scope", "out of scope"]
    colors = {
        "handled": GOOD,
        "measured": ACCENT,
        "acknowledged": WARN,
        "disclosed": WARN,
        "out of scope": BAD,
    }
    # qualitative residual exposure, 0 = none we claim, 1 = fully open
    residual = [0.08, 0.12, 0.22, 0.55, 0.70, 1.0, 1.0]

    fig, ax = plt.subplots(figsize=(8.4, 4.6))
    y = np.arange(len(labels))
    ax.barh(y, residual, color=[colors[s] for s in status], height=0.62)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(0, 1.15)
    ax.set_xlabel("residual exposure this design does not close  →")
    ax.set_title("Attack vectors considered — handled vs left open")
    for i, s in enumerate(status):
        ax.text(residual[i] + 0.03, i, s, va="center", fontsize=9.5, color=SOFT)
    ax.grid(axis="y", visible=False)
    ax.invert_yaxis()
    save(fig, "attack_status.svg")


def main():
    style()
    plot_saturation()
    plot_cluster_pressure()
    plot_load_scaling()
    plot_timing()
    plot_threads()
    plot_attack_surface()
    plot_attack_status()


if __name__ == "__main__":
    main()
