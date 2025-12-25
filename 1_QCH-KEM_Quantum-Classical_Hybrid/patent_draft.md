# Patent Application: Quantum-Classical Hybrid Key Encapsulation Mechanism (QCH-KEM)

## Title of Invention
Quantum-Classical Hybrid Key Encapsulation System with Dynamic Security Parameter Synchronization

---

## 1. Abstract

This invention relates to a multi-layered key encapsulation mechanism (KEM) that integrates post-quantum cryptographic (PQC) algorithms with Quantum Key Distribution (QKD) systems. The system utilizes a Quantum Random Number Generator (QRNG) to produce high-entropy seeds with certified quantum randomness for a lattice-based cryptographic algorithm (ML-KEM/Kyber). The resulting key is cryptographically combined with QKD-distributed key material through a key derivation function, providing a "fail-safe" security architecture with defense-in-depth protection.

The core innovation is a synchronization protocol that dynamically adjusts the security parameters (lattice dimension, module rank, noise distribution variance) of the PQC algorithm based on real-time fluctuations in the QKD key-rate. When QKD provides abundant key material, PQC parameters can be relaxed for efficiency; when QKD is degraded or unavailable, PQC parameters are automatically escalated to maintain overall security.

The system remains resilient even if the underlying mathematical hard problems of the PQC layer are compromised (protected by QKD) or if the QKD hardware is bypassed (protected by PQC), representing a true dual-layer defense architecture.

---

## 2. Technical Field

The present invention relates to quantum cryptography, post-quantum cryptography (PQC), and network security, specifically to:
- Hybrid key encapsulation mechanisms combining quantum and classical techniques
- Dynamic cryptographic parameter adjustment systems
- Quantum-enhanced random number generation for cryptographic seeding
- Fail-safe cryptographic architectures with automatic fallback mechanisms

**IPC Classifications:**
- H04L 9/08 — Key distribution
- H04L 9/30 — Public key cryptosystems
- H04B 10/70 — Quantum key distribution
- G06F 7/58 — Random number generators

---

## 3. Background of the Invention

### 3.1 The Quantum Computing Threat

Current public-key encryption standards, including RSA and Elliptic Curve Cryptography (ECC), are mathematically vulnerable to Shor's algorithm running on sufficiently powerful quantum computers. NIST estimates that cryptographically-relevant quantum computers may exist by 2030-2035, creating an urgent need for quantum-safe cryptographic migration.

### 3.2 Post-Quantum Cryptography (PQC)

NIST has standardized several PQC algorithms, including ML-KEM (formerly Kyber) for key encapsulation. These algorithms are based on mathematical hard problems (Learning With Errors, Module-LWE) that are believed to resist quantum attacks. However, PQC security relies on mathematical assumptions that could be invalidated by future cryptanalytic advances.

### 3.3 Quantum Key Distribution (QKD)

QKD provides information-theoretic security based on fundamental quantum mechanical principles. However, QKD faces practical limitations:
- Distance constraints (typically <100 km without repeaters)
- Hardware cost and complexity
- Key-rate limitations dependent on channel quality
- Vulnerability to implementation side-channels

### 3.4 Need for Hybrid Approach

No existing system adequately addresses the need for:
1. Dual-layer security combining mathematical and physics-based protection
2. Dynamic parameter adjustment based on real-time QKD availability
3. Graceful degradation when QKD is unavailable
4. Quantum-certified randomness for PQC operations

---

## 4. Summary of the Invention

### 4.1 Technical Problem

The present invention addresses the following technical problems:
1. Single-point cryptographic failure in pure PQC or pure QKD systems
2. Static security parameters that cannot adapt to changing QKD availability
3. Lack of certified quantum randomness in PQC implementations
4. Service interruption when QKD hardware fails or is under maintenance

### 4.2 Technical Solution

The present invention provides:

**Innovation A: Three-Layer Hybrid Architecture**
- Layer 1: QRNG providing certified quantum entropy for PQC seeding
- Layer 2: ML-KEM (Kyber) providing computational security based on lattice problems
- Layer 3: QKD providing information-theoretic security from quantum mechanics

**Innovation B: Dynamic Synchronization Protocol**
- Real-time monitoring of QKD key-rate and quality metrics
- Adaptive adjustment of PQC security parameters (ML-KEM-512/768/1024)
- Exponential moving average (EMA) smoothing to prevent parameter oscillation
- Security margin computation considering both PQC and QKD contributions

**Innovation C: Multi-Source Seed Generation**
- QRNG output provides base entropy with quantum certification
- QKD key material provides additional entropy contribution
- Cryptographic combination via KDF ensures uniform seed distribution
- Dual-source approach survives compromise of either source

**Innovation D: Fail-Safe Fallback Protocol**
- State machine managing NORMAL → DEGRADED → FALLBACK transitions
- Automatic PQC parameter escalation upon QKD degradation
- Zero-interruption service continuity during QKD outages
- Automatic recovery and re-integration when QKD resumes

### 4.3 Technical Effects

| Technical Metric | This Invention | PQC Only | QKD Only |
|------------------|----------------|----------|----------|
| Quantum Resistance | ✓ (Dual-layer) | ✓ | ✓ |
| Computational Security | ✓ | ✓ | ✗ |
| Information-Theoretic Security | Partial | ✗ | ✓ |
| Dynamic Adaptation | ✓ | ✗ | ✗ |
| Fail-Safe Mechanism | ✓ | ✗ | ✗ |
| Distance Limitation | None | None | ~100 km |
| Availability | 99.99% | 99.99% | 99.7% |

---

## 5. Detailed Description of Preferred Embodiments

### 5.1 System Architecture

The QCH-KEM system comprises five primary modules:

1. **QRNG Module**: Generates certified quantum random bits through measurement of quantum mechanical phenomena (photon arrival time, vacuum fluctuations, or single-photon polarization). Includes entropy extraction, health monitoring, and output buffering.

2. **PQC/KEM Module**: Executes ML-KEM (Kyber) key encapsulation using QRNG-generated seeds. Supports dynamic variant selection (512/768/1024) based on security requirements.

3. **QKD Module**: Establishes information-theoretically secure keys through quantum channel transmission. Provides key material and real-time key-rate metrics to synchronization controller.

4. **Synchronization Controller**: Central coordination unit that monitors QKD metrics, computes security margins, adjusts PQC parameters, and manages fallback state transitions.

5. **Key Combination Module**: Derives final session key by cryptographically combining PQC and QKD key components using HKDF.

### 5.2 Dynamic Parameter Adjustment Algorithm

The synchronization controller implements the following algorithm:

```
1. Receive QKD key-rate R_QKD and QBER from QKD module
2. Apply EMA smoothing: R_smooth = α·R_QKD + (1-α)·R_smooth_prev
3. Compute QKD security contribution: S_QKD = min(R_smooth × 0.01, 64)
4. Compute required PQC security: S_PQC_req = S_target - S_QKD
5. Select ML-KEM variant:
   - If S_PQC_req ≤ 118: ML-KEM-512
   - Elif S_PQC_req ≤ 180: ML-KEM-768
   - Else: ML-KEM-1024
6. Apply parameter change if different from current
7. Log transition for audit trail
```

### 5.3 Key Derivation Process

The final session key is derived as:
$$K_{final} = \text{HKDF-Expand}(\text{HKDF-Extract}(nonce, K_{PQC} \| K_{QKD}), context, L)$$

Where:
- $K_{PQC}$ is the ML-KEM shared secret (256 bits)
- $K_{QKD}$ is QKD-derived key material (configurable, typically 128 bits)
- $context$ includes session identifiers and timestamp
- $L$ is output key length

### 5.4 Fallback State Machine

The system maintains four states:
- **NORMAL**: Full QKD + PQC operation with dynamic parameter adjustment
- **DEGRADED**: QKD rate below threshold, PQC parameters increased
- **FALLBACK**: QKD unavailable, PQC-only mode with maximum security
- **RECOVERY**: QKD restored, verification before returning to NORMAL

---

## 6. Claims

### Independent Claims

#### Claim 1 (System Claim)

A quantum-classical hybrid key encapsulation system, comprising:

a) a Quantum Random Number Generator (QRNG) module configured to produce high-entropy seeds through quantum mechanical processes, wherein the QRNG utilizes at least one of: photon arrival time measurement, vacuum fluctuation sampling, or single-photon polarization detection to generate certified random bits;

b) a lattice-based encryption module configured to execute a post-quantum cryptographic (PQC) algorithm using said QRNG-generated seeds as cryptographic randomness, wherein the PQC algorithm comprises at least one of: ML-KEM (Kyber), NTRU, or Module-LWE based key encapsulation;

c) a Quantum Key Distribution (QKD) module configured to establish a physics-based symmetric key between communicating parties through quantum channel transmission of encoded quantum states, wherein the QKD module outputs a key stream and associated key-rate metrics;

d) a synchronization controller configured to receive real-time key-rate data from the QKD module and dynamically adjust security parameters of the lattice-based encryption module, wherein the security parameters include at least one of: lattice dimension, modulus size, or error distribution variance;

e) a key combination module configured to cryptographically combine: (i) the encapsulated key from the lattice-based encryption module, and (ii) key material from the QKD module, to produce a final session key providing defense-in-depth security.

#### Claim 2 (Method Claim)

A method for quantum-classical hybrid key encapsulation, comprising the steps of:

S1) generating high-entropy random seeds using a Quantum Random Number Generator (QRNG) through measurement of quantum mechanical phenomena;

S2) executing a lattice-based key encapsulation algorithm using the QRNG-generated seeds to produce a first key component and corresponding ciphertext;

S3) establishing a quantum key distribution (QKD) session between communicating parties to produce a second key component derived from quantum-transmitted states;

S4) monitoring the QKD key-rate in real-time and transmitting key-rate metrics to a synchronization controller;

S5) dynamically adjusting the security parameters of the lattice-based algorithm based on the monitored QKD key-rate, wherein:
   - when QKD key-rate exceeds a first threshold, reducing PQC security parameters to optimize bandwidth;
   - when QKD key-rate falls below a second threshold, increasing PQC security parameters to maintain overall security;

S6) cryptographically combining the first key component and the second key component using a key derivation function to produce a final session key.

### Dependent Claims

#### Claims Dependent on Claim 1 (System)

**Claim 3.** The system according to claim 1, wherein the synchronization controller implements a dynamic parameter adjustment algorithm comprising:
- monitoring QKD key-rate $R_{QKD}$ continuously;
- computing security margin $\Delta S = S_{target} - S_{QKD}(R_{QKD})$;
- adjusting lattice dimension $n$ according to: $n_{adjusted} = n_{base} + \alpha \cdot \Delta S$;
- wherein $\alpha$ is a configurable scaling factor and $S_{target}$ is a target security level.

**Claim 4.** The system according to claim 1, wherein the QRNG module comprises:
- a quantum entropy source generating raw quantum random bits;
- a randomness extractor applying a cryptographic hash function to concentrate entropy;
- a health monitor performing continuous statistical tests on output randomness;
- a certification module providing verifiable proof of quantum origin for generated bits.

**Claim 5.** The system according to claim 1, wherein the key combination module implements a multi-layered key derivation comprising:
$$K_{final} = \text{KDF}(K_{PQC} \| K_{QKD} \| \text{context})$$
wherein KDF is a key derivation function, $K_{PQC}$ is the lattice-based key component, $K_{QKD}$ is the QKD-derived key component, and context includes session identifiers and timestamps.

**Claim 6.** The system according to claim 1, further comprising a fail-safe fallback module configured to:
- detect QKD channel disruption or hardware failure;
- automatically increase PQC security parameters to maximum configured level upon QKD failure detection;
- maintain secure communication using PQC-only mode until QKD service is restored;
- log all fallback events for security audit purposes.

**Claim 7.** The system according to claim 6, wherein the fail-safe fallback module implements a graceful degradation protocol comprising:
- QKD health monitoring with configurable heartbeat intervals;
- gradual security parameter escalation as QKD quality degrades;
- seamless transition to PQC-only mode without session interruption;
- automatic recovery and re-integration when QKD service resumes.

**Claim 8.** The system according to claim 1, wherein the lattice-based encryption module supports multiple PQC algorithm variants and is configured to:
- maintain concurrent support for ML-KEM-512, ML-KEM-768, and ML-KEM-1024;
- dynamically select algorithm variant based on security requirements and QKD availability;
- provide algorithm agility for future NIST standard updates.

**Claim 9.** The system according to claim 1, wherein the QKD module implements at least one of:
- BB84 protocol using polarization-encoded single photons;
- E91 protocol using entangled photon pairs;
- CV-QKD (Continuous Variable) protocol using coherent states;
- wherein quantum bit error rate (QBER) is continuously monitored and used for key-rate estimation.

**Claim 10.** The system according to claim 1, further comprising a bandwidth optimization module configured to:
- estimate available network bandwidth between communicating parties;
- balance PQC ciphertext size against QKD key consumption;
- minimize total communication overhead while maintaining target security level.

#### Claims Dependent on Claim 2 (Method)

**Claim 11.** The method according to claim 2, wherein step S5 implements adaptive security parameter adjustment according to the formula:
$$n = n_{min} + \left\lfloor \frac{n_{max} - n_{min}}{R_{max}} \cdot (R_{max} - R_{QKD}) \right\rfloor$$
wherein $n$ is the lattice dimension, $n_{min}$ and $n_{max}$ are minimum and maximum dimensions, $R_{QKD}$ is current QKD key-rate, and $R_{max}$ is maximum expected key-rate.

**Claim 12.** The method according to claim 2, wherein step S1 further comprises:
- applying NIST SP 800-90B compliant entropy assessment to QRNG output;
- performing real-time min-entropy estimation;
- conditioning raw quantum entropy using a cryptographic hash function;
- providing entropy certification metadata for audit trail.

**Claim 13.** The method according to claim 2, wherein step S6 employs a key derivation function comprising:
- HKDF (HMAC-based Key Derivation Function) with SHA-3 as underlying hash;
- domain separation using application-specific labels;
- incorporation of nonces to prevent key reuse attacks;
- output key length configurable based on symmetric cipher requirements.

**Claim 14.** The method according to claim 2, further comprising a step S7 of key confirmation, wherein:
- both parties compute a key confirmation tag using the derived session key;
- tags are exchanged and verified to confirm successful key agreement;
- session establishment fails if key confirmation verification fails.

**Claim 15.** The method according to claim 2, wherein the dynamic adjustment of step S5 occurs at configurable intervals selected from:
- continuous adjustment with smoothing filter to prevent oscillation;
- periodic adjustment at fixed time intervals;
- event-triggered adjustment upon significant QKD key-rate change.

### Application-Specific Claims

**Claim 16.** The system according to claim 1, applied to secure communication network infrastructure, wherein:
- the system is deployed at network edge nodes;
- multiple QKD links are aggregated for geographic coverage;
- PQC fallback ensures service continuity during QKD link maintenance.

**Claim 17.** The system according to claim 1, applied to data center interconnection, wherein:
- high-bandwidth data channels are protected using the hybrid mechanism;
- QKD key material is distributed from dedicated quantum links;
- PQC parameters are adjusted based on data sensitivity classification.

**Claim 18.** The method according to claim 2, applied to financial transaction security, wherein:
- each transaction or transaction batch triggers a new key encapsulation;
- regulatory compliance metadata is incorporated into key derivation context;
- audit logs record security parameter choices for each transaction.

### Security Claims

**Claim 19.** The system according to claim 1, wherein security is provided through:
- information-theoretic security from QKD layer against computationally unbounded adversaries;
- computational security from PQC layer based on lattice hard problems;
- combined security ensuring that compromise of either single layer does not reveal the final key.

**Claim 20.** The system according to claim 1, wherein resilience against "harvest now, decrypt later" attacks is provided by:
- immediate quantum resistance from the PQC layer;
- forward secrecy through ephemeral key generation for each session;
- periodic key refresh incorporating fresh QKD material.

---

## 7. Brief Description of Drawings

- **Figure 1**: Overall system architecture diagram
- **Figure 2**: Dynamic parameter adjustment flowchart
- **Figure 3**: Multi-layered seed generation process
- **Figure 4**: Fail-safe fallback protocol state machine
- **Figure 5**: Key encapsulation handshake sequence diagram

See accompanying `drawings_specification.md` for detailed figure specifications.

---

## 8. Related Documents

| Document | Filename | Description |
|----------|----------|-------------|
| Abstract | `abstract_EN.md` | Patent abstract for filing |
| Claims | `claims_EN.md` | Complete claim set |
| Technical Spec | `technical_specification.md` | Detailed algorithms and protocols |
| Drawings | `drawings_specification.md` | Figure specifications |
| Prior Art | `prior_art_report.md` | Prior art search report |
| Experimental Data | `experimental_data.md` | Performance measurements |

---

*Patent Application Prepared: December 2024*
*Application Status: Ready for Filing*
