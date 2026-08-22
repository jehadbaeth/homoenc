package sgp4fhe;

import com.sun.jna.Pointer;
import com.sun.jna.ptr.PointerByReference;

/**
 * First proof point for the Java/JNA/SEAL bridge, the direct analogue of the
 * Python prototype's stage 3: build a CKKS context by hand through the sealc
 * C ABI, encrypt two values, add them and multiply one by a plaintext scalar
 * homomorphically, decrypt, and check the result. Nothing here is SGP4-shaped
 * yet — the goal is only to prove the JNA bindings in SealC.java are wired
 * correctly (right argument order/types) before porting the orbit stages.
 */
public class Stage00Roundtrip {

    static void check(int hresult, String what) {
        if (hresult != SealC.S_OK) {
            throw new RuntimeException(what + " failed, HRESULT=0x" + Integer.toHexString(hresult));
        }
    }

    public static void main(String[] args) {
        SealC seal = SealC.INSTANCE;

        long polyModulusDegree = 8192;
        int[] bitSizes = {60, 40, 40, 60};

        Pointer[] coeffModulus = new Pointer[bitSizes.length];
        check(seal.CoeffModulus_Create1(polyModulusDegree, bitSizes.length, bitSizes, coeffModulus), "CoeffModulus_Create1");

        PointerByReference encParamsRef = new PointerByReference();
        check(seal.EncParams_Create1((byte) 2 /* ckks */, encParamsRef), "EncParams_Create1");
        Pointer encParams = encParamsRef.getValue();
        check(seal.EncParams_SetPolyModulusDegree(encParams, polyModulusDegree), "EncParams_SetPolyModulusDegree");
        check(seal.EncParams_SetCoeffModulus(encParams, coeffModulus.length, coeffModulus), "EncParams_SetCoeffModulus");

        PointerByReference contextRef = new PointerByReference();
        check(seal.SEALContext_Create(encParams, true, 0 /* sec_level_type::none, matches prototype's own tuning */, contextRef), "SEALContext_Create");
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

        long[] firstParmsId = new long[4];
        check(seal.SEALContext_FirstParmsId(context, firstParmsId), "SEALContext_FirstParmsId");
        double scale = Math.pow(2, 40);

        double a = 3.5;
        double b = 2.25;

        Pointer plainA = encodeScalar(seal, encoder, a, firstParmsId, scale, pool);
        Pointer plainB = encodeScalar(seal, encoder, b, firstParmsId, scale, pool);

        PointerByReference cipherARef = new PointerByReference();
        check(seal.Ciphertext_Create1(pool, cipherARef), "Ciphertext_Create1 (a)");
        Pointer cipherA = cipherARef.getValue();
        check(seal.Encryptor_Encrypt(encryptor, plainA, cipherA, pool), "Encryptor_Encrypt (a)");

        PointerByReference cipherBRef = new PointerByReference();
        check(seal.Ciphertext_Create1(pool, cipherBRef), "Ciphertext_Create1 (b)");
        Pointer cipherB = cipherBRef.getValue();
        check(seal.Encryptor_Encrypt(encryptor, plainB, cipherB, pool), "Encryptor_Encrypt (b)");

        // homomorphic: (a + b) * 2.0, using add + multiply-by-plaintext-scalar
        PointerByReference sumRef = new PointerByReference();
        check(seal.Ciphertext_Create1(pool, sumRef), "Ciphertext_Create1 (sum)");
        Pointer sum = sumRef.getValue();
        check(seal.Evaluator_Add(evaluator, cipherA, cipherB, sum), "Evaluator_Add");

        Pointer plainTwo = encodeScalar(seal, encoder, 2.0, firstParmsId, scale, pool);
        PointerByReference productRef = new PointerByReference();
        check(seal.Ciphertext_Create1(pool, productRef), "Ciphertext_Create1 (product)");
        Pointer product = productRef.getValue();
        check(seal.Evaluator_MultiplyPlain(evaluator, sum, plainTwo, product, pool), "Evaluator_MultiplyPlain");

        PointerByReference resultPlainRef = new PointerByReference();
        check(seal.Plaintext_Create1(Pointer.NULL, resultPlainRef), "Plaintext_Create1 (result)");
        Pointer resultPlain = resultPlainRef.getValue();
        check(seal.Decryptor_Decrypt(decryptor, product, resultPlain), "Decryptor_Decrypt");

        com.sun.jna.ptr.LongByReference slotCount = new com.sun.jna.ptr.LongByReference();
        check(seal.CKKSEncoder_SlotCount(encoder, slotCount), "CKKSEncoder_SlotCount");
        double[] decoded = new double[(int) slotCount.getValue()];
        com.sun.jna.ptr.LongByReference valueCount = new com.sun.jna.ptr.LongByReference(decoded.length);
        check(seal.CKKSEncoder_Decode1(encoder, resultPlain, valueCount, decoded, pool), "CKKSEncoder_Decode1");

        double expected = (a + b) * 2.0;
        double actual = decoded[0];
        System.out.printf("expected=%.6f decrypted=%.6f abs_err=%.2e%n", expected, actual, Math.abs(expected - actual));
        System.out.println(Math.abs(expected - actual) < 1e-3
                ? "JNA -> sealc -> SEAL round trip OK"
                : "JNA -> sealc -> SEAL round trip PRODUCED WRONG RESULT");
    }

    private static Pointer encodeScalar(SealC seal, Pointer encoder, double value, long[] parmsId, double scale, Pointer pool) {
        PointerByReference plainRef = new PointerByReference();
        check(seal.Plaintext_Create1(Pointer.NULL, plainRef), "Plaintext_Create1");
        Pointer plain = plainRef.getValue();
        check(seal.CKKSEncoder_Encode1(encoder, 1, new double[] { value }, parmsId, scale, plain, pool), "CKKSEncoder_Encode1");
        return plain;
    }
}
