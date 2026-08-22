# java-stack

Java port of the `../scripts/` Python/TenSEAL prototype, bridging to Microsoft
SEAL via JNA instead of a native Java FHE library (none exist for a modern
scheme — see `notes/SGP4 FHE Java Prototype Findings.md`).

## Build Microsoft SEAL's C shim

`native/SEAL/` is not vendored in this repo (it's a third-party project); clone
and build it yourself:

```bash
cd java-stack/native
git clone --depth 1 https://github.com/microsoft/SEAL.git
cd SEAL
cmake -S . -B build -DSEAL_BUILD_SEAL_C=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(sysctl -n hw.ncpu)   # or nproc on Linux
```

This produces `build/lib/libsealc.dylib` (or `.so` on Linux), which
`build.gradle`'s `jna.library.path` points at.

## Run

```bash
cd java-stack
gradle run -DmainClass=sgp4fhe.Stage00Roundtrip
gradle run -DmainClass=sgp4fhe.Stage01LinearPropagation
gradle run -DmainClass=sgp4fhe.Stage02KeplerDivisionWall
gradle run -DmainClass=sgp4fhe.Stage03ClosedFormPolynomial
gradle run -DmainClass=sgp4fhe.Stage04EncryptedEccentricity
```

## Source layout

- `SealC.java` — JNA bindings to `sealc`, signatures copied from SEAL's own
  `dotnet/src/NativeMethods.cs` P/Invoke declarations.
- `CkksContext.java` — context setup, encrypt/decrypt, and hand-managed
  multiply/relinearize/rescale/mod-switch (SEAL's raw C API has no `polyval`
  convenience the way TenSEAL does).
- `Kepler.java`, `PolyFit.java`, `BivariatePolyFit.java` — plaintext ground
  truth and least-squares polynomial fitting, no external math library.
- `Stage00`–`Stage04` — the staged prototype, see
  `notes/SGP4 FHE Java Prototype Findings.md` for what each one found.
