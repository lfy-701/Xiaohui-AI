"""校验生成的 docx：段落、表格、字体是否正确。"""
from docx import Document

path = r"C:\Users\53487\Documents\deepseek-harness\default-workspace\docs\成员A模型服务接入指南.docx"
doc = Document(path)

print("段落数:", len(doc.paragraphs))
print("表格数:", len(doc.tables))
print("\n--- 前 12 段 ---")
for p in doc.paragraphs[:12]:
    if p.text.strip():
        print(f"[{p.style.name}] {p.text[:70]}")

print("\n--- 标题结构 ---")
for p in doc.paragraphs:
    if p.style.name.startswith("Heading") and p.text.strip():
        print(f"{'  ' * (int(p.style.name[-1]) - 1)}{p.text}")

print("\n--- 表格尺寸 ---")
for i, t in enumerate(doc.tables):
    print(f"表 {i}: {len(t.rows)} 行 x {len(t.columns)} 列 | 首行: {[c.text for c in t.rows[0].cells]}")

# 字体检查
from docx.oxml.ns import qn
title_run = doc.paragraphs[0].runs[0]
print("\n标题字体:", title_run.font.name, "| eastAsia:",
      title_run._element.rPr.rFonts.get(qn("w:eastAsia")), "| size:", title_run.font.size.pt)
