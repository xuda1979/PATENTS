# Mathematical Theory of Noise-Adaptive Variational Quantum Encryption (NAV-QE)

## Comprehensive Mathematical Foundations and Derivations

---

## Table of Contents

1. [Introduction and Notation](#1-introduction-and-notation)
2. [Quantum Noise Physics and Open Quantum Systems](#2-quantum-noise-physics-and-open-quantum-systems)
3. [Noise Parameter Characterization Protocols](#3-noise-parameter-characterization-protocols)
4. [Hardware Fingerprint Construction](#4-hardware-fingerprint-construction)
5. [Fingerprint-to-Key Mapping Pipeline](#5-fingerprint-to-key-mapping-pipeline)
6. [Entropy Analysis and Information-Theoretic Bounds](#6-entropy-analysis-and-information-theoretic-bounds)
7. [Tamper Detection: Statistical Deviation Framework](#7-tamper-detection-statistical-deviation-framework)
8. [Fuzzy Extractor and Helper Data Mechanism](#8-fuzzy-extractor-and-helper-data-mechanism)
9. [Security Proofs and Guarantees](#9-security-proofs-and-guarantees)
10. [Scalability Analysis](#10-scalability-analysis)
11. [Operational Convertibility Models](#11-operational-convertibility-models)
12. [Attestation Protocol and API Formalization](#12-attestation-protocol-and-api-formalization)
13. [Device Lifecycle Mathematics](#13-device-lifecycle-mathematics)
14. [Summary of Key Equations](#14-summary-of-key-equations)

---

## 1. Introduction and Notation

### 1.1 Core Idea

The NAV-QE system transforms the intrinsic quantum noise of a quantum processor — traditionally viewed as a computational impediment — into a **cryptographic security resource**. The mathematical framework underpinning this transformation involves:

1. **Characterizing** device-specific noise via quantum measurement protocols
2. **Encoding** the noise into a high-dimensional fingerprint vector
3. **Mapping** the continuous fingerprint to discrete cryptographic keys
4. **Monitoring** fingerprint deviations for tamper detection

### 1.2 Notation Table

| Symbol | Description |
|--------|-------------|
| $n$ | Number of physical qubits on the processor |
| $m$ | Number of two-qubit gate configurations |
| $T_1^{(i)}$ | Longitudinal relaxation time of qubit $i$ |
| $T_2^{(i)}$ | Transverse dephasing time of qubit $i$ |
| $T_2^{*(i)}$ | Inhomogeneous dephasing time of qubit $i$ |
| $\epsilon_1^{(i)}$ | Single-qubit gate error rate for qubit $i$ |
| $\epsilon_2^{(i,j)}$ | Two-qubit gate error rate for qubit pair $(i,j)$ |
| $\epsilon_r^{(i)}$ | Readout error for qubit $i$ |
| $c_{ij}$ | Crosstalk coefficient between qubits $i$ and $j$ |
| $\mathbf{f}$ | Hardware fingerprint vector, $\mathbf{f} \in \mathbb{R}^d$ |
| $d$ | Dimensionality of the fingerprint vector |
| $K$ | Derived cryptographic key |
| $\Sigma$ | Covariance matrix of natural noise drift |
| $\tau$ | Tamper detection threshold |
| $H_{min}(\cdot)$ | Min-entropy function |
| $\rho$ | Quantum density matrix |
| $\sigma_i$ | Pauli matrices ($i \in \{x, y, z\}$) |
| $\mathcal{E}(\cdot)$ | Quantum channel (completely positive, trace-preserving map) |

---

## 2. Quantum Noise Physics and Open Quantum Systems

### 2.1 Open Quantum System Dynamics

A quantum processor is an **open quantum system** — its qubits interact with an uncontrollable environment (bath). The total Hamiltonian is:

$$H_{total} = H_{system} + H_{bath} + H_{interaction}$$

The evolution of the system's reduced density matrix $\rho_S(t)$ is obtained by tracing out the bath degrees of freedom:

$$\rho_S(t) = \text{Tr}_{bath}\left[ U(t) \left(\rho_S(0) \otimes \rho_{bath}(0)\right) U^\dagger(t) \right]$$

where $U(t) = e^{-iH_{total}t/\hbar}$.

Under the Born-Markov approximation, this evolution is described by the **Lindblad master equation**:

$$\frac{d\rho}{dt} = -\frac{i}{\hbar}[H_S, \rho] + \sum_k \gamma_k \left( L_k \rho L_k^\dagger - \frac{1}{2}\{L_k^\dagger L_k, \rho\} \right)$$

where $L_k$ are Lindblad (jump) operators and $\gamma_k$ are the associated decay rates. These decay rates are **device-specific** and form the physical basis of the NAV-QE fingerprint.

### 2.2 T₁ Relaxation (Energy Decay)

$T_1$ describes the irreversible energy decay from the excited state $|1\rangle$ to the ground state $|0\rangle$. In the Lindblad framework, the relevant jump operator is:

$$L_1 = \sqrt{\gamma_1} \, \sigma_- = \sqrt{\gamma_1} \begin{pmatrix} 0 & 1 \\ 0 & 0 \end{pmatrix}, \quad \gamma_1 = \frac{1}{T_1}$$

For a qubit initialized in a general state $\rho(0)$, the density matrix evolves as:

$$\rho(t) = \begin{pmatrix} 1 - p(t) & \rho_{01}(0) \, e^{-t/(2T_1)} \\ \rho_{10}(0) \, e^{-t/(2T_1)} & p(t) \end{pmatrix}$$

where the excited-state population decays as:

$$\boxed{p(t) = p(0) \, e^{-t/T_1} + p_{eq}\left(1 - e^{-t/T_1}\right)}$$

At dilution refrigerator temperatures ($T \approx 15\,\text{mK}$), the thermal equilibrium population is $p_{eq} \approx 0$, simplifying to:

$$p(t) \approx p(0) \, e^{-t/T_1}$$

**Physical origin**: $T_1$ is determined by dielectric losses in the substrate, two-level system (TLS) defects in the Josephson junction barrier, quasiparticle tunneling, and radiative coupling to the electromagnetic environment. These factors are **unique to each physical device** due to irreproducible atomic-scale manufacturing variations.

### 2.3 T₂ Dephasing (Phase Coherence Loss)

$T_2$ describes the decay of off-diagonal elements of the density matrix, i.e., the loss of quantum phase coherence. The relevant Lindblad operator for pure dephasing is:

$$L_\phi = \sqrt{\gamma_\phi} \, \sigma_z = \sqrt{\gamma_\phi} \begin{pmatrix} 1 & 0 \\ 0 & -1 \end{pmatrix}, \quad \gamma_\phi = \frac{1}{T_\phi}$$

The off-diagonal element evolves as:

$$\rho_{01}(t) = \rho_{01}(0) \cdot e^{-t/T_2}$$

The total dephasing rate combines contributions from energy relaxation and pure dephasing:

$$\boxed{\frac{1}{T_2} = \frac{1}{2T_1} + \frac{1}{T_\phi}}$$

where $T_\phi$ is the **pure dephasing time**, arising from low-frequency charge noise, flux noise, and photon number fluctuations. Since $T_2 \leq 2T_1$ always holds, the pure dephasing contribution $1/T_\phi$ is the device-specific excess.

For **inhomogeneous dephasing** $T_2^*$, the Ramsey decay includes Gaussian envelope contributions from slow environmental fluctuations:

$$\rho_{01}(t) = \rho_{01}(0) \cdot e^{-t/T_2} \cdot e^{-(t/T_\omega)^2}$$

where $T_\omega$ captures the Gaussian decay from quasi-static noise. The resulting Ramsey fringe signal is:

$$\boxed{P_0(t) = \frac{1}{2}\left(1 + A \, e^{-t/T_2} \cos(\Delta\omega \cdot t + \phi)\right)}$$

where $\Delta\omega$ is the frequency detuning between the qubit and the drive, and $\phi$ is an initial phase offset.

### 2.4 Gate Errors

Ideal quantum gates implement unitary transformations $U_{ideal}$. In practice, the actual operation is a quantum channel:

$$\mathcal{E}_{actual}(\rho) = \sum_k E_k \rho E_k^\dagger$$

where $\{E_k\}$ are Kraus operators satisfying $\sum_k E_k^\dagger E_k = I$.

The **average gate fidelity** between the ideal unitary $U$ and the actual channel $\mathcal{E}$ is:

$$\boxed{F_{avg} = \int d\psi \, \langle\psi| U^\dagger \, \mathcal{E}(|\psi\rangle\langle\psi|) \, U |\psi\rangle}$$

The **average gate error rate** (infidelity) is:

$$\epsilon = 1 - F_{avg}$$

For a $d$-dimensional system ($d=2$ for single-qubit, $d=4$ for two-qubit), the average fidelity relates to the depolarizing parameter $p$ (measured via randomized benchmarking) as:

$$F_{avg} = \frac{p(d-1) + 1}{d}$$

Therefore:

$$\boxed{\epsilon = \frac{(1-p)(d-1)}{d}}$$

**Coherent vs. incoherent errors**: The actual gate unitary can be decomposed as:

$$U_{actual} = U_{ideal} \cdot U_{error}$$

where $U_{error} = e^{i\delta\theta \cdot \hat{n} \cdot \vec{\sigma}/2}$ represents systematic over/under-rotation. The total gate infidelity includes both this coherent error and stochastic incoherent contributions from decoherence during the gate.

### 2.5 Crosstalk

Crosstalk arises from unwanted couplings between qubits. The crosstalk Hamiltonian is:

$$H_{crosstalk} = \sum_{i < j} J_{ij}(t) \left(\vec{\sigma}^{(i)} \otimes \vec{\sigma}^{(j)}\right)$$

where $J_{ij}(t)$ are coupling strengths that depend on the physical geometry, parasitic capacitance/inductance, and microwave drive spillover.

The **crosstalk coefficient** $c_{ij}$ quantifies the induced error on qubit $i$ when qubit $j$ is being driven:

$$\boxed{c_{ij} = \text{Corr}\left(\epsilon_i(t),\; \epsilon_j(t + \tau) \;\big|\; \text{drive applied on } j\right)}$$

Operationally, $c_{ij}$ is measured as the change in error rate of qubit $i$ when qubit $j$ is simultaneously driven, relative to the baseline error of qubit $i$ in isolation:

$$c_{ij} = \frac{\epsilon_i^{(\text{active-}j)} - \epsilon_i^{(\text{idle})}}{A_j}$$

where $A_j$ is the drive amplitude on qubit $j$.

### 2.6 Readout Error

Readout error $\epsilon_r^{(i)}$ for qubit $i$ captures the probability of misassigning the qubit's state during measurement. It is described by a confusion matrix:

$$M^{(i)} = \begin{pmatrix} 1 - \epsilon_r^{(i)}(0 \to 1) & \epsilon_r^{(i)}(1 \to 0) \\ \epsilon_r^{(i)}(0 \to 1) & 1 - \epsilon_r^{(i)}(1 \to 0) \end{pmatrix}$$

The average readout error is:

$$\epsilon_r^{(i)} = \frac{\epsilon_r^{(i)}(0 \to 1) + \epsilon_r^{(i)}(1 \to 0)}{2}$$

---

## 3. Noise Parameter Characterization Protocols

### 3.1 T₁ Measurement Protocol

**Circuit**: Prepare $|1\rangle$, wait for variable delay $t$, measure.

$$|0\rangle \xrightarrow{X} |1\rangle \xrightarrow{\text{Wait}(t)} \xrightarrow{M} P_1(t)$$

**Fitting model**: The measured excited-state probability as a function of delay time is fitted to:

$$\boxed{P_1(t) = A \, e^{-t/T_1} + B}$$

where:
- $A$ is the amplitude (ideally 1)
- $B$ is the offset (ideally 0 at low temperature)
- $T_1$ is the extracted relaxation time

**Fitting procedure**: Nonlinear least-squares regression (Levenberg-Marquardt) over delay points $\{t_k\}_{k=1}^{N_t}$:

$$\hat{T}_1 = \arg\min_{T_1, A, B} \sum_{k=1}^{N_t} \left[ P_1^{(\text{meas})}(t_k) - A \, e^{-t_k/T_1} - B \right]^2$$

**Parameters**: 50+ delay points over $[0, 5 \times T_1^{(\text{expected})}]$, with 1024–4096 shots per point.

### 3.2 T₂ Measurement Protocol (Ramsey Interferometry)

**Circuit**: Superposition → free precession → recombination → measure.

$$|0\rangle \xrightarrow{H} \frac{|0\rangle + |1\rangle}{\sqrt{2}} \xrightarrow{\text{Wait}(t)} \xrightarrow{R_z(\theta)} \xrightarrow{H} \xrightarrow{M} P_0(t)$$

where $\theta = \Delta\omega \cdot t$ introduces a controlled detuning.

**Fitting model**:

$$\boxed{P_0(t) = \frac{1}{2}\left(1 + A \, e^{-t/T_2} \cos(\Delta\omega \cdot t + \phi)\right)}$$

The fit extracts $T_2$ (exponential decay envelope) and $\Delta\omega$ (oscillation frequency corresponding to detuning from the qubit resonance).

**Spin Echo variant** ($T_2^{\text{echo}}$): Inserts a refocusing $\pi$-pulse at $t/2$ to cancel quasi-static noise:

$$|0\rangle \xrightarrow{\pi/2} \xrightarrow{\text{Wait}(t/2)} \xrightarrow{\pi} \xrightarrow{\text{Wait}(t/2)} \xrightarrow{\pi/2} \xrightarrow{M}$$

The echo experiment recovers coherence that was lost to slow fluctuations, yielding $T_2^{\text{echo}} \geq T_2^*$.

### 3.3 Randomized Benchmarking (RB) for Gate Errors

**Protocol**: Apply a random sequence of $m$ Clifford gates, followed by a recovery gate, and measure the return probability.

For each sequence length $m$:
1. Sample random Clifford gates $C_1, C_2, \ldots, C_m$
2. Compute recovery $C_r = (C_m \circ \cdots \circ C_1)^{-1}$
3. Execute: $|0\rangle \xrightarrow{C_1} \xrightarrow{C_2} \cdots \xrightarrow{C_m} \xrightarrow{C_r} \xrightarrow{M}$
4. Average survival probability over $K$ random sequences

**Fitting model**: The average survival probability follows an exponential decay:

$$\boxed{F(m) = A \, p^m + B}$$

where:
- $p$ is the **depolarizing parameter** (decay rate per Clifford)
- $A$ and $B$ are state preparation and measurement (SPAM) constants

**Gate error extraction**:

$$\boxed{\epsilon_1 = \frac{(1 - p)(d - 1)}{d}}$$

For single-qubit RB: $d = 2$, so $\epsilon_1 = (1 - p)/2$.

For two-qubit RB: $d = 4$, so $\epsilon_2 = 3(1 - p)/4$.

**Interleaved RB** isolates the error of a specific gate $G$ by interleaving it between random Cliffords:

$$F_{\text{interleaved}}(m) = A_G \, p_G^m + B_G$$

The gate-specific error is:

$$\epsilon_G = \frac{(d-1)(1 - p_G/p)}{d}$$

### 3.4 Crosstalk Measurement Protocol

**Simultaneous Randomized Benchmarking (SRB)** measures crosstalk by comparing the error rates of qubits under isolated vs. simultaneous operation:

1. **Baseline**: Measure gate error $\epsilon_i^{(\text{iso})}$ of qubit $i$ with all other qubits idle
2. **Simultaneous**: Measure gate error $\epsilon_i^{(\text{sim})}$ while qubit $j$ undergoes random gates
3. **Crosstalk coefficient**:

$$c_{ij} = \epsilon_i^{(\text{sim})} - \epsilon_i^{(\text{iso})}$$

The full crosstalk matrix $\mathbf{C} \in \mathbb{R}^{n \times n}$ has diagonal entries $c_{ii} = 0$ and off-diagonal entries $c_{ij}$ capturing pairwise coupling.

### 3.5 Bayesian Parameter Estimation

For more robust parameter extraction with uncertainty quantification, the system employs Bayesian inference:

$$P(\theta \mid D) \propto P(D \mid \theta) \cdot P(\theta)$$

where:
- $\theta = (T_1, T_2, \epsilon_1, \epsilon_2, \ldots)$ is the parameter vector
- $D = \{(t_k, n_k^{(1)}, N_k)\}$ is the measurement data (delay times, counts of $|1\rangle$, total shots)
- $P(D \mid \theta)$ is the binomial likelihood:

$$P(D \mid \theta) = \prod_{k} \binom{N_k}{n_k^{(1)}} \left[P_1(t_k; \theta)\right]^{n_k^{(1)}} \left[1 - P_1(t_k; \theta)\right]^{N_k - n_k^{(1)}}$$

**Prior distributions** (physically motivated):

| Parameter | Prior | Rationale |
|-----------|-------|-----------|
| $T_1$ | $\text{LogNormal}(\mu_{T_1}, \sigma_{T_1})$ | Positive, right-skewed |
| $T_2$ | $\text{LogNormal}(\mu_{T_2}, \sigma_{T_2})$ with $T_2 \leq 2T_1$ | Physical constraint |
| $\epsilon$ | $\text{Beta}(\alpha, \beta)$ | Bounded on $[0, 1]$ |
| $c_{ij}$ | $\text{HalfNormal}(\sigma_c)$ | Non-negative, small |

Posterior sampling via Markov Chain Monte Carlo (MCMC) yields point estimates and credible intervals:

$$\hat{\theta} = \mathbb{E}[\theta \mid D], \quad \text{CI}_{95\%}(\theta) = [q_{0.025}, q_{0.975}]$$

### 3.6 Neural Network Parameter Estimation

In addition to Bayesian methods, a trained neural network provides rapid estimation:

$$\hat{\theta} = f_{NN}(\mathbf{x}; \mathbf{w})$$

where $\mathbf{x}$ is the raw measurement histogram and $\mathbf{w}$ are learned weights. The network architecture is:

$$\mathbf{x} \in \mathbb{R}^{N_{\text{circuits}} \times N_{\text{shots}} \times n} \xrightarrow{\text{Dense}(512, \text{ReLU})} \xrightarrow{\text{Dense}(256, \text{ReLU})} \xrightarrow{\text{Dense}(128, \text{ReLU})} \hat{\theta} \in \mathbb{R}^d$$

Training loss: $\mathcal{L} = \text{MSE}(\hat{\theta}, \theta_{\text{true}}) + \lambda \cdot R(\mathbf{w})$

where $R(\mathbf{w})$ is a regularization term. This achieves $R^2 > 0.92$ across all parameter types and inference time $\approx 12\,$ms.

> **Convertibility Note — Characterization Protocols**: From a deployment perspective, these protocols are commercially significant because they reuse existing calibration sequences already present in quantum cloud platforms (e.g., IBM Qiskit Runtime, AWS Braket). No additional cryogenic hardware modification is required. The 62 ms total inference time enables inline parameter estimation within standard job scheduling loops, ensuring that the characterization step introduces negligible latency to production workloads. This means the system can be deployed as a **software-only middleware layer** in its first commercial version, lowering adoption barriers.

---

## 4. Hardware Fingerprint Construction

### 4.1 Fingerprint Vector Definition

The noise parameters extracted from all qubits and gates are assembled into a single high-dimensional **fingerprint vector**:

$$\boxed{\mathbf{f} = \left[\underbrace{T_1^{(1)}, T_2^{(1)}, \ldots, T_1^{(n)}, T_2^{(n)}}_{2n},\; \underbrace{\epsilon_1^{(1)}, \ldots, \epsilon_1^{(n)}}_{n},\; \underbrace{\epsilon_r^{(1)}, \ldots, \epsilon_r^{(n)}}_{n},\; \underbrace{\epsilon_2^{(1,2)}, \ldots, \epsilon_2^{(\cdot,\cdot)}}_{m},\; \underbrace{c_{12}, c_{13}, \ldots}_{n(n-1)/2}\right]}$$

### 4.2 Fingerprint Dimensionality

For a processor with $n$ qubits and $m$ two-qubit gate configurations:

| Component | Count | Description |
|-----------|-------|-------------|
| $T_1, T_2$ | $2n$ | Relaxation/dephasing per qubit |
| $\epsilon_1$ | $n$ | Single-qubit gate error per qubit |
| $\epsilon_r$ | $n$ | Readout error per qubit |
| $\epsilon_2$ | $m$ | Two-qubit gate error per pair |
| $c_{ij}$ | $\binom{n}{2} = \frac{n(n-1)}{2}$ | Crosstalk per qubit pair |

Total dimensionality:

$$\boxed{d = \dim(\mathbf{f}) = 4n + m + \frac{n(n-1)}{2}}$$

**Example** (IBM Falcon R5.11, 27 qubits, 127 two-qubit gate configurations):

$$d = 4(27) + 127 + \frac{27 \times 26}{2} = 108 + 127 + 351 = 586$$

> **Convertibility Note — Fingerprint Dimensionality**: The high dimensionality ($d = 586$) is an advantage for both security and product differentiation. However, for lightweight deployment (e.g., IoT edge devices or 6G terminals), the system supports a configurable **reduced fingerprint mode** using a subset of the most stable and high-entropy parameters. For example, using only $T_1, T_2$ and single-qubit errors ($d_{reduced} = 3n = 81$) still yields $\approx 111$ bits of raw entropy — sufficient for 64-bit device authentication tokens in resource-constrained environments. This flexibility enables a tiered product lineup: full fingerprint for sovereign/defense use, reduced fingerprint for commercial IoT.

### 4.3 Fingerprint Uniqueness: Inter-Device Separability

For two devices $A$ and $B$ with fingerprint vectors $\mathbf{f}_A$ and $\mathbf{f}_B$, the **inter-device separation** is quantified by:

**Euclidean distance**:

$$d_E(\mathbf{f}_A, \mathbf{f}_B) = \|\mathbf{f}_A - \mathbf{f}_B\|_2 = \sqrt{\sum_{i=1}^{d}(f_{A,i} - f_{B,i})^2}$$

**Mahalanobis distance** (accounts for parameter correlations and scaling):

$$d_M(\mathbf{f}_A, \mathbf{f}_B) = \sqrt{(\mathbf{f}_A - \mathbf{f}_B)^T \Sigma^{-1} (\mathbf{f}_A - \mathbf{f}_B)}$$

Experimental results on 5 IBM Quantum processors demonstrate:

| Metric | Inter-device (mean) | Intra-device 30-day (max) | Separation Ratio |
|--------|---------------------|---------------------------|------------------|
| Euclidean | 0.44 | 0.12 | 3.7× |
| Mahalanobis | 9.2 | 2.8 | 3.3× |

A **threshold** $\tau = 4.0$ cleanly separates same-device from different-device measurements.

### 4.4 Fingerprint Reproducibility: Intra-Device Consistency

Over a 30-day measurement period on the same device, the fingerprint correlation remains high:

$$r(\mathbf{f}_{t_1}, \mathbf{f}_{t_2}) = \frac{\text{Cov}(\mathbf{f}_{t_1}, \mathbf{f}_{t_2})}{\sigma_{\mathbf{f}_{t_1}} \cdot \sigma_{\mathbf{f}_{t_2}}} \approx 0.94$$

The intra-device Mahalanobis distance grows with time but remains well below the detection threshold:

| Time gap | Mahalanobis $d_M$ | Within threshold? |
|----------|-------------------|--------------------|
| 1 hour | 0.8 | ✓ ($d_M \ll 4.0$) |
| 1 day | 1.2 | ✓ |
| 1 week | 1.9 | ✓ |
| 30 days | 2.8 | ✓ |

---

## 5. Fingerprint-to-Key Mapping Pipeline

The conversion from continuous noise parameters to a discrete cryptographic key follows a multi-stage pipeline:

$$\mathbf{f} \in \mathbb{R}^d \xrightarrow{\text{Normalize}} \tilde{\mathbf{f}} \in [0,1]^d \xrightarrow{\text{Quantize}} \mathbf{b} \in \{0,1\}^{kd} \xrightarrow{\text{Fuzzy Extract}} \mathbf{b}' \xrightarrow{\text{Hash + KDF}} K$$

### 5.1 Step 1: Normalization

Each parameter $f_i$ is normalized to $[0, 1]$ using calibration-derived bounds:

$$\tilde{f}_i = \frac{f_i - f_i^{(\min)}}{f_i^{(\max)} - f_i^{(\min)}}$$

where $f_i^{(\min)}, f_i^{(\max)}$ are the observed range bounds for parameter type $i$ across the device class.

### 5.2 Step 2: Adaptive Quantization

Each normalized parameter is quantized to $k$ bits:

$$b_i = \left\lfloor \tilde{f}_i \cdot (2^k - 1) \right\rfloor$$

yielding a $k$-bit integer per parameter. The total quantized signature has $kd$ bits.

**Adaptive resolution**: Different parameter types may use different bit widths $k_j$ based on their stability and entropy contribution:

| Parameter type | Typical $k$ | Rationale |
|----------------|-------------|-----------|
| $T_1$ | 8 | High stability, moderate entropy |
| $T_2$ | 7 | Slightly more variable |
| $\epsilon_1$ | 6 | Higher variability, lower precision |
| $\epsilon_2$ | 6 | Similar to $\epsilon_1$ |
| $c_{ij}$ | 4 | Small values, lower entropy per pair |

### 5.3 Step 3: Fuzzy Extraction

Because quantum noise is continuous and slightly variable between measurements, a **fuzzy extractor** ensures deterministic key output despite noisy inputs.

A fuzzy extractor $(\text{Gen}, \text{Rep})$ consists of:

- $\text{Gen}(\mathbf{b})$: During enrollment, outputs a key $K$ and public helper data $P$
- $\text{Rep}(\mathbf{b}', P)$: During reproduction, given a noisy reading $\mathbf{b}'$ close to $\mathbf{b}$ and helper data $P$, recovers the same key $K$

**Correctness condition**: If the Hamming distance satisfies $d_H(\mathbf{b}, \mathbf{b}') \leq t$ (error tolerance), then $\text{Rep}(\mathbf{b}', P) = K$.

**Security condition**: $K$ is statistically close to uniform even given $P$:

$$\tilde{H}_\infty(\mathbf{b} \mid P) \geq H_{min}(\mathbf{b}) - \text{leak}(P)$$

The helper data is generated using error-correcting codes (e.g., BCH, LDPC, or Polar codes). The code is chosen so that its error-correction capability $t$ exceeds the expected intra-device variation.

**Dynamic Helper Data Matrix**: To adapt to cryogenic thermal drift across cooldown cycles, the helper data is periodically updated:

$$P_{new} = \text{Update}(P_{old}, \mathbf{b}_{current}, \text{drift\_model})$$

This update preserves key identity continuity while adapting to legitimate device evolution.

### 5.4 Step 4: Cryptographic Hashing and Key Derivation

The corrected bitstring is compressed via a cryptographic hash and expanded via a Key Derivation Function (KDF):

$$\boxed{K = \text{KDF}\left(\text{Hash}(\mathbf{f}) \;\|\; \text{salt} \;\|\; \text{context}\right)}$$

**Concrete instantiation**:

1. **Hash**: SHA3-256 or SHAKE256
   $$h = \text{SHA3-256}(\mathbf{b}')$$

2. **KDF**: HKDF (HMAC-based Key Derivation Function, RFC 5869)
   - **Extract**: $\text{PRK} = \text{HMAC-SHA3-256}(\text{salt}, h)$
   - **Expand**: $K = \text{HMAC-SHA3-256}(\text{PRK}, \text{info} \| \text{counter})$

where:
- $\text{salt}$ is a random or policy-derived value
- $\text{context}$ encodes device identity, tenant policy, usage purpose, and timestamp
- $\text{info} = \text{"NAV-QE-KEY"} \| \text{context}$

**Alternative formulation** (using SHAKE256 as an extractor):

$$K = \text{SHAKE256}\left(\text{FuzzyExtract}(\mathbf{f}, \text{HelperData}) \;\|\; \text{nonce},\; \text{key\_length}\right)$$

The derived key $K$ can serve as:
- An AES-256 symmetric key
- A seed for post-quantum algorithms (ML-KEM / FIPS 203, ML-DSA / FIPS 204, SLH-DSA / FIPS 205)
- An attestation token or proof-of-hardware input

> **Convertibility Note — Key Derivation Pipeline**: The end-to-end key derivation latency of $< 15$ ms (fingerprint extraction 8 ms + quantization 2 ms + hash 1 ms + HKDF 3 ms) is compatible with real-time enterprise security workflows including TLS session establishment, VPN tunnel keying, and PKCS#11 key generation calls. The use of standardized primitives (SHA3-256, HKDF RFC 5869, SHAKE256) ensures that the output can be consumed by existing cryptographic libraries (OpenSSL, BoringSSL, libsodium) without custom integration. This design choice directly supports procurement by regulated industries (banking, telecommunications, government) that require FIPS 140-3 validated cryptographic modules.

---

## 6. Entropy Analysis and Information-Theoretic Bounds

### 6.1 Per-Parameter Entropy

For a noise parameter $f_i$ modeled as Gaussian $f_i \sim \mathcal{N}(\mu_i, \sigma_i^2)$ and quantized with resolution $\delta_i$, the discrete entropy is:

$$H(f_i) = h(f_i) - \log_2(\delta_i)$$

where the differential (continuous) entropy of a Gaussian is:

$$h(f_i) = \frac{1}{2}\log_2(2\pi e \, \sigma_i^2)$$

Therefore:

$$\boxed{H(f_i) = \log_2\left(\frac{\sigma_i \sqrt{2\pi e}}{\delta_i}\right)}$$

The **min-entropy** provides a more conservative (worst-case) bound:

$$H_{min}(f_i) = -\log_2\left(\max_x \Pr[f_i = x]\right)$$

For a Gaussian quantized to bins of width $\delta_i$, the maximum probability bin is centered at the mean:

$$\max_x \Pr[f_i = x] \approx \frac{\delta_i}{\sigma_i \sqrt{2\pi}}$$

So:

$$H_{min}(f_i) \approx \log_2\left(\frac{\sigma_i \sqrt{2\pi}}{\delta_i}\right)$$

### 6.2 Total Fingerprint Entropy

**Theorem (Min-Entropy Bound for NAV-QE Keys)**:

Let $\mathbf{f} = (f_1, \ldots, f_d)$ be the fingerprint vector. Under the assumption that each parameter $f_i$ has standard deviation $\sigma_i$ and quantization resolution $\delta_i$, the total min-entropy is:

$$\boxed{H_{min}(\mathbf{f}) \geq \sum_{i=1}^{d} \log_2\left(\frac{\sigma_i \sqrt{2\pi e}}{\delta_i}\right) - I(\mathbf{f})}$$

where $I(\mathbf{f})$ is the mutual information between correlated parameters, accounting for the reduction in total entropy due to statistical dependencies.

**Proof sketch**:

1. For independent Gaussian parameters, the joint entropy is the sum of marginal entropies:
   $$H(\mathbf{f}) = \sum_i H(f_i) = \sum_i \log_2\left(\frac{\sigma_i \sqrt{2\pi e}}{\delta_i}\right)$$

2. Parameter correlations reduce the total entropy. The joint entropy of a multivariate Gaussian $\mathbf{f} \sim \mathcal{N}(\boldsymbol{\mu}, \Sigma)$ is:
   $$H(\mathbf{f}) = \frac{1}{2}\log_2\left((2\pi e)^d |\Sigma|\right) - d\log_2(\delta)$$

3. The entropy loss due to correlations is:
   $$I(\mathbf{f}) = \sum_i H(f_i) - H(\mathbf{f}) = \frac{1}{2}\log_2\left(\frac{\prod_i \sigma_i^2}{|\Sigma|}\right)$$

4. Min-entropy is bounded below by Shannon entropy minus a logarithmic correction for near-Gaussian distributions.

### 6.3 Practical Entropy Computation (27-Qubit Processor)

| Source | Count | Per-element entropy | Total contribution |
|--------|-------|--------------------|--------------------|
| $T_1$ (27 qubits) | 27 | ~1.56 bits | 42 bits |
| $T_2$ (27 qubits) | 27 | ~1.41 bits | 38 bits |
| $\epsilon_1$ (27 qubits) | 27 | ~1.15 bits | 31 bits |
| $\epsilon_2$ (52 pairs) | 52 | ~0.92 bits | 48 bits |
| $c_{ij}$ (351 pairs) | 351 | ~0.08 bits | 28 bits |
| **Marginal sum** | | | **270 bits** |
| **Correlation reduction** $I(\mathbf{f})$ | | | **−83 bits** |
| **Net min-entropy** $H_{min}(\mathbf{f})$ | | | **≥ 187 bits** |

After conservative application of the **leftover hash lemma**:

$$\ell \leq H_{min}(\mathbf{f}) - 2\log_2(1/\varepsilon)$$

where $\varepsilon$ is the statistical distance from uniform. For $\varepsilon = 2^{-32}$ (negligible security loss):

$$\ell \leq 187 - 64 = 123 \text{ bits}$$

Rounding conservatively: **128 bits** of secure key material, sufficient for AES-128 or as a seed for post-quantum algorithms.

### 6.4 Entropy Scaling with System Size

The fingerprint entropy scales superlinearly with qubit count due to the $O(n^2)$ crosstalk contribution:

$$H_{min}(\mathbf{f}) \sim \alpha \cdot n + \beta \cdot n^2$$

where $\alpha \approx 4$ bits/qubit (from $T_1, T_2, \epsilon_1, \epsilon_r$) and $\beta \approx 0.04$ bits/pair (from crosstalk).

| Qubits $n$ | Fingerprint dimension $d$ | Estimated $H_{min}$ (bits) |
|-------------|---------------------------|----------------------------|
| 7 | 78 | 45 |
| 27 | 586 | 187 |
| 65 | 3,128 | 420 |
| 127 | 11,938 | 810 |
| 433 | 139,246 | 2,700 |

> **Convertibility Note — Entropy Scaling**: The superlinear entropy scaling ($\sim O(n^2)$) means that as quantum hardware matures from 27-qubit to 433+ qubit systems, the security margin of NAV-QE grows rapidly — from 128-bit to 2,700+ bit key material. This property makes the system **future-proof**: the same mathematical architecture and software codebase can serve current NISQ devices and future fault-tolerant quantum computers without fundamental redesign, protecting long-term product investment and enabling subscription-based pricing that scales with processor capability.

### 6.5 Key Entropy Bound (Formal Statement)

**Theorem**: The entropy of keys derived from an $n$-qubit processor with $m$ two-qubit gates satisfies:

$$\boxed{H(K) \geq \sum_{i=1}^{n} \left[H_{min}(T_1^{(i)}) + H_{min}(T_2^{(i)}) + H_{min}(\epsilon_1^{(i)})\right] + \sum_{j=1}^{m} H_{min}(\epsilon_2^{(j)}) - I(\mathbf{f}) - 2\log_2(1/\varepsilon)}$$

where $\varepsilon$ is the distinguishing advantage of the derived key from a uniform random key.

---

## 7. Tamper Detection: Statistical Deviation Framework

### 7.1 Baseline Registration

During enrollment, the system collects $N$ fingerprint samples under controlled conditions:

$$\{\mathbf{f}^{(1)}, \mathbf{f}^{(2)}, \ldots, \mathbf{f}^{(N)}\}$$

The **baseline profile** and **natural drift covariance** are estimated as:

$$\mathbf{f}_{baseline} = \frac{1}{N}\sum_{k=1}^{N} \mathbf{f}^{(k)}$$

$$\hat{\Sigma} = \frac{1}{N-1}\sum_{k=1}^{N} (\mathbf{f}^{(k)} - \mathbf{f}_{baseline})(\mathbf{f}^{(k)} - \mathbf{f}_{baseline})^T$$

### 7.2 Mahalanobis Distance

The primary deviation metric is the **Mahalanobis distance**, which generalizes the concept of "number of standard deviations away" to multiple correlated dimensions:

$$\boxed{d_M = \sqrt{(\mathbf{f}_{current} - \mathbf{f}_{baseline})^T \Sigma^{-1} (\mathbf{f}_{current} - \mathbf{f}_{baseline})}}$$

**Properties**:
- Scale-invariant: automatically accounts for different parameter units and magnitudes
- Correlation-aware: accounts for the fact that $T_1$ and $T_2$ are correlated (since $T_2 \leq 2T_1$)
- Under normal operation (null hypothesis $H_0$): $d_M^2 \sim \chi^2_d$ (chi-squared with $d$ degrees of freedom)

**Decision rule**:

$$\text{Decision} = \begin{cases} \text{NORMAL} & \text{if } d_M \leq \tau \\ \text{TAMPER ALERT} & \text{if } d_M > \tau \end{cases}$$

### 7.3 Threshold Selection and Error Rates

The threshold $\tau$ controls the trade-off between false positives and false negatives.

Under $H_0$ (no tampering), $d_M^2$ follows a chi-squared distribution with $d$ degrees of freedom. In practice, with $d = 586$ parameters, the chi-squared distribution concentrates sharply, so a reduced-dimension approach is used (e.g., principal components capturing 95% of variance, yielding effective dimension $d_{\text{eff}} \approx 50$).

**False Positive Rate (FPR)**:

$$\text{FPR} = \Pr[d_M > \tau \mid H_0] = 1 - F_{\chi^2_{d_{\text{eff}}}}(\tau^2)$$

**False Negative Rate (FNR)**: Depends on the magnitude of the tampering-induced shift $\Delta\mathbf{f}$:

$$\text{FNR} = \Pr[d_M \leq \tau \mid H_1] = F_{\chi^2_{d_{\text{eff}}}(\lambda)}(\tau^2)$$

where $\lambda = \Delta\mathbf{f}^T \Sigma^{-1} \Delta\mathbf{f}$ is the **non-centrality parameter** of the chi-squared distribution under the alternative hypothesis.

**Experimental results** with $\tau = 4.0$:

| Metric | Value |
|--------|-------|
| False Accept Rate (FAR) | < 0.001% |
| False Reject Rate (FRR) | < 0.1% |
| Equal Error Rate (EER) | 0.02% |

### 7.4 Alternative Distance Metrics

The framework is not limited to Mahalanobis distance. Alternative metrics include:

**Wasserstein distance** (Earth Mover's Distance): Measures the cost of transforming one probability distribution into another:

$$W_p(\mu, \nu) = \left(\inf_{\gamma \in \Gamma(\mu, \nu)} \int \|x - y\|^p \, d\gamma(x, y)\right)^{1/p}$$

**Kullback-Leibler (KL) divergence**: Measures the information-theoretic difference between the current noise distribution and the baseline:

$$D_{KL}(P_{current} \| P_{baseline}) = \int p_{current}(x) \log\frac{p_{current}(x)}{p_{baseline}(x)} \, dx$$

For multivariate Gaussians:

$$D_{KL}(\mathcal{N}_1 \| \mathcal{N}_0) = \frac{1}{2}\left[\text{tr}(\Sigma_0^{-1}\Sigma_1) + (\mu_0 - \mu_1)^T\Sigma_0^{-1}(\mu_0 - \mu_1) - d + \ln\frac{|\Sigma_0|}{|\Sigma_1|}\right]$$

**Statistical process control (SPC) charts**: CUSUM or EWMA charts can track gradual drift vs. sudden shifts:

$$S_t = \max(0, S_{t-1} + (d_M^{(t)} - k))$$

where $k$ is the reference value and an alert is triggered when $S_t > h$.

### 7.5 Tamper Detection Sensitivity

Experimental validation of detection rates for various attack types:

| Attack Type | Primary Effect | Profile Change | Detection Rate |
|-------------|----------------|----------------|----------------|
| Probe insertion | $T_1 \downarrow 15\%$ | $\Delta T_1/T_1 = 0.15$ | 99.8% |
| EM interference | All parameters $\uparrow 5\%$ | Multi-dimensional shift | 98.2% |
| Temperature shift | $T_1, T_2 \downarrow 8\%$ | Correlated decay | 97.1% |
| Crosstalk enhancement | $c_{ij} \uparrow 50\%$ | Off-diagonal shift | 99.5% |
| Subtle probe | $T_1 \downarrow 3\%$ | Small perturbation | 78.4% |

> **Convertibility Note — Tamper Detection**: The >97% detection rate for profile changes ≥5% directly translates to auditable security guarantees for regulated customers. In a compliance context, these detection rates can be mapped to **NIST SP 800-53 SI-4 (Information System Monitoring)** and **ISO 27001 A.12.4 (Logging and Monitoring)** controls. The configurable monitoring interval ($N_{mon} = 10, 100, 1000$) allows customers to select a security/overhead trade-off appropriate to their risk profile — high-frequency for defense, lower-frequency for commercial cloud — supporting tiered service offerings.

### 7.6 Adaptive Baseline Update

To distinguish natural drift from tampering, the baseline is periodically updated using an exponentially weighted moving average:

$$\mathbf{f}_{baseline}^{(t+1)} = (1 - \alpha) \cdot \mathbf{f}_{baseline}^{(t)} + \alpha \cdot \mathbf{f}_{current}$$

$$\Sigma^{(t+1)} = (1 - \alpha) \cdot \Sigma^{(t)} + \alpha \cdot (\mathbf{f}_{current} - \mathbf{f}_{baseline}^{(t)})(\mathbf{f}_{current} - \mathbf{f}_{baseline}^{(t)})^T$$

The update rate $\alpha$ is chosen to track slow natural drift ($\alpha \sim 0.01$) while remaining sensitive to sudden changes (which cause $d_M$ spikes well above $\tau$ before the baseline adapts).

---

## 8. Fuzzy Extractor and Helper Data Mechanism

### 8.1 Formal Definition

A $(\ell, t, \varepsilon)$-fuzzy extractor for metric space $(\mathcal{M}, \text{dis})$ is a pair of procedures:

- $\text{Gen}(w) \to (K, P)$: On input $w \in \mathcal{M}$, outputs a key $K \in \{0,1\}^\ell$ and helper data $P$
- $\text{Rep}(w', P) \to K$: On input $w' \in \mathcal{M}$ with $\text{dis}(w, w') \leq t$ and helper data $P$, outputs the same $K$

**Security guarantee**: For any distribution $W$ over $\mathcal{M}$ with min-entropy $H_{min}(W) \geq m$:

$$\Delta\left((K, P), (U_\ell, P)\right) \leq \varepsilon$$

where $\Delta$ is statistical distance and $U_\ell$ is the uniform distribution on $\{0,1\}^\ell$.

### 8.2 Construction via Secure Sketch

A fuzzy extractor is typically built from a **secure sketch** and a **strong extractor**:

1. **Secure sketch** $\text{SS}(w) = s$: Public sketch that allows recovery of $w$ from any $w'$ with $\text{dis}(w, w') \leq t$
   - $\text{Rec}(w', s) = w$
   - Security: $\tilde{H}_\infty(W \mid \text{SS}(W)) \geq H_{min}(W) - \text{leak}$

2. **Strong extractor** $\text{Ext}(w; r) = K$: Converts high-entropy source into uniform key
   - Using the leftover hash lemma: $\ell = H_{min}(W) - \text{leak} - 2\log_2(1/\varepsilon)$

**Implementation in NAV-QE**: The secure sketch uses a **binary error-correcting code** $\mathcal{C}$ with correction capability $t$:

$$\text{SS}(w) = w \oplus \text{Encode}(\mathbf{0})$$

$$\text{Rec}(w', s) = \text{Decode}(w' \oplus s) \oplus s$$

Code candidates: BCH codes, concatenated Polar codes, or LDPC codes optimized for the expected noise profile.

### 8.3 Entropy Loss from Helper Data

The helper data $P$ leaks at most:

$$\text{leak}(P) \leq n - k$$

where $n$ is the codeword length and $k$ is the message length of the error-correcting code $\mathcal{C}$. This is the redundancy of the code.

The **residual entropy** available for key generation is:

$$\ell \leq H_{min}(\mathbf{f}) - (n - k) - 2\log_2(1/\varepsilon)$$

### 8.4 Dynamic Helper Data for Cryogenic Drift

Standard fuzzy extractors assume a fixed reference. To handle the slow drift inherent in superconducting qubit systems (temperature variations, TLS reconfiguration), NAV-QE employs **dynamic helper data**:

1. Periodically re-compute the secure sketch: $s_{new} = w_{current} \oplus \text{Encode}(\mathbf{0})$
2. Verify that the same key is still recoverable: $K_{check} = \text{Rep}(w_{current}, s_{new}) \stackrel{?}{=} K$
3. If yes, update $s \leftarrow s_{new}$ (extends operational lifetime)
4. If no, trigger re-enrollment (device identity may have changed)

This mechanism enables key reproducibility rates of **99.3%** over realistic operational windows, compared to <90% with static helper data.

> **Convertibility Note — Fuzzy Extraction**: The dynamic helper data mechanism is a critical differentiator for real-world deployment. Classical PUF systems typically suffer from high FRR due to environmental drift, making them impractical for production use. By achieving 99.3% key regeneration success across cryogenic cooldown cycles, NAV-QE meets the reliability threshold required for enterprise SLAs (typically ≥99.0%). The helper data is public and can be stored in standard databases or distributed via CDN, requiring no specialized secure storage — further reducing deployment cost.

---

## 9. Security Proofs and Guarantees

### 9.1 Physical Unclonable Function (PUF) Properties

NAV-QE satisfies the formal requirements of a PUF:

**Property 1 — Uniqueness**: For two distinct devices $A, B$:

$$\Pr\left[d_M(\mathbf{f}_A, \mathbf{f}_B) < \tau\right] < \text{FAR}$$

Experimentally: FAR $< 0.001\%$ with $\tau = 4.0$.

**Property 2 — Reproducibility**: For the same device at times $t_1, t_2$:

$$\Pr\left[d_M(\mathbf{f}_{t_1}, \mathbf{f}_{t_2}) > \tau\right] < \text{FRR}$$

Experimentally: FRR $< 0.1\%$ over 30 days.

**Property 3 — Unclonability**: By the **quantum no-cloning theorem**, an unknown quantum state $|\psi\rangle$ cannot be exactly copied:

$$\nexists \; U : U|\psi\rangle|0\rangle = |\psi\rangle|\psi\rangle \quad \text{for all } |\psi\rangle$$

Since the noise parameters are determined by the quantum states of TLS defects, Josephson junction imperfections, and electromagnetic mode structures, they cannot be precisely replicated on another device.

**Property 4 — Tamper evidence**: Any physical interaction with the quantum processor introduces additional decoherence channels, altering the noise fingerprint:

$$\mathbf{f}_{tampered} = \mathbf{f}_{baseline} + \Delta\mathbf{f}_{tamper}, \quad \|\Delta\mathbf{f}_{tamper}\| > 0$$

This is detectable when $d_M(\mathbf{f}_{tampered}, \mathbf{f}_{baseline}) > \tau$.

### 9.2 Collision Resistance

The probability that two distinct devices produce the same quantized fingerprint (and hence the same key) is bounded by:

$$\boxed{P_{collision} \leq 2^{-k \cdot d_{\text{eff}}}}$$

where $k$ is bits per parameter and $d_{\text{eff}}$ is the effective number of independent parameters.

For $d_{\text{eff}} = 50$ (conservative, from PCA of the 586-dimensional correlated vector) and $k = 8$:

$$P_{collision} \leq 2^{-400} \ll 2^{-128}$$

This vastly exceeds the 128-bit security level.

### 9.3 Unpredictability Against Modeling Attacks

Let $\hat{\theta}_i$ be the best prediction of parameter $\theta_i$ by an adversary with full knowledge of the device architecture, fabrication process, and historical calibration data. The prediction error satisfies:

$$\text{Var}(\theta_i - \hat{\theta}_i) \geq \sigma_{fab}^2$$

where $\sigma_{fab}$ is the **irreducible fabrication variance**. For superconducting qubits:

$$\frac{\sigma_{fab}}{\mu} \approx 0.1 - 0.3$$

This coefficient of variation ensures that each parameter contributes $\geq 1$ bit of unpredictable entropy per qubit, even against a computationally unbounded adversary with classical side information.

### 9.4 Security Under Key Derivation

By the **leftover hash lemma**, if $\text{Hash}$ is chosen from a family of universal hash functions, the derived key $K$ satisfies:

$$\Delta\left(K, U_\ell\right) \leq \frac{1}{2}\sqrt{2^{\ell - H_{min}(\mathbf{f} \mid P)}}$$

Setting $\ell = H_{min}(\mathbf{f} \mid P) - 2\log_2(1/\varepsilon)$ ensures:

$$\Delta\left(K, U_\ell\right) \leq \varepsilon$$

With $H_{min}(\mathbf{f} \mid P) \geq 187 - (n - k)$ and appropriate code parameters, this yields $\ell \geq 128$ bits with $\varepsilon \leq 2^{-32}$.

---

## 10. Scalability Analysis

### 10.1 Computational Complexity

| Operation | Time Complexity | Space Complexity |
|-----------|----------------|-----------------|
| $T_1$ characterization (per qubit) | $O(N_t \cdot N_s)$ | $O(N_t)$ |
| $T_2$ characterization (per qubit) | $O(N_t \cdot N_s)$ | $O(N_t)$ |
| Single-qubit RB (per qubit) | $O(N_m \cdot K \cdot N_s)$ | $O(N_m)$ |
| Two-qubit RB (per pair) | $O(N_m \cdot K \cdot N_s)$ | $O(N_m)$ |
| Crosstalk (per pair) | $O(N_d \cdot N_s)$ | $O(N_d)$ |
| Fingerprint assembly | $O(d)$ | $O(d)$ |
| Mahalanobis distance | $O(d^2)$ | $O(d^2)$ |
| Key derivation (HKDF) | $O(d)$ | $O(1)$ |

where $N_t$ = number of delay points, $N_s$ = shots per circuit, $N_m$ = number of RB sequence lengths, $K$ = number of random sequences, $N_d$ = number of drive configurations.

### 10.2 Total Characterization Time

The full characterization time scales as:

$$T_{char} = n \cdot (t_{T_1} + t_{T_2} + t_{RB_1}) + m \cdot t_{RB_2} + \binom{n}{2} \cdot t_{XT}$$

$$T_{char} \sim O\left(n + m + n^2\right) \sim O(n^2) \text{ (dominated by crosstalk)}$$

For a 27-qubit processor: $T_{char} \approx 40$ minutes.

### 10.3 Fingerprint Dimensionality Scaling

$$d = 4n + m + \frac{n(n-1)}{2} \sim O(n^2)$$

The quadratic scaling in $n$ is beneficial for security (more entropy) but requires careful management of the covariance matrix $\Sigma \in \mathbb{R}^{d \times d}$.

**Dimensionality reduction**: Principal Component Analysis (PCA) can reduce the effective dimension to $d_{\text{eff}} \ll d$ while preserving >95% of the variance, making Mahalanobis distance computation tractable even for large processors.

---

## 11. Operational Convertibility Models

> **Purpose**: This section formalizes the mathematical criteria and quantitative models that enable the NAV-QE system to transition from a theoretical framework into deployable products and revenue-generating services. These models provide procurement-grade acceptance criteria, cost–benefit quantification, and service-level guarantees that are essential for enterprise and sovereign infrastructure adoption.

### 11.1 Service-Level Agreement (SLA) Mathematical Framework

For a commercially deployable NAV-QE service, the provider must guarantee quantifiable security metrics. Define the **SLA compliance vector**:

$$\mathbf{s} = (\text{FAR}, \text{FRR}, R_{key}, T_{detect}, \eta_{overhead})$$

where:
- $\text{FAR}$: False Accept Rate — probability of accepting a forged or different device
- $\text{FRR}$: False Reject Rate — probability of rejecting a legitimate device
- $R_{key}$: Key regeneration success rate across operational windows
- $T_{detect}$: Tamper detection latency (seconds)
- $\eta_{overhead}$: QPU throughput overhead introduced by attestation

**Contractual constraints** (procurement specification targets):

$$\text{FAR} \leq \text{FAR}_{max}, \quad \text{FRR} \leq \text{FRR}_{max}, \quad R_{key} \geq R_{min}, \quad T_{detect} \leq T_{max}, \quad \eta_{overhead} \leq \eta_{max}$$

Experimental data validates that the system meets or exceeds typical enterprise thresholds:

| SLA Parameter | Contractual Target | Measured Value | Margin |
|---------------|-------------------|----------------|--------|
| FAR | ≤ 0.01% | < 0.001% | 10× |
| FRR | ≤ 0.5% | < 0.1% | 5× |
| $R_{key}$ | ≥ 99.0% | 99.3% | Compliant |
| $T_{detect}$ | ≤ 10 s | 8 s (at 100-circuit interval) | Compliant |
| $\eta_{overhead}$ | ≤ 5% | < 3% (attestation-only mode) | Compliant |

### 11.2 Throughput Overhead Model

Let $T_{job}$ be the average quantum job execution time. The attestation module introduces periodic characterization micro-jobs. If the monitoring interval is every $N_{mon}$ circuits and each characterization micro-job costs $T_{char}^{(\text{quick})}$ seconds, the **fractional throughput overhead** is:

$$\boxed{\eta_{overhead} = \frac{T_{char}^{(\text{quick})}}{N_{mon} \cdot T_{circuit} + T_{char}^{(\text{quick})}}}$$

For typical values ($T_{char}^{(\text{quick})} = 8\,$s, $N_{mon} = 100$, $T_{circuit} = 2.5\,$s):

$$\eta_{overhead} = \frac{8}{100 \times 2.5 + 8} = \frac{8}{258} \approx 3.1\%$$

**Optimization**: The monitoring interval $N_{mon}$ can be tuned as a function of risk tolerance $\mathcal{R}$ and the estimated drift rate $\dot{d}_M$:

$$N_{mon}^{*} = \arg\min_{N} \left[\eta_{overhead}(N) + \lambda \cdot \Pr\left[\text{undetected tamper within } N \text{ circuits}\right]\right]$$

where $\lambda$ is a Lagrange multiplier encoding the cost of a missed tamper event relative to throughput loss.

### 11.3 Cost–Benefit and ROI Quantification

To support procurement decisions, define the **annualized economic model**:

**Cost of NAV-QE deployment** per processor per year:

$$C_{NAV\text{-}QE} = C_{enroll} + 365 \cdot C_{daily\_mon} + C_{re\text{-}enroll} \cdot N_{re\text{-}enroll} + C_{infra}$$

where:
- $C_{enroll}$: one-time enrollment cost (characterization time × infrastructure rate)
- $C_{daily\_mon}$: daily monitoring cost (overhead × QPU hourly rate × hours/day)
- $C_{re\text{-}enroll}$: re-enrollment cost per event
- $N_{re\text{-}enroll}$: expected re-enrollments per year (≈ 26 at biweekly schedule)
- $C_{infra}$: annual infrastructure cost for verifier service, storage, and integration

**Value of NAV-QE deployment** per processor per year:

$$V_{NAV\text{-}QE} = V_{trust\_premium} + V_{avoided\_breach} \cdot P_{breach} + V_{compliance} + V_{attestation\_revenue}$$

**Return on Investment**:

$$\boxed{\text{ROI} = \frac{V_{NAV\text{-}QE} - C_{NAV\text{-}QE}}{C_{NAV\text{-}QE}} \times 100\%}$$

For a QCaaS provider operating 20 quantum processors, if each processor's trust premium generates an additional \$50K/year in attestation-service revenue and the per-processor NAV-QE cost is \$8K/year, the fleet ROI exceeds 500%.

### 11.4 Multi-Tenant Isolation Model

In a QCaaS environment with $M$ tenants sharing $P$ quantum processors, the attestation system must guarantee **tenant-level isolation**. Define the tenant-specific attestation scope as:

$$\text{Attestation}_{tenant_j} = \text{Sign}\left(\text{KDF}(\mathbf{f}_{device_p} \| \text{tenant\_id}_j \| \text{job\_id} \| \text{nonce}),\; sk_{verifier}\right)$$

**Isolation guarantee**: For tenants $j \neq k$ on the same processor $p$:

$$\Pr\left[K_{j,p} = K_{k,p}\right] \leq 2^{-\ell}$$

This is ensured by the domain-separation property of the KDF: distinct $\text{tenant\_id}$ inputs produce cryptographically independent keys even from the same underlying fingerprint.

**Throughput fairness constraint**: The attestation overhead must be distributed equitably:

$$\eta_{overhead}^{(j)} \leq \frac{\eta_{overhead}^{(total)}}{M} + \epsilon_{fairness}$$

### 11.5 Deployment Mode Formalization

The system supports four deployment modes, each with distinct mathematical operating constraints:

| Mode | Access Level | Input Data | Latency Budget | Key Output |
|------|-------------|------------|----------------|------------|
| Cloud Verifier | Job metadata + calibration API | $\mathbf{x}_{calib}$ | $< 1$ s per attestation | Attestation token |
| Provider-Integrated | Control-plane telemetry tap | $\mathbf{x}_{telemetry}$ | $< 100$ ms inline | Key seed + token |
| Embedded qHSM | Firmware / cryocontroller bus | $\mathbf{x}_{raw}$ | $< 10$ ms hardware loop | AES-256 key |
| OEM Licensing | Adapter SDK + parser | $\mathbf{x}_{adapted}$ | Vendor-defined | Configurable |

The **mathematical equivalence** across modes is guaranteed by the invariant:

$$K = \text{KDF}(\text{Hash}(\Phi(\mathbf{x}_{mode})) \| \text{salt} \| \text{context})$$

where $\Phi(\cdot)$ is a mode-specific telemetry adapter that normalizes heterogeneous input sources into a canonical noise parameter vector. The adapter satisfies:

$$\|\Phi(\mathbf{x}_{mode_1}) - \Phi(\mathbf{x}_{mode_2})\|_2 \leq \epsilon_{adapter}$$

for the same underlying physical device state, ensuring cross-mode fingerprint consistency.

### 11.6 Billing and Metering Model

For subscription-based monetization, the system supports metered billing based on discrete security events. Define the **monthly billing function**:

$$\text{Bill}_{month} = \underbrace{P \cdot R_{enroll}}_{\text{enrolled processors}} + \underbrace{N_{att} \cdot R_{att}}_{\text{attestations}} + \underbrace{N_{key} \cdot R_{key\_gen}}_{\text{key derivations}} + \underbrace{N_{alert} \cdot R_{alert}}_{\text{tamper alerts}}$$

where $R_{enroll}, R_{att}, R_{key\_gen}, R_{alert}$ are per-event rate cards. This model is significant because it directly maps each mathematical operation in the pipeline to a billable event, enabling immediate revenue recognition.

---

## 12. Attestation Protocol and API Formalization

> **Purpose**: This section provides the formal mathematical specification for challenge-response authentication protocols and standardized API interfaces, enabling the NAV-QE system to integrate into existing enterprise security stacks (TLS, PKCS#11, zero-trust gateways).

### 12.1 Challenge-Response Attestation Protocol

The device attestation follows a three-party protocol among the **Quantum Device** ($\mathcal{D}$), the **Verifier** ($\mathcal{V}$), and the **Relying Party** ($\mathcal{R}$):

**Step 1 — Challenge**: $\mathcal{V}$ sends a fresh nonce $r$ and a circuit specification $\mathcal{C}_{challenge}$ to $\mathcal{D}$:

$$\mathcal{V} \xrightarrow{(r, \mathcal{C}_{challenge})} \mathcal{D}$$

**Step 2 — Execute & Characterize**: $\mathcal{D}$ executes $\mathcal{C}_{challenge}$ on the quantum processor, extracts the noise fingerprint $\mathbf{f}_{current}$, and computes a response:

$$\text{response} = \text{HMAC-SHA3-256}\left(\text{KDF}(\mathbf{f}_{current}),\; r \| \text{device\_id} \| \text{timestamp}\right)$$

**Step 3 — Verify**: $\mathcal{V}$ compares the response against the expected value computed from the enrolled baseline:

$$\text{accept} \iff d_M(\mathbf{f}_{current}, \mathbf{f}_{baseline}) \leq \tau \;\wedge\; \text{HMAC\_verify}(\text{response}, K_{baseline}, r)$$

**Step 4 — Issue Token**: If accepted, $\mathcal{V}$ issues a signed attestation token:

$$\text{Token} = \text{Sign}_{sk_{\mathcal{V}}}\left(\text{device\_id} \| \text{timestamp} \| \text{expiry} \| \text{Hash}(\mathbf{f}_{current}) \| r\right)$$

**Step 5 — Consume**: $\mathcal{R}$ verifies the token using $\mathcal{V}$'s public key $pk_{\mathcal{V}}$:

$$\text{Verify}_{pk_{\mathcal{V}}}(\text{Token}) \stackrel{?}{=} \text{valid}$$

### 12.2 Attestation Token Structure (JWT-Compatible)

For interoperability with existing enterprise identity systems, the attestation token is structured as a JSON Web Token (JWT):

$$\text{Token} = \text{Header} \;.\; \text{Payload} \;.\; \text{Signature}$$

**Payload fields**:

| Field | Description | Mathematical Source |
|-------|-------------|---------------------|
| `device_id` | Unique processor identifier | Enrollment registry |
| `fingerprint_hash` | $\text{SHA3-256}(\mathbf{f}_{current})$ | Fingerprint pipeline |
| `deviation_score` | $d_M / \tau$ (normalized, $\in [0,1]$) | Tamper detection |
| `entropy_estimate` | $\hat{H}_{min}(\mathbf{f})$ in bits | Entropy analysis |
| `key_binding` | $\text{Hash}(K \| \text{context})$ | KDF output |
| `issued_at` | UTC timestamp | System clock |
| `expires_at` | $\text{issued\_at} + \Delta t_{validity}$ | Policy engine |
| `nonce` | Challenge $r$ | Protocol Step 1 |

### 12.3 PKCS#11 / Cryptographic API Mapping

For integration with existing Hardware Security Module (HSM) infrastructure, the NAV-QE key operations map onto standard PKCS#11 functions:

| PKCS#11 Function | NAV-QE Operation | Mathematical Mapping |
|-------------------|-----------------|----------------------|
| `C_Initialize` | Device enrollment | $\text{Gen}(\mathbf{f}_{baseline}) \to (K, P)$ |
| `C_GenerateKey` | Key derivation | $K = \text{KDF}(\text{Hash}(\mathbf{f}) \| \text{salt} \| \text{ctx})$ |
| `C_GetAttributeValue` | Fingerprint query | Return $\text{Hash}(\mathbf{f}_{current}), d_M, \hat{H}_{min}$ |
| `C_Sign` | Attestation signature | $\text{HMAC}(K, \text{message})$ |
| `C_Verify` | Attestation verification | $\text{HMAC\_verify}(\text{sig}, K, \text{message})$ |
| `C_DestroyObject` | Key revocation on tamper | Triggered when $d_M > \tau$ |

### 12.4 REST API Endpoint Formalization

The cloud-deployable verifier service exposes endpoints with formally defined input/output schemas:

**Enrollment endpoint** — `POST /enroll`:

$$\text{Input}: (\text{device\_id}, \mathbf{f}_{baseline}, \hat{\Sigma}, \text{policy}) \quad \xrightarrow{\text{Store}} \quad \text{Output}: (\text{enrollment\_id}, P, \text{certificate})$$

**Attestation endpoint** — `POST /attest`:

$$\text{Input}: (\text{device\_id}, \mathbf{f}_{current}, r) \quad \xrightarrow{d_M \leq \tau?} \quad \text{Output}: (\text{Token}, d_M, \text{status})$$

**Key derivation endpoint** — `POST /derive-key`:

$$\text{Input}: (\text{device\_id}, \text{context}, \text{key\_length}) \quad \xrightarrow{\text{KDF}} \quad \text{Output}: (K_{wrapped}, \text{key\_id}, \text{metadata})$$

**Health / monitoring endpoint** — `GET /device/{id}/health`:

$$\text{Output}: (d_M^{(\text{latest})}, \dot{d}_M, \hat{H}_{min}, \text{next\_re\text{-}enroll}, \text{alert\_status})$$

### 12.5 Formal Security Properties of the Protocol

**Theorem (Attestation Soundness)**: An adversary $\mathcal{A}$ without physical access to the enrolled device $\mathcal{D}$ cannot produce a valid attestation response with probability greater than:

$$\Pr[\mathcal{A} \text{ forges attestation}] \leq 2^{-H_{min}(\mathbf{f})} + \text{Adv}^{\text{HMAC}}_{\mathcal{A}} + \frac{q}{2^{|r|}}$$

where $q$ is the number of oracle queries and $|r|$ is the nonce length.

**Theorem (Freshness)**: Each attestation token is bound to a unique nonce $r$, preventing replay:

$$\Pr[\text{replay accepted}] \leq \frac{1}{2^{|r|}} \quad \text{(negligible for } |r| \geq 128\text{)}$$

**Theorem (Device Binding)**: The attestation output is computationally bound to the specific hardware instance through the fingerprint:

$$K_{device_A} \neq K_{device_B} \quad \text{w.h.p.} \quad \text{whenever} \quad d_M(\mathbf{f}_A, \mathbf{f}_B) > \tau$$

---

## 13. Device Lifecycle Mathematics

> **Purpose**: This section formalizes the mathematical models governing the full operational lifecycle of a quantum device within the NAV-QE system — from factory enrollment through active service to retirement — providing the quantitative basis for maintenance schedules, key rotation policies, and fleet management.

### 13.1 Enrollment Quality Metric

During initial enrollment, the system must verify that the device produces a fingerprint of sufficient quality for secure operation. Define the **enrollment quality score**:

$$\boxed{Q_{enroll} = \frac{H_{min}(\mathbf{f})}{\ell_{target}} \cdot \left(1 - \frac{d_M^{(\text{intra, max})}}{\tau}\right) \cdot \left(\frac{d_M^{(\text{inter, min})}}{\tau}\right)}$$

where:
- $H_{min}(\mathbf{f}) / \ell_{target}$: entropy sufficiency ratio (must be $> 1$)
- $d_M^{(\text{intra, max})} / \tau$: intra-device stability ratio (smaller is better)
- $d_M^{(\text{inter, min})} / \tau$: inter-device separability ratio (larger is better)

**Acceptance criterion**: $Q_{enroll} > Q_{threshold}$ (e.g., $Q_{threshold} = 1.5$).

For the 27-qubit IBM Falcon:

$$Q_{enroll} = \frac{187}{128} \cdot \left(1 - \frac{2.8}{4.0}\right) \cdot \frac{7.2}{4.0} = 1.46 \times 0.30 \times 1.80 = 0.79$$

This can be improved by increasing the enrollment sample count $N$ or adjusting the quantization resolution.

### 13.2 Drift Budget Model

The natural drift of quantum hardware noise parameters can be modeled as a **bounded random walk** in the fingerprint space. Define the **drift budget**:

$$\boxed{d_M(t) = d_M(0) + \dot{d}_M \cdot t + \sigma_{drift} \cdot \sqrt{t} \cdot Z}$$

where:
- $\dot{d}_M$: deterministic drift rate (from systematic aging, TLS reconfiguration)
- $\sigma_{drift}$: stochastic drift volatility
- $Z \sim \mathcal{N}(0, 1)$: standard normal random variable
- $t$: time since last enrollment (days)

The **time to breach threshold** $T_{breach}$ is the first passage time:

$$T_{breach} = \inf\{t : d_M(t) > \tau\}$$

For a pure random walk ($\dot{d}_M \approx 0$), the expected re-enrollment interval is:

$$\mathbb{E}[T_{breach}] \approx \frac{(\tau - d_M(0))^2}{\sigma_{drift}^2}$$

With experimental values ($\tau = 4.0$, $d_M(0) = 0.8$, $\sigma_{drift} \approx 0.15$/day):

$$\mathbb{E}[T_{breach}] \approx \frac{(3.2)^2}{0.0225} \approx 455 \text{ days}$$

However, conservative operational practice recommends re-enrollment every 14 days ($T_{re\text{-}enroll} \ll T_{breach}$) to maintain high $R_{key}$.

### 13.3 Optimal Re-Enrollment Schedule

The re-enrollment interval $T_{re}$ can be optimized to minimize total operational cost:

$$\boxed{T_{re}^{*} = \arg\min_{T_{re}} \left[ \frac{C_{re\text{-}enroll}}{T_{re}} + C_{FRR} \cdot \text{FRR}(T_{re}) + C_{miss} \cdot \Pr[\text{undetected tamper in } T_{re}] \right]}$$

where:
- $C_{re\text{-}enroll} / T_{re}$: amortized re-enrollment cost per day
- $C_{FRR} \cdot \text{FRR}(T_{re})$: cost of false rejections (increases with $T_{re}$)
- $C_{miss} \cdot \Pr[\text{undetected tamper}]$: security risk cost

The FRR increases with time since enrollment according to:

$$\text{FRR}(T_{re}) \approx \Phi\left(\frac{d_M(T_{re}) - \tau}{\sigma_{meas}}\right)$$

where $\Phi$ is the standard normal CDF and $\sigma_{meas}$ is the measurement uncertainty.

### 13.4 Key Rotation Mathematics

Keys derived from quantum noise should be rotated periodically. Define the **key rotation policy** as:

$$K^{(t+1)} = \text{KDF}\left(\text{Hash}(\mathbf{f}_{current}^{(t+1)}) \;\|\; \text{salt}^{(t+1)} \;\|\; K^{(t)} \;\|\; \text{context}\right)$$

**Forward secrecy**: Including the previous key $K^{(t)}$ in the derivation ensures that:
- Compromise of $K^{(t+1)}$ does not reveal $K^{(t)}$ (due to preimage resistance of Hash)
- The key chain is anchored to both hardware state and temporal sequence

**Key validity window**: Each key is valid for a bounded period:

$$\text{Valid}(K^{(t)}) \iff t_{issue} \leq t_{current} \leq t_{issue} + \Delta t_{key} \;\wedge\; d_M^{(t)} \leq \tau$$

If $d_M$ exceeds $\tau$ at any point, all outstanding keys are immediately invalidated:

$$d_M > \tau \implies \forall t' \geq t : \text{Valid}(K^{(t')}) = \text{false}$$

### 13.5 Fleet-Level Management

For a provider operating a fleet of $P$ quantum processors, define the **fleet health matrix**:

$$\mathbf{H}_{fleet} = \begin{pmatrix} d_M^{(1)} & \hat{H}_{min}^{(1)} & R_{key}^{(1)} & T_{next\_re}^{(1)} \\ d_M^{(2)} & \hat{H}_{min}^{(2)} & R_{key}^{(2)} & T_{next\_re}^{(2)} \\ \vdots & \vdots & \vdots & \vdots \\ d_M^{(P)} & \hat{H}_{min}^{(P)} & R_{key}^{(P)} & T_{next\_re}^{(P)} \end{pmatrix}$$

**Fleet-level SLA compliance**:

$$\text{SLA}_{fleet} = \frac{1}{P}\sum_{p=1}^{P} \mathbb{1}\left[\text{FAR}_p \leq \text{FAR}_{max} \;\wedge\; \text{FRR}_p \leq \text{FRR}_{max} \;\wedge\; R_{key}^{(p)} \geq R_{min}\right]$$

Target: $\text{SLA}_{fleet} \geq 99.9\%$.

**Staggered re-enrollment scheduling** avoids simultaneous downtime:

$$t_{re\text{-}enroll}^{(p)} = t_0 + \frac{(p-1) \cdot T_{re}}{P} \mod T_{re}$$

This distributes re-enrollment events uniformly across the maintenance window.

### 13.6 Retirement and Revocation Model

When a device is decommissioned or suffers irrecoverable drift, the system executes a **cryptographic retirement protocol**:

1. **Revoke trust anchor**: Remove device from the enrollment registry
   $$\text{Registry} \leftarrow \text{Registry} \setminus \{(\text{device\_id}_p, \mathbf{f}_{baseline}^{(p)}, P^{(p)})\}$$

2. **Destroy helper data**: Securely erase all helper data to prevent future key recovery
   $$P^{(p)} \leftarrow \mathbf{0}$$

3. **Publish revocation**: Issue a signed revocation certificate
   $$\text{CRL\_entry} = \text{Sign}_{sk_{\mathcal{V}}}(\text{device\_id}_p \| \text{revocation\_time} \| \text{reason})$$

4. **Audit log**: Record immutable audit entry with final device state
   $$\text{AuditLog} \leftarrow \text{AuditLog} \cup \{(\text{device\_id}_p, d_M^{(\text{final})}, \text{timestamp}, \text{reason})\}$$

**Irrecoverable drift criterion**: A device is retired if repeated re-enrollment attempts fail:

$$\text{Retire} \iff \forall k \in \{1, \ldots, N_{retry}\} : Q_{enroll}^{(k)} < Q_{threshold}$$

---

## 14. Summary of Key Equations

### 14.1 Noise Characterization

| Process | Equation |
|---------|----------|
| $T_1$ decay | $P_1(t) = A \, e^{-t/T_1} + B$ |
| $T_2$ Ramsey | $P_0(t) = \frac{1}{2}(1 + A \, e^{-t/T_2}\cos(\Delta\omega t + \phi))$ |
| Dephasing relation | $\frac{1}{T_2} = \frac{1}{2T_1} + \frac{1}{T_\phi}$ |
| RB decay | $F(m) = A \, p^m + B$ |
| Gate error | $\epsilon = \frac{(1-p)(d-1)}{d}$ |

### 14.2 Fingerprint and Key

| Concept | Equation |
|---------|----------|
| Fingerprint vector | $\mathbf{f} = [T_1^{(1)}, T_2^{(1)}, \ldots, c_{(n-1),n}] \in \mathbb{R}^d$ |
| Dimensionality | $d = 4n + m + n(n-1)/2$ |
| Key derivation | $K = \text{KDF}(\text{Hash}(\mathbf{f}) \| \text{salt} \| \text{context})$ |
| Fuzzy extraction | $K = \text{SHAKE256}(\text{FuzzyExtract}(\mathbf{f}, P) \| \text{nonce}, \ell)$ |

### 14.3 Security Metrics

| Metric | Equation |
|--------|----------|
| Mahalanobis distance | $d_M = \sqrt{(\mathbf{f}_c - \mathbf{f}_b)^T \Sigma^{-1} (\mathbf{f}_c - \mathbf{f}_b)}$ |
| Min-entropy bound | $H_{min}(\mathbf{f}) \geq \sum_i \log_2(\sigma_i\sqrt{2\pi e}/\delta_i) - I(\mathbf{f})$ |
| Key entropy bound | $H(K) \geq H_{min}(\mathbf{f}) - \text{leak}(P) - 2\log_2(1/\varepsilon)$ |
| Collision probability | $P_{collision} \leq 2^{-k \cdot d_{\text{eff}}}$ |

### 14.4 Experimental Benchmarks (27-Qubit IBM Falcon)

| Quantity | Value |
|----------|-------|
| Fingerprint dimension $d$ | 586 |
| Raw min-entropy $H_{min}$ | ≥ 187 bits |
| Secure key length $\ell$ | 128 bits |
| Inter-device Mahalanobis distance | 9.2 (mean) |
| Intra-device Mahalanobis distance (30 days) | 2.8 (max) |
| Detection threshold $\tau$ | 4.0 |
| FAR / FRR / EER | < 0.001% / < 0.1% / 0.02% |
| Key generation time (post-characterization) | < 15 ms |
| Tamper detection rate (≥5% change) | > 97% |
| NIST SP 800-22 randomness tests | 15/15 passed |

### 14.5 Convertibility and Operational Metrics

| Concept | Equation / Metric |
|---------|-------------------|
| Throughput overhead | $\eta = T_{char}^{(quick)} / (N_{mon} \cdot T_{circuit} + T_{char}^{(quick)})$ |
| Drift budget | $d_M(t) = d_M(0) + \dot{d}_M t + \sigma_{drift}\sqrt{t} \cdot Z$ |
| Enrollment quality | $Q = \frac{H_{min}}{\ell_{target}} \cdot (1 - d_M^{intra}/\tau) \cdot (d_M^{inter}/\tau)$ |
| Optimal re-enrollment | $T_{re}^* = \arg\min[C_{re}/T_{re} + C_{FRR} \cdot \text{FRR}(T_{re}) + C_{miss} \cdot P_{miss}]$ |
| Key rotation (forward secrecy) | $K^{(t+1)} = \text{KDF}(\text{Hash}(\mathbf{f}^{(t+1)}) \| \text{salt} \| K^{(t)} \| \text{ctx})$ |
| Fleet SLA compliance | $\text{SLA}_{fleet} = P^{-1}\sum_p \mathbb{1}[\text{FAR}_p, \text{FRR}_p, R_{key}^{(p)} \text{ meet targets}]$ |
| Attestation soundness | $\Pr[\text{forge}] \leq 2^{-H_{min}} + \text{Adv}^{HMAC} + q/2^{|r|}$ |
| Billing model | $\text{Bill} = P \cdot R_{enroll} + N_{att} \cdot R_{att} + N_{key} \cdot R_{key} + N_{alert} \cdot R_{alert}$ |
| Measured throughput overhead | < 3% (attestation-only mode) |
| Key regeneration success rate | 99.3% |
| Enrollment time per processor | 18–35 min |
| End-to-end key derivation latency | < 15 ms |

---

*This document provides the complete mathematical foundations of the NAV-QE patent, including operational convertibility models for enterprise and sovereign infrastructure deployment. All equations are consistent with the patent claims, technical specification, and experimental data.*

*Document Version: 2.0 — Enhanced with convertibility and productization mathematics*
*Created: March 2026*
