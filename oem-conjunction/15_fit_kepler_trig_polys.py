"""Offline step for the encrypted-propagation test: fit plaintext
polynomial approximations of sin(E), cos(E) (E = eccentric anomaly) and
sqrt(1-e^2), the only non-polynomial pieces the Kepler solve and position
reconstruction need. Same "fit offline in plaintext, evaluate
homomorphically" pattern as 03_fit_sign_polynomial.py, but sin/cos are
smooth, non-periodic-looking over the bounded domain actually needed here,
so a single least-squares fit works -- no iterated composition required
the way the sign function needed one.

Domain for E: 14_kepler_plaintext_reference.py verified that for
STARLINK-35712's real TLE elements, over the same +/-1800s screening
window Approach E already uses, mean anomaly (and, since e is tiny here,
eccentric anomaly with it) stays within [2.190075, 6.207133] rad without
crossing the 0/2*pi boundary -- so this fits a domain, not the full
circle. A general implementation (arbitrary epoch, wider window) would
need mod-2*pi range reduction first; that's explicitly out of scope here
(see 17_'s module docstring).

The direct monomial fit on the raw domain is poorly conditioned (numpy
warns about it) -- the same numerical-conditioning trap Key Finding 2 of
notes/FHE-HEIR/SGP4 FHE Prototype Findings.md hit. The fix is the same
one used there: rescale the domain to [-1, 1] before fitting.

Run: python3 oem-conjunction/15_fit_kepler_trig_polys.py
"""
import json

import numpy as np

E_DOMAIN = (2.0, 6.35)      # rad; verified bound from 14_, with margin
ECC_DOMAIN = (0.0, 0.005)   # narrow near-circular LEO band (matches the
                             # e in [0, 0.02] range Key Finding 4 found
                             # "basically free" to encrypt)
DEGREE_TRIG = 10
DEGREE_SQRT = 2


def rescale(x, lo, hi):
    return 2 * (x - lo) / (hi - lo) - 1


def fit(f, domain, degree, n_samples=5000):
    lo, hi = domain
    xs = np.linspace(lo, hi, n_samples)
    u = rescale(xs, lo, hi)
    ys = f(xs)
    coeffs = np.polyfit(u, ys, degree)[::-1]  # ascending order, like the rest of this repo
    fitted = np.polyval(list(reversed(coeffs)), u)
    max_err = float(np.max(np.abs(fitted - ys)))
    return coeffs.tolist(), max_err


def main():
    sin_coeffs, sin_err = fit(np.sin, E_DOMAIN, DEGREE_TRIG)
    cos_coeffs, cos_err = fit(np.cos, E_DOMAIN, DEGREE_TRIG)
    sqrt_coeffs, sqrt_err = fit(lambda e: np.sqrt(1 - e ** 2), ECC_DOMAIN, DEGREE_SQRT)

    out = {
        "e_domain": list(E_DOMAIN),
        "ecc_domain": list(ECC_DOMAIN),
        "sin_E": {"degree": DEGREE_TRIG, "coeffs": sin_coeffs, "max_fit_err": sin_err},
        "cos_E": {"degree": DEGREE_TRIG, "coeffs": cos_coeffs, "max_fit_err": cos_err},
        "sqrt_one_minus_e2": {"degree": DEGREE_SQRT, "coeffs": sqrt_coeffs, "max_fit_err": sqrt_err},
    }
    with open("oem-conjunction/data/kepler_trig_poly_coeffs.json", "w") as f:
        json.dump(out, f, indent=2)

    print(f"sin(E) over {E_DOMAIN}, degree {DEGREE_TRIG}: max fit error {sin_err:.3e}")
    print(f"cos(E) over {E_DOMAIN}, degree {DEGREE_TRIG}: max fit error {cos_err:.3e}")
    print(f"sqrt(1-e^2) over {ECC_DOMAIN}, degree {DEGREE_SQRT}: max fit error {sqrt_err:.3e}")
    print("\nwritten: oem-conjunction/data/kepler_trig_poly_coeffs.json")


if __name__ == "__main__":
    main()
