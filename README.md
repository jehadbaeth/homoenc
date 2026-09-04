# homoenc

Published write-ups, in the order they were done:

1. **[FHE Feasibility Study — CKKS for orbit propagation](https://jehadbaeth.github.io/homoenc/)** — can CKKS carry an SGP4-shaped workload at all?
2. **[Encrypted conjunction assessment](https://jehadbaeth.github.io/homoenc/conjunction.html)** — two real OEM ephemerides, several disclosure designs (A–E) on the same Starlink pair.
3. **[Approach E](https://jehadbaeth.github.io/homoenc/conjunction-e.html)** — the follow-on that keeps only the protocol which finishes under encryption and decrypts a count.

Hands-on exploration of fully homomorphic encryption (FHE), prompted by Google's
HEIR announcement, aimed at a concrete question: could OKAPI:Orbits host its
space situational awareness (SSA) / collision-avoidance software while letting
satellite operator customers keep their orbital data encrypted end to end?

## Layout

- `notes/FHE-HEIR/` — Obsidian-importable learning notes (backlinked, tagged),
  covering FHE fundamentals through to the prototype findings.
- `scripts/` — Python/TenSEAL staged prototype (stages 1–6).
- `java-stack/` — Java port of the same staged prototype, bridging to Microsoft
  SEAL directly via a hand-written JNA binding to SEAL's `sealc` C ABI (no
  viable native Java FHE library exists).
- `benchmarks/` — performance benchmarks for both stacks (latency, memory,
  ciphertext size) and the source of report (1).
- `oem-conjunction/` — two-OEM conjunction study. `report.html` is report (2);
  `report-approach-e.html` is report (3).
- `docs/` — GitHub Pages copies of the three reports.

## Key findings, short version

Propagation study (report 1):

- CKKS has no ciphertext/ciphertext division. Iterative solvers (e.g.
  Newton-Raphson for Kepler's equation) can't run under encryption without
  decrypting an intermediate value — which defeats the point.
- The fix that works: fit the pipeline's output as a closed-form polynomial
  offline (in plaintext, for public orbit-shape parameters), then evaluate
  that polynomial homomorphically at runtime with only add/subtract/multiply.
- Multiplicative depth is a hard, budgeted resource — a fixed CKKS context
  supports a fixed number of sequential ciphertext multiplications and fails
  beyond that, in both Python and Java, identically.

Conjunction / Approach E (reports 2–3):

- Lagrange interpolation weights depend only on public sample times, so two
  encrypted OEM position tables can be compared without disclosing orbit shape.
- The protocol that decrypts *only a count* needs CKKS bootstrapping (OpenFHE).
  On the real STARLINK-35712 × STARLINK-3845 pair that count is 1, matching
  the 5.432 km conjunction, with near-boundary safes at 11.7 km and 13.3 km
  left unflagged.

Full narrative write-ups: [`notes/FHE-HEIR/SGP4 FHE Prototype Findings.md`](notes/FHE-HEIR/SGP4%20FHE%20Prototype%20Findings.md)
(Python) and [`java-stack/notes/SGP4 FHE Java Prototype Findings.md`](java-stack/notes/SGP4%20FHE%20Java%20Prototype%20Findings.md) (Java).

## Setup

### SGP4 / TenSEAL stages (`scripts/`, Approaches A–D)

Needs a CPython that TenSEAL ships a wheel for (3.11–3.14 on Linux x86_64).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r oem-conjunction/requirements.txt   # tenseal, numpy
# or: pip install tenseal sgp4 numpy
```

From the repo root, with `PYTHONPATH=oem-conjunction`:

```bash
python oem-conjunction/01_plaintext_reference.py
python oem-conjunction/02_approach_b_encrypted_distance_curve.py
python oem-conjunction/04_approach_c_thresholded_flags.py
```

Each encrypted TenSEAL stage holds a ~1.3–1.5 GB CKKS context. Run them one
at a time.

### Approach E (OpenFHE)

The published `openfhe` wheel is tagged `py3-none-any` but is actually
`cpython-312-x86_64-linux-gnu`. It will not import on Python 3.13/3.14 or on
macOS/arm64 (that host needs a from-source OpenFHE build).

```bash
# 3.12 interpreter, e.g. via uv:
uv python install 3.12
$(uv python find 3.12) -m venv .venv-openfhe
source .venv-openfhe/bin/activate
pip install -r oem-conjunction/requirements-openfhe.txt   # openfhe, matplotlib, numpy
```

Use physical cores, not hyperthreads. On a 16-core machine, 8 is the sweet spot:

```bash
export OMP_NUM_THREADS=8
export PYTHONPATH=oem-conjunction

python oem-conjunction/09_approach_e_openfhe_bootstrap.py      # single CPA, 61 times
python oem-conjunction/13_multi_approach_e_openfhe_bootstrap.py # 7 real events, 63 times
python oem-conjunction/benchmark_e.py                          # pressure + timing CSVs
python oem-conjunction/plot_e.py
python oem-conjunction/build_report_e.py                       # writes report-approach-e.html
                                                               # and docs/conjunction-e.html
```

Inputs are the committed OEM CSVs under `oem-conjunction/data/` (real CelesTrak
TLEs, not synthetic). The production decrypt is the masked flag-sum; per-point
flag CSVs are diagnostics.

Java: see [`java-stack/README.md`](java-stack/README.md) for building Microsoft SEAL's C shim and running via Gradle.
