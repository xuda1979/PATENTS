# Technical Specification
# Dynamic Lattice-Hopping Protocol (DLHP)

---

## 1. Introduction

### 1.1 Purpose

This document provides the complete technical specification for the Dynamic Lattice-Hopping Protocol (DLHP), a cryptographic communication framework designed to enhance resilience against both current cryptanalytic attacks and future quantum computer-enabled threats through continuous algorithm rotation.

### 1.2 Scope

The specification covers:
- Protocol architecture and component design
- Algorithm library requirements
- Temporal synchronization mechanisms
- State machine definitions
- Key derivation procedures
- Security analysis and threat modeling

### 1.3 Design Philosophy

DLHP applies the proven concept of frequency hopping from radio communications to cryptographic algorithm selection. Just as frequency hopping thwarts jammers by never staying on one frequency long enough to be effectively targeted, DLHP thwarts cryptanalysts by never encrypting enough data under one algorithm to make cryptanalysis worthwhile.

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DLHP Node                                │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Application Layer Interface                │   │
│  └───────────────────────────┬─────────────────────────────┘   │
│                              │                                  │
│  ┌───────────────────────────▼─────────────────────────────┐   │
│  │              Protocol State Machine                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │   │
│  │  │ INITIAL  │ │ ACTIVE   │ │TRANSITION│ │ CLOSED   │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │   │
│  └───────────────────────────┬─────────────────────────────┘   │
│                              │                                  │
│  ┌───────────────────────────▼─────────────────────────────┐   │
│  │              Temporal Synchronization Module             │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐              │   │
│  │  │ Clock Sync│ │ Schedule  │ │ Transition│              │   │
│  │  │ Engine    │ │ Generator │ │ Timer     │              │   │
│  │  └───────────┘ └───────────┘ └───────────┘              │   │
│  └───────────────────────────┬─────────────────────────────┘   │
│                              │                                  │
│  ┌───────────────────────────▼─────────────────────────────┐   │
│  │              Post-Quantum Algorithm Library              │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │   │
│  │  │ ML-KEM │ │  NTRU  │ │McEliece│ │  BIKE  │           │   │
│  │  │(Kyber) │ │        │ │        │ │        │           │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘           │   │
│  └───────────────────────────┬─────────────────────────────┘   │
│                              │                                  │
│  ┌───────────────────────────▼─────────────────────────────┐   │
│  │              Key Management Module                       │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐              │   │
│  │  │ Master Key│ │ KDF Engine│ │ Key Store │              │   │
│  │  │ Exchange  │ │           │ │           │              │   │
│  │  └───────────┘ └───────────┘ └───────────┘              │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Interactions

```
┌────────────┐        ┌────────────┐
│   Node A   │        │   Node B   │
└─────┬──────┘        └──────┬─────┘
      │                      │
      │   Initial Handshake  │
      │◀────────────────────▶│
      │                      │
      │ [Derive master key,  │
      │  hopping schedule]   │
      │                      │
      │   Algorithm 1 Data   │
      │─────────────────────▶│
      │◀─────────────────────│
      │                      │
      │   [Switch Point]     │
      │                      │
      │   Algorithm 2 Data   │
      │─────────────────────▶│
      │◀─────────────────────│
      │                      │
      │   [Switch Point]     │
      │                      │
      │   Algorithm 3 Data   │
      │─────────────────────▶│
      │                      │
      ▼                      ▼
```

---

## 3. Post-Quantum Algorithm Library

### 3.1 Supported Algorithms

| Algorithm | Hard Problem | NIST Status | Security Level | Key Size |
|-----------|--------------|-------------|----------------|----------|
| ML-KEM-768 | Module-LWE | Standardized | Level 3 | 2,400 bytes |
| ML-KEM-1024 | Module-LWE | Standardized | Level 5 | 3,168 bytes |
| NTRU-HPS-677 | NTRU | Round 3 Alt | Level 3 | 930 bytes |
| NTRU-HRSS-701 | NTRU | Round 3 Alt | Level 3 | 1,138 bytes |
| Classic McEliece | Coding Theory | Round 4 | Level 5 | 261,120 bytes |
| BIKE-L3 | QC-MDPC | Round 4 | Level 3 | 5,122 bytes |
| HQC-256 | QC | Round 4 | Level 5 | 7,245 bytes |
| FrodoKEM-976 | Plain LWE | Round 3 Alt | Level 3 | 31,296 bytes |

### 3.2 Algorithm Independence Requirements

For effective algorithm diversity, the library must include algorithms based on at least three mathematically independent hard problems:

| Hard Problem Class | Representatives | Independence |
|-------------------|-----------------|--------------|
| Structured Lattices | ML-KEM, NTRU | Related but distinct |
| Unstructured Lattices | FrodoKEM | Independent of structured |
| Coding Theory | McEliece, BIKE, HQC | Independent of lattices |
| Isogenies | SIKE (broken), SQIsign | Independent (currently limited) |
| Hash-based (signatures) | SPHINCS+, SLH-DSA | Independent (conservative) |

### 3.3 Algorithm Interface

```python
class PQAlgorithm(Protocol):
    """Interface for post-quantum algorithms in DLHP"""
    
    @property
    def algorithm_id(self) -> bytes:
        """Unique 4-byte identifier for this algorithm"""
        ...
    
    @property
    def hard_problem(self) -> str:
        """Mathematical hard problem (LWE, NTRU, CODE, etc.)"""
        ...
    
    def keygen(self) -> Tuple[PublicKey, SecretKey]:
        """Generate algorithm-specific keypair"""
        ...
    
    def encaps(self, pk: PublicKey) -> Tuple[Ciphertext, SharedSecret]:
        """Encapsulate shared secret under public key"""
        ...
    
    def decaps(self, sk: SecretKey, ct: Ciphertext) -> SharedSecret:
        """Decapsulate shared secret using secret key"""
        ...
    
    def estimated_security_bits(self) -> int:
        """Current best-known security estimate"""
        ...
```

---

## 4. Temporal Synchronization

### 4.1 Time Model

```
Timeline:
┌───────────┬───────────┬───────────┬───────────┬───────────┐
│  Algo 1   │  Algo 2   │  Algo 3   │  Algo 1   │  Algo 2   │
│           │           │           │           │           │
└───────────┴───────────┴───────────┴───────────┴───────────┘
t₀          t₁          t₂          t₃          t₄          t

Where:
- t₀ = session epoch (initial handshake completion)
- tᵢ - tᵢ₋₁ = hopping interval (configurable, default 60 seconds)
- Algorithm at time t: A[⌊(t - t₀) / interval⌋ mod n]
```

### 4.2 Epoch Establishment

During initial handshake:

```
Node A                                      Node B
   │                                           │
   │─── ClientHello (timestamp_A) ───────────▶│
   │                                           │
   │◀── ServerHello (timestamp_B, Δ_est) ─────│
   │                                           │
   │    epoch = (timestamp_A + timestamp_B) / 2 + RTT/4
   │                                           │
```

### 4.3 Hopping Schedule Generation

The hopping schedule is derived deterministically from shared secrets:

```python
def generate_hopping_schedule(
    master_secret: bytes,
    algorithm_ids: List[bytes],
    session_id: bytes,
    max_transitions: int = 2**20
) -> List[int]:
    """
    Generate deterministic hopping schedule.
    
    Returns indices into algorithm_ids list.
    """
    schedule = []
    n = len(algorithm_ids)
    
    for i in range(max_transitions):
        # Derive pseudo-random value for this transition
        prk = HKDF_Extract(
            salt=session_id,
            ikm=master_secret
        )
        okm = HKDF_Expand(
            prk=prk,
            info=b"DLHP-HOP" + i.to_bytes(4, 'big'),
            length=4
        )
        
        # Map to algorithm index
        index = int.from_bytes(okm, 'big') % n
        schedule.append(index)
    
    return schedule
```

### 4.4 Transition Overlap Window

To accommodate clock skew, transitions use overlap windows:

```
           Node A Clock
           ────────────────────────────────────▶
                     │  Transition  │
           ──────────┼──────────────┼─────────────
           [  Algo 1 │  Overlap     │  Algo 2  ]
                     │              │
                     │◀───window───▶│
           
           Node B Clock (slightly behind)
           ────────────────────────────────────▶
                        │ Transition │
           ─────────────┼────────────┼────────────
           [   Algo 1   │  Overlap   │  Algo 2  ]
                        │            │
```

**Overlap Window Size**: `W = 2 × (max_clock_drift + max_network_latency)`

**Default**: W = 2 × (500ms + 500ms) = 2 seconds

### 4.5 Transition Protocol

```
Phase 1: Pre-Transition (t < T_switch - W/2)
- Normal operation under current algorithm
- Both nodes compute upcoming algorithm

Phase 2: Overlap Window (T_switch - W/2 ≤ t ≤ T_switch + W/2)
- Sender: Can use either algorithm, prefers new
- Receiver: Accepts both algorithms, identified by header
- Transition marker included in first packet of new algorithm

Phase 3: Post-Transition (t > T_switch + W/2)
- Normal operation under new algorithm
- Reject packets under old algorithm (possible replay)
```

---

## 5. Protocol State Machine

### 5.1 State Definitions

| State | Description | Valid Operations |
|-------|-------------|------------------|
| INITIAL | Pre-handshake | Initiate, Accept |
| HANDSHAKING | Key exchange in progress | Exchange messages |
| ACTIVE | Normal operation | Encrypt, Decrypt, Switch |
| TRANSITIONING | Algorithm switch in progress | Dual-decode |
| SUSPENDED | Temporary pause | Resume, Close |
| CLOSED | Session terminated | None |
| ERROR | Unrecoverable error | Close |

### 5.2 State Transition Diagram

```
                          ┌─────────────┐
                          │   INITIAL   │
                          └──────┬──────┘
                                 │ initiate/accept
                                 ▼
                          ┌─────────────┐
                          │ HANDSHAKING │◀──────────┐
                          └──────┬──────┘           │
                                 │ complete         │ retry
                                 ▼                  │
                          ┌─────────────┐           │
              ┌──────────▶│   ACTIVE    │───────────┘
              │           └──────┬──────┘
              │                  │ switch_time
              │                  ▼
              │           ┌─────────────────┐
              │           │  TRANSITIONING  │
              │           └──────┬──────────┘
              │                  │ switch_complete
              └──────────────────┘
              
        From any state:
              │ close                    │ error
              ▼                          ▼
        ┌───────────┐             ┌───────────┐
        │  CLOSED   │             │   ERROR   │
        └───────────┘             └───────────┘
```

### 5.3 Session State Structure

```python
@dataclass
class DLHPSession:
    """Complete state for a DLHP session"""
    
    # Identification
    session_id: bytes              # 32-byte unique identifier
    local_node_id: bytes           # Local node identifier
    remote_node_id: bytes          # Peer node identifier
    
    # Timing
    epoch: float                   # Session start timestamp
    hopping_interval: float        # Seconds between transitions
    overlap_window: float          # Transition overlap size
    
    # Cryptographic State
    master_secret: bytes           # Derived from initial handshake
    hopping_schedule: List[int]    # Algorithm index sequence
    current_hop_index: int         # Current position in schedule
    
    # Algorithm State
    current_algorithm: PQAlgorithm # Active algorithm
    current_keys: KeyPair          # Algorithm-specific keys
    next_algorithm: PQAlgorithm    # Pre-computed next algorithm
    next_keys: KeyPair             # Pre-computed next keys
    
    # Counters
    packets_this_hop: int          # Packets since last transition
    total_packets: int             # Total session packets
    
    # State Machine
    state: SessionState            # Current protocol state
    
    # Security
    threat_level: int              # 0-10 scale
    last_transition: float         # Timestamp of last switch
```

---

## 6. Key Management

### 6.1 Master Key Derivation

Initial handshake produces master key material:

```python
def derive_master_key(
    initial_kem_shared_secret: bytes,
    client_random: bytes,
    server_random: bytes
) -> Tuple[bytes, bytes, bytes]:
    """
    Derive session keys from initial handshake.
    
    Returns:
        master_secret: For deriving algorithm-specific keys
        client_to_server_key: Initial C→S encryption
        server_to_client_key: Initial S→C encryption
    """
    # Concatenate all handshake secrets
    handshake_secret = (
        initial_kem_shared_secret +
        client_random +
        server_random
    )
    
    # Extract PRK using HKDF
    prk = HKDF_Extract(
        salt=b"DLHP-v1-master",
        ikm=handshake_secret
    )
    
    # Expand to multiple keys
    master_secret = HKDF_Expand(prk, b"master", 32)
    c2s_key = HKDF_Expand(prk, b"c2s", 32)
    s2c_key = HKDF_Expand(prk, b"s2c", 32)
    
    return master_secret, c2s_key, s2c_key
```

### 6.2 Algorithm-Specific Key Derivation

Each algorithm transition derives fresh keys:

```python
def derive_hop_keys(
    master_secret: bytes,
    hop_index: int,
    algorithm_id: bytes,
    session_id: bytes
) -> bytes:
    """
    Derive keys for a specific hop in the sequence.
    
    This ensures forward secrecy within the session—compromising
    one hop's keys doesn't reveal others.
    """
    info = (
        b"DLHP-hop-key" +
        hop_index.to_bytes(4, 'big') +
        algorithm_id +
        session_id
    )
    
    return HKDF_Expand(
        prk=master_secret,
        info=info,
        length=64  # 32 bytes each direction
    )
```

### 6.3 Key Hierarchy

```
                   Initial KEM
                       │
                       ▼
              ┌─────────────────┐
              │  Handshake PRK  │
              └────────┬────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌───────────┐┌───────────┐┌───────────┐
    │  Master   ││   C→S     ││   S→C     │
    │  Secret   ││   Key₀    ││   Key₀    │
    └─────┬─────┘└───────────┘└───────────┘
          │
          ├─────────────┬─────────────┐
          ▼             ▼             ▼
    ┌───────────┐ ┌───────────┐ ┌───────────┐
    │ Hop₁ Keys │ │ Hop₂ Keys │ │ Hop₃ Keys │
    │ (Algo A)  │ │ (Algo B)  │ │ (Algo C)  │
    └───────────┘ └───────────┘ └───────────┘
```

---

## 7. Packet Format

### 7.1 DLHP Packet Structure

```
┌────────────────────────────────────────────────────────────────┐
│                        DLHP Packet                             │
├────────────────────────────────────────────────────────────────┤
│  0                   1                   2                   3 │
│  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1│
├─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┤
│V│T│R│ Reserved  │         Algorithm ID (8 bits)               │
├─┴─┴─┴───────────┴─────────────────────────────────────────────┤
│                      Hop Index (32 bits)                       │
├────────────────────────────────────────────────────────────────┤
│                   Sequence Number (64 bits)                    │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                      Nonce (96 bits)                           │
│                                                                │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│                   Encrypted Payload                            │
│                       (variable)                               │
│                                                                │
├────────────────────────────────────────────────────────────────┤
│                Authentication Tag (128 bits)                   │
│                                                                │
│                                                                │
│                                                                │
└────────────────────────────────────────────────────────────────┘

Flags:
  V (1 bit):  Protocol version indicator
  T (1 bit):  Transition marker (first packet after switch)
  R (1 bit):  Retransmission flag
```

### 7.2 Header Processing

```python
def process_packet_header(
    packet: bytes,
    session: DLHPSession
) -> Tuple[int, int, bytes]:
    """
    Extract and validate packet header.
    
    Returns:
        algorithm_id: Which algorithm encrypted this packet
        hop_index: Which hop this packet belongs to
        sequence: Packet sequence number
    
    Raises:
        InvalidPacketError: If header validation fails
    """
    flags = packet[0]
    algorithm_id = packet[1]
    hop_index = int.from_bytes(packet[2:6], 'big')
    sequence = int.from_bytes(packet[6:14], 'big')
    
    # Validate hop index is current or adjacent
    if abs(hop_index - session.current_hop_index) > 1:
        raise InvalidPacketError("Hop index out of range")
    
    # Validate algorithm matches hop
    expected_algo = session.hopping_schedule[hop_index]
    if algorithm_id != expected_algo:
        raise InvalidPacketError("Algorithm mismatch")
    
    return algorithm_id, hop_index, sequence
```

---

## 8. Adaptive Hopping

### 8.1 Threat Level Indicators

| Threat Level | Condition | Hopping Interval |
|--------------|-----------|------------------|
| 0 (Low) | Normal operation | 120 seconds |
| 1-3 (Moderate) | Elevated monitoring | 60 seconds |
| 4-6 (High) | Active probing detected | 30 seconds |
| 7-9 (Critical) | Known attack underway | 10 seconds |
| 10 (Emergency) | Immediate threat | 5 seconds |

### 8.2 Threat Detection Sources

```python
class ThreatIndicators:
    """Sources for threat level computation"""
    
    # Published cryptanalytic advances
    algorithm_advisories: Dict[AlgorithmID, SecurityStatus]
    
    # Network anomalies
    connection_anomalies: int     # Unusual connection patterns
    timing_anomalies: int         # Suspicious timing behavior
    traffic_anomalies: int        # Unusual traffic patterns
    
    # Policy inputs
    organization_threat_level: int  # Organizational security posture
    geographic_risk: int            # Location-based risk
    
    # Session observations
    failed_authentications: int   # Auth failures this session
    replay_attempts: int          # Detected replay attacks
    
    def compute_threat_level(self) -> int:
        """Aggregate indicators into 0-10 threat level"""
        ...
```

### 8.3 In-Band Frequency Adjustment

```
Node A (detects threat)                Node B
    │                                     │
    │── ADJUST_FREQUENCY(new_interval) ──▶│
    │                                     │
    │◀─── FREQUENCY_ACK ─────────────────│
    │                                     │
    [Both nodes apply new interval at next transition]
```

---

## 9. Security Analysis

### 9.1 Threat Model

| Threat | DLHP Mitigation |
|--------|-----------------|
| Store Now, Decrypt Later | Fragments under different algorithms |
| Single algorithm break | Only fraction of session exposed |
| Active MITM | Each transition requires key knowledge |
| Replay attacks | Sequence numbers, hop indices |
| Clock manipulation | Bounded acceptance windows |

### 9.2 Security Reduction

**Theorem**: If any single algorithm in the DLHP library provides IND-CCA2 security, then DLHP provides at least equivalent security for the fragments encrypted under that algorithm.

**Corollary**: DLHP security is at least as strong as the strongest algorithm in the library, and potentially stronger due to diversity.

### 9.3 Quantitative Analysis

For a session with:
- Duration: T seconds
- Hopping interval: H seconds
- Number of algorithms: N
- Algorithm security: S bits each

**Transitions per session**: ⌈T/H⌉

**Data per algorithm**: T/(N × H) × data_rate

**Attack complexity**: An attacker breaking k algorithms gains access to k/N of the session data, requiring ~k × 2^S work.

---

## 10. Performance Considerations

### 10.1 Overhead Analysis

| Operation | Latency | Frequency |
|-----------|---------|-----------|
| Initial handshake | ~200ms | Once per session |
| Key derivation | ~1ms | Per transition |
| Algorithm switch | ~0.5ms | Per transition |
| Packet encrypt | ~10μs | Per packet |
| Packet decrypt | ~10μs | Per packet |

### 10.2 Bandwidth Overhead

| Component | Size | Overhead |
|-----------|------|----------|
| DLHP header | 18 bytes | Per packet |
| Auth tag | 16 bytes | Per packet |
| Transition marker | 1 byte (flag) | Per transition |

**Total overhead**: ~34 bytes per packet (~2% for 1500-byte packets)

### 10.3 Memory Requirements

| Component | Memory |
|-----------|--------|
| Algorithm library | ~500 KB |
| Session state | ~2 KB |
| Key storage | ~1 KB per session |
| Schedule cache | ~4 KB |

---

## 11. Implementation Guidelines

### 11.1 Reference Implementation Structure

```
dlhp/
├── algorithms/
│   ├── __init__.py
│   ├── interface.py      # Algorithm interface definition
│   ├── mlkem.py          # ML-KEM implementation
│   ├── ntru.py           # NTRU implementation
│   └── mceliece.py       # McEliece implementation
├── protocol/
│   ├── __init__.py
│   ├── state_machine.py  # Protocol state machine
│   ├── session.py        # Session management
│   └── packets.py        # Packet format handling
├── timing/
│   ├── __init__.py
│   ├── sync.py           # Time synchronization
│   └── schedule.py       # Hopping schedule generation
├── keys/
│   ├── __init__.py
│   ├── derivation.py     # Key derivation functions
│   └── storage.py        # Secure key storage
└── security/
    ├── __init__.py
    ├── threat.py         # Threat level computation
    └── audit.py          # Security event logging
```

### 11.2 Integration Points

- **TLS**: Implement as TLS extension (see RFC 8446 extensions)
- **IPsec**: Implement as IKEv2 extension
- **Custom**: Implement over raw TCP/UDP

---

*Technical Specification Version: 1.0*
*Last Updated: December 2024*

