"""固件：调整坐下/趴下姿态，加快并延长跳舞；页面加「起身」按钮。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

FW = Path(r"D:\xiaozhi-esp32-2.5.2\main\boards\esp32-dog-wangcai")
S = FW / "servo_controller.cc"
t = S.read_text(encoding="utf-8")

# 1) 坐下：前腿抬高撑起、后腿收得更低
old_sit = "    MoveAll({110, 110, 70, 70, 90, 90}, 600);"
new_sit = "    MoveAll({145, 145, 35, 35, 90, 90}, 700);"
if old_sit in t:
    t = t.replace(old_sit, new_sit, 1)
    print("坐下：已调整角度")

# 2) 趴下：更低更平
old_lie = "    MoveAll({135, 135, 45, 45, 90, 75}, 700);"
new_lie = "    MoveAll({158, 158, 22, 22, 90, 60}, 800);"
if old_lie in t:
    t = t.replace(old_lie, new_lie, 1)
    print("趴下：已调整角度")

# 3) 跳舞：更快（260→170ms）且循环更多
t = t.replace("    MoveAll({70, 70, 110, 110, 90, 60}, 260);",
              "    MoveAll({70, 70, 110, 110, 90, 60}, 170);", 1)
t = t.replace("    MoveAll({110, 110, 70, 70, 90, 120}, 260);",
              "    MoveAll({110, 110, 70, 70, 90, 120}, 170);", 1)
print("跳舞：已加快（260ms → 170ms）")

S.write_text(t, encoding="utf-8")

# 4) 动作入口：Dance(2) → Dance(4)
B = FW / "dog_board.cc"
b = B.read_text(encoding="utf-8")
if "servo_.Dance(2);" in b:
    b = b.replace("servo_.Dance(2);", "servo_.Dance(4);", 1)
    B.write_text(b, encoding="utf-8")
    print("跳舞：循环 2 → 4 次（更持久）")

# 5) 页面加「起身」
C = Path(r"D:\AI-Companion-shared\xiaohui-ai\console\static\chat.html")
c = C.read_text(encoding="utf-8")
if 'data-a="stand"' not in c:
    c = c.replace('    <button data-a="dance">跳舞</button>',
                  '    <button data-a="stand">起身</button>\n    <button data-a="dance">跳舞</button>', 1)
    C.write_text(c, encoding="utf-8")
    print("页面：已加「起身」按钮")
