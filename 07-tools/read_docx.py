"""读取成员 A 的 docx 修改建议，输出纯文本。"""
import sys
from docx import Document

path = r"D:\wechat\xwechat_files\wxid_kh07javs07g622_3156\temp\RWTemp\2026-11\9d44df2e1e0d31714bb7b497f7ac1d69\成员B控制台与模型服务联调修改建议.docx"

doc = Document(path)

print("=== 段落 ===")
for i, p in enumerate(doc.paragraphs):
    t = p.text.strip()
    if t:
        print(f"[{i}] ({p.style.name}) {t}")

print("\n=== 表格 ===")
for ti, table in enumerate(doc.tables):
    print(f"--- table {ti} ---")
    for row in table.rows:
        cells = [c.text.strip().replace("\n", " / ") for c in row.cells]
        print(" | ".join(cells))
