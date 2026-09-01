"""Shared CKKS machinery for all three encrypted approaches: same context
parameters as the original SGP4 study, so results are comparable, plus the
encrypted interpolation / squared-distance building blocks every approach
is built from.
"""
import tenseal as ts

from common import lagrange_weights

CKKS_PARAMS = dict(
    poly_modulus_degree=32768,
    coeff_mod_bit_sizes=[60] + [40] * 16 + [60],
)
GLOBAL_SCALE = 2 ** 40


def make_context():
    context = ts.context(ts.SCHEME_TYPE.CKKS, **CKKS_PARAMS)
    context.global_scale = GLOBAL_SCALE
    context.generate_galois_keys()
    return context


def encrypt_oem(context, oem):
    return {
        "t": oem["t"],  # sample times are public
        "x": ts.ckks_vector(context, oem["x"]),
        "y": ts.ckks_vector(context, oem["y"]),
        "z": ts.ckks_vector(context, oem["z"]),
    }


def encrypted_interpolate(enc_oem, query_t):
    w = lagrange_weights(enc_oem["t"], query_t)
    return enc_oem["x"].dot(w), enc_oem["y"].dot(w), enc_oem["z"].dot(w)


def encrypted_distance_sq(enc_a, enc_b, query_t):
    xa, ya, za = encrypted_interpolate(enc_a, query_t)
    xb, yb, zb = encrypted_interpolate(enc_b, query_t)
    dx, dy, dz = xa - xb, ya - yb, za - zb
    return dx * dx + dy * dy + dz * dz
