"""Shared pieces used by every stage: OEM loading and local Lagrange
interpolation weights. The weights depend only on the (public) sample
times, never on the (potentially encrypted) sample values -- that's what
lets interpolation be done homomorphically as a plaintext-weighted sum.
"""
import csv

LAGRANGE_ORDER = 7  # 8-point local window, standard order for OEM/ephemeris interpolation


def load_oem(path):
    t, x, y, z, vx, vy, vz = [], [], [], [], [], [], []
    with open(path) as f:
        r = csv.DictReader(f)
        for row in r:
            t.append(float(row["t_offset_s"]))
            x.append(float(row["x_km"]))
            y.append(float(row["y_km"]))
            z.append(float(row["z_km"]))
    return {"t": t, "x": x, "y": y, "z": z}


def local_window(sample_times, query_t, order=LAGRANGE_ORDER):
    """Index of the (order+1) sample times closest to query_t, sorted."""
    n = len(sample_times)
    idxs = sorted(range(n), key=lambda i: abs(sample_times[i] - query_t))[: order + 1]
    return sorted(idxs)


def lagrange_weights(sample_times, query_t, order=LAGRANGE_ORDER):
    """Full-length weight vector (zero outside the local window) such that
    interpolated_value = sum(weights[i] * sample_values[i]).
    Depends only on sample_times (public) and query_t (public), never on values.
    """
    n = len(sample_times)
    window = local_window(sample_times, query_t, order)
    weights = [0.0] * n
    for i in window:
        ti = sample_times[i]
        w = 1.0
        for j in window:
            if j == i:
                continue
            tj = sample_times[j]
            w *= (query_t - tj) / (ti - tj)
        weights[i] = w
    return weights


def interpolate_plain(sample_times, sample_values, query_t, order=LAGRANGE_ORDER):
    w = lagrange_weights(sample_times, query_t, order)
    return sum(wi * vi for wi, vi in zip(w, sample_values))
