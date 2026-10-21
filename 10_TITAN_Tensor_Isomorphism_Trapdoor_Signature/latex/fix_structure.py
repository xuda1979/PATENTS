import re

tex_file = "/Users/daxu/PATENTS/10_TITAN_Tensor_Isomorphism_Trapdoor_Signature/latex/一种基于张量同构陷门的抗量子数字签名方法、系统、设备及介质-交底书.tex"

with open(tex_file, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Extract the text of "联邦学习场景下的显存内原生验签机制"
pattern_fl = r"\\subsection\{联邦学习场景下的显存内原生验签机制\}\n\n(.*?)(?=\\subsection|\\section)"
match_fl = re.search(pattern_fl, text, flags=re.DOTALL)
fl_text = ""
if match_fl:
    fl_text = match_fl.group(1).strip()
    text = text.replace(match_fl.group(0), "")

# 2. Re-write the scenarios section
new_scenarios = r"""\subsection{三大重点应用场景说明}

为最大化本申请作为技术方案的客体稳定性，本申请优先强调以下三类具有物理属性、硬件边界和可量化技术效果的应用场景：

\begin{itemize}
    \item \textbf{跨域联邦学习梯度防投毒场景}：验签动作发生在 GPU/NPU 显存侧或训练框架计算图内部，目标是在模型聚合前校验梯度张量或模型更新块的来源合法性和完整性，技术效果体现为防投毒、减少 PCIe 或其它主机总线搬运开销、提高集群吞吐量并降低 CPU 参与度。
    
    【联邦学习场景下的显存内原生验签补充说明】
    这一场景是本专利特别关键的应用方向。原因在于，联邦学习里传输和聚合的对象本身就是梯度张量，而本专利的签名验证核心也是张量运算，底层硬件又正好是 GPU/NPU 的张量计算单元，因此三者天然对齐，能够把“安全校验”直接并入“训练计算流”。
    在跨域联邦学习场景中，待签名对象 $M_{fl}$ 不是普通字符串，而是边缘节点计算出的高维模型梯度张量或模型更新块。现有签名算法通常需要将这些数据从 AI 加速器显存搬运到主机 CPU 内存，再进行哈希和验签。由于梯度数据量较大，这种跨总线搬运会显著降低系统吞吐量。
    针对上述问题，本申请提供如下解决方案：\textbf{将验签过程保留在显存中完成，避免梯度数据的跨总线搬运。}
    具体地，可将本申请的张量同构验签逻辑直接编译为深度学习框架的自定义算子，并嵌入联邦学习聚合计算流图中。这样，聚合节点在接收到梯度张量后，无需先把梯度拷贝到 CPU 侧内存，而是直接在 GPU、NPU 或 Tensor Core 对应的显存内部完成多轮挑战下的张量重构与一致性校验。校验失败时，异常梯度在显存侧直接被阻断，不进入参数聚合过程。
    换言之，\textbf{训练用的张量留在原来的地方，安全校验也在原来的地方做完。}

    \item \textbf{分布式 AI 训练集群中的梯度/检查点同步验签场景}：验签动作发生在训练框架同步代理、分布式训练运行时或加速卡通信侧，目标是在梯度分片、参数块和检查点分片进入同步链路前完成来源合法性和完整性校验。技术效果体现为减少异常数据进入 all-reduce、参数恢复和断点续训流程，并尽量复用现有张量算力。举例来说，多机多卡训练一个大模型时，节点在同步梯度分片前，先检查分片摘要是否与签名一致，不一致则不允许进入同步流程。该场景中本专利特别重要，因为训练集群同步频率高、数据量大，只要混入异常分片，就可能拖垮整轮训练；而本专利由于直接基于张量数学，验签速度极快且高度契合AI加速硬件，不会成为同步通信的瓶颈。

    \item \textbf{5G/6G核心网网络切片准入签名场景}：验签动作发生在网关及核心网设备节点，目标是对请求建立网络切片的终端设备和会话进行极高并发的入网身份合法性校验。技术效果体现为避免因传统晶格高斯采样导致的时延抖动，满足毫秒级及高确定的处理预算。本专利的无高斯拒绝采样特性使得一次签名时间和验证时间严格恒定，这在网络切片面对突发信令洪峰时极为关键；同时验证计算依赖有限域矩阵乘法，非常容易通过定制化算子在5G/6G基站侧专用的轻量级NPU或FPGA内实现线速验证。
\end{itemize}
"""

pattern_replace = r"\\subsection\{(六|三)类重点应用场景说明\}.*?\\end\{itemize\}"

text = re.sub(pattern_replace, new_scenarios.replace("\\", "\\\\"), text, flags=re.DOTALL)
# Also check if it was already matching 三大重点应用场景说明
pattern_replace_2 = r"\\subsection\{三大重点应用场景说明\}.*?\\end\{itemize\}"
text = re.sub(pattern_replace_2, new_scenarios.replace("\\", "\\\\"), text, flags=re.DOTALL)

with open(tex_file, 'w', encoding='utf-8') as f:
    f.write(text)

print("Replacement Complete")
