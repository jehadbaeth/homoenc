"""Precision gate for the RK4 encrypted test (20_), same role
16_kepler_plain_approx_pipeline.py plays for the Kepler test: run the
identical sequence of operations the encrypted script will run, in plain
floats, and diff against 18_rk4_plaintext_reference.py AT THE SAME STEP
COUNT -- not against the Kepler-exact end state. That isolates the error
this approximation chain adds on top of RK4's own discretization error
(which is a property of the algorithm, already characterized in 18_'s
output, not something encryption should be blamed for).

The one non-polynomial operation RK4's force evaluation needs is
1/r^3 = (x^2+y^2)^(-3/2). CKKS has no division and no square root, so
this is built the same way 16_/17_ built 1/(1-e*cos E): Newton-Raphson,
multiply-only. Specifically inverse square root (the "fast inverse
square root" iteration): y_(k+1) = y_k*(3 - r^2*y_k^2)/2, converging to
r^(-1). Cubing that (y^2 * y) gives r^(-3) without ever computing r or
dividing by it.

The starting guess y0 = 1/7000 is a fixed PUBLIC constant (a generic
"LEO altitude" prior, not derived from this satellite's actual, private
radius) -- it only has to be roughly right because Newton's method
converges quadratically; this repo's own earlier work established that
LEO orbital radius sits in a narrow, known band (~6800-7200 km), which
is exactly what makes a public, generic seed adequate here without
leaking anything about the specific orbit.

Run: python3 oem-conjunction/19_rk4_plain_approx_pipeline.py
"""
import math

from importlib import import_module

MU_EARTH_KM3_S2 = 398600.4418
ECCENTRICITY = 0.0001093
MEAN_ANOMALY_0_DEG = 240.5623
MEAN_MOTION_REV_PER_DAY = 15.34403268
WINDOW_HALF_SPAN_S = 1800
N_STEPS = 4                 # matches what 20_ actually runs under encryption
INV_SQRT_NR_ROUNDS = 3       # validated below: ~1e-12 relative error at 3 rounds
R0_GUESS_KM = 7000.0         # public generic LEO-altitude seed, see module docstring


def nr_inv_sqrt(d, rounds=INV_SQRT_NR_ROUNDS, y0=1.0 / R0_GUESS_KM):
    y = y0
    for _ in range(rounds):
        y = y * (3 - d * y * y) / 2
    return y


def accel_approx(x, y, mu=MU_EARTH_KM3_S2):
    r2 = x * x + y * y
    inv_r = nr_inv_sqrt(r2)
    inv_r3 = inv_r * inv_r * inv_r
    return -mu * x * inv_r3, -mu * y * inv_r3


def rk4_step_approx(x, y, vx, vy, h):
    def deriv(x, y, vx, vy):
        ax, ay = accel_approx(x, y)
        return vx, vy, ax, ay

    k1 = deriv(x, y, vx, vy)
    k2 = deriv(x + h / 2 * k1[0], y + h / 2 * k1[1], vx + h / 2 * k1[2], vy + h / 2 * k1[3])
    k3 = deriv(x + h / 2 * k2[0], y + h / 2 * k2[1], vx + h / 2 * k2[2], vy + h / 2 * k2[3])
    k4 = deriv(x + h * k3[0], y + h * k3[1], vx + h * k3[2], vy + h * k3[3])
    x2 = x + h / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
    y2 = y + h / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
    vx2 = vx + h / 6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2])
    vy2 = vy + h / 6 * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3])
    return x2, y2, vx2, vy2


def main():
    ref = import_module("18_rk4_plaintext_reference")

    n = MEAN_MOTION_REV_PER_DAY * 2 * math.pi / 86400.0
    a = (MU_EARTH_KM3_S2 / n ** 2) ** (1.0 / 3.0)
    p = a * (1 - ECCENTRICITY ** 2)
    M0 = math.radians(MEAN_ANOMALY_0_DEG)

    x0, y0, vx0, vy0 = ref.perifocal_state(-WINDOW_HALF_SPAN_S, a, ECCENTRICITY, n, p, M0)

    print("round-by-round inverse-sqrt convergence check (r^2 for this orbit's radius):")
    r2_typical = x0 * x0 + y0 * y0
    true_inv_r = 1.0 / math.sqrt(r2_typical)
    y = 1.0 / R0_GUESS_KM
    for k in range(1, INV_SQRT_NR_ROUNDS + 1):
        y = y * (3 - r2_typical * y * y) / 2
        print(f"  round {k}: rel_err={abs(y-true_inv_r)/true_inv_r:.3e}")

    h = (2 * WINDOW_HALF_SPAN_S) / N_STEPS
    x_exact, y_exact, vx_exact, vy_exact = x0, y0, vx0, vy0
    x_approx, y_approx, vx_approx, vy_approx = x0, y0, vx0, vy0

    print(f"\n{N_STEPS} steps of h={h:.1f}s, exact RK4 (18_) vs. this approximation chain:")
    print(f"{'step':>5}  {'x exact':>12}  {'x approx':>12}  {'err (m)':>10}  "
          f"{'y exact':>12}  {'y approx':>12}  {'err (m)':>10}")
    for step in range(1, N_STEPS + 1):
        x_exact, y_exact, vx_exact, vy_exact = ref.rk4_step(x_exact, y_exact, vx_exact, vy_exact, h)
        x_approx, y_approx, vx_approx, vy_approx = rk4_step_approx(x_approx, y_approx, vx_approx, vy_approx, h)
        err_x_m = abs(x_exact - x_approx) * 1000
        err_y_m = abs(y_exact - y_approx) * 1000
        print(f"{step:>5}  {x_exact:>12.4f}  {x_approx:>12.4f}  {err_x_m:>10.3e}  "
              f"{y_exact:>12.4f}  {y_approx:>12.4f}  {err_y_m:>10.3e}")

    max_err_m = max(abs(x_exact - x_approx), abs(y_exact - y_approx)) * 1000
    print(f"\nmax position error from the approximation chain alone (inverse-sqrt NR "
          f"instead of real sqrt/division, zero encryption), after {N_STEPS} steps: "
          f"{max_err_m:.3e} m")
    print("this is on top of RK4's own discretization error at this step count "
          "(see 18_'s output for that) -- the two are separate error sources.")


if __name__ == "__main__":
    main()
