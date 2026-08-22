---
title: CKKS
tags: [fhe/scheme, status/todo]
created: 2026-08-21
---

# CKKS

FHE scheme (Cheon-Kim-Kim-Song) for **approximate arithmetic over real/complex numbers**. Encodes floating-point-like values, computation introduces small approximation error similar to floating-point rounding, on top of the usual FHE noise.

## Why it matters
This is the scheme behind most encrypted ML/statistics work, since neural net inference and stats are inherently tolerant of small numerical error. If you're interested in privacy-preserving ML, this is likely your scheme.

## Open questions to fill in
- How does "rescaling" work here, and how does it interact with the noise budget from [[Noise and Bootstrapping]]?
- Real-world precision loss — how many bits of precision do you typically retain after a deep circuit?

## Links
- Previous: [[Noise and Bootstrapping]]
- Siblings: [[BGV and BFV]], [[TFHE and FHEW]]
- Try in: [[FHE Libraries]]
- Relevant for: [[FHE Project Ideas]]

#fhe/scheme
