---
title: SGP4 FHE Prototype — Findings
tags: [fhe/project, fhe/experiment, status/done]
created: 2026-08-21
---

# SGP4 FHE Prototype — Findings

Hands-on prototype in `scripts/` (project repo), CKKS via TenSEAL, built in five stages to find exactly where FHE breaks on an orbit-propagation-shaped workload, motivated by [[FHE Project Ideas]].

## Setup
- Stage 1: real `sgp4` library, plaintext, ground truth.
- Stage 2: simplified two-body Keplerian propagator (SGP4's math skeleton minus perturbation terms), plaintext.
- Stage 3: encrypt the linear part (`M = M0 + n*dt`) — trivial, CKKS is built for exactly this.
- Stage 4: attempt to encrypt the iterative Kepler solve (Newton-Raphson).
- Stage 5: restructure the problem to avoid iteration/division entirely.
- Stage 6: stage 5 assumed orbit shape `(a, e)` is public and only phase `M` is private — what if `e` needs to stay private too?

## Key finding 1 — ciphertext/ciphertext division does not exist in CKKS
Newton's method needs `f(E)/f'(E)`. CKKS supports add, subtract, multiply, and division by a *known plaintext* scalar — not ciphertext-by-ciphertext division, at all. The only way to make stage 4 run was to decrypt the denominator every iteration, which hands the server the intermediate eccentric anomaly in plaintext and defeats the entire privacy goal. This is not a performance problem, it's a missing operation. See [[Noise and Bootstrapping]] and [[CKKS]].

## Key finding 2 — hand-rolled polynomial evaluation under CKKS is a minefield, but for two very different reasons
- A hand-rolled Taylor-series sin/cos using raw `+`/`*` crashed with "scale out of bounds." Fixed by using TenSEAL's built-in `polyval`, which manages CKKS rescale/level bookkeeping correctly. Lesson: don't hand-roll polynomial evaluation under CKKS, use the library's evaluator.
- Separately, in stage 5, fitting a Chebyshev polynomial (for plaintext numerical stability) and then converting to monomial coefficients for `polyval` introduced ~77 km of error — confirmed in plain double-precision numpy, zero encryption involved. Basis conversion after a Chebyshev fit is numerically unstable on its own; fitting the monomial polynomial directly, in a rescaled domain `t = (M - pi)/pi in [-1, 1]`, was stable to degree 14. Lesson: CKKS failures and plain numerical-conditioning failures can look identical from the outside ("wildly wrong output") — isolate which one you're looking at before assuming it's an encryption problem.

## Key finding 3 — the actual fix is architectural, not a better algorithm
The way to make this privacy-preserving end to end wasn't a smarter encrypted Newton's method, it was restructuring the problem so no iteration is needed at all: since orbit shape `(a, e)` is public and only orbital phase `M` is the customer's private state, fit `x(M)`, `y(M)` once offline in plaintext, then evaluate that polynomial homomorphically. Fixed, known-in-advance multiplicative depth (proportional to polynomial degree), no division, no server-side decryption.

## Key finding 4 — encrypting a second variable is nearly free until it isn't, and multiplicative depth doesn't scale evenly across variables
Stage 6 encrypted eccentricity `e` alongside `M`, turning the curve fit `x(M)` into a surface fit `x(M, e)`. Three distinct results, each surprising in a different way:
- Over a narrow, near-circular LEO eccentricity range (`e` in [0, 0.02]), encrypting `e` was basically free: `DE=2` (degree 2 in `e`) was enough, barely growing multiplicative depth beyond stage 5's single-variable case, and encrypted accuracy stayed at the same 44–70 m level. Eccentricity's effect on position is nearly linear that close to circular.
- A first attempt at the bivariate plaintext fit (`DM=6, DE=4`) gave a shockingly bad 10–40 km error — before encryption even entered the picture. A degree/grid-density sweep isolated the cause as insufficient `DM` (the M-degree), not `DE`: retuning to `DM=14, DE=2` with a denser sampling grid brought the plaintext fit back in line with stage 5's single-variable accuracy (~0.001 km). The lesson isn't about FHE at all — adding a second input variable to a regression problem can silently starve the *other* variable of fitting capacity if degree isn't rebalanced.
- Pushing eccentricity to a wider, more elliptical range (up to `e ≈ 0.7`) needs a much higher polynomial degree in both variables (`DM=20, DE=16` just to hold ~100–400 m accuracy — worse than the narrow-range case despite 8x more terms) and building that power ladder hits a genuine hard wall: the same 16×40-bit-prime CKKS context that comfortably handled stage 5 fails on the ladder's 17th ciphertext multiplication. This isn't a tuning problem, it's a quantified, budgeted resource running out — one sequential multiplication per 40-bit prime in the modulus chain, no more. Supporting wider eccentricity coverage means a larger modulus chain: bigger `poly_modulus_degree`, more primes, directly slower and more memory/bandwidth-hungry per operation.
- New failure mode this stage introduced (and stage 5 never could, since it only ever multiplied a single power ladder against itself in a strictly increasing chain): cross terms need `t_M^i * t_e^j`, where the two power ladders sit at *different* levels (`i` vs `j`) in the modulus chain. Multiplying ciphertexts at mismatched levels is exactly the class of bug that broke the hand-rolled Chebyshev recurrence in stage 5's first attempt — TenSEAL's `auto_mod_switch` absorbed this silently in the narrow-range case tested here, but it's a sharp edge worth knowing about explicitly (the [[SGP4 FHE Java Prototype Findings|Java port]] hit this exact issue head-on, without a library auto-mod-switch to paper over it, and needed hand-written level *and* scale alignment to fix it).

## Numbers, for reference
- Plaintext fit error (degree 14 monomial, rescaled domain): 2e-5 to 1e-4 km.
- Encrypted evaluation error on top of that: roughly 3-90 m across six test points spanning a full orbit (CKKS's own fixed-point precision cost at `global_scale = 2^40`).
- Wall time: ~2.5s per point evaluation (single-threaded prototype, unoptimized parameters).

## The tradeoff this leaves open
This design protects orbital *phase* (`M`), not orbital *shape* (`a`, `e`) — those must be public to fit the polynomial. If a customer's actual privacy requirement includes hiding orbit shape from OKAPI:Orbits, this specific approach doesn't cover it, and you're back at the stage 4 wall (iterative solving, division). Worth pinning down which quantities actually need to stay private before picking a design, this is the central open question for applying any of this to real SSA/collision-avoidance work.

## Links
- Java port (same findings, JNA/SEAL instead of TenSEAL): [[SGP4 FHE Java Prototype Findings]]
- Motivated by: [[FHE Project Ideas]]
- Concepts used: [[CKKS]], [[Noise and Bootstrapping]]
- Back to: [[FHE MOC]]

#fhe/project #fhe/experiment
