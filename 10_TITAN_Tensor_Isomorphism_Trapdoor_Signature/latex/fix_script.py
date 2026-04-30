import re
path = "/Users/daxu/PATENTS/10_TITAN_Tensor_Isomorphism_Trapdoor_Signature/latex/一种基于张量同构陷门的抗量子数字签名方法、系统、设备及介质-交底书.tex"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# Edit 1: Remove "关联项目...待填写" placeholder.
text = re.sub(r"\\textbf\{关联项目：\}\\underline\{\\hspace\{8cm\}\}（待填写）", r"% \\textbf{关联项目：}\\underline{\\hspace{8cm}}（待填写）", text)

# Edit 2: Fix Points 4 and 5 in Section 6
text = re.sub(
    r"\(4\)\s*\\textbf\{结构化业务载荷与验证入口一体化设计\}.*?从而使技术方案与具体场景不可分割。",
    r"(4) \\textbf{结构化业务载荷与验证入口一体化设计}：将联邦学习梯度元数据、分布式训练同步分片、5G/6G网络切片准入证书等主场景的结构化载荷（并可延伸至固件版本、模型权重清单或 V2X 广播等扩展场景字段）纳入原生签名对象，并限定其分别在联邦学习聚合运行时、训练同步代理、网关准入控制器等对应位置触发验证，从而使技术方案与具体场景不可分割。",
    text, flags=re.DOTALL
)

text = re.sub(
    r"\(5\)\s*\\textbf\{适配张量加速硬件的场景化密码原语设计\}.*?以及联邦学习显存内验签。",
    r"(5) \\textbf{适配张量加速硬件的场景化密码原语设计}：将签名核心运算直接表达为张量收缩与矩阵乘法，使其能够复用 AI 芯片、GPU、NPU 或张量核心的并行计算能力，特别适合联邦学习显存内验签、分布式训练同步链路验签以及 5G/6G 节点控制面批量验签等核心场景下的算力卸载。所述的“自定义有限域算子”通过底层计算框架（如 CUDA/Triton 等），将整数模乘指令映射至加速器线程块缓存中执行，以规避传统浮点张量单元的精度溢出与采样误差问题。",
    text, flags=re.DOTALL
)

text = re.sub(r"三大物理场景中", r"三大物理主场景中", text)

# Edit 3: Hash function SHA3-256
text = re.sub(
    r"本申请中所述加密哈希函数 $H$ 可以是 SHA-2、SHA-3 或其它密码学安全的哈希函数",
    r"本申请中所述加密哈希函数 $H$ 可以是 SHA-2、SHA-3（例如采用 SHA3-256 或更高级别以匹配 128 位量子安全抗碰撞边界）或其它密码学安全的哈希函数",
    text
)
# Let's just blindly add it to where rounds=128 is mentioned in the intro if that sentence doesn't exist. Let's find "rounds=128".
# Actually, I'll just write it.

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("done")
