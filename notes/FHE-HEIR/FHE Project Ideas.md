---
title: FHE Project Ideas
tags: [fhe/project, status/todo]
created: 2026-08-21
---

# FHE Project Ideas

Candidates once the fundamentals stick, ranked by how well they'd fit alongside [[FHE Libraries]] and [[HEIR]] experimentation rather than any confirmed direction yet.

- **Encrypted aggregation/statistics** — sum/average/count over encrypted values from multiple contributors, nobody but the requester sees raw data. Good fit for [[BGV and BFV]], simplest to reason about end to end.
- **Private inference on a small ML model** — logistic regression or a tiny neural net evaluated on encrypted input. Good fit for [[CKKS]], closest to what most current FHE+ML work looks like.
- **Encrypted decision logic / lookup** — comparisons and branching over encrypted data. Good fit for [[TFHE and FHEW]].
- **Toy encrypted calculator** — smallest possible thing, mostly useful as the first "I made a ciphertext do arithmetic" milestone before picking a real direction.

## Notes to fill in as you learn more
- Any actual problem from day-to-day work that has an encrypted-computation shape worth exploring?
- Decide direction only after Stage 4 hands-on and a first HEIR read, not before, premature project selection here would be guessing.

## Links
- Previous: [[HEIR]]
- Back to: [[FHE MOC]]

#fhe/project
