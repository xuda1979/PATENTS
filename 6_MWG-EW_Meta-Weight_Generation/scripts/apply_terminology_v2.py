#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply global terminology replacements to patent disclosure documents.
Uses single-pass regex to avoid substring collision between replacements.
Run from the project root directory."""
import re
import os
import sys

def main():
    # All replacement pairs. Order does NOT matter because we use single-pass
    # regex with longest-match-first priority.
    replacements = {
        "节点间高带宽通信总线": "高速互连",
        "融合执行引擎": "融合算子",
        "反向重算模块": "描述子重计算模块",
        "反向重算": "反向重计算",
        "向量计算单元": "向量处理单元",
        "矩阵计算单元": "张量计算核心",
        "片上存储器": "片上内存",
        "片上存储": "片上内存",
        "外部存储器": "片外存储器",
        "外部存储": "片外存储",
        "外存物化": "片外物化",
        "不可外存": "不可片外",
        "外存访问": "片外存储访问",
        "外存中": "片外存储中",
        "读外存": "读片外存储",
        "外存": "片外存储",
        "元生成器": "描述子生成器",
        "不回写": "不写回",
        "回写": "写回",
        "短驻": "暂留",
        # Identity mappings: protect pre-existing "片外" patterns from
        # the "外存" rule matching within them
        "片外存储": "片外存储",
        "片外总线": "片外总线",
        "片外显存": "片外显存",
    }

    # Build regex: sort keys by length (longest first) so longer matches
    # take priority over shorter substrings. This is a SINGLE-PASS approach:
    # each position in the text is matched at most once.
    sorted_keys = sorted(replacements.keys(), key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(k) for k in sorted_keys))

    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prefix = "\u4e00\u79cd\u9762\u5411\u5b58\u50a8\u5e26\u5bbd\u53d7\u9650\u795e\u7ecf\u7f51\u7edc\u6267\u884c\u7684\u4e34\u65f6\u6743\u91cd\u63cf\u8ff0\u5b50\u751f\u6210\u3001\u6d88\u8d39\u4e0e\u751f\u547d\u5468\u671f\u63a7\u5236\u7cfb\u7edf\u53ca\u65b9\u6cd5-\u4ea4\u5e95\u4e66"
    files = [os.path.join(base, prefix + ext) for ext in [".md", ".tex"]]

    for fpath in files:
        fname = os.path.basename(fpath)
        with open(fpath, "r", encoding="utf-8") as f:
            text = f.read()

        counts = {}
        def replace_fn(m):
            old = m.group(0)
            counts[old] = counts.get(old, 0) + 1
            return replacements[old]

        text = pattern.sub(replace_fn, text)

        with open(fpath, "w", encoding="utf-8") as f:
            f.write(text)

        total = sum(c for k, c in counts.items() if replacements[k] != k)
        ext = fname.split(".")[-1]
        for old in sorted_keys:
            if old in counts and replacements[old] != old:
                print(f"  '{old}' -> '{replacements[old]}' ({counts[old]}x)")
        print(f"  === Saved .{ext}: {total} replacements ===\n")

    print("All replacements complete.")

if __name__ == "__main__":
    main()
