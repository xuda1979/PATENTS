# Patent Drawing Specifications
# Meta-Weight Generation for On-the-Fly Ephemeral Weights (MWG-EW)

---

## Drawing Requirements

These layouts are conceptual drafting guides and should be converted into formal black-and-white patent figures before filing.

- Format: black-and-white line drawings
- Resolution: at least 300 DPI
- Reference numerals: Arabic numerals, consistent across figures
- Line style: solid arrows for data path, dashed arrows for control path
- No color dependence for meaning
- Use textual prohibition notes or prohibition boxes for blocked paths; do not place oversized cross marks over blocks or labels
- Split long labels across lines and leave enough spacing so blocks, arrows, and annotations do not overlap

---

## Figure 1: Conventional Dense Inference vs Ephemeral-Weight Inference

### Description

Compares a conventional path that repeatedly loads dense FFN matrices from external memory with the proposed path that stores a shared meta-generator and creates temporary descriptors on chip.

### Reference Numerals

| Number | Element |
|--------|---------|
| 100 | Conventional dense path |
| 110 | External weight memory |
| 120 | Dense FFN matrix load |
| 130 | On-chip compute array |
| 140 | Idle or stalled compute time |
| 150 | MWG-EW path |
| 160 | Shared meta-generator |
| 170 | Conditioning input |
| 180 | Temporary descriptors |
| 190 | Local-memory fused execution |

### Layout Sketch

```text
+---------------------------------------------------------------+
| Dense Path [100]                                              |
| External Memory [110] -> Dense Weight Load [120] -> Compute   |
|                                           ^                   |
|                                           |                   |
|                                   Stall / Wait [140]          |
|                                           |                   |
|                                 Compute Array [130]           |
+---------------------------------------------------------------+

+---------------------------------------------------------------+
| MWG-EW Path [150]                                             |
| Shared Meta-Generator [160] <- Conditioning [170]             |
|              |                                                |
|              v                                                |
|      Temporary Descriptors [180] -> Fused Local Execution     |
|                                   in SRAM / Cache [190]       |
+---------------------------------------------------------------+
```

---

## Figure 2: Technical Workflow Overview

### Description

Shows one reviewer-friendly master flow: conditioning input, descriptor generation, on-chip local residency and conversion, immediate matrix consumption, lifecycle release, plus optional decode-time and training-time benefit branches.

### Reference Numerals

| Number | Element |
|--------|---------|
| 200 | Activation block and layer identifier |
| 210 | Conditioning module |
| 220 | Meta-generator |
| 230 | On-chip local memory residency and conversion |
| 240 | Matrix compute unit |
| 250 | Release / overwrite / zeroization |
| 260 | No-write-back constraint |
| 270 | Decode-time branch |
| 280 | Training-time branch |

### Layout Sketch

```text
Activation + Layer ID [200] -> Conditioning [210] -> Meta-Generator [220]
                                               -> On-Chip Local Residency / Conversion [230]
                                               -> Matrix Compute [240]
                                               -> Release / Overwrite / Zeroize [250]

No Write-Back to External Memory [260] constrains [220]-[250]
Decode-Time KV Cache Benefit [270] branches from [250]
Training-Time Recompute / Sync Truncation [280] branches from [250]
```

---

## Figure 3: Temporary Descriptor Tile Lifecycle and Constraint Actions

### Description

Shows a fused lifecycle in which each temporary descriptor tile is generated, resides on chip, is converted or consumed, and is then released before buffer reuse, while write-back, optimizer-state, or synchronization requests are rejected, bypassed, or truncated.

### Reference Numerals

| Number | Element |
|--------|---------|
| 300 | Descriptor tile generation |
| 310 | On-chip residency |
| 320 | On-chip conversion |
| 330 | Immediate consumption |
| 340 | Release / zeroization |
| 350 | Reuse barrier |
| 360 | Blocked write-back / optimizer / sync request |

### Layout Sketch

```text
Generate [300] -> Reside On Chip [310] -> Convert [320] -> Consume [330]
                                              |
                                              v
                                   Release / Zeroize [340] -> Reuse Barrier [350]

Blocked Write-Back / Optimizer / Sync Request [360]
```

---

## Figure 4: Chained Matrix Execution and Prohibited External Materialization

### Description

Shows a prohibited dense-materialization path and the claimed on-chip chained execution path, where a target transform is evaluated as `(XU)V` so the dense matrix `UV` is never instantiated in external memory.

### Reference Numerals

| Number | Element |
|--------|---------|
| 400 | Input activation X |
| 410 | First low-rank factor U |
| 420 | Second low-rank factor V |
| 430 | Intermediate product XU |
| 440 | Output Y |
| 450 | Prohibited dense-materialization path |
| 460 | External-memory prohibition text box |

### Layout Sketch

```text
Prohibited Path:
X [400] -> Dense UV Materialization [450] -> Y [440]

Claimed Path:
X [400] -> U [410] -> XU [430] -> V [420] -> Y [440]

Textual Prohibition Box [460]
```

---

## Figure 5: Decode-Time KV Cache Reallocation and Double Buffering

### Description

Shows an autoregressive decoding scenario in which saved external-memory capacity is reassigned to KV cache storage, while two local buffers are alternated so next-descriptor generation overlaps current matrix computation.

### Reference Numerals

| Number | Element |
|--------|---------|
| 500 | Autoregressive decoding path |
| 510 | Freed external-memory capacity |
| 520 | Reallocated KV cache |
| 530 | Current descriptor buffer |
| 540 | Next descriptor buffer |
| 550 | Current matrix-compute path |
| 560 | Next-block generation path |
| 570 | Overlap scheduler / lifecycle controller |

### Layout Sketch

```text
Freed External Capacity [510] ------------------------------> KV Cache [520]

Descriptor Buffer A [530] ---> Current Matrix Compute [550]
        ^                                      |
        |                                      v
Overlap Scheduler / Lifecycle Controller [570]
        |                                      ^
        v                                      |
Descriptor Buffer B [540] <--- Next-Block Generation [560]
```

---

## Figure 6: Backward Recompute and Synchronization Truncation

### Description

Shows a training-time backward path in which temporary descriptors are regenerated on chip for local gradient computation, while optimizer-state entry and cross-node synchronization are selectively blocked.

### Reference Numerals

| Number | Element |
|--------|---------|
| 600 | Backward propagation request |
| 610 | Recompute module |
| 620 | Regenerated temporary descriptors |
| 630 | Local gradient computation |
| 640 | Optimizer-state gate |
| 650 | Cross-node synchronization gate |
| 660 | Parameter-subset synchronization |

### Layout Sketch

```text
Backward Request [600] -> Recompute Module [610] -> Temporary Descriptors [620]
                                                       |
                                                       v
                                           Local Gradient Compute [630]
                                                       |
                            +--------------------------+-------------------------+
                            |                                                    |
                            v                                                    v
                  Optimizer-State Gate [640]                         Sync Gate [650]
                                                                                 |
                                                                                 v
                                                                  Parameter Subset Sync [660]
```

---

## Figure 7: Observable Features and Evidence Entry Points

### Description

Shows external tools, observable metrics, and evidence entry points used to verify reduced external-memory traffic, high matrix-unit utilization, and reduced synchronization volume when the claimed execution path is active.

### Reference Numerals

| Number | Element |
|--------|---------|
| 700 | Profiler |
| 710 | Memory counter |
| 720 | Network packet capture tool |
| 730 | External-memory traffic reduction metric |
| 740 | Matrix-unit utilization / stall metric |
| 750 | Synchronization-volume reduction metric |
| 760 | Monitoring module / public interface / logs |

### Layout Sketch

```text
Profiler [700] -----------+
Memory Counter [710] -----+--> Monitoring / Public Interface / Logs [760]
Packet Capture [720] -----+                                 --> External Traffic [730]
                                                              Matrix Utilization / Stall [740]
                                                              Sync Volume [750]
```

---

## General Drafting Notes

1. Keep reference numerals stable across all figures.
2. Use one visual style for external memory, one for local memory, and one for compute units.
3. Figure 2 should be the one figure a reviewer can read first to understand the invention end-to-end.
4. Explicitly mark blocked requests and lifecycle boundaries in Figure 3.
5. Explicitly mark the forbidden dense-materialization path in Figure 4.
6. In Figure 5, explicitly show buffer alternation and overlap between next-block generation and current-block consumption.
7. In Figure 6, visually separate local gradient computation from optimizer-state entry and cross-node synchronization paths.
8. Avoid oversized "X" overlays; use concise prohibition text instead.
9. If any label becomes crowded, widen the box or split the label before allowing overlaps.
