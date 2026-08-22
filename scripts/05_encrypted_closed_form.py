"""Stage 5: restructure the problem so it never needs iteration or division
at all, which is the actual fix for what stage 4 exposed.

Instead of solving Kepler's equation homomorphically (iterative, needs
ciphertext/ciphertext division), we exploit that for a FIXED (a, e) — which
are non-secret orbit shape parameters, not the customer's live private state
— position is just some periodic function of mean anomaly M:

    x(M), y(M)

We fit that function offline, in plaintext, as a monomial polynomial in a
rescaled variable t = (M - pi) / pi (t in [-1, 1]), then evaluate it
homomorphically with repeated +, -, * only. No division, anywhere, ever.
Privacy-wise: the client encrypts M (their private orbital phase), the server
holds only public fit coefficients and evaluates the polynomial homomorphically,
the client decrypts the final x, y. The server never sees plaintext M or the
result.

(First attempt at this fit the polynomial in a Chebyshev basis for numerical
stability, then converted to monomial coefficients for CKKS's polyval — that
conversion turned out to be its own numerical disaster, see the comment
further down.)
"""
import math
import time
import numpy as np
import tenseal as ts

MU_EARTH = 398600.4418
a = 6798.0
e = 0.0007

def mean_motion(a):
    return math.sqrt(MU_EARTH / a**3)

def true_position(M, a, e):
    E = M
    for _ in range(50):
        f = E - e * math.sin(E) - M
        fp = 1 - e * math.cos(E)
        E = E - f / fp
    x = a * (math.cos(E) - e)
    y = a * math.sqrt(1 - e**2) * math.sin(E)
    return x, y

# --- offline, plaintext, server-side: fit x(M), y(M) once for this (a, e) ---
DEGREE = 14
samples_M = np.linspace(0, 2 * math.pi, 400, endpoint=False)
samples_x = np.array([true_position(m, a, e)[0] for m in samples_M])
samples_y = np.array([true_position(m, a, e)[1] for m in samples_M])

# domain map M in [0, 2pi) -> t in [-1, 1], required for Chebyshev basis
def to_t(M):
    return (M - math.pi) / math.pi

t_samples = to_t(samples_M)
# First attempt at this used a Chebyshev fit (for numerical stability) then
# converted to monomial coefficients via cheb2poly for CKKS's polyval. That
# conversion turned out to be catastrophically ill-conditioned on its own —
# confirmed by re-running it in plain numpy with no encryption involved at
# all: same ~77 km error regardless of degree. Not a CKKS problem, a basis-
# change problem. Fitting numpy.polyfit directly in the monomial basis, but
# on the same well-scaled t in [-1, 1] domain, turns out to be stable up to
# degree ~14 for this orbit — so skip Chebyshev entirely and fit monomial
# coefficients directly.
coeffs_x = np.polyfit(t_samples, samples_x, DEGREE)[::-1]  # numpy gives highest power first
coeffs_y = np.polyfit(t_samples, samples_y, DEGREE)[::-1]  # polyval wants ascending powers

# sanity check the fit quality in plaintext before ever touching FHE
fit_errs_x, fit_errs_y = [], []
for m in samples_M:
    t = to_t(m)
    fit_errs_x.append(abs(np.polyval(coeffs_x[::-1], t) - true_position(m, a, e)[0]))
    fit_errs_y.append(abs(np.polyval(coeffs_y[::-1], t) - true_position(m, a, e)[1]))
print(f"plaintext monomial fit (t in [-1,1]), degree {DEGREE}: max |error| x={max(fit_errs_x):.2e} km, y={max(fit_errs_y):.2e} km")
print()

# --- client side: encrypt private M once ---
context = ts.context(ts.SCHEME_TYPE.CKKS, poly_modulus_degree=32768,
                      coeff_mod_bit_sizes=[60] + [40] * 16 + [60])
context.global_scale = 2**40

def eval_poly_encrypted(M_enc, power_coeffs):
    # t_enc = (M_enc - pi) / pi -- subtract/scale by known plaintext constants only
    t_enc = (M_enc - math.pi) * (1.0 / math.pi)
    return t_enc.polyval(list(power_coeffs))

# --- test across several M values spanning the whole orbit, not just one ---
test_Ms = [0.3, 1.5, 1.837924, 3.1, 4.6, 6.0]

print(f"{'M':>10} {'x true':>12} {'x FHE':>12} {'err x (m)':>10} {'y true':>12} {'y FHE':>12} {'err y (m)':>10} {'time (s)':>9}")
for M in test_Ms:
    x_true, y_true = true_position(M, a, e)

    M_enc = ts.ckks_vector(context, [M])
    t0 = time.time()
    x_enc = eval_poly_encrypted(M_enc, coeffs_x)
    y_enc = eval_poly_encrypted(M_enc, coeffs_y)
    elapsed = time.time() - t0

    x_fhe = x_enc.decrypt()[0]
    y_fhe = y_enc.decrypt()[0]

    print(f"{M:10.4f} {x_true:12.4f} {x_fhe:12.4f} {abs(x_true - x_fhe) * 1000:10.4f} "
          f"{y_true:12.4f} {y_fhe:12.4f} {abs(y_true - y_fhe) * 1000:10.4f} {elapsed:9.3f}")

print()
print("No decryption happened server-side at any point in this version.")
print("No division, ciphertext or otherwise, was needed at any point.")
print("Depth cost is fixed and known in advance: proportional to DEGREE, not to a")
print("data-dependent iteration count. That predictability is itself valuable —")
print("real deployments need to size FHE parameters before they know the answer.")
print()
print("The tradeoff this makes explicit: (a, e) must be public/known to whoever")
print("fits the polynomial. If eccentricity itself is considered sensitive")
print("customer data, this approach doesn't cover that — it only protects the")
print("orbital *phase* (M), not the orbit *shape*. Worth deciding which of those")
print("actually needs to stay private before picking this design.")
