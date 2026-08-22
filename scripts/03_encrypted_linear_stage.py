"""Stage 3: encrypt the easy part — mean anomaly propagation is just
M = M0 + n*dt, pure addition and scalar multiplication. CKKS should handle
this without any drama. This also doubles as "does my TenSEAL setup work."

Threat model mirrored here: the *client* holds the secret key and M0 (their
private orbital state). The *server* (us) only ever sees ciphertexts and n, dt
(non-secret orbit parameters in this toy example), performs the propagation
homomorphically, and returns an encrypted result the client decrypts locally.
"""
import math
import tenseal as ts

MU_EARTH = 398600.4418

def mean_motion(a):
    return math.sqrt(MU_EARTH / a**3)

# --- client side: generate context + keys, encrypt private state ---
context = ts.context(ts.SCHEME_TYPE.CKKS, poly_modulus_degree=8192,
                      coeff_mod_bit_sizes=[60, 40, 40, 60])
context.generate_galois_keys()
context.global_scale = 2**40

a = 6798.0
e = 0.0007
M0 = 1.5
dt = 300
n = mean_motion(a)

M0_enc = ts.ckks_vector(context, [M0])

# --- server side: only ever touches M0_enc, n, dt. never sees M0 in plaintext ---
M_enc = M0_enc + n * dt

# --- client side: decrypt ---
M_dec = M_enc.decrypt()[0]

M_plain = (M0 + n * dt) % (2 * math.pi)

print(f"encrypted-path result (before mod 2pi): {M_dec:.6f}")
print(f"plaintext result       (before mod 2pi): {M0 + n * dt:.6f}")
print(f"difference: {abs(M_dec - (M0 + n * dt)):.2e}")
print()
print("Note: the mod 2*pi wrap isn't done here — that's a comparison/branch,")
print("which is exactly the kind of operation CKKS can't do natively. More on")
print("that in stage 4.")
