"""Approach B: homomorphic interpolation + squared-distance curve.

Both OEMs are encrypted once (three CKKS vectors each: x, y, z sample
arrays). For every candidate time in a public grid, the interpolated
position of each object is a plaintext-weighted sum of the encrypted
samples (TenSEAL's dot()), so it never needs the sample values in the
clear -- only the sample *times*, which are public. Squared distance is
then two ciphertext subtractions and three ciphertext-ciphertext squarings
per candidate time.

Only the resulting distance_sq(t) scalars are decrypted -- never the
underlying position samples. The full curve is still a real disclosure
(see the report), which is the whole point of separating this from
Approach C.

Run: python3 oem-conjunction/02_approach_b_encrypted_distance_curve.py
"""
import csv
import math
import time

from common import load_oem
from crypto_common import make_context, encrypt_oem, encrypted_distance_sq

WINDOW_S = 300
GRID_STEP_S = 10.0


def main():
    oem_a = load_oem("oem-conjunction/data/oem_a.csv")
    oem_b = load_oem("oem-conjunction/data/oem_b.csv")

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
        d2 = d2_enc.decrypt()[0]
        rows.append((t, d2))
    t_eval = time.perf_counter() - t0

    best_t, best_d2 = min(rows, key=lambda r: r[1])

    with open("oem-conjunction/results/approach_b_distance_curve.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_offset_s", "distance_sq_km2", "distance_km"])
        for t, d2 in rows:
            w.writerow([t, d2, math.sqrt(max(d2, 0.0))])

    print(f"context setup (incl. galois keys): {t_ctx*1000:.1f} ms")
    print(f"encrypt both OEMs (6 vectors):      {t_enc*1000:.1f} ms")
    print(f"evaluate {n} candidate times:        {t_eval*1000:.1f} ms  ({t_eval/n*1000:.2f} ms/point)")
    print(f"encrypted-approach CPA estimate: t={best_t:+.1f}s  miss_distance={math.sqrt(best_d2):.4f} km")


if __name__ == "__main__":
    main()
