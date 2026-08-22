---
title: What is Homomorphic Encryption
tags: [fhe/concept, status/todo]
created: 2026-08-21
---

# What is Homomorphic Encryption

Encryption scheme where you can perform computation directly on ciphertexts, and decrypting the result gives the same answer as if you'd computed on the plaintexts.

E(a) op E(b) = E(a op b), without ever decrypting a or b.

## Why it matters
- Lets an untrusted party (cloud, third-party compute) process your data without seeing it.
- Core building block for privacy-preserving ML, encrypted search, secure aggregation.

## Open questions to fill in
- What's the actual threat model? Who is untrusted here — the compute provider, other parties, both?
- What's the performance cost relative to plaintext computation, roughly?
- How does this differ from secure multi-party computation (MPC) or trusted execution environments (TEE)? When would you pick one over the others?

## Links
- Next: [[PHE vs SHE vs FHE]]

#fhe/concept
