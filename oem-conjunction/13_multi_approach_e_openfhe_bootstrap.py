"""Scenario 2, Approach E: OpenFHE CKKS bootstrapping flag-sum (see
09_approach_e_openfhe_bootstrap.py), run over the seven real close-approach
clusters from the wider +/-3h search instead of the single global minimum.
Same from-source OpenFHE build, same non-production demo security
parameters, same masked-sum fix for the within-block corruption documented
in 09_'s docstring. The only change is the candidate grid: 7 clusters x 9
points/cluster = 63 candidate times, still fitting in one 64-slot-per-block
SIMD ciphertext (63*64 = 4032 <= 4096 slots at ring dimension 2**13).

This is the scenario that actually stresses the design: two of the seven
clusters (11.698 km, 13.276 km true miss distance) sit only a few km
outside the 10 km threshold, mixed in with the one true violation
(5.432 km) and four clearly-safe events. If bootstrapping's fix generalizes
beyond the single-event case, the decrypted sum here should match
n_points - 2*1 = 61, with the same 11 compositions used before -- not a
retuned constant for this scenario.

Run: python3 oem-conjunction/13_multi_approach_e_openfhe_bootstrap.py
"""
import csv
import json
import time

import openfhe

from common import load_oem, lagrange_weights

THRESHOLD_KM = 10.0
SCALE_KM2 = 5_000_000.0
BLOCK = 64
TOTAL_COMPOSITIONS = 11  # unchanged from the single-event scenario -- see module docstring
CLUSTER_WINDOW_S = 40
CLUSTER_STEP_S = 10.0


def load_sign_poly():
    with open("oem-conjunction/data/sign_poly_coeffs.json") as f:
        return json.load(f)["coeffs"]


def load_clusters():
    with open("oem-conjunction/data/multi_ground_truth.csv") as f:
        return [float(row["t_center_offset_s"]) for row in csv.DictReader(f)]


def build_query_ts(clusters):
    n_per_cluster = int(2 * CLUSTER_WINDOW_S / CLUSTER_STEP_S) + 1
    query_ts, cluster_of = [], []
    for ci, center in enumerate(clusters):
        for i in range(n_per_cluster):
            query_ts.append(center - CLUSTER_WINDOW_S + i * CLUSTER_STEP_S)
            cluster_of.append(ci)
    return query_ts, cluster_of


LOCAL_HALF_SPAN_S = 1800  # matches the single-event scenario's own OEM span


def pad(values, block=BLOCK):
    return list(values) + [0.0] * (block - len(values))


def local_oem_for_cluster(oem, center, half_span=LOCAL_HALF_SPAN_S):
    """Each SIMD block can only hold BLOCK=64 samples, so each cluster gets
    its own local interpolation basis (nearest samples within +/-half_span),
    exactly like the single-event scenario's OEM did for its one event --
    not the full multi-hour OEM, which is far larger than one block."""
    idx = [i for i, t in enumerate(oem["t"]) if abs(t - center) <= half_span]
    local = {k: [oem[k][i] for i in idx] for k in ("t", "x", "y", "z")}
    assert len(local["t"]) <= BLOCK, f"cluster at {center}s has {len(local['t'])} local samples, > BLOCK={BLOCK}"
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


def make_bootstrapping_context(num_blocks):
    secret_key_dist = openfhe.SecretKeyDist.UNIFORM_TERNARY
    level_budget = [4, 4]
    levels_available_after_bootstrap = 15
    bootstrap_depth = openfhe.FHECKKSRNS.GetBootstrapDepth(level_budget, secret_key_dist)
    depth = levels_available_after_bootstrap + bootstrap_depth

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
    assert num_blocks * BLOCK <= num_slots, "not enough slots for full SIMD packing"

    cc.EvalBootstrapSetup(level_budget, [0, 0], num_slots)
    keys = cc.KeyGen()
    cc.EvalMultKeyGen(keys.secretKey)
    cc.EvalSumKeyGen(keys.secretKey)
    cc.EvalBootstrapKeyGen(keys.secretKey, num_slots)

    return cc, keys, depth, num_slots


def main():
    oem_a = load_oem("oem-conjunction/data/oem_a_multi.csv")
    oem_b = load_oem("oem-conjunction/data/oem_b_multi.csv")
    coeffs = load_sign_poly()
    threshold_sq = THRESHOLD_KM ** 2
    clusters = load_clusters()
    query_ts, cluster_of = build_query_ts(clusters)
    n_points = len(query_ts)
    total_slots = n_points * BLOCK

    t0 = time.perf_counter()
    cc, keys, depth, num_slots = make_bootstrapping_context(n_points)
    t_ctx = time.perf_counter() - t0
    print(f"context+keygen (incl. bootstrap setup): {t_ctx*1000:.1f} ms")
    print(f"ring dim: {cc.GetRingDimension()}   num_slots: {num_slots}   "
          f"packed slots used: {total_slots}   multiplicative depth: {depth}")
    print(f"{len(clusters)} clusters, {n_points} total candidate points")

    t0 = time.perf_counter()
    local_a = [local_oem_for_cluster(oem_a, c) for c in clusters]
    local_b = [local_oem_for_cluster(oem_b, c) for c in clusters]
    big_xa, big_ya, big_za = (tile_per_cluster(local_a, cluster_of, k) for k in ("x", "y", "z"))
    big_xb, big_yb, big_zb = (tile_per_cluster(local_b, cluster_of, k) for k in ("x", "y", "z"))
    w_a_big = build_weights_per_cluster(local_a, cluster_of, query_ts)
    w_b_big = build_weights_per_cluster(local_b, cluster_of, query_ts)

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
        if remaining < 8:
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

    # Diagnostic verification only -- see 09_'s docstring for why this section
    # exists and why a real deployment would skip it.
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

    with open("oem-conjunction/results/multi_approach_e_openfhe_bootstrap_flags.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cluster_index", "t_offset_s", "raw_flag", "below_threshold_flagged"])
        for ci, t, flag in zip(cluster_of, query_ts, flags):
            w.writerow([ci, t, flag, int(flag < 0)])

    print("\nper-cluster verdict (from the diagnostic per-point flags above):")
    for ci in range(len(clusters)):
        cluster_flags = [f for c, f in zip(cluster_of, flags) if c == ci]
        verdict = "FLAGGED below threshold" if any(f < 0 for f in cluster_flags) else "not flagged"
        print(f"  cluster {ci} (t={clusters[ci]:+9.1f}s): {verdict}")

    # Production disclosure: masked homomorphic sum, single decrypt.
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

    ideal_sum_if_1_below_threshold = n_points - 2 * 1
    with open("oem-conjunction/results/multi_approach_e_flag_sum.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n_points", "decrypted_flag_sum", "ideal_sum_for_true_count_1", "compositions", "bootstraps"])
        w.writerow([n_points, flag_sum, ideal_sum_if_1_below_threshold, TOTAL_COMPOSITIONS, n_bootstraps])

    print(f"\nhomomorphic sum + single decrypt: {t_sum*1000:.1f} ms")
    print(f"decrypted sum of {n_points} saturated flags: {flag_sum:.4f}")
    print(f"ideal sum if exactly 1 of {n_points} points is genuinely below threshold: "
          f"{ideal_sum_if_1_below_threshold}")
    print(f"estimated count from this sum, (n - sum) / 2: {(n_points - flag_sum) / 2.0:.4f}  "
          f"(true count: 1)")


if __name__ == "__main__":
    main()
