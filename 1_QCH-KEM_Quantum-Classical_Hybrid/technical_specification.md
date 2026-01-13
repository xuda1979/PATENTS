# Technical Specification: Mathematical Foundations and Algorithmic Details

## Quantum-Classical Hybrid Key Encapsulation Mechanism (QCH-KEM)

---

## 1. System Overview

### 1.1 Architecture Components

The QCH-KEM system comprises five primary modules integrated through a central synchronization controller:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    QCH-KEM System Architecture                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │    QRNG     │    │   PQC/KEM   │    │    QKD      │             │
│  │   Module    │───▶│   Module    │    │   Module    │             │
│  │             │    │ (ML-KEM)    │    │  (BB84/E91) │             │
│  └─────────────┘    └──────┬──────┘    └──────┬──────┘             │
│         │                  │                  │                     │
│         │                  ▼                  ▼                     │
│         │         ┌─────────────────────────────────┐              │
│         │         │   Synchronization Controller     │              │
│         │         │   • Key-rate monitoring          │              │
│         │         │   • Parameter adjustment         │              │
│         │         │   • Fallback management          │              │
│         │         └─────────────────────────────────┘              │
│         │                       │                                   │
│         ▼                       ▼                                   │
│  ┌─────────────────────────────────────────────────┐               │
│  │           Key Combination Module                 │               │
│  │   K_final = KDF(K_PQC || K_QKD || context)      │               │
│  └─────────────────────────────────────────────────┘               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Security Model

The system provides defense-in-depth security through layered protection:

**Layer 1 (QRNG)**: Certified quantum randomness ensuring unpredictable cryptographic seeds
**Layer 2 (PQC)**: Computational security based on lattice hard problems (LWE/MLWE)
**Layer 3 (QKD)**: Information-theoretic security from quantum mechanical principles

**Composite Security Guarantee**: An adversary must break BOTH the PQC layer AND the QKD layer to recover the session key. This provides:
- Resilience against future cryptanalytic advances in lattice problems
- Resilience against QKD implementation vulnerabilities
- Protection during QKD hardware maintenance or disruption

---

## 2. QRNG Module Specification

### 2.1 Quantum Entropy Sources

The QRNG module supports multiple quantum entropy generation mechanisms:

#### 2.1.1 Photon Arrival Time (PAT) Method
```
Entropy rate: ~10 Mbps
Min-entropy per bit: ≥ 0.99
Implementation: Single-photon detector + high-resolution timestamping
Security assumption: Detector timing jitter provides quantum uncertainty
```

#### 2.1.2 Vacuum Fluctuation Sampling
```
Entropy rate: ~1 Gbps
Min-entropy per bit: ≥ 0.95
Implementation: Homodyne detection of vacuum state
Security assumption: Shot noise is fundamentally quantum
```

#### 2.1.3 Single-Photon Polarization
```
Entropy rate: ~100 kbps
Min-entropy per bit: ≥ 0.999
Implementation: Prepare-and-measure with random basis
Security assumption: Heisenberg uncertainty principle
```

### 2.2 Entropy Extraction

Raw quantum bits undergo conditioning to produce uniform random output:

$$H_{output} = H_{input} \cdot \frac{n_{out}}{n_{in}}$$

Where the extraction ratio satisfies the leftover hash lemma:
$$n_{out} \leq n_{in} \cdot H_{\min}(X) - 2\log(1/\epsilon)$$

**Recommended Extractor**: SHAKE-256 (SHA-3 XOF) with output length matching security parameter

### 2.3 Health Monitoring

Continuous statistical testing per NIST SP 800-90B:

| Test | Threshold | Action on Failure |
|------|-----------|-------------------|
| Repetition Count | 20 consecutive identical | Alarm + buffer flush |
| Adaptive Proportion | >19/20 same value | Alarm + rate limiting |
| Chi-Square | p < 0.0001 | Warning + investigation |
| Autocorrelation | |ρ| > 0.1 | Warning + source check |

---

## 3. Lattice-Based Encryption Module

### 3.1 ML-KEM (Kyber) Parameters

The system supports all three NIST-standardized ML-KEM parameter sets:

| Parameter | ML-KEM-512 | ML-KEM-768 | ML-KEM-1024 |
|-----------|------------|------------|-------------|
| Security Level | NIST Level 1 | NIST Level 3 | NIST Level 5 |
| n (ring dimension) | 256 | 256 | 256 |
| k (module rank) | 2 | 3 | 4 |
| q (modulus) | 3329 | 3329 | 3329 |
| η₁ (secret noise) | 3 | 2 | 2 |
| η₂ (error noise) | 2 | 2 | 2 |
| Public Key Size | 800 bytes | 1184 bytes | 1568 bytes |
| Ciphertext Size | 768 bytes | 1088 bytes | 1568 bytes |
| Shared Secret | 32 bytes | 32 bytes | 32 bytes |

### 3.2 Dynamic Parameter Selection

The synchronization controller adjusts the ML-KEM variant based on QKD key-rate:

```python
def select_pqc_parameters(qkd_rate, target_security):
    """
    Select ML-KEM variant based on QKD availability
    
    Args:
        qkd_rate: Current QKD key-rate in bits/second
        target_security: Target security level (128, 192, 256 bits)
    
    Returns:
        Selected ML-KEM parameter set
    """
    # QKD security contribution (simplified model)
    qkd_security = min(qkd_rate / 1000, 128)  # Cap at 128 bits
    
    # Required PQC security to reach target
    required_pqc = target_security - qkd_security
    
    if required_pqc <= 118:  # ML-KEM-512 provides ~118 bits
        return "ML-KEM-512"
    elif required_pqc <= 180:  # ML-KEM-768 provides ~180 bits
        return "ML-KEM-768"
    else:
        return "ML-KEM-1024"
```

### 3.3 QRNG Integration

The ML-KEM key generation and encapsulation use QRNG as randomness source:

```
KeyGen():
    d ← QRNG(32)           // 256-bit seed from QRNG
    z ← QRNG(32)           // 256-bit implicit rejection value
    (ρ, σ) ← G(d)          // Expand seed
    ... standard ML-KEM KeyGen ...

Encaps(pk):
    m ← QRNG(32)           // 256-bit message from QRNG
    (K, r) ← G(m || H(pk))
    ... standard ML-KEM Encaps ...
```

---

## 4. QKD Module Specification

### 4.1 Supported Protocols

#### 4.1.1 BB84 Protocol
```
Quantum States: {|0⟩, |1⟩, |+⟩, |-⟩}
Bases: Z (computational), X (Hadamard)
Theoretical Key Rate: R = 1 - h(QBER) - f·h(QBER)
Typical QBER threshold: 11%
```

#### 4.1.2 E91 (Entanglement-Based)
```
Quantum States: Bell state |Φ⁺⟩ = (|00⟩ + |11⟩)/√2
Security Verification: CHSH inequality violation
Theoretical Key Rate: R = 1 - h(E) - f·h(E)
Device-independent security possible
```

#### 4.1.3 CV-QKD
```
Quantum States: Coherent states |α⟩
Modulation: Gaussian modulation of amplitude and phase
Detector: Homodyne or heterodyne
Advantage: Compatible with standard telecom components
```

### 4.2 Key-Rate Monitoring

Real-time metrics provided to synchronization controller:

| Metric | Update Frequency | Used For |
|--------|------------------|----------|
| Secure Key Rate (bits/s) | 1 Hz | Parameter adjustment |
| QBER/Excess Noise | Per block | Security verification |
| Channel Loss (dB) | 10 Hz | Link quality monitoring |
| Detector Efficiency | 1/minute | Calibration |
| Background Count Rate | 1/minute | Security margin |

### 4.3 Key Buffer Management

```python
class QKDKeyBuffer:
    def __init__(self, max_size=1_000_000):
        self.buffer = []
        self.max_size = max_size
        self.consumption_rate = 0
        self.generation_rate = 0
    
    def get_key_material(self, length):
        """
        Extract key material from buffer
        Returns None if insufficient material
        """
        if len(self.buffer) < length:
            return None
        key = self.buffer[:length]
        self.buffer = self.buffer[length:]
        return bytes(key)
    
    def predict_depletion_time(self):
        """
        Estimate time until buffer runs out
        Triggers PQC parameter increase when low
        """
        if self.consumption_rate <= self.generation_rate:
            return float('inf')
        net_consumption = self.consumption_rate - self.generation_rate
        return len(self.buffer) / net_consumption
```

---

## 5. Synchronization Controller

### 5.1 Dynamic Parameter Adjustment Algorithm

```python
class SynchronizationController:
    def __init__(self, config):
        self.target_security = config.target_security  # bits
        self.min_pqc_level = config.min_pqc_level
        self.adjustment_interval = config.adjustment_interval
        self.smoothing_factor = 0.3  # EMA smoothing
        
        self.current_qkd_rate = 0
        self.smoothed_qkd_rate = 0
        self.current_pqc_params = "ML-KEM-768"
        
    def update_qkd_metrics(self, new_rate, qber):
        """
        Called when QKD module reports new metrics
        """
        # Exponential moving average for stability
        self.smoothed_qkd_rate = (
            self.smoothing_factor * new_rate + 
            (1 - self.smoothing_factor) * self.smoothed_qkd_rate
        )
        
        # Check QBER threshold
        if qber > 0.11:  # BB84 security threshold
            self.trigger_qkd_alarm()
        
        self.adjust_pqc_parameters()
    
    def adjust_pqc_parameters(self):
        """
        Adjust PQC security level based on QKD availability
        """
        # Calculate effective QKD security contribution
        qkd_contribution = self.calculate_qkd_security(self.smoothed_qkd_rate)
        
        # Determine required PQC security
        required_pqc = self.target_security - qkd_contribution
        
        # Select appropriate ML-KEM variant
        new_params = self.select_variant(required_pqc)
        
        if new_params != self.current_pqc_params:
            self.log_parameter_change(self.current_pqc_params, new_params)
            self.current_pqc_params = new_params
            
    def calculate_qkd_security(self, rate):
        """
        Model QKD security contribution based on key consumption
        
        Higher key rate = more key material available
        = can use more key material per session
        = higher information-theoretic security contribution
        """
        # Simplified model: 1 bit/s QKD → 0.01 bits security contribution
        # Capped at 64 bits (QKD provides supplementary, not primary security)
        return min(rate * 0.01, 64)
```

### 5.2 Fallback State Machine

```
                    ┌──────────────┐
                    │   NORMAL     │
                    │  QKD + PQC   │
                    └──────┬───────┘
                           │
            QKD rate drops │
            below threshold│
                           ▼
                    ┌──────────────┐
                    │  DEGRADED    │
                    │ Increased PQC│
                    └──────┬───────┘
                           │
              QKD failure  │
              detected     │
                           ▼
                    ┌──────────────┐
                    │  FALLBACK    │
                    │  PQC Only    │
                    │  Max Security│
                    └──────┬───────┘
                           │
              QKD restored │
                           │
                           ▼
                    ┌──────────────┐
                    │  RECOVERY    │
                    │ Verify + Test│
                    └──────┬───────┘
                           │
              Tests pass   │
                           │
                           ▼
                    ┌──────────────┐
                    │   NORMAL     │
                    └──────────────┘
```

---

## 6. Key Combination Module

### 6.1 Multi-Layer Key Derivation

The final session key is derived from both PQC and QKD key components:

```
K_final = HKDF-Expand(
    HKDF-Extract(
        salt = session_nonce,
        IKM = K_PQC || K_QKD
    ),
    info = "QCH-KEM v1.0" || session_id || timestamp,
    L = output_key_length
)
```

### 6.2 Security Analysis

**Theorem (Hybrid Security)**: If the HKDF is modeled as a random oracle, then:

$$\text{Adv}^{\text{KEM}}_{\text{QCH-KEM}}(\mathcal{A}) \leq \text{Adv}^{\text{MLWE}}(\mathcal{A}) + \text{Adv}^{\text{QKD}}(\mathcal{A})$$

**Interpretation**: This additive bound represents a conservative security guarantee. In the Random Oracle Model (ROM), the key combination function acts as a robust combiner, ensuring that the session key remains secure as long as at least one of the input keys ($K_{PQC}$ or $K_{QKD}$) remains indistinguishable from random. The additive form arises from the sequence of game hops used in the security reduction, where we replace one key component with a random value, and then the other.

### 6.3 Forward Secrecy

Each session generates fresh ephemeral keys:
- PQC: New ephemeral key pair per session
- QKD: Fresh key material consumed from buffer

This ensures that compromise of long-term keys does not affect past sessions.

---

## 7. Protocol Specification

### 7.1 Full Handshake Protocol

```
Initiator (Alice)                           Responder (Bob)
─────────────────                           ───────────────

1. Generate ephemeral ML-KEM keypair
   (ek, dk) ← ML-KEM.KeyGen(QRNG)
   
2. Send ClientHello
   ────────────────────────────────────▶
   {ek, supported_pqc_variants, 
    qkd_session_id}

                                        3. Verify supported parameters
                                           Select ML-KEM variant
                                           
                                        4. Encapsulate to ek
                                           (K_PQC, ct) ← ML-KEM.Encaps(ek, QRNG)
                                           
                                        5. Get QKD key material
                                           K_QKD ← QKD.GetKey(session_id, len)
                                           
                                        6. Derive session key
                                           K = KDF(K_PQC || K_QKD || ctx)
                                           
                                        7. Compute key confirmation
                                           MAC_B = HMAC(K, "server_confirm")
                                           
   ◀────────────────────────────────────
   {ct, qkd_key_id, MAC_B}

8. Decapsulate ciphertext
   K_PQC ← ML-KEM.Decaps(dk, ct)
   
9. Get QKD key material
   K_QKD ← QKD.GetKey(qkd_key_id, len)
   
10. Derive session key
    K = KDF(K_PQC || K_QKD || ctx)
    
11. Verify server confirmation
    HMAC(K, "server_confirm") == MAC_B?
    
12. Compute client confirmation
    MAC_A = HMAC(K, "client_confirm")
    
   ────────────────────────────────────▶
   {MAC_A}

                                        13. Verify client confirmation
                                            HMAC(K, "client_confirm") == MAC_A?
                                            
                                        14. Session established
```

### 7.2 Abbreviated Handshake (Session Resumption)

For resumed sessions, PQC handshake can be abbreviated using PSK:

```
K_resumed = KDF(K_PSK || K_QKD_fresh || ctx)
```

Where K_PSK is derived from a previous full handshake.

---

## 8. Performance Characteristics

### 8.1 Latency Analysis

| Phase | Latency | Notes |
|-------|---------|-------|
| QRNG Seed Generation | < 1 ms | Buffered |
| ML-KEM KeyGen | ~50 μs | ML-KEM-768 |
| ML-KEM Encaps | ~70 μs | ML-KEM-768 |
| ML-KEM Decaps | ~60 μs | ML-KEM-768 |
| QKD Key Retrieval | < 1 ms | From buffer |
| Key Derivation | < 100 μs | HKDF-SHA3-256 |
| **Total Handshake** | **< 5 ms** | Excluding network RTT |

### 8.2 Bandwidth Analysis

| Component | Size | Direction |
|-----------|------|-----------|
| ML-KEM-768 Public Key | 1184 bytes | → |
| ML-KEM-768 Ciphertext | 1088 bytes | ← |
| QKD Key ID | 16 bytes | ← |
| MACs (2x) | 64 bytes | ↔ |
| **Total Handshake** | **~2.4 KB** | |

### 8.3 QKD Key Consumption

For a 256-bit session key with 128-bit QKD contribution:
- QKD material per session: 128 bits = 16 bytes
- At 1000 sessions/second: 16 KB/s QKD key consumption
- Requires QKD rate > 128 kbps for sustained operation

---

## 9. Security Considerations

### 9.1 Threat Model

**Protected Against:**
- Quantum computers (Shor's algorithm on classical crypto)
- Harvest-now-decrypt-later attacks
- Single-point cryptographic failures
- QKD implementation side-channels (via PQC backup)
- PQC algorithm weaknesses (via QKD supplement)

**Assumed Trusted:**
- QRNG hardware produces genuine quantum randomness
- Implementation is free of side-channel leakage
- QKD and PQC implementations are correct

### 9.2 Side-Channel Mitigation

- Constant-time ML-KEM implementation
- Power analysis resistant QRNG
- Timing-safe key comparison
- Memory zeroization after use

---

## 10. Implementation Notes

### 10.1 Recommended Libraries

| Component | Recommended Implementation |
|-----------|---------------------------|
| ML-KEM | liboqs (Open Quantum Safe) |
| SHA-3/SHAKE | OpenSSL 3.x or libsodium |
| HKDF | OpenSSL or custom implementation |
| QKD Interface | Vendor-specific SDK |
| QRNG | Hardware vendor SDK |

### 10.2 Interoperability

The QCH-KEM system is designed for integration with:
- TLS 1.3 (as hybrid key exchange)
- IKEv2/IPsec (as key agreement mechanism)
- SSH (as key exchange algorithm)
- Custom secure channels

---

*Document Version: 1.0*
*Last Updated: December 2024*

