# PCM 3.1 Activation Code Algorithm — CRACKED

## Algorithm: RSA Modular Exponentiation

The Porsche PCM 3.1 software activation system uses a **64-bit RSA** scheme
implemented in the C++ class `CPPorscheEncrypter`.

### RSA Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Modulus (n) | `0x69f39c927ef94985` | 1831263461 × 4169044001 |
| Public exponent (e) | `0x4c1c5eeaf397c0b3` | Used for verification |
| **Private exponent (d)** | **`0x5483975015d0287b`** | **COMPUTED by factoring n** |

### How It Works

**Verification** (PCM firmware does this):
```
plaintext = activation_code ^ e mod n
if plaintext == expected_value: VALID
```

**Code Generation** (what we can now do):
```
activation_code = plaintext ^ d mod n
```

### Plaintext Structure (for ENGINEERING/BTH/KOMP)

```
[SWID:16bit][FeatureID:16bit][VIN_number:32bit]
```

- SWID: Always `0x0010` for standard features
- FeatureID: Varies by feature (0x00bc=ENGINEERING, 0x00ac=BTH, 0x006c=KOMP)
- VIN_number: 32-bit value derived from VIN by `FUN_08240738`

### Code Path in PCM3Root

```
CPPorscheEncrypter::verify(VIN, unlockCode, featureInfo)
  → FUN_08240738(VIN) → VIN_number
  → sprintf("%04x%04x", SWID, SubID) + sprintf("%08x", VIN_number) → plaintext
  → FUN_08240cdc(keyStruct, unlockCode)
    → FUN_082405a0(code, exponent, modulus, result) [MODULAR EXPONENTIATION]
  → FUN_08240906(result, expected) [STRING COMPARISON]
  → return match
```

### Key Location in Firmware

The RSA key strings are stored in a literal pool at:
- `0x082270b4` → `"69f39c927ef94985"` (modulus as hex string)
- `0x082270b8` → `"4c1c5eeaf397c0b3"` (exponent as hex string)

Initialized by `FUN_0824067c` (key init), called from the unlock
checking function at `FUN_08226f80`.

### Verification Results

All 27 known VIN/code pairs from PagSWAct.csv verified:
- `pow(code, e, n)` produces consistent plaintext structures
- `pow(plaintext, d, n)` regenerates the exact activation code
- VIN_number is identical across features for the same VIN
- 100% roundtrip verification success

### Python Code Generator

```python
n = 0x69f39c927ef94985  # modulus
d = 0x5483975015d0287b  # private exponent

def generate_code(plaintext):
    """Generate activation code from plaintext value"""
    code = pow(plaintext, d, n)
    return f"{code:016x}"

# Example: generate ENGINEERING code for a given VIN
# plaintext = 0x001000bc0f050e04  (for VIN WP0ZZZ97Z8L040010)
# code = generate_code(plaintext)
# Result: "0e8e0b97ec875242" ← matches PagSWAct.csv!
```

### Remaining Work

1. **VIN → VIN_number mapping**: Replicate FUN_08240738 in Python
2. **Feature ID table**: Map all feature names to their P2 values
3. **P2 computation**: Determine if P2 is purely feature-dependent or VIN+feature
4. **Build web tool**: VIN input → all activation codes output

## VIN → VIN_number Mapping (Partial)

### Key Findings from Differential Analysis

By comparing VINs that differ at only one position:

| Position | Weight | Evidence |
|----------|--------|----------|
| 16 | 170 | WP0ZZZ99ZCS110100 vs 110103: diff=510, 3 chars, 170/char |
| 9 | 151,455,744 | WP1ZZZ92ZBLA20006 vs ZCLA20006: diff=0x09060800 |

### Character Value Conversion
- Digits use **face value** (0→0, 1→1, ..., 9→9), NOT ASCII % 10
- Letters use **ASCII - 0x30** (a→49, b→50, ..., z→74)
- Or possibly **hex value** (a→10, b→11, ..., f→15, others→larger)

### Positions Used
The function `FUN_08240738` processes 8 VIN positions from the stack:
- VIN[7], VIN[9], VIN[11], VIN[12], VIN[13], VIN[14], VIN[15], VIN[16]
- Positions 8 (check digit) and 10 (plant code) are SKIPPED

### Computed VIN_num Values (21 unique VINs)
All computed from `pow(activation_code, e, n) & 0xFFFFFFFF`:

| VIN | VIN_num | P2 (feature) |
|-----|---------|--------------|
| WP0ZZZ97Z8L040010 | 0x0f050e04 | 0x00bc |
| WP0LLLL3L3L300815 | 0x040d0106 | 0x00b5 |
| WP1ZZZ9PZ6LA46923 | 0x04010a0e | 0x00ba |
| ... (20 more in PagSWAct.csv) |

### Current Status
The RSA algorithm is fully cracked. The VIN→plaintext mapping
requires either:
1. Completing the weight table for all 8 positions (solvable
   with enough differential VIN pairs)
2. Running the actual SH4 function with QEMU + QNX sysroot
3. Using one known activation code for a target VIN to extract
   its VIN_num, then generating all other feature codes
