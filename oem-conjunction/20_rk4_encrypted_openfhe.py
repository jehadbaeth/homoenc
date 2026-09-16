"""The "harder algorithm" benchmark: general-purpose RK4 numerical
integration of the two-body equations of motion, genuinely encrypted
(state x, y, vx, vy all ciphertexts), run alongside
17_kepler_encrypted_openfhe.py's closed-form Kepler solve for a direct
cost comparison on the same satellite, same window, same hardware.

WHY THIS EXISTS: 17_ showed a closed-form propagator (Kepler's equation)
runs cheap under encryption -- 0 bootstraps, well under a second per
query time. That's a property of Kepler's equation having a closed form
at all, not a property of "propagation" in general. Most real dynamics
(J2, drag, third-body, anything non-Keplerian) don't have closed forms
and need general numerical integration instead. This script measures
what THAT costs, so the earlier result isn't accidentally read as
"propagation under encryption is cheap" when the honest claim is
"propagation under encryption is cheap when a closed form exists."

THE FORCE EVALUATION: RK4 needs 1/r^3 = (x^2+y^2)^(-3/2) at every
stage of every step. CKKS has neither square root nor division, so this
is built the same multiply-only way 16_/17_ built 1/(1-e cos E): Newton-
Raphson, here for inverse square root (y_(k+1) = y_k*(3 - r^2*y_k^2)/2),
cubed afterward (y^3 = y^2 * y). The starting guess y0 = 1/7000 is a
fixed PUBLIC constant (a generic LEO-altitude prior), not derived from
this satellite's actual private radius -- adequate only because Newton's
method converges quadratically and this repo's own earlier work
established LEO radius sits in a narrow, known band. Validated in plain
floats first, zero encryption, in 19_rk4_plain_approx_pipeline.py.

SCOPE: same as 17_ -- perifocal plane only (2D, not 3D ECI), this one
satellite's real TLE elements, no J2/drag/SGP4. N_STEPS below is
deliberately small (a handful of RK4 steps, not the ~180 needed to match
Kepler's sub-meter accuracy over this window -- see 18_'s own printed
error-vs-stepcount table for why). The point of this run is to measure
real, per-step encrypted cost; 18_'s plaintext table is what you'd use
to extrapolate the cost of a full, accurate run from that measurement.

CANONICAL UNITS: a first version of this script encrypted raw km-scale
positions (thousands) and r^2 (~4.7e7) directly and hit a real failure:
EvalBootstrap on those large-magnitude ciphertexts corrupted them badly
enough that the final Decrypt raised "the approximation error is too
high" -- CKKS bootstrapping's internal sine-based modular reduction is
only accurate within a calibrated range, and nothing here was rescaled
into it. The fix is standard in orbital mechanics -- canonical units:
divide every length by DU_KM=7000 (so positions and r^2 become O(1)) and
every time by TU_S=sqrt(DU_KM^3/mu) (which makes mu exactly 1 in these
units, so the force evaluation doesn't even need the large MU_EARTH_KM3_S2
constant). This is the same discipline Approach E already uses -- see
openfhe_e.py's SCALE_KM2, which rescales distance^2 before continuing --
applied here because this script's own first attempt skipped it and paid
for that directly.

LEVEL MANAGEMENT: every stage's force evaluation is deep (~15-20 levels:
two squarings for r^2, three Newton rounds for the inverse square root,
two more multiplies to cube it, two more to scale into ax/ay). Four
stages per RK4 step make this dramatically deeper than 17_'s whole
Kepler solve. Unlike 17_ (which never needed to bootstrap), this WILL
need to bootstrap, likely more than once per step -- and it needs to
keep the original (x, y, vx, vy) state alive and level-matched against
an accumulator that gets multiplied into on every stage. Whenever
anything in the currently-live working set runs low on depth, this
script bootstraps the ENTIRE working set together (see sync_bootstrap),
the same defensive, not-necessarily-optimal strategy 17_ used for its
smaller (E, e, a) working set.

Run (Python 3.12 on Linux via the pip wheel, or this repo's .venv on
macOS/arm64 via the from-source build -- see README.md):
    python3 oem-conjunction/20_rk4_encrypted_openfhe.py
"""
import json
import math
import time

import openfhe

MU_EARTH_KM3_S2 = 398600.4418
ECCENTRICITY = 0.0001093
MEAN_ANOMALY_0_DEG = 240.5623
MEAN_MOTION_REV_PER_DAY = 15.34403268
WINDOW_HALF_SPAN_S = 1800
N_STEPS = 4  # see module docstring -- a real, bounded measurement, not the accurate run

INV_SQRT_NR_ROUNDS = 3
DU_KM = 7000.0  # canonical distance unit -- see module docstring's "CANONICAL UNITS" note
TU_S = math.sqrt(DU_KM ** 3 / MU_EARTH_KM3_S2)  # canonical time unit, makes mu=1

LEVEL_BUDGET = [4, 4]
LEVELS_AFTER_BOOTSTRAP = 25   # deeper than 17_'s 15: each RK4 stage is a long chain
MIN_LEVELS_FOR_STAGE = 20     # headroom for one full deriv() call (~15-20 levels)


def solve_kepler_exact(M, e, tol=1e-13, max_iter=60):
    E = M
    for _ in range(max_iter):
        dE = (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
        E -= dE
        if abs(dE) < tol:
            break
    return E


def perifocal_state_exact(t, a, e, n, p, M0):
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


def make_bootstrapping_context():
    secret_key_dist = openfhe.SecretKeyDist.UNIFORM_TERNARY
    bootstrap_depth = openfhe.FHECKKSRNS.GetBootstrapDepth(LEVEL_BUDGET, secret_key_dist)
    depth = LEVELS_AFTER_BOOTSTRAP + bootstrap_depth

    params = openfhe.CCParamsCKKSRNS()
    params.SetSecretKeyDist(secret_key_dist)
    params.SetSecurityLevel(openfhe.SecurityLevel.HEStd_NotSet)
    params.SetRingDim(1 << 13)
    params.SetScalingModSize(59)
    params.SetScalingTechnique(openfhe.ScalingTechnique.FLEXIBLEAUTO)
    params.SetFirstModSize(60)
    params.SetMultiplicativeDepth(depth)

    cc = openfhe.GenCryptoContext(params)
    cc.Enable(openfhe.PKESchemeFeature.PKE)
    cc.Enable(openfhe.PKESchemeFeature.KEYSWITCH)
    cc.Enable(openfhe.PKESchemeFeature.LEVELEDSHE)
    cc.Enable(openfhe.PKESchemeFeature.ADVANCEDSHE)
    cc.Enable(openfhe.PKESchemeFeature.FHE)

    num_slots = cc.GetRingDimension() // 2
    cc.EvalBootstrapSetup(LEVEL_BUDGET, [0, 0], num_slots)
    keys = cc.KeyGen()
    cc.EvalMultKeyGen(keys.secretKey)
    cc.EvalBootstrapKeyGen(keys.secretKey, num_slots)
    return cc, keys, depth, num_slots


def enc_scalar(cc, keys, value, num_slots):
    return cc.Encrypt(keys.publicKey, cc.MakeCKKSPackedPlaintext([value] * num_slots))


def dec_scalar(cc, keys, ct):
    pt = cc.Decrypt(ct, keys.secretKey)
    pt.SetLength(1)
    return pt.GetRealPackedValue()[0]


def nr_inv_sqrt(cc, d, rounds=INV_SQRT_NR_ROUNDS, y0=1.0):
    """Multiply-only approximate 1/sqrt(d). Round 1 uses the PLAINTEXT
    constant y0 directly (d*y0^2 is a ciphertext-plaintext multiply),
    so it costs one multiply instead of a ciphertext-ciphertext one;
    only rounds after that operate on the ciphertext y."""
    t1 = cc.EvalMult(d, -(y0 ** 2))
    y = cc.EvalMult(cc.EvalAdd(t1, 3.0), y0 / 2.0)  # y_1
    for _ in range(rounds - 1):
        y2 = cc.EvalMult(y, y)
        dy2 = cc.EvalMult(d, y2)
        y = cc.EvalMult(y, cc.EvalAdd(cc.EvalMult(dy2, -0.5), 1.5))
    return y


def bootstrap_all(cc, cts):
    return [cc.EvalBootstrap(ct) for ct in cts]


def deepest_level(cts):
    return max(ct.GetLevel() for ct in cts)


def sync_bootstrap(cc, depth, working_set, on_bootstrap=None):
    """working_set: dict name->ciphertext. Bootstraps every value in it
    together if the deepest one is running low, so nothing in active use
    ever drifts out of level-sync with anything else in the set."""
    if depth - deepest_level(working_set.values()) < MIN_LEVELS_FOR_STAGE:
        names = list(working_set.keys())
        fresh = bootstrap_all(cc, [working_set[n] for n in names])
        for name, ct in zip(names, fresh):
            working_set[name] = ct
        if on_bootstrap:
            on_bootstrap(fresh[0].GetLevel())
        return True
    return False


def deriv_encrypted(cc, x, y, vx, vy):
    """Canonical units (DU_KM, TU_S): mu=1 exactly, so no large constant
    multiplication is needed here at all."""
    r2 = cc.EvalAdd(cc.EvalMult(x, x), cc.EvalMult(y, y))
    inv_r = nr_inv_sqrt(cc, r2)
    inv_r3 = cc.EvalMult(cc.EvalMult(inv_r, inv_r), inv_r)
    ax = cc.EvalMult(x, cc.EvalMult(inv_r3, -1.0))
    ay = cc.EvalMult(y, cc.EvalMult(inv_r3, -1.0))
    return vx, vy, ax, ay  # dx/dt=vx, dy/dt=vy, dvx/dt=ax, dvy/dt=ay


def rk4_step_encrypted(cc, depth, h, state, n_bootstrap_counter, on_bootstrap=None):
    x, y, vx, vy = state["x"], state["y"], state["vx"], state["vy"]

    def stage(sx, sy, svx, svy, tag):
        ws = {"x": x, "y": y, "vx": vx, "vy": vy, "sx": sx, "sy": sy, "svx": svx, "svy": svy}
        if sync_bootstrap(cc, depth, ws, on_bootstrap):
            n_bootstrap_counter[0] += 1
        return deriv_encrypted(cc, ws["sx"], ws["sy"], ws["svx"], ws["svy"]), \
            ws["x"], ws["y"], ws["vx"], ws["vy"]

    k1, x, y, vx, vy = stage(x, y, vx, vy, "k1")
    s2x = cc.EvalAdd(x, cc.EvalMult(k1[0], h / 2))
    s2y = cc.EvalAdd(y, cc.EvalMult(k1[1], h / 2))
    s2vx = cc.EvalAdd(vx, cc.EvalMult(k1[2], h / 2))
    s2vy = cc.EvalAdd(vy, cc.EvalMult(k1[3], h / 2))
    k2, x, y, vx, vy = stage(s2x, s2y, s2vx, s2vy, "k2")

    s3x = cc.EvalAdd(x, cc.EvalMult(k2[0], h / 2))
    s3y = cc.EvalAdd(y, cc.EvalMult(k2[1], h / 2))
    s3vx = cc.EvalAdd(vx, cc.EvalMult(k2[2], h / 2))
    s3vy = cc.EvalAdd(vy, cc.EvalMult(k2[3], h / 2))
    k3, x, y, vx, vy = stage(s3x, s3y, s3vx, s3vy, "k3")

    s4x = cc.EvalAdd(x, cc.EvalMult(k3[0], h))
    s4y = cc.EvalAdd(y, cc.EvalMult(k3[1], h))
    s4vx = cc.EvalAdd(vx, cc.EvalMult(k3[2], h))
    s4vy = cc.EvalAdd(vy, cc.EvalMult(k3[3], h))
    k4, x, y, vx, vy = stage(s4x, s4y, s4vx, s4vy, "k4")

    def combine(orig, ks, idx):
        acc = cc.EvalAdd(cc.EvalAdd(ks[0][idx], cc.EvalMult(ks[1][idx], 2.0)),
                          cc.EvalAdd(cc.EvalMult(ks[2][idx], 2.0), ks[3][idx]))
        return cc.EvalAdd(orig, cc.EvalMult(acc, h / 6.0))

    ks = (k1, k2, k3, k4)
    x_new = combine(x, ks, 0)
    y_new = combine(y, ks, 1)
    vx_new = combine(vx, ks, 2)
    vy_new = combine(vy, ks, 3)
    return {"x": x_new, "y": y_new, "vx": vx_new, "vy": vy_new}


def main():
    n = MEAN_MOTION_REV_PER_DAY * 2 * math.pi / 86400.0
    a = (MU_EARTH_KM3_S2 / n ** 2) ** (1.0 / 3.0)
    p = a * (1 - ECCENTRICITY ** 2)
    M0 = math.radians(MEAN_ANOMALY_0_DEG)
    x0, y0, vx0, vy0 = perifocal_state_exact(-WINDOW_HALF_SPAN_S, a, ECCENTRICITY, n, p, M0)
    h_s = (2 * WINDOW_HALF_SPAN_S) / N_STEPS

    # Canonical units: divide lengths by DU_KM, velocities by DU_KM/TU_S, time by
    # TU_S. Puts every encrypted quantity (positions, r^2, the inverse-sqrt
    # iterate, forces) at O(1) magnitude -- see module docstring's "CANONICAL
    # UNITS" note for why bootstrapping raw km-scale values corrupted the result.
    x0_c, y0_c = x0 / DU_KM, y0 / DU_KM
    vx0_c, vy0_c = vx0 / (DU_KM / TU_S), vy0 / (DU_KM / TU_S)
    h_c = h_s / TU_S

    t0 = time.perf_counter()
    cc, keys, depth, num_slots = make_bootstrapping_context()
    t_ctx = time.perf_counter() - t0
    print(f"context+keygen (incl. bootstrap setup): {t_ctx*1000:.1f} ms")
    print(f"ring dim: {cc.GetRingDimension()}   multiplicative depth: {depth}")
    print(f"canonical units: DU={DU_KM} km, TU={TU_S:.3f} s")
    print(f"{N_STEPS} steps of h={h_s:.1f}s ({h_c:.4f} TU)\n")

    state = {
        "x": enc_scalar(cc, keys, x0_c, num_slots),
        "y": enc_scalar(cc, keys, y0_c, num_slots),
        "vx": enc_scalar(cc, keys, vx0_c, num_slots),
        "vy": enc_scalar(cc, keys, vy0_c, num_slots),
    }

    total_bootstraps = 0
    total_wall = 0.0
    per_step = []
    for step in range(1, N_STEPS + 1):
        n_boot = [0]

        def on_bootstrap(level, step=step):
            print(f"  step {step}  [bootstrap] refreshed to level {level}")

        t_start = time.perf_counter()
        state = rk4_step_encrypted(cc, depth, h_c, state, n_boot, on_bootstrap)
        t_step = time.perf_counter() - t_start

        x_val = dec_scalar(cc, keys, state["x"]) * DU_KM
        y_val = dec_scalar(cc, keys, state["y"]) * DU_KM
        total_bootstraps += n_boot[0]
        total_wall += t_step
        print(f"step {step}: x={x_val:12.4f}  y={y_val:12.4f} km   "
              f"{n_boot[0]} bootstrap(s)   {t_step:.2f}s")
        per_step.append({"step": step, "x_km": x_val, "y_km": y_val,
                          "bootstraps": n_boot[0], "wall_s": t_step})

    print(f"\n{N_STEPS} RK4 steps, {total_bootstraps} bootstraps total, "
          f"{total_wall:.2f}s wall clock ({total_wall/N_STEPS:.2f}s/step average, "
          f"{total_bootstraps/N_STEPS:.2f} bootstraps/step average)")
    print("Diff x/y against 19_rk4_plain_approx_pipeline.py's printed values at the same "
          "step to separate CKKS+bootstrap noise from the approximation-chain floor "
          "that script already measured with zero encryption.")

    with open("oem-conjunction/results/rk4_encrypted_timing.json", "w") as f:
        json.dump({"ring_dim": cc.GetRingDimension(), "depth": depth, "n_steps": N_STEPS,
                   "h_s": h_s, "context_setup_s": t_ctx, "total_bootstraps": total_bootstraps,
                   "total_wall_s": total_wall, "per_step": per_step}, f, indent=2)
    print("\nwritten: oem-conjunction/results/rk4_encrypted_timing.json")


if __name__ == "__main__":
    main()
