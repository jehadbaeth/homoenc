package sgp4fhe;

/** Plaintext two-body Keplerian propagation, ground truth for all stages. */
public final class Kepler {
    public static final double MU_EARTH = 398600.4418;

    private Kepler() {}

    public static double meanMotion(double a) {
        return Math.sqrt(MU_EARTH / (a * a * a));
    }

    /** Newton-Raphson solve of M = E - e*sin(E), then orbital-plane position. */
    public static double[] truePosition(double M, double a, double e) {
        double E = M;
        for (int i = 0; i < 50; i++) {
            double f = E - e * Math.sin(E) - M;
            double fp = 1 - e * Math.cos(E);
            E = E - f / fp;
        }
        double x = a * (Math.cos(E) - e);
        double y = a * Math.sqrt(1 - e * e) * Math.sin(E);
        return new double[] { x, y };
    }
}
