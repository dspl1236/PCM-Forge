# PCM 3.1 Activation Code Analysis

## Andrew's Vehicle
- VIN: WP1AE2A28GLA64179
- PCM3.1 V4.76
- HWID: PCME02XX1221
- Cayenne 958, 2016 model year, Leipzig assembly

## PagSWAct.csv Structure

29 columns, semicolon-delimited:
- Col 0: Name (test label)
- Col 1: VIN (17-char)
- Col 2: Vehicle type (E1, E2, G1, 991, etc.)
- Col 3: ENGINEERING code (16-digit hex)
- Col 4-12: Feature codes (BTH, KOMP, FB, INDMEM, SDARS, SSS, SC, TVINF, UMS)
- Col 13: Navigation code
- Col 14-24: Regional NavDB codes
- Col 25-27: HDTuner, DABTuner, OnlineServices
- Col 28: FeatureLevel

## Known VIN/Code Pairs for ENGINEERING Menu

27 pairs extracted from PagSWAct.csv (see csv file for full data).
Same VIN always produces same code (verified with WP0ZZZ97Z8L040010).
All code values < 2^63.

## Algorithm Analysis

Tested and RULED OUT:
- MD5(VIN) — no match
- SHA1(VIN) — no match
- MD5(VIN + "ENGINEERING") — no match
- MD5(VIN + column_index) — no match

The algorithm is NOT a simple public hash of the VIN.
It's likely a keyed cipher or HMAC using a secret key embedded
in the PCM firmware. The key would be in the IFS images.

## Next Steps to Crack the Algorithm

1. **Extract PCM3_IFS1.ifs and PCM3_IFS2.ifs** from the firmware ISO
   - These QNX IFS images contain the application code
   - The activation validation function is in here

2. **Find the validation function** in the extracted binaries
   - Search for references to "PagSWAct" or the column names
   - The function that reads and validates CSV entries
   - Likely computes HMAC or keyed hash of (VIN + feature_id + secret_key)

3. **Extract the secret key** from the validation function
   - Once we have the key, generating codes is trivial
   - The key is probably a static byte array in the binary

4. **Alternative: Buy one code for Andrew's VIN**
   - $30-90 from euronavmaps for engineering menu activation
   - Gives us one more data point (Andrew's VIN → known code)
   - Also gets engineering menu access for further exploration
