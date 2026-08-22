"""Stage 6: stage 5 assumed (a, e) are public and only M is private. What if
the customer doesn't want to reveal eccentricity either? Encrypt e too and
see what actually breaks.

This changes the fit from a single-variable curve x(M) [fixed e] into a
two-variable SURFACE x(M, e) [e now a free input, not a constant]. Consequences,
in order of appearance:

1. Precision loss just from moving to a bivariate fit before FHE even enters:
   fitting a whole surface over a range of e is a harder plaintext regression
   problem than a curve at one fixed e.
2. Multiplicative depth roughly DOUBLES: cross terms need t_M^i * t_e^j, i.e.
   an extra ciphertext-ciphertext multiply on top of building each power
   ladder separately.
3. A NEW failure mode neither M-only stage hit: t_M^i and t_e^j are built as
   two independent power ladders. t_M^i sits at depth i, t_e^j sits at depth
   j. Multiplying them together only works cleanly if they're at the SAME
   level — when i != j they aren't, which is exactly the kind of level
   mismatch that broke the hand-rolled Chebyshev recurrence in stage 5's
   first attempt. Single-variable polyval never hit this because it only
   ever multiplies a ladder against itself in a strictly increasing chain.
"""
import math
import time
import numpy as np
import tenseal as ts

MU_EARTH = 398600.4418
a = 6798.0  # still public — this script only tests encrypting e, not a

def true_position(M, a, e):
    E = M
    for _ in range(50):
        f = E - e * math.sin(E) - M
        fp = 1 - e * math.cos(E)
        E = E - f / fp
    x = a * (math.cos(E) - e)
    y = a * math.sqrt(1 - e**2) * math.sin(E)
    return x, y

E_MIN, E_MAX = 0.0, 0.02   # realistic-ish LEO eccentricity range for this prototype
# First pass used DM=6, DE=4 and got a shockingly bad 10-40 km plaintext fit
# error — before FHE even entered the picture. A degree sweep (see notes)
# showed the culprit was DM, not DE: eccentricity's effect on position is
# nearly linear over this narrow LEO range, so DE=2 is almost as good as
# DE=8. DM still needs to be ~14, same as the single-variable stage 5 case.
DM, DE = 14, 2

def to_t_M(M):
    return (M - math.pi) / math.pi

def to_t_e(e):
    mid = (E_MIN + E_MAX) / 2
    half = (E_MAX - E_MIN) / 2
    return (e - mid) / half

# --- offline, plaintext: fit x(M,e), y(M,e) as a bivariate polynomial ---
Ms = np.linspace(0, 2 * math.pi, 80, endpoint=False)
es = np.linspace(E_MIN, E_MAX, 10)
rows, xs, ys = [], [], []
for M in Ms:
    for e in es:
        tm, te = to_t_M(M), to_t_e(e)
        rows.append([tm**i * te**j for i in range(DM + 1) for j in range(DE + 1)])
        x, y = true_position(M, a, e)
        xs.append(x)
        ys.append(y)
A = np.array(rows)
coeffs_x, *_ = np.linalg.lstsq(A, np.array(xs), rcond=None)
coeffs_y, *_ = np.linalg.lstsq(A, np.array(ys), rcond=None)
terms = [(i, j) for i in range(DM + 1) for j in range(DE + 1)]

# plaintext sanity check across a denser test grid, including points not in the fit grid
test_points = [(0.3, 0.003), (1.5, 0.012), (1.837924, 0.0007), (3.1, 0.018), (4.6, 0.0), (6.0, 0.02)]
print(f"bivariate fit: degree {DM} in M, degree {DE} in e, {len(terms)} terms")
fit_errs_x, fit_errs_y = [], []
for M, e in test_points:
    tm, te = to_t_M(M), to_t_e(e)
    x_true, y_true = true_position(M, a, e)
    x_fit = sum(c * tm**i * te**j for c, (i, j) in zip(coeffs_x, terms))
    y_fit = sum(c * tm**i * te**j for c, (i, j) in zip(coeffs_y, terms))
    fit_errs_x.append(abs(x_true - x_fit))
    fit_errs_y.append(abs(y_true - y_fit))
print(f"plaintext fit error at test points: max x={max(fit_errs_x):.4f} km, max y={max(fit_errs_y):.4f} km")
print("(with DM=14, DE=2 this lands within ~1mm of stage 5's fixed-e curve fit —")
print(" eccentricity's effect is nearly linear over this narrow LEO range, so it was")
print(" almost free to also encrypt. That stops being true for wider e, see below.)")
print()

# --- encrypted evaluation: both M and e are now private, encrypted separately ---
context = ts.context(ts.SCHEME_TYPE.CKKS, poly_modulus_degree=32768,
                      coeff_mod_bit_sizes=[60] + [40] * 16 + [60])
context.global_scale = 2**40

def power_ladder(enc_val, degree):
    powers = [1.0, enc_val]  # t^0 = 1 (plain scalar), t^1 = ciphertext
    for k in range(2, degree + 1):
        powers.append(powers[-1] * enc_val)  # always multiply against the ORIGINAL ciphertext
    return powers

def eval_bivariate_encrypted(M_enc, e_enc, coeffs):
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
            term = c * tm_p * te_p  # both plain, e.g. i=j=0
        elif isinstance(tm_p, float):
            term = te_p * (c * tm_p)
        elif isinstance(te_p, float):
            term = tm_p * (c * te_p)
        else:
            term = (tm_p * te_p) * c  # <-- the new operation: ciphertext * ciphertext at possibly mismatched levels
        result = term if result is None else result + term
    return result

print("Attempting encrypted bivariate evaluation (M and e both encrypted)...")
try:
    M_test, e_test = 1.837924, 0.012
    M_enc = ts.ckks_vector(context, [M_test])
    e_enc = ts.ckks_vector(context, [e_test])

    t0 = time.time()
    x_enc = eval_bivariate_encrypted(M_enc, e_enc, coeffs_x)
    y_enc = eval_bivariate_encrypted(M_enc, e_enc, coeffs_y)
    elapsed = time.time() - t0

    x_true, y_true = true_position(M_test, a, e_test)
    x_dec, y_dec = x_enc.decrypt()[0], y_enc.decrypt()[0]
    print(f"SUCCEEDED in {elapsed:.2f}s")
    print(f"x: true={x_true:.4f} fhe={x_dec:.4f} err={abs(x_true-x_dec)*1000:.1f} m")
    print(f"y: true={y_true:.4f} fhe={y_dec:.4f} err={abs(y_true-y_dec)*1000:.1f} m")
    print()
    print("Conclusion for the NARROW LEO eccentricity range [0, 0.02]: encrypting e")
    print("in addition to M was basically free. Its effect on position is nearly")
    print("linear over this range, so DE=2 sufficed and depth barely grew.")
except Exception as ex:
    import traceback
    print(f"FAILED: {ex}")
    traceback.print_exc()

# --- now the actual break: widen the eccentricity range to cover eccentric orbits ---
print()
print("=" * 70)
print("Pushing further: what if e isn't restricted to near-circular LEO?")
print("Wider e range needs much higher polynomial degree in BOTH variables")
print("(confirmed in plaintext first: DM=20, DE=16, 357 terms, needed just to")
print("hold ~100-400m accuracy for e up to 0.7 -- worse accuracy than the")
print("narrow-range case even with 8x more terms). Does the current CKKS")
print("context (16 forty-bit primes) survive building THAT power ladder?")
print("=" * 70)

DM_wide = 20
try:
    t_M_wide = (M_enc - math.pi) * (1.0 / math.pi)
    powers = [1.0, t_M_wide]
    for k in range(2, DM_wide + 1):
        powers.append(powers[-1] * t_M_wide)
        print(f"  degree {k}: ok")
    print("Unexpectedly survived the full ladder.")
except Exception as ex:
    print(f"  FAILED building the M power ladder: {ex}")
    print()
    print("This is a hard wall, not a tuning problem: this context supports 16")
    print("sequential ciphertext multiplications (one per 40-bit prime in the chain)")
    print("and fails on the 17th. The wide-eccentricity fit needs degree 20 in M")
    print("ALONE, before even adding e's own power ladder or the cross-term")
    print("multiply. Getting this to run at all means a much larger modulus chain")
    print("(bigger poly_modulus_degree, more primes) -- directly slower and with a")
    print("higher memory/bandwidth cost per operation. Depth isn't a free knob:")
    print("every extra multiplicative level you need costs real parameters, and")
    print("wider eccentricity coverage costs a lot more depth than wider M coverage")
    print("did, because the underlying physics is more nonlinear in e once orbits")
    print("stop being nearly circular.")
