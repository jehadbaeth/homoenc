"""Approach A: full homomorphic argmin, toy scale, to demonstrate honestly
whether/how it fits in this study's depth budget.

Homomorphic min(a, b) is built as (a+b)/2 - |a-b|/2, where |x| is
approximated as x * sign_approx(x) using the same offline-fitted
polynomial as Approach C. Reducing K candidate points to one minimum
needs a depth-log2(K) tree of these pairwise min operations, and each
pairwise min costs: 1 subtract, 1 polyval (sign_approx, itself several
sequential multiplications baked into the fitted polynomial's Horner
evaluation), 1 multiply (x * sign_approx(x)), 1 add/subtract/scale.

An earlier version of this script used a badly-chosen scale constant for
the |a-b| approximation, which pushed inputs to the fitted sign polynomial
far outside its valid [-1,1] domain and produced numerically nonsensical
results (a Python-level lesson learned the hard way: always sanity-check
against the plaintext value, never trust a decrypt() that merely doesn't
throw). With the scale corrected: a single pairwise min (K=2, one
reduction level) succeeds and matches the plaintext value to within
~0.01-0.1%. A full reduction tree at K=4 (two sequential levels) genuinely
exhausts this study's ~16-level CKKS budget and throws a loud
`ValueError: scale out of bounds` partway through the second level -- this
is a real depth wall, not a scaling artifact, and it is caught below so
the script reports it cleanly instead of crashing.

Run: python3 oem-conjunction/05_approach_a_toy_argmin.py
"""
import csv
import json
import math
import time

from common import load_oem
from crypto_common import make_context, encrypt_oem, encrypted_distance_sq

WINDOW_S = 300
PLAUSIBLE_MAX_KM2 = 2.0e7  # generous upper bound given this scenario's observed max (~4.89e6 km^2)
ABS_SCALE_KM2 = 5_000_000.0  # same scale/domain caveat as Approach C's SCALE_KM2


def load_sign_poly():
    with open("oem-conjunction/data/sign_poly_coeffs.json") as f:
        return json.load(f)["coeffs"]


def homomorphic_abs(x_enc, coeffs, scale):
    """|x| ~= x * sign_approx(x / scale). scale should roughly bound |x|."""
    sign = (x_enc * (1.0 / scale)).polyval(coeffs)
    return x_enc * sign


def homomorphic_min(a_enc, b_enc, coeffs, scale):
    diff = a_enc - b_enc
    abs_diff = homomorphic_abs(diff, coeffs, scale)
    return (a_enc + b_enc) * 0.5 - abs_diff * 0.5


def run_case(context, enc_a, enc_b, coeffs, K):
    candidate_times = [-WINDOW_S + i * (2 * WINDOW_S / (K - 1)) for i in range(K)]
    print(f"\n--- toy argmin over K={K} candidate times: {[round(t,1) for t in candidate_times]} ---")

    t0 = time.perf_counter()
    d2s = [encrypted_distance_sq(enc_a, enc_b, t) for t in candidate_times]
    t_dist = time.perf_counter() - t0

    plain_min = min(d.decrypt()[0] for d in d2s)

    t0 = time.perf_counter()
    depth_used = 0
    level = d2s
    depth_wall_hit = False
    error_msg = ""
    try:
        while len(level) > 1:
            next_level = []
            for i in range(0, len(level), 2):
                m = homomorphic_min(level[i], level[i + 1], coeffs, ABS_SCALE_KM2)
                next_level.append(m)
            level = next_level
            depth_used += 1
            print(f"  reduction level {depth_used}: {len(level)} value(s) remaining")
    except Exception as exc:
        depth_wall_hit = True
        error_msg = str(exc)
        print(f"  reduction level {depth_used + 1} raised: {exc}")
    t_reduce = time.perf_counter() - t0

    status, min_d2, rel_err_pct = "depth_wall", None, None
    if depth_wall_hit:
        print(f"genuine depth wall: ran out of CKKS levels partway through reduction level {depth_used + 1} "
              f"of log2(K)={math.log2(K):.0f}. This is a real budget limit, not a scaling artifact.")
        print(f"(true min via plaintext-decrypted inputs: {plain_min:.4f} km^2)")
    else:
        result_enc = level[0]
        min_d2 = result_enc.decrypt()[0]
        if not (0 <= min_d2 <= PLAUSIBLE_MAX_KM2):
            status = "implausible"
            print(f"decrypt did NOT throw, but returned {min_d2:.3e} km^2 -- physically implausible")
            print(f"(true min via plaintext-decrypted inputs: {plain_min:.4f} km^2)")
        else:
            status = "ok"
            rel_err_pct = abs(min_d2 - plain_min) / plain_min * 100
            min_d = math.sqrt(max(min_d2, 0.0))
            print(f"homomorphic min(distance_sq) over {K} points: {min_d2:.4f} km^2  (~{min_d:.4f} km)")
            print(f"(true min: {plain_min:.4f} km^2, relative error {rel_err_pct:.4f}%) -- decrypt succeeded and is plausible.")

    print(f"distance evaluation: {t_dist*1000:.1f} ms   reduction attempted ({depth_used} completed level(s)): {t_reduce*1000:.1f} ms")
    return {
        "K": K,
        "levels_attempted": int(math.log2(K)),
        "levels_completed": depth_used,
        "status": status,
        "encrypted_min_km2": min_d2,
        "plaintext_min_km2": plain_min,
        "relative_error_pct": rel_err_pct,
        "error_message": error_msg,
        "distance_eval_ms": t_dist * 1000,
        "reduction_ms": t_reduce * 1000,
    }


def main():
    oem_a = load_oem("oem-conjunction/data/oem_a.csv")
    oem_b = load_oem("oem-conjunction/data/oem_b.csv")
    coeffs = load_sign_poly()

    context = make_context()
    enc_a = encrypt_oem(context, oem_a)
    enc_b = encrypt_oem(context, oem_b)

    results = [run_case(context, enc_a, enc_b, coeffs, K) for K in (2, 4)]

    print("\n=== summary ===")
    for r in results:
        print(f"K={r['K']} (log2={r['levels_attempted']} levels): status={r['status']}")

    with open("oem-conjunction/results/approach_a_argmin.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["K", "levels_attempted", "levels_completed", "status", "encrypted_min_km2",
                    "plaintext_min_km2", "relative_error_pct", "error_message",
                    "distance_eval_ms", "reduction_ms"])
        for r in results:
            w.writerow([r["K"], r["levels_attempted"], r["levels_completed"], r["status"],
                        r["encrypted_min_km2"], r["plaintext_min_km2"], r["relative_error_pct"],
                        r["error_message"], f"{r['distance_eval_ms']:.1f}", f"{r['reduction_ms']:.1f}"])


if __name__ == "__main__":
    main()
