# Patent Drawing Specifications
# Dynamic Multi-Primitive Cryptographic Hopping Protocol (DMP-CHP) (also referred to as DLHP)

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

## Figure 1: Overall System Architecture

### Description
Shows the complete DLHP system including both communicating nodes and the protocol layers.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 100 | System Overview | Complete DLHP architecture |
| 110 | Node A | First communicating endpoint |
| 120 | Node B | Second communicating endpoint |
| 130 | Network | Communication channel |
| 140 | Algorithm Library | Post-quantum algorithm collection |
| 141 | ML-KEM Module | Lattice-based KEM |
| 142 | NTRU Module | NTRU-based KEM |
| 143 | McEliece Module | Code-based KEM |
| 144 | BIKE Module | QC-MDPC KEM |
| 150 | Temporal Sync Module | Time synchronization |
| 160 | Protocol State Machine | Session management |
| 170 | Key Management | Key derivation and storage |
| 180 | Application Interface | API layer |

### Layout Specification

```
+------------------------------------------------------------------+
|  [Height: 260mm, Width: 180mm]                                   |
|                                                                  |
|  ┌──────────────────────┐        ┌──────────────────────┐       |
|  │      NODE A [110]     │        │      NODE B [120]    │       |
|  ├──────────────────────┤        ├──────────────────────┤       |
|  │                      │        │                      │       |
|  │ ┌──────────────────┐ │        │ ┌──────────────────┐ │       |
|  │ │ Application [180]│ │        │ │ Application [180]│ │       |
|  │ └────────┬─────────┘ │        │ └────────┬─────────┘ │       |
|  │          │           │        │          │           │       |
|  │ ┌────────▼─────────┐ │        │ ┌────────▼─────────┐ │       |
|  │ │ Protocol State   │ │        │ │ Protocol State   │ │       |
|  │ │ Machine [160]    │ │        │ │ Machine [160]    │ │       |
|  │ └────────┬─────────┘ │        │ └────────┬─────────┘ │       |
|  │          │           │        │          │           │       |
|  │ ┌────────▼─────────┐ │        │ ┌────────▼─────────┐ │       |
|  │ │ Temporal Sync    │ │        │ │ Temporal Sync    │ │       |
|  │ │ Module [150]     │ │        │ │ Module [150]     │ │       |
|  │ └────────┬─────────┘ │        │ └────────┬─────────┘ │       |
|  │          │           │        │          │           │       |
|  │ ┌────────▼─────────┐ │        │ ┌────────▼─────────┐ │       |
|  │ │ Algorithm Library│ │        │ │ Algorithm Library│ │       |
|  │ │ [140]            │ │        │ │ [140]            │ │       |
|  │ │┌────┐┌────┐┌────┐│ │        │ │┌────┐┌────┐┌────┐│ │       |
|  │ ││141 ││142 ││143 ││ │        │ ││141 ││142 ││143 ││ │       |
|  │ │└────┘└────┘└────┘│ │        │ │└────┘└────┘└────┘│ │       |
|  │ └────────┬─────────┘ │        │ └────────┬─────────┘ │       |
|  │          │           │        │          │           │       |
|  │ ┌────────▼─────────┐ │        │ ┌────────▼─────────┐ │       |
|  │ │ Key Management   │ │        │ │ Key Management   │ │       |
|  │ │ [170]            │ │        │ │ [170]            │ │       |
|  │ └────────┬─────────┘ │        │ └────────┬─────────┘ │       |
|  │          │           │        │          │           │       |
|  └──────────┼───────────┘        └──────────┼───────────┘       |
|             │                               │                    |
|             │      ┌───────────────┐        │                    |
|             └─────▶│ Network [130] │◀───────┘                    |
|                    │ (Untrusted)   │                             |
|                    └───────────────┘                             |
|                                                                  |
+------------------------------------------------------------------+
```

---

## Figure 2: Algorithm Hopping Timeline

### Description
Shows the temporal sequence of algorithm transitions during a communication session.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 200 | Timeline Overview | Hopping sequence |
| 210 | Epoch (t₀) | Session start |
| 220 | Algorithm Period 1 | First algorithm active |
| 230 | Transition Window 1 | First switch overlap |
| 240 | Algorithm Period 2 | Second algorithm active |
| 250 | Transition Window 2 | Second switch overlap |
| 260 | Algorithm Period 3 | Third algorithm active |
| 270 | Hopping Interval | Time between switches |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 150mm, Width: 170mm]                           |
|                                                          |
|  TIME ─────────────────────────────────────────────────▶ |
|                                                          |
|  Epoch                                                   |
|   t₀ [210]                                               |
|    │                                                     |
|    ▼                                                     |
|  ──┬────────────────┬──┬────────────────┬──┬──────────── |
|    │   ML-KEM       │TW│    NTRU        │TW│  McEliece   |
|    │   [220]        │  │    [240]       │  │   [260]     |
|    │                │  │                │  │             |
|  ──┴────────────────┴──┴────────────────┴──┴──────────── |
|                                                          |
|    ◀───── 60s ─────▶    ◀───── 60s ─────▶               |
|        [270]                [270]                        |
|                                                          |
|  LEGEND:                                                 |
|  ┌───────────────────────────────────────────────────┐  |
|  │ Algorithm Period: Normal encrypted communication  │  |
|  │ TW: Transition Window (2s overlap) [230][250]     │  |
|  └───────────────────────────────────────────────────┘  |
|                                                          |
|  Hopping Schedule (derived from master secret):          |
|  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┐           |
|  │Hop 0│Hop 1│Hop 2│Hop 3│Hop 4│Hop 5│ ... │           |
|  │ML-KEM│NTRU│McE  │BIKE │ML-KEM│NTRU│     │           |
|  └─────┴─────┴─────┴─────┴─────┴─────┴─────┘           |
|                                                          |
+----------------------------------------------------------+
```

---

## Figure 3: Temporal Synchronization Protocol

### Description
Sequence diagram showing how nodes establish and maintain time synchronization.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 300 | Sync Overview | Synchronization protocol |
| 310 | Node A | Initiating node |
| 320 | Node B | Responding node |
| 330 | ClientHello | Initial message with timestamp |
| 340 | ServerHello | Response with timestamps |
| 350 | Epoch Calculation | Common epoch derivation |
| 360 | Schedule Derivation | Hopping schedule computation |
| 370 | Synchronized State | Both nodes synchronized |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 200mm, Width: 150mm]                           |
|                                                          |
|     Node A [310]                    Node B [320]         |
|         │                               │                |
|         │   ClientHello [330]           │                |
|         │   (timestamp_A, random_A)     │                |
|         │──────────────────────────────▶│                |
|         │                               │                |
|         │                          ┌────┴────┐          |
|         │                          │ Record  │          |
|         │                          │timestamp│          |
|         │                          └────┬────┘          |
|         │                               │                |
|         │   ServerHello [340]           │                |
|         │   (timestamp_B, random_B,     │                |
|         │    KEM ciphertext)            │                |
|         │◀──────────────────────────────│                |
|         │                               │                |
|    ┌────┴────┐                    ┌────┴────┐           |
|    │Calculate│                    │Calculate│           |
|    │RTT & Δ  │                    │RTT & Δ  │           |
|    └────┬────┘                    └────┬────┘           |
|         │                               │                |
|    ┌────▼────┐                    ┌────▼────┐           |
|    │ Epoch   │                    │ Epoch   │           |
|    │ = (tA + │                    │ = (tA + │           |
|    │tB)/2    │                    │tB)/2    │           |
|    │[350]    │                    │[350]    │           |
|    └────┬────┘                    └────┬────┘           |
|         │                               │                |
|    ┌────▼────┐                    ┌────▼────┐           |
|    │ Derive  │                    │ Derive  │           |
|    │Schedule │                    │Schedule │           |
|    │[360]    │                    │[360]    │           |
|    └────┬────┘                    └────┬────┘           |
|         │                               │                |
|         │        [Synchronized]         │                |
|         │◀─────────[370]───────────────▶│                |
|         │                               │                |
|         ▼                               ▼                |
|    [Begin Secure Communication]                          |
|                                                          |
+----------------------------------------------------------+
```

---

## Figure 4: Transition Window Detail

### Description
Detailed view of the overlap window during algorithm transition.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 400 | Window Overview | Transition window detail |
| 410 | Pre-Transition | Before switch |
| 420 | Overlap Start | Window begins |
| 430 | Nominal Switch | Ideal switch point |
| 440 | Overlap End | Window closes |
| 450 | Post-Transition | After switch |
| 460 | Clock A | Node A's clock |
| 470 | Clock B | Node B's clock |
| 480 | Acceptance Zone | Dual-algorithm period |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 180mm, Width: 160mm]                           |
|                                                          |
|  Node A Clock [460]                                      |
|  ──────────────────────────────────────────────────────▶ |
|        │              │              │                   |
|        t₁             T_switch       t₂                  |
|        [420]          [430]          [440]               |
|                                                          |
|  ┌─────────────────────────────────────────────────────┐|
|  │                                                     │|
|  │  Algorithm A                  │  Algorithm B        │|
|  │  (active)                     │  (active)           │|
|  │  [410]                        │  [450]              │|
|  │                               │                     │|
|  │◀────── Overlap Window ───────▶│                     │|
|  │        [480]                  │                     │|
|  │        (Accept A or B)        │                     │|
|  │                               │                     │|
|  └─────────────────────────────────────────────────────┘|
|                                                          |
|  Node B Clock [470] (slightly offset)                   |
|  ──────────────────────────────────────────────────────▶ |
|           │              │              │                |
|           t₁'            T_switch'      t₂'              |
|                                                          |
|  Overlap Window Size:                                    |
|  ┌─────────────────────────────────────────────────────┐|
|  │ W = 2 × (max_clock_drift + max_network_latency)     │|
|  │ Default: W = 2 × (500ms + 500ms) = 2 seconds        │|
|  └─────────────────────────────────────────────────────┘|
|                                                          |
|  Packet Handling During Overlap:                         |
|  ┌────────────────────────────────────────────────┐     |
|  │ Sender: May use either algorithm               │     |
|  │ Receiver: Identifies algorithm from header     │     |
|  │           Decrypts with appropriate keys       │     |
|  └────────────────────────────────────────────────┘     |
|                                                          |
+----------------------------------------------------------+
```

---

## Figure 5: Key Derivation Hierarchy

### Description
Shows the hierarchical relationship between master keys and algorithm-specific keys.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 500 | Hierarchy Overview | Key derivation tree |
| 510 | Initial KEM | First key encapsulation |
| 520 | Handshake PRK | Pseudo-random key |
| 530 | Master Secret | Long-term session key |
| 540 | Hop Keys | Per-transition keys |
| 550 | C→S Key | Client to server key |
| 560 | S→C Key | Server to client key |
| 570 | KDF Function | Key derivation function |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 200mm, Width: 150mm]                           |
|                                                          |
|                 ┌────────────────┐                       |
|                 │  Initial KEM   │                       |
|                 │  Shared Secret │                       |
|                 │  [510]         │                       |
|                 └───────┬────────┘                       |
|                         │                                |
|                         ▼ HKDF-Extract                   |
|                 ┌────────────────┐                       |
|                 │ Handshake PRK  │                       |
|                 │ [520]          │                       |
|                 └───────┬────────┘                       |
|                         │                                |
|           ┌─────────────┼─────────────┐                 |
|           │             │             │                 |
|           ▼             ▼             ▼                 |
|     ┌──────────┐ ┌──────────┐ ┌──────────┐             |
|     │ Master   │ │ Initial  │ │ Initial  │             |
|     │ Secret   │ │ C→S Key  │ │ S→C Key  │             |
|     │ [530]    │ │ [550]    │ │ [560]    │             |
|     └────┬─────┘ └──────────┘ └──────────┘             |
|          │                                              |
|          │ HKDF-Expand (per hop)                        |
|          │ [570]                                        |
|          │                                              |
|    ┌─────┼─────┬─────────────┬─────────────┐           |
|    │     │     │             │             │           |
|    ▼     │     ▼             ▼             ▼           |
| ┌──────┐│  ┌──────┐      ┌──────┐      ┌──────┐       |
| │Hop 0 ││  │Hop 1 │      │Hop 2 │      │Hop 3 │       |
| │Keys  ││  │Keys  │      │Keys  │      │Keys  │       |
| │(ML-KEM)│ │(NTRU)│      │(McE) │      │(BIKE)│       |
| └──────┘│  └──────┘      └──────┘      └──────┘       |
|         │                                              |
|         │  Derivation Formula:                         |
|         │  ┌────────────────────────────────────┐     |
|         │  │ K_i = HKDF(Master, algo_id ∥       │     |
|         │  │           session_id ∥ hop_index)  │     |
|         │  └────────────────────────────────────┘     |
|                                                          |
+----------------------------------------------------------+
```

---

## Figure 6: Packet Format Structure

### Description
Detailed breakdown of the DLHP packet format.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 600 | Packet Overview | Complete packet structure |
| 610 | Header Section | Fixed-size header |
| 620 | Flags Byte | Control flags |
| 630 | Algorithm ID | Current algorithm identifier |
| 640 | Hop Index | Position in hopping schedule |
| 650 | Sequence Number | Replay protection |
| 660 | Nonce | AEAD nonce |
| 670 | Encrypted Payload | Ciphertext |
| 680 | Authentication Tag | AEAD tag |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 200mm, Width: 160mm]                           |
|                                                          |
|  DLHP Packet Structure [600]                             |
|                                                          |
|  ┌────────────────────────────────────────────────────┐ |
|  │ HEADER [610]                                       │ |
|  ├────────────────────────────────────────────────────┤ |
|  │  Byte 0: Flags [620]                               │ |
|  │  ┌───┬───┬───┬───────────────────────────────────┐│ |
|  │  │ V │ T │ R │        Reserved (5 bits)          ││ |
|  │  │1b │1b │1b │                                   ││ |
|  │  └───┴───┴───┴───────────────────────────────────┘│ |
|  │                                                    │ |
|  │  Byte 1: Algorithm ID [630]                        │ |
|  │  ┌───────────────────────────────────────────────┐│ |
|  │  │     Algorithm Identifier (8 bits)             ││ |
|  │  │     0x01=ML-KEM, 0x02=NTRU, 0x03=McE, etc.   ││ |
|  │  └───────────────────────────────────────────────┘│ |
|  │                                                    │ |
|  │  Bytes 2-5: Hop Index [640]                        │ |
|  │  ┌───────────────────────────────────────────────┐│ |
|  │  │     32-bit unsigned integer (big endian)      ││ |
|  │  └───────────────────────────────────────────────┘│ |
|  │                                                    │ |
|  │  Bytes 6-13: Sequence Number [650]                 │ |
|  │  ┌───────────────────────────────────────────────┐│ |
|  │  │     64-bit unsigned integer (big endian)      ││ |
|  │  └───────────────────────────────────────────────┘│ |
|  │                                                    │ |
|  │  Bytes 14-25: Nonce [660]                          │ |
|  │  ┌───────────────────────────────────────────────┐│ |
|  │  │     96-bit AEAD nonce                         ││ |
|  │  └───────────────────────────────────────────────┘│ |
|  └────────────────────────────────────────────────────┘ |
|                                                          |
|  ┌────────────────────────────────────────────────────┐ |
|  │ PAYLOAD [670]                                      │ |
|  ├────────────────────────────────────────────────────┤ |
|  │  Variable length encrypted application data        │ |
|  │  (Encrypted with AES-256-GCM under hop key)       │ |
|  └────────────────────────────────────────────────────┘ |
|                                                          |
|  ┌────────────────────────────────────────────────────┐ |
|  │ TAG [680]                                          │ |
|  ├────────────────────────────────────────────────────┤ |
|  │  128-bit AEAD authentication tag                   │ |
|  └────────────────────────────────────────────────────┘ |
|                                                          |
|  Total Header Overhead: 26 bytes                        |
|  Total Overhead: 42 bytes (with tag)                    |
|                                                          |
+----------------------------------------------------------+
```

---

## Figure 7: Adaptive Threat Response

### Description
Shows how the system adjusts hopping frequency based on threat level.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 700 | Response Overview | Adaptive system |
| 710 | Threat Indicators | Input signals |
| 720 | Threat Analyzer | Assessment module |
| 730 | Level 0-3 | Low threat |
| 740 | Level 4-6 | Medium threat |
| 750 | Level 7-9 | High threat |
| 760 | Level 10 | Emergency |
| 770 | Interval Adjustment | Frequency modification |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 200mm, Width: 150mm]                           |
|                                                          |
|  THREAT INDICATORS [710]                                 |
|  ┌────────────────────────────────────────────────────┐ |
|  │ • Cryptanalytic advisories                         │ |
|  │ • Network anomalies                                │ |
|  │ • Failed authentication attempts                   │ |
|  │ • Policy-based requirements                        │ |
|  │ • Geographic risk factors                          │ |
|  └───────────────────────┬────────────────────────────┘ |
|                          │                               |
|                          ▼                               |
|  ┌────────────────────────────────────────────────────┐ |
|  │            THREAT ANALYZER [720]                   │ |
|  │      (Aggregate and compute threat level)          │ |
|  └───────────────────────┬────────────────────────────┘ |
|                          │                               |
|          ┌───────────────┼───────────────┐              |
|          ▼               ▼               ▼              |
|  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    |
|  │ Level 0-3    │ │ Level 4-6    │ │ Level 7-10   │    |
|  │ [730]        │ │ [740]        │ │ [750][760]   │    |
|  │              │ │              │ │              │    |
|  │ Interval:    │ │ Interval:    │ │ Interval:    │    |
|  │ 60-120 sec   │ │ 30 sec       │ │ 5-10 sec     │    |
|  │              │ │              │ │              │    |
|  │ Normal       │ │ Elevated     │ │ Critical     │    |
|  │ operation    │ │ vigilance    │ │ response     │    |
|  └──────────────┘ └──────────────┘ └──────────────┘    |
|                                                          |
|  INTERVAL ADJUSTMENT [770]                               |
|  ┌────────────────────────────────────────────────────┐ |
|  │  Threat  │  Hopping   │  Data per  │  Algorithms   │ |
|  │  Level   │  Interval  │  Algorithm │  per Hour     │ |
|  ├──────────┼────────────┼────────────┼───────────────┤ |
|  │  0-3     │  60-120s   │  Large     │  30-60        │ |
|  │  4-6     │  30s       │  Medium    │  120          │ |
|  │  7-9     │  10s       │  Small     │  360          │ |
|  │  10      │  5s        │  Minimal   │  720          │ |
|  └──────────┴────────────┴────────────┴───────────────┘ |
|                                                          |
+----------------------------------------------------------+
```

---

## General Drawing Notes

1. Protocol flows shown with solid arrows for data, dashed for control
2. Time flows left to right in timeline diagrams
3. Security boundaries indicated with double-line boxes
4. Key material paths highlighted where applicable
5. All timestamps shown in relative time from epoch
6. Algorithm names abbreviated consistently (ML-KEM, McE, etc.)
7. Reference numerals used consistently across all figures

---

*Document Version: 1.0*
*Last Updated: December 2024*

