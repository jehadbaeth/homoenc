"""Scenario 2, Approach C: thresholded per-point flags (see
04_approach_c_thresholded_flags.py) run over the seven real close-approach
clusters found in the wider +/-3h search instead of the single global
minimum. Same TenSEAL/SEAL context, same fitted sign polynomial, same
SCALE_KM2 operating parameter -- the only change is which candidate times
get evaluated.

This is the key test for whether the pipeline is trustworthy this close to
the decision boundary: two of the seven clusters (11.698 km and 13.276 km
true miss distance) sit only a few km outside the 10 km threshold. Approach
C decrypts a flag at every one of the 63 candidate points, so it can be
checked directly against the plaintext reference (10_multi_plaintext_reference.py)
point by point, cluster by cluster.

Run: python3 oem-conjunction/11_multi_approach_c_flags.py
"""
import csv
import json
import time

from common import load_oem
from crypto_common import make_context, encrypt_oem, encrypted_distance_sq

CLUSTER_WINDOW_S = 40
CLUSTER_STEP_S = 10.0
THRESHOLD_KM = 10.0
SCALE_KM2 = 5_000_000.0  # same operating parameter as the single-event scenario


def load_sign_poly():
    with open("oem-conjunction/data/sign_poly_coeffs.json") as f:
        return json.load(f)["coeffs"]


def load_clusters():
    with open("oem-conjunction/data/multi_ground_truth.csv") as f:
        return [float(row["t_center_offset_s"]) for row in csv.DictReader(f)]


def build_query_ts(clusters):
    n_per_cluster = int(2 * CLUSTER_WINDOW_S / CLUSTER_STEP_S) + 1
    query_ts, cluster_of = [], []
    for ci, center in enumerate(clusters):
        for i in range(n_per_cluster):
            query_ts.append(center - CLUSTER_WINDOW_S + i * CLUSTER_STEP_S)
            cluster_of.append(ci)
    return query_ts, cluster_of


def main():
    oem_a = load_oem("oem-conjunction/data/oem_a_multi.csv")
    oem_b = load_oem("oem-conjunction/data/oem_b_multi.csv")
    coeffs = load_sign_poly()
    threshold_sq = THRESHOLD_KM ** 2
    clusters = load_clusters()
    query_ts, cluster_of = build_query_ts(clusters)

    t0 = time.perf_counter()
    context = make_context()
    t_ctx = time.perf_counter() - t0

    t0 = time.perf_counter()
    enc_a = encrypt_oem(context, oem_a)
    enc_b = encrypt_oem(context, oem_b)
    t_enc = time.perf_counter() - t0

    rows = []
    t0 = time.perf_counter()
    for t in query_ts:
        d2_enc = encrypted_distance_sq(enc_a, enc_b, t)
        scaled = (d2_enc - threshold_sq) * (1.0 / SCALE_KM2)
        flag_enc = scaled.polyval(coeffs)
        flag = flag_enc.decrypt()[0]
        rows.append(flag)
    t_eval = time.perf_counter() - t0

    with open("oem-conjunction/results/multi_approach_c_flags.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cluster_index", "t_offset_s", "raw_flag", "below_threshold_flagged"])
        for ci, t, flag in zip(cluster_of, query_ts, rows):
            w.writerow([ci, t, flag, int(flag < 0)])

    n = len(query_ts)
    n_flagged = sum(1 for f in rows if f < 0)
    print(f"context setup: {t_ctx*1000:.1f} ms   encrypt: {t_enc*1000:.1f} ms")
    print(f"evaluate {n} candidate times across {len(clusters)} clusters: {t_eval*1000:.1f} ms")
    print(f"points flagged below {THRESHOLD_KM} km threshold: {n_flagged} / {n}")

    print("\nper-cluster minimum |flag| (closest approach to the 0 decision boundary):")
    for ci in range(len(clusters)):
        cluster_flags = [f for c, f in zip(cluster_of, rows) if c == ci]
        best = min(cluster_flags, key=abs)
        verdict = "FLAGGED below threshold" if best < 0 else "not flagged"
        print(f"  cluster {ci} (t={clusters[ci]:+9.1f}s): min|flag|={abs(best):.4f}  {verdict}")


if __name__ == "__main__":
    main()
