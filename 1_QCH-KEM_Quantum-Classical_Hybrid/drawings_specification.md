# Patent Drawing Specifications
# Quantum-Classical Hybrid Key Encapsulation Mechanism (QCH-KEM)

---

## Drawing Requirements

- **Format**: Black and white line drawings (no grayscale, no color)
- **Resolution**: Minimum 300 DPI
- **Paper Size**: A4 (210mm × 297mm) or US Letter (8.5" × 11")
- **Margins**: At least 25mm on all sides
- **Line Width**: 0.25mm minimum for all lines
- **Reference Numerals**: Arabic numerals, consistent across all figures
- **Font**: Arial or similar sans-serif, minimum 8pt

---

## Figure 1: Overall System Architecture Diagram

### Description
Shows the complete QCH-KEM system architecture with QRNG, PQC, QKD modules, synchronization controller, and key combination module.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 100 | System Overview | Complete QCH-KEM system |
| 110 | QRNG Module | Quantum Random Number Generator |
| 111 | Quantum Entropy Source | Physical quantum randomness generator |
| 112 | Entropy Extractor | Randomness conditioning unit |
| 113 | Health Monitor | Continuous statistical testing |
| 114 | QRNG Output Buffer | Cached random bits |
| 120 | PQC/KEM Module | Lattice-based encryption unit |
| 121 | ML-KEM-512 Variant | Low security parameter set |
| 122 | ML-KEM-768 Variant | Medium security parameter set |
| 123 | ML-KEM-1024 Variant | High security parameter set |
| 124 | Parameter Selector | Dynamic variant selection |
| 130 | QKD Module | Quantum Key Distribution unit |
| 131 | Quantum Transmitter | Quantum state preparation |
| 132 | Quantum Receiver | Quantum state measurement |
| 133 | Classical Post-Processing | Sifting and error correction |
| 134 | QKD Key Buffer | Secure key material storage |
| 135 | Key-Rate Monitor | Real-time rate measurement |
| 140 | Synchronization Controller | Central coordination unit |
| 141 | Rate Analysis Unit | QKD rate processing |
| 142 | Parameter Adjustment Logic | Security level computation |
| 143 | Fallback Manager | Graceful degradation control |
| 144 | State Machine | System state tracking |
| 150 | Key Combination Module | Final key derivation |
| 151 | Key Aggregator | Combines K_PQC and K_QKD |
| 152 | KDF Unit | HKDF-based key derivation |
| 153 | Key Confirmation | MAC-based verification |
| 160 | Communication Interface | Network I/O |
| 161 | Secure Channel Output | Protected session key |
| 170 | Data Flow Arrow | Information transfer |
| 171 | Control Flow Arrow | Command/control signal |

### Layout Specification

```
+------------------------------------------------------------------+
|  [Height: 220mm, Width: 170mm]                                   |
|                                                                  |
|  TOP ROW (60mm): Input Modules                                   |
|  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  |
|  │  QRNG Module    │  │  PQC/KEM Module │  │   QKD Module    │  |
|  │     [110]       │  │     [120]       │  │     [130]       │  |
|  │ ┌─────────────┐ │  │ ┌─────────────┐ │  │ ┌─────────────┐ │  |
|  │ │Entropy[111]│ │  │ │ML-KEM [121] │ │  │ │Tx/Rx [131/2]│ │  |
|  │ └──────┬──────┘ │  │ │      [122] │ │  │ └──────┬──────┘ │  |
|  │ ┌──────▼──────┐ │  │ │      [123] │ │  │ ┌──────▼──────┐ │  |
|  │ │Extract[112]│ │  │ └──────┬──────┘ │  │ │Post-Pr[133]│ │  |
|  │ └──────┬──────┘ │  │ ┌──────▼──────┐ │  │ └──────┬──────┘ │  |
|  │ ┌──────▼──────┐ │  │ │Select [124]│ │  │ ┌──────▼──────┐ │  |
|  │ │Health [113]│ │  │ └─────────────┘ │  │ │Buffer [134]│ │  |
|  │ └──────┬──────┘ │  │                 │  │ └──────┬──────┘ │  |
|  │ ┌──────▼──────┐ │  │                 │  │ ┌──────▼──────┐ │  |
|  │ │Buffer [114]│ │  │                 │  │ │Rate   [135]│ │  |
|  │ └──────┬──────┘ │  │                 │  │ └──────┬──────┘ │  |
|  └────────┼────────┘  └────────┼────────┘  └────────┼────────┘  |
|           │                    │                    │            |
|           │[170]               │[170]               │[171]       |
|           ▼                    ▼                    ▼            |
|  MIDDLE (60mm): Synchronization Controller                       |
|  ┌──────────────────────────────────────────────────────────┐   |
|  │           Synchronization Controller [140]                │   |
|  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────┐ │   |
|  │  │Rate    [141]│ │Adjust [142]│ │Fallback[143]│ │State│ │   |
|  │  │Analysis   │ │Logic      │ │Manager    │ │[144]│ │   |
|  │  └────────────┘ └────────────┘ └────────────┘ └────────┘ │   |
|  └──────────────────────────────────────────────────────────┘   |
|                              │                                   |
|                              │[170]                              |
|                              ▼                                   |
|  BOTTOM (50mm): Key Combination and Output                       |
|  ┌──────────────────────────────────────────────────────────┐   |
|  │           Key Combination Module [150]                    │   |
|  │  ┌────────────┐   ┌────────────┐   ┌────────────┐        │   |
|  │  │Aggregator  │──▶│ KDF Unit   │──▶│Key Confirm │        │   |
|  │  │   [151]    │   │   [152]    │   │   [153]    │        │   |
|  │  └────────────┘   └────────────┘   └────────────┘        │   |
|  └──────────────────────────────────────────────────────────┘   |
|                              │                                   |
|                              ▼                                   |
|  ┌──────────────────────────────────────────────────────────┐   |
|  │           Secure Channel Output [161]                     │   |
|  └──────────────────────────────────────────────────────────┘   |
|                                                                  |
+------------------------------------------------------------------+
```

---

## Figure 2: Dynamic Parameter Adjustment Flowchart

### Description
Flowchart showing how the synchronization controller adjusts PQC parameters based on QKD key-rate monitoring.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 200 | Process Start | Algorithm entry point |
| 210 | QKD Rate Input | Receive current key-rate |
| 220 | Smoothing Filter | Apply EMA to rate |
| 230 | Security Calculation | Compute QKD security contribution |
| 240 | Gap Analysis | Calculate security gap |
| 250 | Decision: Gap > 0? | Check if PQC adjustment needed |
| 260 | Increase PQC Level | Select higher security variant |
| 270 | Decision: Gap < 0? | Check for optimization opportunity |
| 280 | Decrease PQC Level | Select lower security variant |
| 290 | Apply New Parameters | Update PQC module |
| 295 | Log Change | Record parameter adjustment |
| 299 | Process End | Return to monitoring |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 250mm, Width: 150mm]                           |
|                                                          |
|                    ┌──────────────┐                      |
|                    │  Start [200] │                      |
|                    └──────┬───────┘                      |
|                           │                              |
|                           ▼                              |
|                    ┌──────────────┐                      |
|                    │ QKD Rate     │                      |
|                    │ Input [210]  │                      |
|                    └──────┬───────┘                      |
|                           │                              |
|                           ▼                              |
|                    ┌──────────────┐                      |
|                    │ Smoothing    │                      |
|                    │ Filter [220] │                      |
|                    └──────┬───────┘                      |
|                           │                              |
|                           ▼                              |
|                    ┌──────────────┐                      |
|                    │ Calculate    │                      |
|                    │ QKD Security │                      |
|                    │ [230]        │                      |
|                    └──────┬───────┘                      |
|                           │                              |
|                           ▼                              |
|                    ┌──────────────┐                      |
|                    │ Compute Gap  │                      |
|                    │ [240]        │                      |
|                    └──────┬───────┘                      |
|                           │                              |
|                           ▼                              |
|                    ◇──────────────◇                      |
|                   ╱   Gap > 0?    ╲                     |
|                  ╱     [250]       ╲                    |
|                 ◇──────────────────◇                    |
|                 │Yes              │No                   |
|                 ▼                 │                      |
|          ┌──────────────┐        │                      |
|          │ Increase PQC │        │                      |
|          │ Level [260]  │        │                      |
|          └──────┬───────┘        │                      |
|                 │                │                      |
|                 │                ▼                      |
|                 │        ◇──────────────◇               |
|                 │       ╱   Gap < -Δ?   ╲              |
|                 │      ╱     [270]       ╲             |
|                 │     ◇──────────────────◇             |
|                 │     │Yes              │No            |
|                 │     ▼                 │              |
|                 │ ┌──────────────┐      │              |
|                 │ │ Decrease PQC │      │              |
|                 │ │ Level [280]  │      │              |
|                 │ └──────┬───────┘      │              |
|                 │        │              │              |
|                 └───────►│◄─────────────┘              |
|                          │                             |
|                          ▼                             |
|                   ┌──────────────┐                     |
|                   │ Apply Params │                     |
|                   │ [290]        │                     |
|                   └──────┬───────┘                     |
|                          │                             |
|                          ▼                             |
|                   ┌──────────────┐                     |
|                   │ Log Change   │                     |
|                   │ [295]        │                     |
|                   └──────┬───────┘                     |
|                          │                             |
|                          ▼                             |
|                   ┌──────────────┐                     |
|                   │  End [299]   │                     |
|                   └──────────────┘                     |
|                                                        |
+--------------------------------------------------------+
```

---

## Figure 3: Multi-Layered Seed Generation Process

### Description
Diagram showing how QRNG output is cryptographically combined with QKD-derived material to produce seeds for PQC.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 300 | Process Overview | Seed generation flow |
| 310 | QRNG Raw Output | Quantum entropy bits |
| 320 | Entropy Conditioning | Hash-based extraction |
| 330 | QKD Key Material | Physics-based key bits |
| 340 | Concatenation | Combine entropy sources |
| 350 | KDF Processing | Derive uniform seed |
| 360 | Seed Output | Final seed for PQC |
| 370 | Entropy Flow | Data path |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 150mm, Width: 160mm]                           |
|                                                          |
|  ┌─────────────────────┐     ┌─────────────────────┐    |
|  │   QRNG Raw Output   │     │  QKD Key Material   │    |
|  │       [310]         │     │       [330]         │    |
|  │  ┌───────────────┐  │     │  ┌───────────────┐  │    |
|  │  │ Quantum Bits  │  │     │  │ Secure Key    │  │    |
|  │  │ (High entropy)│  │     │  │ (IT-Secure)   │  │    |
|  │  └───────┬───────┘  │     │  └───────┬───────┘  │    |
|  └──────────┼──────────┘     └──────────┼──────────┘    |
|             │[370]                      │[370]          |
|             ▼                           │               |
|  ┌─────────────────────┐               │               |
|  │ Entropy Conditioning│               │               |
|  │       [320]         │               │               |
|  │  SHAKE-256 Extract  │               │               |
|  └──────────┬──────────┘               │               |
|             │                           │               |
|             └────────────┬──────────────┘               |
|                          │                              |
|                          ▼                              |
|              ┌─────────────────────┐                    |
|              │   Concatenation     │                    |
|              │       [340]         │                    |
|              │  QRNG || QKD || ctx │                    |
|              └──────────┬──────────┘                    |
|                         │                               |
|                         ▼                               |
|              ┌─────────────────────┐                    |
|              │   KDF Processing    │                    |
|              │       [350]         │                    |
|              │  HKDF-Expand(...)   │                    |
|              └──────────┬──────────┘                    |
|                         │                               |
|                         ▼                               |
|              ┌─────────────────────┐                    |
|              │    Seed Output      │                    |
|              │       [360]         │                    |
|              │  256-bit PQC Seed   │                    |
|              └─────────────────────┘                    |
|                                                         |
+----------------------------------------------------------+
```

---

## Figure 4: Fail-Safe Fallback Protocol State Machine

### Description
State diagram showing system behavior when QKD hardware is bypassed, disrupted, or compromised.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 400 | State Machine Overview | Fallback states |
| 410 | NORMAL State | Full QKD + PQC operation |
| 420 | DEGRADED State | Reduced QKD, enhanced PQC |
| 430 | FALLBACK State | PQC-only mode |
| 440 | RECOVERY State | QKD restoration testing |
| 450 | Transition: Rate Drop | QKD rate below threshold |
| 460 | Transition: QKD Fail | Complete QKD failure |
| 470 | Transition: QKD Restore | QKD service resumed |
| 480 | Transition: Tests Pass | Recovery verification ok |
| 490 | Transition: Tests Fail | Recovery verification fail |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 180mm, Width: 170mm]                           |
|                                                          |
|                    ┌─────────────────┐                   |
|                    │  NORMAL [410]   │                   |
|                    │   QKD + PQC     │                   |
|                    │  (Full security)│◄──────────┐       |
|                    └────────┬────────┘           │       |
|                             │                    │       |
|              Rate < T₁ [450]│                    │       |
|                             ▼                    │       |
|                    ┌─────────────────┐           │       |
|                    │ DEGRADED [420]  │           │       |
|                    │  Low QKD Rate   │           │       |
|                    │ Enhanced PQC    │           │       |
|                    └────────┬────────┘           │       |
|                             │                    │       |
|             QKD Fail [460]  │                    │       |
|                             ▼                    │       |
|                    ┌─────────────────┐           │       |
|                    │ FALLBACK [430]  │           │       |
|                    │   PQC Only      │           │       |
|                    │ Max Security    │           │       |
|                    └────────┬────────┘           │       |
|                             │                    │       |
|          QKD Restore [470]  │                    │       |
|                             ▼                    │       |
|                    ┌─────────────────┐           │       |
|                    │ RECOVERY [440]  │           │       |
|                    │ Verify + Test   │───────────┘       |
|                    └────────┬────────┘  Pass [480]       |
|                             │                            |
|               Fail [490]    │                            |
|                             ▼                            |
|                    ┌─────────────────┐                   |
|                    │ Return to       │                   |
|                    │ FALLBACK        │                   |
|                    └─────────────────┘                   |
|                                                          |
|  ─────────────────────────────────────────────────────  |
|  Legend:                                                 |
|  ┌───┐ = State    ──▶ = Transition                      |
|  T₁ = Rate threshold for degradation                     |
|                                                          |
+----------------------------------------------------------+
```

---

## Figure 5: Key Encapsulation Handshake Protocol

### Description
Sequence diagram showing the complete key encapsulation handshake between two parties.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 500 | Protocol Overview | Complete handshake |
| 510 | Initiator (Alice) | Client party |
| 520 | Responder (Bob) | Server party |
| 530 | ClientHello | Initial handshake message |
| 540 | ServerResponse | Response with ciphertext |
| 550 | KeyConfirm | Client confirmation |
| 560 | Session Established | Secure channel ready |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 200mm, Width: 160mm]                           |
|                                                          |
|     Initiator [510]                Responder [520]       |
|          │                              │                |
|          │     ClientHello [530]        │                |
|          │  {ek, params, qkd_session}   │                |
|          │─────────────────────────────▶│                |
|          │                              │                |
|          │                         Generate K_PQC       |
|          │                         Retrieve K_QKD       |
|          │                         Compute K_final      |
|          │                              │                |
|          │    ServerResponse [540]      │                |
|          │  {ct, qkd_key_id, MAC_B}     │                |
|          │◀─────────────────────────────│                |
|          │                              │                |
|     Decapsulate ct                      │                |
|     Retrieve K_QKD                      │                |
|     Compute K_final                     │                |
|     Verify MAC_B                        │                |
|          │                              │                |
|          │    KeyConfirm [550]          │                |
|          │  {MAC_A}                     │                |
|          │─────────────────────────────▶│                |
|          │                              │                |
|          │                         Verify MAC_A         |
|          │                              │                |
|          │   Session Established [560]   │                |
|          │◀ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─▶│                |
|          │      K_final active          │                |
|          │                              │                |
+----------------------------------------------------------+
```

---

## General Drawing Notes

1. All arrows indicating data flow should use solid lines with filled arrowheads
2. Control/status signals should use dashed lines with open arrowheads
3. State transitions should use solid lines with filled arrowheads
4. Decision diamonds should be clearly marked with condition text
5. All reference numerals should appear at least once in each figure where the element appears
6. Shading or cross-hatching may be used to distinguish different functional blocks
7. Text within figures should be horizontal where possible

---

*Document Version: 1.0*
*Last Updated: December 2024*

