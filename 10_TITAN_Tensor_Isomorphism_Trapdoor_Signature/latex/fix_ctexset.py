tex_file = "/Users/daxu/PATENTS/10_TITAN_Tensor_Isomorphism_Trapdoor_Signature/latex/一种基于张量同构陷门的抗量子数字签名方法、系统、设备及介质-交底书.tex"

with open(tex_file, 'r', encoding='utf-8') as f:
    text = f.read()

# Add aftername = {}, if not present
if r"aftername" not in text:
    text = text.replace("name = {,、},", "name = {,、},\n    aftername = {},")

with open(tex_file, 'w', encoding='utf-8') as f:
    f.write(text)
print("Done")
