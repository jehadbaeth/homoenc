package sgp4fhe;

import com.sun.jna.Pointer;

/**
 * Java analogue of the Python prototype's stage 5: sidestep the division wall
 * from stage 2 by fitting x(M), y(M) as a plaintext polynomial offline (for a
 * fixed, public orbit shape a, e) and evaluating it homomorphically with only
 * +, -, * — no iteration, no division, anywhere.
 *
 * The Java port surfaces a real difference from the Python/TenSEAL version:
 * TenSEAL's CKKSVector.polyval() manages relinearize/rescale/level bookkeeping
 * internally. sealc's raw Evaluator has no such convenience — Horner's method
 * had to be hand-implemented here, including manually mod-switching the `t`
 * ciphertext down one level per iteration to keep it aligned with the
 * shrinking level of the running result before every multiply (see
 * CkksContext.multiply/modSwitchToNext). Getting this wrong is exactly the
 * "scale out of bounds" / parms_id-mismatch class of bug the Python prototype
 * hit when it abandoned polyval for a hand-rolled evaluator in stage 4 — in
 * Java there is no non-hand-rolled option to fall back to.
 */
public class Stage03ClosedFormPolynomial {

    static final int DEGREE = 14;
    static final double A = 6798.0;
    static final double E = 0.0007;

    static double toT(double M) {
        return (M - Math.PI) / Math.PI;
    }

    public static void main(String[] args) {
        int samples = 400;
        double[] tSamples = new double[samples];
        double[] xSamples = new double[samples];
        double[] ySamples = new double[samples];
        for (int i = 0; i < samples; i++) {
            double M = 2 * Math.PI * i / samples;
            tSamples[i] = toT(M);
            double[] pos = Kepler.truePosition(M, A, E);
            xSamples[i] = pos[0];
            ySamples[i] = pos[1];
        }
        double[] coeffsX = PolyFit.fitMonomial(tSamples, xSamples, DEGREE);
        double[] coeffsY = PolyFit.fitMonomial(tSamples, ySamples, DEGREE);

        double maxErrX = 0, maxErrY = 0;
        for (int i = 0; i < samples; i++) {
            maxErrX = Math.max(maxErrX, Math.abs(PolyFit.evaluate(coeffsX, tSamples[i]) - xSamples[i]));
            maxErrY = Math.max(maxErrY, Math.abs(PolyFit.evaluate(coeffsY, tSamples[i]) - ySamples[i]));
        }
        System.out.printf("plaintext monomial fit (t in [-1,1]), degree %d: max|error| x=%.2e km, y=%.2e km%n%n", DEGREE, maxErrX, maxErrY);

        CkksContext ctx = new CkksContext(32768, new int[] { 60, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 40, 60 }, Math.pow(2, 40));

        double[] testMs = { 0.3, 1.5, 1.837924, 3.1, 4.6, 6.0 };
        System.out.printf("%10s %12s %12s %10s %12s %12s %10s%n", "M", "x true", "x FHE", "err x (m)", "y true", "y FHE", "err y (m)");
        for (double M : testMs) {
            double[] truePos = Kepler.truePosition(M, A, E);
            double t = toT(M);
            Pointer tCipher = ctx.encrypt(t);

            double xFhe = evalHorner(ctx, tCipher, coeffsX);
            double yFhe = evalHorner(ctx, tCipher, coeffsY);

            System.out.printf("%10.4f %12.4f %12.4f %10.4f %12.4f %12.4f %10.4f%n",
                    M, truePos[0], xFhe, Math.abs(truePos[0] - xFhe) * 1000,
                    truePos[1], yFhe, Math.abs(truePos[1] - yFhe) * 1000);
        }

        System.out.println();
        System.out.println("No decryption happened server-side. No division, ciphertext or otherwise, was used.");
        System.out.println("Depth cost is fixed at DEGREE multiplications, known before encrypting anything.");
    }

    static double evalHorner(CkksContext ctx, Pointer tCipher, double[] ascendingCoeffs) {
        return ctx.decrypt(evalHornerCipher(ctx, tCipher, ascendingCoeffs));
    }

    /** Horner evaluation: result = ((c_n * t + c_{n-1}) * t + ... ) * t + c_0, entirely homomorphic. */
    static Pointer evalHornerCipher(CkksContext ctx, Pointer tCipher, double[] ascendingCoeffs) {
        int n = ascendingCoeffs.length - 1;
        Pointer result = ctx.encrypt(ascendingCoeffs[n]);
        Pointer tAtLevel = tCipher;

        for (int i = n - 1; i >= 0; i--) {
            Pointer multiplied = ctx.multiply(result, tAtLevel);
            ctx.destroy(result);
            Pointer coeffPlain = ctx.encodeAt(ascendingCoeffs[i], ctx.parmsIdOf(multiplied), ctx.scaleOf(multiplied));
            result = ctx.addPlain(multiplied, coeffPlain);
            ctx.destroy(multiplied);
            ctx.destroyPlain(coeffPlain);
            if (i > 0) {
                Pointer nextT = ctx.modSwitchToNext(tAtLevel);
                if (tAtLevel != tCipher) ctx.destroy(tAtLevel);
                tAtLevel = nextT;
            }
        }
        if (tAtLevel != tCipher) ctx.destroy(tAtLevel);
        return result;
    }
}
