# 递交前检查清单
# MWG-EW

---

## 当前状态

- [x] 技术方案、权利要求、交底书、检索报告和支撑文件已完成本轮收口
- [x] LaTeX 文档已同步并完成编译
- [ ] 当前仍待补的最小现实信息已补齐

当前最小阻塞项请优先查看：

`[minimal_pending_info_CN.md](/C:/Users/Lenovo/patents/6_MWG-EW_Meta-Weight_Generation/minimal_pending_info_CN.md)`

---

## 一、主体信息

- [x] 发明人姓名已确认
- [x] 发明人排序已确认（当前包内仅记录发明人为许达）
- [ ] 申请主体已确认
- [x] 联系人及邮箱已确认

---

## 二、时间与公开状态

- [ ] 最早技术完成时间已确认
- [ ] 是否已有论文/预印本已确认
- [ ] 是否已有代码仓库公开已确认
- [ ] 是否已有客户演示、路演或技术分享已确认
- [ ] 是否需要优先权已确认

---

## 三、核心申请文件

- [x] `[claims_CN_final.md](/C:/Users/Lenovo/patents/6_MWG-EW_Meta-Weight_Generation/claims_CN_final.md)` 已确认
- [x] `[patent_spec_CN_final.md](/C:/Users/Lenovo/patents/6_MWG-EW_Meta-Weight_Generation/patent_spec_CN_final.md)` 已确认
- [x] `[abstract_CN_final.md](/C:/Users/Lenovo/patents/6_MWG-EW_Meta-Weight_Generation/abstract_CN_final.md)` 已确认
- [x] 主案已同时覆盖前向执行、解码场景和训练场景
- [x] 主权项已避免使用平台专有术语

---

## 四、代理支持文件

- [x] `[一种面向存储带宽受限神经网络执行的临时权重描述子生成、消费与生命周期控制系统及方法-交底书.md](/C:/Users/Lenovo/patents/6_MWG-EW_Meta-Weight_Generation/一种面向存储带宽受限神经网络执行的临时权重描述子生成、消费与生命周期控制系统及方法-交底书.md)` 已准备
- [x] `[claim_support_map_CN_final.md](/C:/Users/Lenovo/patents/6_MWG-EW_Meta-Weight_Generation/claim_support_map_CN_final.md)` 已准备
- [x] `[一种面向存储带宽受限神经网络执行的临时权重描述子生成、消费与生命周期控制系统及方法-检索报告.md](/C:/Users/Lenovo/patents/6_MWG-EW_Meta-Weight_Generation/一种面向存储带宽受限神经网络执行的临时权重描述子生成、消费与生命周期控制系统及方法-检索报告.md)` 已准备
- [x] `[prosecution_playbook_CN.md](/C:/Users/Lenovo/patents/6_MWG-EW_Meta-Weight_Generation/prosecution_playbook_CN.md)` 已准备
- [x] `[claims_CN_backup.md](/C:/Users/Lenovo/patents/6_MWG-EW_Meta-Weight_Generation/claims_CN_backup.md)` 已准备

---

## 五、附图与实施例

- [x] 附图结构已确认
- [ ] 正式黑白专利附图已绘制或已安排绘制
- [x] 说明书中的图号与附图一致
- [x] 说明书中的模块名称与权利要求一致

---

## 六、技术效果证据

- [ ] 是否已有 profiler 证明不回写 HBM/DRAM
- [ ] 是否已有与稠密基线相比的外部存储流量对比
- [ ] 是否已有数值一致性验证
- [ ] 是否已有 KV Cache / 上下文长度受益证据
- [ ] 是否已有训练反向重算证据
- [ ] 是否已有 All-Reduce 或 optimizer state 对比证据
- [ ] 是否已有蒸馏/继续训练后的精度恢复曲线
- [ ] 是否已有时延或吞吐收益数据

---

## 七、申请策略

- [ ] 是否先中国申请
- [ ] 是否同步准备 PCT
- [ ] 是否考虑美国并行
- [ ] 是否考虑后续分案方向
- [ ] 是否在拿到受理通知书前暂停论文/代码公开

建议候选分案方向：

- [ ] 基库系数重构
- [ ] 分组 token 复用
- [ ] 自适应秩调度
- [ ] 动态/静态混合切换
- [ ] 解码 KV Cache / 双缓冲
- [ ] 训练反向重算 / 通信门控

---

## 八、正式发代理人前

- [x] 已附发送说明 `[counsel_cover_note_CN.md](/C:/Users/Lenovo/patents/6_MWG-EW_Meta-Weight_Generation/counsel_cover_note_CN.md)`
- [x] 已准备邮件草稿 `[agent_email_draft_CN.md](/C:/Users/Lenovo/patents/6_MWG-EW_Meta-Weight_Generation/agent_email_draft_CN.md)`
- [x] 已核对发包顺序 `[application_package_index.md](/C:/Users/Lenovo/patents/6_MWG-EW_Meta-Weight_Generation/application_package_index.md)`
