"""The precision gate before touching OpenFHE at all: run the exact same
sequence of operations the encrypted script (17_) will run -- polynomial
sin/cos instead of math.sin/cos, a Newton-Raphson multiply-only reciprocal
instead of real division -- but in plain floats, no encryption anywhere.
Diff the result against 14_kepler_plaintext_reference.py's exact answer.

This isolates two error sources that look identical from the outside
("the answer is wrong") but have completely different fixes:
  - algorithm/approximation error (bad polynomial fit, too few reciprocal
    rounds, insufficient NR iterations) -- visible here, in plain floats,
    with zero CKKS noise involved.
  - CKKS-specific error (fixed-point scale, bootstrap noise) -- only
    visible once 17_ actually runs. It should be on top of whatever
    error this script reports, not instead of it.

If this script's error is already too large, no amount of tuning CKKS
parameters on the encrypted side will fix it -- that's the whole point of
running this cheaply, here, first. See Key Finding 2 in
notes/FHE-HEIR/SGP4 FHE Prototype Findings.md for the precedent: the
earlier TenSEAL prototype hit two superficially-identical-looking
failures (a CKKS bug and a plain numerical-conditioning bug) and had to
isolate which was which the same way.

The reciprocal of (1 - e*cos E) is computed via Newton-Raphson refinement
(y_{k+1} = y_k*(2 - d*y_k), y_0 = 1), NOT real division -- CKKS has no
ciphertext/ciphertext division (Key Finding 1 in the same notes). y_0 = 1
is a good starting guess specifically because e is tiny here: d sits in
[1-e, 1+e], a window about 2e-4 wide around 1, so this reciprocal
converges to machine precision in 1-2 rounds. This is the concrete way
this test tries to clear the wall Key Finding 1 hit: not by finding a way
to divide, but by never needing to.

Run: python3 oem-conjunction/16_kepler_plain_approx_pipeline.py
"""
import json
import math

import numpy as np

MU_EARTH_KM3_S2 = 398600.4418
ECCENTRICITY = 0.0001093
MEAN_ANOMALY_0_DEG = 240.5623
MEAN_MOTION_REV_PER_DAY = 15.34403268
WINDOW_HALF_SPAN_S = 1800
KEPLER_NR_ITERS = 2       # matches what 14_ needed to converge to 1e-12
RECIPROCAL_NR_ROUNDS = 2  # see module docstring for why 2 is enough here


def load_poly_coeffs():
    with open("oem-conjunction/data/kepler_trig_poly_coeffs.json") as f:
        return json.load(f)


def rescale(x, lo, hi):
    return 2 * (x - lo) / (hi - lo) - 1


def polyval_ascending(coeffs, x):
    return np.polyval(list(reversed(coeffs)), x)


def nr_reciprocal(d, rounds=RECIPROCAL_NR_ROUNDS):
    """Multiply-only approximate reciprocal, y0=1, matching 17_'s encrypted
    version exactly: round 1 with y0=1 simplifies to y_1 = 2-d (no
    multiply needed), only `rounds - 1` further rounds need one."""
    y = 2.0 - d  # y_1
    for _ in range(rounds - 1):
        y = y * (2.0 - d * y)
    return y


# --- exact reference, duplicated from 14_ (real math.sin/cos, real
# division) purely so this script can diff against it directly without a
# cross-numbered-script import. Keep in sync with 14_ by hand. ---
def solve_kepler_exact(M, e, tol=1e-12, max_iter=50):
    E = M
    for _ in range(max_iter):
        dE = (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
        E -= dE
        if abs(dE) < tol:
            break
    return E


def perifocal_position_exact(a, e, E):
    cosE, sinE = math.cos(E), math.sin(E)
    denom = 1 - e * cosE
    r = a * denom
    cos_nu = (cosE - e) / denom
    sin_nu = math.sqrt(1 - e * e) * sinE / denom
    return r * cos_nu, r * sin_nu, r


def solve_kepler_approx(M, e, coeffs, n_iters=KEPLER_NR_ITERS):
    lo, hi = coeffs["e_domain"]
    E = M
    s = c = fp = recip = None
    for _ in range(n_iters):
        u = rescale(E, lo, hi)
        s = polyval_ascending(coeffs["sin_E"]["coeffs"], u)
        c = polyval_ascending(coeffs["cos_E"]["coeffs"], u)
        f = E - e * s - M
        fp = 1 - e * c
        recip = nr_reciprocal(fp)
        E = E - f * recip
    return E, s, c, fp, recip


def perifocal_position_approx(a, e, s, c, fp, recip, coeffs):
    elo, ehi = coeffs["ecc_domain"]
    sqrt_term = polyval_ascending(coeffs["sqrt_one_minus_e2"]["coeffs"], rescale(e, elo, ehi))
    r = a * fp
    cos_nu = (c - e) * recip
    sin_nu = sqrt_term * s * recip
    return r * cos_nu, r * sin_nu, r


def main():
    coeffs = load_poly_coeffs()
    n = MEAN_MOTION_REV_PER_DAY * 2 * math.pi / 86400.0
    a = (MU_EARTH_KM3_S2 / n ** 2) ** (1.0 / 3.0)
    e = ECCENTRICITY
    M0 = math.radians(MEAN_ANOMALY_0_DEG)

    print(f"{'t (s)':>8}  {'px exact':>14}  {'px approx':>14}  {'err (m)':>10}  "
          f"{'py exact':>14}  {'py approx':>14}  {'err (m)':>10}")
    max_err_m = 0.0
    for t in (-WINDOW_HALF_SPAN_S, -900, 0, 900, WINDOW_HALF_SPAN_S):
        M = M0 + n * t

        E_exact = solve_kepler_exact(M, e)
        px_exact, py_exact, _ = perifocal_position_exact(a, e, E_exact)

        E_approx, s, c, fp, recip = solve_kepler_approx(M, e, coeffs)
        px_approx, py_approx, _ = perifocal_position_approx(a, e, s, c, fp, recip, coeffs)

        err_x_m = abs(px_exact - px_approx) * 1000
        err_y_m = abs(py_exact - py_approx) * 1000
        max_err_m = max(max_err_m, err_x_m, err_y_m)
        print(f"{t:>8d}  {px_exact:>14.6f}  {px_approx:>14.6f}  {err_x_m:>10.3e}  "
              f"{py_exact:>14.6f}  {py_approx:>14.6f}  {err_y_m:>10.3e}")

    print(f"\nmax position error from approximation alone (poly sin/cos + NR reciprocal, "
          f"zero encryption): {max_err_m:.3e} m")
    print("this is the floor 17_'s encrypted result cannot beat -- CKKS noise and bootstrap "
          "noise only add to it.")


if __name__ == "__main__":
    main()
