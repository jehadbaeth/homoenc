package sgp4fhe;

import com.sun.jna.Pointer;
import com.sun.jna.ptr.LongByReference;
import com.sun.jna.ptr.PointerByReference;

/**
 * Thin wrapper around the raw sealc calls needed repeatedly across stages:
 * context setup, key generation, encrypt/decrypt, encode/decode. Deliberately
 * NOT a general-purpose CKKS library — SEAL's C API has no equivalent of
 * TenSEAL's polyval() convenience method, so callers still hand-manage
 * relinearize/rescale/mod-switch themselves for anything beyond one multiply.
 */
public class CkksContext {
    public final SealC seal = SealC.INSTANCE;
    public final Pointer context, pool, encryptor, decryptor, evaluator, encoder, relinKeys;
    public final long[] firstParmsId = new long[4];
    public final double scale;

    static void check(int hresult, String what) {
        if (hresult != SealC.S_OK) {
            throw new RuntimeException(what + " failed, HRESULT=0x" + Integer.toHexString(hresult));
        }
    }

    public CkksContext(long polyModulusDegree, int[] bitSizes, double scale) {
        this.scale = scale;
        Pointer[] coeffModulus = new Pointer[bitSizes.length];
        check(seal.CoeffModulus_Create1(polyModulusDegree, bitSizes.length, bitSizes, coeffModulus), "CoeffModulus_Create1");

        PointerByReference encParamsRef = new PointerByReference();
        check(seal.EncParams_Create1((byte) 2, encParamsRef), "EncParams_Create1");
        Pointer encParams = encParamsRef.getValue();
        check(seal.EncParams_SetPolyModulusDegree(encParams, polyModulusDegree), "EncParams_SetPolyModulusDegree");
        check(seal.EncParams_SetCoeffModulus(encParams, coeffModulus.length, coeffModulus), "EncParams_SetCoeffModulus");

        PointerByReference contextRef = new PointerByReference();
        check(seal.SEALContext_Create(encParams, true, 0, contextRef), "SEALContext_Create");
        context = contextRef.getValue();

        PointerByReference poolRef = new PointerByReference();
        check(seal.MemoryPoolHandle_Global(poolRef), "MemoryPoolHandle_Global");
        pool = poolRef.getValue();

        PointerByReference keygenRef = new PointerByReference();
        check(seal.KeyGenerator_Create1(context, keygenRef), "KeyGenerator_Create1");
        Pointer keygen = keygenRef.getValue();

        PointerByReference secretKeyRef = new PointerByReference();
        check(seal.KeyGenerator_SecretKey(keygen, secretKeyRef), "KeyGenerator_SecretKey");
        Pointer secretKey = secretKeyRef.getValue();

        PointerByReference publicKeyRef = new PointerByReference();
        check(seal.KeyGenerator_CreatePublicKey(keygen, false, publicKeyRef), "KeyGenerator_CreatePublicKey");
        Pointer publicKey = publicKeyRef.getValue();

        PointerByReference relinKeysRef = new PointerByReference();
        check(seal.KeyGenerator_CreateRelinKeys(keygen, false, relinKeysRef), "KeyGenerator_CreateRelinKeys");
        relinKeys = relinKeysRef.getValue();

        PointerByReference encryptorRef = new PointerByReference();
        check(seal.Encryptor_Create(context, publicKey, Pointer.NULL, encryptorRef), "Encryptor_Create");
        encryptor = encryptorRef.getValue();

        PointerByReference decryptorRef = new PointerByReference();
        check(seal.Decryptor_Create(context, secretKey, decryptorRef), "Decryptor_Create");
        decryptor = decryptorRef.getValue();

        PointerByReference evaluatorRef = new PointerByReference();
        check(seal.Evaluator_Create(context, evaluatorRef), "Evaluator_Create");
        evaluator = evaluatorRef.getValue();

        PointerByReference encoderRef = new PointerByReference();
        check(seal.CKKSEncoder_Create(context, encoderRef), "CKKSEncoder_Create");
        encoder = encoderRef.getValue();

        check(seal.SEALContext_FirstParmsId(context, firstParmsId), "SEALContext_FirstParmsId");
    }

    public Pointer encodeAt(double value, long[] parmsId, double atScale) {
        PointerByReference plainRef = new PointerByReference();
        check(seal.Plaintext_Create1(Pointer.NULL, plainRef), "Plaintext_Create1");
        Pointer plain = plainRef.getValue();
        check(seal.CKKSEncoder_Encode1(encoder, 1, new double[] { value }, parmsId, atScale, plain, pool), "CKKSEncoder_Encode1");
        return plain;
    }

    public Pointer encode(double value) {
        return encodeAt(value, firstParmsId, scale);
    }

    public Pointer encrypt(double value) {
        Pointer plain = encode(value);
        PointerByReference cipherRef = new PointerByReference();
        check(seal.Ciphertext_Create1(pool, cipherRef), "Ciphertext_Create1");
        Pointer cipher = cipherRef.getValue();
        check(seal.Encryptor_Encrypt(encryptor, plain, cipher, pool), "Encryptor_Encrypt");
        return cipher;
    }

    public double decrypt(Pointer cipher) {
        PointerByReference plainRef = new PointerByReference();
        check(seal.Plaintext_Create1(Pointer.NULL, plainRef), "Plaintext_Create1 (decrypt)");
        Pointer plain = plainRef.getValue();
        check(seal.Decryptor_Decrypt(decryptor, cipher, plain), "Decryptor_Decrypt");

        LongByReference slotCount = new LongByReference();
        check(seal.CKKSEncoder_SlotCount(encoder, slotCount), "CKKSEncoder_SlotCount");
        double[] decoded = new double[(int) slotCount.getValue()];
        LongByReference valueCount = new LongByReference(decoded.length);
        check(seal.CKKSEncoder_Decode1(encoder, plain, valueCount, decoded, pool), "CKKSEncoder_Decode1");
        return decoded[0];
    }

    public Pointer newCiphertext() {
        PointerByReference ref = new PointerByReference();
        check(seal.Ciphertext_Create1(pool, ref), "Ciphertext_Create1");
        return ref.getValue();
    }

    public double scaleOf(Pointer cipher) {
        com.sun.jna.ptr.DoubleByReference ref = new com.sun.jna.ptr.DoubleByReference();
        check(seal.Ciphertext_Scale(cipher, ref), "Ciphertext_Scale");
        return ref.getValue();
    }

    public long[] parmsIdOf(Pointer cipher) {
        long[] id = new long[4];
        check(seal.Ciphertext_ParmsId(cipher, id), "Ciphertext_ParmsId");
        return id;
    }

    /** Ciphertext * ciphertext, relinearized and rescaled to the next level — one multiplicative depth unit. */
    public Pointer multiply(Pointer x, Pointer y) {
        Pointer raw = newCiphertext();
        check(seal.Evaluator_Multiply(evaluator, x, y, raw, pool), "Evaluator_Multiply");
        Pointer relinearized = newCiphertext();
        check(seal.Evaluator_Relinearize(evaluator, raw, relinKeys, relinearized, pool), "Evaluator_Relinearize");
        Pointer rescaled = newCiphertext();
        check(seal.Evaluator_RescaleToNext(evaluator, relinearized, rescaled, pool), "Evaluator_RescaleToNext");
        return rescaled;
    }

    /** Drops a ciphertext one level down the modulus chain without rescaling (for level-matching before ops). */
    public Pointer modSwitchToNext(Pointer x) {
        Pointer result = newCiphertext();
        check(seal.Evaluator_ModSwitchToNext1(evaluator, x, result, pool), "Evaluator_ModSwitchToNext1");
        return result;
    }

    public Pointer add(Pointer x, Pointer y) {
        Pointer result = newCiphertext();
        check(seal.Evaluator_Add(evaluator, x, y, result), "Evaluator_Add");
        return result;
    }

    public Pointer addPlain(Pointer x, Pointer plain) {
        Pointer result = newCiphertext();
        check(seal.Evaluator_AddPlain(evaluator, x, plain, result), "Evaluator_AddPlain");
        return result;
    }

    /** Ciphertext * known plaintext scalar, at the ciphertext's current level. No relinearize needed (no new key-switch term). */
    public Pointer multiplyByScalar(Pointer x, double value) {
        Pointer plain = encodeAt(value, parmsIdOf(x), scaleOf(x));
        Pointer result = newCiphertext();
        check(seal.Evaluator_MultiplyPlain(evaluator, x, plain, result, pool), "Evaluator_MultiplyPlain");
        return result;
    }
}
