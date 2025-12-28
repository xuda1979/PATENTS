# Patent Abstract

## Quantum-Secure Threshold Signature System and Method Based on Lattice-Based Falcon Algorithm

---

### Abstract

**Technical Field**: The present invention relates to blockchain technology, Post-Quantum Cryptography (PQC), and Multi-Party Computation (MPC).

**Technical Problem**: Existing cross-chain bridges using elliptic curve threshold signatures are vulnerable to quantum computing attacks. Furthermore, distributed implementation of the Falcon algorithm faces discrete Gaussian sampling challenges and O(n) communication complexity.

**Technical Solution**: A quantum-secure threshold signature system comprising: a distributed key generation module for generating secret-shared NTRU trapdoor portions among multiple nodes via secure multi-party computation; an arithmetic-shared NTT computation module utilizing NTT linearity for zero-communication distributed polynomial operations; a collaborative rejection sampling module reducing communication rounds from O(n) to O(1) through a pre-check commitment mechanism; and a signature aggregation module outputting NIST Falcon-compliant digital signatures.

**Technical Effects**: Compared to existing Dilithium threshold schemes, signature length is reduced by approximately 3.6 times (~666 bytes vs ~2420 bytes), blockchain gas costs are reduced by approximately 72%, dynamic node management is supported, while maintaining quantum-resistant security properties.

---

### Keywords

Post-quantum cryptography; Falcon signature; Threshold signature; Multi-party secure computation; NTRU lattice; Cross-chain bridge; Discrete Gaussian sampling

---

### Brief Description of Drawings

**Figure 1**: Overall system architecture diagram showing interaction flow between source chain, threshold signature system, and target chain

**Figure 2**: Collaborative rejection sampling flowchart showing the three-phase protocol of commitment, pre-check, and reveal

**Figure 3**: Dynamic node management diagram including three scenarios: node addition, revocation, and offline recovery

---

### IPC Classifications

- H04L 9/32 — Digital signatures
- H04L 9/30 — Public key cryptosystems
- H04L 9/08 — Key distribution
- G06F 21/64 — Integrity protection

---

### Technical Effects Summary

| Technical Metric | This Invention | Prior Art (Dilithium) | Improvement |
|------------------|----------------|----------------------|-------------|
| Signature Length | ~666 bytes | ~2420 bytes | 3.6x smaller |
| Communication Rounds | O(1) | O(n) | Significantly reduced |
| Gas Cost | ~50,000 | ~180,000 | 72% savings |
| Quantum-Safe | ✓ | ✓ | Equivalent |
| Dynamic Nodes | ✓ | Limited | Enhanced |

---

### Document Checklist

1. Patent Application (Chinese) - `专利申请书_中文.md`
2. Patent Application (English) - `patent_draft.md`
3. Technical Specification - `technical_specification.md`
4. Claims (English) - `claims_EN.md`
5. Abstract (Chinese) - `摘要_中文.md`
6. Abstract (English) - This document
7. Drawing Specifications - `drawings_specification.md`
8. Prior Art Search Report - `prior_art_report.md`
9. Experimental Data - `experimental_data.md`

---

### Word Count

Abstract body word count: ~150 words (compliant with USPTO 150-word limit)

---

### Priority and Filing Strategy

**Recommended Filing Sequence:**

1. **Initial Filing (China)**: Submit to CNIPA to establish priority date
2. **PCT Application**: File within 12 months claiming China priority
3. **National Phase**: Enter US, EU, and other jurisdictions within 30/31 months

**Priority Date**: [To be determined upon filing]

---

*This abstract is prepared for international patent filing through the PCT route. The Chinese application serves as the priority document.*
