# Patent Drawing Specifications
# 专利附图规格说明

> **Purpose**: This document provides detailed specifications for creating formal patent drawings.
> **用途**: 本文档为专业制图人员提供正式专利附图的详细规格说明。

---

## Drawing Requirements / 附图要求

- **Format**: Black and white line drawings (no grayscale, no color)
- **Resolution**: Minimum 300 DPI
- **Paper Size**: A4 (210mm × 297mm) or US Letter (8.5" × 11")
- **Margins**: At least 25mm on all sides
- **Line Width**: 0.25mm minimum for all lines
- **Reference Numerals**: Arabic numerals, consistent across all figures
- **Font**: Arial or similar sans-serif, minimum 8pt

---

## Figure 1: Overall System Architecture Diagram
## 图1：系统整体架构图

### Description / 描述
Shows the complete threshold Falcon signature system architecture with source chain, signature system, and target chain interaction.

### Reference Numerals / 附图标记

| Number | Element (EN) | 元素 (CN) |
|--------|--------------|-----------|
| 100 | System Overview | 系统总览 |
| 110 | Source Blockchain | 源链 |
| 111 | Cross-chain Request Module | 跨链请求模块 |
| 112 | Message Hash Unit | 消息哈希单元 |
| 120 | Threshold Signature System | 门限签名系统 |
| 121 | Node P₁ | 节点 P₁ |
| 122 | Node P₂ | 节点 P₂ |
| 123 | Node P₃ | 节点 P₃ |
| 12n | Node Pₙ | 节点 Pₙ |
| 130 | Private Key Share Storage | 私钥分片存储 |
| 131 | Share [f]₁ | 分片 [f]₁ |
| 132 | Share [f]₂ | 分片 [f]₂ |
| 133 | Share [f]₃ | 分片 [f]₃ |
| 13n | Share [f]ₙ | 分片 [f]ₙ |
| 140 | MPC Coordination Module | MPC协调模块 |
| 141 | Arithmetic-Shared NTT Unit | 算术共享NTT单元 |
| 142 | Collaborative Rejection Sampling Unit | 协同纠偏采样单元 |
| 143 | Signature Aggregation Unit | 签名聚合单元 |
| 150 | Output Signature (r, s) | 输出签名 (r, s) |
| 160 | Target Blockchain | 目标链 |
| 161 | Falcon Verification Contract | Falcon验证合约 |
| 162 | Execution Module | 执行模块 |
| 170 | Communication Channel (Secure) | 安全通信信道 |
| 180 | Broadcast Channel | 广播信道 |

### Layout Specification / 布局规格

```
+----------------------------------------------------------+
|  [Height: 200mm, Width: 160mm]                           |
|                                                          |
|  TOP SECTION (30mm): Source Blockchain (110)             |
|  +--------------------------------------------------+    |
|  |  Source Blockchain  [110]                        |    |
|  |  +------------------+    +-------------------+   |    |
|  |  | Cross-chain      |    | Message Hash     |   |    |
|  |  | Request [111]    |--->| Unit [112]       |   |    |
|  |  +------------------+    +-------------------+   |    |
|  +--------------------------------------------------+    |
|                          |                               |
|                          v [Arrow: 170]                  |
|                                                          |
|  MIDDLE SECTION (100mm): Threshold System (120)          |
|  +--------------------------------------------------+    |
|  |  Quantum-Secure Threshold Signature System [120] |    |
|  |                                                  |    |
|  |  +------+ +------+ +------+     +------+        |    |
|  |  |Node  | |Node  | |Node  | ... |Node  |        |    |
|  |  |P₁    | |P₂    | |P₃    |     |Pₙ    |        |    |
|  |  |[121] | |[122] | |[123] |     |[12n] |        |    |
|  |  |      | |      | |      |     |      |        |    |
|  |  |[f]₁  | |[f]₂  | |[f]₃  |     |[f]ₙ  |        |    |
|  |  |[131] | |[132] | |[133] |     |[13n] |        |    |
|  |  +---+--+ +---+--+ +---+--+     +---+--+        |    |
|  |      |       |       |             |            |    |
|  |      +-------+-------+-------------+            |    |
|  |              |                                  |    |
|  |              v                                  |    |
|  |  +------------------------------------------+  |    |
|  |  |  MPC Coordination Module [140]           |  |    |
|  |  |  +------------+ +-------------+ +------+ |  |    |
|  |  |  |Arith-NTT   | |Collab Reject| |Sig   | |  |    |
|  |  |  |Unit [141]  | |Sample [142] | |Agg   | |  |    |
|  |  |  +------------+ +-------------+ |[143] | |  |    |
|  |  +------------------------------------------+  |    |
|  |              |                                  |    |
|  |              v                                  |    |
|  |  +------------------------------------------+  |    |
|  |  |  Falcon Signature (r, s) [150]           |  |    |
|  |  +------------------------------------------+  |    |
|  +--------------------------------------------------+    |
|                          |                               |
|                          v [Arrow: 180]                  |
|                                                          |
|  BOTTOM SECTION (30mm): Target Blockchain (160)          |
|  +--------------------------------------------------+    |
|  |  Target Blockchain [160]                         |    |
|  |  +------------------+    +-------------------+   |    |
|  |  | Falcon Verify    |    | Execute Cross-   |   |    |
|  |  | Contract [161]   |--->| chain [162]      |   |    |
|  |  +------------------+    +-------------------+   |    |
|  +--------------------------------------------------+    |
|                                                          |
+----------------------------------------------------------+
```

### Arrow Specifications / 箭头规格
- All arrows: 0.5mm line width, solid arrowhead
- Vertical data flow arrows: Downward direction
- Horizontal process arrows: Left to right
- Dashed lines for internal communication within modules

---

## Figure 2: Collaborative Rejection Sampling Flowchart
## 图2：协同纠偏采样流程图

### Description / 描述
Flowchart showing the three-phase protocol: Commitment, Pre-check Verification, and Conditional Reveal.

### Reference Numerals / 附图标记

| Number | Element (EN) | 元素 (CN) |
|--------|--------------|-----------|
| 200 | Protocol Start | 协议开始 |
| 210 | Phase 1: Local Sampling | 阶段1：本地采样 |
| 211 | Generate Local Sample sᵢ | 生成本地采样值 sᵢ |
| 212 | Generate Random Mask mᵢ | 生成随机掩码 mᵢ |
| 220 | Phase 2: Commitment | 阶段2：承诺 |
| 221 | Compute Commitment Cᵢ = H(mᵢ ‖ sᵢ) | 计算承诺值 Cᵢ |
| 222 | Broadcast Commitment | 广播承诺 |
| 223 | Collect All Commitments | 收集所有承诺 |
| 230 | Phase 3: Pre-check | 阶段3：预检 |
| 231 | Exchange Masked Statistics | 交换掩码统计量 |
| 232 | Secure Aggregation | 安全聚合 |
| 233 | Compute Global Norm ‖s‖² | 计算全局范数 |
| 240 | Decision Diamond: Global Check Pass? | 决策菱形：全局检验通过？ |
| 250 | Phase 4: Reveal (Yes Branch) | 阶段4：揭示（是分支） |
| 251 | Reveal Sample Components | 揭示采样分量 |
| 252 | Aggregate Signature | 聚合签名 |
| 260 | Retry Path (No Branch) | 重试路径（否分支） |
| 261 | Discard Current Samples | 丢弃当前采样 |
| 262 | Increment Retry Counter | 增加重试计数器 |
| 270 | Output: Valid Signature (r, s) | 输出：有效签名 |
| 280 | Protocol End | 协议结束 |
| 290 | Statistics Box: ~35% rejection, ~1.5 avg retries | 统计框：~35%拒绝率，平均~1.5次重试 |

### Layout Specification / 布局规格

```
+----------------------------------------------------------+
|  [Height: 250mm, Width: 160mm]                           |
|                                                          |
|           ( START [200] )                                |
|                 |                                        |
|                 v                                        |
|  +------------------------------------------+            |
|  | PHASE 1: LOCAL SAMPLING [210]            |            |
|  | +------------------------------------+   |            |
|  | | Generate local sample sᵢ [211]     |   |            |
|  | +------------------------------------+   |            |
|  |                 |                        |            |
|  |                 v                        |            |
|  | +------------------------------------+   |            |
|  | | Generate random mask mᵢ [212]      |   |            |
|  | +------------------------------------+   |            |
|  +------------------------------------------+            |
|                 |                                        |
|                 v                                        |
|  +------------------------------------------+            |
|  | PHASE 2: COMMITMENT [220]                |            |
|  | +------------------------------------+   |            |
|  | | Compute Cᵢ = H(mᵢ ‖ sᵢ) [221]      |   |            |
|  | +------------------------------------+   |            |
|  |                 |                        |            |
|  |                 v                        |            |
|  | +------------------------------------+   |            |
|  | | Broadcast commitment [222]         |   |            |
|  | +------------------------------------+   |            |
|  |                 |                        |            |
|  |                 v                        |            |
|  | +------------------------------------+   |            |
|  | | Collect all commitments [223]      |   |            |
|  | +------------------------------------+   |            |
|  +------------------------------------------+            |
|                 |                                        |
|                 v                                        |
|  +------------------------------------------+            |
|  | PHASE 3: PRE-CHECK [230]                 |            |
|  | +------------------------------------+   |            |
|  | | Exchange masked statistics [231]   |   |            |
|  | +------------------------------------+   |            |
|  |                 |                        |            |
|  |                 v                        |            |
|  | +------------------------------------+   |            |
|  | | Secure aggregation [232]           |   |            |
|  | +------------------------------------+   |            |
|  |                 |                        |            |
|  |                 v                        |            |
|  | +------------------------------------+   |            |
|  | | Compute global norm [233]          |   |            |
|  | +------------------------------------+   |            |
|  +------------------------------------------+            |
|                 |                                        |
|                 v                                        |
|           /          \                                   |
|          /   Global   \                                  |
|         <   Check      >  [240]                          |
|          \   Pass?    /                                  |
|           \          /                                   |
|        Yes |      | No                                   |
|            v      v                                      |
|  +----------+    +---------------------------+           |
|  | PHASE 4: |    | RETRY PATH [260]          |           |
|  | REVEAL   |    | +---------------------+   |           |
|  | [250]    |    | |Discard samples [261]|   |           |
|  +----------+    | +---------------------+   |           |
|       |          |           |               |           |
|       v          | +---------------------+   |           |
|  +----------+    | |Incr. counter [262]  |   |           |
|  | Reveal   |    | +---------------------+   |           |
|  | samples  |    +------------+--------------+           |
|  | [251]    |                 |                          |
|  +----------+                 |                          |
|       |                       |                          |
|       v                       |                          |
|  +----------+                 |                          |
|  |Aggregate |                 |                          |
|  |signature |      [Loop back to Phase 1]                |
|  | [252]    |<----------------+                          |
|  +----------+                                            |
|       |                                                  |
|       v                                                  |
|  +------------------------------------------+            |
|  | OUTPUT: Valid Signature (r, s) [270]     |            |
|  +------------------------------------------+            |
|                 |                                        |
|                 v                                        |
|           ( END [280] )                                  |
|                                                          |
|  +------------------------------------------+            |
|  | Statistics [290]:                        |            |
|  | • Rejection probability: ~35%            |            |
|  | • Average retry count: ~1.5              |            |
|  +------------------------------------------+            |
|                                                          |
+----------------------------------------------------------+
```

### Flowchart Symbol Standards / 流程图符号标准
- **Oval/Ellipse**: Start/End terminals (200, 280)
- **Rectangle**: Process steps (211, 212, 221-223, 231-233, 251, 252, 261, 262)
- **Diamond**: Decision point (240)
- **Rectangle with double border**: Phase groupings (210, 220, 230, 250)
- **Arrows**: 0.5mm width, solid arrowhead

---

## Figure 3: Dynamic Node Management Diagram
## 图3：动态节点管理示意图

### Description / 描述
Three sub-diagrams showing: (A) Node Addition, (B) Node Revocation, (C) Offline Node Recovery

### Reference Numerals / 附图标记

| Number | Element (EN) | 元素 (CN) |
|--------|--------------|-----------|
| 300 | Initial State | 初始状态 |
| 301-307 | Nodes P₁ through P₇ | 节点 P₁ 至 P₇ |
| 310 | Scenario A: Node Addition | 场景A：节点加入 |
| 311 | New Node P₈ | 新节点 P₈ |
| 312 | MPC Share Generation Process | MPC分片生成过程 |
| 313 | New Shares [f']ᵢ | 新分片 [f']ᵢ |
| 314 | Unchanged Public Key pk | 不变的公钥 pk |
| 320 | Scenario B: Node Revocation | 场景B：节点撤销 |
| 321 | Revoked Node (P₃) with X mark | 被撤销节点（P₃）标记X |
| 322 | Proactive Secret Sharing Process | 主动秘密共享过程 |
| 323 | Updated Shares for Remaining Nodes | 剩余节点的更新分片 |
| 324 | Invalidated Share (strikethrough) | 失效分片（删除线） |
| 330 | Scenario C: Offline Recovery | 场景C：离线恢复 |
| 331 | Offline Node (P₅) with ? mark | 离线节点（P₅）标记? |
| 332 | Threshold Reconstruction Process | 门限重构过程 |
| 333 | Reconstructed Share [f]₅ | 重构的分片 [f]₅ |
| 334 | System Continues Operating | 系统继续运行 |
| 340 | Threshold Parameters (t, n) | 门限参数 (t, n) |
| 341 | Initial: (5, 7) | 初始：(5, 7) |
| 342 | After Addition: (5, 8) | 加入后：(5, 8) |
| 343 | After Revocation: (5, 6) | 撤销后：(5, 6) |

### Layout Specification / 布局规格

```
+----------------------------------------------------------+
|  [Height: 220mm, Width: 160mm]                           |
|                                                          |
|  INITIAL STATE [300]                                     |
|  +------------------------------------------------------+|
|  | Threshold: (5, 7) [341]                              ||
|  | +----+ +----+ +----+ +----+ +----+ +----+ +----+     ||
|  | | P₁ | | P₂ | | P₃ | | P₄ | | P₅ | | P₆ | | P₇ |     ||
|  | |301 | |302 | |303 | |304 | |305 | |306 | |307 |     ||
|  | +----+ +----+ +----+ +----+ +----+ +----+ +----+     ||
|  | |[f]₁| |[f]₂| |[f]₃| |[f]₄| |[f]₅| |[f]₆| |[f]₇|     ||
|  | +----+ +----+ +----+ +----+ +----+ +----+ +----+     ||
|  +------------------------------------------------------+|
|                                                          |
|  ═══════════════════════════════════════════════════════ |
|                                                          |
|  SCENARIO A: NODE ADDITION [310]                         |
|  +------------------------------------------------------+|
|  | New Threshold: (5, 8) [342]                          ||
|  |                                                      ||
|  | +----+ +----+ +----+ +----+ +----+ +----+ +----+     ||
|  | | P₁ | | P₂ | | P₃ | | P₄ | | P₅ | | P₆ | | P₇ |     ||
|  | +--+-+ +--+-+ +--+-+ +--+-+ +--+-+ +--+-+ +--+-+     ||
|  |    |     |     |     |     |     |     |             ||
|  |    +-----+-----+-----+-----+-----+-----+             ||
|  |                      |                               ||
|  |                      v                               ||
|  |            +------------------+      +------+        ||
|  |            | MPC Share        |      | P₈   |        ||
|  |            | Generation [312] |<---->| [311]|        ||
|  |            +------------------+      +------+        ||
|  |                                                      ||
|  | Result: All nodes hold new shares [f']ᵢ [313]        ||
|  | Public key pk remains unchanged [314]                ||
|  +------------------------------------------------------+|
|                                                          |
|  ═══════════════════════════════════════════════════════ |
|                                                          |
|  SCENARIO B: NODE REVOCATION [320]                       |
|  +------------------------------------------------------+|
|  | New Threshold: (5, 6) [343]                          ||
|  |                                                      ||
|  | +----+ +----+ +----+ +----+ +----+ +----+ +----+     ||
|  | | P₁ | | P₂ | | ✗  | | P₄ | | P₅ | | P₆ | | P₇ |     ||
|  | +----+ +----+ |P₃  | +----+ +----+ +----+ +----+     ||
|  |               |[321]|                                ||
|  |               +--+--+                                ||
|  |                  |                                   ||
|  |         [Share invalidated - strikethrough]          ||
|  |                                                      ||
|  |    Remaining nodes: Proactive Secret Sharing [322]   ||
|  |    +----+ +----+      +----+ +----+ +----+ +----+    ||
|  |    |[f']₁| |[f']₂|    |[f']₄| |[f']₅| |[f']₆| |[f']₇||
|  |    +----+ +----+      +----+ +----+ +----+ +----+    ||
|  |    [323] Updated shares                              ||
|  +------------------------------------------------------+|
|                                                          |
|  ═══════════════════════════════════════════════════════ |
|                                                          |
|  SCENARIO C: OFFLINE NODE RECOVERY [330]                 |
|  +------------------------------------------------------+|
|  | Threshold: (5, 7) [341] - Maintained                 ||
|  |                                                      ||
|  | +----+ +----+ +----+ +----+ +----+ +----+ +----+     ||
|  | | P₁ | | P₂ | | P₃ | | P₄ | | ?  | | P₆ | | P₇ |     ||
|  | +----+ +----+ +----+ +----+ |P₅  | +----+ +----+     ||
|  |                             |[331]|                  ||
|  |                             +--+--+                  ||
|  |                                |                     ||
|  |    Active nodes perform threshold reconstruction     ||
|  |    +----+ +----+ +----+ +----+      +----+ +----+    ||
|  |    | P₁ | | P₂ | | P₃ | | P₄ |      | P₆ | | P₇ |    ||
|  |    +--+-+ +--+-+ +--+-+ +--+-+      +--+-+ +--+-+    ||
|  |       |     |     |     |             |     |        ||
|  |       +-----+-----+-----+-------------+-----+        ||
|  |                      |                               ||
|  |                      v                               ||
|  |            +----------------------+                  ||
|  |            | Threshold            |                  ||
|  |            | Reconstruction [332] |                  ||
|  |            +----------+-----------+                  ||
|  |                       |                              ||
|  |                       v                              ||
|  |            +----------------------+                  ||
|  |            | Reconstructed [f]₅   |                  ||
|  |            | [333]                |                  ||
|  |            +----------------------+                  ||
|  |                                                      ||
|  | Result: P₅ recovers, system continues [334]          ||
|  +------------------------------------------------------+|
|                                                          |
+----------------------------------------------------------+
```

### Visual Element Standards / 视觉元素标准
- **Active Node**: Solid border rectangle
- **Revoked Node**: Rectangle with X overlay
- **Offline Node**: Rectangle with ? overlay
- **New Node**: Dashed border rectangle (before integration)
- **Process Box**: Rounded rectangle with gray fill (10%)
- **Arrows**: Indicate data/share flow direction
- **Separator Lines**: Double line (═) between scenarios

---

## Production Instructions / 制作说明

### For Professional Illustrators / 给专业制图人员

1. **Software Recommendations / 软件建议**:
   - Adobe Illustrator (preferred)
   - Microsoft Visio
   - Draw.io (free alternative)
   - AutoCAD LT

2. **File Deliverables / 交付文件**:
   - Source file (AI, VSDX, or DWG)
   - PDF export (vector, not rasterized)
   - PNG export at 300 DPI
   - TIFF export at 300 DPI (for USPTO)

3. **Color Mode / 颜色模式**:
   - Grayscale only
   - No fills darker than 20% gray
   - All text and lines must be pure black (#000000)

4. **Text Handling / 文字处理**:
   - Convert all text to outlines/curves for final submission
   - Maintain editable version separately

5. **Reference Numeral Placement / 标记放置**:
   - Place numerals adjacent to elements, not overlapping
   - Use leader lines (thin, 0.25mm) when necessary
   - Consistent numeral size throughout (10pt minimum)

---

## Estimated Production Time / 预计制作时间

| Figure | Complexity | Estimated Hours |
|--------|------------|-----------------|
| Figure 1 | Medium | 4-6 hours |
| Figure 2 | Medium | 3-4 hours |
| Figure 3 | High | 5-7 hours |
| **Total** | | **12-17 hours** |

---

## Approval Checklist / 审批清单

- [ ] Figure 1 draft reviewed
- [ ] Figure 2 draft reviewed
- [ ] Figure 3 draft reviewed
- [ ] All reference numerals match specification text
- [ ] Resolution meets patent office requirements
- [ ] Chinese and English versions consistent
- [ ] Final files exported in required formats

---

*Document Version: 1.0*
*Created: December 2025*
*Last Updated: December 2025*
