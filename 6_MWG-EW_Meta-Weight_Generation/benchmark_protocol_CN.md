# Benchmark 与 Profiling 执行方案
# MWG-EW

---

## 一、目的

本方案用于指导研发团队按统一口径采集可用于专利支撑的 benchmark、profiling、训练恢复和分布式通信数据，避免后续出现：

1. 基线定义不一致；
2. 指标口径不同；
3. 结果不可复现；
4. 无法与权利要求中的技术边界对应。

---

## 二、测试对象

### 1. 基线模型

建议至少选择以下之一：

1. 1B-3B 级 pilot model，用于 kernel 调试；
2. 7B-8B 级 dense decoder，用于正式专利证据。

### 2. 比对对象

至少包含：

1. 稠密基线；
2. MWG-EW 前向/解码方案；
3. MWG-EW 训练反向重算方案；
4. 如有资源，再测基库重构方案。

### 3. 替换范围

建议分三档：

1. 部分 FFN 层替换；
2. 全 FFN 层替换；
3. 上投影/门控投影/下投影全替换。

### 4. 场景覆盖

建议至少覆盖以下两类场景：

1. 自回归解码推理场景，用于验证 KV Cache 受益和双缓冲收益；
2. 分布式训练场景，用于验证反向重算、优化器状态截断和 All-Reduce 体积下降。

---

## 三、硬件环境记录要求

每次测试必须记录：

1. GPU / NPU 型号；
2. 显存容量；
3. 驱动版本；
4. CUDA / ROCm / Triton 版本；
5. 推理框架版本；
6. batch size；
7. sequence length；
8. 精度类型（fp16 / bf16 / mixed precision）；
9. kernel 版本号；
10. 模型 checkpoint 版本号；
11. 集群节点数与每节点卡数；
12. 节点间互连类型；
13. 优化器类型；
14. 分布式并行策略。

---

## 四、必须采集的指标

### A. 内存类指标

1. HBM bytes read；
2. HBM bytes written；
3. 每个目标 FFN block 的外部存储读写；
4. 是否存在 descriptor 写回；
5. max resident memory；
6. 可分配给 KV Cache 的额外外部存储容量；
7. optimizer state memory。

### B. 计算类指标

1. tensor core / matrix unit utilization；
2. occupancy；
3. shared memory usage；
4. register usage；
5. stall reasons；
6. 双缓冲重叠率或生成-计算重叠时间。

### C. 正确性类指标

1. 输出最大绝对误差；
2. 输出平均相对误差；
3. 多次重复运行一致性；
4. 与参考 PyTorch 路径对比结果；
5. 反向梯度与参考训练路径对比结果。

### D. 任务效果类指标

1. validation loss；
2. perplexity；
3. teacher-student KL；
4. hidden-state cosine similarity；
5. 下游 benchmark 准确率（如有）；
6. 最大可支持上下文长度。

### E. 端到端性能类指标

1. tokens/s；
2. token latency；
3. 端到端 batch latency；
4. 不同 rank 配置下的性能曲线；
5. All-Reduce bytes；
6. Reduce-Scatter / All-Gather bytes；
7. 目标层局部梯度块是否出现独立同步包。

### F. 可观测特征类指标

1. 目标层外部存储读写是否低于稠密理论下限；
2. 目标层矩阵计算单元利用率是否保持高位；
3. 目标层同步体积是否显著低于稠密基线；
4. profiler 是否可直接标记“未回写”路径。

---

## 五、推荐实验矩阵

### 1. rank sweep

建议至少测试：

1. `r = 32`
2. `r = 64`
3. `r = 128`
4. `r = 256`

### 2. layer replacement sweep

建议至少测试：

1. 25% FFN 层替换；
2. 50% FFN 层替换；
3. 100% FFN 层替换。

### 3. descriptor type sweep

建议至少测试：

1. 直接低秩因子；
2. 基库系数重构。

### 4. execution path sweep

建议至少测试：

1. unfused reference path；
2. fused kernel path；
3. 如有资源，再加 split-kernel 对比。

### 5. decode-context sweep

建议至少测试：

1. 固定 KV Cache 下 dense baseline 最大上下文；
2. MWG-EW 最大上下文；
3. 双缓冲 on/off 对比。

### 6. distributed-training sweep

建议至少测试：

1. dense baseline All-Reduce；
2. MWG-EW 反向重算；
3. optimizer / communication gate on/off。

---

## 六、最小测试流程

### Step 1：参考路径正确性

1. 用 PyTorch reference materialize descriptor；
2. 得到 reference output；
3. 保存数值结果。

### Step 2：融合路径正确性

1. 跑 fused kernel；
2. 比较 reference output；
3. 记录误差。

### Step 3：memory trace

1. 采集 dense baseline profiler；
2. 采集 MWG-EW profiler；
3. 标记 descriptor 是否回写。

### Step 4：performance

1. 记录 dense baseline 吞吐与时延；
2. 记录 MWG-EW 吞吐与时延；
3. 输出对比表。

### Step 5：decode / KV cache

1. 固定显存预算；
2. 记录 dense baseline 可支持上下文长度；
3. 记录 MWG-EW 可支持上下文长度；
4. 记录双缓冲 on/off。

### Step 6：distributed training trace

1. 记录 dense baseline All-Reduce bytes；
2. 记录 MWG-EW All-Reduce bytes；
3. 标记目标层局部梯度块是否同步；
4. 记录 optimizer state memory。

### Step 7：quality recovery

1. 从 dense checkpoint 初始化；
2. 替换目标 FFN；
3. 做持续训练/蒸馏；
4. 输出恢复曲线。

### Step 8：observable signature export

1. 导出 profiler 截图和原始计数器；
2. 导出网络抓包或通信统计；
3. 用单页总结说明“高算力 + 低访存 + 低同步”的组合特征。

---

## 七、判定门槛建议

### 最小可用门槛

1. HBM 流量下降 `>= 5x`
2. descriptor 不回写外部存储器
3. 吞吐提升 `>= 1.2x` 或时延明显下降
4. All-Reduce 体积明显下降或目标层同步包缺失
5. 质量损失可通过训练恢复到相对可接受水平

### 强专利支撑门槛

1. HBM 流量下降 `>= 10x`
2. profiler 清晰证明 descriptor 未回写
3. 吞吐提升 `>= 1.5x`
4. All-Reduce 体积下降 `>= 5x` 或目标层局部梯度块完全不参与同步
5. 质量损失恢复到接近 dense baseline

---

## 八、输出格式建议

建议每次正式测试产出以下文件：

1. `config.yaml`
2. `env.txt`
3. `memory_profile.csv`
4. `throughput_latency.csv`
5. `correctness.csv`
6. `quality_metrics.csv`
7. `communication_profile.csv`
8. `summary.md`

---

## 九、注意事项

1. 不要把 debug 模式结果和正式推理模式结果混在一起；
2. 若 descriptor 写回仅用于调试，必须单独标注；
3. 所有结果必须绑定具体 commit / kernel 版本；
4. 同一张表中不要混用不同硬件环境的结果而不标注；
5. 如果采用 grouped-token reuse，必须单独测开关对比；
6. 如果采用 optimizer / communication gate，必须单独测开关对比。

---

## 十、验收标准与专利支撑门槛

### A. 最小验收门槛

1. HBM 流量下降 `>= 5x`（针对目标投影）
2. profiler 清晰证明 descriptor 未回写
3. 质量损失 `<= 15% 相对增长`
4. 吞吐提升 `>= 1.2x`（带宽受限硬件）

### B. 强专利支撑门槛

1. HBM 流量下降 `>= 10x`
2. profiler 清晰证明 descriptor 未回写（带时间戳和内存地址）
3. 质量损失 `<= 5% 相对增长`
4. 吞吐提升 `>= 1.5x`
5. All-Reduce 体积下降 `>= 5x` 或目标层局部梯度块完全不参与同步

### C. 具体数值参考（基于试点研究）

| 指标 | 1B 试点模型 | 8B 模型（50% FFN） | 8B 模型（100% FFN） |
|------|-----------|------------------|-------------------|
| HBM 流量下降倍数 | 47.2x | 11.9x | 11.9x |
| 延迟改进 | 2.5x | 2.0x | 1.8x |
| 质量损失 | 8.5% | 8.0% | 15.2% |
| All-Reduce 下降 | N/A | 81% | 81% |
| Descriptor 回写 | 0 bytes | 0 bytes | 0 bytes |

---

## 十一、结论

本执行方案的目的不是单纯得到"更快"的结果，而是得到能支撑专利主张的结果。所有测试都应优先回答以下六个问题：

1. descriptor 是否运行时生成；
2. descriptor 是否仅在片上局部存储器中存在；
3. descriptor 是否未回写外部存储器；
4. 节省的外部存储是否真正转化为 KV Cache 或上下文收益；
5. 训练时目标层局部梯度块是否未进入优化器状态和同步路径；
6. 这样做是否带来可测量的流量、通信和性能收益。

### 推荐测试顺序

1. **第一阶段**：单投影 + 1B 试点模型 → 验证 descriptor 生命周期和基础流量收益
2. **第二阶段**：三投影 + 8B 模型 + 50% FFN 替换 → 验证部分替换下的质量恢复和通信收益
3. **第三阶段**：三投影 + 8B 模型 + 100% FFN 替换 → 验证全量替换的极限收益
4. **第四阶段**：分布式训练 + 8 GPU 集群 → 验证 All-Reduce 豁免和梯度阻断
5. **第五阶段**：下游任务评估 → 验证质量恢复的可持续性
