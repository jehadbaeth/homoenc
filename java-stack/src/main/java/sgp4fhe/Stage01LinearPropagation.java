package sgp4fhe;

import com.sun.jna.Pointer;
import com.sun.jna.ptr.PointerByReference;

/**
 * Java analogue of the Python prototype's stage 3: mean anomaly propagates
 * linearly (M = M0 + n*dt), which is exactly the shape CKKS is built for
 * (plaintext-scalar multiply and add, no ciphertext/ciphertext ops needed).
 * Confirms the JNA bridge handles this trivial case before attempting the
 * Kepler-solve wall in stage 2.
 */
public class Stage01LinearPropagation {

    static void check(int hresult, String what) {
        if (hresult != SealC.S_OK) {
            throw new RuntimeException(what + " failed, HRESULT=0x" + Integer.toHexString(hresult));
        }
    }

    static final double MU_EARTH = 398600.4418;

    static double meanMotion(double a) {
        return Math.sqrt(MU_EARTH / (a * a * a));
    }

    public static void main(String[] args) {
        SealC seal = SealC.INSTANCE;

        long polyModulusDegree = 8192;
        int[] bitSizes = {60, 40, 40, 60};
        Pointer[] coeffModulus = new Pointer[bitSizes.length];
        check(seal.CoeffModulus_Create1(polyModulusDegree, bitSizes.length, bitSizes, coeffModulus), "CoeffModulus_Create1");

        PointerByReference encParamsRef = new PointerByReference();
        check(seal.EncParams_Create1((byte) 2, encParamsRef), "EncParams_Create1");
        Pointer encParams = encParamsRef.getValue();
        check(seal.EncParams_SetPolyModulusDegree(encParams, polyModulusDegree), "EncParams_SetPolyModulusDegree");
        check(seal.EncParams_SetCoeffModulus(encParams, coeffModulus.length, coeffModulus), "EncParams_SetCoeffModulus");

        PointerByReference contextRef = new PointerByReference();
        check(seal.SEALContext_Create(encParams, true, 0, contextRef), "SEALContext_Create");
        Pointer context = contextRef.getValue();

        PointerByReference poolRef = new PointerByReference();
        check(seal.MemoryPoolHandle_Global(poolRef), "MemoryPoolHandle_Global");
        Pointer pool = poolRef.getValue();

        PointerByReference keygenRef = new PointerByReference();
        check(seal.KeyGenerator_Create1(context, keygenRef), "KeyGenerator_Create1");
        Pointer keygen = keygenRef.getValue();
        PointerByReference secretKeyRef = new PointerByReference();
        check(seal.KeyGenerator_SecretKey(keygen, secretKeyRef), "KeyGenerator_SecretKey");
        Pointer secretKey = secretKeyRef.getValue();
        PointerByReference publicKeyRef = new PointerByReference();
        check(seal.KeyGenerator_CreatePublicKey(keygen, false, publicKeyRef), "KeyGenerator_CreatePublicKey");
        Pointer publicKey = publicKeyRef.getValue();

        PointerByReference encryptorRef = new PointerByReference();
        check(seal.Encryptor_Create(context, publicKey, Pointer.NULL, encryptorRef), "Encryptor_Create");
        Pointer encryptor = encryptorRef.getValue();
        PointerByReference decryptorRef = new PointerByReference();
        check(seal.Decryptor_Create(context, secretKey, decryptorRef), "Decryptor_Create");
        Pointer decryptor = decryptorRef.getValue();
        PointerByReference evaluatorRef = new PointerByReference();
        check(seal.Evaluator_Create(context, evaluatorRef), "Evaluator_Create");
        Pointer evaluator = evaluatorRef.getValue();
        PointerByReference encoderRef = new PointerByReference();
        check(seal.CKKSEncoder_Create(context, encoderRef), "CKKSEncoder_Create");
        Pointer encoder = encoderRef.getValue();

        long[] parmsId = new long[4];
        check(seal.SEALContext_FirstParmsId(context, parmsId), "SEALContext_FirstParmsId");
        double scale = Math.pow(2, 40);

        double a = 6798.0;
        double M0 = 1.2;
        double n = meanMotion(a);

        double[] test_dt = {0, 600, 1800, 3600, 7200};
        System.out.printf("%12s %14s %14s %12s%n", "dt(s)", "M true (rad)", "M FHE (rad)", "err (rad)");
        for (double dt : test_dt) {
            double mTrue = M0 + n * dt;

            PointerByReference plainM0Ref = new PointerByReference();
            check(seal.Plaintext_Create1(Pointer.NULL, plainM0Ref), "Plaintext_Create1 (M0)");
            Pointer plainM0 = plainM0Ref.getValue();
            check(seal.CKKSEncoder_Encode1(encoder, 1, new double[] { M0 }, parmsId, scale, plainM0, pool), "Encode M0");

            PointerByReference cipherM0Ref = new PointerByReference();
            check(seal.Ciphertext_Create1(pool, cipherM0Ref), "Ciphertext_Create1 (M0)");
            Pointer cipherM0 = cipherM0Ref.getValue();
            check(seal.Encryptor_Encrypt(encryptor, plainM0, cipherM0, pool), "Encrypt M0");

            PointerByReference plainDriftRef = new PointerByReference();
            check(seal.Plaintext_Create1(Pointer.NULL, plainDriftRef), "Plaintext_Create1 (drift)");
            Pointer plainDrift = plainDriftRef.getValue();
            check(seal.CKKSEncoder_Encode1(encoder, 1, new double[] { n * dt }, parmsId, scale, plainDrift, pool), "Encode drift");

            PointerByReference cipherMRef = new PointerByReference();
            check(seal.Ciphertext_Create1(pool, cipherMRef), "Ciphertext_Create1 (M)");
            Pointer cipherM = cipherMRef.getValue();
            check(seal.Evaluator_AddPlain(evaluator, cipherM0, plainDrift, cipherM), "AddPlain (M0 + n*dt)");

            PointerByReference resultPlainRef = new PointerByReference();
            check(seal.Plaintext_Create1(Pointer.NULL, resultPlainRef), "Plaintext_Create1 (result)");
            Pointer resultPlain = resultPlainRef.getValue();
            check(seal.Decryptor_Decrypt(decryptor, cipherM, resultPlain), "Decrypt M");

            com.sun.jna.ptr.LongByReference slotCount = new com.sun.jna.ptr.LongByReference();
            check(seal.CKKSEncoder_SlotCount(encoder, slotCount), "SlotCount");
            double[] decoded = new double[(int) slotCount.getValue()];
            com.sun.jna.ptr.LongByReference valueCount = new com.sun.jna.ptr.LongByReference(decoded.length);
            check(seal.CKKSEncoder_Decode1(encoder, resultPlain, valueCount, decoded, pool), "Decode M");

            double mFhe = decoded[0];
            System.out.printf("%12.1f %14.6f %14.6f %12.2e%n", dt, mTrue, mFhe, Math.abs(mTrue - mFhe));
        }
    }
}
