"""Stage 4: attempt the actual hard part — solving Kepler's equation under
encryption. This is where FHE's real limitations show up, not as an opaque
failure, but as concrete, explainable costs.

Two problems collide here:

1. No sin()/cos() natively. CKKS only gives +, -, * (and division by a known
   plaintext). Newton's method needs sin(E) and cos(E) every iteration, so we
   substitute a Taylor polynomial. Every extra term = extra multiplicative
   depth = more noise budget consumed = larger, slower parameters.

2. No convergence check. In plaintext, Newton's method stops when the update
   is small enough — that's a comparison on a value the server can't see.
   Under encryption we can't ask "did this converge yet", so we just run a
   FIXED number of iterations blind and hope it's enough. That fixed count
   has to be chosen conservatively up front, wasting depth in the common case
   where 2-3 iterations would have sufficed in plaintext (see stage 2 output).

This script runs a *fixed 3-iteration* Newton solve homomorphically, using a
degree-5 Taylor approximation for sin/cos, and compares against the plaintext
result.
"""
import math
import time
import tenseal as ts

def taylor_coeffs(kind, terms):
    # coefficients for polyval, index i = coefficient of x^i
    coeffs = [0.0] * (2 * terms)
    sign = 1
    for k in range(terms):
        power = 2 * k + (1 if kind == "sin" else 0)
        coeffs[power] = sign / math.factorial(power)
        sign *= -1
    return coeffs

def sin_taylor(x, terms=3):
    # polyval handles CKKS rescale/level bookkeeping internally, unlike a
    # hand-rolled Horner loop, which is exactly what tripped up the first
    # version of this script with a raw "scale out of bounds" error.
    return x.polyval(taylor_coeffs("sin", terms))

def cos_taylor(x, terms=3):
    return x.polyval(taylor_coeffs("cos", terms))

M_plain = 1.837924
e = 0.0007
FIXED_ITERS = 3
TAYLOR_TERMS = 4  # bump this up if precision is bad; costs more depth

# --- plaintext reference, same fixed-iteration / Taylor-approx logic ---
def kepler_plaintext_fixed(M, e, iters, terms):
    E = M
    for _ in range(iters):
        s = sum(((-1) ** k) * E ** (2 * k + 1) / math.factorial(2 * k + 1) for k in range(terms))
        c = sum(((-1) ** k) * E ** (2 * k) / math.factorial(2 * k) for k in range(terms))
        f = E - e * s - M
        fp = 1 - e * c
        E = E - f / fp
    return E

E_plain_exact = None
E_ref = M_plain
for _ in range(50):
    f = E_ref - e * math.sin(E_ref) - M_plain
    fp = 1 - e * math.cos(E_ref)
    E_ref = E_ref - f / fp
E_plain_exact = E_ref

E_plain_fixed = kepler_plaintext_fixed(M_plain, e, FIXED_ITERS, TAYLOR_TERMS)

print(f"true E (many iterations, real sin/cos):      {E_plain_exact:.8f}")
print(f"E with {FIXED_ITERS} fixed iters + Taylor sin/cos:   {E_plain_fixed:.8f}")
print(f"plaintext approximation error:                 {abs(E_plain_exact - E_plain_fixed):.2e}")
print()

# --- now the encrypted version ---
context = ts.context(ts.SCHEME_TYPE.CKKS, poly_modulus_degree=32768,
                      coeff_mod_bit_sizes=[60] + [40] * 18 + [60])
context.global_scale = 2**40

M_enc = ts.ckks_vector(context, [M_plain])

t0 = time.time()
E_enc = M_enc  # initial guess = M
depth_note = []
try:
    for i in range(FIXED_ITERS):
        s_enc = sin_taylor(E_enc, TAYLOR_TERMS)
        c_enc = cos_taylor(E_enc, TAYLOR_TERMS)
        f_enc = E_enc - e * s_enc - M_plain
        fp_enc = c_enc * (-e) + 1.0
        # CKKS has no native division by a ciphertext — invert fp in plaintext
        # is not possible either (fp depends on encrypted E). We cheat here by
        # using a plaintext reciprocal approximation, which is itself a real
        # limitation: division ciphertext-by-ciphertext isn't a thing in CKKS.
        fp_dec = fp_enc.decrypt()[0]  # <-- breaks the privacy property, flagged below
        E_enc = E_enc - f_enc * (1.0 / fp_dec)
    elapsed = time.time() - t0
    E_dec = E_enc.decrypt()[0]
    print(f"encrypted result:                              {E_dec:.8f}")
    print(f"error vs true E:                                {abs(E_plain_exact - E_dec):.2e}")
    print(f"error vs plaintext-fixed-iters version:         {abs(E_plain_fixed - E_dec):.2e}")
    print(f"wall time for {FIXED_ITERS} encrypted iterations:          {elapsed:.2f}s")
except Exception as ex:
    import traceback
    print(f"FAILED: {ex}")
    traceback.print_exc()

print()
print("The line marked '<-- breaks the privacy property' is the real finding:")
print("Newton's method needs f(E)/f'(E), i.e. ciphertext-by-ciphertext division,")
print("which CKKS does not support at all. Every real FHE Kepler-solver either")
print("(a) decrypts the denominator each round like this script does, which defeats")
print("the whole point, (b) uses a fixed-point iteration that avoids division", )
print("entirely (a real research problem), or (c) skips iteration and uses a")
print("closed-form / low-order polynomial approximation of E(M, e) instead of")
print("solving Kepler's equation exactly.")
