package sgp4fhe;

/** Least-squares fit of x(tM, tE) = sum_{i,j} c[i,j] * tM^i * tE^j, same normal-equations approach as PolyFit. */
public final class BivariatePolyFit {
    private BivariatePolyFit() {}

    public static double[] fit(double[] tM, double[] tE, double[] y, int degM, int degE) {
        int terms = (degM + 1) * (degE + 1);
        double[][] ata = new double[terms][terms];
        double[] aty = new double[terms];
        double[] row = new double[terms];

        for (int s = 0; s < y.length; s++) {
            double[] powM = new double[degM + 1];
            double[] powE = new double[degE + 1];
            powM[0] = 1.0;
            for (int k = 1; k <= degM; k++) powM[k] = powM[k - 1] * tM[s];
            powE[0] = 1.0;
            for (int k = 1; k <= degE; k++) powE[k] = powE[k - 1] * tE[s];

            int idx = 0;
            for (int i = 0; i <= degM; i++)
                for (int j = 0; j <= degE; j++)
                    row[idx++] = powM[i] * powE[j];

            for (int a = 0; a < terms; a++) {
                aty[a] += row[a] * y[s];
                for (int b = 0; b < terms; b++) ata[a][b] += row[a] * row[b];
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

    public static double evaluate(double[] coeffs, int degM, int degE, double tM, double tE) {
        double[] powM = new double[degM + 1];
        double[] powE = new double[degE + 1];
        powM[0] = 1.0;
        for (int k = 1; k <= degM; k++) powM[k] = powM[k - 1] * tM;
        powE[0] = 1.0;
        for (int k = 1; k <= degE; k++) powE[k] = powE[k - 1] * tE;
        double result = 0.0;
        int idx = 0;
        for (int i = 0; i <= degM; i++)
            for (int j = 0; j <= degE; j++)
                result += coeffs[idx++] * powM[i] * powE[j];
        return result;
    }
}
