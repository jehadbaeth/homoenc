---
title: TFHE and FHEW
tags: [fhe/scheme, status/todo]
created: 2026-08-21
---

# TFHE and FHEW

FHE schemes optimized for **boolean/binary circuits** (gate-by-gate evaluation: AND, OR, XOR, etc.), with fast bootstrapping after every gate rather than avoiding it. FHEW came first, TFHE (Zama's line of work) made bootstrapping fast enough to be practical (sub-second, later sub-millisecond for simple gates).

## Why it matters
Best fit for arbitrary logic/control flow (comparisons, branching, lookup tables) rather than bulk arithmetic. Zama's Concrete/TFHE-rs libraries are built on this and are the most approachable on-ramp for hands-on experimentation.

## Open questions to fill in
- "Programmable bootstrapping" — Zama's term for evaluating an arbitrary function during the bootstrap step itself. Worth understanding, it's a genuinely clever trick.
- How this compares practically to [[BGV and BFV]] / [[CKKS]] for a workload that's mixed arithmetic + comparisons (e.g. an encrypted decision tree).

## Links
- Previous: [[Noise and Bootstrapping]]
- Siblings: [[BGV and BFV]], [[CKKS]]
- Try in: [[FHE Libraries]]

#fhe/scheme
