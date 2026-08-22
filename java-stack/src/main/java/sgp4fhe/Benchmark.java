package sgp4fhe;

import com.sun.jna.Pointer;
import java.util.Arrays;
import java.util.function.Supplier;

/**
 * Performance benchmark for the JNA/SEAL bridge, run standalone (not via
 * gradle run) so an external `/usr/bin/time -l` wrapper measures the actual
 * JVM process's peak RSS, which includes SEAL's native (off-heap) allocations
 * that Runtime.totalMemory() would miss entirely.
 *
 * Reports, in CSV to stdout: operation, N, mean/median/min/max/p95 (ms).
 * A one-time context+keygen cost is reported separately, since in a real
 * client/server deployment the context and public/relinearization keys are
 * set up once and reused across many requests -- only encrypt (client),
 * evaluate (server), decrypt (client) repeat per request.
 */
public class Benchmark {
    static final int WARMUP = 5;
    static final int REPS = 30;

    public static void main(String[] args) {
        System.out.println("operation,n,mean_ms,median_ms,min_ms,max_ms,p95_ms");

        long[] contextTimes = new long[10];
        CkksContext ctx = null;
        for (int i = 0; i < 10; i++) {
            long t0 = System.nanoTime();
            ctx = new CkksContext(32768,
                    new int[] { 60, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 60 },
                    Math.pow(2, 40));
            contextTimes[i] = System.nanoTime() - t0;
        }
        report("context_setup_incl_keygen", contextTimes);

        final CkksContext fctx = ctx;

        // Every op below returns a freshly heap-allocated native ciphertext/plaintext that SEAL's C
        // API never frees automatically (no GC across the JNA boundary) -- destroy it right after
        // timing so REPS repetitions of a full-level (tens-of-MB) ciphertext don't exhaust RAM.
        time("encrypt_scalar", () -> { fctx.destroy(fctx.encrypt(1.837924)); return null; });

        Pointer sampleCipher = fctx.encrypt(1.837924);
        time("decrypt_scalar", () -> { fctx.decrypt(sampleCipher); return null; });

        Pointer a = fctx.encrypt(0.6), b = fctx.encrypt(0.4);
        time("add_ciphertexts", () -> { fctx.destroy(fctx.add(a, b)); return null; });
        time("add_plain", () -> {
            Pointer plain = fctx.encode(0.4);
            fctx.destroy(fctx.addPlain(a, plain));
            fctx.destroyPlain(plain);
            return null;
        });
        time("multiply_ciphertexts_incl_relin_rescale", () -> { fctx.destroy(fctx.multiply(a, b)); return null; });
        time("mod_switch_to_next", () -> { fctx.destroy(fctx.modSwitchToNext(a)); return null; });

        double[] coeffsX = fitStage3CoeffsX();
        Pointer tCipher = fctx.encrypt(Stage03ClosedFormPolynomial.toT(1.837924));
        time("stage3_horner_degree14_full_eval", () -> {
            fctx.destroy(Stage03ClosedFormPolynomial.evalHornerCipher(fctx, tCipher, coeffsX));
            return null;
        });

        double[] coeffsBivX = fitStage4CoeffsX();
        Pointer tM = fctx.encrypt(Stage04EncryptedEccentricity.toTM(1.837924));
        Pointer tE = fctx.encrypt(Stage04EncryptedEccentricity.toTE(0.012));
        time("stage4_bivariate_degree14x2_full_eval", () -> Stage04EncryptedEccentricity.evalBivariate(fctx, tM, tE, coeffsBivX));

        Pointer afterStage3 = Stage03ClosedFormPolynomial.evalHornerCipher(fctx, tCipher, coeffsX);
        System.err.println("# fresh_ciphertext_bytes_uncompressed=" + fctx.serializedSize(sampleCipher, (byte) 0));
        System.err.println("# fresh_ciphertext_bytes_zstd=" + fctx.serializedSize(sampleCipher, (byte) 2));
        System.err.println("# depth14_ciphertext_bytes_uncompressed=" + fctx.serializedSize(afterStage3, (byte) 0));
        System.err.println("# depth14_ciphertext_bytes_zstd=" + fctx.serializedSize(afterStage3, (byte) 2));
    }

    static double[] fitStage3CoeffsX() {
        int samples = 400;
        double[] t = new double[samples], x = new double[samples];
        for (int i = 0; i < samples; i++) {
            double M = 2 * Math.PI * i / samples;
            t[i] = Stage03ClosedFormPolynomial.toT(M);
            x[i] = Kepler.truePosition(M, Stage03ClosedFormPolynomial.A, Stage03ClosedFormPolynomial.E)[0];
        }
        return PolyFit.fitMonomial(t, x, Stage03ClosedFormPolynomial.DEGREE);
    }

    static double[] fitStage4CoeffsX() {
        int nM = 80, nE = 10;
        double[] tMs = new double[nM * nE], tEs = new double[nM * nE], xs = new double[nM * nE];
        int idx = 0;
        for (int mi = 0; mi < nM; mi++) {
            double M = 2 * Math.PI * mi / nM;
            for (int ei = 0; ei < nE; ei++) {
                double e = Stage04EncryptedEccentricity.E_MIN + (Stage04EncryptedEccentricity.E_MAX - Stage04EncryptedEccentricity.E_MIN) * ei / (nE - 1);
                tMs[idx] = Stage04EncryptedEccentricity.toTM(M);
                tEs[idx] = Stage04EncryptedEccentricity.toTE(e);
                xs[idx] = Kepler.truePosition(M, Stage04EncryptedEccentricity.A, e)[0];
                idx++;
            }
        }
        return BivariatePolyFit.fit(tMs, tEs, xs, Stage04EncryptedEccentricity.DM, Stage04EncryptedEccentricity.DE);
    }

    static void time(String name, Supplier<Object> op) {
        for (int i = 0; i < WARMUP; i++) op.get();
        long[] samples = new long[REPS];
        for (int i = 0; i < REPS; i++) {
            long t0 = System.nanoTime();
            op.get();
            samples[i] = System.nanoTime() - t0;
        }
        report(name, samples);
    }

    static void report(String name, long[] nanos) {
        long[] sorted = nanos.clone();
        Arrays.sort(sorted);
        double mean = Arrays.stream(sorted).average().orElse(0) / 1e6;
        double median = sorted[sorted.length / 2] / 1e6;
        double min = sorted[0] / 1e6;
        double max = sorted[sorted.length - 1] / 1e6;
        double p95 = sorted[(int) Math.min(sorted.length - 1, Math.ceil(sorted.length * 0.95) - 1)] / 1e6;
        System.out.printf("%s,%d,%.4f,%.4f,%.4f,%.4f,%.4f%n", name, nanos.length, mean, median, min, max, p95);
    }
}
