"""Stage 1: the plaintext cross-match algorithm. Runs the *identical*
local-Lagrange-interpolation + squared-distance computation the encrypted
stages run, but entirely in plaintext with plain floats. This is what
every encrypted approach's numeric output gets diffed against -- not the
dense-SGP4 ground truth (that answers "is our scenario realistic"), but
this (answers "does the homomorphic version compute the same thing the
plaintext version of the same algorithm computes").

Run: python3 oem-conjunction/01_plaintext_reference.py
"""
import csv
import math

from common import load_oem, interpolate_plain

WINDOW_S = 300      # candidate grid spans +/- 300 s around OEM center
GRID_STEP_S = 10.0  # 61 candidate times
THRESHOLD_KM = 10.0  # public safety threshold used by approach C


def distance_sq_at(oem_a, oem_b, t):
    xa = interpolate_plain(oem_a["t"], oem_a["x"], t)
    ya = interpolate_plain(oem_a["t"], oem_a["y"], t)
    za = interpolate_plain(oem_a["t"], oem_a["z"], t)
    xb = interpolate_plain(oem_b["t"], oem_b["x"], t)
    yb = interpolate_plain(oem_b["t"], oem_b["y"], t)
    zb = interpolate_plain(oem_b["t"], oem_b["z"], t)
    return (xa - xb) ** 2 + (ya - yb) ** 2 + (za - zb) ** 2


def main():
    oem_a = load_oem("oem-conjunction/data/oem_a.csv")
    oem_b = load_oem("oem-conjunction/data/oem_b.csv")

    n = int(2 * WINDOW_S / GRID_STEP_S) + 1
    rows = []
    best_t, best_d2 = None, None
    for i in range(n):
        t = -WINDOW_S + i * GRID_STEP_S
        d2 = distance_sq_at(oem_a, oem_b, t)
        rows.append((t, d2))
        if best_d2 is None or d2 < best_d2:
            best_d2, best_t = d2, t

    with open("oem-conjunction/results/plaintext_distance_curve.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_offset_s", "distance_sq_km2", "distance_km", "below_threshold"])
        for t, d2 in rows:
            d = math.sqrt(d2)
            w.writerow([t, d2, d, int(d < THRESHOLD_KM)])

    print(f"grid points: {n}, step {GRID_STEP_S}s, window +/-{WINDOW_S}s")
    print(f"plaintext-algorithm CPA estimate: t={best_t:+.1f}s  miss_distance={math.sqrt(best_d2):.4f} km")
    print(f"threshold used for stage 3 (approach C): {THRESHOLD_KM} km")
    n_below = sum(1 for _, d2 in rows if math.sqrt(d2) < THRESHOLD_KM)
    print(f"grid points below threshold: {n_below} / {n}")


if __name__ == "__main__":
    main()
