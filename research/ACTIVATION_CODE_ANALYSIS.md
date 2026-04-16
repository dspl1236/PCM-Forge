# PCM 3.1 Activation Code Analysis

> **This document contains early research notes. The algorithm has been fully cracked.**
> See [ALGORITHM_CRACKED.md](ALGORITHM_CRACKED.md) for the complete solution.

## Target Vehicle
- VIN: WP1AE2A28GLA64179
- PCM3.1 V4.76, Serial BE9632G5671071
- Cayenne 958, 2016 model year

## PagSWAct.csv

29 columns, semicolon-delimited, containing 27 VIN/code pairs across 11 unique VINs. Located at `research/firmware/PagSWAct.csv`. This file was the starting point for the algorithm analysis — every pair has been verified against the cracked RSA algorithm with 100% accuracy.

## Algorithm Summary

**64-bit RSA modular exponentiation** with interleaved plaintext construction. Not MD5, SHA, TEA, or any standard hash. See [ALGORITHM_CRACKED.md](ALGORITHM_CRACKED.md) for full details including RSA parameters, VIN mapping function, and Python implementation.
