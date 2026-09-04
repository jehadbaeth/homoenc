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
ACCENT_SOFT = "#d9e8ea"
GOOD = "#2f7d4f"
GOOD_SOFT = "#dff0e4"
BAD = "#a8412a"
BAD_SOFT = "#f6e1da"
WARN = "#a5741e"
WARN_SOFT = "#f3e6cd"
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


def _box(ax, x, y, w, h, title, body, face, edge=None):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
        facecolor=face, edgecolor=edge or INK, linewidth=1.15,
    ))
    ax.text(x + 0.16, y + h - 0.16, title, fontsize=11.5, fontweight="bold",
            color=INK, va="top")
    ax.text(x + 0.16, y + h - 0.48, body, fontsize=10.5, color=INK, va="top",
            linespacing=1.4)


def plot_attack_surface():
    """Who sees what — light fills, dark ink. Gray-on-teal was unreadable."""
    fig, ax = plt.subplots(figsize=(9.4, 5.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6.3)
    ax.axis("off")
    ax.set_title("What each party actually sees", loc="left", pad=10, fontweight="bold")

    _box(ax, 0.15, 4.45, 2.7, 1.5, "Alice · operator A",
         "Encrypts OEM A under pk\nKeeps sk off this machine", ACCENT_SOFT, ACCENT)
    _box(ax, 0.15, 2.45, 2.7, 1.5, "Bob · operator B",
         "Encrypts OEM B under pk\nKeeps sk off this machine", ACCENT_SOFT, ACCENT)
    _box(ax, 0.15, 0.35, 2.7, 1.6, "Public metadata",
         "Query times T, threshold τ\nSample times (Lagrange)", WARN_SOFT, WARN)
    _box(ax, 3.5, 1.45, 3.15, 3.5, "Server · no secret key",
         "Sees only CKKS ciphertexts\nplus public T, τ, times\n\nInterpolates, distance²,\nbootstraps, masked sum",
         ALT, INK)
    _box(ax, 7.25, 2.2, 2.55, 2.0, "Key holder",
         "Decrypts one scalar\ncount = (n − sum) / 2\nNo positions, no times",
         GOOD_SOFT, GOOD)

    for (x1, y1), (x2, y2) in [
        ((2.85, 5.2), (3.5, 4.4)),
        ((2.85, 3.2), (3.5, 3.4)),
        ((2.85, 1.15), (3.5, 2.15)),
        ((6.65, 3.2), (7.25, 3.2)),
    ]:
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                     mutation_scale=13, color=INK, lw=1.3))
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
    ax.set_yticklabels(labels, color=INK, fontsize=11)
    ax.tick_params(axis="y", colors=INK)
    ax.set_xlim(0, 1.15)
    ax.set_xlabel("residual exposure this design does not close  →")
    ax.set_title("Attack vectors considered — handled vs left open")
    for i, s in enumerate(status):
        ax.text(residual[i] + 0.03, i, s, va="center", fontsize=10, color=INK,
                fontweight="bold")
    ax.grid(axis="y", visible=False)
    ax.invert_yaxis()
    save(fig, "attack_status.svg")


def plot_pipeline():
    """Start-to-end computation flowchart (what the server actually runs)."""
    fig, ax = plt.subplots(figsize=(9.4, 7.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0.2, 11.5)
    ax.axis("off")
    ax.set_title("Computation, start to end", loc="left", pad=8, fontweight="bold")

    steps = [
        (9.05, "1. Local encrypt", "Alice and Bob each turn x,y,z samples\ninto a CKKS ciphertext under pk", ACCENT_SOFT, ACCENT),
        (7.65, "2. Pack query times", "One 64-slot block per public t.\n63 times → 4032 of 4096 slots", ALT, INK),
        (6.25, "3. Interpolate + distance²", "EvalInnerProduct with public Lagrange\nweights, then dx²+dy²+dz²", ALT, INK),
        (4.85, "4. Scale vs threshold", "(d² − τ²) / SCALE into [−1, 1]\nτ and SCALE are public", WARN_SOFT, WARN),
        (3.45, "5. Saturate the sign", "11× EvalPoly. EvalBootstrap when remaining\ndepth < 8 (3 times here)", ACCENT_SOFT, ACCENT),
        (2.05, "6. Mask and sum", "Keep only slot 0 of each block.\nEvalSum → one ciphertext scalar", ALT, INK),
        (0.65, "7. Decrypt the count", "Key holder opens the scalar.\ncount = (n − sum) / 2", GOOD_SOFT, GOOD),
    ]
    x, w, h = 1.45, 7.1, 1.22
    for y, title, body, face, edge in steps:
        _box(ax, x, y, w, h, title, body, face, edge)
    ys = [s[0] for s in steps]
    for y0, y1 in zip(ys, ys[1:]):
        ax.add_patch(FancyArrowPatch(
            (x + w / 2, y0), (x + w / 2, y1 + h),
            arrowstyle="-|>", mutation_scale=11, color=INK, lw=1.2,
        ))
    save(fig, "pipeline.svg")


def plot_alice_bob():
    """Message sequence chart: Alice, Bob, honest-but-curious server, key holder."""
    fig, ax = plt.subplots(figsize=(9.8, 8.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 13.0)
    ax.axis("off")
    ax.set_title("Alice–Bob protocol diagram  ·  who sends what, in which form",
                 loc="left", pad=8, fontweight="bold")

    xs = {"Alice": 1.2, "Bob": 3.6, "Server": 6.15, "Key": 8.7}
    top, bottom = 11.35, 1.15
    headers = [
        (xs["Alice"], "Alice", "operator A"),
        (xs["Bob"], "Bob", "operator B"),
        (xs["Server"], "Server", "no secret key"),
        (xs["Key"], "Key holder", "holds sk"),
    ]
    for x, name, role in headers:
        ax.text(x, 12.35, name, ha="center", fontsize=12, fontweight="bold", color=INK)
        ax.text(x, 12.05, role, ha="center", fontsize=9.5, color=INK)
        ax.plot([x, x], [bottom, top], color=INK, lw=1.15)
        ax.plot(x, top, "o", color=INK, ms=5.5)
        ax.plot(x, bottom, "o", color=INK, ms=5.5)

    def msg(y, src, dst, label, face):
        x0, x1 = xs[src], xs[dst]
        ax.annotate(
            "", xy=(x1, y), xytext=(x0, y),
            arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.3,
                            shrinkA=2, shrinkB=2),
        )
        ax.text((x0 + x1) / 2, y + 0.08, label, ha="center", va="bottom",
                fontsize=8.7, color=INK,
                bbox=dict(boxstyle="round,pad=0.25", facecolor=face,
                          edgecolor=INK, linewidth=0.8))

    def note(y, who, label, face):
        x = xs[who]
        ax.add_patch(FancyBboxPatch(
            (x - 0.95, y - 0.28), 1.9, 0.7,
            boxstyle="round,pad=0.02,rounding_size=0.06",
            facecolor=face, edgecolor=INK, linewidth=0.8,
        ))
        ax.text(x, y + 0.07, label, ha="center", va="center", fontsize=8.2, color=INK)

    msg(10.7, "Key", "Alice", "pk   (public key)", WARN_SOFT)
    msg(9.95, "Key", "Bob", "pk   (public key)", WARN_SOFT)
    msg(9.2, "Key", "Server", "eval keys only  ·  mult, rotate, bootstrap  ·  not sk", WARN_SOFT)
    note(8.35, "Alice", "plaintext OEM A\n→ Enc_pk(x,y,z)", ACCENT_SOFT)
    note(8.35, "Bob", "plaintext OEM B\n→ Enc_pk(x,y,z)", ACCENT_SOFT)
    msg(7.45, "Alice", "Server", "CKKS ciphertext  Enc(OEM A)", ACCENT_SOFT)
    msg(6.7, "Bob", "Server", "CKKS ciphertext  Enc(OEM B)", ACCENT_SOFT)
    msg(5.95, "Alice", "Server", "public: query times T,  threshold τ,  sample times", WARN_SOFT)
    note(5.05, "Server", "homomorphic eval\nnever decrypts", ALT)
    msg(4.15, "Server", "Key", "CKKS scalar  Enc(flag-sum)", ACCENT_SOFT)
    note(3.2, "Key", "sk: decrypt → 61.0000\ncount = (n−sum)/2 = 1", GOOD_SOFT)

    ax.text(5.0, 0.45,
            "Teal = ciphertext    Amber = public metadata    Green = plaintext result at the key holder only",
            ha="center", fontsize=9, color=INK)
    save(fig, "alice_bob.svg")


def main():
    style()
    plot_saturation()
    plot_cluster_pressure()
    plot_load_scaling()
    plot_timing()
    plot_threads()
    plot_attack_surface()
    plot_attack_status()
    plot_pipeline()
    plot_alice_bob()


if __name__ == "__main__":
    main()
