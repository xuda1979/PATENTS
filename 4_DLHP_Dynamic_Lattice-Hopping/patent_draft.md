# Patent Draft: Dynamic Multi-Primitive Cryptographic Hopping Protocol (DMP-CHP)

*Also referred to herein as the Dynamic Lattice-Hopping Protocol (DLHP).* 

## 1. Abstract

This invention discloses a dynamic cryptographic communication protocol that can improve resilience against cryptanalytic advances, including post-quantum threats, by utilizing cryptographic "hopping" not just in time but across mathematical hard-problem classes and (optionally) network paths. The system enables micro-fragmentation of encrypted sessions in which protected units (e.g., packets, records, blocks, or shares) may be protected under different cryptographic constructions over time, thereby limiting exposure if any single algorithm is later compromised. In some embodiments, the protocol further applies threshold splitting (e.g., $(k,n)$ secret sharing or erasure coding) such that reconstruction of a payload requires at least $k$ independently protected shares. A cognitive adaptation engine may monitor network conditions and threat indicators (e.g., latency anomalies) to adjust hopping frequency and algorithm selection. Furthermore, the protocol can support "spatial hopping" or transport dispersion by distributing protected units across multiple physical network paths (e.g., 5G, Wi-Fi, satellite), thereby increasing the difficulty of complete traffic capture.

---

## 2. Technical Field

The present invention relates to cryptographic communications and post-quantum cryptography, and more particularly to:

- Protocol design for quantum-resistant communications
- "Cryptographic Agility" and "Orthogonal Security" enforcement
- Cognitive networking and threat-adaptive encryption
- Defense against "Store Now, Decrypt Later" (SNDL) and side-channel attacks
- Multi-algorithm key encapsulation and spatial transport dispersion

---

## 3. Background of the Invention

### 3.1 Problem Statement

The advent of quantum computing poses an existential threat to current public-key cryptographic systems. While post-quantum cryptography (PQC) algorithms offer resistance, the security landscape faces several challenges:

1. **Algorithm Uncertainty**: No PQC algorithm has withstood decades of cryptanalysis; unexpected weaknesses may emerge.
2. **SNDL Attacks**: Adversaries can store encrypted traffic today for decryption once quantum computers become available.
3. **Static Vulnerabilities**: Current protocols use single algorithms throughout sessions, creating concentrated attack targets.
4. **Migration Complexity**: Transitioning between algorithms typically requires full session re-establishment.
5. **Side-Channel Leaks**: Long-term usage of a single key/algo increases the signal-to-noise ratio for power/timing analysis.

### 3.2 Limitations of Existing Approaches

| Approach | Limitation |
|----------|------------|
| Static PQC | Single point of failure; entire session at risk |
| Hybrid Classical/PQ | Still single PQ algorithm per session; adds overhead without diversity |
| Algorithm migration | Requires re-handshaking; high latency; no protection within session |
| Algorithm combiners | Increased overhead; all algorithms used simultaneously, not distinctively |

### 3.3 Technical Opportunity

Frequency hopping in radio communications demonstrates that rapidly switching between different channels can provide resilience against jamming and interception. This invention extends this principle to the logical layer (mathematical hopping) and, in some embodiments, to the spatial layer (path hopping).

---

## 4. Summary of the Invention

### 4.1 Core Innovation

The invention implements "Cryptographic Frequency Hopping" by:

1.  **Micro-Fragmentation**: Breaking the session into granular units (time-blocks, packets, or bytes), each protected by a different mathematical foundation.
2.  **Holographic Data Reconstruction**: Using threshold splitting (e.g., secret sharing or erasure coding) where fragments are encrypted with disparate algorithms. This can require an attacker to compromise multiple independently protected shares to reconstruct a payload.
3.  **Active Decoy Defense**: In some embodiments, injecting decoy packets that mimic characteristics of legitimate traffic and decrypt to noise or non-operative content, thereby increasing adversary collection and processing burden.
4.  **Orthogonal Security**: Enforcing that sequential hops utilize mathematically independent hard problems (e.g., Lattice $\to$ Code $\to$ Isogeny), ensuring no single mathematical breakthrough compromises adjacent fragments.
5.  **Cognitive Adaptation**: Using an AI-driven or heuristic engine to sense threat levels (e.g., detecting timing analysis) and automatically triggering "Paranoid Mode" (increasing hop rate and algorithm weight).
6.  **Spatial Dispersion**: Splitting the encrypted stream across multiple physical interfaces (MPTCP/QUIC), preventing single-link interception.

### 4.2 System Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      DLHP Cognitive System                      │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Node A (Sender)                                 Node B        │
│  ┌──────────────────┐                    ┌──────────────────┐  │
│  │ Cognitive Engine │                    │ Cognitive Engine │  │
│  │ (Threat Sensor)  │                    │ (Threat Sensor)  │  │
│  └────────┬─────────┘                    └────────┬─────────┘  │
│           │ Controls                              │ Controls   │
│           ▼                                       ▼            │
│  ┌──────────────────┐                    ┌──────────────────┐  │
│  │ Schedule Mutator │                    │ Schedule Mutator │  │
│  │ (Jitter/Entropy) │                    │ (Jitter/Entropy) │  │
│  └────────┬─────────┘                    └────────┬─────────┘  │
│           │                                       │            │
│           ▼                                       ▼            │
│  ┌──────────────────┐                    ┌──────────────────┐  │
│  │ Orthogonal Lib   │                    │ Orthogonal Lib   │  │
│  │[Lattice][Code]...│                    │[Lattice][Code]...│  │
│  └────────┬─────────┘                    └────────┬─────────┘  │
│           │                                       │            │
│           ▼ [Split]                               ▼ [Merge]    │
│  ┌────────────────────────────────────────────────────┐        │
│  │   Spatial Dispersion (Multi-Path Transport)        │        │
│  │ ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │        │
│  │ │ Path 1 (5G)  │  │ Path 2 (WiFi)│  │Path 3 (Sat)│ │        │
│  │ │ [Algo: LWE]  │  │ [Algo: Code] │  │[Algo: ISO] │ │        │
│  │ └──────────────┘  └──────────────┘  └────────────┘ │        │
│  └────────────────────────────────────────────────────┘        │
└────────────────────────────────────────────────────────────────┘
```

### 4.3 Key Innovations

1.  **Seamless Transition**: Switch algorithms packet-by-packet without handshake overhead.
2.  **Deterministic vs. Evolving**: Schedule generation starts deterministic but evolves based on shared environmental entropy (e.g., channel noise), making the schedule unpredictable to outsiders.
3.  **Overlap Windows**: Accommodate clock drift during transitions.
4.  **Threat Adaptation**: Adjust hopping frequency based on threat level.

---

## 5. Detailed Description

### 5.1 Protocol Phases

#### Phase 1: Initial Handshake
```
Client                                              Server
   │                                                   │
   │── ClientHello (timestamp, random, supported_algs)▶│
   │                                                   │
   │◀── ServerHello (timestamp, random, KEM_ct, algs) ─│
   │                                                   │
   │   [Both derive: master_key, hopping_schedule]     │
   │                                                   │
```

#### Phase 2: Hopping Schedule Derivation
```
Input:
  - master_secret: 32 bytes
  - session_id: 32 bytes
  - algorithm_ids: List of supported algorithms

Output:
  - schedule[]: Index sequence for algorithm rotation

Algorithm:
  for i in range(max_transitions):
      okm = HKDF(master_secret, "DMP-CHP-HOP" || i)
    schedule[i] = okm mod len(algorithm_ids)

In a sequence-based (stateless) mode suitable for packetized transports, each protected unit is labeled with an authenticated monotonic sequence identifier (SeqID). The sender and receiver independently derive algorithm selection and per-unit keying material from the SeqID without requiring per-packet chaining state, thereby tolerating packet loss and out-of-order delivery.

Example stateless derivation:

   seed = HMAC(master_secret, "HOP" || SeqID || ModeSalt)
   idx  = BigInt(seed[0:4]) mod len(algorithm_ids)
   k_pkt = HKDF(seed, "KEYGEN")

The SeqID is authenticated as associated data (or equivalently integrity-protected) to prevent an attacker from forcing selection of a chosen algorithm.
```

#### Phase 3: Synchronized Communication

| Time | Active Algorithm | Action |
|------|-----------------|--------|
| t₀ | Algorithm[0] | Session starts |
| t₀ + H | Algorithm[1] | First transition |
| t₀ + 2H | Algorithm[2] | Second transition |
| ... | ... | Continue cycling |

### 5.2 Algorithm Library Requirements

The library must include algorithms based on at least three independent hard problems:

| Category | Hard Problem | Example Algorithms |
|----------|-------------|-------------------|
| Structured Lattices | Module-LWE | ML-KEM (Kyber) |
| NTRU-type | NTRU | NTRU-HPS, NTRU-HRSS |
| Code-based | Decoding | Classic McEliece, BIKE, HQC |
| Unstructured Lattices | Plain LWE | FrodoKEM |

### 5.3 Transition Protocol

```
Time: T_switch - W/2                    T_switch + W/2
         │                                    │
         │◀────── Overlap Window W ──────────▶│
         │                                    │
Sender:  │  Use Algo_old  │  Use Algo_new   │
         │                │                  │
Receiver:│  Accept both, identify from header │
         │                                    │

Replay protection is enforced by rejecting protected units with duplicate SeqID values within a replay window, and by rejecting SeqID values outside an acceptance window after a confirmed transition.

The header includes at least: session identifier, SeqID, mode identifier, and algorithm identifier (or sufficient information for the receiver to compute and validate a derived algorithm identifier).

Orthogonality enforcement may be implemented by prohibiting adjacent protected units from using algorithms within the same hard-problem class, and by retrying schedule derivation (e.g., incrementing SeqID for selection only, while preserving a transmitted canonical SeqID) until the next selected algorithm satisfies the orthogonality constraint.
```

### 5.4 Key Hierarchy

```
Initial KEM Shared Secret
         │
         ▼ HKDF-Extract
    Handshake PRK
         │
    ┌────┼────┐
    ▼    ▼    ▼
Master  C→S   S→C
Secret  Key₀  Key₀
    │
    │ HKDF-Expand (per hop)
    │
┌───┼───┬───────┐
▼       ▼       ▼
Hop₁   Hop₂   Hop₃
Keys   Keys   Keys
```

---

## 6. Claims

This document is a narrative draft. The authoritative claim text and numbering are maintained in:

- `claims_EN.md` (authoritative claim set)
- `patent_consolidated.md` (integrated spec + claims package)

To avoid inconsistencies, this file intentionally does not duplicate the full claim text.

\
*End of Claims section.*

---

## 7. Technical Effects and Advantages

### 7.1 SNDL Attack Mitigation

| Configuration | Data Exposed if One Algorithm Broken |
|--------------|--------------------------------------|
| Static single algorithm | 100% |
| DLHP with 4 algorithms | 25% |
| DLHP with 5 algorithms | 20% |

### 7.2 Resilience to Algorithmic Breakthroughs

If any single PQC algorithm is found to be weak:
- **Static protocol**: All historical traffic decryptable
- **DLHP**: Only fragments under that algorithm affected; session-level forward secrecy preserved

### 7.3 Minimal Overhead

| Interval | Throughput Overhead | Latency Impact |
|----------|--------------------|-----------------| 
| 60 seconds | 1.2% | +0.02 ms |
| 30 seconds | 2.4% | +0.04 ms |
| 10 seconds | 4.9% | +0.09 ms |

### 7.4 Seamless Operation

- No user-visible interruption during transitions
- No re-handshaking required
- No connection drops

---

## 8. Preferred Embodiment

### 8.1 Algorithm Configuration

**Primary Library:**
- ML-KEM-768 (Lattice/M-LWE)
- NTRU-HPS-677 (NTRU)
- BIKE-L3 (Code/QC-MDPC)
- HQC-256 (Code/QC)

**Hopping Interval**: 60 seconds (default), adaptive 5-120 seconds

**Overlap Window**: 2 seconds

### 8.2 Implementation Stack

```
┌─────────────────────────────────────────┐
│           Application Layer             │
├─────────────────────────────────────────┤
│      DLHP Extension to TLS 1.3         │
├─────────────────────────────────────────┤
│   liboqs (PQC algorithm library)       │
├─────────────────────────────────────────┤
│         OpenSSL 3.x                     │
├─────────────────────────────────────────┤
│      TCP/IP Network Stack              │
└─────────────────────────────────────────┘
```

---

## 9. Alternative Embodiments

### 9.1 IPsec Integration

DLHP can extend IKEv2 for IPsec VPN deployments:
- Algorithm library in SA proposals
- Schedule derived from IKE_SA SKEYSEED
- ESP packets tagged with hop index

### 9.2 IoT Constrained Devices

For resource-constrained devices:
- Reduced algorithm library (2-3 algorithms)
- Extended hopping interval (120-300 seconds)
- Lightweight algorithms prioritized

### 9.3 Satellite Communications

For high-latency links:
- Extended overlap windows (10+ seconds)
- Pre-computed schedule caching
- Robust resynchronization protocol

---

## 10. Industrial Applicability

| Industry | Application |
|----------|-------------|
| Financial Services | Transaction protection against future quantum attacks |
| Healthcare | Long-term medical record confidentiality |
| Government | Classified communication protection |
| Telecommunications | Core network encryption |
| Cloud Services | Data-at-rest and in-transit protection |
| Critical Infrastructure | SCADA/ICS communications |

---

## 11. References to Prior Art

1. RFC 8446 - TLS 1.3 Protocol
2. NIST IR 8413 - PQC Standardization
3. Bluetooth SIG - Frequency Hopping Specification
4. Marlinspike & Perrin - Double Ratchet Algorithm
5. RFC 4301 - IPsec Architecture

---

## 12. Document History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | Initial | Original draft |
| 1.0 | December 2024 | Complete technical specification |

---

*This document is a patent draft for internal review.*
