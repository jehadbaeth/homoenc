"""Cross-match: diff each encrypted approach's output against the plaintext
reference algorithm (01_plaintext_reference.py), which runs the identical
Lagrange-interpolation + squared-distance computation with plain floats.

Run: python3 oem-conjunction/06_cross_validate.py
(after 01, 02, and 04 have all produced their results/*.csv files)
"""
import csv


def load_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def main():
    plain = load_csv("oem-conjunction/results/plaintext_distance_curve.csv")
    plain_by_t = {round(float(r["t_offset_s"]), 3): r for r in plain}

    print("=== Approach B vs plaintext reference (distance_sq curve) ===")
    try:
        b = load_csv("oem-conjunction/results/approach_b_distance_curve.csv")
        max_abs_err_km2, max_abs_err_km, worst_t = 0.0, 0.0, None
        for row in b:
            t = round(float(row["t_offset_s"]), 3)
            ref = plain_by_t[t]
            err_km2 = abs(float(row["distance_sq_km2"]) - float(ref["distance_sq_km2"]))
            err_km = abs(float(row["distance_km"]) - float(ref["distance_km"]))
            if err_km2 > max_abs_err_km2:
                max_abs_err_km2, max_abs_err_km, worst_t = err_km2, err_km, t
        print(f"  {len(b)} points compared")
        print(f"  max |distance_sq error|: {max_abs_err_km2:.3e} km^2 (at t={worst_t}s)")
        print(f"  max |distance error|:    {max_abs_err_km:.3e} km")
    except FileNotFoundError:
        print("  (results/approach_b_distance_curve.csv not found yet)")

    print("\n=== Approach C vs plaintext reference (threshold decision) ===")
    try:
        c = load_csv("oem-conjunction/results/approach_c_flags.csv")
        agree, disagree = 0, []
        for row in c:
            t = round(float(row["t_offset_s"]), 3)
            ref = plain_by_t[t]
            enc_flag = int(row["below_threshold_flagged"])
            plain_flag = int(ref["below_threshold"])
            if enc_flag == plain_flag:
                agree += 1
            else:
                disagree.append((t, enc_flag, plain_flag))
        print(f"  {len(c)} points compared, {agree} agree, {len(disagree)} disagree")
        for t, ef, pf in disagree:
            print(f"    DISAGREEMENT at t={t}s: encrypted_flag={ef} plaintext={pf}")
    except FileNotFoundError:
        print("  (results/approach_c_flags.csv not found yet)")


if __name__ == "__main__":
    main()
