"""Performance benchmark for the OEM conjunction pipeline, mirroring
benchmarks/python_benchmark.py's format (same CKKS context, same
mean/median/min/max/p95 timing table) so the two studies are directly
comparable.

Run: PYTHONPATH=oem-conjunction python3 oem-conjunction/benchmark.py \
     > oem-conjunction/results/benchmark_latency.csv
Peak RSS reported to stderr via resource.getrusage (bytes on macOS, KB on
Linux -- collected on macOS/arm64, same host as the SGP4 study's numbers).
"""
import json
import math
import resource
import sys
import time

from common import load_oem
from crypto_common import make_context, encrypt_oem, encrypted_interpolate, encrypted_distance_sq

WARMUP = 1
REPS = 5  # each rep here does real CKKS work costing several seconds; keep this low
THRESHOLD_KM = 10.0
SCALE_KM2 = 5_000_000.0


def load_sign_poly():
    with open("oem-conjunction/data/sign_poly_coeffs.json") as f:
        return json.load(f)["coeffs"]


def time_op(name, op, reps=REPS, warmup=WARMUP):
    for _ in range(warmup):
        op()
    samples = []
    for _ in range(reps):
        t0 = time.perf_counter()
        op()
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    n = len(samples)
    mean = sum(samples) / n
    median = samples[n // 2]
    p95 = samples[min(n - 1, math.ceil(n * 0.95) - 1)]
    print(f"{name},{n},{mean:.4f},{median:.4f},{samples[0]:.4f},{samples[-1]:.4f},{p95:.4f}")


def main():
    print("operation,n,mean_ms,median_ms,min_ms,max_ms,p95_ms")

    oem_a = load_oem("oem-conjunction/data/oem_a.csv")
    oem_b = load_oem("oem-conjunction/data/oem_b.csv")
    coeffs = load_sign_poly()
    threshold_sq = THRESHOLD_KM ** 2

    context_times = []
    context = None
    for _ in range(3):
        t0 = time.perf_counter()
        context = make_context()
        context_times.append((time.perf_counter() - t0) * 1000)
    context_times.sort()
    n = len(context_times)
    print(f"context_setup_incl_keygen,{n},{sum(context_times)/n:.4f},{context_times[n//2]:.4f},"
          f"{context_times[0]:.4f},{context_times[-1]:.4f},{context_times[min(n-1, math.ceil(n*0.95)-1)]:.4f}")

    time_op("encrypt_oem_3vectors", lambda: encrypt_oem(context, oem_a), reps=10, warmup=2)

    enc_a = encrypt_oem(context, oem_a)
    enc_b = encrypt_oem(context, oem_b)

    time_op("encrypted_interpolate_one_point", lambda: encrypted_interpolate(enc_a, 0.0))
    time_op("encrypted_distance_sq_one_point", lambda: encrypted_distance_sq(enc_a, enc_b, 0.0))

    d2_sample = encrypted_distance_sq(enc_a, enc_b, 0.0)
    time_op("decrypt_distance_sq", lambda: d2_sample.decrypt())

    time_op("approach_b_distance_sq_plus_decrypt",
            lambda: encrypted_distance_sq(enc_a, enc_b, 0.0).decrypt())

    def approach_c_point():
        d2_enc = encrypted_distance_sq(enc_a, enc_b, 0.0)
        scaled = (d2_enc - threshold_sq) * (1.0 / SCALE_KM2)
        flag_enc = scaled.polyval(coeffs)
        return flag_enc.decrypt()

    time_op("approach_c_scaled_polyval_sign_plus_decrypt", approach_c_point)

    a_pt = encrypted_distance_sq(enc_a, enc_b, -300.0)
    b_pt = encrypted_distance_sq(enc_a, enc_b, 300.0)

    def homomorphic_min():
        diff = a_pt - b_pt
        sign = (diff * (1.0 / SCALE_KM2)).polyval(coeffs)
        abs_diff = diff * sign
        return (a_pt + b_pt) * 0.5 - abs_diff * 0.5

    time_op("approach_a_pairwise_homomorphic_min", homomorphic_min, reps=10, warmup=2)

    min_result = homomorphic_min()
    time_op("decrypt_scalar", lambda: min_result.decrypt())

    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_bytes = peak_rss if sys.platform == "darwin" else peak_rss * 1024
    print(f"# peak_rss_bytes={peak_rss_bytes}", file=sys.stderr)
    print(f"# fresh_oem_vector_bytes={len(enc_a['x'].serialize())}", file=sys.stderr)
    print(f"# distance_sq_ciphertext_bytes={len(d2_sample.serialize())}", file=sys.stderr)


if __name__ == "__main__":
    main()
