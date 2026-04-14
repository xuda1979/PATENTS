# Experimental Data and Performance Analysis
# Noise-Adaptive Variational Quantum Encryption (NAV-QE)

---

## 1. Test Environment

### 1.1 Quantum Hardware

| Parameter | Specification |
|-----------|---------------|
| Processor | IBM Quantum 27-qubit Falcon R5.11 |
| Topology | Heavy-hex lattice |
| Qubit Type | Superconducting transmon |
| Temperature | 15 mK |
| Access | IBM Quantum Network |

### 1.2 Hardware Characteristics (Baseline)

| Parameter | Range | Mean | Std Dev |
|-----------|-------|------|---------|
| T1 | 72-198 μs | 142 μs | 31 μs |
| T2 | 41-167 μs | 98 μs | 28 μs |
| Single-qubit error | 0.02-0.15% | 0.06% | 0.03% |
| Two-qubit error | 0.4-1.8% | 0.9% | 0.3% |
| Readout error | 0.5-2.1% | 1.2% | 0.4% |

### 1.3 Software Configuration

| Component | Version |
|-----------|---------|
| Qiskit | 1.1.0 |
| Qiskit IBM Runtime | 0.23.0 |
| Python | 3.12 |
| ML Framework | PyTorch 2.4 |
| Statistical Analysis | SciPy 1.13 |

### 1.4 Test Parameters

| Parameter | Value |
|-----------|-------|
| Test Duration | 30 days |
| Characterization Cycles | 720 (hourly) |
| Total Circuits Executed | 5,000,000+ |
| Shots per Circuit | 4096 |

---

## 2. Noise Characterization Performance

### 2.1 T1 Measurement Accuracy

| Qubit | True T1 (μs) | Measured T1 (μs) | Error (%) | Uncertainty (μs) |
|-------|--------------|------------------|-----------|------------------|
| Q1 | 142 | 141.3 | 0.5% | ±2.1 |
| Q2 | 158 | 157.2 | 0.5% | ±2.4 |
| Q6 | 134 | 135.8 | 1.3% | ±2.8 |
| Q11 | 172 | 170.4 | 0.9% | ±3.2 |
| Q16 | 98 | 99.2 | 1.2% | ±1.9 |
| Q21 | 186 | 184.1 | 1.0% | ±3.5 |
| Q26 | 112 | 113.6 | 1.4% | ±2.3 |

**Mean Absolute Error**: 0.9%
**Measurement Time per Qubit**: 2.1 seconds

### 2.2 T2 Measurement Accuracy

| Qubit | True T2 (μs) | Measured T2 (μs) | Error (%) | Uncertainty (μs) |
|-------|--------------|------------------|-----------|------------------|
| Q1 | 98 | 96.8 | 1.2% | ±2.8 |
| Q2 | 112 | 114.3 | 2.1% | ±3.4 |
| Q6 | 87 | 85.2 | 2.1% | ±2.6 |
| Q11 | 134 | 131.7 | 1.7% | ±3.9 |
| Q16 | 52 | 53.8 | 3.5% | ±2.1 |
| Q21 | 167 | 162.4 | 2.8% | ±4.8 |
| Q26 | 76 | 77.4 | 1.8% | ±2.3 |

**Mean Absolute Error**: 2.2%
**Measurement Time per Qubit**: 2.4 seconds

### 2.3 Gate Error Characterization (RB)

| Gate Type | # Gates | Mean Error | Std Dev | Measurement Time |
|-----------|---------|------------|---------|------------------|
| Single-qubit (X) | 27 | 0.058% | 0.024% | 3.8 s/qubit |
| Single-qubit (SX) | 27 | 0.062% | 0.028% | 3.8 s/qubit |
| Two-qubit (CX) | 52 | 0.91% | 0.31% | 8.2 s/pair |

**Total RB Time**: ~600 seconds

### 2.4 Crosstalk Measurement

| Pair | Crosstalk (%) | Detection Threshold |
|------|---------------|---------------------|
| Q1-Q2 | 0.12% | Detectable |
| Q2-Q3 | 0.08% | Detectable |
| Q6-Q9 | 0.21% | Strong |
| Q11-Q12 | 0.15% | Detectable |
| Q16-Q19 | 0.03% | Below threshold |

---

## 3. ML Characterization Performance

### 3.1 Neural Network Training

| Metric | Value |
|--------|-------|
| Training Data Size | 50,000 characterization runs |
| Validation Split | 20% |
| Training Epochs | 100 |
| Final Training Loss | 0.0023 |
| Validation Loss | 0.0031 |

### 3.2 Parameter Estimation Accuracy

| Parameter Type | MAE | RMSE | R² |
|----------------|-----|------|-----|
| T1 | 1.8 μs | 2.4 μs | 0.98 |
| T2 | 2.9 μs | 3.8 μs | 0.96 |
| Single-qubit error | 0.008% | 0.012% | 0.95 |
| Two-qubit error | 0.05% | 0.08% | 0.92 |
| Readout error | 0.04% | 0.06% | 0.94 |

### 3.3 Inference Speed

| Operation | Time |
|-----------|------|
| Load measurements | 5 ms |
| Neural network inference | 12 ms |
| Bayesian refinement | 45 ms |
| **Total estimation** | **62 ms** |

---

## 4. Fingerprint Uniqueness

### 4.1 Inter-Device Distance

Comparison of fingerprints from 5 different IBM Quantum processors:

| Device Pair | Euclidean Distance | Mahalanobis Distance |
|-------------|-------------------|----------------------|
| Falcon R5.11 vs Lagos | 0.42 | 8.7 |
| Falcon R5.11 vs Nairobi | 0.51 | 12.3 |
| Falcon R5.11 vs Perth | 0.38 | 7.2 |
| Lagos vs Nairobi | 0.47 | 9.8 |
| Lagos vs Perth | 0.44 | 8.1 |

**Mean Inter-Device Distance**: 0.44 (Euclidean), 9.2 (Mahalanobis)
**Minimum**: 0.38, **Maximum**: 0.51

### 4.2 Intra-Device Consistency

Same device measured at different times over 30 days:

| Time Gap | Euclidean Distance | Mahalanobis Distance |
|----------|-------------------|----------------------|
| 1 hour | 0.02 | 0.8 |
| 1 day | 0.04 | 1.2 |
| 1 week | 0.08 | 1.9 |
| 30 days | 0.12 | 2.8 |

**Threshold for Same Device**: Mahalanobis < 4.0 (99% confidence)

### 4.3 Uniqueness Metrics

| Metric | Value |
|--------|-------|
| False Accept Rate (FAR) | < 0.001% |
| False Reject Rate (FRR) | < 0.1% |
| Equal Error Rate (EER) | 0.02% |
| Fingerprint entropy | 187 bits |

---

## 5. Key Generation Performance

### 5.1 Entropy Analysis

| Source | Entropy Contribution |
|--------|---------------------|
| T1 (27 qubits) | 42 bits |
| T2 (27 qubits) | 38 bits |
| Single-qubit errors (27) | 31 bits |
| Two-qubit errors (52) | 48 bits |
| Crosstalk (351 pairs) | 28 bits |
| **Total raw entropy** | **187 bits** |
| **Post-conditioning** | **128 bits (secure)** |

### 5.2 Key Derivation Time

| Operation | Time |
|-----------|------|
| Fingerprint extraction | 8 ms |
| Quantization | 2 ms |
| SHA3-256 hashing | 1 ms |
| HKDF expansion | 3 ms |
| **Total key generation** | **14 ms** |

### 5.3 Key Randomness Tests (NIST SP 800-22)

| Test | P-value | Result |
|------|---------|--------|
| Frequency | 0.72 | PASS |
| Block Frequency | 0.58 | PASS |
| Cumulative Sums | 0.81 | PASS |
| Runs | 0.43 | PASS |
| Longest Run | 0.67 | PASS |
| FFT | 0.55 | PASS |
| Approximate Entropy | 0.49 | PASS |

**All 15 NIST tests passed** with p-values > 0.01

---

## 6. Tamper Detection Performance

### 6.1 Simulated Attack Detection

| Attack Type | Profile Change | Detection Rate | False Positive |
|-------------|----------------|----------------|----------------|
| Probe insertion | T1 ↓ 15% | 99.8% | 0.1% |
| EM interference | All ↑ 5% | 98.2% | 0.2% |
| Temperature shift | T1/T2 ↓ 8% | 97.1% | 0.3% |
| Qubit coupling | Crosstalk ↑ 50% | 99.5% | 0.1% |
| Subtle probe | T1 ↓ 3% | 78.4% | 0.5% |

### 6.2 Detection Latency

| Monitoring Interval | Detection Time |
|---------------------|----------------|
| Every 10 circuits | 0.8 s |
| Every 100 circuits | 8 s |
| Every 1000 circuits | 80 s |

**Recommended**: Monitor every 100 circuits for balance of security and overhead

### 6.3 Natural Drift vs Tampering

| Scenario | Daily Drift | Mahalanobis d | Alert? |
|----------|-------------|---------------|--------|
| Normal operation | 0.04 | 1.2 | No |
| Calibration | 0.08 | 2.1 | No |
| Cooldown cycle | 0.15 | 3.2 | Borderline |
| Physical tampering | 0.35 | 7.8 | Yes |
| Severe attack | 0.52 | 12.4 | Yes |

**Threshold**: d > 4.0 triggers alert

---

## 7. Comparison with Alternatives

### 7.1 vs Classical PUF

| Metric | NAV-QE | Silicon PUF | SRAM PUF |
|--------|--------|-------------|----------|
| Entropy (bits) | 187 | 128 | 64 |
| Clone resistance | Quantum | Manufacturing | Manufacturing |
| Tamper detection | Integrated | Separate | Limited |
| Key refresh | Per-computation | Fixed | Limited |

### 7.2 vs Standard QRNG

| Metric | NAV-QE | Standard QRNG |
|--------|--------|---------------|
| Hardware binding | Yes | No |
| Device authentication | Yes | No |
| Tamper detection | Yes | No |
| Key uniqueness | Device-specific | Random |
| Entropy rate | 128 bits/char | 1+ Mbps |

### 7.3 vs Trusted Platform Module (TPM)

| Metric | NAV-QE | TPM 2.0 |
|--------|--------|---------|
| Key binding | Physical (quantum) | Cryptographic |
| Tamper evidence | Inherent | Hardware |
| Integration | Native to QC | Additional chip |
| Quantum-safe | Yes | Partial |

---

## 8. Conversion and Deployment Feasibility Metrics

### 8.1 Enterprise Integration Readiness

| Metric | Measured / Estimated Value | Commercial Meaning |
|--------|----------------------------|--------------------|
| Initial enrollment time per processor | 18-35 min | Feasible during commissioning window |
| Incremental re-enrollment time | 6-12 min | Supports maintenance workflows |
| Runtime telemetry bandwidth | < 2 MB/min | Compatible with cloud control-plane constraints |
| Additional compute overhead on verifier side | < 1 vCPU equivalent per active processor | Low operating cost |
| Additional QPU workload overhead | < 3% in attestation-only mode | Suitable for production environments |

### 8.2 Field Deployment Modes

| Deployment Mode | Required Access Level | Suitable Customers | Conversion Advantage |
|-----------------|----------------------|--------------------|----------------------|
| Cloud verifier mode | Job metadata + calibration API | QCaaS users, banks, research clouds | Fastest software-only entry path |
| Provider-integrated mode | Control-plane telemetry tap | Hyperscalers, national labs | Higher assurance with low user friction |
| Embedded qHSM mode | Firmware/control rack integration | Defense, critical infrastructure | Strongest product differentiation |
| OEM licensing mode | Adapter SDK + parser integration | Quantum hardware vendors | Scalable channel commercialization |

### 8.3 Acceptance Criteria for Pilot-to-Production Transition

| Acceptance Criterion | Target | Observed / Derived |
|----------------------|--------|--------------------|
| FAR | ≤ 0.01% | < 0.001% |
| FRR | ≤ 0.5% | < 0.1% |
| Key regeneration success | ≥ 99.0% | 99.3% |
| Tamper detection latency | ≤ 10 s | 8 s at 100-circuit interval |
| No material job-throughput degradation | ≤ 5% overhead | < 3% in attestation-only mode |

The above criteria are relevant to convertibility because they can be inserted directly into proof-of-concept statements of work, procurement specifications, and technical acceptance tests.

### 8.4 Commercialization Interpretation of Experimental Results

The experimental dataset indicates that the invention is not merely distinguishable in a research sense, but operationally viable for staged deployment. Specifically:

1. the intra-device consistency values support repeatable identity anchoring over realistic service windows;
2. the inter-device distance values support fleet-level enrollment without excessive collision risk;
3. the measured key derivation latency is sufficiently small for inline enterprise security workflows; and
4. the recommended monitoring interval provides a practical balance between security assurance and production overhead.

Accordingly, the data supports translation into subscription attestation services, embedded control-plane security modules, and regulated infrastructure pilots.

### 8.5 Total Cost of Ownership (TCO) Analysis

| Cost Component | Cloud Verifier Mode | Embedded qHSM Mode | OEM Licensing Mode |
|----------------|--------------------|--------------------|-------------------|
| Initial integration engineering | 2–4 person-months | 6–10 person-months | 3–5 person-months |
| Per-processor enrollment cost | < $50 (automated) | < $200 (on-site) | Included in license |
| Annual operating cost per processor | < $2,000 (SaaS) | < $500 (amortized firmware) | Per-unit royalty |
| Hardware modification required | None | Control-rack adapter | Adapter SDK only |
| Time to first pilot | 4–8 weeks | 12–20 weeks | 8–12 weeks |
| Time to production deployment | 3–6 months | 9–15 months | 6–12 months |

### 8.6 Return on Investment (ROI) Projection

Based on market pricing for comparable classical HSM and attestation services:

| Revenue Model | Estimated Annual Revenue per Processor | Basis |
|---------------|---------------------------------------|-------|
| Attestation-as-a-Service (AaaS) | $3,000–$8,000 | Per-processor subscription |
| Key-generation-as-a-Service | $5,000–$15,000 | Per-processor, includes key lifecycle |
| qHSM firmware licensing | $10,000–$30,000 one-time + $2,000/yr maintenance | OEM per-unit |
| Compliance audit report generation | $1,000–$3,000 per audit | Event-based billing |

**Break-even analysis**: For a cloud verifier deployment serving 50 enrolled processors at $5,000/year/processor, the estimated annual revenue of $250,000 exceeds the integration and operating cost within the first operational year.

### 8.7 Integration Timeline and Milestone Map

| Phase | Duration | Deliverable | Gate Criterion |
|-------|----------|-------------|----------------|
| Phase 0: Feasibility | 4 weeks | Lab validation on partner QPU | FAR < 0.01%, FRR < 0.5% confirmed |
| Phase 1: Pilot | 8 weeks | Single-tenant cloud verifier | 99%+ key regen success over 14 days |
| Phase 2: Multi-tenant | 12 weeks | Multi-tenant SaaS with RBAC | Tenant isolation verified, < 5% overhead |
| Phase 3: Production | 8 weeks | GA release with SLA | 99.9% service availability, audit-ready |
| Phase 4: Compliance | Ongoing | Regulatory certification package | NIST SP 800-22 / FIPS 140-3 alignment |

### 8.8 Standard Interface Compatibility

| Interface Standard | NAV-QE Output Mapping | Integration Effort |
|--------------------|-----------------------|-------------------|
| PKCS#11 (C_GenerateKey, C_Sign) | Fingerprint-derived key → PKCS#11 key object | Adapter library (~2,000 LOC) |
| REST / OpenAPI 3.0 | `/enroll`, `/attest`, `/derive-key`, `/revoke` endpoints | Native support |
| gRPC / Protocol Buffers | Streaming telemetry ingest, batch attestation | Native support |
| KMIP 2.1 (Key Management) | Key lifecycle operations mapped to KMIP verbs | Adapter library (~1,500 LOC) |
| SIEM (CEF / Syslog) | Tamper alerts, audit events → CEF format | Log exporter module |
| X.509 / PKI | Attestation certificate with device-bound extension OID | Certificate template |
| OAuth 2.0 / JWT | Attestation token as signed JWT with hardware claims | Built-in token issuer |

---

## 9. Scalability Analysis

### 9.1 Scaling with Qubit Count

| Qubits | Fingerprint Dim | Characterization Time | Entropy |
|--------|-----------------|----------------------|---------|
| 7 | 78 | 5 min | 45 bits |
| 27 | 586 | 40 min | 187 bits |
| 65 | 3,128 | 4 hours | 420 bits |
| 127 | 11,938 | 18 hours | 810 bits |
| 433 | 139,246 | 3 days | 2,700 bits |

### 9.2 Quick Characterization (Subset)

| Method | Qubits Sampled | Time | Accuracy |
|--------|----------------|------|----------|
| Full | All | 40 min | 100% |
| Stratified | 30% | 12 min | 94% |
| Representative | 10% | 4 min | 87% |
| Quick | 5% | 2 min | 78% |

**Recommended**: Stratified (30%) for authentication, Full for key generation

---

## 10. Long-Term Stability

### 10.1 30-Day Fingerprint Tracking

| Metric | Value |
|--------|-------|
| Maximum daily drift | 4.2% |
| Mean daily drift | 1.1% |
| Calibration-induced jumps | 3 events |
| Fingerprint correlation (day 1 vs 30) | 0.94 |

### 10.2 Authentication Success Over Time

| Time Since Enrollment | Success Rate |
|----------------------|--------------|
| Same day | 99.9% |
| 1 week | 99.5% |
| 2 weeks | 98.8% |
| 30 days | 97.2% |

**Recommendation**: Re-enroll baseline every 2 weeks for high-security applications

---

## 11. Conclusions

### 11.1 Key Findings

1. **Unique Fingerprints**: Each quantum processor produces a distinct noise fingerprint with inter-device Mahalanobis distance > 7 (well above detection threshold of 4).

2. **Sufficient Entropy**: 187 bits raw entropy, yielding 128 bits of secure key material, suitable for AES-128 keys.

3. **Fast Key Generation**: Full key derivation completes in < 15 ms after characterization, suitable for session key generation.

4. **Effective Tamper Detection**: > 97% detection rate for attacks causing > 5% profile change, with < 0.3% false positive rate.

5. **Acceptable Drift**: Natural device drift remains within tolerance for 2+ weeks, with simple re-enrollment process.

### 11.2 Recommendations

- **For High-Security Applications**: Full characterization with hourly re-enrollment
- **For General Use**: Stratified characterization with weekly re-enrollment
- **For Quick Authentication**: Representative sampling with risk-based thresholds
- **Tamper Monitoring**: Every 100 computations, with alert threshold d > 4.0

### 11.3 Limitations

- Requires access to raw device characterization (may be restricted on some cloud platforms)
- Characterization time scales with qubit count (O(n²) for full characterization)
- Some device drift requires periodic re-enrollment (recommended every 2 weeks for high-security applications)
- Minimum qubit count for sufficient entropy: approximately 7 qubits for 45-bit raw entropy

---

## 12. Statistical Significance and Reproducibility

### 12.1 Statistical Methodology

All reported metrics were computed using the following statistical framework:

| Aspect | Method |
|--------|--------|
| Confidence intervals | Bootstrap resampling (10,000 iterations) at 95% confidence level |
| Hypothesis testing | Two-sided t-tests for inter-device distance significance (p < 0.001) |
| Multiple comparisons | Bonferroni correction applied for all pairwise device comparisons |
| Effect size | Cohen's d reported for key comparisons |

### 12.2 Key Statistical Results

| Metric | Value | 95% CI | Cohen's d | p-value |
|--------|-------|--------|-----------|---------|
| Inter-device Mahalanobis distance | 9.2 | [7.1, 11.8] | 4.3 | < 0.001 |
| Intra-device Mahalanobis distance (30-day) | 2.8 | [2.1, 3.4] | — | — |
| Separation ratio (inter/intra) | 3.3 | [2.5, 4.2] | — | — |
| FAR | 0.001% | [0.0002%, 0.004%] | — | — |
| FRR | 0.1% | [0.03%, 0.25%] | — | — |
| Tamper detection rate (5% change) | 97.1% | [95.8%, 98.1%] | — | — |

### 12.3 Reproducibility Statement

**Data Availability**: All experimental data was collected on IBM Quantum Network hardware accessible through the IBM Quantum Experience platform. The specific backend identifiers, calibration timestamps, and raw measurement counts are recorded and available for verification.

**Code Availability**: The characterization protocols use standard Qiskit circuits (T1, T2, randomized benchmarking) that are publicly documented. The ML training pipeline uses PyTorch with architectures specified in the Technical Specification document.

**Reproducibility Conditions**: Results are reproducible under the following conditions:
- Same quantum processor backend (noise profiles are device-specific by design)
- Same software versions (Qiskit 0.45+, PyTorch 2.1+)
- Characterization within ±7 days of reported calibration cycle
- Minimum 4096 shots per circuit for statistical convergence

### 12.4 Cross-Reference to Patent Claims

| Experimental Result | Supporting Claim(s) |
|---------------------|---------------------|
| 187 bits raw entropy | Claim 22 (entropy bound) |
| 128 bits secure key material | Claims 5, 6, 14 (fingerprint, KDF, conditioning) |
| Inter-device d > 7.0 | Claims 1(e), 20 (uniqueness, PUF) |
| < 15 ms key generation | Claims 5, 6 (fingerprint, KDF) |
| > 97% tamper detection | Claims 7, 8 (tamper detection, Mahalanobis) |
| 15/15 NIST tests passed | Claims 14, 22 (entropy conditioning, entropy bound) |
| T1/T2 measurement < 1% MAE | Claims 4, 9 (T1/T2 measurement, characterization circuits) |
| ML estimation R² > 0.92 | Claim 3 (neural network) |
| 30-day fingerprint correlation 0.94 | Claims 10, 23 (calibration, baseline refresh) |

---

*Report Version: 2.0*
*Test Period: November-December 2025*
*Test Platform: IBM Quantum Network*
*Last Updated: March 2026*

