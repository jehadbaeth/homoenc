"""Ground truth for the encrypted-propagation timing test: an exact
two-body Keplerian propagator in plain floats (real math.sin/cos, real
division), no approximation of any kind. Everything downstream (the
polynomial-approximation validation in 16_, and the OpenFHE version in
17_) gets diffed against this.

Orbital elements are the real TLE mean elements for STARLINK-35712 at its
epoch (same object as TLE_A in data/find_multi_cpa_and_build_oems.py),
treated as osculating two-body classical elements for this test. This is
NOT SGP4 -- there is no drag, no J2, no perturbation theory here, only
pure two-body Kepler dynamics. That is a deliberate scope choice: see the
module docstring in 17_kepler_encrypted_openfhe.py for why.

Run: python3 oem-conjunction/14_kepler_plaintext_reference.py
"""
import math

MU_EARTH_KM3_S2 = 398600.4418  # WGS-84 GM

# TLE_A / STARLINK-35712, line 2: "2 66215  53.1570 133.1789 0001093 119.5489 240.5623 15.34403268 48533"
INCLINATION_DEG = 53.1570
RAAN_DEG = 133.1789
ECCENTRICITY = 0.0001093
ARGP_DEG = 119.5489
MEAN_ANOMALY_0_DEG = 240.5623
MEAN_MOTION_REV_PER_DAY = 15.34403268

# Same local screening window Approach E already uses (openfhe_e.py's
# LOCAL_HALF_SPAN_S) -- conjunction screening only ever needs propagation
# across a short window around a close-approach event, not a full orbit.
WINDOW_HALF_SPAN_S = 1800


def mean_motion_rad_s(rev_per_day=MEAN_MOTION_REV_PER_DAY):
    return rev_per_day * 2 * math.pi / 86400.0


def semi_major_axis_km(n_rad_s, mu=MU_EARTH_KM3_S2):
    return (mu / n_rad_s ** 2) ** (1.0 / 3.0)


def solve_kepler_exact(M, e, tol=1e-12, max_iter=50):
    """Newton-Raphson on E - e*sin(E) - M = 0, exact math.sin/cos, exact
    division. Returns (E, n_iterations_used)."""
    E = M  # good starting guess: e is tiny here, error in E0 is O(e)
    for k in range(1, max_iter + 1):
        f = E - e * math.sin(E) - M
        fp = 1 - e * math.cos(E)
        dE = f / fp
        E -= dE
        if abs(dE) < tol:
            return E, k
    return E, max_iter


def perifocal_position(a, e, E):
    cosE, sinE = math.cos(E), math.sin(E)
    denom = 1 - e * cosE
    r = a * denom
    cos_nu = (cosE - e) / denom
    sin_nu = math.sqrt(1 - e * e) * sinE / denom
    return r * cos_nu, r * sin_nu, r


def perifocal_to_eci(px, py, i, raan, argp):
    """Standard 3-1-3 (RAAN, inclination, argument of perigee) rotation."""
    cO, sO = math.cos(raan), math.sin(raan)
    co, so = math.cos(argp), math.sin(argp)
    ci, si = math.cos(i), math.sin(i)
    x = (cO * co - sO * so * ci) * px + (-cO * so - sO * co * ci) * py
    y = (sO * co + cO * so * ci) * px + (-sO * so + cO * co * ci) * py
    z = (so * si) * px + (co * si) * py
    return x, y, z


def propagate(t, a=None, e=ECCENTRICITY, i_deg=INCLINATION_DEG, raan_deg=RAAN_DEG,
              argp_deg=ARGP_DEG, M0_deg=MEAN_ANOMALY_0_DEG, n=None):
    """Position (km, ECI) at time t (seconds since the TLE epoch)."""
    if n is None:
        n = mean_motion_rad_s()
    if a is None:
        a = semi_major_axis_km(n)
    M0 = math.radians(M0_deg)
    M = M0 + n * t
    E, n_iter = solve_kepler_exact(M, e)
    px, py, r = perifocal_position(a, e, E)
    x, y, z = perifocal_to_eci(px, py, math.radians(i_deg), math.radians(raan_deg), math.radians(argp_deg))
    return {"x": x, "y": y, "z": z, "r": r, "E": E, "M": M, "kepler_iters": n_iter}


def main():
    n = mean_motion_rad_s()
    a = semi_major_axis_km(n)
    period_s = 2 * math.pi / n
    print(f"mean motion: {n:.8f} rad/s   semi-major axis: {a:.4f} km   period: {period_s:.1f} s "
          f"({period_s/60:.2f} min)")

    M0 = math.radians(MEAN_ANOMALY_0_DEG)
    M_lo = M0 + n * (-WINDOW_HALF_SPAN_S)
    M_hi = M0 + n * (WINDOW_HALF_SPAN_S)
    print(f"mean anomaly over +/-{WINDOW_HALF_SPAN_S}s window: [{M_lo:.6f}, {M_hi:.6f}] rad "
          f"(2*pi = {2*math.pi:.6f})")
    assert 0.0 <= M_lo and M_hi <= 2 * math.pi, (
        "window wraps past 0/2*pi -- the no-mod-2pi scope limit (see 17_'s docstring) "
        "does not hold for this window/epoch; would need range reduction"
    )
    print("no mod-2*pi wraparound for this satellite/window: confirmed\n")

    for t in (-WINDOW_HALF_SPAN_S, 0, WINDOW_HALF_SPAN_S):
        result = propagate(t, a=a, n=n)
        print(f"t={t:+6d}s  x={result['x']:14.6f}  y={result['y']:14.6f}  z={result['z']:14.6f}  "
              f"km   |r|={result['r']:.6f} km   Kepler solve: {result['kepler_iters']} NR iteration(s)")

    # Sanity check: |r| should be within a few km of a for this near-circular orbit.
    r0 = propagate(0, a=a, n=n)["r"]
    print(f"\nsanity: eccentricity={ECCENTRICITY}, a={a:.3f} km, |r| at t=0 is {r0:.3f} km "
          f"(a*(1-e)={a*(1-ECCENTRICITY):.3f}, a*(1+e)={a*(1+ECCENTRICITY):.3f} bound the range)")


if __name__ == "__main__":
    main()
