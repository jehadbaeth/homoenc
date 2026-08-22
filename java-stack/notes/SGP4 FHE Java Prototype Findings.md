---
title: SGP4 FHE Java Prototype — Findings
tags: [fhe/project, fhe/experiment, fhe/java, status/done]
created: 2026-08-22
---

# SGP4 FHE Java Prototype — Findings

Java port of the [[SGP4 FHE Prototype Findings|Python/TenSEAL prototype]], built to see whether the same conclusions hold in OKAPI:Orbits' actual production language. Code in `java-stack/` (project repo). No native Java FHE library exists that implements a real modern scheme — `kryptnostic/krypto` is abandoned since 2016 and was never a CKKS/BFV/BGV implementation — so this bridges Java to Microsoft SEAL directly via JNA, calling into `sealc`, the C-ABI shim SEAL itself ships to support its .NET wrapper.

## Setup
- Built `libsealc.dylib` from SEAL's source with `-DSEAL_BUILD_SEAL_C=ON`.
- Hand-wrote JNA bindings (`SealC.java`) for every native function used, with each signature copied from SEAL's own `dotnet/src/NativeMethods.cs` P/Invoke declarations rather than guessed from the C++ headers — a wrong argument order/type here is silent memory corruption, not a compile error.
- Stage 0: bare encrypt → homomorphic add → homomorphic multiply-by-plaintext → decrypt, to validate the bindings before building anything SGP4-shaped.
- Stage 1: linear mean-anomaly propagation, the trivial case.
- Stage 2: the Kepler-solve division wall, confirmed by reading SEAL's C++ API surface rather than by triggering a runtime crash.
- Stage 3: closed-form polynomial evaluation (the same architectural fix as Python stage 5), hand-implemented via Horner's method.
- Stage 4: bivariate (M, e) surface evaluation (the same fix as Python stage 6).

## Key finding 1 — the bindings work, and the underlying limits are identical
Once the JNA signatures were correct (stage 0 succeeded first try, error ~2e-9), every substantive finding from the Python prototype reproduced exactly: no ciphertext/ciphertext division, multiplicative depth as a hard budgeted resource, and the same architectural fix (fit a closed-form polynomial offline, evaluate it with only +/−/× at runtime). This isn't a surprise — TenSEAL wraps the same SEAL C++ core sealc exposes — but it's worth having confirmed directly against the C++ source rather than assuming Python's findings transfer.

## Key finding 2 — SEAL's raw C API has no polyval; TenSEAL's convenience layer doesn't exist at this level
This is the one real, language-specific difference. TenSEAL's `CKKSVector.polyval()` manages relinearize/rescale/level bookkeeping internally — that convenience simply doesn't exist in `sealc`. Every polynomial evaluation here was hand-implemented with explicit `Evaluator_Multiply` → `Evaluator_Relinearize` → `Evaluator_RescaleToNext` sequencing (`CkksContext.multiply()`), and every plaintext operand had to be re-encoded at the exact `parms_id`/scale of whatever ciphertext it was about to combine with (`CkksContext.encodeAt`, driven by `Ciphertext_ParmsId`/`Ciphertext_Scale` getters — there is no automatic mod-switch-on-mismatch in the raw API the way some higher-level wrappers provide).

Confirmed the "no ciphertext divide anywhere" finding by reading `native/src/seal/evaluator.h` directly: `grep -i divide` on the header returns zero matches involving two ciphertexts. In Java this is visible as an API-surface fact before writing any code, rather than a runtime exception as it was in the Python prototype.

## Key finding 3 — hand-rolled polynomial evaluation is a real minefield here too, but the specific bug was new
Stage 4 (bivariate M/e evaluation) failed twice before working, both times with `Evaluator_Add failed` rather than a scale/parameter exception with a readable message:
1. First attempt matched ciphertext **levels** (via mod-switching) before summing cross-terms, but not **scale**. Mod-switching moves a ciphertext to the next position in the modulus chain without dividing its value — it changes level but not the scale field. A real multiply-then-rescale changes both. Two terms that reached the same level by different mixes of "real rescale" vs "bare mod-switch" steps had matching levels but mismatched scales, and `Evaluator_Add` rejected the sum.
2. Fix: force every term (every value of `j` in the `e`-power sum) through the exact same total count of real rescales — `DM + DE`, padding shorter paths with multiplies against a fresh encrypted `1.0` rather than free mod-switches. CKKS's scale field is pure bookkeeping (`original_scale / product_of_primes_consumed_so_far`), deterministic and data-independent — so equal rescale counts through the same modulus chain guarantee an *exact* scale match, not just an approximate one. Once every term took the same "budget" path, `Evaluator_Add` succeeded.

Lesson, sharper than the Python version's: in CKKS, "same level" and "same scale" are two different invariants that both have to hold before combining ciphertexts, and cheap level-only operations (mod-switch) can silently desynchronize them from ciphertexts that reached the same level via an actual rescale.

## Numbers, for reference
- Stage 0 (add + multiply-by-plaintext round trip): error 2e-9.
- Stage 1 (linear propagation): error ~1e-9 rad.
- Stage 3 (closed-form x(M), y(M), degree 14): error 0.003–0.06 m across six test points — noticeably tighter than the Python prototype's 3–90 m. Plausibly because Horner's method here does one multiply per degree with a single running ciphertext, vs. TenSEAL's internal polyval building a full power ladder; fewer or differently-ordered rescales can mean less accumulated floating-point drift. Not confirmed against TenSEAL's source, just the most likely explanation.
- Stage 4 (bivariate x(M,e), y(M,e), DM=14, DE=2): error 0.4–0.5 m at the test point, using exactly 16 sequential ciphertext multiplies against a 16×40-bit-prime chain — the same context size Python needed for the single-variable case, because the eccentricity term was folded in via padding rather than adding net new depth.
- Wall test: identical to Python — a 16×40-bit-prime chain (`poly_modulus_degree=32768`) supports exactly 16 sequential multiplications and fails on the 17th, regardless of language.

## The tradeoff this leaves open
Same as the Python prototype: this design protects orbital *phase* (M) and, as of stage 4, narrow-range eccentricity (e). It does not protect orbit *shape* parameters that must stay public to build the offline fit (here: semi-major axis `a`, and the fitting range of `e`). See [[SGP4 FHE Prototype Findings]] for the original framing of this tradeoff against real SSA/collision-avoidance use.

## Links
- Python counterpart: [[SGP4 FHE Prototype Findings]]
- Motivated by: [[FHE Project Ideas]]
- Concepts used: [[CKKS]], [[Noise and Bootstrapping]]
- Back to: [[FHE MOC]]

#fhe/project #fhe/experiment #fhe/java
