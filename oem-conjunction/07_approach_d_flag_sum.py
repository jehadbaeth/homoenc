"""Approach D: homomorphic flag-sum -- a verified negative result, kept for
the report. Same per-point pipeline as Approach C (encrypted distance_sq ->
scaled -> sign-approximation polynomial -> per-point flag near +-1), but the
61 per-point flag ciphertexts are homomorphically summed before anything is
decrypted. CKKS ciphertext addition costs zero multiplicative depth, so this
adds no cost over Approach C's own per-point evaluation, and only one number
ever leaves the encrypted domain.

That mechanism is verified correct: the homomorphic sum reproduces, to 4
decimal places, the manual sum of Approach C's own decrypted per-point flags
(both come out to 37.3017 for this scenario). But the sum is NOT a usable
proxy for "how many points are below threshold." The fitted sign polynomial
(03_fit_sign_polynomial.py) only saturates to a confident +-1 within about
+-100s of the conjunction; across most of the 300s window it is still
linear-ish (slope ~3.4 near zero, from SCALE_KM2 = 5,000,000). With 1 point
genuinely below threshold, an ideal step function would sum to 61 - 2 = 59;
the actual sum is 37.3, because 45 of the 61 points never saturate. Treating
"(n - sum) / 2" as a count is wrong (it reports 12, not 1) and is not
reported here as a working estimator.

We also checked whether iterating the sign polynomial against its own output
(the standard sharpening trick: f(f(x)) pushes values away from the x=0
fixed point) could fix this without bootstrapping. In plaintext it works --
10 extra compositions correctly classify all 61 points. But under the
current CKKS parameters (TenSEAL/SEAL, ~16 usable levels) only 2 extra
compositions fit before the identical `ValueError: scale out of bounds`
depth wall documented for Approach A (05_approach_a_toy_argmin.py) at K=4.
This is the same structural limit reached from a different direction, not a
new bug: TenSEAL/SEAL CKKS has no bootstrapping, so there is a hard ceiling
on how many nonlinear (nonaddition) stages a single ciphertext can pass
through, and this problem needs more than that ceiling allows to get a
trustworthy encrypted-domain count or comparison across the full window.

What this genuinely demonstrates: the "compute over all N points, decrypt
only one aggregate number, never decrypt per-point flags/distances/times"
control-flow pattern is real and cheap (summation is free). What it does NOT
demonstrate: a trustworthy way to interpret that aggregate as a count or a
threshold decision at this problem's precision, on this backend. Closing
that gap requires either materially fewer required nonlinear compositions
(a coarser, lower-precision question) or a bootstrapping-capable backend
(OpenFHE) so the sign polynomial can be iterated enough times to saturate
confidently across the full window. See report for the OpenFHE feasibility
check (the pip wheel available for this problem is Linux x86_64 only,
mislabeled as universal -- it does not run on this Darwin arm64 machine, so
a real evaluation means building from source).

Run: python3 oem-conjunction/07_approach_d_flag_sum.py
"""
import csv
import json
import time

from common import load_oem
from crypto_common import make_context, encrypt_oem, encrypted_distance_sq

WINDOW_S = 300
GRID_STEP_S = 10.0
THRESHOLD_KM = 10.0
SCALE_KM2 = 5_000_000.0  # same operating parameter as Approach C, see 04 for rationale


def load_sign_poly():
    with open("oem-conjunction/data/sign_poly_coeffs.json") as f:
        return json.load(f)["coeffs"]


def main():
    oem_a = load_oem("oem-conjunction/data/oem_a.csv")
    oem_b = load_oem("oem-conjunction/data/oem_b.csv")
    coeffs = load_sign_poly()
    threshold_sq = THRESHOLD_KM ** 2

    t0 = time.perf_counter()
    context = make_context()
    t_ctx = time.perf_counter() - t0

    t0 = time.perf_counter()
    enc_a = encrypt_oem(context, oem_a)
    enc_b = encrypt_oem(context, oem_b)
    t_enc = time.perf_counter() - t0

    n = int(2 * WINDOW_S / GRID_STEP_S) + 1
    sum_enc = None
    t0 = time.perf_counter()
    for i in range(n):
        t = -WINDOW_S + i * GRID_STEP_S
        d2_enc = encrypted_distance_sq(enc_a, enc_b, t)
        scaled = (d2_enc - threshold_sq) * (1.0 / SCALE_KM2)
        flag_enc = scaled.polyval(coeffs)
        sum_enc = flag_enc if sum_enc is None else sum_enc + flag_enc
    t_eval = time.perf_counter() - t0

    t0 = time.perf_counter()
    flag_sum = sum_enc.decrypt()[0]
    t_dec = time.perf_counter() - t0

    with open("oem-conjunction/results/approach_d_flag_sum.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n_points", "decrypted_flag_sum", "naive_count_estimate_do_not_trust"])
        w.writerow([n, flag_sum, round((n - flag_sum) / 2.0)])

    print(f"context setup: {t_ctx*1000:.1f} ms   encrypt: {t_enc*1000:.1f} ms")
    print(f"evaluate + homomorphically sum {n} candidate flags: {t_eval*1000:.1f} ms"
          f"  ({t_eval/n*1000:.2f} ms/point)")
    print(f"single decrypt: {t_dec*1000:.2f} ms")
    print(f"decrypted sum of {n} flags: {flag_sum:.4f}")
    print("this sum is NOT a reliable count of points below threshold -- see module")
    print("docstring. Only one aggregate number was ever decrypted (zero per-point")
    print("disclosure), but its naive interpretation as a count is wrong at this")
    print("problem's precision on this backend. Do not report the naive estimate.")


if __name__ == "__main__":
    main()
