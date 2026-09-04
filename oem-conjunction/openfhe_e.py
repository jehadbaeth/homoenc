"""Shared OpenFHE CKKS primitives for Approach E.

Packs many public query times into one ciphertext (one BLOCK-wide SIMD
lane per time), interpolates both encrypted OEMs, forms distance^2, and
iterates the offline sign polynomial with EvalBootstrap when depth runs
out. The production disclosure is a masked homomorphic sum of the
saturated per-point flags — one decrypt.

Demo-grade parameters (HEStd_NotSet, ring 2^13), same as 09_/13_.
"""
import os

if "OMP_NUM_THREADS" not in os.environ:
    # Physical cores, not hyperthreads. OpenFHE's own guidance: HT often
    # slows CKKS bootstrap. Override with OMP_NUM_THREADS in the environment.
    os.environ["OMP_NUM_THREADS"] = str(max(1, (os.cpu_count() or 2) // 2))

import openfhe

from common import lagrange_weights

BLOCK = 64
THRESHOLD_KM = 10.0
SCALE_KM2 = 5_000_000.0
TOTAL_COMPOSITIONS = 11
LOCAL_HALF_SPAN_S = 1800
LEVEL_BUDGET = [4, 4]
LEVELS_AFTER_BOOTSTRAP = 15
MIN_LEVELS_FOR_POLY = 8


def pad(values, block=BLOCK):
    return list(values) + [0.0] * (block - len(values))


def make_bootstrapping_context(num_blocks):
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
    assert num_blocks * BLOCK <= num_slots, (
        f"need {num_blocks * BLOCK} slots, context has {num_slots}"
    )

    cc.EvalBootstrapSetup(LEVEL_BUDGET, [0, 0], num_slots)
    keys = cc.KeyGen()
    cc.EvalMultKeyGen(keys.secretKey)
    cc.EvalSumKeyGen(keys.secretKey)
    cc.EvalBootstrapKeyGen(keys.secretKey, num_slots)
    return cc, keys, depth, num_slots


def local_oem_for_cluster(oem, center, half_span=LOCAL_HALF_SPAN_S):
    idx = [i for i, t in enumerate(oem["t"]) if abs(t - center) <= half_span]
    local = {k: [oem[k][i] for i in idx] for k in ("t", "x", "y", "z")}
    assert len(local["t"]) <= BLOCK, (
        f"cluster at {center}s has {len(local['t'])} samples, > BLOCK={BLOCK}"
    )
    return local


def tile_per_cluster(local_oems, cluster_of, key, block=BLOCK):
    out = []
    for ci in cluster_of:
        out.extend(pad(local_oems[ci][key], block))
    return out


def build_weights_per_cluster(local_oems, cluster_of, query_ts, block=BLOCK):
    out = []
    for ci, t in zip(cluster_of, query_ts):
        out.extend(pad(lagrange_weights(local_oems[ci]["t"], t), block))
    return out


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


def encrypt_packed(cc, keys, values):
    return cc.Encrypt(keys.publicKey, cc.MakeCKKSPackedPlaintext(values))


def encrypted_scaled_distance(cc, keys, packed_a, packed_b, w_a, w_b, threshold_sq=THRESHOLD_KM ** 2):
    """packed_* are 3-tuples of ciphertext (x,y,z); w_* are plaintext weight vectors."""
    ct_xa, ct_ya, ct_za = packed_a
    ct_xb, ct_yb, ct_zb = packed_b
    pt_wa = cc.MakeCKKSPackedPlaintext(w_a)
    pt_wb = cc.MakeCKKSPackedPlaintext(w_b)

    xa = cc.EvalInnerProduct(ct_xa, pt_wa, BLOCK)
    ya = cc.EvalInnerProduct(ct_ya, pt_wa, BLOCK)
    za = cc.EvalInnerProduct(ct_za, pt_wa, BLOCK)
    xb = cc.EvalInnerProduct(ct_xb, pt_wb, BLOCK)
    yb = cc.EvalInnerProduct(ct_yb, pt_wb, BLOCK)
    zb = cc.EvalInnerProduct(ct_zb, pt_wb, BLOCK)

    dx, dy, dz = cc.EvalSub(xa, xb), cc.EvalSub(ya, yb), cc.EvalSub(za, zb)
    d2 = cc.EvalAdd(cc.EvalAdd(cc.EvalMult(dx, dx), cc.EvalMult(dy, dy)), cc.EvalMult(dz, dz))
    return cc.EvalMult(cc.EvalAdd(d2, -threshold_sq), 1.0 / SCALE_KM2)


def compose_sign(cc, cur, coeffs, depth, n_compositions=TOTAL_COMPOSITIONS, on_step=None):
    """Iterate the sign polynomial, bootstrapping when remaining depth < 8.

    on_step(k, ciphertext, n_bootstraps_so_far, compose_s, bootstrap_s) is
    called after each composition (k is 1-based).
    """
    n_bootstraps = 0
    t_compose = 0.0
    t_bootstrap = 0.0
    import time

    for k in range(1, n_compositions + 1):
        remaining = depth - cur.GetLevel()
        if remaining < MIN_LEVELS_FOR_POLY:
            t0 = time.perf_counter()
            cur = cc.EvalBootstrap(cur)
            dt = time.perf_counter() - t0
            t_bootstrap += dt
            n_bootstraps += 1
        t0 = time.perf_counter()
        cur = cc.EvalPoly(cur, coeffs)
        t_compose += time.perf_counter() - t0
        if on_step is not None:
            on_step(k, cur, n_bootstraps, t_compose, t_bootstrap)
    return cur, n_bootstraps, t_compose, t_bootstrap


def decrypt_block_slots(cc, keys, ct, n_points, num_slots):
    pt = cc.Decrypt(ct, keys.secretKey)
    pt.SetLength(n_points * BLOCK)
    vals = pt.GetRealPackedValue()
    return [vals[i * BLOCK] for i in range(n_points)]


def masked_flag_sum(cc, keys, ct, n_points, num_slots):
    mask = [0.0] * num_slots
    for i in range(n_points):
        mask[i * BLOCK] = 1.0
    masked = cc.EvalMult(ct, cc.MakeCKKSPackedPlaintext(mask))
    summed = cc.EvalSum(masked, num_slots)
    result = cc.Decrypt(summed, keys.secretKey)
    result.SetLength(1)
    return result.GetRealPackedValue()[0]
