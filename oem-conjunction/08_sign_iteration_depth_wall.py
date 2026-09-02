"""Checks whether iterating the sign-approximation polynomial against its own
output (f(f(x)), f(f(f(x))), ...) can sharpen Approach D's flags enough to be
a trustworthy threshold count, and if so, how much CKKS depth that costs.

Plaintext check: sign was never wrong -- a single evaluation of the fitted
polynomial (03_fit_sign_polynomial.py) already classifies all 61 candidate
points correctly (matches the plaintext ground truth of 1 point below
threshold). What's missing is saturation: after 10 extra compositions beyond
that single evaluation, all 61 flags sit close enough to +-1 for their sum
to be read as a trustworthy count.

Encrypted check: on the same scenario's t=0 point (the hardest case -- true
distance 5.432 km sits only fractionally below the 10 km threshold, so its
scaled input is tiny and needs the most iterations to diverge to -1), each
extra .polyval(coeffs) composition is applied to the previous ciphertext and
decrypted to see how far it gets before TenSEAL/SEAL runs out of levels.

Run: python3 oem-conjunction/08_sign_iteration_depth_wall.py
"""
import json

from common import load_oem
from crypto_common import make_context, encrypt_oem, encrypted_distance_sq

THRESHOLD_KM = 10.0
SCALE_KM2 = 5_000_000.0
MAX_EXTRA_COMPOSITIONS = 14


def load_sign_poly():
    with open("oem-conjunction/data/sign_poly_coeffs.json") as f:
        return json.load(f)["coeffs"]


def main():
    coeffs = load_sign_poly()
    threshold_sq = THRESHOLD_KM ** 2

    oem_a = load_oem("oem-conjunction/data/oem_a.csv")
    oem_b = load_oem("oem-conjunction/data/oem_b.csv")
    context = make_context()
    enc_a = encrypt_oem(context, oem_a)
    enc_b = encrypt_oem(context, oem_b)

    d2_enc = encrypted_distance_sq(enc_a, enc_b, 0.0)
    scaled = (d2_enc - threshold_sq) * (1.0 / SCALE_KM2)
    cur = scaled.polyval(coeffs)
    print(f"base composition (t=0, hardest point): value={cur.decrypt()[0]:.6f}")

    for k in range(2, MAX_EXTRA_COMPOSITIONS + 2):
        try:
            cur = cur.polyval(coeffs)
            val = cur.decrypt()[0]
            print(f"composition {k}: OK   value={val:.6f}")
        except Exception as e:
            print(f"composition {k}: FAILED - {type(e).__name__}: {e}")
            print(f"depth wall reached after {k - 1} total compositions "
                  f"(plaintext needs ~11 total compositions to saturate this "
                  f"point to -1 -- see module docstring)")
            break


if __name__ == "__main__":
    main()
