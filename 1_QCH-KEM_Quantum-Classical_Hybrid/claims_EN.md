# Patent Claims Document
# Quantum-Classical Hybrid Key Encapsulation Mechanism (QCH-KEM)

---

## Independent Claims

### Claim 1 (System Claim)

A quantum-classical hybrid key encapsulation system, comprising:

a) a Quantum Random Number Generator (QRNG) module configured to produce high-entropy seeds through quantum mechanical processes, wherein the QRNG utilizes at least one of: photon arrival time measurement, vacuum fluctuation sampling, or single-photon polarization detection to generate certified random bits;

b) a lattice-based encryption module configured to execute a post-quantum cryptographic (PQC) algorithm using said QRNG-generated seeds as cryptographic randomness, wherein the PQC algorithm comprises at least one of: ML-KEM (Kyber), NTRU, or Module-LWE based key encapsulation;

c) a Quantum Key Distribution (QKD) module configured to establish a physics-based symmetric key between communicating parties through quantum channel transmission of encoded quantum states, wherein the QKD module outputs a key stream and associated key-rate metrics;

d) a synchronization controller configured to receive real-time key-rate data from the QKD module and dynamically adjust security parameters of the lattice-based encryption module, wherein the security parameters include at least one of: lattice dimension, modulus size, or error distribution variance;

e) a key combination module configured to cryptographically combine: (i) the encapsulated key from the lattice-based encryption module, and (ii) key material from the QKD module, to produce a final session key providing defense-in-depth security.

### Claim 2 (Method Claim)

A method for quantum-classical hybrid key encapsulation, comprising the steps of:

S1) generating high-entropy random seeds using a Quantum Random Number Generator (QRNG) through measurement of quantum mechanical phenomena;

S2) executing a lattice-based key encapsulation algorithm using the QRNG-generated seeds to produce a first key component and corresponding ciphertext;

S3) establishing a quantum key distribution (QKD) session between communicating parties to produce a second key component derived from quantum-transmitted states;

S4) monitoring the QKD key-rate in real-time and transmitting key-rate metrics to a synchronization controller;

S5) dynamically adjusting the security parameters of the lattice-based algorithm based on the monitored QKD key-rate, wherein:
   - when QKD key-rate exceeds a first threshold, reducing PQC security parameters to optimize bandwidth;
   - when QKD key-rate falls below a second threshold, increasing PQC security parameters to maintain overall security;

S6) cryptographically combining the first key component and the second key component using a key derivation function to produce a final session key.

---

## Dependent Claims

### Claims Dependent on Claim 1 (System)

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

### Claims Dependent on Claim 2 (Method)

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

## Abstract of the Claims

The independent claims define:
1. A system comprising QRNG, lattice-based encryption, QKD, synchronization controller, and key combination modules (Claim 1)
2. A method comprising QRNG seed generation, PQC key encapsulation, QKD session, dynamic parameter adjustment, and key combination steps (Claim 2)

Key innovations protected:
- Dynamic security parameter adjustment based on real-time QKD key-rate
- Multi-layered seed generation combining QRNG with QKD-derived material
- Fail-safe fallback mechanism for QKD disruption
- Dual-layer defense-in-depth key combination
- Bandwidth optimization balancing PQC and QKD overhead
- Algorithm agility supporting multiple PQC variants

---

## Claim Dependency Chart

```
Claim 1 (System - Independent)
├── Claim 3 (Dynamic Parameter Algorithm)
├── Claim 4 (QRNG Module Details)
├── Claim 5 (Key Combination Formula)
├── Claim 6 (Fail-safe Fallback)
│   └── Claim 7 (Graceful Degradation)
├── Claim 8 (PQC Algorithm Variants)
├── Claim 9 (QKD Protocol Variants)
├── Claim 10 (Bandwidth Optimization)
├── Claim 16 (Network Application)
├── Claim 17 (Data Center Application)
├── Claim 19 (Security Properties)
└── Claim 20 (Harvest-Now-Decrypt-Later Resistance)

Claim 2 (Method - Independent)
├── Claim 11 (Parameter Adjustment Formula)
├── Claim 12 (Entropy Assessment)
├── Claim 13 (Key Derivation Details)
├── Claim 14 (Key Confirmation)
├── Claim 15 (Adjustment Intervals)
└── Claim 18 (Financial Application)
```

