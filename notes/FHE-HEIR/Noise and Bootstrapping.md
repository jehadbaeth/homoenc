---
title: Noise and Bootstrapping
tags: [fhe/concept, status/todo]
created: 2026-08-21
---

# Noise and Bootstrapping

Every ciphertext in an LWE/RLWE-based scheme carries a small error term ("noise") for security. Each homomorphic operation increases that noise — multiplication grows it much faster than addition. Once noise exceeds a threshold, decryption returns garbage.

**Bootstrapping** is the technique (from Gentry 2009) that homomorphically evaluates the decryption circuit itself, producing a fresh low-noise ciphertext that decrypts to the same value. This is what turns SHE into FHE, but it's the single most expensive operation in the whole system.

## Why it matters
This is the actual engineering bottleneck of FHE. Almost every scheme/library design decision (which scheme to pick, how deep a circuit you can afford, whether to bootstrap at all) traces back to noise management.

## Open questions to fill in
- Rough order-of-magnitude cost of bootstrapping in TFHE vs CKKS — is it milliseconds or seconds?
- "Leveled" FHE — using SHE with a noise budget sized to your exact circuit depth, avoiding bootstrapping altogether. When do real deployments choose this over full bootstrapping?

## Links
- Previous: [[LWE and RLWE]]
- Next: [[BGV and BFV]], [[CKKS]], [[TFHE and FHEW]]

#fhe/concept
