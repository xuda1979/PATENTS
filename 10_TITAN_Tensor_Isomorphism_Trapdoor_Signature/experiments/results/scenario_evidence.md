# Scenario-Coupled Evidence

Policy experiment executed locally with Python standard library. Signature metrics are imported from the repository's existing real benchmark summary.json.

## 量子计算网络节点准入
- Mapped TITAN point: titan-n8-r16
- Structured payload bytes: min=292, max=295, mean=293.5
- Policy experiment: valid accept 38/50, invalid reject 50/50 (reason=domain_mismatch)
- Signature experiment: verify 50/50, tampered message reject 50/50, tampered signature reject 50/50
- Verify latency: mean=1.808 ms, p95=2.674 ms, throughput=553.097 sig/s

## AI加速设备固件升级
- Mapped TITAN point: titan-n10-r32
- Structured payload bytes: min=232, max=232, mean=232
- Policy experiment: valid accept 50/50, invalid reject 50/50 (reason=rollback_counter_too_small)
- Signature experiment: verify 50/50, tampered message reject 50/50, tampered signature reject 50/50
- Verify latency: mean=4.136 ms, p95=5.343 ms, throughput=241.779 sig/s

## 模型发布完整性校验
- Mapped TITAN point: titan-n12-r32
- Structured payload bytes: min=331, max=331, mean=331
- Policy experiment: valid accept 50/50, invalid reject 50/50 (reason=dependency_digest_mismatch)
- Signature experiment: verify 50/50, tampered message reject 50/50, tampered signature reject 50/50
- Verify latency: mean=4.806 ms, p95=6.271 ms, throughput=208.073 sig/s
