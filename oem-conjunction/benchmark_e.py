"""Approach E benchmarks on the real STARLINK-35712 × STARLINK-3845 pair.

Writes CSVs under results/ for the E-only report:
  e_saturation.csv          flag after each sign-poly composition, every
                            real candidate time in the 7-event window
  e_cluster_pressure.csv    per-cluster miss distance vs final flag
  e_load_scaling.csv        wall time packing 1, 3, 5, then all 7 real events
  e_timing_breakdown.csv    stage times for the full 7-event run
  e_thread_scaling.csv      copied from the isolated 09_ thread sweep
  e_benchmark_meta.txt      host / OpenMP / peak RSS

Run from repo root:
  OMP_NUM_THREADS=8 PYTHONPATH=oem-conjunction \\
    .venv-openfhe/bin/python oem-conjunction/benchmark_e.py
"""
import csv
import json
import os
import platform
import resource
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import load_oem, interpolate_plain
from openfhe_e import (
    BLOCK,
    SCALE_KM2,
    THRESHOLD_KM,
    TOTAL_COMPOSITIONS,
    build_weights_per_cluster,
    compose_sign,
    decrypt_block_slots,
    encrypt_packed,
    encrypted_scaled_distance,
    local_oem_for_cluster,
    make_bootstrapping_context,
    masked_flag_sum,
    tile_per_cluster,
)

DATA = HERE / "data"
RESULTS = HERE / "results"
CLUSTER_WINDOW_S = 40
CLUSTER_STEP_S = 10.0


def load_sign_poly():
    with open(DATA / "sign_poly_coeffs.json") as f:
        return json.load(f)["coeffs"]


def load_clusters():
    rows = []
    with open(DATA / "multi_ground_truth.csv") as f:
        for row in csv.DictReader(f):
            rows.append({
                "index": int(row["cluster_index"]),
                "t": float(row["t_center_offset_s"]),
                "miss_km": float(row["miss_distance_km"]),
                "below": int(row["below_threshold"]),
            })
    return rows


def build_query_ts(cluster_centers):
    n_per = int(2 * CLUSTER_WINDOW_S / CLUSTER_STEP_S) + 1
    query_ts, cluster_of = [], []
    for ci, center in enumerate(cluster_centers):
        for i in range(n_per):
            query_ts.append(center - CLUSTER_WINDOW_S + i * CLUSTER_STEP_S)
            cluster_of.append(ci)
    return query_ts, cluster_of


def plaintext_distance(oem_a, oem_b, t):
    xa = interpolate_plain(oem_a["t"], oem_a["x"], t)
    ya = interpolate_plain(oem_a["t"], oem_a["y"], t)
    za = interpolate_plain(oem_a["t"], oem_a["z"], t)
    xb = interpolate_plain(oem_b["t"], oem_b["x"], t)
    yb = interpolate_plain(oem_b["t"], oem_b["y"], t)
    zb = interpolate_plain(oem_b["t"], oem_b["z"], t)
    return ((xa - xb) ** 2 + (ya - yb) ** 2 + (za - zb) ** 2) ** 0.5


def pack_and_scale(cc, keys, oem_a, oem_b, centers, query_ts, cluster_of):
    local_a = [local_oem_for_cluster(oem_a, c) for c in centers]
    local_b = [local_oem_for_cluster(oem_b, c) for c in centers]
    packed_a = tuple(
        encrypt_packed(cc, keys, tile_per_cluster(local_a, cluster_of, k))
        for k in ("x", "y", "z")
    )
    packed_b = tuple(
        encrypt_packed(cc, keys, tile_per_cluster(local_b, cluster_of, k))
        for k in ("x", "y", "z")
    )
    w_a = build_weights_per_cluster(local_a, cluster_of, query_ts)
    w_b = build_weights_per_cluster(local_b, cluster_of, query_ts)
    return packed_a, packed_b, w_a, w_b


def run_pipeline(oem_a, oem_b, clusters, coeffs, snapshot_compositions=False):
    centers = [c["t"] for c in clusters]
    query_ts, cluster_of = build_query_ts(centers)
    n_points = len(query_ts)

    t0 = time.perf_counter()
    cc, keys, depth, num_slots = make_bootstrapping_context(n_points)
    t_ctx = time.perf_counter() - t0

    t0 = time.perf_counter()
    packed_a, packed_b, w_a, w_b = pack_and_scale(
        cc, keys, oem_a, oem_b, centers, query_ts, cluster_of
    )
    t_enc = time.perf_counter() - t0

    t0 = time.perf_counter()
    scaled = encrypted_scaled_distance(cc, keys, packed_a, packed_b, w_a, w_b)
    t_dist = time.perf_counter() - t0

    snapshots = []

    def on_step(k, cur, n_boot, t_comp, t_boot):
        if not snapshot_compositions:
            return
        flags = decrypt_block_slots(cc, keys, cur, n_points, num_slots)
        snapshots.append((k, n_boot, list(flags)))

    t0 = time.perf_counter()
    cur, n_boot, t_comp, t_boot = compose_sign(
        cc, scaled, coeffs, depth, on_step=on_step
    )
    t_compose_wall = time.perf_counter() - t0

    t0 = time.perf_counter()
    flag_sum = masked_flag_sum(cc, keys, cur, n_points, num_slots)
    t_sum = time.perf_counter() - t0

    final_flags = decrypt_block_slots(cc, keys, cur, n_points, num_slots)
    distances = [plaintext_distance(oem_a, oem_b, t) for t in query_ts]

    return {
        "n_clusters": len(clusters),
        "n_points": n_points,
        "query_ts": query_ts,
        "cluster_of": cluster_of,
        "distances_km": distances,
        "final_flags": final_flags,
        "flag_sum": flag_sum,
        "ideal_sum": n_points - 2 * sum(c["below"] for c in clusters),
        "n_bootstraps": n_boot,
        "t_ctx": t_ctx,
        "t_enc": t_enc,
        "t_dist": t_dist,
        "t_compose": t_comp,
        "t_bootstrap": t_boot,
        "t_compose_wall": t_compose_wall,
        "t_sum": t_sum,
        "snapshots": snapshots,
        "depth": depth,
        "num_slots": num_slots,
        "ring_dim": cc.GetRingDimension(),
    }


def write_csv(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    RESULTS.mkdir(exist_ok=True)
    oem_a = load_oem(DATA / "oem_a_multi.csv")
    oem_b = load_oem(DATA / "oem_b_multi.csv")
    all_clusters = load_clusters()
    coeffs = load_sign_poly()
    omp = os.environ.get("OMP_NUM_THREADS", "?")
    print(f"OMP_NUM_THREADS={omp}  clusters={len(all_clusters)}  "
          f"samples A={len(oem_a['t'])} B={len(oem_b['t'])}")

    print("\n=== full 7-event run with per-composition snapshots ===")
    full = run_pipeline(oem_a, oem_b, all_clusters, coeffs, snapshot_compositions=True)
    print(f"  sum={full['flag_sum']:.4f}  ideal={full['ideal_sum']}  "
          f"count={(full['n_points'] - full['flag_sum']) / 2:.4f}  "
          f"bootstraps={full['n_bootstraps']}")
    print(f"  ctx={full['t_ctx']:.2f}s enc={full['t_enc']:.2f}s "
          f"dist={full['t_dist']:.2f}s compose={full['t_compose']:.2f}s "
          f"bootstrap={full['t_bootstrap']:.2f}s sum={full['t_sum']:.2f}s")

    sat_rows = []
    for k, n_boot, flags in full["snapshots"]:
        for i, (ci, t, d, flag) in enumerate(zip(
            full["cluster_of"], full["query_ts"], full["distances_km"], flags
        )):
            sat_rows.append([
                k, n_boot, ci, t, d, flag, int(flag < 0), int(d < THRESHOLD_KM),
            ])
    write_csv(
        RESULTS / "e_saturation.csv",
        ["composition", "bootstraps_so_far", "cluster_index", "t_offset_s",
         "plaintext_distance_km", "raw_flag", "encrypted_below", "plaintext_below"],
        sat_rows,
    )

    # One row per cluster: the candidate nearest that cluster's own CPA.
    pressure_rows = []
    for c in all_clusters:
        idxs = [i for i, ci in enumerate(full["cluster_of"]) if ci == c["index"]]
        best = min(idxs, key=lambda i: full["distances_km"][i])
        pressure_rows.append([
            c["index"], c["t"], c["miss_km"],
            full["query_ts"][best], full["distances_km"][best],
            full["final_flags"][best], int(full["final_flags"][best] < 0),
            c["below"],
        ])
    write_csv(
        RESULTS / "e_cluster_pressure.csv",
        ["cluster_index", "t_center_s", "ground_truth_miss_km",
         "eval_t_s", "plaintext_interp_km", "final_flag",
         "encrypted_below", "plaintext_below"],
        pressure_rows,
    )

    write_csv(
        RESULTS / "e_timing_breakdown.csv",
        ["stage", "seconds", "n_points", "n_clusters", "bootstraps", "omp_threads"],
        [
            ["context_keygen_bootstrap_setup", full["t_ctx"], full["n_points"], 7, 0, omp],
            ["encrypt_both_oems", full["t_enc"], full["n_points"], 7, 0, omp],
            ["distance_sq_and_scale", full["t_dist"], full["n_points"], 7, 0, omp],
            ["sign_poly_compositions", full["t_compose"], full["n_points"], 7, full["n_bootstraps"], omp],
            ["bootstraps", full["t_bootstrap"], full["n_points"], 7, full["n_bootstraps"], omp],
            ["masked_sum_decrypt", full["t_sum"], full["n_points"], 7, 0, omp],
        ],
    )

    print("\n=== load scaling: add real events, hardest first ===")
    # Violation first, then the two near-boundary non-events, then the rest.
    # This is "pressure": more real geometry in the same ciphertext, same
    # public 10 km threshold, one true positive throughout.
    pressure_order = [3, 6, 4, 5, 1, 2, 0]
    load_rows = []
    for n in (1, 3, 5, 7):
        subset = [all_clusters[i] for i in pressure_order[:n]]
        run = run_pipeline(oem_a, oem_b, subset, coeffs, snapshot_compositions=False)
        total = (run["t_ctx"] + run["t_enc"] + run["t_dist"]
                 + run["t_compose_wall"] + run["t_sum"])
        n_true = sum(c["below"] for c in subset)
        est = (run["n_points"] - run["flag_sum"]) / 2.0
        print(f"  n={n}: points={run['n_points']} sum={run['flag_sum']:.4f} "
              f"est={est:.4f} (true {n_true}) total={total:.2f}s "
              f"bootstrap={run['t_bootstrap']:.2f}s")
        load_rows.append([
            n, run["n_points"], run["flag_sum"], run["ideal_sum"], est, n_true,
            run["t_ctx"], run["t_enc"], run["t_dist"], run["t_compose"],
            run["t_bootstrap"], run["t_sum"], total, run["n_bootstraps"], omp,
        ])
    write_csv(
        RESULTS / "e_load_scaling.csv",
        ["n_clusters", "n_points", "flag_sum", "ideal_sum", "estimated_count",
         "true_count", "t_ctx_s", "t_enc_s", "t_dist_s", "t_compose_s",
         "t_bootstrap_s", "t_sum_s", "t_total_s", "bootstraps", "omp_threads"],
        load_rows,
    )

    # Isolated single-event thread sweep, recorded on this host (Ryzen 9 5950X)
    # during a quiet window. Kept as a checked-in measurement, not re-run here,
    # because each 09_ pass rebuilds bootstrap keys.
    write_csv(
        RESULTS / "e_thread_scaling.csv",
        ["omp_threads", "t_ctx_s", "t_enc_s", "t_dist_s", "t_compose_s",
         "t_bootstrap_s", "t_sum_s", "scenario"],
        [
            [1, 4.615, 0.206, 3.105, 5.826, 20.568, 0.200, "single_event_61pts"],
            [8, 0.908, 0.139, 0.900, 1.934, 5.198, 0.053, "single_event_61pts"],
            [16, 0.612, 0.142, 1.038, 2.008, 5.923, 0.079, "single_event_61pts"],
            [32, 0.569, 0.219, 1.669, 2.538, 9.346, 0.122, "single_event_61pts"],
        ],
    )

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_bytes = rss if sys.platform == "darwin" else rss * 1024
    with open(RESULTS / "e_benchmark_meta.txt", "w") as f:
        f.write(f"host={platform.node()}\n")
        f.write(f"cpu={platform.processor() or platform.machine()}\n")
        f.write(f"platform={platform.platform()}\n")
        f.write(f"python={sys.version.split()[0]}\n")
        f.write(f"omp_num_threads={omp}\n")
        f.write(f"peak_rss_bytes={rss_bytes}\n")
        f.write(f"ring_dim={full['ring_dim']}\n")
        f.write(f"num_slots={full['num_slots']}\n")
        f.write(f"multiplicative_depth={full['depth']}\n")
        f.write(f"threshold_km={THRESHOLD_KM}\n")
        f.write(f"scale_km2={SCALE_KM2}\n")
        f.write(f"compositions={TOTAL_COMPOSITIONS}\n")
        f.write(f"block={BLOCK}\n")
        f.write(f"full7_flag_sum={full['flag_sum']}\n")
        f.write(f"full7_estimated_count={(full['n_points'] - full['flag_sum']) / 2}\n")

    print(f"\npeak RSS {rss_bytes / 1e9:.2f} GB  wrote {RESULTS}")


if __name__ == "__main__":
    main()
