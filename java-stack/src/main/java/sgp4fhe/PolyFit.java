package sgp4fhe;

/**
 * Plain Java least-squares monomial polynomial fit (normal equations + Gaussian
 * elimination with partial pivoting), no external math library. Mirrors the
 * Python prototype's finding: fitting monomial coefficients directly in a
 * rescaled domain t = (M - pi) / pi in [-1, 1] is numerically stable up to
 * degree ~14 for this orbit, so there is no need for a Chebyshev-basis
 * intermediate (which, in the Python prototype, was itself the source of a
 * ~77 km error when converted back to monomial form via cheb2poly).
 */
public final class PolyFit {
    private PolyFit() {}

    /** Returns ascending-power coefficients c[0..degree] minimizing sum((sum c_i t^i - y)^2). */
    public static double[] fitMonomial(double[] t, double[] y, int degree) {
        int n = degree + 1;
        double[][] ata = new double[n][n];
        double[] aty = new double[n];
        double[] powers = new double[2 * degree + 1];

        for (int s = 0; s < t.length; s++) {
            powers[0] = 1.0;
            for (int k = 1; k < powers.length; k++) {
                powers[k] = powers[k - 1] * t[s];
            }
            for (int i = 0; i < n; i++) {
                aty[i] += powers[i] * y[s];
                for (int j = 0; j < n; j++) {
                    ata[i][j] += powers[i + j];
                }
            }
        }
        return solve(ata, aty);
    }

    private static double[] solve(double[][] a, double[] b) {
        int n = b.length;
        for (int col = 0; col < n; col++) {
            int pivot = col;
            for (int row = col + 1; row < n; row++) {
                if (Math.abs(a[row][col]) > Math.abs(a[pivot][col])) pivot = row;
            }
            double[] tmpRow = a[col]; a[col] = a[pivot]; a[pivot] = tmpRow;
            double tmpVal = b[col]; b[col] = b[pivot]; b[pivot] = tmpVal;

            for (int row = col + 1; row < n; row++) {
                double factor = a[row][col] / a[col][col];
                for (int k = col; k < n; k++) a[row][k] -= factor * a[col][k];
                b[row] -= factor * b[col];
            }
        }
        double[] x = new double[n];
        for (int row = n - 1; row >= 0; row--) {
            double sum = b[row];
            for (int k = row + 1; k < n; k++) sum -= a[row][k] * x[k];
            x[row] = sum / a[row][row];
        }
        return x;
    }

    public static double evaluate(double[] coeffs, double t) {
        double result = 0.0, tp = 1.0;
        for (double c : coeffs) {
            result += c * tp;
            tp *= t;
        }
        return result;
    }
}
