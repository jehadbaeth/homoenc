"""Offline step for Approach C: fit a polynomial approximation of the sign
function, the same "fit offline in plaintext, evaluate homomorphically"
pattern the original SGP4 study used for Kepler's equation.

We need an odd, smooth approximation of sign(x) on a bounded, known input
range. Following Cheon et al.'s composable minimax approach, iterating
g(x) = (3x - x^3) / 2 sharpens an approximation of sign(x) on [-1, 1] with
each application (it's a contraction towards +-1 away from 0). We fit a
single polynomial to k compositions of g so the homomorphic side pays for
one Horner evaluation instead of k sequential ciphertext multiplications
of the raw composition (cheaper: one polyval call of the *composed*
polynomial, whose coefficients we compute here once, offline, in plaintext).

Run: python3 oem-conjunction/03_fit_sign_polynomial.py
"""
import json

import numpy as np

COMPOSITIONS = 3   # sharper = better step, but higher resulting polynomial degree
DEGREE = 3 ** COMPOSITIONS  # composing degree-3 maps COMPOSITIONS times


def g(x):
    return (3 * x - x ** 3) / 2


def composed_sign_approx(x, k=COMPOSITIONS):
    for _ in range(k):
        x = g(x)
    return x


def fit_polynomial(domain=(-1.0, 1.0), n_samples=4000, degree=DEGREE):
    xs = np.linspace(domain[0], domain[1], n_samples)
    ys = composed_sign_approx(xs)
    coeffs = np.polyfit(xs, ys, degree)[::-1]  # ascending order, like the rest of this repo
    return coeffs.tolist()


def main():
    coeffs = fit_polynomial()
    with open("oem-conjunction/data/sign_poly_coeffs.json", "w") as f:
        json.dump({"degree": len(coeffs) - 1, "compositions": COMPOSITIONS, "coeffs": coeffs}, f, indent=2)

    # sanity check the fit against the raw composed function
    xs = np.linspace(-1, 1, 21)
    raw = composed_sign_approx(xs)
    fitted = np.polyval(list(reversed(coeffs)), xs)
    max_err = float(np.max(np.abs(raw - fitted)))
    print(f"fit degree {len(coeffs)-1} polynomial to {COMPOSITIONS}x composed sign-approx")
    print(f"max fit-vs-raw-composition error on [-1,1]: {max_err:.2e}")
    print(f"approx(0.02)={composed_sign_approx(0.02):.4f}  approx(-0.02)={composed_sign_approx(-0.02):.4f}"
          f"  approx(0.3)={composed_sign_approx(0.3):.4f}  approx(1.0)={composed_sign_approx(1.0):.4f}")


if __name__ == "__main__":
    main()
