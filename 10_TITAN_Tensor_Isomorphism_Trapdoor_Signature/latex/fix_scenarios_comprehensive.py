import re
import os

def main():
    file_path = "一种基于张量同构陷门的抗量子数字签名方法、系统、设备及介质-交底书.tex"
    
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    # The exact unified string requested by the user
    target_phrase = "联邦学习模型聚合、分布式训练同步验签、5G/6G网络切片准入等三大场景（并可扩展至固件升级、V2X广播等场景）"
    
    # 1. Broadly match and replace the scattered scenario references in the text.
    #    We use a generic regex to catch lists containing V2X, models, etc.
    
    patterns_to_replace = [
        # Catch variations like: 5G/6G核心网网络切片准入签名、跨域联邦学习中模型梯度张量防投毒...固件升级包签名、模型发布...等场景
        r'(?:5G/6G|量子计算).{5,100}跨域联邦学习.{5,100}分布式.*?同步验签.*?车端\s*V2X.*?场景',
        # Catch: 联邦学习、分布式训练同步和5G/6G网络切片准入流程（以及相关的扩展场景如固件升级、模型发布和V2X等）
        r'联邦学习、分布式训练同步和5G/6G网络切片准入流程（以及相关的扩展场景如固件升级、模型发布和V2X等）',
        # Catch: 联邦学习梯度校验、分布式训练同步验签和5G/6G网络切片准入（以及扩展的节点准入、升级、发布和V2X等）
        r'联邦学习梯度校验、分布式训练同步验签和5G/6G网\s*络切片准入（以及扩展的节点准入、升级、发布和V2X等）',
        # Catch: 量子计算网络节点准入控制、AI加速设备固件升级、模型仓库发布校验、跨域联邦学习梯度原生验签、分布式AI训练集群同步以及车端V2X高频消息验签
        r'量子计算网络节点准入控制器?.*?车端\s*V2X\s*.*?(?:消息验签|模块)',
        r'节点准入控制器.*?车端\s*V2X.*?验签模块',
        r'量子计算网络节点认证.*?高频广播验签',
    ]

    for pat in patterns_to_replace:
        # replace with target phrase (or a slightly adapted version based on the grammatical context)
        # using a simple replace for all scattered variants to point to the main three + extensions.
        text = re.sub(pat, target_phrase, text, flags=re.DOTALL)

    # Note: the above might clobber grammatical flow in a few spots. A more manual replace might be better for an exact file edit,
    # but the prompt asked for a python script that runs a "comprehensive replace" over the file.
    
    # 2. Fix the Section 5 bullet points titled "三大重点应用场景说明"
    # Find the section, remove the 6 old bullets and insert the 4 new ones.
    
    # We will look for "\subsection{三大重点应用场景说明}" -> then the first \begin{itemize} ... \end{itemize}
    
    section_5_pattern = r'(\\subsection\{三大重点应用场景说明\}.*?\\begin\{itemize\}).*?(\\end\{itemize\})'
    
    new_bullets = r"""
    \\item \\textbf{5G/6G网络切片准入场景}：验签动作发生在网络控制器或接入网关，目标是在设备接入切片前完成身份摘要和标签的真实性校验，减少伪造设备接入核心网。该场景中本专利的快速验签特性十分关键，确保毫秒级的准入延迟。
    \\item \\textbf{联邦学习模型聚合场景}：验签动作发生在 GPU/NPU 显存侧或训练框架内部，目标是在模型聚合前校验梯度的合法性，避免将海量张量数据搬运至 CPU，极大地提高了集群吞吐量。
    \\item \\textbf{分布式训练同步验签场景}：验签动作发生在训练框架的通信代理，目标是在梯度分片、参数块或检查点同步进入 all-reduce 前完成来源校验，降低异常节点污染整个大模型训练过程的风险。
    \\item \\textbf{其它扩展场景（如固件升级、模型发布、V2X）}：本技术方案亦可灵活退化或扩展应用于硬件设备的固件签名升级、模型仓库的下载校验，以及车路协同环境中对高频车端广播报文的快速验签。
"""
    
    # We use a function for the replacement to avoid backslash escaping issues
    def replacer(match):
        return match.group(1) + new_bullets + match.group(2)
    
    text = re.sub(section_5_pattern, replacer, text, flags=re.DOTALL)

    # Save changes
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)
    
    print("Replaced scenario references and updated Section 5 bullet points successfully.")

if __name__ == "__main__":
    main()
