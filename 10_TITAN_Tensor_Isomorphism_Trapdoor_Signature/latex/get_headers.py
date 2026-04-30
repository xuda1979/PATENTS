import re

tex_file = "/Users/daxu/PATENTS/10_TITAN_Tensor_Isomorphism_Trapdoor_Signature/latex/一种基于张量同构陷门的抗量子数字签名方法、系统、设备及介质-交底书.tex"
with open(tex_file, 'r', encoding='utf-8') as f:
    text = f.read()

headers = re.findall(r"\\section\{([^}]+)\}", text)
for i, h in enumerate(headers, 1):
    print(f"Header {i}: {h}")
