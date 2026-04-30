import re
path = "/Users/daxu/PATENTS/10_TITAN_Tensor_Isomorphism_Trapdoor_Signature/latex/一种基于张量同构陷门的抗量子数字签名方法、系统、设备及介质-交底书.tex"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# Add Figure Note
text = re.sub(
    r"本申请提出一种 TITAN（Tensor Isomorphism Trapdoor Asymmetric Network，张量同构陷门非对称网络）抗量子数字签名方案。本方案的核心在于：",
    r"本申请提出一种 TITAN（Tensor Isomorphism Trapdoor Asymmetric Network，张量同构陷门非对称网络）抗量子数字签名方案。（注：为满足专利法“充分公开”与提供附图说明等实务要求，在移交代理所撰写正式申请文件时，请配合本章节提供相应系统运行方法的方法流程图、5G/6G 网络切片验签架构框图或硬件部署结构图等附图说明）。本方案的核心在于：",
    text
)

# And fix the 6 scenarios list on line 168
text = re.sub(
    r"节点接入、固件升级、模型发布、联邦学习聚合、分布式训练同步和 V2X 广播验签流程",
    r"5G/6G节点接入、联邦学习聚合、分布式训练同步等三大主要场景以及相关扩展场景的验签流程",
    text
)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Figures fix applied.")
