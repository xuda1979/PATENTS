"""Build the two editable DOCX forms from the repository's 6* template contract.

Run with the Codex primary runtime Python. QA renders are deliberately external.
"""
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager
from matplotlib.patches import FancyArrowPatch, Rectangle
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "patent_content.json").read_text(encoding="utf-8"))
TEMPLATE = ROOT.parent / "6_MWG-EW_Meta-Weight_Generation"
WIDTH = 14.65


def font(run, size=12, chinese="仿宋", bold=False):
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)
    rp = run._r.get_or_add_rPr()
    rf = rp.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rp.insert(0, rf)
    for key in ["ascii", "hAnsi", "cs"]:
        rf.set(qn("w:" + key), "Times New Roman")
    rf.set(qn("w:eastAsia"), chinese)
    for attr in list(rf.attrib):
        if "Theme" in attr:
            del rf.attrib[attr]


def fmt(p, line=24, indent=True, before=0, after=0, keep=False):
    f = p.paragraph_format
    f.line_spacing = Pt(line)
    f.space_before, f.space_after = Pt(before), Pt(after)
    f.first_line_indent = Pt(24 if indent else 0)
    f.keep_with_next = keep
    f.keep_together = False
    f.widow_control = True


def text(doc, value, search=False, bold=False):
    p = doc.add_paragraph()
    fmt(p, line=18 if search else 24)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.keep_together = search
    font(p.add_run(value), bold=bold)
    return p


def table(doc, rows, widths, size=12, line=18, cover=False):
    t = doc.add_table(rows=0, cols=len(widths))
    t.autofit = False
    for c, w in zip(t.columns, widths):
        c.width = Cm(w)
    props = t._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for side in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        x = OxmlElement("w:" + side)
        for key, value in {"val": "single", "sz": "4", "color": "000000"}.items():
            x.set(qn("w:" + key), value)
        borders.append(x)
    props.append(borders)
    margins = OxmlElement("w:tblCellMar")
    for side in ["top", "bottom", "left", "right"]:
        m = OxmlElement("w:" + side)
        m.set(qn("w:w"), "70" if side in ["top", "bottom"] else "120")
        m.set(qn("w:type"), "dxa")
        margins.append(m)
    props.append(margins)
    for i, values in enumerate(rows):
        row = t.add_row()
        for cell, value, w in zip(row.cells, values, widths):
            cell.width = Cm(w)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            fmt(p, line=line, indent=False)
            if not cover:
                p.paragraph_format.keep_with_next = i < len(rows) - 1
            font(p.add_run(value), size=size, chinese="宋体" if cover else "仿宋")
        pr = row._tr.get_or_add_trPr()
        no_split = OxmlElement("w:cantSplit")
        pr.append(no_split)
        if i == 0 and not cover:
            pr.append(OxmlElement("w:tblHeader"))
    return t


def native_math(doc, key, number):
    p = doc.add_paragraph()
    fmt(p, line=24, indent=False, before=3, after=3)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    om = OxmlElement("m:oMath")

    def mr(value):
        r = OxmlElement("m:r")
        t = OxmlElement("m:t")
        t.text = value
        r.append(t)
        return r

    def sub(base, index):
        s = OxmlElement("m:sSub")
        e = OxmlElement("m:e")
        e.append(mr(base))
        v = OxmlElement("m:sub")
        v.append(mr(index))
        s.extend([e, v])
        return s

    if key == "weights":
        om.append(sub("W", "new"))
        om.append(mr(" = Q("))
        om.append(sub("W", "0"))
        om.append(mr(" + "))
        n = OxmlElement("m:nary")
        np = OxmlElement("m:naryPr")
        ch = OxmlElement("m:chr")
        ch.set(qn("m:val"), "∑")
        np.append(ch)
        loc = OxmlElement("m:limLoc")
        loc.set(qn("m:val"), "subSup")
        np.append(loc)
        n.append(np)
        for tag, val in [("sub", "i=1"), ("sup", "m")]:
            el = OxmlElement("m:" + tag)
            el.append(mr(val))
            n.append(el)
        e = OxmlElement("m:e")
        e.append(sub("α", "i"))
        e.append(mr("Δ"))
        e.append(sub("W", "i"))
        n.append(e)
        om.append(n)
        om.append(mr(")"))
    else:
        for j, (base, index) in enumerate([("H", "k"), ("R", "k"), ("b", "k"), ("B", "k")]):
            if j:
                om.append(mr(" ≤ " if j == 3 else " + "))
            om.append(sub(base, index))
    p._p.append(om)
    font(p.add_run("    （" + str(number) + "）"), size=11)


def drawings():
    fontfile = Path("/home/agent/.local/share/fonts/FandolHei-Regular.otf")
    if fontfile.exists():
        fontManager.addfont(str(fontfile))
        prop = FontProperties(fname=str(fontfile))
    else:
        prop = FontProperties(family="Noto Sans CJK SC")
    plt.rcParams["svg.fonttype"] = "none"

    def setup(h):
        fig, ax = plt.subplots(figsize=(8.4, h))
        fig.subplots_adjust(left=0.005, right=0.995, top=0.985, bottom=0.015)
        ax.set(xlim=(0, 100), ylim=(0, 100))
        ax.axis("off")
        return fig, ax

    def box(ax, x, y, w, h, label):
        ax.add_patch(Rectangle((x, y), w, h, fill=False, linewidth=1, edgecolor="black"))
        ax.text(x + w / 2, y + h / 2, label, fontproperties=prop, ha="center", va="center", fontsize=11)

    def arrow(ax, a, b):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=11, linewidth=1, color="black"))

    fig, ax = setup(3.8)
    box(ax, 1, 65, 26, 27, "101 状态提取\n神经特征与质量")
    box(ax, 36, 65, 26, 27, "102 智能体\n受限控制基系数")
    box(ax, 71, 65, 28, 27, "103 编译器\n绑定权重包")
    arrow(ax, (27, 78), (36, 78)); arrow(ax, (62, 78), (71, 78))
    box(ax, 71, 12, 28, 32, "104 部署管理器\n候选验证与交接\n一致活动描述符")
    box(ax, 36, 12, 26, 32, "105 快环控制器\n106 独立监督器\n跨版本物理账本")
    box(ax, 1, 12, 26, 32, "107 设备驱动器\n完整包许可与回读")
    arrow(ax, (85, 65), (85, 44)); arrow(ax, (71, 28), (62, 28)); arrow(ax, (36, 28), (27, 28))
    arrow(ax, (14, 44), (14, 65))
    arrow(ax, (26, 65), (49, 44))
    ax.text(39, 59, "当前特征", fontproperties=prop, ha="center", fontsize=9)
    arrow(ax, (62, 39), (71, 39))
    ax.text(66, 47, "交接复核", fontproperties=prop, ha="center", fontsize=9)
    for ext in ["png", "svg"]:
        fig.savefig(ROOT / "figures" / ("architecture." + ext), dpi=230, facecolor="white")
    svg = ROOT / "figures" / "architecture.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n", encoding="utf-8")
    plt.close(fig)

    fig, ax = setup(3.6)
    box(ax, 2, 69, 43, 23, "候选区\n校验最终字节及输入约束绑定")
    box(ax, 55, 69, 43, 23, "当前监督状态\n账本  纪元  相位  完整包边界")
    box(ax, 21, 33, 58, 23, "交接凭据\n绑定候选、纪元、首包及预留预算")
    arrow(ax, (24, 69), (37, 56)); arrow(ax, (76, 69), (63, 56))
    box(ax, 21, 1, 58, 20, "边界复核通过：原子发布并一次性使用凭据\n变化或超期：撤销凭据并重新检查")
    arrow(ax, (50, 33), (50, 21))
    for ext in ["png", "svg"]:
        fig.savefig(ROOT / "figures" / ("handover." + ext), dpi=230, facecolor="white")
    svg = ROOT / "figures" / "handover.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n", encoding="utf-8")
    plt.close(fig)


def init_doc(search):
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(3.175)
    sec.top_margin = sec.bottom_margin = Cm(2.54)
    for name in ["Normal", "Title", "Heading 1"]:
        st = doc.styles[name]
        for border in st.element.xpath(".//w:pBdr"):
            border.getparent().remove(border)
        st.font.name = "Times New Roman"
        st.font.size = Pt(12)
        st.font.color.rgb = RGBColor(0, 0, 0)
        st.paragraph_format.space_after = Pt(0)
        st.paragraph_format.line_spacing = Pt(18 if search else 24)
    doc.core_properties.title = DATA["title"] + (" 检索报告" if search else " 技术交底书")
    doc.core_properties.author = "许达、郑智民"
    doc.core_properties.subject = "中国移动研究院"
    doc.core_properties.keywords = "脑机接口；权重编程；部署交接；跨版本输出账本"
    for value in ["中国移动专利申请", "检索报告" if search else "技术交底书"]:
        p = doc.add_paragraph(style="Title")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fmt(p, line=24, indent=False, before=6, after=12)
        font(p.add_run(value), size=22, chinese="黑体")
    authors = "许达、郑智民（均为中国移动研究院）"
    contact = "许达、xudayj@chinamobile.com、13521894156"
    rows = [("发明名称", DATA["title"]), ("申报单位", "中国移动研究院")]
    if search:
        rows += [("检索人", authors + "\n" + contact), ("检索日期", DATA["date"])]
    else:
        rows = [("公司编号", "")] + rows + [("申报类型", "发明"), ("发明人", authors), ("技术联系人", contact)]
    table(doc, rows, [3.2, WIDTH - 3.2], cover=True)
    p = doc.add_paragraph(); fmt(p, line=10, indent=False)
    kind = "检索报告" if search else "交底书"
    if search:
        notice = "注意事项1．检索应当针对发明的关键点充分选取关键词，关键词应使用所属技术领域通用技术术语，而非直接用发明名称或自行命名的系统名称进行检索。2．请按照集团公司提供的本检索报告模板逐项填写，缺检索报告的专利申请，集团公司不予立案；检索报告存在明显问题的，要求重新进行检索。3．检索报告文件命名要求：发明名称＋短横线（半角）＋检索报告＋版本号。"
    else:
        notice = "注意事项1．技术联系人应为深入了解本申请提案技术方案的技术人员，如交底书撰写人，负责向专利审核人员和代理人解释技术细节、修改交底书、审核申请文件等工作，请务必填写技术联系人的姓名、E-mail、手机。2．请按照集团公司提供的本技术交底书模板逐项填写，除交底书第八部分为可选项外，其他均为必须填写的内容。填写不全的专利申请提案，集团公司不予立案。3．专利申请不要求已具体实现或实施，形成完整的技术方案即可提交申请，特别是需要向合作方公开、向标准提案或以其他方式公开的重要技术构思应在公开前尽早申请。4．技术交底书文件命名要求：发明名称＋短横线（半角）＋交底书＋版本号。"
    table(doc, [(notice,)], [WIDTH], size=10.5, line=16)
    if not search:
        p = doc.add_paragraph(); fmt(p, line=18, before=12, after=8, indent=False)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        font(p.add_run("中国移动通信集团有限公司"), size=16, chinese="黑体")
    return doc


COMPARISON = [
    ("文献", "已公开内容", "本申请须进一步限定的关系"),
    ("P1、P2", "大模型建议、远程权重更新", "实际部署表示与当前交接状态绑定"),
    ("P3、P4", "认证、期限、累计计数及安全监督", "首包许可与跨版本账本共同控制激活"),
    ("P5、P6", "安全双缓冲、隔离测试及热替换", "完整包边界及当前纪元复核"),
    ("P7—P9、N1—N3", "相位控制、低秩及权重生成", "不作为单独新颖点"),
    ("L1", "原始文本未核验", "不能排除其影响，须补检")
]


def build(search=False):
    key = "search" if search else "disclosure"
    sections = DATA[key]
    templatefile = next(TEMPLATE.glob("*" + ("检索报告" if search else "交底书") + ".tex"))
    macro = "cmsearchsection" if search else "cmdisclosuresection"
    expected = re.findall(r"\\" + macro + r"\{([^}]+)\}", templatefile.read_text(encoding="utf-8"))
    assert [s["heading"] for s in sections] == expected, "Template chapter mismatch"
    doc = init_doc(search)
    for section in sections:
        p = doc.add_paragraph(style="Heading 1")
        fmt(p, line=18 if search else 24, before=8, after=2, keep=True)
        font(p.add_run(section["heading"]), chinese="仿宋" if search else "黑体")
        for item in section["paragraphs"]:
            if isinstance(item, str):
                text(doc, item, search)
            elif "figure" in item:
                p = doc.add_paragraph(); fmt(p, line=12, indent=False, before=4, after=2, keep=True)
                p.paragraph_format.line_spacing = 1.0
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.add_run().add_picture(str(ROOT / "figures" / (item["figure"] + ".png")), width=Cm(WIDTH - .1))
                p = doc.add_paragraph(); fmt(p, line=16, indent=False, after=4)
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                font(p.add_run(item["caption"]), size=10.5)
            elif "equation" in item:
                native_math(doc, item["equation"], item["number"])
            elif "url" in item:
                doc.paragraphs[-1].paragraph_format.keep_with_next = True
                p = doc.add_paragraph(); fmt(p, line=14, indent=False, after=3)
                font(p.add_run(item["url"]), size=10)
            elif "comparison" in item:
                table(doc, COMPARISON, [2.3, 5.3, WIDTH - 7.6], size=10.5, line=16)
        if search and section["heading"] == "四、检索结论":
            for p in doc.paragraphs[-len(section["paragraphs"]):-1]:
                p.paragraph_format.keep_with_next = True
    out = ROOT / (DATA["title"] + "-" + ("检索报告" if search else "交底书") + DATA["version"] + ".docx")
    doc.save(out)
    md = ["中国移动专利申请", "检索报告" if search else "技术交底书", ""]
    for s in sections:
        md.extend(["## " + s["heading"], ""])
        for item in s["paragraphs"]:
            if isinstance(item, str):
                md.extend([item, ""])
            elif "figure" in item:
                md.extend(["![" + item["caption"] + "](figures/" + item["figure"] + ".svg)", ""])
            elif "url" in item:
                md.extend([item["url"], ""])
            elif "equation" in item:
                eq = r"W_{new}=Q\left(W_0+\sum_{i=1}^{m}\alpha_i\Delta W_i\right)" if item["equation"] == "weights" else r"H_k+R_k+b_k\le B_k"
                md.extend(["$$" + eq + "$$", ""])
            else:
                md.extend(["| " + " | ".join(COMPARISON[0]) + " |", "| --- | --- | --- |"])
                md.extend("| " + " | ".join(row) + " |" for row in COMPARISON[1:])
                md.append("")
    out.with_suffix(".md").write_text("\n".join(md), encoding="utf-8")
    return out


if __name__ == "__main__":
    drawings()
    for search in [False, True]:
        print(build(search))
