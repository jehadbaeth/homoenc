---
title: HEIR
tags: [fhe/tooling, fhe/compiler, status/todo]
created: 2026-08-21
---

# HEIR

Google's open-source compiler for FHE, built on MLIR (the same compiler infrastructure underlying parts of TensorFlow/XLA). Goal: let you write a program once at a reasonably high level, then compile it down to run under different FHE schemes/backends (targeting libraries like [[FHE Libraries|OpenFHE]]), instead of hand-writing scheme-specific ciphertext code.

## Why it matters, and why not to start here
FHE code written directly against a scheme's API is scheme-specific, hard to port, and easy to get wrong (parameter selection, noise budgeting). A compiler layer that automates scheme selection, parameter choice, and lowering is exactly the kind of infra abstraction that matters once you already understand what's underneath, it. This is why it's the last stage, not the first, in this notes path: the abstractions only make sense once you've felt the pain they're solving.

## Open questions to fill in
- What's the actual input language / dialect you write against? (MLIR dialects, or a frontend DSL?)
- Which backend schemes does it currently target, and how mature is each path?
- Does it help with parameter selection (a genuinely hard, error-prone manual step in raw scheme APIs)?

## Plan
- [ ] Read the HEIR docs/README once Stage 3 concepts are solid
- [ ] Find or write the smallest possible example program and compile it
- [ ] Compare the generated code/params against what you'd hand-write with a raw library

## Links
- Previous: [[FHE Libraries]]
- Next: [[FHE Project Ideas]]

#fhe/compiler
