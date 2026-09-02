"""Approach E: OpenFHE CKKS bootstrapping fixes Approach D's saturation
problem. Same per-point pipeline as Approaches C/D (encrypted distance_sq ->
scaled -> sign-approximation polynomial -> per-point flag near +-1), but
built on OpenFHE (built from source, see docs/notes on the build) instead of
TenSEAL/SEAL, specifically to get CKKS bootstrapping. 08_sign_iteration_depth_wall.py
showed that the fitted sign polynomial (03_fit_sign_polynomial.py) needs
~10-11 total compositions to saturate all 61 candidate flags to confident
+-1 values, but TenSEAL/SEAL (no bootstrapping) only has depth for 2 extra
compositions beyond the first before `scale out of bounds`. This script
reruns the same computation on OpenFHE, using EvalBootstrap between
composition batches to refresh levels, so all 11 compositions actually run,
then sums the 61 saturated flags homomorphically and decrypts ONLY that sum.

All 61 candidate points are packed into ONE ciphertext (SIMD/CKKS packing),
not 61 separate ciphertexts: each candidate time's 59-sample interpolation
window occupies its own 64-slot block (next power of two above the 59
samples per OEM), so all 61 points go through the same EvalPoly/EvalBootstrap
calls simultaneously. This is standard CKKS batching, not a shortcut: it
still applies the identical per-point polynomial independently to each of
the 61 encrypted scalars, and still only the final aggregate is decrypted
for the reported result.

Honesty notes (read before citing this result):
  - The CKKS bootstrapping example parameters used here (HEStd_NotSet,
    ring dimension 2**13) are OpenFHE's own *demo* parameters, chosen for
    speed of iteration on a laptop -- NOT a 128-bit-secure production
    parameter set. A production deployment would need a much larger ring
    dimension (bootstrapping at HEStd_128_classic commonly needs 2**16-2**17),
    which is far slower per bootstrap; this script reports wall-clock time
    for the demo parameters and flags this explicitly rather than
    presenting it as a production-ready number.
  - This script decrypts the per-point flags in a clearly separated
    "diagnostic verification" section purely to check saturation and cross
    validate against plaintext ground truth for this report -- exactly like
    08_sign_iteration_depth_wall.py decrypted intermediate compositions to
    diagnose the depth wall. The number actually meant to leave the
    encrypted domain in a real deployment of this pattern is the single
    homomorphic sum, computed and decrypted separately below.
  - The final sum is computed via a one-hot plaintext mask (1.0 at each
    point's representative slot, index i*BLOCK, 0 elsewhere) multiplied in
    before EvalSum, NOT a naive EvalSum over every slot divided by BLOCK.
    Decrypting a full 64-slot block directly (before AND after the 11
    compositions) shows it is NOT a uniform replica of one value the way a
    textbook "replicate across the batch" inner product would be: even in
    the pre-composition `scaled` ciphertext, only slot 0 of each block holds
    the value that matches this point's correctly-computed distance; the
    other 63 slots hold different, smaller-magnitude values, almost
    certainly leftover partial sums from EvalInnerProduct's underlying
    rotate-and-add reduction rather than 59 independent real samples plus 5
    zero-padding slots as the packing scheme's block layout might suggest.
    Those other slots are also close enough to zero to sit in the sign
    polynomial's unstable region, so after 11 compositions most of them
    saturate to +1 regardless of the block's true sign. This was caught by
    decrypting the raw block for t=0s (the one genuinely-below-threshold
    point) directly: slot 0 correctly held -1 (matching the true label),
    but only slots 0-27 of the 64 held -1 after composition -- slots 28-63
    had all saturated to +1 -- so a naive whole-block average silently
    corrupts the count (an earlier run of this script, with that bug, gave
    56.4375 instead of 59). Masking to exactly slot i*BLOCK per point before
    summing avoids this: the plaintext zero at every other slot position
    kills that corrupted majority outright, regardless of how wrong the
    ciphertext's value was there. This is a property of how EvalInnerProduct
    populates the block, not proven to be specifically an x=0 fixed-point
    instability; treat the mechanism as "only slot 0 is trustworthy," not as
    a claim about which slots are "padding."

Run: python3 oem-conjunction/09_approach_e_openfhe_bootstrap.py
"""
import csv
import json
import time

import openfhe

from common import load_oem, lagrange_weights

WINDOW_S = 300
GRID_STEP_S = 10.0
THRESHOLD_KM = 10.0
SCALE_KM2 = 5_000_000.0  # same operating parameter as Approaches C/D
BLOCK = 64  # next power of two >= 59 samples/OEM; one SIMD block per candidate time
TOTAL_COMPOSITIONS = 11  # matches the ~10-11 compositions 08_ found necessary in plaintext


def load_sign_poly():
    with open("oem-conjunction/data/sign_poly_coeffs.json") as f:
        return json.load(f)["coeffs"]


def pad(values, block=BLOCK):
    return list(values) + [0.0] * (block - len(values))


def tile(values, n_blocks, block=BLOCK):
    p = pad(values, block)
    out = []
    for _ in range(n_blocks):
        out.extend(p)
    return out


def build_weights_big(sample_times, query_ts, block=BLOCK):
    out = []
    for t in query_ts:
        out.extend(pad(lagrange_weights(sample_times, t), block))
    return out


def make_bootstrapping_context(num_blocks):
    secret_key_dist = openfhe.SecretKeyDist.UNIFORM_TERNARY
    level_budget = [4, 4]
    levels_available_after_bootstrap = 15  # ~3 degree-27 EvalPoly compositions per cycle
    bootstrap_depth = openfhe.FHECKKSRNS.GetBootstrapDepth(level_budget, secret_key_dist)
    depth = levels_available_after_bootstrap + bootstrap_depth

    params = openfhe.CCParamsCKKSRNS()
    params.SetSecretKeyDist(secret_key_dist)
    # NotSet + small ring dimension: OpenFHE's own bootstrapping-example demo
    # parameters, chosen for iteration speed on a laptop. NOT production security.
    # See module docstring.
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
    assert num_blocks * BLOCK <= num_slots, "not enough slots for full SIMD packing"

    cc.EvalBootstrapSetup(level_budget, [0, 0], num_slots)
    keys = cc.KeyGen()
    cc.EvalMultKeyGen(keys.secretKey)
    cc.EvalSumKeyGen(keys.secretKey)
    cc.EvalBootstrapKeyGen(keys.secretKey, num_slots)

    return cc, keys, depth, num_slots


def main():
    oem_a = load_oem("oem-conjunction/data/oem_a.csv")
    oem_b = load_oem("oem-conjunction/data/oem_b.csv")
    coeffs = load_sign_poly()
    threshold_sq = THRESHOLD_KM ** 2

    n_points = int(2 * WINDOW_S / GRID_STEP_S) + 1
    query_ts = [-WINDOW_S + i * GRID_STEP_S for i in range(n_points)]
    total_slots = n_points * BLOCK

    t0 = time.perf_counter()
    cc, keys, depth, num_slots = make_bootstrapping_context(n_points)
    t_ctx = time.perf_counter() - t0
    print(f"context+keygen (incl. bootstrap setup): {t_ctx*1000:.1f} ms")
    print(f"ring dim: {cc.GetRingDimension()}   num_slots: {num_slots}   "
          f"packed slots used: {total_slots}   multiplicative depth: {depth}")

    t0 = time.perf_counter()
    big_xa, big_ya, big_za = (tile(oem_a[k], n_points) for k in ("x", "y", "z"))
    big_xb, big_yb, big_zb = (tile(oem_b[k], n_points) for k in ("x", "y", "z"))
    w_a_big = build_weights_big(oem_a["t"], query_ts)
    w_b_big = build_weights_big(oem_b["t"], query_ts)

    def enc(values):
        return cc.Encrypt(keys.publicKey, cc.MakeCKKSPackedPlaintext(values))

    ct_xa, ct_ya, ct_za = enc(big_xa), enc(big_ya), enc(big_za)
    ct_xb, ct_yb, ct_zb = enc(big_xb), enc(big_yb), enc(big_zb)
    pt_wa = cc.MakeCKKSPackedPlaintext(w_a_big)
    pt_wb = cc.MakeCKKSPackedPlaintext(w_b_big)
    t_enc = time.perf_counter() - t0
    print(f"encrypt (6 ciphertexts, all {n_points} points packed together): {t_enc*1000:.1f} ms")

    t0 = time.perf_counter()
    xa_i = cc.EvalInnerProduct(ct_xa, pt_wa, BLOCK)
    ya_i = cc.EvalInnerProduct(ct_ya, pt_wa, BLOCK)
    za_i = cc.EvalInnerProduct(ct_za, pt_wa, BLOCK)
    xb_i = cc.EvalInnerProduct(ct_xb, pt_wb, BLOCK)
    yb_i = cc.EvalInnerProduct(ct_yb, pt_wb, BLOCK)
    zb_i = cc.EvalInnerProduct(ct_zb, pt_wb, BLOCK)

    dx, dy, dz = cc.EvalSub(xa_i, xb_i), cc.EvalSub(ya_i, yb_i), cc.EvalSub(za_i, zb_i)
    d2 = cc.EvalAdd(cc.EvalAdd(cc.EvalMult(dx, dx), cc.EvalMult(dy, dy)), cc.EvalMult(dz, dz))
    scaled = cc.EvalMult(cc.EvalAdd(d2, -threshold_sq), 1.0 / SCALE_KM2)
    t_dist = time.perf_counter() - t0
    print(f"encrypted distance_sq + scale for all {n_points} points (1 SIMD pass): "
          f"{t_dist*1000:.1f} ms   (level {scaled.GetLevel()}/{depth})")

    cur = scaled
    n_bootstraps = 0
    t_compose_total = 0.0
    t_bootstrap_total = 0.0
    for k in range(1, TOTAL_COMPOSITIONS + 1):
        remaining = depth - cur.GetLevel()
        if remaining < 8:  # not enough headroom for another degree-27 EvalPoly + margin
            t0 = time.perf_counter()
            cur = cc.EvalBootstrap(cur)
            dt = time.perf_counter() - t0
            t_bootstrap_total += dt
            n_bootstraps += 1
            print(f"  [bootstrap #{n_bootstraps}] refreshed to level {cur.GetLevel()}  ({dt:.2f}s)")
        t0 = time.perf_counter()
        cur = cc.EvalPoly(cur, coeffs)
        t_compose_total += time.perf_counter() - t0

    print(f"{TOTAL_COMPOSITIONS} sign-polynomial compositions: {t_compose_total*1000:.1f} ms "
          f"across {n_bootstraps} bootstraps ({t_bootstrap_total*1000:.1f} ms total bootstrap time)")

    # --- Diagnostic verification only (mirrors 08_'s per-point decryption to
    # check saturation): decrypt the 61 per-point flags to confirm they
    # actually saturated and to cross-check against plaintext ground truth.
    # A real deployment of this pattern would skip this and only decrypt the
    # homomorphic sum computed below.
    verify_pt = cc.Decrypt(cur, keys.secretKey)
    verify_pt.SetLength(total_slots)
    verify_vals = verify_pt.GetRealPackedValue()
    flags = [verify_vals[i * BLOCK] for i in range(n_points)]
    n_flagged = sum(1 for f in flags if f < 0)
    max_dev_from_saturation = max(abs(abs(f) - 1.0) for f in flags)
    print(f"\n[diagnostic, not part of the production disclosure] per-point flags decrypted:")
    print(f"  min={min(flags):.6f}  max={max(flags):.6f}  "
          f"max |{{|flag|-1}}| (distance from saturation): {max_dev_from_saturation:.6f}")
    print(f"  points flagged below threshold: {n_flagged} / {n_points}")

    with open("oem-conjunction/results/approach_e_openfhe_bootstrap_flags.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_offset_s", "raw_flag", "below_threshold_flagged"])
        for t, flag in zip(query_ts, flags):
            w.writerow([t, flag, int(flag < 0)])

    # --- The actual production disclosure: homomorphic sum, single decrypt. ---
    # IMPORTANT: naively EvalSum-ing the whole packed ciphertext and dividing by
    # BLOCK (treating each 64-slot block as a uniform replica of one flag) is
    # WRONG here. Only slot 0 of each 64-wide block reliably holds this point's
    # correct value; the other 63 slots hold different, smaller-magnitude
    # values (see module docstring) that sit close enough to the sign
    # polynomial's unstable region to mostly saturate to +1 after 11
    # compositions, regardless of the block's true sign. This was caught by
    # decrypting block 30 (t=0s, the one genuinely below-threshold point)
    # directly: slot 0 held -1 as expected, but slots 28-63 of that same
    # block had all saturated to +1. Averaging over the full block silently
    # corrupts the count. The fix: mask down to exactly one representative
    # slot per point (index i*BLOCK) before summing, so the other, unreliable
    # slots are multiplied by an exact plaintext 0 and contribute nothing,
    # instead of being averaged in.
    mask = [0.0] * num_slots
    for i in range(n_points):
        mask[i * BLOCK] = 1.0
    pt_mask = cc.MakeCKKSPackedPlaintext(mask)

    t0 = time.perf_counter()
    masked = cc.EvalMult(cur, pt_mask)
    sum_enc = cc.EvalSum(masked, num_slots)
    result_pt = cc.Decrypt(sum_enc, keys.secretKey)
    result_pt.SetLength(1)
    flag_sum = result_pt.GetRealPackedValue()[0]
    t_sum = time.perf_counter() - t0

    ideal_sum_if_1_below_threshold = n_points - 2 * 1  # true ground truth: 1/61 points below threshold
    with open("oem-conjunction/results/approach_e_flag_sum.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n_points", "decrypted_flag_sum", "ideal_sum_for_true_count_1", "compositions", "bootstraps"])
        w.writerow([n_points, flag_sum, ideal_sum_if_1_below_threshold, TOTAL_COMPOSITIONS, n_bootstraps])

    print(f"\nhomomorphic sum + single decrypt: {t_sum*1000:.1f} ms")
    print(f"decrypted sum of {n_points} saturated flags: {flag_sum:.4f}")
    print(f"ideal sum if exactly 1 of {n_points} points is genuinely below threshold: "
          f"{ideal_sum_if_1_below_threshold}")
    print(f"Approach D (TenSEAL, no bootstrapping, no saturation) got 37.3017 for the same scenario.")
    print(f"estimated count from this sum, (n - sum) / 2: {(n_points - flag_sum) / 2.0:.4f}  "
          f"(true count: 1)")


if __name__ == "__main__":
    main()
