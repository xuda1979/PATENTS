# 专利证据附录模板
# MWG-EW

---

## 一、项目基本信息

- 项目名称：
- 版本号：
- 生成日期：
- 负责人：
- 关联模型：
- 关联硬件：
- 关联 kernel / commit：

---

## 二、测试环境

| 项目 | 内容 |
|------|------|
| 硬件型号 | |
| 显存容量 | |
| 驱动版本 | |
| CUDA/ROCm/Triton 版本 | |
| 框架版本 | |
| 精度类型 | |
| batch size | |
| sequence length | |

---

## 三、基线与方案定义

### 1. 稠密基线

- 模型：
- 目标层：
- 权重形式：
- 执行路径：

### 2. MWG-EW 方案

- 元生成器形式：
- descriptor 形式：
- rank：
- 是否单内核：
- 是否 grouped-token reuse：

---

## 四、内存访问结果

| 指标 | 稠密基线 | MWG-EW | 改善倍数 |
|------|----------|--------|----------|
| HBM bytes read | | | |
| HBM bytes written | | | |
| 每 block HBM read | | | |
| 每 block HBM write | | | |
| max resident memory | | | |

### 说明

- 是否存在 descriptor 写回：
- 若无写回，对应 profiler 证据编号：
- 若存在写回，说明是否为 debug 模式：

---

## 五、正确性结果

| 指标 | 数值 |
|------|------|
| max abs error | |
| mean relative error | |
| repeated run variance | |

### 说明

- reference path：
- fused path：
- 判定结论：

---

## 六、性能结果

| 指标 | 稠密基线 | MWG-EW | 改善 |
|------|----------|--------|------|
| tokens/s | | | |
| token latency | | | |
| batch latency | | | |
| tensor core utilization | | | |
| occupancy | | | |

---

## 七、训练/蒸馏恢复结果

| 指标 | 稠密基线 | 替换后初始 | 恢复后 |
|------|----------|------------|--------|
| validation loss | | | |
| perplexity | | | |
| teacher-student KL | | | |
| hidden-state cosine similarity | | | |

---

## 八、消融结果

### 1. rank sweep

| rank | HBM read | throughput | ppl / loss |
|------|----------|------------|------------|
| 32 | | | |
| 64 | | | |
| 128 | | | |
| 256 | | | |

### 2. layer replacement sweep

| replacement ratio | HBM read | throughput | ppl / loss |
|-------------------|----------|------------|------------|
| 25% | | | |
| 50% | | | |
| 100% | | | |

### 3. descriptor type sweep

| descriptor type | HBM read | throughput | ppl / loss |
|-----------------|----------|------------|------------|
| direct factor | | | |
| basis bank | | | |

---

## 九、结论摘要

建议用 5-10 句话总结：

1. descriptor 是否未回写；
2. HBM 流量下降多少；
3. 吞吐/时延改善多少；
4. 精度恢复到什么程度；
5. 这些结果如何支持专利技术效果。

---

## 十、附件目录

- profiler 截图：
- 原始 csv：
- 训练曲线：
- kernel trace：
- 配置文件：
