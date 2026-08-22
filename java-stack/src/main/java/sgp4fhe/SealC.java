package sgp4fhe;

import com.sun.jna.Library;
import com.sun.jna.Native;
import com.sun.jna.Pointer;
import com.sun.jna.ptr.DoubleByReference;
import com.sun.jna.ptr.LongByReference;
import com.sun.jna.ptr.PointerByReference;

/**
 * JNA binding to Microsoft SEAL's "sealc" C-ABI shim (native/src/seal/c in the
 * SEAL source tree). That shim was built to back SEAL's own .NET wrapper via
 * P/Invoke; every signature here was copied from dotnet/src/NativeMethods.cs
 * rather than guessed from the C++ headers, since a wrong parameter order or
 * type is silent memory corruption in JNA, not a compile error.
 *
 * Every function returns an HRESULT (0 = S_OK) instead of throwing, unlike the
 * C# wrapper which hides this behind PreserveSig=false. Callers must check it.
 */
public interface SealC extends Library {
    SealC INSTANCE = Native.load("sealc", SealC.class);

    int S_OK = 0;

    // --- Modulus ---
    int Modulus_Create1(long value, PointerByReference smallModulus);
    int Modulus_Destroy(Pointer thisptr);

    // --- CoeffModulus ---
    int CoeffModulus_Create1(long polyModulusDegree, long length, int[] bitSizes, Pointer[] coeffs);

    // --- EncryptionParameters ---
    int EncParams_Create1(byte scheme, PointerByReference encParams);
    int EncParams_Destroy(Pointer thisptr);
    int EncParams_SetPolyModulusDegree(Pointer thisptr, long polyModulusDegree);
    int EncParams_SetCoeffModulus(Pointer thisptr, long length, Pointer[] coeffs);

    // --- SEALContext ---
    int SEALContext_Create(Pointer encryptionParams, boolean expandModChain, int secLevel, PointerByReference context);
    int SEALContext_Destroy(Pointer thisptr);
    int SEALContext_FirstParmsId(Pointer thisptr, long[] parmsId);

    // --- KeyGenerator ---
    int KeyGenerator_Create1(Pointer sealContext, PointerByReference keyGenerator);
    int KeyGenerator_Destroy(Pointer thisptr);
    int KeyGenerator_CreatePublicKey(Pointer thisptr, boolean saveSeed, PointerByReference publicKey);
    int KeyGenerator_SecretKey(Pointer thisptr, PointerByReference secretKey);
    int KeyGenerator_CreateRelinKeys(Pointer thisptr, boolean saveSeed, PointerByReference relinKeys);

    // --- PublicKey / SecretKey ---
    int PublicKey_Destroy(Pointer thisptr);
    int SecretKey_Destroy(Pointer thisptr);

    // --- Encryptor / Decryptor ---
    int Encryptor_Create(Pointer context, Pointer publicKey, Pointer secretKey, PointerByReference encryptor);
    int Encryptor_Destroy(Pointer thisptr);
    int Encryptor_Encrypt(Pointer thisptr, Pointer plaintext, Pointer destination, Pointer poolHandle);

    int Decryptor_Create(Pointer context, Pointer secretKey, PointerByReference decryptor);
    int Decryptor_Destroy(Pointer thisptr);
    int Decryptor_Decrypt(Pointer thisptr, Pointer encrypted, Pointer destination);

    // --- Evaluator ---
    int Evaluator_Create(Pointer sealContext, PointerByReference evaluator);
    int Evaluator_Destroy(Pointer thisptr);
    int Evaluator_Add(Pointer thisptr, Pointer encrypted1, Pointer encrypted2, Pointer destination);
    int Evaluator_AddPlain(Pointer thisptr, Pointer encrypted, Pointer plain, Pointer destination);
    int Evaluator_Multiply(Pointer thisptr, Pointer encrypted1, Pointer encrypted2, Pointer destination, Pointer pool);
    int Evaluator_MultiplyPlain(Pointer thisptr, Pointer encrypted, Pointer plain, Pointer destination, Pointer pool);
    int Evaluator_Relinearize(Pointer thisptr, Pointer encrypted, Pointer relinKeys, Pointer destination, Pointer pool);
    int Evaluator_RescaleToNext(Pointer thisptr, Pointer encrypted, Pointer destination, Pointer pool);
    int Evaluator_ModSwitchToNext1(Pointer thisptr, Pointer encrypted, Pointer destination, Pointer pool);

    // --- Ciphertext / Plaintext ---
    int Ciphertext_Create1(Pointer pool, PointerByReference cipher);
    int Ciphertext_Destroy(Pointer thisptr);
    int Ciphertext_Scale(Pointer thisptr, DoubleByReference scale);
    int Ciphertext_SetScale(Pointer thisptr, double scale);
    int Ciphertext_ParmsId(Pointer thisptr, long[] parmsId);
    int Ciphertext_SaveSize(Pointer thisptr, byte comprMode, LongByReference result);
    int Ciphertext_Save(Pointer thisptr, byte[] outptr, long size, byte comprMode, LongByReference outBytes);

    int Plaintext_Create1(Pointer memoryPoolHandle, PointerByReference plainText);
    int Plaintext_Destroy(Pointer thisptr);

    // --- CKKSEncoder ---
    int CKKSEncoder_Create(Pointer context, PointerByReference ckksEncoder);
    int CKKSEncoder_Destroy(Pointer thisptr);
    int CKKSEncoder_Encode1(Pointer thisptr, long valueCount, double[] values, long[] parmsId, double scale, Pointer destination, Pointer pool);
    int CKKSEncoder_Decode1(Pointer thisptr, Pointer plain, LongByReference valueCount, double[] values, Pointer pool);
    int CKKSEncoder_SlotCount(Pointer thisptr, LongByReference slotCount);

    // --- MemoryPoolHandle ---
    int MemoryPoolHandle_Global(PointerByReference handlePtr);
    int MemoryPoolHandle_Destroy(Pointer thisptr);
}
