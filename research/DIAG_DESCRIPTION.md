# The diagnostic stack is data, not code

Written while hunting the SecurityAccess seed/key algorithm, which is the one
thing standing between us and driving the PCM ourselves — every routine behind
the lock has been proven reachable once a tester opens it (`PCM_DIAGNOSTICS.md`).

## PCM3Root was the wrong binary

The obvious starting point was `PCM3Root`, because it is the only file in either
extracted tree that contains the string `SecurityAccess`. That was a red herring
twice over.

The strings that looked promising are mostly false friends:

| string | what it actually is |
|--------|--------------------|
| `CGDTCPDSPComm::transferSeed` | **DTCP** content protection for the DSP |
| `readDummySeedFromFlash` | also DTCP |
| `UnlockCode`, `Checking UnlockCode %s` | navigation-database feature licensing |
| `processDiagnosisUnlockRequest` | a **DSI method name**, not an implementation |

`processDiagnosisUnlockRequest` resolves to a literal-pool slot at `08271AF0`,
loaded at `082717F2` — inside a long run of `(name, descriptor) -> jsr`
registrations. The paired word points into the RW data segment (`0867860C`,
stepping 0x10), so it is a method descriptor table, not a function pointer.

The genuinely diagnostic strings — `HBDiagnosisState = 0x%08X (with
SecurityAccess)` at `08247A1C`, the plain variant at `08247A26`, and
`HBDiagnosisState not initialized!` at `08247A34` — are three arms of a **state
printer**. Useful for decoding the state word later; no algorithm.

## The KWP stack lives in PCM3Reload, and it is an interpreter

`PCM3Reload` (ifs2) carries the KWP symbols that `PCM3Root` does not:
`KWP_receiveDeviceName`, `KWP_receiveStartDiagnosisSession`,
`KWP_receiveECUReset`, `KWP_receiveTransferDataExit`, `KWP_receiveUnknownRoutine`.

But it does not implement the services either. Its class list is a set of
interpreter nodes, every one carrying an `onDispatch`:

```
CRBDiagService::execute / denial / ready / response
CRBDiagCalculate::calculate / setVal      CRBDiagSelect::onDispatch
CRBDiagTable::map / getBitsFromVal        CRBDiagConst::compare
CRBDiagNextLayer::pass                    CRBDiagCollector::collect
CRBDiagFormat, CRBDiagLength, CRBDiagTimer, CRBDiagIOSub::SendToSystem
```

That is a graph walker over a diagnostic description — the ODX pattern. So the
services, including SecurityAccess, are **data**.

## diagnosis.cfg is that description

`ifs2/HBproject/diagnosis.cfg`, 150,140 bytes. Header:

```
DCLVersion = 2
version = 2 Porsche PCM3_1 PZabler OEKAP96U 28 03 2013  10 04 34
entry = Protokoll
  CommProcessor  DataProc  HBProduction  ODXCheck  Protokoll  SH4Internal  Version
```

**Format** — a stream of length-prefixed ASCII inside binary records: `u16`
little-endian length, then that many bytes. (`0e00` + `"DCLVersion = 2"` = 14.)
It is *not* UTF-16; decoding it as such yields nothing. Records around a string
look like `16 <idx> 03 07 <type> <u16 len> <string>`, with `23 00` as the
expression-node type, followed by `06 00 <operand>` entries.

**The calculation language is RPN**, stored as operator templates with `x` as
operand placeholders. 40-odd expressions are present:

```
011648   xx&x>>xx&x<<xx&x<<|'|     mask/shift/or bit assembly
00F9C4   xDx>xx<&&                 range check
01C06C   xx*xx*xx*xx*xx*xx*+++++   polynomial
015223   xx+x/x+                   linear scaling
```

`011648` is the strongest seed/key candidate on shape alone — pure mask-and-shift
assembly, which is what a 2-byte key derivation looks like — and it falls
between the `SH4Internal` markers at `006C45` and `012859`, so it is interpreted
on the SH4 rather than delegated to the CommProcessor.

**Not yet proven.** The operands live in the surrounding binary record and the
record format is only partly decoded, so the expression cannot yet be evaluated
against the four captured seed/key pairs. That evaluation is the test that would
settle it — the pairs are the ground truth we already hold.

## A false positive worth recording

Scanning for a 256-byte window containing many known service ids (`10 14 18 1A
22 27 31 32 33 3E`) reported `006600` with 9 of 10. It is **a counter table**:
`0006 000d 0002 000e 0001 0000 0006 000f 0002 0010 …` — consecutive small
integers, matching by coincidence. Same failure mode as the earlier attempt to
find CAN ids in the firmware, which matched font tables and JPEG data. Small
integers are not evidence; a dispatch table has to be confirmed structurally.

## Tooling

- `tools/firmware/sh4find.py` — locates strings in a section-header-stripped SH4
  ELF, maps file offsets to virtual addresses via PT_LOAD, and builds a complete
  PC-relative cross-reference by decoding every `mov.l/mov.w @(disp,PC)` in the
  executable segment (286,433 constant slots). Also disassembles (capstone
  `CS_ARCH_SH`) and dumps annotated literal pools. Linear disassembly dies on the
  interleaved pools, so the xref map is what makes this binary navigable.
- `tools/firmware/dclparse.py` — extracts and greps the DCL string stream.

## The description is generation-keyed, and nearly frozen

Fourteen shipped IFS2 images (`ISO Extract/PCM31*/HEADUNIT/ADR0FC0000/`) carry
only **five distinct** `diagnosis.cfg` files. They key to the software
generation, not the region — every 400-series build ships the same one:

| sha256 (12) | size | builds |
|-------------|------|--------|
| `DEE3F8BB5F87` | 150140 | ARB400, CHN400, LOW400, RDW400 — **and our extracted copy** |
| `DD9A30E611A6` | 137520 | ARB300, CHN300, CHN350, RDW300 |
| `27B31F2011A4` | 136723 | CHN200, CHN250, RDW200 |
| `17818D8E788D` | 135771 | CHN100, CHN150 |
| `1EA74B26FFC0` | 134590 | RDW100 |

Our copy is byte-identical to ARB400, so **the 3.xx and 4.xx trains share one
description** — its header still reads `28 03 2013`.

Across all five generations the calculation set is essentially frozen: 23
distinct expressions, of which **22 appear in every generation**. The only
addition in the product's life is `xx*xx*xx*xx*xx*xx*+++++`, a six-term
polynomial that arrives at gen300 — a new scaling curve, not security.

**`xx&x>>xx&x<<xx&x<<|'|` is present exactly once in every generation,
unchanged.** That is what a seed/key derivation has to look like: the dealer
tool unlocks every one of these units, so the algorithm cannot have moved.
Suggestive, not proof — the diff eliminated nothing and confirmed nothing,
because almost everything is stable.

Note the file grew 134,590 → 150,140 bytes while gaining only six strings, so
the growth is in binary records. Whatever changed between generations is
structural, not textual.

## The file is sectioned, and a flat record walk cannot parse it

`pcmexplorer/dcl.py` (in PCM-Explorer) implements what is solid so far.
`header()` and `sections()` are correct and stable across all five generations;
`scan_expressions()` finds all 49 without depending on the record model.

**`records()` does not work yet, and the way it fails is the useful part.**
Three resync strategies gave wildly different answers on the same file:

| strategy | coverage | expressions found |
|----------|----------|-------------------|
| byte-at-a-time resync | 74% | 20 |
| strict one-record lookahead | 50% | 2 |
| pad-tolerant lookahead | 66% | 15–19 |

A plain string scan reliably finds **49**. Three tunings disagreeing that badly
means the model is structurally wrong, not mis-tuned — and the first attempt is
the cautionary one, because 74% coverage looked like a working parser while
silently dropping 29 of 49 records.

The reason is almost certainly that the file is **sectioned rather than flat**.
The header declares named entries and those names recur through the body as
boundaries:

```
00006D..0000C8  the declaration list
00694E  CommProcessor      006C1A  HBProduction     006C45  SH4Internal
012859  SH4Internal        015FBD  SH4Internal      016162  HBProduction
0229B3  SH4Internal        02308B  Version          0245FB  ODXCheck
0246E9  DataProc
```

Sections plausibly carry their own framing, so no single walk covers the file.

Placing the expressions in that map is worth having on its own:

- `xx&x>>xx&x<<xx&x<<|'|` — our seed/key candidate — sits at `01164A`, inside an
  **SH4Internal** section. Interpreted on the SH4, not handed to the
  CommProcessor, so the algorithm is in reach of these images.
- `xx*xx*xx*xx*xx*xx*+++++` — the only expression added in the product's life —
  is at `01C06E` in **HBProduction**. A manufacturing calibration curve, which
  is further reason to stop treating it as interesting.

## There are TWO KWP stacks, and only one faces the tester

Hunting the `0x27` handler in `PCM3Reload` turned up a complete, hand-written
KWP service dispatcher — for the **wrong channel**.

The parser is at `08122A90`, called from `08123370`, and traces with
`diagparser: msg={%02X,%02X,%02X` / `match sid=%02X`. It walks a service table
of **12-byte entries**, each pointing to a descriptor whose byte 0 is a length
and byte 1 onward is the SID pattern, matched by a routine at `0804A6E4`. On a
hit it dispatches through a computed branch:

```
0812338A  add   #-25,r7        ; index = sid - 25
0812338C  cmp/hi #26,r7        ; reject > 26
08123396  mova  0x81233c0,r0   ; 16-bit offset table, 27 entries
0812339C  braf  r1             ; target = 0x081233A0 + offset
```

Dedicated handlers exist for `0x20 0x21 0x22 0x23 0x24 0x2A 0x2B 0x2C 0x2D 0x2E
0x31 0x32 0x33`. **`0x27` shares target `08123898` with `0x1A 0x1C 0x1D 0x1E
0x25 0x26 0x28 0x29 0x2F 0x30`** — and that target prints
`received unknown command:%02x` and returns.

It is the **IOC software-download link**, not the CAN tester. Its string
neighbourhood is unambiguous: `negative IPC response on TransferData from IOC`,
`SWDL ERROR`, `EEPROM1`, `IBOC_FPGA`, `IBOC_SW`, `ROUTINGTABLE`, `MAINAPPL`, and
the `KWP_receive*` symbols belong to `CHBJobIOCBase` / `CHBJobIOCReset`. Here
the PCM is a KWP *client* driving an internal microcontroller.

So the architecture is:

| channel | stack | where |
|---------|-------|-------|
| PCM -> IOC, flash/SWDL | hand-written dispatcher, 27-entry jump table | `PCM3Reload` @ `08122A90` |
| tester -> PCM on 773/7DD | `CRBDiag*` interpreter over `diagnosis.cfg` | description-driven |

`1A 9F` answers real data on the bench yet is "unknown" to this dispatcher,
which on its own proves the tester-facing services do not come through here.

**Consequence: SecurityAccess for the tester is in the CRBDiag path**, either as
description data or inside a `CRBDiag*` method. It is not a hand-written service
handler, so there is no `0x27` function to find by this route.

Also worth recording as false friends, since both cost time: `PCM3Root`'s
`transferSeed` / `readDummySeedFromFlash` are **DTCP** content protection, and
`PCM3Reload`'s `miInternal_Unlock` / `UnlockCode` / `request_UnlockPhone` are
**SIM PIN/PUK** telephony. Neither has anything to do with KWP SecurityAccess.

## The calculate operators, from the code

`CRBDiagCalculate::calculate` in `PCM3Reload`, reached via its trace strings at
`0952AF44` (loaders `08907614`, `08907696`, `089076A4`, `08907776`).

### Complete operator inventory

Stored as plain strings at `0952AE2C`, and there are 26:

```
Get  SetVal2  Set  Add  SubRev  Sub  DivRev  Div  Mul  Scale
Not  And  Or  Xor  Nand  Nor  Nxor
RotateLeft8  RotateRight8  RotateLeft16  RotateRight16
RotateLeft32 RotateRight32  ShiftLeft  ShiftRight  Random
```

Neighbouring trace strings decode the RPN template characters that had no
obvious meaning:

```
Activate Denial (D)      Deactivate Denial (d)     -> the D in "xDx="
m+ %d   M+ %d   MR %d   Mem = %d   M %d            -> the memory digraphs
round > %d  between %d and %d                      -> r> and r<
%d (invers)                                        -> i- and i/
absolut %d      Average
%d is inside %d, %d      %d is outside %d, %d
```

### Dispatch

```
08907622  mov   r10,r5        ; operator code
08907624  add   #-3,r5
08907626  mov   #21,r1
08907628  cmp/hi r1,r5        ; reject >21, so valid codes are 3..24
08907632  mova  0x890764c,r0  ; 22-entry table of u16 offsets
08907638  braf  r1            ; target = 0x0890763C + offset
```

Handler addresses, in table order (codes 3..24):

```
08907678 0890767E 08907686 089076B8 0890768C 0890769C 089076C0 0890770A
089076E4 089076EA 089076F0 089076F8 089076FE 08907706 08907720 0890772C
08907738 08907748 08907754 08907760 0890770E 08907716
```

### The operator table, verified from the handlers

All 22 read from their own code rather than taken from a name list. Notation:
**`a`** is the stored operand at `@(16,r9)`, **`b`** is the incoming value in
`r8`, result in `r2`.

| code | handler | behaviour | operator |
|------|---------|-----------|----------|
| 3 | `08907678` | `a + b` | Add |
| 4 | `0890767E` | `b - a` | Sub |
| 5 | `08907686` | `a - b` | Sub, reversed |
| 6 | `089076B8` | `mul.l` / `sts macl` — `a * b` | **Mul** |
| 7 | `0890768C` | divide, **divisor `a`**, zero-checked | **Div** |
| 8 | `0890769C` | divide, **divisor `b`**, zero-checked | **DivRev** |
| 9 | `089076C0` | clamp `b` to `[@(28,r9), @(32,r9)]`, then scale via `@(36,r9)`/`@(40,r9)` | Scale |
| 10 | `0890770A` | `~b` | Not |
| 11 | `089076E4` | `a & b` | And |
| 12 | `089076EA` | `a \| b` | Or |
| 13 | `089076F0` | `b ^ a` | Xor |
| 14 | `089076F8` | `~(a & b)` | Nand |
| 15 | `089076FE` | `~(a \| b)` | Nor |
| 16 | `08907706` | `~(a ^ b)` | Nxor |
| 17 | `08907720` | rotate width 8, helper `08907508` | RotateLeft8 |
| 18 | `0890772C` | rotate width 8, helper `08907536` | RotateRight8 |
| 19 | `08907738` | rotate width 16, helper `08907508` | RotateLeft16 |
| 20 | `08907748` | rotate width 16, helper `08907536` | RotateRight16 |
| 21 | `08907754` | rotate width 32, helper `08907508` | RotateLeft32 |
| 22 | `08907760` | rotate width 32, helper `08907536` | RotateRight32 |
| 23 | `0890770E` | `shld` positive — `b << a` | ShiftLeft |
| 24 | `08907716` | `neg` then `shld` — `b >> a` | ShiftRight |

The rotate helpers both build a width mask `(1 << width) - 1` then combine two
shifts:

```
08907508   (v << n) & mask | (v >> (width - n))    rotate LEFT
08907536   (v << (width - n)) & mask | (v >> n)    rotate RIGHT
```

which independently confirms the Left/Right alternation the name lists imply for
17–22.

### Neither name table is the dispatch enum

Codes 9 through 24 agree with both name lists. **Codes 4–8 do not:**

| code | verified | `008C72E8` says | `008C7424` says |
|------|----------|-----------------|-----------------|
| 6 | **Mul** (`mul.l`) | DivRev | Div |
| 7 | **Div** (divisor `a`) | Div | Mul |
| 8 | **DivRev** (divisor `b`) | Mul | Scale |

`008C7424` also has no `DivRev` at all, so it cannot be the enum for a dispatch
that plainly has two division handlers. Take the verified column; the name
tables are for display or parsing, not dispatch.

### The template parser — located, not yet decoded

`calculate()` receives an opcode in `r10` and never sees the template string, so
a separate parser turns characters into opcodes. It is at **`08906280`–
`08906C40`** in `PCM3Reload`, found by scanning the executable segment for
`cmp/eq #imm,R0` (`0x88nn`) against operator characters and clustering the hits
— two dense clusters at `08906300` and `0890639C`.

It is a **comparison tree**, not a table: range splits (`mov #45,r1 ; cmp/hi`)
narrowing to equality tests, each match branching to its own handler. Handler
targets seen include `08906442`, `08906458`, `08906550`, `089065B8`, `089065DE`,
`08906616`, `089066BC`, `08906790`, `089067B6`, `089068E0`, `08906A00`,
`08906B54`.

**Do not extract this with a naive scan.** SH4 puts the next `cmp/eq` in the
*delay slot* of the previous test's branch, so pairing each comparison with the
following branch attributes it to the wrong character — a first pass produced
adjacent pairs sharing one target (`m` and `<` both to `089066BC`), which is the
artifact, not the format.

That pass also missed characters that demonstrably occur in real templates:
`=` (in `xDx=`), `'` (in `xx*xx*xx*|'|`) and `R` (in `MRx+`). So it is
incomplete as well as mis-paired. A correct extraction has to follow the tree
with delay-slot semantics honoured.

### The template evaluator — it is a stack machine, not a compiler

**Correction to an earlier assumption here.** The template parser does not
translate characters into opcodes for `calculate()`. It **evaluates directly**:
each character's handler performs its own arithmetic inline.

```
'+'  mov.l @r9,r1 ; mov.l @(4,r9),r2 ; add r2,r1
'*'  mov.l @r9,r2 ; mov.l @(4,r9),r1 ; mul.l r1,r2 ; sts macl,r3
```

Stack convention: **`@r9` is the top of stack, `@(4,r9)` the next entry, `r12`
the depth** (every handler opens with `cmp/gt r1,r12` as an underflow guard).
Results are written back to `@r9`.

So there are **two independent evaluation mechanisms**: this one for RPN
template strings, and `CRBDiagCalculate::calculate` with its 22 opcodes for
dataflow-graph nodes. They implement overlapping operations separately, and
conflating them would misread both.

### The character dispatch, by interpretation

Tree entry is `089062DC` with the character already in `r0`. It is
compiler-generated binary search that **reuses branch delay slots to hold the
next comparison**, so textual pairing attributes tests to the wrong character.
Recovered instead by interpreting the tree per character with delay-slot
semantics honoured:

| char | handler | char | handler | char | handler |
|------|---------|------|---------|------|---------|
| `x` | `0890640E` | `=` | `089065DE` | `d` | `08906A00` |
| `+` | `08906442` | `>` | `08906616` | `a` | `08906A16` |
| `*` | `08906458` | `<` | `089066BC` | `A` | `08906A38` |
| `-` | `08906474` | `?` | `0890676E` | `m` | `08906B20` |
| `/` | `0890648A` | `^` | `08906790` | `M` | `08906B54` |
| `&` | `089064E8` | `!` | `089067B6` | | |
| `\|` | `08906550` | `~` | `089067C8` | | |
| `%` | `089065B8` | `i` | `08906828` | | |
| `o` | `089068E0` | `r` | `0890692E` | `D` | `089069EA` |

Anything else falls to `08906C1A` (reject). Twenty-four characters, each with
its own handler — no sharing, contrary to what a naive scan reported.

### Operations verified from the handlers

```
+   add r2,r1                        add
-   sub r2,r1                        subtract
*   mul.l r1,r2 ; sts macl,r3        multiply
^   xor r2,r1                        xor
~   not r1,r1                        bitwise not
!   movt r7                          logical (T-bit to value)
D   mov.l r1,@(56,r2)                set Denial flag at object+56
d   mov.l r7,@(56,r0)                clear Denial flag
m   mov.l r7,@(r0,r14)               memory store
/ % i r                              call helper routines
```

`D`/`d` writing to `+56` corroborates the `Activate Denial (D)` /
`Deactivate Denial (d)` trace strings.

### Digraphs are handled by peeking the next character

Confirmed in the handlers themselves — each two-character token is a `cmp/eq`
against the following character inside the first character's handler:

```
'&' peeks '&'   -> &&        '>' peeks '=' and '>'  -> >= and >>
'|' peeks '|'   -> ||        '<' peeks '<' and '='  -> << and <=
```

This is why `R` and `'` do not appear in the dispatch table: `R` is consumed
inside the `M` handler as the `MR` token, and `'` likewise belongs to an
enclosing form rather than being an operator in its own right.

### Still open

`calculate()` receives an opcode in `r10` — it never sees the template string.
So the mapping from the RPN characters (`&`, `|`, `<<`, `D`, `MR`, `i-`, `r>` …)
to these codes happens in a parser elsewhere, and **that is still unfound**.
Without it, `dcl.py`'s `evaluate()` cannot be trusted: the operations are now
known exactly, but which character selects which is not.

### Earlier verification notes

```
08907678  add  r8,r2                      a + b
0890767E  mov r8,r2 ; sub r1,r2           b - a
08907686  mov.l @(16,r9),r2 ; sub r8,r2   a - b
0890768C  tst r5,r5 -> trace, jsr 89077B8 division, divisor = a
0890769C  tst r8,r8 -> trace, jsr 89077B8 division, divisor = b
```

The two zero-checking handlers share one division helper with the operands
swapped — `Div` and `DivRev`, corroborated by the two distinct
`calculate:eDiv`/`eDivRev <div through 0>` strings.

**They occupy table indices 4 and 5.** In the name table at `008C72E8` those
indices are `Div`/`Mul`; in the one at `008C7424` they are `Mul`/`Scale`.
**Neither ordering matches the dispatch**, so the two name tables are not the
enum `calculate()` uses.

Do not build an operator map from either list. Identify each operator by
reading its handler — the remaining 17 are addressed above and the method is
demonstrated. Assuming a name table's order here would produce a confident and
wrong evaluator, which is precisely the failure this file already records once.

## Next

1. Finish the DCL record format far enough to read `011648`'s operands, then
   evaluate it against the four seed/key pairs. Pass or fail is decisive.
2. Diff against `spyderdocPCM100gb.img` — a 991/9633 unit, different vehicle line
   and a later build. If its `diagnosis.cfg` carries the same expression, that
   argues the algorithm is platform-wide; if it differs, the difference localises
   it. Requires pulling ifs2 off the image and inflating it (`lzo1x`).
3. Rule the CommProcessor in or out. `diagnosis.cfg` partitions work between
   `SH4Internal` and `CommProcessor` domains; if SecurityAccess turns out to be
   CommProcessor-side, the algorithm is in a separate MCU's firmware that these
   images may not contain at all.
