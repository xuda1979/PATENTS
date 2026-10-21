# Core-only diagnostic fix (next remote iteration)

Runtime error 507014 (stream sync failure) occurs when GetTensorC is called
OUTSIDE the Iterate loop. The amplitude==-2 core-only mode must therefore
reuse the normal Iterate loop and skip only the activation staging:

Inside the main while loop:
  bool coreOnly = (amplitude_ == -2.0f);
  ... Tanh / Muls(amplitude*0.5 sign trick) / Adds(1.0) as today ...
  if (!coreOnly) { Cast(actF32, actLocal, ...); Mul(cLocal, cLocal, actF32); }
  Cast(outLocal, cLocal, ...);   // straight from the core tile
  DataCopy(outGm_[rowsDone*rankDim_], outLocal, actCopy);

Expected: out ~= 1 + 0.5*tanh(A@B+bias) elementwise (no activation factor).
If this matches (max_err < 0.02), the matmul/bias/tiling path is proven and
the residual defect is confined to the activation staging interaction.
Then remove the diagnostic modes and gating proceeds with the standard
fp16-tolerance check -> four-arm run -> msprof counters.
