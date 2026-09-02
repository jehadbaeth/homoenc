"""Stage 0 for the multi-event scenario: find ALL real close-approach events
(not just the single global minimum) between the same real, published
Starlink TLE pair used in the single-event scenario, over a wider window,
and build OEM tables wide enough to cover every event found.

This gives a genuinely nuanced test case from real orbital mechanics, not a
constructed one: within +/-2.5 hours of the original conjunction there are
six further local-minimum approaches between these same two objects, at
miss distances ranging from ~11.7 km to ~62 km -- including two that sit
just OUTSIDE the 10 km screening threshold (11.698 km and 13.276 km), which
is exactly the kind of near-boundary case a counting mechanism can get
wrong if it isn't precise. Only one of the seven events (the original,
5.432 km) is a genuine violation of the 10 km threshold.

Run: python3 oem-conjunction/data/find_multi_cpa_and_build_oems.py
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

EPOCH = (2026, 9, 1, 0, 0, 0)
SCAN_WINDOW_HOURS = 3  # +/- 3h around the epoch center used for the original scenario
CLUSTER_WINDOW_S = 40  # per-cluster fine monitoring window, +/- this many seconds
CLUSTER_STEP_S = 10  # per-cluster grid step -- matches the original single-event design


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


def find_all_local_minima(sat_a, sat_b, window_hours, coarse_step_s=30, fine_window_s=120, fine_step_s=0.5):
    window_days = window_hours * 3600 / 86400
    step_days = coarse_step_s / 86400
    n = int(2 * window_days / step_days)
    dists = []
    for i in range(n + 1):
        t = -window_days + i * step_days
        dists.append((t, dist_km(t, sat_a, sat_b)))

    coarse_minima = []
    for i in range(1, len(dists) - 1):
        t, d = dists[i]
        if d < dists[i - 1][1] and d < dists[i + 1][1]:
            coarse_minima.append(t)

    refined = []
    fine_window_days = fine_window_s / 86400
    fine_step_days = fine_step_s / 86400
    for t_coarse in coarse_minima:
        best_t, best_d = t_coarse, dist_km(t_coarse, sat_a, sat_b)
        t = t_coarse - fine_window_days
        while t <= t_coarse + fine_window_days:
            d = dist_km(t, sat_a, sat_b)
            if d < best_d:
                best_d, best_t = d, t
            t += fine_step_days
        refined.append((best_t * 86400, best_d))  # seconds, km
    refined.sort(key=lambda x: x[0])
    return refined


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

    events = find_all_local_minima(sat_a, sat_b, SCAN_WINDOW_HOURS)
    print(f"found {len(events)} real local-minimum approach events within +/-{SCAN_WINDOW_HOURS}h:")
    for t_s, d_km in events:
        print(f"  t={t_s:+9.1f}s   miss={d_km:8.3f} km")

    threshold_km = 10.0
    n_below = sum(1 for _, d in events if d < threshold_km)
    print(f"\n{n_below} of {len(events)} events genuinely below the {threshold_km} km threshold")

    # epoch center (t=0) is the original scenario's exact CPA time -- reuse it
    # as the reference so cluster offsets below line up with the single-event
    # scenario's own t=0.
    t_center_days = 0.0
    max_abs_s = max(abs(t_s) for t_s, _ in events)
    span_s = max_abs_s + CLUSTER_WINDOW_S + 300  # padding for Lagrange interpolation windows

    write_oem("oem-conjunction/data/oem_a_multi.csv", NAME_A, sat_a, t_center_days, span_s, sample_step_s=60)
    write_oem("oem-conjunction/data/oem_b_multi.csv", NAME_B, sat_b, t_center_days, span_s, sample_step_s=60)

    with open("oem-conjunction/data/multi_ground_truth.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cluster_index", "t_center_offset_s", "miss_distance_km", "below_threshold"])
        for i, (t_s, d_km) in enumerate(events):
            w.writerow([i, f"{t_s:.3f}", f"{d_km:.6f}", int(d_km < threshold_km)])
    print("wrote oem-conjunction/data/multi_ground_truth.csv")


if __name__ == "__main__":
    main()
