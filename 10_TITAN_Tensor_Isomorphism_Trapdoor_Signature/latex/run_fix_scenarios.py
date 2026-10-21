import re
import os

def main():
    file_path = "/Users/daxu/PATENTS/10_TITAN_Tensor_Isomorphism_Trapdoor_Signature/latex/一种基于张量同构陷门的抗量子数字签名方法、系统、设备及介质-交底书.tex"
    
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    target_phrase = "联邦学习模型聚合、分布式训练同步验签、5G/6G网络切片准入等三大场景（并可扩展至固件升级、V2X广播等场景）"

    # Targeted precise replacements using regex
    
    # 1. Abstract / Introduction occurrences
    text = re.sub(
        r'量子计算网络节点准入认证、AI\s*加速设备固件升级包签名、模型发布\s*清单完整性校验、跨域联邦学习中模型梯度张量防投毒与显存内原生验签、分布式\s*AI\s*训练集群中的梯度/检查点同步验签，以及自动驾驶与车路协同\s*V2X\s*高频广播消息验签等场景',
        target_phrase,
        text,
        flags=re.DOTALL
    )
    
    # 2. Existing "六类" to "三大"
    text = re.sub(r'六类具体场景', r'三大具体场景', text)
    text = re.sub(r'六类业务', r'三大主业务', text)
    text = re.sub(r'六类典型', r'三大典型', text)
    
    # 3. Scattered Lists
    text = re.sub(
        r'节点准入、固件升级、模型发布、联邦学习聚合、分布式训练同步和\s*V2X\s*广播验签流程',
        target_phrase,
        text,
        flags=re.DOTALL
    )
    text = re.sub(
        r'节点接入、固件升级、模型发布、联邦学习聚合、分布式训练同步和\s*V2X\s*广播验签流程',
        target_phrase,
        text,
        flags=re.DOTALL
    )
    text = re.sub(
        r'节点准入、升级校验、训练同步链路或\s*V2X\s*运行时中',
        r'网络切片准入、联邦学习、训练同步链路（以及V2X等扩展场景）中',
        text,
        flags=re.DOTALL
    )
    text = re.sub(
        r'节点准入、固件升级、模型发布、联邦学习梯度校验、分布式训练同步验签和\s*V2X\s*高\s*频广播验签',
        target_phrase,
        text,
        flags=re.DOTALL
    )
    text = re.sub(
        r'节点身份证书摘要、节点角色与调度域字段、\s*固件版本与回滚计数器、模型权.*?V2X广播字段',
        r'联邦学习梯度元数据、分布式训练同步分片、5G/6G网络切片准入证书等主场景的结构化载荷（并可延伸至固件版本、模型权重清单或 V2X 广播等扩展场景字段）',
        text,
        flags=re.DOTALL
    )

    text = re.sub(
        r'量子计算网络节点准入控制器、AI\s*加速设\s*备可信启动/升级代理、模型仓库发布校验代理、联邦学习训练加速卡运行时、分布式训练\s*集群同步代理以及车端\s*V2X\s*消息验签模块',
        r'5G/6G网络切片准入网关、联邦学习训练加速卡运行时、分布式训练集群同步代理（以及扩展的升级代理和车端V2X消息验签模块等）',
        text,
        flags=re.DOTALL
    )

    text = re.sub(
        r'节点准入控制器、设备安全启动链/升级代理、模型仓库校验代理、联邦学习计算图\s*运行时、分布式训练同步代理和车端\s*V2X\s*消息验签模块',
        r'5G/6G网络准入控制器、联邦学习计算图运行时、分布式训练同步代理（以及扩展的升级代理和车端V2X消息验签模块等）',
        text,
        flags=re.DOTALL
    )

    text = re.sub(
        r'量子计算网络节点认证、模型文件签名、固件升级保护、分布\s*式软件发布、跨域联邦学习梯度防投毒、分布式训练集群同步验签以及自动驾驶与车路协同\s*V2X\s*高频广播验签',
        target_phrase,
        text,
        flags=re.DOTALL
    )

    # 4. Section 5 Bullet Points
    section_5_pattern = r'(\\subsection\{三大重点应用场景说明\}.*?\\begin\{itemize\}).*?(\\end\{itemize\})'
    
    new_bullets = r"""
    \item \textbf{5G/6G网络切片准入场景}：验签动作发生在网络控制器或接入网关，目标是在设备接入切片前完成身份摘要和标签的真实性校验，减少伪造设备接入核心网。该场景中本专利的快速验签特性十分关键，确保毫秒级的准入延迟。
    \item \textbf{联邦学习模型聚合场景}：验签动作发生在 GPU/NPU 显存侧或训练框架内部，目标是在模型聚合前校验梯度的合法性，避免将海量张量数据搬运至 CPU，极大地提高了集群吞吐量。
    \item \textbf{分布式训练同步验签场景}：验签动作发生在训练框架的通信代理，目标是在梯度分片、参数块或检查点同步进入 all-reduce 前完成来源校验，降低异常节点污染整个大模型训练过程的风险。
    \item \textbf{其它扩展场景（如固件升级、模型发布、V2X）}：本技术方案亦可灵活退化或扩展应用于硬件设备的固件签名升级、模型仓库的下载校验，以及车路协同环境中对高频车端广播报文的快速验签。
"""

    def replacer(match):
        return match.group(1) + new_bullets + match.group(2)
    
    text = re.sub(section_5_pattern, replacer, text, flags=re.DOTALL)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(text)
    
    print("Replaced scenario references and updated Section 5 bullet points successfully.")

if __name__ == "__main__":
    main()
