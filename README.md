# homoenc

**Full study: [FHE Feasibility Study — CKKS Performance for Orbit Propagation](https://jehadbaeth.github.io/homoenc/)**

Hands-on exploration of fully homomorphic encryption (FHE), prompted by Google's
HEIR announcement, aimed at a concrete question: could OKAPI:Orbits host its
space situational awareness (SSA) / collision-avoidance software while letting
satellite operator customers keep their orbital data encrypted end to end?

Rather than reasoning about this abstractly, this repo builds a small staged
SGP4-shaped orbit-propagation prototype under CKKS (the FHE scheme for
approximate real-number arithmetic), first in Python, then again in Java, to
find out concretely where FHE helps and where it breaks.

## Layout

- `notes/FHE-HEIR/` — Obsidian-importable learning notes (backlinked, tagged),
  covering FHE fundamentals through to the prototype findings.
- `scripts/` — Python/TenSEAL staged prototype (stages 1–6).
- `java-stack/` — Java port of the same staged prototype, bridging to Microsoft
  SEAL directly via a hand-written JNA binding to SEAL's `sealc` C ABI (no
  viable native Java FHE library exists).
- `benchmarks/` — performance benchmarks for both stacks (latency, memory,
  ciphertext size) and the source of the report below.
- `docs/` — the published study (served via GitHub Pages at the link above).

## Key findings, short version

- CKKS has no ciphertext/ciphertext division. Iterative solvers (e.g.
  Newton-Raphson for Kepler's equation) can't run under encryption without
  decrypting an intermediate value — which defeats the point.
- The fix that works: fit the pipeline's output as a closed-form polynomial
  offline (in plaintext, for public orbit-shape parameters), then evaluate
  that polynomial homomorphically at runtime with only add/subtract/multiply.
- Multiplicative depth is a hard, budgeted resource — a fixed CKKS context
  supports a fixed number of sequential ciphertext multiplications and fails
  beyond that, in both Python and Java, identically.
- What this protects: orbital *phase*. What it doesn't: orbit *shape*
  parameters, which must stay public to build the offline fit.

Full narrative write-ups: [`notes/FHE-HEIR/SGP4 FHE Prototype Findings.md`](notes/FHE-HEIR/SGP4%20FHE%20Prototype%20Findings.md)
(Python) and [`java-stack/notes/SGP4 FHE Java Prototype Findings.md`](java-stack/notes/SGP4%20FHE%20Java%20Prototype%20Findings.md) (Java).

## Setup

Python: see `scripts/` — `python3.13 -m venv .venv && source .venv/bin/activate && pip install tenseal sgp4 numpy`.

Java: see [`java-stack/README.md`](java-stack/README.md) for building Microsoft SEAL's C shim and running via Gradle.
