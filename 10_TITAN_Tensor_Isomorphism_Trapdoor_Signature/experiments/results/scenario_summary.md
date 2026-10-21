# Scenario Summary

Policy-side scenario experiment executed locally with Python standard library; signature latency/correctness metrics are imported from the repository's existing real benchmark summary.json and mapped to the corresponding deployment scenario.

## 量子计算网络节点准入
- 部署入口：节点准入控制器
- 绑定参数点：titan-n8-r16
- 有效载荷长度：min=292 B, max=295 B, mean=293.5 B
- 有效载荷策略放行：50/50 (100.0%)
- 字段级篡改策略拒绝：150/150 (100.0%)
- 导入的原始签名验证成功：50/50 (100.0%)
- 导入的篡改消息验签拒绝：50/50 (100.0%)
- 验签延迟：mean=1.808 ms, p95=2.674 ms, throughput=553.097 sig/s

## AI加速设备固件升级
- 部署入口：可信启动链/升级代理
- 绑定参数点：titan-n10-r32
- 有效载荷长度：min=232 B, max=232 B, mean=232 B
- 有效载荷策略放行：50/50 (100.0%)
- 字段级篡改策略拒绝：150/150 (100.0%)
- 导入的原始签名验证成功：50/50 (100.0%)
- 导入的篡改消息验签拒绝：50/50 (100.0%)
- 验签延迟：mean=4.136 ms, p95=5.343 ms, throughput=241.779 sig/s

## 模型发布完整性校验
- 部署入口：模型仓库发布/下载校验代理
- 绑定参数点：titan-n12-r32
- 有效载荷长度：min=331 B, max=331 B, mean=331 B
- 有效载荷策略放行：50/50 (100.0%)
- 字段级篡改策略拒绝：150/150 (100.0%)
- 导入的原始签名验证成功：50/50 (100.0%)
- 导入的篡改消息验签拒绝：50/50 (100.0%)
- 验签延迟：mean=4.806 ms, p95=6.271 ms, throughput=208.073 sig/s
