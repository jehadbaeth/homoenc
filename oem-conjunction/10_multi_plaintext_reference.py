"""Scenario 2, stage 1: plaintext cross-match reference for the multi-event
scenario. Same algorithm as 01_plaintext_reference.py (local Lagrange
interpolation + squared distance from the OEM samples, exactly what the
encrypted stages compute), but evaluated over SEVEN real close-approach
clusters found by 10_/data/find_multi_cpa_and_build_oems.py instead of one.

Each cluster gets its own +/-40s / 10s-step monitoring window (9 candidate
times), centered on that cluster's own fine-refined approach time -- the
same per-event methodology as the single-event scenario, just repeated for
every real event found in the wider +/-3h search instead of only the global
minimum. Two of the seven clusters (11.698 km and 13.276 km true miss
distance) sit within a few km of the 10 km threshold, which is exactly the
case that stresses whether the interpolation + threshold pipeline still
classifies correctly this close to the boundary.

Run: python3 oem-conjunction/10_multi_plaintext_reference.py
"""
import csv
import math

from common import load_oem, interpolate_plain

CLUSTER_WINDOW_S = 40
CLUSTER_STEP_S = 10.0
THRESHOLD_KM = 10.0


def load_clusters():
    clusters = []
    with open("oem-conjunction/data/multi_ground_truth.csv") as f:
        r = csv.DictReader(f)
        for row in r:
            clusters.append(float(row["t_center_offset_s"]))
    return clusters


def distance_sq_at(oem_a, oem_b, t):
    xa = interpolate_plain(oem_a["t"], oem_a["x"], t)
    ya = interpolate_plain(oem_a["t"], oem_a["y"], t)
    za = interpolate_plain(oem_a["t"], oem_a["z"], t)
    xb = interpolate_plain(oem_b["t"], oem_b["x"], t)
    yb = interpolate_plain(oem_b["t"], oem_b["y"], t)
    zb = interpolate_plain(oem_b["t"], oem_b["z"], t)
    return (xa - xb) ** 2 + (ya - yb) ** 2 + (za - zb) ** 2


def build_query_ts(clusters):
    n_per_cluster = int(2 * CLUSTER_WINDOW_S / CLUSTER_STEP_S) + 1
    query_ts = []
    cluster_of = []
    for ci, center in enumerate(clusters):
        for i in range(n_per_cluster):
            query_ts.append(center - CLUSTER_WINDOW_S + i * CLUSTER_STEP_S)
            cluster_of.append(ci)
    return query_ts, cluster_of


def main():
    oem_a = load_oem("oem-conjunction/data/oem_a_multi.csv")
    oem_b = load_oem("oem-conjunction/data/oem_b_multi.csv")
    clusters = load_clusters()
    query_ts, cluster_of = build_query_ts(clusters)

    rows = []
    for t in query_ts:
        d2 = distance_sq_at(oem_a, oem_b, t)
        rows.append((t, d2))

    with open("oem-conjunction/results/multi_plaintext_distance_curve.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cluster_index", "t_offset_s", "distance_sq_km2", "distance_km", "below_threshold"])
        for (t, d2), ci in zip(rows, cluster_of):
            d = math.sqrt(d2)
            w.writerow([ci, t, d2, d, int(d < THRESHOLD_KM)])

    print(f"{len(clusters)} clusters, {len(query_ts)} total candidate points "
          f"({int(2*CLUSTER_WINDOW_S/CLUSTER_STEP_S)+1} per cluster)")
    per_cluster_min = {}
    for (t, d2), ci in zip(rows, cluster_of):
        d = math.sqrt(d2)
        if ci not in per_cluster_min or d < per_cluster_min[ci][1]:
            per_cluster_min[ci] = (t, d)
    print("per-cluster minimum found by this algorithm (interpolated from the 60s-cadence OEM):")
    n_below = 0
    for ci in sorted(per_cluster_min):
        t, d = per_cluster_min[ci]
        flag = "BELOW threshold" if d < THRESHOLD_KM else "above"
        if d < THRESHOLD_KM:
            n_below += 1
        print(f"  cluster {ci}: t={t:+9.1f}s   miss={d:8.4f} km   {flag}")
    print(f"\ntrue count of clusters below {THRESHOLD_KM} km threshold: {n_below} / {len(clusters)}")


if __name__ == "__main__":
    main()
