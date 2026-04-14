# Patent Drawing Specifications
# Meta-Weight Generation for On-the-Fly Ephemeral Weights (MWG-EW)

---

## Drawing Requirements

These layouts are conceptual drafting guides for formal patent figures.

- Format: black-and-white line drawings
- Resolution: at least 300 DPI
- Reference numerals: Arabic numerals, consistent across figures
- Use a distinct outline for the on-chip local memory region and the external memory region
- Use a blocked or crossed path to show prohibited dense-matrix storage or write-back paths

---

## Figure 1: Dense Stored-Weight Path vs Generated-Descriptor Path

### Description

Compares a conventional inference path that repeatedly fetches stored projection weights from external memory with a claimed path in which a meta-generator creates temporary weight-descriptor tiles that are consumed locally on the accelerator.

### Reference Numerals

| Number | Element |
|--------|---------|
| 100 | Conventional dense path |
| 110 | External memory region |
| 120 | Stored dense projection weights |
| 130 | Matrix-compute units |
| 140 | Weight-fetch bottleneck |
| 150 | Generated-descriptor path |
| 160 | Conditioning module |
| 170 | Meta-generator |
| 180 | Weight-descriptor tiles |
| 190 | On-chip local memory region |
| 195 | Fused execution engine |

### Layout Sketch

```text
+-------------------------------------------------------------------+
| Dense Path [100]                                                  |
| External Memory [110] -> Stored Weights [120] -> Compute [130]    |
|                                |                                  |
|                                v                                  |
|                      Weight-Fetch Bottleneck [140]                |
+-------------------------------------------------------------------+

+-------------------------------------------------------------------+
| Generated Path [150]                                              |
| Conditioning [160] -> Meta-Generator [170] -> Descriptor Tiles    |
|                                         [180] -> Local Memory [190]|
|                                                    -> Fused Exec   |
|                                                       [195]        |
+-------------------------------------------------------------------+
```

---

## Figure 2: Accelerator Architecture and Memory Hierarchy

### Description

Shows an accelerator architecture including matrix-compute units, an on-chip local memory region, an external memory region, a conditioning module, a layer identifier input, a meta-generator, a fused execution engine, and a memory-lifecycle controller.

### Reference Numerals

| Number | Element |
|--------|---------|
| 200 | Overall accelerator system |
| 210 | Activation input |
| 220 | Conditioning module |
| 230 | Layer identifier input |
| 240 | Meta-generator |
| 250 | On-chip local memory region |
| 260 | Fused execution engine |
| 270 | Matrix-compute units |
| 280 | Memory-lifecycle controller |
| 290 | External memory region |
| 295 | Output activation |

### Layout Sketch

```text
Activation [210] ---> Conditioning [220] ----+
                                             |
Layer ID [230] ------------------------------+--> Meta-Generator [240]
                                                    |
                                                    v
                                         On-Chip Local Memory [250]
                                                    |
                                                    v
                                      Fused Execution Engine [260]
                                                    |
                                                    v
                                       Matrix-Compute Units [270]
                                                    |
                                                    v
                                               Output [295]

Memory-Lifecycle Controller [280] controls [250] and [260]
External Memory Region [290] is outside the local-memory boundary
```

---

## Figure 3: Associative Execution Without External Dense-Matrix Storage

### Description

Shows execution of a linear transformation using generated factor tiles in a form including `Y = (XU)V`, while blocking storage of a corresponding full dense matrix in the external memory region.

### Reference Numerals

| Number | Element |
|--------|---------|
| 300 | Input activation X |
| 310 | Generated factor tile U |
| 320 | Generated factor tile V |
| 330 | Intermediate product XU |
| 340 | Output Y |
| 350 | Prohibited full dense matrix path |
| 360 | External memory region |

### Layout Sketch

```text
          [Prohibited]
X [300] -> Full Dense Matrix [350] -> External Memory [360]

          [Claimed]
X [300] -> U [310] -> XU [330] -> V [320] -> Y [340]
```

---

## Figure 4: Tile-Wise Generation, Consumption, and Release

### Description

Shows a tile-wise loop in which each generated weight-descriptor tile is placed in on-chip local memory, consumed for computation, accumulated into a partial output, and released or overwritten before generation of a next tile.

### Reference Numerals

| Number | Element |
|--------|---------|
| 400 | Activation tile |
| 410 | Conditioning tile |
| 420 | Weight-descriptor tile generation |
| 430 | On-chip local memory region |
| 440 | Matrix-compute unit |
| 450 | Partial output tile |
| 460 | Release or overwrite operation |
| 470 | Next descriptor-tile generation boundary |

### Layout Sketch

```text
Activation Tile [400] ------------------------------+
                                                    |
Conditioning Tile [410] -> Descriptor Generation [420]
                                                    |
                                                    v
                                       Local Memory Region [430]
                                                    |
                                                    v
                                     Matrix-Compute Unit [440]
                                                    |
                                                    v
                                        Partial Output [450]
                                                    |
                                                    v
                                  Release / Overwrite [460]
                                                    |
                                                    v
                             Next Tile Generation Boundary [470]
```

---

## Figure 5: Migration From Pretrained Dense Model

### Description

Shows a migration path in which a pretrained dense model is modified by replacing one or more stored dense projections with the claimed meta-generator and fused execution path, followed by continual training or knowledge distillation.

### Reference Numerals

| Number | Element |
|--------|---------|
| 500 | Pretrained dense model |
| 510 | Target projection selection |
| 520 | Replacement with generated-descriptor path |
| 530 | Freeze set |
| 540 | Teacher model |
| 550 | Continual training or distillation |
| 560 | Converted MWG-EW model |

### Layout Sketch

```text
Pretrained Dense Model [500] -> Projection Selection [510] -> Replace Path [520]
                                                          -> Freeze Set [530]
Teacher Model [540] ----------------------------------------------+
                                                                 |
                                                                 v
                                           Continual Training / Distillation [550]
                                                                 |
                                                                 v
                                                    Converted Model [560]
```

---

## Figure 6: Hybrid Scheduler for Generated and Static Weights

### Description

Shows a scheduler that selects generated weight descriptors or stored static weights according to layer, token, batch, latency target, or available bandwidth.

### Reference Numerals

| Number | Element |
|--------|---------|
| 600 | Scheduler |
| 610 | Layer or token state input |
| 620 | Bandwidth or latency input |
| 630 | Generated-descriptor path |
| 640 | Stored static-weight path |
| 650 | Selected execution path |

### Layout Sketch

```text
Layer / Token State [610] ----+
                              |
Bandwidth / Latency [620] ----+--> Scheduler [600]
                                         |
                         +---------------+---------------+
                         |                               |
                         v                               v
              Generated Path [630]            Static-Weight Path [640]
                         \                               /
                          \                             /
                           +---- Selected Path [650] --+
```

---

## General Drafting Notes

1. Keep the on-chip local memory region visually enclosed and distinct from the external memory region.
2. Mark prohibited dense-matrix storage or write-back paths with a blocked symbol or crossed line.
3. In Figure 4, emphasize that release or overwrite occurs before generation of the next descriptor tile.
4. In Figure 6, show the hybrid scheduler as optional so the core invention remains independent of the scheduler embodiment.
