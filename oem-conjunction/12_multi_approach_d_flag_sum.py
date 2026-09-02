"""Scenario 2, Approach D: homomorphic flag-sum (see 07_approach_d_flag_sum.py),
no bootstrapping, run over the seven real close-approach clusters from the
wider +/-3h search. Same TenSEAL/SEAL backend, same known saturation limit
(only ~2 extra compositions fit before `scale out of bounds`), now tested
against a scenario with two genuinely near-boundary events (11.698 km and
13.276 km) mixed in with the one true violation (5.432 km) and four clearly
safe events (20-62 km).

Expected outcome, stated up front: this should fail the same way Approach D
failed on the single-event scenario, for the same reason -- unsaturated
flags near the linear region of the sign polynomial don't sum to a
trustworthy count. Run so the failure mode can be shown on a scenario with
more than one real event, not asserted from the simpler case.

Run: python3 oem-conjunction/12_multi_approach_d_flag_sum.py
"""
import csv
import json
import time

from common import load_oem
from crypto_common import make_context, encrypt_oem, encrypted_distance_sq

CLUSTER_WINDOW_S = 40
CLUSTER_STEP_S = 10.0
THRESHOLD_KM = 10.0
SCALE_KM2 = 5_000_000.0


def load_sign_poly():
    with open("oem-conjunction/data/sign_poly_coeffs.json") as f:
        return json.load(f)["coeffs"]


def load_clusters():
    with open("oem-conjunction/data/multi_ground_truth.csv") as f:
        return [float(row["t_center_offset_s"]) for row in csv.DictReader(f)]


def build_query_ts(clusters):
    n_per_cluster = int(2 * CLUSTER_WINDOW_S / CLUSTER_STEP_S) + 1
    query_ts = []
    for center in clusters:
        for i in range(n_per_cluster):
            query_ts.append(center - CLUSTER_WINDOW_S + i * CLUSTER_STEP_S)
    return query_ts


def main():
    oem_a = load_oem("oem-conjunction/data/oem_a_multi.csv")
    oem_b = load_oem("oem-conjunction/data/oem_b_multi.csv")
    coeffs = load_sign_poly()
    threshold_sq = THRESHOLD_KM ** 2
    clusters = load_clusters()
    query_ts = build_query_ts(clusters)
    n = len(query_ts)

    t0 = time.perf_counter()
    context = make_context()
    t_ctx = time.perf_counter() - t0

    t0 = time.perf_counter()
    enc_a = encrypt_oem(context, oem_a)
    enc_b = encrypt_oem(context, oem_b)
    t_enc = time.perf_counter() - t0

    sum_enc = None
    t0 = time.perf_counter()
    for t in query_ts:
        d2_enc = encrypted_distance_sq(enc_a, enc_b, t)
        scaled = (d2_enc - threshold_sq) * (1.0 / SCALE_KM2)
        flag_enc = scaled.polyval(coeffs)
        sum_enc = flag_enc if sum_enc is None else sum_enc + flag_enc
    t_eval = time.perf_counter() - t0

    t0 = time.perf_counter()
    flag_sum = sum_enc.decrypt()[0]
    t_dec = time.perf_counter() - t0

    ideal_sum_if_1_below = n - 2 * 1
    with open("oem-conjunction/results/multi_approach_d_flag_sum.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n_points", "decrypted_flag_sum", "ideal_sum_for_true_count_1", "naive_count_estimate_do_not_trust"])
        w.writerow([n, flag_sum, ideal_sum_if_1_below, round((n - flag_sum) / 2.0)])

    print(f"context setup: {t_ctx*1000:.1f} ms   encrypt: {t_enc*1000:.1f} ms")
    print(f"evaluate + homomorphically sum {n} candidate flags: {t_eval*1000:.1f} ms")
    print(f"single decrypt: {t_dec*1000:.2f} ms")
    print(f"decrypted sum of {n} flags: {flag_sum:.4f}   (ideal for true count 1: {ideal_sum_if_1_below})")
    print(f"naive count estimate (n - sum)/2: {(n - flag_sum) / 2.0:.4f}  (true count: 1)")
    print("as with the single-event scenario, do not trust this naive estimate -- see report.")


if __name__ == "__main__":
    main()
