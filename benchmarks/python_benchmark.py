"""Performance benchmark for the Python/TenSEAL stack, mirroring
java-stack/src/main/java/sgp4fhe/Benchmark.java so the two are comparable:
same CKKS parameters, same operations timed, same one-time-vs-per-request
split (context+keygen once, then encrypt/evaluate/decrypt repeated).

Run: python3 benchmarks/python_benchmark.py > benchmarks/results/python_benchmark_latency.csv
Peak RSS is reported to stderr via resource.getrusage (bytes on macOS, KB on
Linux -- this repo's numbers were collected on macOS/arm64, same host as the
Java run, so they're directly comparable to each other).
"""
import math
import resource
import sys
import time

import numpy as np
import tenseal as ts

MU_EARTH = 398600.4418
A = 6798.0
E = 0.0007
WARMUP = 5
REPS = 30


def true_position(M, a, e):
    Ecc = M
    for _ in range(50):
        f = Ecc - e * math.sin(Ecc) - M
        fp = 1 - e * math.cos(Ecc)
        Ecc = Ecc - f / fp
    x = a * (math.cos(Ecc) - e)
    y = a * math.sqrt(1 - e ** 2) * math.sin(Ecc)
    return x, y


def to_t(M):
    return (M - math.pi) / math.pi


def fit_stage3_coeffs():
    samples_M = np.linspace(0, 2 * math.pi, 400, endpoint=False)
    samples_x = np.array([true_position(m, A, E)[0] for m in samples_M])
    t_samples = to_t(samples_M)
    return np.polyfit(t_samples, samples_x, 14)[::-1]


E_MIN, E_MAX = 0.0, 0.02
DM, DE = 14, 2


def to_t_M(M):
    return (M - math.pi) / math.pi


def to_t_e(e):
    mid = (E_MIN + E_MAX) / 2
    half = (E_MAX - E_MIN) / 2
    return (e - mid) / half


def fit_stage4_coeffs():
    Ms = np.linspace(0, 2 * math.pi, 80, endpoint=False)
    es = np.linspace(E_MIN, E_MAX, 10)
    rows, xs = [], []
    for M in Ms:
        for e in es:
            tm, te = to_t_M(M), to_t_e(e)
            rows.append([tm ** i * te ** j for i in range(DM + 1) for j in range(DE + 1)])
            xs.append(true_position(M, A, e)[0])
    Amat = np.array(rows)
    coeffs, *_ = np.linalg.lstsq(Amat, np.array(xs), rcond=None)
    terms = [(i, j) for i in range(DM + 1) for j in range(DE + 1)]
    return coeffs, terms


def power_ladder(enc_val, degree):
    powers = [1.0, enc_val]
    for _ in range(2, degree + 1):
        powers.append(powers[-1] * enc_val)
    return powers


def eval_bivariate(M_enc, e_enc, coeffs, terms):
    t_M_enc = (M_enc - math.pi) * (1.0 / math.pi)
    mid = (E_MIN + E_MAX) / 2
    half = (E_MAX - E_MIN) / 2
    t_e_enc = (e_enc - mid) * (1.0 / half)

    tm_pows = power_ladder(t_M_enc, DM)
    te_pows = power_ladder(t_e_enc, DE)

    result = None
    for c, (i, j) in zip(coeffs, terms):
        tm_p, te_p = tm_pows[i], te_pows[j]
        if isinstance(tm_p, float) and isinstance(te_p, float):
            term = c * tm_p * te_p
        elif isinstance(tm_p, float):
            term = te_p * (c * tm_p)
        elif isinstance(te_p, float):
            term = tm_p * (c * te_p)
        else:
            term = (tm_p * te_p) * c
        result = term if result is None else result + term
    return result


def time_op(name, op, reps=REPS, warmup=WARMUP):
    for _ in range(warmup):
        op()
    samples = []
    for _ in range(reps):
        t0 = time.perf_counter()
        op()
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    n = len(samples)
    mean = sum(samples) / n
    median = samples[n // 2]
    p95 = samples[min(n - 1, math.ceil(n * 0.95) - 1)]
    print(f"{name},{n},{mean:.4f},{median:.4f},{samples[0]:.4f},{samples[-1]:.4f},{p95:.4f}")


def main():
    print("operation,n,mean_ms,median_ms,min_ms,max_ms,p95_ms")

    context_times = []
    context = None
    for _ in range(10):
        t0 = time.perf_counter()
        context = ts.context(ts.SCHEME_TYPE.CKKS, poly_modulus_degree=32768,
                              coeff_mod_bit_sizes=[60] + [40] * 16 + [60])
        context.global_scale = 2 ** 40
        context_times.append((time.perf_counter() - t0) * 1000)
    context_times.sort()
    n = len(context_times)
    print(f"context_setup_incl_keygen,{n},{sum(context_times)/n:.4f},{context_times[n//2]:.4f},"
          f"{context_times[0]:.4f},{context_times[-1]:.4f},{context_times[min(n-1, math.ceil(n*0.95)-1)]:.4f}")

    time_op("encrypt_scalar", lambda: ts.ckks_vector(context, [1.837924]))

    sample_cipher = ts.ckks_vector(context, [1.837924])
    time_op("decrypt_scalar", lambda: sample_cipher.decrypt())

    a_enc = ts.ckks_vector(context, [0.6])
    b_enc = ts.ckks_vector(context, [0.4])
    time_op("add_ciphertexts", lambda: a_enc + b_enc)
    time_op("add_plain", lambda: a_enc + 0.4)
    time_op("multiply_ciphertexts_incl_relin_rescale", lambda: a_enc * b_enc)

    coeffs_x = fit_stage3_coeffs()
    t_cipher = ts.ckks_vector(context, [to_t(1.837924)])
    time_op("stage3_horner_degree14_full_eval", lambda: t_cipher.polyval(list(coeffs_x)))

    coeffs_biv_x, terms = fit_stage4_coeffs()
    m_enc = ts.ckks_vector(context, [1.837924])
    e_enc = ts.ckks_vector(context, [0.012])
    time_op("stage4_bivariate_degree14x2_full_eval",
            lambda: eval_bivariate(m_enc, e_enc, coeffs_biv_x, terms))

    after_stage3 = t_cipher.polyval(list(coeffs_x))
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports ru_maxrss in bytes; Linux reports KB.
    peak_rss_bytes = peak_rss if sys.platform == "darwin" else peak_rss * 1024
    print(f"# peak_rss_bytes={peak_rss_bytes}", file=sys.stderr)
    print(f"# fresh_ciphertext_bytes={len(sample_cipher.serialize())}", file=sys.stderr)
    print(f"# depth14_ciphertext_bytes={len(after_stage3.serialize())}", file=sys.stderr)


if __name__ == "__main__":
    main()
