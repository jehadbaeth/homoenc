"""Ground truth: propagate a real TLE with the actual SGP4 algorithm, in plaintext.
Just to see what the real thing computes, before we try to encrypt anything.
"""
from sgp4.api import Satrec, jday

# ISS TLE (arbitrary real example, epoch is whatever it is, doesn't matter for the prototype)
line1 = "1 25544U 98067A   24001.00000000  .00016717  00000-0  10270-3 0  9007"
line2 = "2 25544  51.6416 247.4627 0006703 130.5360 325.0288 15.49560770 12345"

sat = Satrec.twoline2rv(line1, line2)

jd, fr = jday(2024, 1, 1, 12, 0, 0)
e, r, v = sat.sgp4(jd, fr)

print("error code:", e)
print("position (km, TEME):", r)
print("velocity (km/s, TEME):", v)
print()
print("This single call involves: WGS72 gravity constants, secular perturbations from J2/J4,")
print("periodic perturbations, atmospheric drag terms, and an internal Newton-Raphson solve")
print("of Kepler's equation with trig functions at every step. None of that is a good target")
print("for a first FHE attempt.")
