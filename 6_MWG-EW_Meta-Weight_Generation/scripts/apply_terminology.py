#!/usr/bin/env python3
"""Apply global terminology replacements to patent disclosure documents."""
import os

# Order matters: longer/more-specific patterns first to avoid substring conflicts
replacements = [
    # Compound terms first (longest match first)
    ("\u8282\u70b9\u95f4\u9ad8\u5e26\u5bbd\u901a\u4fe1\u603b\u7ebf", "\u9ad8\u901f\u4e92\u8fde"),
    ("\u878d\u5408\u6267\u884c\u5f15\u64ce", "\u878d\u5408\u7b97\u5b50"),
    ("\u53cd\u5411\u91cd\u7b97\u6a21\u5757", "\u63cf\u8ff0\u5b50\u91cd\u8ba1\u7b97\u6a21\u5757"),
    ("\u53cd\u5411\u91cd\u7b97", "\u53cd\u5411\u91cd\u8ba1\u7b97"),
    ("\u5411\u91cf\u8ba1\u7b97\u5355\u5143", "\u5411\u91cf\u5904\u7406\u5355\u5143"),
    ("\u77e9\u9635\u8ba1\u7b97\u5355\u5143", "\u5f20\u91cf\u8ba1\u7b97\u6838\u5fc3"),
    # On-chip storage: full term first
    ("\u7247\u4e0a\u5b58\u50a8\u5668", "\u7247\u4e0a\u5185\u5b58"),
    ("\u7247\u4e0a\u5b58\u50a8", "\u7247\u4e0a\u5185\u5b58"),
    # External storage: full term first (keep 器)
    ("\u5916\u90e8\u5b58\u50a8\u5668", "\u7247\u5916\u5b58\u50a8\u5668"),
    ("\u5916\u90e8\u5b58\u50a8", "\u7247\u5916\u5b58\u50a8"),
    # 外存 patterns: specific first
    ("\u5916\u5b58\u7269\u5316", "\u7247\u5916\u7269\u5316"),
    ("\u4e0d\u53ef\u5916\u5b58", "\u4e0d\u53ef\u7247\u5916"),
    ("\u5916\u5b58\u8bbf\u95ee", "\u7247\u5916\u5b58\u50a8\u8bbf\u95ee"),
    ("\u5916\u5b58\u4e2d", "\u7247\u5916\u5b58\u50a8\u4e2d"),
    ("\u8bfb\u5916\u5b58", "\u8bfb\u7247\u5916\u5b58\u50a8"),
    # remaining standalone 外存
    ("\u5916\u5b58", "\u7247\u5916\u5b58\u50a8"),
    # Other term replacements
    ("\u5143\u751f\u6210\u5668", "\u63cf\u8ff0\u5b50\u751f\u6210\u5668"),
    ("\u4e0d\u56de\u5199", "\u4e0d\u5199\u56de"),
    ("\u56de\u5199", "\u5199\u56de"),
    ("\u77ed\u9a7b", "\u6682\u7559"),
]

# Verify the replacements are correct by printing them
print("Replacement pairs (decoded):")
for old, new in replacements:
    print(f"  '{old}' -> '{new}'")
print()

files = [
    "\u4e00\u79cd\u9762\u5411\u5b58\u50a8\u5e26\u5bbd\u53d7\u9650\u795e\u7ecf\u7f51\u7edc\u6267\u884c\u7684\u4e34\u65f6\u6743\u91cd\u63cf\u8ff0\u5b50\u751f\u6210\u3001\u6d88\u8d39\u4e0e\u751f\u547d\u5468\u671f\u63a7\u5236\u7cfb\u7edf\u53ca\u65b9\u6cd5-\u4ea4\u5e95\u4e66.md",
    "\u4e00\u79cd\u9762\u5411\u5b58\u50a8\u5e26\u5bbd\u53d7\u9650\u795e\u7ecf\u7f51\u7edc\u6267\u884c\u7684\u4e34\u65f6\u6743\u91cd\u63cf\u8ff0\u5b50\u751f\u6210\u3001\u6d88\u8d39\u4e0e\u751f\u547d\u5468\u671f\u63a7\u5236\u7cfb\u7edf\u53ca\u65b9\u6cd5-\u4ea4\u5e95\u4e66.tex",
]

for fname in files:
    with open(fname, "r", encoding="utf-8") as f:
        text = f.read()
    total = 0
    for old, new in replacements:
        count = text.count(old)
        if count > 0:
            text = text.replace(old, new)
            total += count
            print(f"  '{old}' -> '{new}' ({count}x)")
    with open(fname, "w", encoding="utf-8") as f:
        f.write(text)
    short = fname.split("-")[-1]
    print(f"  === Saved {short}: {total} replacements ===")
    print()

print("All replacements complete.")
