# MIB2 FEC / Data / Metainfo public keys

Per-OEM RSA **public** keys extracted from the MIB2 High firmware
(`efs-system/backup/Keys/`). Three trust chains, one set per OEM
(AU=Audi, BY=Bentley, **PO=Porsche**, SE=Seat, SK=Skoda, VW, + generic `MIB-High`):

- `FECKey/`  — verifies **FSC** (FreischaltCode) feature-unlock codes
- `DataKey/` — verifies **content/data** (e.g. nav map DB) signatures
- `MetainfoKey/` — verifies the **software-update metainfo** signature

Each `*_public_signed.bin` is 288 bytes:

```
[ modulus n : 128 bytes  (RSA-1024, big-endian) ]
[ exponent  :  32 bytes  (big-endian, == 3)      ]
[ signature : 128 bytes  (the blob signed by a VAG root key) ]
```

These are **public** halves only (not factorable in practice), and verification on the unit
uses OpenSSL with strict PKCS#1 v1.5 — so FSCs are not forgeable from these. Published here
so others can analyse the trust structure. Format details: [`../docs/FILE_FORMATS.md`](../docs/FILE_FORMATS.md) §5.
