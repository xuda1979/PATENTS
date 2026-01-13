# Mathematical Rigor Analysis of QCH-KEM Technical Specification

This report analyzes the mathematical definitions, security bounds, and algorithmic logic presented in the QCH-KEM Technical Specification.

## 1. Security Reduction Bound (Critical)

**Issue**: The stated security theorem contradicts the claimed "Composite Security Guarantee".

**Text Reference**:
> **Theorem (Hybrid Security)**: ... $\text{Adv}^{\text{KEM}}_{\text{QCH-KEM}}(\mathcal{A}) \leq \text{Adv}^{\text{MLWE}}(\mathcal{A}) + \text{Adv}^{\text{QKD}}(\mathcal{A})$
> **Interpretation**: ... An adversary must break BOTH the PQC layer AND the QKD layer...

**Analysis**:
The additive bound $\text{Adv}_{Total} \leq \text{Adv}_{PQC} + \text{Adv}_{QKD}$ is a standard bound for systems that are secure if **all** components are secure (intersection of security), or for analyzing failure probabilities. However, for a **Robust Combiner** (where the system is secure if **at least one** component is secure), this bound is loose and misleading.

If the adversary breaks the PQC layer ($\text{Adv}_{PQC} \approx 1$), the bound becomes $\text{Adv}_{Total} \leq 1 + \text{Adv}_{QKD}$, which provides no security guarantee (since probability $\leq 1$ is trivial). This contradicts the claim that the adversary must break **BOTH** layers.

**Correction**:
For a robust combiner in the Random Oracle Model (ROM), if the key derivation function $K = H(K_{PQC} || K_{QKD})$ is modeled as a random oracle, the security advantage is bounded by the **minimum** of the advantages (or the product, depending on the specific game definition):
$$ \text{Adv}^{\text{KEM}}_{\text{QCH-KEM}}(\mathcal{A}) \leq \min(\text{Adv}^{\text{MLWE}}(\mathcal{A}), \text{Adv}^{\text{QKD}}(\mathcal{A})) $$
This correctly reflects that the system remains secure as long as one component is secure.

## 2. Entropy Extraction Formula (Incorrect)

**Issue**: The formula for output entropy is mathematically incorrect for randomness extractors.

**Text Reference**:
> $$H_{output} = H_{input} \cdot \frac{n_{out}}{n_{in}}$$

**Analysis**:
This formula implies that output entropy scales linearly with the compression ratio.
- **Scenario**: Suppose we have $n_{in}=1000$ bits with min-entropy $k=100$ bits. We extract $n_{out}=100$ bits.
- **Formula Prediction**: $H_{output} = 100 \cdot \frac{100}{1000} = 10$ bits.
- **Reality**: A good extractor (like the Leftover Hash Lemma suggests) would preserve almost all 100 bits of entropy, resulting in $H_{output} \approx 100$ bits (full entropy output).

The formula suggests that compressing the input **destroys** entropy proportionally, whereas the goal of extraction is to **concentrate** entropy.

**Correction**:
The relationship should be defined by the Leftover Hash Lemma (which is correctly cited immediately after). The first equation should be removed or replaced with $H_{output} \approx n_{out}$ (assuming $n_{out} \le H_{min}(input) - 2\log(1/\epsilon)$).

## 3. QKD Security Contribution Logic (Inconsistent)

**Issue**: Dimensional mismatch and numerical inconsistency in the dynamic parameter selection.

**Text Reference**:
```python
# QKD security contribution (simplified model)
qkd_security = min(qkd_rate / 1000, 128)  # Cap at 128 bits
```
> Comment: "1 bit/s QKD → 0.01 bits security contribution"

**Analysis**:
1.  **Numerical Mismatch**:
    - Code: `rate / 1000` implies a factor of **0.001**.
    - Comment: Claims **0.01**. There is an order of magnitude difference.
2.  **Dimensional Error**:
    - `qkd_rate` is in **bits/second** ($[T^{-1}]$).
    - `qkd_security` is in **bits** (dimensionless quantity of information).
    - Equating Rate to Bits requires a time factor (e.g., session duration). The formula implies that a faster rate inherently adds more security bits *regardless of how many keys are actually used*.
    - **Correct Logic**: Security depends on the **amount** of QKD key material consumed ($L_{key}$), not the rate at which it was generated. If the system consumes 128 bits of QKD key, it adds 128 bits of entropy (assuming one-time pad equivalence), regardless of whether it took 1 second or 1 hour to generate.

**Correction**:
The logic should likely be based on the **available buffer size** or **configured key consumption per session**, not the generation rate.
```python
# Example Correction
bits_consumed = 128 # defined by protocol
qkd_security = bits_consumed # direct entropy addition
```

## 5. Patent Claim Inaccuracies

**Issue**: Technical terminology in claims does not match the specified algorithm (ML-KEM).

**Text Reference**:
> **Claim 3**: "... adjusting lattice dimension $n$ according to: $n_{adjusted} = n_{base} + \alpha \cdot \Delta S$"
> **Claim 11**: "... $n = n_{min} + \lfloor \frac{n_{max} - n_{min}}{R_{max}} \cdot (R_{max} - R_{QKD}) \rfloor$ wherein $n$ is the lattice dimension..."

**Analysis**:
The specification explicitly identifies **ML-KEM (Kyber)** as the PQC algorithm.
- In ML-KEM, the ring dimension $n$ is **fixed at 256** for all security levels (512, 768, 1024).
- The parameter that varies is the **module rank** ($k=2, 3, 4$).
- Varying $n$ (lattice dimension) is characteristic of generic LWE or other schemes, but not ML-KEM.
- Claiming to adjust "lattice dimension" for ML-KEM is technically incorrect and could invalidate the claim or make it unenforceable for ML-KEM implementations.

**Correction**:
Replace "lattice dimension" with "module rank" or "security parameter set" in the claims to accurately reflect ML-KEM's structure.

## 6. Summary of Recommendations

1.  **Update Security Theorem**: Change the additive bound to a minimization bound to support the "break both" claim.
2.  **Fix Entropy Formula**: Remove the linear scaling equation; rely on the Leftover Hash Lemma.
3.  **Revise Parameter Selection**: Base security contribution on **key length consumed**, not generation rate. Fix the 0.001 vs 0.01 discrepancy.
4.  **Correct Claim Terminology**: Change "lattice dimension" to "module rank" or "parameter set" in Claims 3 and 11.
