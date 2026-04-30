# PCM 3.1 Activation Code Algorithm — FULLY CRACKED

## RSA Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Modulus (n) | `0x69f39c927ef94985` | 1831263461 × 4169044001 |
| Public exponent (e) | `0x4c1c5eeaf397c0b3` | Verification |
| **Private exponent (d)** | **`0x5483975015d0287b`** | Code generation |

## Complete Algorithm

### Step 1: VIN → VIN_number

Function `FUN_08240738` computes a weighted sum from specific VIN positions:
- Positions used: **[7, 9, 11, 12, 13, 14, 15, 16]** (skip check digit 8 and plant 10)
- Character values: **digits = face value** (0-9), **lowercase letters = ASCII % 10**
- Weighted sum: reverse order, base-10 with **16-bit weight overflow**

```python
def vin_to_number(vin):
    vl = vin.lower()
    positions = [7, 9, 11, 12, 13, 14, 15, 16]
    result = 0
    weight = 10  # Start at 10 (null byte consumed weight=1)
    for pos in reversed(positions):
        c = vl[pos]
        b = int(c) if c.isdigit() else (ord(c) % 10 if c.islower() else 0)
        result = (result + b * weight) & 0xFFFFFFFF
        weight = (weight * 10) & 0xFFFF
    return result
```

### Step 2: Plaintext Construction (INTERLEAVED!)

The plaintext is **NOT** a simple concatenation. It's formed by **interleaving** two
8-character hex strings character-by-character:

```python
def interleave(feat_hex, vin_hex):
    return ''.join(feat_hex[i] + vin_hex[i] for i in range(8))
```

Where:
- `feat_hex` = feature-specific 8-char hex constant
- `vin_hex` = `f"{vin_to_number(vin):08x}"`

### Step 3: RSA Encryption

```python
plaintext = int(interleave(feat_hex, vin_hex), 16)
activation_code = pow(plaintext, d, n)
code_string = f"{activation_code:016x}"
```

### Feature Hex Constants

| Feature | feat_hex | Notes |
|---------|----------|-------|
| ENGINEERING | `010b0000` | Engineering menu, diagnostics |
| BTH | `010a0000` | Bluetooth telephony |
| KOMP | `01060000` | Kompass (compass display) |

### Key Location in Firmware

Literal pool at PCM3Root:
- `0x082270b4` → `"69f39c927ef94985"` (modulus)
- `0x082270b8` → `"4c1c5eeaf397c0b3"` (exponent)
- `CPPorscheEncrypter::verify` at `0x08240df0` (392 bytes)
- VIN processing at `FUN_08240738` (370 bytes)
- Modular exponentiation at `FUN_082405a0` (186 bytes)

### Verification

All 27 known VIN/code pairs from PagSWAct.csv verified with 100% accuracy:
- 11 unique VINs × ENGINEERING codes → all regenerated exactly
- Cross-feature consistency confirmed (same VIN_number across features)
- Roundtrip verification: generate → verify → match
