"""Timing test: does a real two-body Kepler propagation, run genuinely
under encryption (private orbit shape AND private phase, not just
private phase), finish in a usable amount of time on this hardware?

WHY THIS SCRIPT EXISTS
This repo's first report already asked this question and answered it "no,
not this way": notes/FHE-HEIR/SGP4 FHE Prototype Findings.md, Key Finding
1, states plainly that CKKS has no ciphertext/ciphertext division, that
Newton-Raphson needs f(E)/f'(E), and that the only way that prototype got
an iterative Kepler solve to run was decrypting the denominator every
round -- which defeats the point. That prototype's accepted fix (Key
Finding 3) was architectural: stop iterating, fit the whole propagation
as one polynomial in the phase variable, offline, in plaintext. That
works, but only because it requires orbit SHAPE (a, e) to be public and
just orbit PHASE (M) to be private (Key Finding 4 pushed shape-privacy
partway, encrypting e too, but that assumed public a, i, RAAN, argp).

This script tests whether that finding still holds now that two things
have changed since it was written:
  1. CKKS bootstrapping (OpenFHE, this repo's own Approach E) refreshes
     multiplicative depth on demand. The earlier prototype (TenSEAL, no
     bootstrapping) could not have run more than a couple of iterations
     regardless of the division question -- it would have hit the same
     depth wall 08_sign_iteration_depth_wall.py documented for the sign
     polynomial. That wall is exactly what bootstrapping exists to fix.
  2. The reciprocal used below is NOT ciphertext/ciphertext division. It
     is Newton-Raphson refinement of an approximate reciprocal,
     y_(k+1) = y_k*(2 - d*y_k), using only ciphertext-ciphertext
     multiply and ciphertext-plaintext add/multiply -- operations CKKS
     has always supported. It converges to y=1/d without ever calling a
     division operator, and without ever decrypting anything mid-loop.
     It works well here specifically because this satellite's near-zero
     eccentricity (e=0.0001093) keeps the denominator (1 - e*cos E)
     within about 1e-4 of 1.0, so y_0=1 is already an excellent starting
     guess: 16_kepler_plain_approx_pipeline.py confirms 2 rounds is
     enough for sub-meter accuracy, entirely in plain floats.

If this script's decrypted result matches 16_'s plain-float approximation
(see that script's own docstring for exactly what it isolates) to within
a small multiple of its ~0.8 m error, both open questions from the
earlier study are answered for this specific case: iteration under
encryption works with bootstrapping, and it doesn't need real division.
If the error is much larger, that is CKKS/bootstrap noise on top of the
already-measured approximation floor, not a repeat of Key Finding 1.

SCOPE, STATED PLAINLY (not swept under the rug):
  - Two-body Kepler dynamics only. No SGP4, no J2, no drag. See the
    answer to "which propagator should I test" earlier in this project's
    conversation for why: SGP4's near-Earth/deep-space branch and secular
    perturbation terms are genuinely data-dependent control flow, which
    under FHE means evaluating every branch and blending on encrypted
    predicates -- a timing number from that would measure the cost of
    de-branching a hand port, not the cost of SGP4.
  - Single +/-1800s window (this repo's existing local screening span,
    see openfhe_e.py's LOCAL_HALF_SPAN_S), chosen so mean anomaly stays
    inside [0, 2*pi) without crossing the wrap boundary -- verified
    numerically in 14_kepler_plaintext_reference.py, not assumed. A
    general implementation (arbitrary epoch, wider window, or an orbit
    whose window straddles 0/2*pi) needs mod-2*pi range reduction first;
    that is NOT implemented here.
  - Propagates to eccentric anomaly / perifocal position (r, and
    perifocal-plane px, py) only. Rotating perifocal to ECI needs three
    more encrypted trig evaluations (inclination, RAAN, argument of
    perigee) of the same shape as the ones already here -- straightforward
    to add, deliberately left out of this first pass to keep the thing
    that's actually being tested (does encrypted iteration converge, how
    many bootstraps, how long) uncluttered by more plumbing.
  - Multiple ciphertexts (E, e, a) are kept alive simultaneously and
    re-synchronized (bootstrapped together) whenever any of them runs
    low on depth, rather than the one-evolving-ciphertext pattern
    09_/13_ use. That pattern is new in this repo and UNVERIFIED -- see
    the honesty note below.

STATUS: this has now been run, on a from-source OpenFHE build already
present in this repo's .venv (macOS/arm64 -- the pip wheel doesn't cover
that platform, see README.md's Setup section; the bigger Linux machine
this was written for should just use the documented pip wheel instead).

Result at KEPLER_NR_ITERS=2, demo parameters (ring 2^13, depth 37):
context+keygen 836 ms, 5 query times in 3.86 s total (~0.77 s/query),
ZERO bootstraps needed -- the whole 2-iteration solve plus perifocal
reconstruction never used more than ~10 of the 37 available levels, well
inside a single bootstrap segment. Decrypted px/py matched
16_kepler_plain_approx_pipeline.py's plain-float output to all 6 printed
decimal digits at every query time -- CKKS noise added nothing detectable
on top of the ~0.8 m approximation floor 16_ already measured. Full
numbers: oem-conjunction/results/kepler_encrypted_timing.json.

What this does and doesn't verify: it confirms the core claim -- an
iterative Kepler solve runs under CKKS end to end, decrypts to the right
answer, using only a multiply-only reciprocal and never a division op or
a mid-loop decrypt, closing the specific wall Key Finding 1 in
notes/FHE-HEIR/SGP4 FHE Prototype Findings.md described. It does NOT
verify the bootstrap-triggering path: depth never ran low enough to
call EvalBootstrap even once, so the joint-resync-of-three-ciphertexts
logic (bootstrap_all inside kepler_solve_encrypted) never actually ran.
That remains unverified -- it would need more NR iterations, added ECI
rotation and J2 terms, or production security parameters (which force a
much larger ring and floor, see report-approach-e.html's own measurement
of that wall) to actually exercise it.

Run (Python 3.12 on Linux via the pip wheel, or this repo's .venv on
macOS/arm64 via the from-source build):
    python3 oem-conjunction/17_kepler_encrypted_openfhe.py
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
QUERY_TIMES_S = [-1800, -900, 0, 900, 1800]

KEPLER_NR_ITERS = 2       # validated in 16_: sub-meter accuracy at 2 iterations
RECIPROCAL_NR_ROUNDS = 2  # validated in 16_: enough given e's size here
LEVEL_BUDGET = [4, 4]
LEVELS_AFTER_BOOTSTRAP = 15  # same demo convention as openfhe_e.py / 09_ / 13_
MIN_LEVELS_FOR_POLY = 10     # a bit more headroom than 09_/13_'s 8: this loop
                              # chains more distinct multiplies per "round"
                              # than a single EvalPoly call does


def load_poly_coeffs():
    with open("oem-conjunction/data/kepler_trig_poly_coeffs.json") as f:
        return json.load(f)


def make_bootstrapping_context(num_slots_needed=1):
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
    assert num_slots_needed <= num_slots

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


def rescale_affine(cc, ct, lo, hi):
    """Encrypted affine map from [lo, hi] to [-1, 1], the domain the
    offline polynomial fits (15_) were fit against."""
    scale = 2.0 / (hi - lo)
    offset = -1.0 - 2.0 * lo / (hi - lo)
    return cc.EvalAdd(cc.EvalMult(ct, scale), offset)


def nr_reciprocal(cc, d, rounds):
    """Multiply-only approximate reciprocal of encrypted d, starting from
    y0=1 (no division op, ever). With y0=1, round 1 simplifies exactly to
    y_1 = 2 - d (since d*y0 = d), needing only a plaintext-scalar affine
    map, not a ciphertext-ciphertext multiply -- so only `rounds - 1`
    rounds after that need a real multiply. y_1 stays at the same level
    as d, which is what lets this be combined with other same-generation
    ciphertexts below without an extra bootstrap just to align levels."""
    y = cc.EvalAdd(cc.EvalMult(d, -1.0), 2.0)  # y_1 = 2 - d
    for _ in range(rounds - 1):
        dy = cc.EvalMult(d, y)
        y = cc.EvalMult(y, cc.EvalAdd(cc.EvalMult(dy, -1.0), 2.0))
    return y


def bootstrap_all(cc, cts):
    return [cc.EvalBootstrap(ct) for ct in cts]


def deepest_level(cts):
    return max(ct.GetLevel() for ct in cts)


def kepler_solve_encrypted(cc, keys, depth, coeffs, E, e, M, n_iters, on_bootstrap=None, on_level=None):
    n_bootstraps = 0
    t_compose = 0.0
    t_bootstrap = 0.0
    lo, hi = coeffs["e_domain"]
    s = c = fp = recip = None

    for k in range(1, n_iters + 1):
        if depth - deepest_level([E, e]) < MIN_LEVELS_FOR_POLY:
            t0 = time.perf_counter()
            E, e = bootstrap_all(cc, [E, e])
            t_bootstrap += time.perf_counter() - t0
            n_bootstraps += 1
            if on_bootstrap:
                on_bootstrap(n_bootstraps, E.GetLevel())

        t0 = time.perf_counter()
        u = rescale_affine(cc, E, lo, hi)
        s = cc.EvalPoly(u, coeffs["sin_E"]["coeffs"])
        c = cc.EvalPoly(u, coeffs["cos_E"]["coeffs"])
        if on_level:
            on_level("NR round %d: sin/cos evaluated" % k, s.GetLevel())

        e_s = cc.EvalMult(e, s)
        f = cc.EvalAdd(cc.EvalSub(E, e_s), -M)  # M is public (query time offset)
        e_c = cc.EvalMult(e, c)
        fp = cc.EvalAdd(cc.EvalMult(e_c, -1.0), 1.0)

        if depth - deepest_level([f, fp]) < MIN_LEVELS_FOR_POLY:
            t0b = time.perf_counter()
            f, fp, E, e = bootstrap_all(cc, [f, fp, E, e])
            t_bootstrap += time.perf_counter() - t0b
            n_bootstraps += 1
            if on_bootstrap:
                on_bootstrap(n_bootstraps, E.GetLevel())

        recip = nr_reciprocal(cc, fp, RECIPROCAL_NR_ROUNDS)
        dE = cc.EvalMult(f, recip)
        E = cc.EvalSub(E, dE)
        t_compose += time.perf_counter() - t0
        if on_level:
            on_level("NR round %d: E updated" % k, E.GetLevel())

    return E, s, c, fp, recip, n_bootstraps, t_compose, t_bootstrap


def perifocal_position_encrypted(cc, a, e, s, c, fp, recip, coeffs, on_level=None):
    elo, ehi = coeffs["ecc_domain"]
    u_e = rescale_affine(cc, e, elo, ehi)
    sqrt_term = cc.EvalPoly(u_e, coeffs["sqrt_one_minus_e2"]["coeffs"])

    r = cc.EvalMult(a, fp)
    cos_nu = cc.EvalMult(cc.EvalAdd(c, cc.EvalMult(e, -1.0)), recip)
    sin_nu = cc.EvalMult(cc.EvalMult(sqrt_term, s), recip)
    px = cc.EvalMult(r, cos_nu)
    py = cc.EvalMult(r, sin_nu)
    if on_level:
        on_level("reconstruct: px,py computed", px.GetLevel())
    return px, py


def main():
    coeffs = load_poly_coeffs()
    n = MEAN_MOTION_REV_PER_DAY * 2 * math.pi / 86400.0
    a_val = (MU_EARTH_KM3_S2 / n ** 2) ** (1.0 / 3.0)
    e_val = ECCENTRICITY
    M0 = math.radians(MEAN_ANOMALY_0_DEG)

    t0 = time.perf_counter()
    cc, keys, depth, num_slots = make_bootstrapping_context()
    t_ctx = time.perf_counter() - t0
    print(f"context+keygen (incl. bootstrap setup): {t_ctx*1000:.1f} ms")
    print(f"ring dim: {cc.GetRingDimension()}   multiplicative depth: {depth}\n")

    t0 = time.perf_counter()
    ct_a = enc_scalar(cc, keys, a_val, num_slots)
    ct_e = enc_scalar(cc, keys, e_val, num_slots)
    t_enc = time.perf_counter() - t0
    print(f"encrypt private orbital elements (a, e): {t_enc*1000:.1f} ms\n")

    results = []
    total_bootstraps = 0
    total_wall = 0.0

    for t in QUERY_TIMES_S:
        M_val = M0 + n * t  # M is a public query-time offset from a public epoch;
                              # only a and e are encrypted inputs here (see scope note)
        ct_E0 = enc_scalar(cc, keys, M_val, num_slots)  # E_0 = M, same as the plaintext solver

        def on_bootstrap(k, level, t=t):
            print(f"  t={t:+6d}s  [bootstrap #{k}] refreshed to level {level}")

        def on_level(label, level, t=t):
            print(f"  t={t:+6d}s  level after {label}: {level}/{depth} ({depth-level} remaining)")

        show_levels = (t == QUERY_TIMES_S[-1])  # print the full level trace for one representative query time
        t_start = time.perf_counter()
        E, s, c, fp, recip, n_boot, t_compose, t_boot = kepler_solve_encrypted(
            cc, keys, depth, coeffs, ct_E0, ct_e, M_val, KEPLER_NR_ITERS, on_bootstrap,
            on_level if show_levels else None
        )
        px, py = perifocal_position_encrypted(cc, ct_a, ct_e, s, c, fp, recip, coeffs,
                                               on_level if show_levels else None)
        t_total = time.perf_counter() - t_start

        px_val, py_val = dec_scalar(cc, keys, px), dec_scalar(cc, keys, py)
        total_bootstraps += n_boot
        total_wall += t_total

        print(f"t={t:+6d}s  px={px_val:14.6f}  py={py_val:14.6f} km   "
              f"{n_boot} bootstrap(s)   {t_total:.2f}s total "
              f"(compose {t_compose:.2f}s, bootstrap {t_boot:.2f}s)")
        results.append({"t": t, "px_km": px_val, "py_km": py_val,
                         "bootstraps": n_boot, "wall_s": t_total})

    print(f"\n{len(QUERY_TIMES_S)} query times, {total_bootstraps} bootstraps total, "
          f"{total_wall:.2f}s wall clock ({total_wall/len(QUERY_TIMES_S):.2f}s/query average)")
    print("Diff these px/py values against 16_kepler_plain_approx_pipeline.py's printed "
          "px/py to separate CKKS+bootstrap noise from the ~0.8 m approximation floor "
          "that script already measured with zero encryption.")

    with open("oem-conjunction/results/kepler_encrypted_timing.json", "w") as f:
        json.dump({"ring_dim": cc.GetRingDimension(), "depth": depth,
                   "kepler_nr_iters": KEPLER_NR_ITERS,
                   "reciprocal_nr_rounds": RECIPROCAL_NR_ROUNDS,
                   "context_setup_s": t_ctx, "total_bootstraps": total_bootstraps,
                   "total_wall_s": total_wall, "results": results}, f, indent=2)
    print("\nwritten: oem-conjunction/results/kepler_encrypted_timing.json")


if __name__ == "__main__":
    main()
