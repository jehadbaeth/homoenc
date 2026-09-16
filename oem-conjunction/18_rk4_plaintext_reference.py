"""Ground truth for the "harder algorithm" comparison: general numerical
(RK4) integration of the two-body equations of motion, in plain floats,
no approximation. Same satellite, same window, same perifocal-plane
scope as 14_kepler_plaintext_reference.py -- the point of this script is
a fair, apples-to-apples benchmark against the Kepler/Newton-Raphson
approach, not a different scenario.

Unlike Kepler's equation (closed-form in eccentric anomaly, solved once
per query time regardless of how far ahead that time is), RK4 walks
forward in fixed sub-steps from a starting state (x, y, vx, vy) at
t=-1800s, needing a force evaluation -- and therefore a 1/r^3 -- at every
sub-step. This is the general-purpose propagator that works even when
there's no closed form (arbitrary perturbations, non-Keplerian forces);
Kepler's equation only exists because two-body motion happens to have
one.

Run: python3 oem-conjunction/18_rk4_plaintext_reference.py
"""
import math

MU_EARTH_KM3_S2 = 398600.4418
ECCENTRICITY = 0.0001093
MEAN_ANOMALY_0_DEG = 240.5623
MEAN_MOTION_REV_PER_DAY = 15.34403268
WINDOW_HALF_SPAN_S = 1800


def solve_kepler_exact(M, e, tol=1e-13, max_iter=60):
    E = M
    for _ in range(max_iter):
        dE = (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
        E -= dE
        if abs(dE) < tol:
            break
    return E


def perifocal_state(t, a, e, n, p, M0):
    """Exact position AND velocity in the perifocal plane at time t,
    from the standard closed-form vis-viva / perifocal-velocity
    identities -- this is how RK4's starting state is obtained without
    numerical differentiation."""
    M = M0 + n * t
    E = solve_kepler_exact(M, e)
    cosE, sinE = math.cos(E), math.sin(E)
    denom = 1 - e * cosE
    r = a * denom
    cos_nu = (cosE - e) / denom
    sin_nu = math.sqrt(1 - e * e) * sinE / denom
    nu = math.atan2(sin_nu, cos_nu)
    px, py = r * cos_nu, r * sin_nu
    vx = -math.sqrt(MU_EARTH_KM3_S2 / p) * math.sin(nu)
    vy = math.sqrt(MU_EARTH_KM3_S2 / p) * (e + math.cos(nu))
    return px, py, vx, vy


def accel(x, y, mu=MU_EARTH_KM3_S2):
    r = math.sqrt(x * x + y * y)
    return -mu * x / r ** 3, -mu * y / r ** 3


def rk4_step(x, y, vx, vy, h):
    def deriv(x, y, vx, vy):
        ax, ay = accel(x, y)
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
    n = MEAN_MOTION_REV_PER_DAY * 2 * math.pi / 86400.0
    a = (MU_EARTH_KM3_S2 / n ** 2) ** (1.0 / 3.0)
    p = a * (1 - ECCENTRICITY ** 2)
    M0 = math.radians(MEAN_ANOMALY_0_DEG)

    x0, y0, vx0, vy0 = perifocal_state(-WINDOW_HALF_SPAN_S, a, ECCENTRICITY, n, p, M0)
    x_end_exact, y_end_exact, _, _ = perifocal_state(WINDOW_HALF_SPAN_S, a, ECCENTRICITY, n, p, M0)
    print(f"start state (t=-{WINDOW_HALF_SPAN_S}s): x={x0:.4f} y={y0:.4f} vx={vx0:.6f} vy={vy0:.6f} km, km/s")
    print(f"Kepler-exact end state (t=+{WINDOW_HALF_SPAN_S}s): x={x_end_exact:.4f} y={y_end_exact:.4f} km\n")

    print(f"{'n steps':>8}  {'h (s)':>7}  {'x_end':>12}  {'y_end':>12}  {'error (m)':>12}")
    for nsteps in (1, 2, 4, 6, 10, 20, 40, 180):
        h = (2 * WINDOW_HALF_SPAN_S) / nsteps
        x, y, vx, vy = x0, y0, vx0, vy0
        for _ in range(nsteps):
            x, y, vx, vy = rk4_step(x, y, vx, vy, h)
        err_m = math.hypot(x - x_end_exact, y - y_end_exact) * 1000
        print(f"{nsteps:>8}  {h:>7.1f}  {x:>12.4f}  {y:>12.4f}  {err_m:>12.4e}")

    print("\nRK4 error falls off as O(h^4): each halving of step size should cut error "
          "roughly 16x. Contrast with 14_/16_'s Kepler solve, which gets sub-meter "
          "accuracy in 2 Newton-Raphson iterations regardless of window size.")


if __name__ == "__main__":
    main()
