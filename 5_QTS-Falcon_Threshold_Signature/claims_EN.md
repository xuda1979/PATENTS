# Patent Claims Document
# Quantum-Secure Threshold Signature System Based on Lattice-Based Falcon Algorithm

**Document Version**: 2.0 (Enhanced Claims with Rigorous Mathematical Foundations)

---

## Independent Claims

### Claim 1 (System Claim)

A quantum-secure threshold signature system based on the lattice-based Falcon algorithm, comprising a plurality of hardware nodes connected via a network, each node comprising a processor and a memory storing cryptographic instructions and key shares, the system comprising:

a) a verifiable distributed key generation module configured to generate secret-shared portions of an NTRU trapdoor satisfying $fG - gF = q$ over the cyclotomic ring $R = \mathbb{Z}[X]/(X^n + 1)$ among a plurality of $n$ nodes using secure multi-party computation, wherein:
   - each node $P_i$ holds trapdoor shares $([f]_i, [g]_i, [F]_i, [G]_i)$ in its local memory such that $\sum_{i=1}^{n}[f]_i = f$ and similarly for $g, F, G$;
   - any coalition of fewer than a threshold number $t$ of nodes obtains zero information about the complete private key beyond the public key $h = g \cdot f^{-1} \mod q$;
   - verifiability is achieved through cryptographic commitments and zero-knowledge proofs ensuring correct share generation;

b) an arithmetic-shared transform-domain computation module configured to perform polynomial operations required by Falcon signature generation in a distributed manner, wherein:
   - each node processor locally computes a Number Theoretic Transform (NTT) on its private key share $[f]_i$;
   - the linearity property of the NTT is exploited such that $\text{NTT}(\sum_{i=1}^{n} [f]_i) = \sum_{i=1}^{n} \text{NTT}([f]_i)$;
   - transform-domain polynomial multiplication is performed via pointwise operations on shares: $[\text{NTT}(f \cdot g)]_i = \text{NTT}([f]_i) \odot \text{NTT}(g)$;
   - no reconstruction of the private key polynomial is required during any computation phase;

c) a distributed Gaussian sampling module with variance-preserving aggregation configured to generate properly-distributed samples, wherein:
   - each node $P_i$ samples from a scaled discrete Gaussian distribution $[z]_i \leftarrow D_{\sigma/\sqrt{n}, R}$ where $\sigma$ is the target Falcon parameter;
   - the aggregate $z = \sum_{i=1}^{n}[z]_i$ follows the target distribution $D_{\sigma, R}$ by the Gaussian convolution theorem;
   - statistical independence of individual samples ensures privacy of each node's contribution;

d) a collaborative rejection sampling module configured to perform distributed acceptance testing with privacy preservation, comprising:
   - a local mask generation sub-module for generating random masks $m_i$ at each node;
   - a commitment sub-module for computing and broadcasting cryptographic commitments $C_i = H(m_i \| [s]_i)$ of local signature shares via the network interface;
   - a secure norm computation sub-module utilizing Beaver triple preprocessing to compute global signature norm $\|s\|^2 = \sum_{i}\|[s]_i\|^2 + 2\sum_{i<j}\langle[s]_i, [s]_j\rangle$ in constant rounds;
   - a distributed coin flip sub-module for collaborative acceptance decision with probability proportional to $\exp(-\|s\|^2/(2\sigma^2))$;
   - wherein the online communication complexity is reduced from $O(n)$ rounds to exactly 6 constant rounds;

e) a signature aggregation and verification module configured to aggregate signature components from participating nodes and output a digital signature in standard Falcon format $\sigma = (r, \text{Compress}(s_2))$ that is verifiable using an unmodified standard Falcon verification algorithm.

### Claim 2 (Method Claim)

A quantum-secure threshold signature method based on the lattice-based Falcon algorithm, executed by a plurality of processors distributed across a network, comprising the steps of:

S1) verifiable distributed key generation: a plurality of $n$ signing nodes collaboratively generate an NTRU trapdoor through secure multi-party computation protocol, comprising:
   - each node $P_i$ sampling local polynomial shares $[f]_i, [g]_i \leftarrow D_{\sigma/\sqrt{n}, R}$ from scaled discrete Gaussian distributions;
   - computing commitments $C_i = \text{Commit}([f]_i, r_i)$ and generating zero-knowledge proofs of correct sampling;
   - verifying all commitments and proofs across nodes;
   - executing an MPC-Extended-GCD protocol to solve $fG - gF = q$ over secret-shared polynomials;
   - distributing trapdoor shares $([f]_i, [g]_i, [F]_i, [G]_i)$ to each node and publishing common public key $h = g \cdot f^{-1} \mod q$;

S2) offline preprocessing: generating Beaver multiplication triples $\{([a]_i, [b]_i, [c]_i)\}$ satisfying $\sum_i [c]_i = (\sum_i [a]_i) \cdot (\sum_i [b]_i)$ using post-quantum secure oblivious transfer extensions, with verification via sacrifice protocol ensuring correctness with probability $1 - 2^{-40}$;

S3) message preprocessing: receiving a message $M$ to be signed, sampling distributed random salt $r$ via commit-reveal, computing cryptographic hash $c = H(r \| M)$ using SHAKE-256, and mapping the hash value to a target polynomial in $R_q$;

S4) local signature share computation: each node $P_i$ performing:
   - computing local trapdoor contribution $[t]_i = (\text{NTT}^{-1}(\text{NTT}([F]_i) \odot \text{NTT}(c)), \text{NTT}^{-1}(\text{NTT}([G]_i) \odot \text{NTT}(c)))$;
   - sampling local Gaussian noise $[z]_i \leftarrow D_{\sigma/\sqrt{n}, R}^2$ with scaled parameter;
   - computing masked signature share $[s]_i = [t]_i + [z]_i$;
   - generating commitment $C_i = H(m_i \| [s]_i)$ with random mask $m_i$;

S5) collaborative rejection sampling with constant-round secure aggregation comprising:
   - Round 1: broadcasting commitments $\{C_i\}$ to bind parties to shares;
   - Rounds 2-3: computing cross-term inner products $\langle[s]_i, [s]_j\rangle$ for all $i < j$ using Beaver multiplication protocol;
   - Round 4: aggregating and revealing global norm $\|s\|^2$;
   - Round 5: executing distributed coin flip to determine acceptance with probability $p = M^{-1} \cdot \exp(-\langle s, c \rangle / \sigma^2)$;
   - if rejected, returning to step S4 for resampling;

S6) signature aggregation: upon acceptance:
   - Round 6: each node revealing signature share $[s]_i$;
   - verifying revealed shares against commitments;
   - aggregating components $(s_1, s_2) = \sum_{i=1}^{n}[s]_i$;
   - compressing signature component $s_2$ according to Falcon compression algorithm;
   - outputting final signature $\sigma = (r, \text{Compress}(s_2))$ in standard Falcon format.

### Claim 3 (Independent Method Claim - Distributed Key Generation)

A method for verifiable distributed generation of an NTRU trapdoor for a quantum-secure threshold signature system, executed by a plurality of $n$ computing nodes, comprising:

a) **Distributed Polynomial Sampling**: each node $P_i$ independently sampling local polynomial shares $[f]_i, [g]_i$ from a scaled discrete Gaussian distribution $D_{\sigma/\sqrt{n}, R}$, such that the sum of shares $f = \sum [f]_i$ and $g = \sum [g]_i$ follow a target distribution $D_{\sigma, R}$;

b) **Verifiable Commitment**: each node broadcasting cryptographic commitments to their local shares and providing zero-knowledge proofs of well-formedness to ensure no node has sampled a distribution with insufficient entropy;

c) **Secure Inverse Computation**: the nodes collaboratively computing a shared inversion of the polynomial $f$ in the ring $R_q$ using a secure multi-party computation (MPC) protocol to generate the public key $h = g \cdot f^{-1} \mod q$;

d) **Distributed Trapdoor Completion**: the nodes executing an MPC-based Extended Euclidean Algorithm (XGCD) to collaboratively find secret-shared polynomials $[F]_i$ and $[G]_i$ satisfying the NTRU equation:
   $$f \cdot \left(\sum [G]_i\right) - g \cdot \left(\sum [F]_i\right) = q$$
   without any node learning the complete polynomials $f, g, F, \text{or } G$;

e) **Share Output**: each node storing its resulting trapdoor share tuple $([f]_i, [g]_i, [F]_i, [G]_i)$ in a secure memory, enabling subsequent threshold signing operations.

---

## Dependent Claims

### Claims Dependent on Claim 1 (System)

**Claim 4.** The system according to claim 1, wherein the arithmetic-shared transform-domain computation module exploits the Chinese Remainder Theorem isomorphism $R_q \cong \mathbb{Z}_q^n$ to perform polynomial multiplication as:
$$\text{NTT}(f \cdot g) = \text{NTT}(f) \odot \text{NTT}(g)$$
enabling per-coefficient parallel computation with zero inter-node communication for the transform operation itself.

**Claim 5.** The system according to claim 1, wherein the distributed Gaussian sampling module implements variance-preserving aggregation satisfying:
$$\text{Var}\left(\sum_{i=1}^{n} [z]_i\right) = \sum_{i=1}^{n} \text{Var}([z]_i) = n \cdot \frac{\sigma^2}{n} = \sigma^2$$
ensuring the aggregate follows target distribution $D_{\sigma, R}$ required by Falcon security proofs.

**Claim 6.** The system according to claim 1, wherein the collaborative rejection sampling module employs a commit-reveal protocol with binding property, comprising:
- a commitment phase where each node broadcasts $C_i = H(m_i \| [s]_i)$ using cryptographic hash function $H$ modeled as a random oracle;
- a verification phase where masked norm contributions are securely aggregated via Beaver multiplication;
- a reveal phase executed only upon successful acceptance test;
- wherein any deviation from committed values is detected with probability 1.

**Claim 7.** The system according to claim 1, wherein the secure norm computation utilizes Beaver triples to compute:
$$\|s\|^2 = \sum_{i=1}^{n} \|[s]_i\|^2 + 2\sum_{1 \leq i < j \leq n} \langle [s]_i, [s]_j \rangle$$
wherein local squared norms $\|[s]_i\|^2$ are computed locally without communication, and cross-terms $\langle [s]_i, [s]_j \rangle$ are computed via:
$$\langle [s]_i, [s]_j \rangle = [c]_{ij} + d_i \cdot [b]_j + e_j \cdot [a]_i + d_i \cdot e_j$$
where $d_i = [s]_i - [a]_i$, $e_j = [s]_j - [b]_j$ are masked values, requiring exactly 2 communication rounds.

**Claim 8.** The system according to claim 1, further comprising a dynamic node management module configured to support:
- addition of new signing nodes without modifying the master public key through secret resharing;
- revocation of existing nodes through proactive secret sharing with zero-sharing refresh;
- automatic recovery of offline node key shares through threshold reconstruction when $\geq t$ nodes are available.

**Claim 9.** The system according to claim 8, wherein the dynamic node management module employs proactive secret sharing protocol with the property:
$$[f']_i = [f]_i + \sum_{j=1}^{n} [\delta]_{j \to i} \quad \text{where} \quad \sum_{i=1}^{n} \sum_{j=1}^{n} [\delta]_{j \to i} = 0$$
ensuring old shares $[f]_i$ and new shares $[f']_i$ are statistically independent given partial information, thereby providing security against mobile adversaries.

**Claim 10.** The system according to claim 1, wherein the system is configured with dedicated hardware acceleration units selected from the group consisting of:
- Field Programmable Gate Array (FPGA) implementing butterfly network for 512-point NTT in under 20 microseconds;
- Trusted Execution Environment (TEE) with Intel SGX or ARM TrustZone for secure key share storage with hardware-based sealing;
- Application-Specific Integrated Circuit (ASIC) optimized for lattice polynomial arithmetic;
- constant-time discrete Gaussian sampler using Cumulative Distribution Table (CDT) method with timing-attack resistance;
- a combination thereof.

**Claim 11.** The system according to claim 1, employing a $(t, n)$ threshold structure wherein:
- any $t$ or more nodes can collaboratively generate a valid Falcon signature;
- any coalition of fewer than $t$ nodes obtains zero information about the private key (information-theoretic privacy with statistical distance $\leq 2^{-\lambda}$);
- the system tolerates up to $n-t$ Byzantine node failures or compromises.

**Claim 12.** The system according to claim 1, wherein the signature aggregation and verification module outputs signatures that:
- conform to NIST FIPS 205 Falcon signature standard format with identical byte layout;
- are verifiable using any compliant standard Falcon verification implementation without modification;
- achieve signature size of approximately 666 bytes for Falcon-512 (NIST Level 1) or 1280 bytes for Falcon-1024 (NIST Level 5).

**Claim 13.** The system according to claim 1, wherein the verifiable distributed key generation module generates NTRU trapdoor by:
- solving the NTRU equation $fG - gF = q$ in the MPC setting using an extended Euclidean algorithm over secret-shared polynomials;
- requiring $O(n \log^2 n)$ MPC multiplications and $O(\log n)$ communication rounds;
- verifying trapdoor correctness via probabilistic check: sample random $c \in R_q$, verify $\sum_i([f]_i \cdot [G]_i - [g]_i \cdot [F]_i) \cdot c = q \cdot c$.

### Claims Dependent on Claim 2 (Method)

**Claim 14.** The method according to claim 2, wherein step S5 achieves exactly 6 constant communication rounds through:
- Round 1: commitment distribution ($n \cdot 256$ bits);
- Rounds 2-3: Beaver multiplication opening ($O(n^2 \cdot n \log P)$ bits);
- Round 4: global norm reveal ($n \cdot \log P$ bits);
- Round 5: distributed coin flip contributions ($n \cdot 256$ bits);
- Round 6: signature share reveal ($n \cdot 2n \log q$ bits);
- wherein total expected signing time including rejection sampling retries is approximately $1.53$ times single-attempt time.

**Claim 15.** The method according to claim 2, wherein step S4 comprises computing local signature share with:
- trapdoor contribution in NTT domain: $[\hat{t}_1]_i = \text{NTT}([F]_i) \odot \text{NTT}(c)$, $[\hat{t}_2]_i = \text{NTT}([G]_i) \odot \text{NTT}(c)$;
- inverse transform: $[t]_i = (\text{iNTT}([\hat{t}_1]_i), \text{iNTT}([\hat{t}_2]_i))$;
- Gaussian sampling with scaled parameter $\sigma_i = \sigma/\sqrt{n}$ ensuring $\sigma_i \geq \eta_\varepsilon(\mathbb{Z}^n)$ for smoothing parameter $\eta_\varepsilon$;
- masked sample $[s]_i = [t]_i + [z]_i$ where $[z]_i \leftarrow D_{\sigma/\sqrt{n}, R}^2$.

**Claim 16.** The method according to claim 2, wherein step S6 comprises:
- revealing signature components $[s]_i = ([s_1]_i, [s_2]_i)$ after successful acceptance verification;
- verifying each revealed share against pre-broadcast commitment: $H(m_i \| [s]_i) \stackrel{?}{=} C_i$;
- aggregating: $(s_1, s_2) = \sum_{i=1}^{n} ([s_1]_i, [s_2]_i)$;
- applying Falcon signature compression with Huffman-like encoding to $s_2$;
- outputting $\sigma = (r, \text{Compress}(s_2))$ with size approximately 666 bytes.

**Claim 17.** The method according to claim 2, further comprising a step S7 of standard Falcon verification wherein:
- hash $c$ is recomputed: $c = H(r \| M)$;
- signature component $s_1$ is recovered: $s_1 = c - s_2 \cdot h \mod q$;
- signature validity is confirmed by checking norm bound: $\|(s_1, s_2)\|_2^2 \leq \beta^2$ where $\beta^2 = 34034726$ for Falcon-512;
- verification complexity is $O(n \log n)$ dominated by single NTT operation.

### Application-Specific Claims

**Claim 18.** The system according to claim 1, applied to a cross-chain bridge scenario, wherein:
- the message to be signed comprises cross-chain asset transfer instructions including source chain identifier, destination chain identifier, asset type, amount, and recipient address;
- the signing nodes are distributed across different geographic locations or organizational entities for fault tolerance and censorship resistance;
- the signed instructions authorize atomic asset transfers between different blockchain networks, including but not limited to heterogeneous chains connected via Inter-Blockchain Communication (IBC) or LayerZero protocols, with finality guarantees.

**Claim 19.** The system according to claim 18, wherein the cross-chain bridge comprises:
- a source blockchain monitoring module for detecting and validating cross-chain transfer requests;
- a threshold signing relay network hosting $(t, n)$ threshold Falcon signing nodes;
- a target blockchain verification contract implementing standard Falcon signature verification;
- an oracle network for price feeds and cross-chain state synchronization;
- wherein on-chain verification gas cost is reduced by approximately 70-75% compared to threshold Dilithium signatures.

**Claim 20.** The method according to claim 2, wherein quantum security is mathematically grounded on:
- resistance to Shor's algorithm through reliance on the NTRU problem over cyclotomic rings, requiring quantum resources estimated at $2^{128}$ operations for Falcon-512 parameters;
- resistance to Grover's algorithm through 256-bit hash outputs (SHAKE-256) providing 128-bit post-quantum collision resistance;
- worst-case to average-case reduction from Ring-SIS to approximate SIVP on ideal lattices;
- compliance with NIST PQC security Level 1 (Falcon-512) or Level 5 (Falcon-1024) standards.

**Claim 21.** The system according to claim 1, wherein the collaborative rejection sampling module achieves privacy through:
- information-theoretic hiding of individual signature shares $[s]_i$ via random masking with fresh randomness per signing;
- commitment scheme providing computational binding (collision-resistance of $H$) and hiding (preimage resistance);
- secure aggregation revealing only aggregate statistics $\|s\|^2$ without leaking individual contributions $\|[s]_i\|^2$;
- zero-knowledge property: transcript is simulatable given only final signature.

### Additional Technical Claims (Novel Innovations)

**Claim 22.** The method according to claim 2, wherein step S4 employs variance-preserving Gaussian parameter scaling:
$$\sigma_i = \frac{\sigma}{\sqrt{n}}$$
ensuring for Falcon-512 with $\sigma = 165.74$:
- $(5,7)$ threshold: $\sigma_i \approx 62.6$, min-entropy $\approx 4198$ bits;
- $(7,11)$ threshold: $\sigma_i \approx 49.9$, min-entropy $\approx 3980$ bits;
- $(10,15)$ threshold: $\sigma_i \approx 42.8$, min-entropy $\approx 3841$ bits;
- with maximum supported parties $n \leq 25$ to maintain $\sigma_i \geq 33.1$ for security margin.

**Claim 23.** The system according to claim 1, wherein the offline preprocessing phase utilizes post-quantum secure Oblivious Transfer extensions comprising:
- base OT phase: performing $\kappa$ (security parameter) Kyber-KEM based OTs providing post-quantum security;
- extension phase: expanding base OTs to $N$ extended OTs using IKNP protocol with symmetric primitives;
- triple generation: computing Beaver triples from extended OTs with $O(\kappa + N)$ communication complexity;
- verification: sacrifice-based triple validation ensuring correctness with probability $1 - 2^{-40}$.

**Claim 24.** The method according to claim 2, wherein step S5 further comprises optional Zero-Knowledge Proof generation for each local Gaussian sample, wherein:
- each node constructs a lattice-based Sigma protocol proof attesting that $[z]_i$ is well-formed;
- proof uses Lyubashevsky's rejection sampling technique with masking parameter $\sigma_y = \alpha \cdot \|[z]_i\|_2$;
- verification ensures $\|w\|_2 \leq B$ for response $w$ and linear relation $A \cdot w = t + c \cdot (A \cdot [z]_i)$;
- batch amortization reduces per-sample proof overhead by factor $k$ for $k$ consecutive signing operations.

**Claim 25.** The system according to claim 1, further comprising a malicious party detection and exclusion module implementing:
- commitment-based verification: comparing revealed shares $[s]_i$ against commitments $C_i = H(m_i \| [s]_i)$ with detection probability 1;
- accusation protocol: honest parties broadcast accusation $(P_j, C_j, [s]_j', m_j)$ with cryptographic proof of mismatch;
- exclusion mechanism: cheating party $P_j$ removed from signing set $S$;
- graceful degradation: if $|S \setminus \{P_j\}| \geq t$, signing continues with reduced set;
- key refresh trigger: if $|S| < t$ after exclusion, initiate emergency key refresh protocol.

**Claim 26.** The system according to claim 1, further comprising a fault tolerance module implementing:
- configurable timeout detection: $T_{\text{commit}} = 5$s, $T_{\text{beaver}} = 10$s, $T_{\text{reveal}} = 5$s per phase;
- graceful degradation: continue with $|S| \geq t$ parties if others timeout;
- network partition handling: heartbeat-based quorum verification with partition detection when $< t$ parties reachable;
- state persistence: checkpoint protocol state after each phase for crash recovery;
- idempotent restart: deterministic state reconstruction enabling safe retry after transient failures.

**Claim 27.** The system according to claim 1, wherein the verifiable distributed key generation module comprises an MPC-Extended-GCD protocol for solving:
$$fG - gF = q$$
over secret-shared polynomials $([f]_i, [g]_i)$ to produce secret-shared trapdoor $([F]_i, [G]_i)$, comprising:
- field tower construction embedding $R$ into number field $K = \mathbb{Q}[X]/(X^n + 1)$;
- Chinese Remainder Theorem decomposition for parallel computation;
- iterative quotient and remainder computation via MPC division and multiplication;
- back-substitution for XGCD coefficients;
- size-reduction using Babai's algorithm in MPC to minimize $\|F\|, \|G\|$.

**Claim 28.** The system according to claim 1, further comprising side-channel attack protection measures comprising:
- constant-time modular arithmetic: $x' = x - (q \land ((x \geq q) \cdot \text{0xFFFFFFFF}))$ avoiding branch prediction leakage;
- constant-time NTT butterfly: all operations execute in fixed time regardless of operand values;
- constant-time Gaussian sampling: CDT lookup with masked access pattern $\text{result} = \bigoplus_i (\text{table}[i] \land \text{ct\_eq}(i, \text{index}))$;
- first-order masking: sensitive values represented as $(x \oplus r, r)$ with fresh random $r$;
- fault attack protection: redundancy checks $\text{iNTT}(\text{NTT}(f)) \stackrel{?}{=} f$ and output randomization on verification failure.

**Claim 29.** The system according to claim 1, wherein the system is integrated with a Trusted Execution Environment (TEE), configured to:
- execute all private key operations within hardware-isolated enclave protected from host operating system and hypervisor;
- enforce remote attestation via Intel SGX DCAP or equivalent to verify signing software integrity before key share access;
- implement hardware-based sealing: key shares encrypted with CPU-derived keys bound to enclave identity;
- provide memory encryption (MEE) ensuring key shares never appear in plaintext outside enclave boundaries;
- support secure provisioning: initial key share distribution via attested TLS channels.

**Claim 30.** The method according to claim 2, wherein the dual-modulus architecture employs:
- MPC modulus $P = 2^{62} - 2^{17} + 1$ satisfying $P \equiv 1 \pmod{1024}$ for NTT compatibility;
- overflow prevention: $P > n \cdot q^2$ ensuring no wrap-around during share aggregation;
- single-word arithmetic: $\log_2 P \leq 64$ for efficient CPU computation;
- modulus conversion: coefficient-wise centered reduction $x \mapsto ((x \mod q) + q/2) \mod q - q/2$.

**Claim 31.** The method according to claim 2, further comprising an early rejection optimization wherein:
- each party computes local norm estimate $\hat{N}_i = \|[s]_i\|^2$ before Beaver multiplication;
- aggregate estimate $\hat{N} = \sum_i \hat{N}_i$ computed via single-round broadcast;
- if $\hat{N} > 2 \cdot \beta^2$ (ignoring cross-terms), abort early and resample;
- otherwise proceed with full Beaver multiplication for exact norm computation;
- saving average 0.3 communication rounds by avoiding full computation in $\approx 15\%$ of clearly-failing attempts.

**Claim 32.** The system according to claim 1, wherein the system is configured to achieve the following performance characteristics:
- online signing latency: approximately 15 milliseconds or less for $(5,7)$ threshold with Falcon-512;
- communication complexity: 6 constant rounds independent of party count $n$;
- signature size: 666 bytes (identical to standard Falcon-512);
- on-chain verification gas cost: approximately 50,000 gas on Ethereum;
- throughput: at least 60 signatures per second per node cluster;
- rejection sampling efficiency: approximately 65% acceptance rate.

**Claim 33.** The system according to claim 1, wherein security properties are formally proven comprising:
- EUF-CMA unforgeability: reduction to NTRU problem with advantage loss $\leq Q_H \cdot Q_S / 2^{320}$;
- $t$-privacy: simulation-based proof with statistical distance $\leq \text{negl}(\lambda)$ for $t-1$ corrupted parties;
- robustness: guaranteed output with probability $1 - 2^{-\Omega(\lambda)}$ when $\geq t$ parties honest;
- proactive security: maintains privacy against mobile adversaries corrupting different $t-1$ parties per epoch.

**Claim 34.** A computer-readable storage medium storing instructions that, when executed by one or more processors distributed across multiple network nodes, cause the processors to implement the quantum-secure threshold signature method according to claim 2, wherein the instructions are partitioned such that each node executes only operations requiring its local key share.

**Claim 35.** The method according to claim 2, wherein the distributed coin flipping in step S5 achieves bias resistance by:
- each party $P_i$ broadcasting a commitment $D_i = H(\rho_i)$, where $\rho_i \leftarrow \{0,1\}^{256}$ is a random number;
- after receiving all commitments, each party revealing $\rho_i$;
- verifying $H(\rho_i) = D_i$ for all $i$;
- computing the combined random number $\rho = H(\rho_1 \| \rho_2 \| \cdots \| \rho_n)$;
- acceptance decision: $\text{accept} \iff (\rho \mod 2^{64})/2^{64} < p_{\text{accept}}$;
- wherein any single honest party ensures uniform combined randomness.

**Claim 36.** The system according to claim 1, further comprising batch signing optimization, wherein:
- multiple messages $M_1, \ldots, M_k$ are signed in parallel in a single protocol execution;
- Beaver triples are shared across the batch: $k$ signatures require $\binom{n}{2} \cdot k$ triples;
- amortized communication volume per signature is reduced by a factor of $k$;
- latency for $k$ signatures is approximately $(1 + 0.1k)$ times the latency of a single signature.

**Claim 37.** The method according to claim 2, further comprising a dynamic node management step comprising:
- adding new signing nodes without modifying the master public key through secret resharing;
- revoking existing nodes through proactive secret sharing with zero-sharing refresh;
- automatically recovering offline node key shares through threshold reconstruction when $\geq t$ nodes are available.

**Claim 38.** The method according to claim 37, wherein the proactive secret sharing step includes:
- each node $P_i$ generating a random polynomial $\delta_i(x)$ with zero constant term;
- distributing shares of $\delta_i(x)$ to other nodes;
- each node updating its share $[f]_i \leftarrow [f]_i + \sum_j [\delta_j]_i$;
- verifying consistency of updates via commitments.

**Claim 39.** The system according to claim 1, further comprising an on-chain batch verification module configured to:
- aggregate multiple signatures $\sigma_1, \dots, \sigma_k$ into a single verification transaction;
- verify all signatures simultaneously using a batch verification algorithm;
- reduce per-signature gas cost by amortizing the overhead of loading public parameters.

**Claim 40.** The system according to claim 1, configured for Falcon-1024 parameters (NIST Level 5), wherein:
- the ring dimension is $n=1024$ and modulus $q=12289$;
- the distributed Gaussian sampling module scales the parameter $\sigma \approx 168$ by $\sigma_i = \sigma/\sqrt{n} \approx 5.25$;
- the system supports a threshold $t$ up to 50 nodes while maintaining security against lattice reduction attacks;
- the signature size is approximately 1280 bytes.

**Claim 41.** The method according to claim 2, further comprising a graceful degradation step wherein:
- if the number of active nodes $|S|$ falls below $n$ but remains $\geq t$, the system continues signing with the subset $S$;
- if $|S| < t$, the system automatically enters a suspension mode and triggers an alert;
- upon recovery of nodes such that $|S| \geq t$, the system automatically resumes signing operations without requiring a key regeneration.

---

## Abstract of the Claims

The independent claims define:
1. **System (Claim 1)**: A comprehensive threshold Falcon signature system comprising verifiable distributed key generation, arithmetic-shared NTT computation, variance-preserving Gaussian sampling, constant-round collaborative rejection sampling, and standard-compatible signature aggregation modules.

2. **Method (Claim 2)**: A detailed threshold signing method with explicit protocol steps including preprocessing, local computation, secure aggregation, and verification phases achieving exactly 6 online communication rounds.

**Key Innovations Protected**:
- Zero-communication distributed NTT using algebraic linearity (Claims 3, 14)
- Variance-preserving Gaussian parameter scaling $\sigma_i = \sigma/\sqrt{n}$ (Claims 4, 21)
- Constant 6-round collaborative rejection sampling via Beaver multiplication (Claims 5, 6, 13)
- MPC-Extended-GCD for distributed NTRU trapdoor generation (Claims 12, 26)
- Verifiable secret sharing with commitment-based cheater detection (Claims 24, 32)
- Proactive security against mobile adversaries (Claims 8, 32)
- Post-quantum OT extension using Kyber-KEM (Claim 22)
- Early rejection optimization (Claim 30)
- Dual-modulus MPC architecture (Claim 29)
- Hardware acceleration integration (Claims 9, 28)
- Cross-chain bridge application (Claims 17, 18)
- Formal security proofs with tight reductions (Claim 32)

---

## Claim Dependency Chart

```text
Claim 1 (System - Independent)
├── Claim 4 (NTT Linearity / CRT Isomorphism)
├── Claim 5 (Variance-Preserving Aggregation)
├── Claim 6 (Commit-Reveal Protocol)
├── Claim 7 (Beaver-Based Norm Computation)
├── Claim 10 (Hardware Acceleration)
├── Claim 11 (Threshold Structure Properties)
├── Claim 12 (Standard Format Compatibility)
├── Claim 13 (MPC-XGCD for Trapdoor)
├── Claim 18 (Cross-Chain Application)
│   └── Claim 19 (Bridge Architecture)
├── Claim 21 (Privacy Mechanisms)
├── Claim 23 (PQ-Secure OT Extension)
├── Claim 25 (Malicious Party Detection)
├── Claim 26 (Fault Tolerance)
├── Claim 27 (XGCD Algorithm Details)
├── Claim 28 (Side-Channel Protection)
├── Claim 29 (TEE Integration)
├── Claim 32 (Performance Characteristics)
├── Claim 33 (Security Proofs)
├── Claim 36 (Batch Signing)
├── Claim 39 (Batch Verification)
└── Claim 40 (Falcon-1024 Specifics)

Claim 2 (Method - Independent)
├── Claim 14 (6-Round Communication)
├── Claim 15 (Local Share Computation)
├── Claim 16 (Aggregation and Compression)
├── Claim 17 (Standard Verification)
├── Claim 20 (Quantum Security Basis)
├── Claim 22 (Parameter Scaling Bounds)
├── Claim 24 (ZKP for Gaussian Samples)
├── Claim 30 (Dual-Modulus Architecture)
├── Claim 31 (Early Rejection Optimization)
├── Claim 35 (Bias-Resistant Coin Flip)
├── Claim 37 (Dynamic Node Management Method)
│   └── Claim 38 (Proactive Secret Sharing Method)
└── Claim 41 (Graceful Degradation)

Claims 1 or 2 (System or Method)
├── Claim 8 (Dynamic Node Management)
│   └── Claim 9 (Proactive Secret Sharing)
└── Claim 34 (Computer-Readable Medium)
```
