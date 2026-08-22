---
title: PHE vs SHE vs FHE
tags: [fhe/concept, status/todo]
created: 2026-08-21
---

# PHE vs SHE vs FHE

Three tiers of homomorphic encryption, differing in which operations and how many of them are supported.

- **PHE (Partial)** — supports only one operation type unlimited times (either addition or multiplication, not both). Example: RSA (multiplicative), Paillier (additive).
- **SHE (Somewhat)** — supports both addition and multiplication, but only a limited number of times before noise makes decryption fail.
- **FHE (Fully)** — supports arbitrary depth circuits of both operations, indefinitely. Requires bootstrapping (see [[Noise and Bootstrapping]]) to reset noise growth.

## Why this matters
Gentry's 2009 thesis solved the "how do we go from SHE to FHE" problem via bootstrapping. Before that, arbitrary-depth computation on ciphertexts was an open problem for ~30 years.

## Open questions to fill in
- Where's the line between SHE and FHE in practice — do real systems just use SHE with an app-specific circuit depth, and skip bootstrapping because it's slow?
- Relation to [[LWE and RLWE]] — why lattice problems specifically became the basis for these schemes.

## Links
- Previous: [[What is Homomorphic Encryption]]
- Next: [[LWE and RLWE]]

#fhe/concept
