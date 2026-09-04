"""Approach C: thresholded disclosure. Instead of decrypting the raw
distance_sq(t) curve (Approach B), compute (distance_sq(t) - threshold^2),
scale it into [-1, 1], and evaluate the offline-fitted sign-approximation
polynomial (03_fit_sign_polynomial.py) homomorphically. Only the resulting
~ +-1 flag per candidate time is ever decrypted -- never a distance value.

This is the practical, CDM-style version: "was there a close approach
below the safety threshold, and roughly when" -- without ever revealing
the miss distance or the trajectory shape behind it.

Run: python3 oem-conjunction/04_approach_c_thresholded_flags.py
"""
import csv
import json
import math
import time

from common import load_oem
from crypto_common import make_context, encrypt_oem, encrypted_distance_sq

WINDOW_S = 300
GRID_STEP_S = 10.0
THRESHOLD_KM = 10.0

# Scale so that (d2 - threshold^2) / SCALE lands within [-1, 1] over the
# window we actually expect distances to range over -- the fitted sign
# polynomial is only valid on that domain; anything larger overflows it.
# Chosen from the plaintext reference curve's observed max (~4.89e6 km^2
# at the window edges, this scenario's relative velocity is high enough
# that distance grows fast away from the conjunction). This is a public,
# chosen-in-advance operating parameter, not derived from the encrypted
# data, and it comes with a real cost: see the report for how it crushes
# resolution near the actual decision boundary.
SCALE_KM2 = 5_000_000.0


def load_sign_poly():
    with open("oem-conjunction/data/sign_poly_coeffs.json") as f:
        data = json.load(f)
    return data["coeffs"]


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
    rows = []
    t0 = time.perf_counter()
    for i in range(n):
        t = -WINDOW_S + i * GRID_STEP_S
        d2_enc = encrypted_distance_sq(enc_a, enc_b, t)
        scaled = (d2_enc - threshold_sq) * (1.0 / SCALE_KM2)
        flag_enc = scaled.polyval(coeffs)
        flag = flag_enc.decrypt()[0]
        rows.append((t, flag))
        print(f"  [{i+1}/{n}] t={t:+.1f}s  flag={flag:+.6f}  below={int(flag < 0)}", flush=True)
    t_eval = time.perf_counter() - t0

    with open("oem-conjunction/results/approach_c_flags.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_offset_s", "raw_flag", "below_threshold_flagged"])
        for t, flag in rows:
            w.writerow([t, flag, int(flag < 0)])

    n_flagged = sum(1 for _, flag in rows if flag < 0)
    print(f"context setup: {t_ctx*1000:.1f} ms   encrypt: {t_enc*1000:.1f} ms")
    print(f"evaluate {n} candidate times: {t_eval*1000:.1f} ms  ({t_eval/n*1000:.2f} ms/point)")
    print(f"grid points flagged below {THRESHOLD_KM} km threshold: {n_flagged} / {n}")
    min_abs_near_boundary = min(abs(f) for _, f in rows)
    print(f"closest raw flag value got to the 0 decision boundary: {min_abs_near_boundary:.6e}"
          f" (further from 0 = higher confidence in the flag)")


if __name__ == "__main__":
    main()
