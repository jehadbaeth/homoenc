"""SGP4's mathematical skeleton, stripped of perturbation terms: plain two-body
Keplerian propagation. This is what we'll actually try to encrypt, in stages.

Steps, same shape as real SGP4:
1. mean anomaly M advances linearly with time      -> pure add/multiply, trivial for FHE
2. solve Kepler's equation E - e*sin(E) = M for E  -> iterative, needs sin() each round
3. convert E to position via cos(E), sin(E), sqrt   -> trig + sqrt

We propagate mean anomaly only and track how many operations / what depth each
step costs, since that's what will matter once this moves under encryption.
"""
import math

MU_EARTH = 398600.4418  # km^3/s^2

def mean_motion(a):
    return math.sqrt(MU_EARTH / a**3)

def propagate_mean_anomaly(M0, a, dt):
    n = mean_motion(a)
    return (M0 + n * dt) % (2 * math.pi)

def solve_kepler(M, e, tol=1e-10, max_iter=20):
    E = M  # initial guess
    for i in range(max_iter):
        f = E - e * math.sin(E) - M
        fp = 1 - e * math.cos(E)
        E_next = E - f / fp
        if abs(E_next - E) < tol:
            return E_next, i + 1
        E = E_next
    return E, max_iter

def orbital_to_position(a, e, E):
    x = a * (math.cos(E) - e)
    y = a * math.sqrt(1 - e**2) * math.sin(E)
    return x, y

if __name__ == "__main__":
    a = 6798.0       # semi-major axis, km (roughly ISS altitude)
    e = 0.0007        # eccentricity
    M0 = 1.5          # initial mean anomaly, rad
    dt = 300          # seconds

    M = propagate_mean_anomaly(M0, a, dt)
    E, iters = solve_kepler(M, e)
    x, y = orbital_to_position(a, e, E)

    print(f"mean anomaly after {dt}s: {M:.6f} rad")
    print(f"Kepler solve converged in {iters} Newton iterations, E = {E:.6f} rad")
    print(f"orbital-plane position: x={x:.3f} km, y={y:.3f} km")
