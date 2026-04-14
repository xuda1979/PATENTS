# Patent Abstract

## Noise-Adaptive Variational Quantum Encryption (NAV-QE)

---

### Abstract

A hardware-agnostic, noise-adaptive variational quantum encryption (NAV-QE) system and method for generating hardware-bound cryptographic keys by exploiting intrinsic quantum processor noise characteristics across diverse architectures including superconducting, photonic, neutral-atom, trapped-ion, topological, and spin-qubit platforms. The system comprises a quantum processor executing parameterized circuits and calibration sequences, a machine-learning characterization module extracting device-specific noise profiles including T1/T2 relaxation parameters, gate error rates, readout errors, and crosstalk coefficients, an error-mapping module transforming the extracted profile into a reproducible hardware fingerprint, and a key-generation module deriving post-quantum-compatible cryptographic material physically bound to the underlying device. A tamper-detection module continuously monitors deviations between current and enrolled baseline profiles and invalidates keys upon detection of physical interference or unauthorized manipulation. The invention converts quantum noise from a computational limitation into a deployable security primitive for device authentication, attestation, and hardware-rooted key management. The architecture is expressly structured for industrial conversion through cloud APIs, middleware adapters, verifier services, and embedded quantum hardware security modules (qHSM), thereby supporting staged deployment in quantum cloud computing, regulated infrastructure, secure communications, and post-quantum migration programs.

**(Word count: 184)**

---

### Keywords

NISQ; Variational Quantum Circuit; Hardware Fingerprinting; Quantum Noise Characterization; Machine Learning; Physical Unclonable Function; Device Authentication; Key Derivation; Tamper Detection; Quantum Cloud Security; Hardware Attestation; Post-Quantum Cryptography

---

### Brief Description of Drawings

**Figure 1**: Overall system architecture (100) showing quantum processor (110), parameterized circuit execution module (120), ML characterization module (130), error-mapping module (140), key generation module (150), and tamper detection module (160)

**Figure 2**: Noise characterization workflow (200) using VQC outputs including T1, T2, randomized benchmarking, and crosstalk measurement circuits

**Figure 3**: Cryptographic signature derivation (300) from continuous noise parameters through normalization, quantization, and SHA3-256 hashing

**Figure 4**: Device fingerprinting and challenge-response authentication protocol (400) between quantum device and verifier

**Figure 5**: Tamper detection (500) through continuous noise profile monitoring with Mahalanobis distance comparison against baseline

**Figure 6**: Entropy extraction and key derivation pipeline (600) showing raw noise measurements flowing through parameter estimation, min-entropy assessment, correlation analysis, entropy conditioning, and HKDF key expansion

**Figure 7**: Multi-device authentication network (700) showing enrollment, challenge-response verification, and attestation certificate issuance across multiple quantum processors

---

### IPC Classifications

- H04L 9/08 — Key distribution (generation)
- G06N 10/00 — Quantum computing
- G06N 10/70 — Quantum error correction or detection (related: noise characterization)
- G06F 21/44 — Device authentication
- H04L 9/32 — Including means for verifying identity
- G09C 1/00 — Cryptographic apparatus (quantum-based)
- H04L 9/06 — Encryption apparatus using shift registers or memories (key derivation)

---

### CPC Classifications (Supplementary)

- H04L 9/0866 — Key generation using physical unclonable functions
- G06N 10/20 — Quantum computing models based on VQC/VQE
- H04L 2209/12 — Quantum cryptography

---

### Technical Effects Summary

| Technical Metric | This Invention | Classical PUF | Standard QRNG |
|------------------|----------------|---------------|---------------|
| Entropy Source | Device noise | Manufacturing variation | Quantum measurement |
| Device Binding | Physical (inherent) | Physical | None |
| Tamper Evidence | Automatic | Partial | None |
| Integration w/ QC | Native | External | External |
| Clone Resistance | Quantum uniqueness | Manufacturing | N/A |
| Key Refresh | Per computation | Fixed | On demand |
| Total Entropy | 187 bits (27 qubits) | ~128 bits | Unlimited (no binding) |
| Authentication | Challenge-response | CRP-based | None |



