# Patent Claims
# Dynamic Multi-Primitive Cryptographic Hopping Protocol (DMP-CHP) (also referred to as DLHP)

---

## Independent Claims

### Claim 1: System Claim (Broad Core)

A secure communication system comprising:

(a) a first communication node and a second communication node configured to communicate over an untrusted network;

(b) a cryptographic algorithm library stored at each of the first communication node and the second communication node, the cryptographic algorithm library including a plurality of cryptographic algorithms from at least two different hard-problem classes, wherein said algorithms include at least one of (i) key encapsulation mechanisms (KEMs) for establishing or refreshing shared secret material or (ii) data encapsulation mechanisms (DEMs), including authenticated encryption with associated data (AEAD), for protecting payload-bearing protected units;

(c) a packet processing engine at each of the first communication node and the second communication node configured to protect a sequence of protected units of data, wherein each protected unit comprises at least one of a packet, a super-frame, a record, or a block;

(d) a deterministic schedule derivation module configured to, for each protected unit, derive (i) an algorithm selection index identifying a selected cryptographic algorithm from the cryptographic algorithm library and (ii) per-unit keying material, as a deterministic function of at least a session secret and an integrity-protected monotonic sequence identifier associated with the protected unit;

(e) an orthogonality enforcement module configured to enforce an orthogonality constraint defined in terms of hard-problem classes by prohibiting selection, for an immediately adjacent protected unit, of a next cryptographic algorithm that shares a hard-problem class with a cryptographic algorithm used for a preceding protected unit; and

(f) a receiver replay protection module configured to reject protected units having duplicate sequence identifiers within a replay window;

wherein the system is configured such that at least some consecutive protected units are protected using cryptographic algorithms from different hard-problem classes without requiring renegotiation of the session.

---

**Claim 1a.** The system of Claim 1, wherein the deterministic schedule derivation module is configured to derive the algorithm selection index as:
\[
idx = \text{Trunc32}(\text{HMAC}(K, \id{context} \parallel \id{SeqID} \parallel \id{ModeSalt})) \bmod N
\]
where $K$ is derived from the session secret, $N$ is a count of available algorithms, and $\id{SeqID}$ is authenticated as associated data.

**Claim 1b.** The system of Claim 1, wherein an authenticated header for a protected unit omits an explicit algorithm identifier and instead enables the receiving node to re-derive the selected cryptographic algorithm based on the integrity-protected monotonic sequence identifier.

\
For purposes of this claim set, “monotonic sequence identifier” means a value that increases for successive protected units within a session and is integrity protected (including authentication as associated data) such that modification of the value by an adversary is detectable.

### Claim 2: System Claim (Cognitive + Hardware)

A dynamic cognitive cryptographic communication system comprising:

(a) a first communication node and a second communication node, each configured to establish secure communication over one or more network paths;

(b) a **Cryptographic Orthogonality Library** at each node, comprising a plurality of cryptographic constructions derived from mathematically distinct hard problems (including but not limited to structured lattices, unstructured lattices, error-correcting codes, isogenies, and multivariate equations);

(c) a threat analysis module configured to monitor one or more conditions associated with secure communication over a network, the one or more conditions including at least one of latency, jitter, packet loss, reordering, or timing anomaly indicators, and to compute a threat indicator value as a function of the monitored one or more conditions;

(d) a schedule generator configured to derive and update a hopping schedule as a function of at least (i) a session secret and (ii) the threat indicator value;

(e) a **Transport Dispersion Engine** configured to fragment the communication session into granular units (packets, blocks, or time-slots) and assign each unit a specific cryptographic algorithm from the library based on the current schedule;

(f) a decoy injection module configured to generate and intersperse decoy protected units constructed to be computationally indistinguishable from legitimate protected units to an external traffic observer based on observable characteristics;

(g) an authenticated packet header format including at least a session identifier and a monotonic sequence identifier, the authenticated packet header format enabling a receiving node to deterministically derive, without storing a per-packet chaining state, (i) an algorithm selection index and (ii) per-packet keying material for a corresponding packet;

whereby the system ensures that sequential data units are encrypted using mathematically orthogonal algorithms, preventing a single cryptanalytic breakthrough from compromising contiguous data streams.

---

**Claim 2a.** The system of Claim 2, wherein the threat analysis module is configured to compute the threat indicator value based on external threat intelligence indicative of cryptanalytic advances against one or more cryptographic algorithms.

**Claim 2b.** The system of Claim 2, wherein the threat analysis module comprises a machine learning model trained to classify network timing anomalies indicative of an attack.

**Claim 2c.** The system of Claim 2, wherein the threat analysis module is implemented using federated learning in which each communication node trains a local model and exchanges model updates with one or more peer nodes without exposing raw traffic data.

**Claim 2d.** The system of Claim 2, wherein the threat analysis module is trained using reinforcement learning to select at least one of a hopping frequency, a hopping mode, or an algorithm library subset that optimizes a policy objective comprising at least one of throughput, latency, battery consumption, or security level.

**Claim 2e.** The system of Claim 2, wherein the schedule generator is configured to mutate the hopping schedule based on shared environmental entropy and the threat indicator value.

**Claim 2f.** The system of Claim 2, wherein derivation of the hopping schedule is cryptographically bound to a Physical Unclonable Function (PUF) response.

---

### Claim 3: Method Claim - Orthogonal Poly-Algorithmic Encryption

A method for Orthogonal Poly-Algorithmic Encryption, comprising:

(a) performing an initial handshake to establish a master session key and a baseline algorithm rotation schedule;

(b) monitoring a set of environmental variables to detect potential surveillance or interference;

(c) **micro-fragmenting** the data stream into discrete units (including packet-level segmentation);

(d) applying a **Holographic Entropy Dispersion** scheme (extending Shamir’s Secret Sharing or Reed-Solomon erasure coding) to split a single logical data payload into $N$ cryptographically interdependent shares, wherein reconstruction of the payload requires a threshold $k$ of said shares;

(e) protecting each of said $N$ shares using a selected cryptographic mechanism from the library, including at least one of (i) deriving a per-share key and encrypting the share with AEAD or (ii) performing a KEM operation to refresh seed material for deriving per-share keys, wherein selections are diversified across hard-problem classes;

(f) assigning a unique cryptographic algorithm to each unit based on the schedule, enforcing an **Orthogonality Constraint** such that no two consecutive units are encrypted with algorithms sharing the same mathematical hard problem class;

(g) optionally transmitting said units over physically distinct network paths ("Spatial Hopping");

(h) reconstructing the stream at the receiver by applying the inverse schedule, collecting $k$ valid shares, and combining them to recover the original payload;

whereby "Store Now, Decrypt Later" attacks are mitigated by requiring the adversary to compromise multiple distinct hard-problem classes associated with the shares in order to reconstruct the payload.

\
For purposes of this claim set, “monotonic sequence identifier” has the meaning set forth following Claim 1.

---

### Claim 4: Method Claim - Synchronization

A method for synchronizing cryptographic algorithm transitions between communication nodes comprising:

(a) during initial handshake, exchanging time reference information and establishing a common epoch;

(b) deriving a pseudo-random hopping sequence from shared secret material using a deterministic algorithm, wherein both nodes independently compute identical sequences;

(c) maintaining local clocks with bounded drift tolerance;

(d) computing current algorithm index as a function of elapsed time since epoch and the hopping sequence;

(e) implementing transition windows with overlap periods to accommodate clock skew, wherein:
   - (i) the receiving node accepts data encrypted under both current and adjacent algorithms during overlap;
   - (ii) the sending node transitions at the midpoint of the overlap window;

(f) optionally, exchanging periodic heartbeat messages to verify synchronization.

\
wherein, for packet-based transport, the method further comprises deriving, at a receiver, an algorithm index and per-packet keying material as a deterministic function of a master session secret, the monotonic sequence identifier, and a mode-specific salt, thereby tolerating packet loss and out-of-order delivery.

---

### Claim 5: Method Claim - Algorithmic Chaffing and Winnowing

A method for defeating "Store Now, Decrypt Later" attacks through active deception, comprising:

(a) analyzing the entropy and timing characteristics of the legitimate encrypted traffic stream;

(b) generating synthetic decoy packets that act as cryptographic "chaff";

(c) injecting said decoy packets into the stream at a rate dynamically determined by at least one threat indicator;

(d) encrypting decoy packets with valid-looking authenticated headers and payloads that are non-operative for an intended application, wherein the decoy packets are constructed to be computationally indistinguishable from legitimate protected units to an external traffic observer based on observable characteristics, and wherein, in some embodiments, the decoy packets emulate protocol message shapes to increase adversary processing burden;

(e) ensuring decoy packets are discarded by the legitimate receiver while indistinguishable to an echelon-monitoring adversary.

---

### Claim 6: Method Claim - Adaptive Hopping

A method for adaptive hopping frequency adjustment comprising:

(a) monitoring threat indicators including at least one of:
   - (i) known cryptanalytic advances published against employed algorithms;
   - (ii) network anomaly detection suggesting active attack;
   - (iii) policy-based security level requirements;
   - (iv) available computational resources and power status;

(b) computing an adjusted hopping frequency based on threat indicators, wherein higher threat levels result in more frequent algorithm switching;

(c) communicating hopping frequency adjustments to peer nodes through in-band signaling;

(d) applying adjusted frequency to subsequent hopping intervals while maintaining schedule determinism.

---

### Claim 7: Non-Transitory Computer-Readable Medium

A non-transitory computer-readable medium storing instructions that, when executed by one or more processors of a communication node, cause the communication node to perform operations comprising:

(a) during establishment of a secure session with a peer communication node, deriving a session secret;

(b) for each protected unit of a sequence of protected units, deterministically deriving, as a function of at least the session secret and an integrity-protected monotonic sequence identifier for the protected unit, (i) an algorithm selection index identifying a selected cryptographic algorithm from an algorithm library comprising algorithms from at least two different hard-problem classes, and (ii) per-unit keying material;

(c) protecting the protected unit using the selected cryptographic algorithm and the per-unit keying material; and

(d) enforcing an orthogonality constraint by verifying a hard-problem class of a candidate next cryptographic algorithm against a hard-problem class of a prior selected cryptographic algorithm, and rejecting or skipping said candidate if it violates an orthogonality constraint.

---

### Claim 8: Method Claim - Data Fragmentation Strategy

A method for mitigating "Store Now, Decrypt Later" (SNDL) attacks comprising:

(a) fragmenting a contiguous data stream into a plurality of discrete time-slots;

(b) assigning a different cryptographic algorithm from the library to each sequential time-slot based on the hopping schedule;

(c) ensuring that no single mathematical hard problem protects more than a predetermined percentage of the total session data;

(d) whereby the compromise of any single underlying mathematical problem yields only non-contiguous fragments of the plaintext data, preventing reconstruction of the complete session context.

---

## Dependent Claims

### Claims 9-13: Algorithm Library Variations

**Claim 9.** The system of Claim 1, wherein the cryptographic primitives include at least one lattice-based construction and at least one code-based construction, ensuring protection against attacks targeting specific lattice vulnerabilities.

**Claim 10.** The system of Claim 1, wherein the algorithm library is updateable via secure over-the-air (OTA) updates to include new cryptographic primitives as they are standardized.

**Claim 11.** The system of Claim 1, wherein the algorithm library further comprises a symmetric algorithm (AES-256-GCM) used for bulk data encryption, with the dynamic hopping algorithms employed for frequent re-keying or key encapsulation.

**Claim 12.** The system of Claim 1, wherein the algorithm library comprises at least three mathematically independent constructions based on distinct hard problems (e.g., Lattice, Code, Isogeny, Multivariate, Hash-based).

**Claim 13.** The system of Claim 1, further comprising a hash-based signature scheme for authentication continuity across algorithm transitions.

### Claims 14-18: Synchronization Refinements

**Claim 14.** The system of Claim 2, wherein the temporal synchronization module implements an "overlap window" during algorithm transitions, wherein the receiving node is configured to accept decryption attempts using both the current algorithm and the immediate next algorithm for a defined duration, thereby tolerating network jitter and clock drift.


**Claim 15.** The method of Claim 4, wherein the bounded drift tolerance is configurable based on network conditions (e.g., between 100 milliseconds and 10 seconds).

**Claim 16.** The method of Claim 4, wherein overlap periods are calculated as a function of measured network latency and clock drift history.

**Claim 17.** The method of Claim 4, further comprising utilizing a network time synchronization protocol (e.g., NTP or PTP) to minimize clock drift.

**Claim 18.** The method of Claim 4, wherein transition boundaries are marked using authenticated sequence numbers resistant to replay attacks.

---

### Claims 19-23: Session Management

**Claim 19.** The method of Claim 3, wherein algorithm-specific keys are derived using:
$$K_i = \text{HKDF}(K_{master}, \text{algorithm\_id} \| \text{epoch} \| i)$$
where $i$ is the algorithm transition index.

**Claim 20.** The method of Claim 3, wherein session continuity is maintained by preserving authenticated encryption state across transitions.

**Claim 21.** The method of Claim 3, further comprising periodic re-keying within each algorithm's active period.

**Claim 22.** The method of Claim 3, wherein the hopping schedule includes algorithm-specific parameter variations (security levels, polynomial degrees).

**Claim 23.** The method of Claim 3, further comprising logging transition events for forensic analysis.

---

### Claims 24-28: Security Enhancements

**Claim 24.** The system of Claim 1, further comprising a secure enclave or trusted execution environment for storing the master session key and hopping schedule.

**Claim 25.** The method of Claim 5, wherein threat indicators include real-time feeds from cryptographic advisory services.

**Claim 26.** The system of Claim 1, wherein algorithm transition is triggered by either temporal schedule or detection of potential compromise, whichever occurs first.

**Claim 27.** The method of Claim 3, wherein the initial key exchange employs a hybrid classical/post-quantum mechanism for defense in depth.

**Claim 28.** The system of Claim 1, further comprising algorithm health monitoring that removes compromised algorithms from the rotation schedule.

---

### Claims 29-33: Implementation Variations

**Claim 29.** The system of Claim 1, implemented within a Transport Layer Security (TLS) extension.

**Claim 30.** The system of Claim 1, implemented within an Internet Protocol Security (IPsec) framework.

**Claim 31.** The system of Claim 1, wherein the communication nodes are Internet of Things (IoT) devices with constrained resources, and algorithm selection is optimized for computational efficiency.

**Claim 32.** The system of Claim 1, wherein the communication occurs over satellite links with high latency, and overlap windows are extended accordingly.

**Claim 33.** The system of Claim 1, integrated with quantum key distribution (QKD) for initial key establishment, with DMP-CHP providing algorithmic diversity for post-QKD encryption.

---

### Claims 34-36: High-Value Defensive Embodiments

**Claim 34.** The system of Claim 1, further comprising a holographic fragmentation module configured to apply a $(k,n)$ threshold secret sharing scheme to a plaintext payload to generate $n$ shares such that any subset of size $k$ is sufficient to reconstruct the plaintext payload, and such that any subset of fewer than $k$ shares yields no information about the plaintext payload under the threshold secret sharing scheme, and wherein at least a subset of the shares are protected using different cryptographic algorithms from the cryptographic algorithm library.

**Claim 35.** The system of Claim 1, further comprising a threat-adaptive scheduler configured to select at least one of (i) a hopping frequency, (ii) a hopping mode, or (iii) an algorithm library subset, as a function of at least one measured network condition selected from latency, jitter, packet loss, or reordering, thereby increasing hopping frequency upon detecting a condition indicative of increased attack risk.

**Claim 36.** The system of Claim 1, wherein derivation of the hopping schedule is cryptographically bound to a Physical Unclonable Function (PUF) response such that a device lacking access to the PUF response is unable to reproduce the hopping schedule.
---

## Claims Summary

| Claim Type | Count | Coverage |
|------------|-------|----------|
| Independent | 8 | System (broad), System (cognitive), Poly-Algorithmic Encryption, Synchronization, Chaffing, Adaptive, Computer-readable medium, Fragmentation |
| Algorithm Library | 6 | ML-KEM, McEliece, Symmetric, Multi-basis, Signatures, Weighting |
| Synchronization | 5 | HKDF, Drift, Overlap, NTP, Sequence numbers |
| Session Management | 5 | Key derivation, State, Re-keying, Parameters, Logging |
| Security | 5 | Enclave, Threat feeds, Dual trigger, Hybrid, Health monitoring |
| Implementation | 5 | TLS, IPsec, IoT, Satellite, QKD integration |
| Additional embodiments | 3 | Threshold secret sharing (HED), threat-adaptive hopping, PUF binding |
| **Total** | **36** | Comprehensive coverage |

---

*Document Version: 1.0*
*Last Updated: December 2024*

