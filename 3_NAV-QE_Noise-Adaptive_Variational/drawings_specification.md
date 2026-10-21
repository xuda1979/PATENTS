# Patent Drawing Specifications
# Noise-Adaptive Variational Quantum Encryption (NAV-QE)

---

## Drawing Requirements

*Note: The following layouts are provided as ASCII string representations of the conceptual flow. These informal layouts must be converted to formal USPTO/PCT-compliant vector diagrams by a patent draftsperson before the final non-provisional submission.*

- **Format**: Black and white line drawings (no grayscale, no color)
- **Resolution**: Minimum 300 DPI
- **Paper Size**: A4 (210mm x 297mm) or US Letter (8.5" x 11")
- **Margins**: At least 25mm on all sides
- **Line Width**: 0.25mm minimum for all lines
- **Reference Numerals**: Arabic numerals, consistent across all figures
- **Font**: Arial or similar sans-serif, minimum 8pt

---

## Figure 1: Overall System Architecture

### Description
Shows the complete NAV-QE system including quantum processor, VQC module, ML characterization, error-mapping, key generation, and tamper detection modules.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 100 | System Overview | Complete NAV-QE architecture |
| 110 | NISQ Quantum Processor | Physical qubit hardware |
| 111 | Qubit Array | Physical qubits Q₀...Qₙ |
| 112 | Control Electronics | Gate pulse generation |
| 113 | Readout System | Measurement apparatus |
| 114 | Noise Characteristics | T1, T2, ε, crosstalk |
| 120 | Parameterized Circuit Exec. Module | Circuit execution |
| 121 | Characterization Circuits | T1, T2, RB circuits |
| 122 | Application Circuits | User computations |
| 130 | ML Characterization Module | Noise analysis |
| 131 | Neural Network | Deep learning model |
| 132 | Bayesian Estimator | Parameter estimation |
| 133 | Anomaly Detector | Tampering detection |
| 140 | Error-Mapping Module | Signature generation |
| 141 | Fingerprint Extractor | Profile to vector |
| 142 | Quantizer | Continuous to discrete |
| 143 | Signature Generator | Crypto signature |
| 150 | Key Generation Module | Key derivation |
| 151 | Entropy Extractor | Min-entropy extraction |
| 152 | KDF Unit | Key derivation function |
| 153 | Key Storage | Secure key memory |
| 160 | Tamper Detection Module | Security monitoring |
| 161 | Profile Monitor | Continuous checking |
| 162 | Alert System | Security alerts |
| 163 | Key Invalidation | Automatic key wipe |

### Layout Specification

```
+------------------------------------------------------------------+
|  [Height: 260mm, Width: 180mm]                                   |
|                                                                  |
|  TOP SECTION: Quantum Hardware [110]                             |
|  ┌────────────────────────────────────────────────────────┐     |
|  │         NISQ Quantum Processor [110]                   │     |
|  │  ┌─────────────────────────────────────────────────┐  │     |
|  │  │ ○──○──○──○──○──○  Qubit Array [111]             │  │     |
|  │  │ Q₀ Q₁ Q₂ Q₃ Q₄ Q₅...                           │  │     |
|  │  │                                                 │  │     |
|  │  │ T1, T2, ε₁, ε₂, crosstalk [114]                │  │     |
|  │  └─────────────────────────────────────────────────┘  │     |
|  │  ┌──────────────┐    ┌──────────────┐                 │     |
|  │  │Control [112] │    │Readout [113] │                 │     |
|  │  └──────┬───────┘    └──────┬───────┘                 │     |
|  └─────────┼──────────────────┼─────────────────────────┘     |
|            │                   │                               |
|            ▼                   ▼                               |
|  ┌────────────────────────────────────────────────────────┐   |
|  │         Param. Circuit Execution \[120\]                     │   |
|  │  ┌─────────────────┐    ┌─────────────────┐           │   |
|  │  │Characterization │    │Application      │           │   |
|  │  │Circuits [121]   │    │Circuits [122]   │           │   |
|  │  │(T1,T2,RB,XT)    │    │(User VQC)       │           │   |
|  │  └────────┬────────┘    └────────┬────────┘           │   |
|  └───────────┼────────────────────────────────────────────┘   |
|              │                                                 |
|              ▼                                                 |
|  ┌────────────────────────────────────────────────────────┐   |
|  │         ML Characterization Module [130]               │   |
|  │  ┌──────────┐  ┌──────────┐  ┌──────────┐             │   |
|  │  │Neural Net│  │Bayesian  │  │Anomaly   │             │   |
|  │  │[131]     │  │Estimator │  │Detector  │             │   |
|  │  │          │  │[132]     │  │[133]     │             │   |
|  │  └────┬─────┘  └────┬─────┘  └────┬─────┘             │   |
|  └───────┼─────────────┼─────────────┼────────────────────┘   |
|          │             │             │                         |
|          └──────┬──────┘             │                         |
|                 │                    │                         |
|     ┌───────────┴─────────┐         │                         |
|     │                     │         │                         |
|     ▼                     ▼         ▼                         |
|  ┌────────────────┐  ┌────────────────────────────────────┐   |
|  │Error-Mapping   │  │ Tamper Detection Module [160]      │   |
|  │Module [140]    │  │ ┌────────┐ ┌─────┐ ┌─────────┐    │   |
|  │┌──────────────┐│  │ │Monitor │ │Alert│ │Key      │    │   |
|  ││Fingerprint   ││  │ │[161]   │ │[162]│ │Invalidate│   │   |
|  ││Extractor[141]││  │ └────────┘ └─────┘ │[163]    │    │   |
|  │└──────┬───────┘│  │                    └─────────┘    │   |
|  │┌──────▼───────┐│  └────────────────────────────────────┘   |
|  ││Quantizer     ││                                           |
|  ││[142]         ││                                           |
|  │└──────┬───────┘│                                           |
|  │┌──────▼───────┐│                                           |
|  ││Signature Gen ││                                           |
|  ││[143]         ││                                           |
|  │└──────┬───────┘│                                           |
|  └───────┼────────┘                                           |
|          │                                                     |
|          ▼                                                     |
|  ┌────────────────────────────────────────────────────────┐   |
|  │         Key Generation Module [150]                    │   |
|  │  ┌──────────────┐  ┌────────────┐  ┌──────────────┐   │   |
|  │  │Entropy       │─▶│KDF Unit    │─▶│Key Storage   │   │   |
|  │  │Extractor[151]│  │[152]       │  │[153]         │   │   |
|  │  └──────────────┘  └────────────┘  └──────────────┘   │   |
|  └────────────────────────────────────────────────────────┘   |
|                                                                |
+----------------------------------------------------------------+
```

---

## Figure 2: Noise Characterization Workflow

### Description
Flowchart showing the process of characterizing device-specific noise using VQC outputs.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 200 | Workflow Start | Entry point |
| 210 | Execute T1 Circuits | Relaxation measurement |
| 220 | Execute T2 Circuits | Dephasing measurement |
| 230 | Execute RB Circuits | Gate error measurement |
| 240 | Execute Crosstalk Circuits | Coupling measurement |
| 250 | Collect Measurements | Aggregate data |
| 260 | ML Analysis | Neural network processing |
| 270 | Parameter Estimation | Bayesian inference |
| 280 | Build Noise Profile | Assemble fingerprint |
| 290 | Store Profile | Save baseline |
| 299 | Workflow End | Exit point |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 260mm, Width: 150mm]                           |
|                                                          |
|                    ┌──────────────┐                      |
|                    │  Start [200] │                      |
|                    └──────┬───────┘                      |
|                           │                              |
|         ┌─────────────────┼─────────────────┐           |
|         │                 │                 │           |
|         ▼                 ▼                 ▼           |
|  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    |
|  │Execute T1   │ │Execute T2   │ │Execute RB   │    |
|  │Circuits[210]│ │Circuits[220]│ │Circuits[230]│    |
|  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘    |
|         │                 │                 │           |
|         └─────────────────┼─────────────────┘           |
|                           │                              |
|                           ▼                              |
|                    ┌──────────────┐                      |
|                    │Execute XT   │                      |
|                    │Circuits[240]│                      |
|                    └──────┬───────┘                      |
|                           │                              |
|                           ▼                              |
|                    ┌──────────────┐                      |
|                    │Collect All  │                      |
|                    │Measurements │                      |
|                    │[250]        │                      |
|                    └──────┬───────┘                      |
|                           │                              |
|                           ▼                              |
|                    ┌──────────────┐                      |
|                    │ML Analysis  │                      |
|                    │Neural Net   │                      |
|                    │[260]        │                      |
|                    └──────┬───────┘                      |
|                           │                              |
|                           ▼                              |
|                    ┌──────────────┐                      |
|                    │Parameter    │                      |
|                    │Estimation   │                      |
|                    │Bayesian[270]│                      |
|                    └──────┬───────┘                      |
|                           │                              |
|                           ▼                              |
|                    ┌──────────────┐                      |
|                    │Build Noise  │                      |
|                    │Profile [280]│                      |
|                    │             │                      |
|                    │ f = (T1,T2, │                      |
|                    │  ε₁,ε₂,c_ij)│                      |
|                    └──────┬───────┘                      |
|                           │                              |
|                           ▼                              |
|                    ┌──────────────┐                      |
|                    │Store Profile│                      |
|                    │[290]        │                      |
|                    └──────┬───────┘                      |
|                           │                              |
|                           ▼                              |
|                    ┌──────────────┐                      |
|                    │  End [299]  │                      |
|                    └──────────────┘                      |
|                                                          |
+----------------------------------------------------------+
```

---

## Figure 3: Cryptographic Signature Derivation

### Description
Diagram showing the transformation from continuous noise parameters to discrete cryptographic signatures.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 300 | Derivation Overview | Signature process |
| 310 | Noise Profile Input | Raw parameters |
| 320 | Fingerprint Vector | Assembled vector f |
| 330 | Normalization | Scale to [0,1] |
| 340 | Quantization | Discretize to bits |
| 350 | Concatenation | Combine all bits |
| 360 | Hash Function | SHA3-256 |
| 370 | Cryptographic Signature | Final output |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 180mm, Width: 160mm]                           |
|                                                          |
|  INPUT: Noise Profile [310]                              |
|  ┌──────────────────────────────────────────────┐       |
|  │ T1₀ T2₀ T1₁ T2₁ ... ε₁₀ ε₁₁ ... ε₂₀₁ ... c₀₁... │  |
|  │ (continuous float values)                     │       |
|  └──────────────────────┬───────────────────────┘       |
|                         │                                |
|                         ▼                                |
|  ┌──────────────────────────────────────────────┐       |
|  │ Fingerprint Vector [320]                     │       |
|  │ f = [T1₀, T2₀, ..., ε₁₀, ..., c₀₁, ...]     │       |
|  │ Dimension: ~586 for 27 qubits                │       |
|  └──────────────────────┬───────────────────────┘       |
|                         │                                |
|                         ▼                                |
|  ┌──────────────────────────────────────────────┐       |
|  │ Normalization [330]                          │       |
|  │ f_i → (f_i - min_i) / (max_i - min_i)       │       |
|  │ Result: values in [0, 1]                     │       |
|  └──────────────────────┬───────────────────────┘       |
|                         │                                |
|                         ▼                                |
|  ┌──────────────────────────────────────────────┐       |
|  │ Quantization [340] (8 bits per parameter)    │       |
|  │ ┌────┐ ┌────┐ ┌────┐     ┌────┐             │       |
|  │ │10110│ │01101│ │11001│ ... │00111│           │       |
|  │ │ T1₀ │ │ T2₀ │ │ T1₁ │     │ c_mn│           │       |
|  │ └────┘ └────┘ └────┘     └────┘             │       |
|  └──────────────────────┬───────────────────────┘       |
|                         │                                |
|                         ▼                                |
|  ┌──────────────────────────────────────────────┐       |
|  │ Concatenation [350]                          │       |
|  │ 10110011010110011... (586 x� 8 = 4688 bits)  │       |
|  └──────────────────────┬───────────────────────┘       |
|                         │                                |
|                         ▼                                |
|  ┌──────────────────────────────────────────────┐       |
|  │ Hash Function [360]                          │       |
|  │ SHA3-256(concatenated_bits || device_id)    │       |
|  └──────────────────────┬───────────────────────┘       |
|                         │                                |
|                         ▼                                |
|  OUTPUT: Cryptographic Signature [370]                  |
|  ┌──────────────────────────────────────────────┐       |
|  │ 256-bit unique device signature              │       |
|  │ 0xa3b2c1d4e5f6... (64 hex characters)       │       |
|  └──────────────────────────────────────────────┘       |
|                                                          |
+----------------------------------------------------------+
```

---

## Figure 4: Device Fingerprinting and Authentication Protocol

### Description
Sequence diagram showing how device fingerprints are used for authentication.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 400 | Protocol Overview | Authentication flow |
| 410 | Quantum Device | Hardware being authenticated |
| 420 | Verifier | Authentication server |
| 430 | Challenge Request | Verifier initiates |
| 440 | Run Characterization | Device response |
| 450 | Generate Signature | Create fingerprint |
| 460 | Send Response | Signature to verifier |
| 470 | Compare Signatures | Verification step |
| 480 | Authentication Result | Accept/Reject |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 200mm, Width: 160mm]                           |
|                                                          |
|     Device [410]               Verifier [420]            |
|          │                          │                    |
|          │    Challenge [430]       │                    |
|          │◀─────────────────────────│                    |
|          │  "Prove you are Device X"│                    |
|          │                          │                    |
|          │                          │                    |
|     ┌────┴────┐                     │                    |
|     │Run Char │                     │                    |
|     │Circuits │                     │                    |
|     │[440]    │                     │                    |
|     └────┬────┘                     │                    |
|          │                          │                    |
|     ┌────┴────┐                     │                    |
|     │Generate │                     │                    |
|     │Signature│                     │                    |
|     │[450]    │                     │                    |
|     └────┬────┘                     │                    |
|          │                          │                    |
|          │    Response [460]        │                    |
|          │─────────────────────────▶│                    |
|          │  Signature + Nonce       │                    |
|          │                          │                    |
|          │                     ┌────┴────┐              |
|          │                     │Compare  │              |
|          │                     │Signatures│              |
|          │                     │[470]    │              |
|          │                     │         │              |
|          │                     │Stored vs│              |
|          │                     │Received │              |
|          │                     └────┬────┘              |
|          │                          │                    |
|          │                     ◇────┴────◇              |
|          │                    ╱  Match?   ╲             |
|          │                   ╱   [480]     ╲            |
|          │                  ◇───────────────◇           |
|          │                  │Yes           │No          |
|          │                  ▼              ▼            |
|          │           ┌──────────┐  ┌──────────┐        |
|          │◀──────────│ ACCEPT   │  │ REJECT   │        |
|          │           │Authenticated│ │Denied   │        |
|          │           └──────────┘  └──────────┘        |
|          │                                              |
+----------------------------------------------------------+
```

---

## Figure 5: Tamper Detection Through Noise Profile Monitoring

### Description
Diagram showing continuous monitoring for physical tampering attempts.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 500 | Monitoring Overview | Tamper detection system |
| 510 | Baseline Profile | Reference fingerprint |
| 520 | Current Profile | Real-time measurement |
| 530 | Deviation Calculation | Mahalanobis distance |
| 540 | Threshold Comparison | Check against τ |
| 550 | Normal Operation | Continue |
| 560 | Tamper Alert | Security warning |
| 570 | Key Invalidation | Wipe keys |
| 580 | Security Log | Record event |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 220mm, Width: 160mm]                           |
|                                                          |
|  ┌─────────────────┐    ┌─────────────────┐             |
|  │ Baseline [510]  │    │ Current [520]   │             |
|  │ Profile (stored)│    │ Profile (live)  │             |
|  │                 │    │                 │             |
|  │ f_baseline      │    │ f_current       │             |
|  └────────┬────────┘    └────────┬────────┘             |
|           │                      │                       |
|           └──────────┬───────────┘                       |
|                      │                                   |
|                      ▼                                   |
|           ┌─────────────────────────┐                   |
|           │ Deviation Calculation   │                   |
|           │ [530]                   │                   |
|           │                         │                   |
|           │ d = √[(f_c - f_b)ᵀ     │                   |
|           │       Σ⁻¹(f_c - f_b)]  │                   |
|           │                         │                   |
|           │ (Mahalanobis distance) │                   |
|           └───────────┬─────────────┘                   |
|                       │                                  |
|                       ▼                                  |
|           ◇───────────────────────◇                     |
|          ╱      d > τ ?            ╲                    |
|         ╱       [540]               ╲                   |
|        ◇─────────────────────────────◇                  |
|        │No                          │Yes                |
|        ▼                            ▼                   |
|  ┌──────────────┐           ┌──────────────┐           |
|  │ Normal [550] │           │ ALERT [560]  │           |
|  │ Continue     │           │ Tampering    │           |
|  │ Operation    │           │ Detected!    │           |
|  └──────────────┘           └──────┬───────┘           |
|        │                           │                    |
|        │                           ▼                    |
|        │                    ┌──────────────┐           |
|        │                    │ Invalidate   │           |
|        │                    │ Keys [570]   │           |
|        │                    └──────┬───────┘           |
|        │                           │                    |
|        │                           ▼                    |
|        │                    ┌──────────────┐           |
|        │                    │ Log Event    │           |
|        │                    │ [580]        │           |
|        │                    └──────────────┘           |
|        │                                               |
|        └──────────────────────────────────────────▶    |
|                    Continue Monitoring                  |
|                    (Loop every N computations)          |
|                                                          |
+----------------------------------------------------------+
```

---

## General Drawing Notes

1. Quantum hardware components shown with circular qubit symbols
2. Data flow indicated with solid arrows
3. Control/monitoring paths shown with dashed arrows
4. Security-critical paths highlighted with double lines
5. Decision points use diamond shapes
6. All mathematical formulas rendered in standard notation
7. Reference numerals appear consistently across all figures

---

## Figure 6: Entropy Extraction and Key Derivation Pipeline

### Description
Detailed pipeline diagram showing how raw noise measurements are processed through entropy extraction, conditioning, and key derivation to produce cryptographic keys.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 600 | Pipeline Overview | Full entropy-to-key pipeline |
| 610 | Raw Noise Measurements | Unprocessed characterization data |
| 620 | Parameter Estimation | ML-based noise parameter extraction |
| 625 | Uncertainty Quantification | Confidence bounds per parameter |
| 630 | Min-Entropy Assessment | Per-parameter entropy calculation |
| 640 | Correlation Analysis | Inter-parameter dependency check |
| 650 | Entropy Conditioning | Leftover hash lemma application |
| 660 | HKDF Extract | PRK generation from conditioned entropy |
| 670 | HKDF Expand | Key material expansion |
| 680 | Key Output | Final cryptographic key (128/256 bit) |
| 690 | Entropy Certificate | Attestation of key entropy quality |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 240mm, Width: 160mm]                           |
|                                                          |
|  ┌──────────────────────────────────────────────┐       |
|  │ Raw Noise Measurements [610]                 │       |
|  │ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐          │       |
|  │ │T1  │ │T2  │ │ε₁  │ │ε₂  │ │c_ij│ ... x586 │       |
|  │ └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘          │       |
|  └────┼──────┼──────┼──────┼──────┼─────────────┘       |
|       └──────┴──────┴──────┴──────┘                      |
|                      │                                    |
|                      ▼                                    |
|  ┌──────────────────────────────────────────────┐       |
|  │ Parameter Estimation [620]                   │       |
|  │ ML inference → θ̂ᵢ ± σᵢ                       │       |
|  │                                              │       |
|  │ Uncertainty Quantification [625]             │       |
|  │ Bootstrap CI: [θ̂ᵢ - 1.96σᵢ, θ̂ᵢ + 1.96σᵢ]    │       |
|  └──────────────────────┬───────────────────────┘       |
|                         │                                |
|              ┌──────────┴──────────┐                    |
|              ▼                     ▼                    |
|  ┌───────────────────┐  ┌───────────────────┐          |
|  │ Min-Entropy [630] │  │ Correlation [640] │          |
|  │ H_min(θᵢ) =       │  │ Σ = Cov(θ)       │          |
|  │ log₂(σᵢ√2πe/δᵢ)  │  │ I(f) ≈ 83 bits   │          |
|  └────────┬──────────┘  └────────┬──────────┘          |
|           └──────────┬───────────┘                      |
|                      ▼                                   |
|  ┌──────────────────────────────────────────────┐       |
|  │ Entropy Conditioning [650]                   │       |
|  │ H_secure = H_raw - I(f) - safety_margin     │       |
|  │ = 270 - 83 - 59 = 128 bits                  │       |
|  │ (Leftover Hash Lemma guarantee)              │       |
|  └──────────────────────┬───────────────────────┘       |
|                         │                                |
|              ┌──────────┴──────────┐                    |
|              ▼                     ▼                    |
|  ┌───────────────────┐  ┌───────────────────┐          |
|  │ HKDF Extract [660]│  │ Salt + Context    │          |
|  │ PRK = HMAC(salt,  │  │ "NAV-QE-KEY-V1"  │          |
|  │   fingerprint)    │──│                   │          |
|  └────────┬──────────┘  └───────────────────┘          |
|           │                                             |
|           ▼                                             |
|  ┌───────────────────────────────────────────┐         |
|  │ HKDF Expand [670]                        │         |
|  │ K = HMAC(PRK, info ∥ counter)            │         |
|  │ Iterate for key_length / 256 blocks      │         |
|  └────────┬──────────────────────────────────┘         |
|           │                                             |
|    ┌──────┴──────┐                                     |
|    ▼             ▼                                     |
|  ┌──────────┐  ┌──────────────────────────┐           |
|  │Key [680] │  │Entropy Certificate [690] │           |
|  │128 or 256│  │H_min ≥ 128 bits         │           |
|  │bit output│  │NIST SP 800-22: 15/15 pass│           |
|  └──────────┘  └──────────────────────────┘           |
|                                                          |
+----------------------------------------------------------+
```

---

## Figure 7: Multi-Device Authentication Network

### Description
Network diagram showing how multiple quantum processors are authenticated and managed in a quantum cloud or distributed computing environment using NAV-QE fingerprints.

### Reference Numerals

| Number | Element | Description |
|--------|---------|-------------|
| 700 | Network Overview | Multi-device authentication topology |
| 710 | Quantum Device A | First quantum processor |
| 720 | Quantum Device B | Second quantum processor |
| 730 | Quantum Device C | Third quantum processor |
| 740 | Fingerprint Registry | Centralized profile database |
| 750 | Authentication Server | Verification authority |
| 760 | User/Client | Requesting party |
| 770 | Attestation Certificate | Hardware-bound proof |
| 780 | Secure Channel | Authenticated communication |
| 790 | Audit Log | Immutable record of authentications |

### Layout Specification

```
+----------------------------------------------------------+
|  [Height: 240mm, Width: 170mm]                           |
|                                                          |
|               ┌─────────────────────┐                    |
|               │ User/Client [760]   │                    |
|               │ "Run my circuit on  │                    |
|               │  Device A"         │                    |
|               └─────────┬───────────┘                    |
|                         │                                |
|                         ▼                                |
|               ┌─────────────────────┐                    |
|               │ Authentication     │                    |
|               │ Server [750]       │                    |
|               │                    │                    |
|               │ ┌────────────────┐ │                    |
|               │ │ Fingerprint    │ │                    |
|               │ │ Registry [740] │ │                    |
|               │ │ ┌──┐ ┌──┐ ┌──┐│ │                    |
|               │ │ │fA│ │fB│ │fC││ │                    |
|               │ │ └──┘ └──┘ └──┘│ │                    |
|               │ └────────────────┘ │                    |
|               └──┬──────┬──────┬───┘                    |
|                  │      │      │                         |
|         Challenge│      │      │Challenge               |
|                  ▼      │      ▼                         |
|  ┌──────────────────┐  │  ┌──────────────────┐         |
|  │ Device A [710]   │  │  │ Device C [730]   │         |
|  │ ┌──────────────┐ │  │  │ ┌──────────────┐ │         |
|  │ │ NAV-QE       │ │  │  │ │ NAV-QE       │ │         |
|  │ │ Fingerprint  │ │  │  │ │ Fingerprint  │ │         |
|  │ │ fA (unique)  │ │  │  │ │ fC (unique)  │ │         |
|  │ └──────┬───────┘ │  │  │ └──────┬───────┘ │         |
|  │        │Response  │  │  │        │Response  │         |
|  └────────┼──────────┘  │  └────────┼──────────┘         |
|           │             │           │                    |
|           ▼             │           ▼                    |
|  ┌────────────────────────────────────────────┐         |
|  │          Verification Process              │         |
|  │                                            │         |
|  │  Compare: f_received vs f_stored           │         |
|  │  d(fA_received, fA_stored) < τ?            │         |
|  │                                            │         |
|  │  ✓ Match → Issue Attestation [770]         │         |
|  │  ✗ Mismatch → Reject + Alert               │         |
|  └───────────────────────┬────────────────────┘         |
|                          │                               |
|               ┌──────────┴──────────┐                   |
|               ▼                     ▼                   |
|  ┌────────────────────┐  ┌────────────────────┐        |
|  │ Attestation [770]  │  │ Audit Log [790]    │        |
|  │ Certificate:       │  │ Timestamp          │        |
|  │ {Device: A,        │  │ Device ID          │        |
|  │  Fingerprint: fA,  │  │ Result             │        |
|  │  Computation: hash,│  │ Deviation metric   │        |
|  │  Timestamp: t,     │  │                    │        |
|  │  Signature: σ}     │  │                    │        |
|  └────────┬───────────┘  └────────────────────┘        |
|           │                                             |
|           ▼                                             |
|  ┌────────────────────────────┐                        |
|  │ Secure Channel [780]      │                        |
|  │ User receives:            │                        |
|  │ • Computation result      │                        |
|  │ • Attestation certificate │                        |
|  │ • Hardware proof          │                        |
|  └────────────────────────────┘                        |
|                                                          |
+----------------------------------------------------------+
```

---

## General Drawing Notes

1. Quantum hardware components shown with circular qubit symbols
2. Data flow indicated with solid arrows
3. Control/monitoring paths shown with dashed arrows
4. Security-critical paths highlighted with double lines
5. Decision points use diamond shapes
6. All mathematical formulas rendered in standard notation
7. Reference numerals appear consistently across all figures
8. Figures 6-7 extend the system architecture for specific subsystems and deployment scenarios
9. All reference numerals follow the convention: Figure N uses numerals N00-N99

---

*Document Version: 1.1*
*Last Updated: February 2026*

