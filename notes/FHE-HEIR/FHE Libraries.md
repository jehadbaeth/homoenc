---
title: FHE Libraries
tags: [fhe/tooling, status/todo]
created: 2026-08-21
---

# FHE Libraries

Where the concepts turn into runnable code.

- **Microsoft SEAL** (C++) — BFV and CKKS. Well documented, no bootstrapping support (leveled only).
- **OpenFHE** (C++, successor to PALISADE) — BGV, BFV, CKKS, and TFHE-style schemes, actively maintained, closest to a "does everything" library.
- **Zama Concrete / TFHE-rs** (Rust, Python bindings) — TFHE-based, probably the easiest onboarding for a first hands-on program.
- **HElib** (IBM, C++) — BGV, one of the oldest libraries, less active now.
- **Lattigo** (Go) — BGV, BFV, CKKS, good if you'd rather work in Go than C++/Rust.

## Plan
- [ ] Pick one library based on language comfort (leaning: Concrete/TFHE-rs for the fastest first working program)
- [ ] Run a toy encrypted addition/multiplication example
- [ ] Note actual latency observed for a simple op, sanity check against what the docs claim

## Links
- Previous: [[BGV and BFV]], [[CKKS]], [[TFHE and FHEW]]
- Next: [[HEIR]]

#fhe/tooling
