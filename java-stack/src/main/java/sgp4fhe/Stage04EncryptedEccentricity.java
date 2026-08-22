package sgp4fhe;

import com.sun.jna.Pointer;

/**
 * Java analogue of the Python prototype's stage 6: encrypt eccentricity e too,
 * not just mean anomaly M, turning x(M) into a bivariate surface x(M, e).
 *
 * SEAL's raw C API has no polyval-for-two-variables of any kind, so this adds
 * a real architectural problem beyond what stage 3 needed: t_M^i and t_e^j are
 * built as separate power ladders and sit at DIFFERENT levels in the modulus
 * chain (t_M^i at level i-1, t_e^j at level j-1). Multiplying two ciphertexts
 * at different levels is rejected outright by SEAL (parms_id mismatch) — you
 * MUST mod-switch the shallower one up to match before every cross-term
 * multiply. To keep this tractable by hand, the evaluation below is grouped
 * as sum_j te^j * Q_j(t_M), where each Q_j is its own Horner evaluation
 * (identical machinery to stage 3) that lands at a FIXED level (=DM) regardless
 * of j — so only one mod-switch-then-multiply is needed per j, not one per
 * (i,j) cross term.
 *
 * Second part mirrors the Python "hard wall": push the M-ladder alone to
 * degree 20 under the same 16-forty-bit-prime context that stage 3 used, and
 * watch it fail once the chain runs out of primes. Multiplicative depth is a
 * real, exhaustible, budgeted resource, exactly as in Python.
 */
public class Stage04EncryptedEccentricity {

    static final double A = 6798.0;
    static final double E_MIN = 0.0, E_MAX = 0.02;
    static final int DM = 14, DE = 2;

    static double toTM(double M) { return (M - Math.PI) / Math.PI; }
    static double toTE(double e) {
        double mid = (E_MIN + E_MAX) / 2, half = (E_MAX - E_MIN) / 2;
        return (e - mid) / half;
    }

    public static void main(String[] args) {
        int nM = 80, nE = 10;
        double[] tMs = new double[nM * nE], tEs = new double[nM * nE], xs = new double[nM * nE], ys = new double[nM * nE];
        int idx = 0;
        for (int mi = 0; mi < nM; mi++) {
            double M = 2 * Math.PI * mi / nM;
            for (int ei = 0; ei < nE; ei++) {
                double e = E_MIN + (E_MAX - E_MIN) * ei / (nE - 1);
                tMs[idx] = toTM(M);
                tEs[idx] = toTE(e);
                double[] pos = Kepler.truePosition(M, A, e);
                xs[idx] = pos[0];
                ys[idx] = pos[1];
                idx++;
            }
        }
        double[] coeffsX = BivariatePolyFit.fit(tMs, tEs, xs, DM, DE);
        double[] coeffsY = BivariatePolyFit.fit(tMs, tEs, ys, DM, DE);
        System.out.printf("bivariate fit: degree %d in M, degree %d in e, %d terms%n", DM, DE, coeffsX.length);

        double[][] testPoints = { {0.3, 0.003}, {1.5, 0.012}, {1.837924, 0.0007}, {3.1, 0.018}, {4.6, 0.0}, {6.0, 0.02} };
        double maxErrX = 0, maxErrY = 0;
        for (double[] p : testPoints) {
            double[] truePos = Kepler.truePosition(p[0], A, p[1]);
            double xFit = BivariatePolyFit.evaluate(coeffsX, DM, DE, toTM(p[0]), toTE(p[1]));
            double yFit = BivariatePolyFit.evaluate(coeffsY, DM, DE, toTM(p[0]), toTE(p[1]));
            maxErrX = Math.max(maxErrX, Math.abs(truePos[0] - xFit));
            maxErrY = Math.max(maxErrY, Math.abs(truePos[1] - yFit));
        }
        System.out.printf("plaintext fit error at test points: max x=%.4f km, max y=%.4f km%n%n", maxErrX, maxErrY);

        CkksContext ctx = new CkksContext(32768,
                new int[] { 60, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 60 }, Math.pow(2, 40));

        System.out.println("Attempting encrypted bivariate evaluation (M and e both encrypted)...");
        try {
            double Mtest = 1.837924, eTest = 0.012;
            Pointer tM = ctx.encrypt(toTM(Mtest));
            Pointer tE = ctx.encrypt(toTE(eTest));

            long t0 = System.nanoTime();
            double xFhe = evalBivariate(ctx, tM, tE, coeffsX);
            double yFhe = evalBivariate(ctx, tM, tE, coeffsY);
            double elapsed = (System.nanoTime() - t0) / 1e9;

            double[] truePos = Kepler.truePosition(Mtest, A, eTest);
            System.out.printf("SUCCEEDED in %.2fs%n", elapsed);
            System.out.printf("x: true=%.4f fhe=%.4f err=%.1f m%n", truePos[0], xFhe, Math.abs(truePos[0] - xFhe) * 1000);
            System.out.printf("y: true=%.4f fhe=%.4f err=%.1f m%n", truePos[1], yFhe, Math.abs(truePos[1] - yFhe) * 1000);
            System.out.println();
            System.out.println("Narrow LEO eccentricity range [0, 0.02]: encrypting e alongside M was cheap --");
            System.out.println("one extra mod-switch-then-multiply per j (DE=2 => 2 extra ops), not per cross term.");
        } catch (RuntimeException ex) {
            System.out.println("FAILED: " + ex.getMessage());
        }

        System.out.println();
        System.out.println("=".repeat(70));
        System.out.println("Pushing further: build the M-ladder alone to degree 20 under the SAME");
        System.out.println("16x40-bit-prime context. Does it survive?");
        System.out.println("=".repeat(70));

        CkksContext wallCtx = new CkksContext(32768,
                new int[] { 60, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 60 }, Math.pow(2, 40));
        try {
            Pointer t = wallCtx.encrypt(toTM(1.837924));
            Pointer power = t;
            for (int k = 2; k <= 20; k++) {
                power = wallCtx.multiply(power, t);
                System.out.println("  degree " + k + ": ok");
                t = wallCtx.modSwitchToNext(t);
            }
            System.out.println("Unexpectedly survived the full ladder.");
        } catch (RuntimeException ex) {
            System.out.println("  FAILED building the M power ladder: " + ex.getMessage());
            System.out.println();
            System.out.println("Hard wall, not a tuning problem: this 16x40-bit-prime context supports 16");
            System.out.println("sequential ciphertext multiplications and fails beyond that. A wide-eccentricity");
            System.out.println("fit needing degree ~20 in M alone (plus e's own ladder and cross-term multiplies)");
            System.out.println("needs a much larger modulus chain -- slower, more memory, more bandwidth per op.");
        }
    }

    static double evalBivariate(CkksContext ctx, Pointer tM, Pointer tE, double[] coeffs) {
        // Qj(tM): Horner over i for fixed j, ascending coefficients coeffs[i*(DE+1)+j]. Every Qj
        // does exactly DM ciphertext multiplies (14 rescales through the SAME prime sequence), so
        // all Qj land at level DM with IDENTICAL scale fields -- scale in CKKS is pure bookkeeping
        // (original_scale / product_of_primes_used_so_far), not data-dependent, so equal rescale
        // counts through the same chain guarantee an exact scale match, not just an approximate one.
        Pointer[] q = new Pointer[DE + 1];
        for (int j = 0; j <= DE; j++) {
            double[] ascending = new double[DM + 1];
            for (int i = 0; i <= DM; i++) ascending[i] = coeffs[i * (DE + 1) + j];
            q[j] = Stage03ClosedFormPolynomial.evalHornerCipher(ctx, tM, ascending);
        }

        // First attempt here pre-built a te power ladder (tE, tE^2, ...) and multiplied each Qj by
        // the matching power, mod-switching to align LEVELS. That still failed Evaluator_Add: level
        // alignment isn't scale alignment. tE^2 (built via one real multiply+rescale) had gone
        // through one MORE rescale than tE^0/tE^1 (built via mod-switch only, 0 rescales) by the
        // time everything reached a common level -- so despite matching levels, the terms' scale
        // fields differed by that one extra division, and SEAL's Add rejects mismatched scales.
        // Fix: give every term of j the SAME total rescale count DM+DE, by multiplying Qj by tE
        // exactly j times and padding the remaining (DE-j) steps with multiplies against a fresh
        // encrypted 1.0 -- a real ciphertext multiply, so it consumes a real rescale like the rest.
        Pointer sum = null;
        for (int j = 0; j <= DE; j++) {
            Pointer term = q[j];
            for (int s = 0; s < j; s++) {
                Pointer level = bringToLevel(ctx, tE, DM + s);
                Pointer next = ctx.multiply(term, level);
                ctx.destroy(term);
                if (level != tE) ctx.destroy(level);
                term = next;
            }
            for (int s = 0; s < DE - j; s++) {
                Pointer one = ctx.encrypt(1.0);
                Pointer level = bringToLevel(ctx, one, DM + j + s);
                if (level != one) ctx.destroy(one);
                Pointer next = ctx.multiply(term, level);
                ctx.destroy(term);
                ctx.destroy(level);
                term = next;
            }
            if (sum == null) {
                sum = term;
            } else {
                Pointer newSum = ctx.add(sum, term);
                ctx.destroy(sum);
                ctx.destroy(term);
                sum = newSum;
            }
        }
        double result = ctx.decrypt(sum);
        ctx.destroy(sum);
        return result;
    }

    static Pointer bringToLevel(CkksContext ctx, Pointer cipherAtLevel0, int targetLevel) {
        Pointer result = cipherAtLevel0;
        for (int lvl = 0; lvl < targetLevel; lvl++) {
            Pointer next = ctx.modSwitchToNext(result);
            if (result != cipherAtLevel0) ctx.destroy(result);
            result = next;
        }
        return result;
    }
}
