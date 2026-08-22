---
title: BGV and BFV
tags: [fhe/scheme, status/todo]
created: 2026-08-21
---

# BGV and BFV

Two closely related FHE schemes for **exact integer arithmetic** over RLWE. Named after their authors (Brakerski-Gentry-Vaikuntanathan; Brakerski/Fan-Vercauteren). Differ mainly in how they scale/encode plaintexts internally — in practice, similar performance, and most libraries offer both.

## Why it matters
Good fit when you need exact results — counters, integer aggregation, exact comparisons — not approximate math.

## Open questions to fill in
- Concretely: what's a plaintext modulus, and how does it bound the integer range you can compute over?
- Where do BGV/BFV lose to [[CKKS]] (accuracy) or to [[TFHE and FHEW]] (bootstrapping speed) for a given use case?

## Links
- Previous: [[Noise and Bootstrapping]]
- Siblings: [[CKKS]], [[TFHE and FHEW]]
- Try in: [[FHE Libraries]]

#fhe/scheme
