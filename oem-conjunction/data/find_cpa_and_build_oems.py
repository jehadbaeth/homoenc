"""Stage 0: pick a real close-approach event between two real Starlink objects
and build the two OEM-style ephemeris tables (real SGP4 propagation of real,
currently-published TLEs) that every later stage treats as its input data.

This is the "real life data" the encrypted stages get benchmarked against:
the ground-truth CPA is found by dense plaintext SGP4 sampling, and the two
tables written to data/oem_a.csv / oem_b.csv are what a real OEM (CCSDS Orbit
Ephemeris Message) looks like -- a table of (time, x, y, z, vx, vy, vz).

Run: python3 oem-conjunction/data/find_cpa_and_build_oems.py
"""
import csv
import math

from sgp4.api import Satrec, jday

NAME_A = "STARLINK-35712"
NAME_B = "STARLINK-3845"

TLE_A = (
    "1 66215U 25244K   26243.98825758  .00019643  00000+0  59091-3 0  9995",
    "2 66215  53.1570 133.1789 0001093 119.5489 240.5623 15.34403268 48533",
)
TLE_B = (
    "1 52541U 22051J   26244.17451993  .00000181  00000+0  16093-4 0  9996",
    "2 52541  53.1606  56.5326 0001116  89.4581 270.6550 15.35405161237997",
)

EPOCH = (2026, 9, 1, 0, 0, 0)  # jday() base; offsets below are in fractional days


def propagate(sat, days_offset):
    jd, fr = jday(*EPOCH)
    fr += days_offset
    e, r, v = sat.sgp4(jd, fr)
    if e != 0:
        raise RuntimeError(f"SGP4 error code {e}")
    return r, v


def dist_km(days_offset, sat_a, sat_b):
    ra, _ = propagate(sat_a, days_offset)
    rb, _ = propagate(sat_b, days_offset)
    return math.dist(ra, rb)


def coarse_to_fine_cpa(sat_a, sat_b, window_hours=12, coarse_step_s=30, fine_window_s=120, fine_step_s=0.5):
    window_days = window_hours * 3600 / 86400
    step_days = coarse_step_s / 86400
    n = int(2 * window_days / step_days)
    best_t, best_d = None, None
    for i in range(n + 1):
        t = -window_days + i * step_days
        d = dist_km(t, sat_a, sat_b)
        if best_d is None or d < best_d:
            best_d, best_t = d, t
    # refine around the coarse minimum
    fine_window_days = fine_window_s / 86400
    fine_step_days = fine_step_s / 86400
    t = best_t - fine_window_days
    while t <= best_t + fine_window_days:
        d = dist_km(t, sat_a, sat_b)
        if d < best_d:
            best_d, best_t = d, t
        t += fine_step_days
    return best_t, best_d


def write_oem(path, name, sat, t_center_days, span_s, sample_step_s):
    span_days = span_s / 86400
    step_days = sample_step_s / 86400
    n = int(span_days / step_days)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_offset_s", "x_km", "y_km", "z_km", "vx_kms", "vy_kms", "vz_kms"])
        for i in range(-n, n + 1):
            t = t_center_days + i * step_days
            r, v = propagate(sat, t)
            t_offset_s = round((t - t_center_days) * 86400, 6)
            w.writerow([t_offset_s, *r, *v])
    print(f"wrote {path}  ({2*n+1} samples, {name})")


def main():
    sat_a = Satrec.twoline2rv(*TLE_A)
    sat_b = Satrec.twoline2rv(*TLE_B)

    t_cpa_days, d_cpa_km = coarse_to_fine_cpa(sat_a, sat_b)
    t_cpa_s = t_cpa_days * 86400
    print(f"Ground-truth CPA (dense plaintext SGP4 search):")
    print(f"  t = epoch {t_cpa_s:+.3f} s   miss distance = {d_cpa_km:.4f} km")

    # OEM samples: coarse, like a real published ephemeris (60 s cadence),
    # spanning well past the CPA on both sides.
    write_oem("oem-conjunction/data/oem_a.csv", NAME_A, sat_a, t_cpa_days, span_s=1800, sample_step_s=60)
    write_oem("oem-conjunction/data/oem_b.csv", NAME_B, sat_b, t_cpa_days, span_s=1800, sample_step_s=60)

    with open("oem-conjunction/data/ground_truth.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["quantity", "value", "unit"])
        w.writerow(["object_a", NAME_A, ""])
        w.writerow(["object_b", NAME_B, ""])
        w.writerow(["t_cpa_offset_s", f"{t_cpa_s:.6f}", "s from OEM window center"])
        w.writerow(["miss_distance_km", f"{d_cpa_km:.6f}", "km"])
    print("wrote oem-conjunction/data/ground_truth.csv")


if __name__ == "__main__":
    main()
