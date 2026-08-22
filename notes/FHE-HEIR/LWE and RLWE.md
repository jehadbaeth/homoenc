---
title: LWE and RLWE
tags: [fhe/math, status/todo]
created: 2026-08-21
---

# LWE and RLWE

**LWE (Learning With Errors)** — hardness assumption: given many noisy linear equations over a finite field, it's computationally hard to recover the secret vector. Underlies most modern lattice cryptography, including post-quantum schemes.

**RLWE (Ring-LWE)** — same idea, but structured over a polynomial ring instead of plain vectors. Makes keys and ciphertexts much smaller and operations faster, at the cost of extra structure (which is still believed hard to exploit, but is a stronger assumption than plain LWE).

## Why it matters for FHE
Almost every practical FHE scheme (BGV, BFV, CKKS, TFHE) is built on LWE or RLWE. The "noise" that limits SHE depth is literally the LWE error term growing with each operation.

## Open questions to fill in
- Don't need to reprove hardness reductions, but should understand: what does a ciphertext look like concretely (as a vector/polynomial), and where does "noise" physically live in it?
- Why is this believed post-quantum secure (no known efficient quantum attack), unlike RSA/ECC?

## Links
- Previous: [[PHE vs SHE vs FHE]]
- Next: [[Noise and Bootstrapping]]

#fhe/math
