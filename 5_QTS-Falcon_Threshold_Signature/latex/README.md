# Patent LaTeX Documentation System
# 专利 LaTeX 文档系统

## 目录结构 / Directory Structure

```
5_QTS-Falcon_Threshold_Signature/
├── latex/
│   ├── main.tex              # 主文档 (编译此文件)
│   ├── compile.ps1           # PowerShell 编译脚本
│   ├── README.md             # 本说明文件
│   ├── sections/
│   │   ├── titlepage.tex     # 封面
│   │   ├── abstract.tex      # 摘要
│   │   ├── claims.tex        # 权利要求书
│   │   ├── description.tex   # 说明书
│   │   └── drawings.tex      # 附图 (TikZ矢量图)
│   ├── figures/              # 外部图片文件 (如需要)
│   └── output/               # 编译输出目录
└── 专利申请_量子安全门限签名.pdf  # 最终PDF输出
```

## 系统要求 / Requirements

### LaTeX 发行版 (安装其一):

1. **MiKTeX** (Windows 推荐)
   - 下载: https://miktex.org/download
   - 自动安装所需宏包

2. **TeX Live**
   - 下载: https://tug.org/texlive/
   - 建议完整安装

### 所需宏包 (MiKTeX 自动安装):
- `ctex` - 中文支持
- `tikz` - 矢量图形
- `pgfplots` - 数据图表
- `amsmath` - 数学公式
- `geometry` - 页面布局
- `hyperref` - PDF超链接
- `booktabs` - 专业表格

## 编译方法 / Compilation

### 方法 1: PowerShell 脚本 (推荐)
```powershell
cd "c:\Users\Lenovo\patents\5_QTS-Falcon_Threshold_Signature\latex"
.\compile.ps1
```

### 方法 2: 手动编译
```powershell
cd "c:\Users\Lenovo\patents\5_QTS-Falcon_Threshold_Signature\latex"
xelatex -output-directory=output main.tex
xelatex -output-directory=output main.tex
xelatex -output-directory=output main.tex
```

### 方法 3: VS Code LaTeX Workshop 扩展
1. 安装 "LaTeX Workshop" 扩展
2. 打开 `main.tex`
3. 按 `Ctrl+Alt+B` 编译

## 文档内容 / Document Contents

### 1. 封面 (titlepage.tex)
- 发明名称
- 申请人/发明人信息
- IPC 分类号
- 技术要点概述

### 2. 摘要 (abstract.tex)
- 中文摘要 (≤300字)
- 英文摘要
- 关键词
- 技术效果对比表

### 3. 权利要求书 (claims.tex)
- 独立权利要求 1-3
- 从属权利要求 4-12

### 4. 说明书 (description.tex)
- 技术领域
- 背景技术
- 发明内容
- 附图说明
- 具体实施方式
- 技术效果

### 5. 附图 (drawings.tex)
- 图1: 系统整体架构图
- 图2: 协同纠偏采样流程图
- 图3: 动态节点管理示意图
- 图4: 协议通信轮次示意图
- 图5: 性能对比图

## PDF 质量特点 / PDF Quality Features

✅ **矢量图形** - TikZ 绘制，无限缩放不失真
✅ **字体嵌入** - 确保跨平台显示一致
✅ **数学公式** - LaTeX 高质量排版
✅ **超链接** - 目录和交叉引用可点击
✅ **PDF/A 兼容** - 适合长期存档
✅ **CNIPA 格式** - 符合中国专利局要求

## 修改指南 / Editing Guide

### 修改文字内容
直接编辑 `sections/` 目录下对应的 `.tex` 文件

### 添加新附图
在 `sections/drawings.tex` 中添加新的 TikZ 图形:
```latex
\begin{figure}[H]
\centering
\begin{tikzpicture}
    % 你的图形代码
\end{tikzpicture}
\caption{图片标题}
\end{figure}
```

### 可用 TikZ 样式
- `process` - 蓝色圆角矩形 (处理步骤)
- `decision` - 绿色菱形 (判断)
- `startstop` - 红色椭圆 (开始/结束)
- `component` - 灰色矩形 (组件)
- `node_box` - 节点框
- `arrow` - 粗箭头

## 注意事项 / Notes

1. 原始 `.doc` 文件保留在主目录，不受影响
2. 所有新文档开发在 LaTeX 中进行
3. 编译输出自动复制到主目录
4. 建议使用 XeLaTeX 以获得更好的中文支持

---

*生成日期: 2026年1月6日*
