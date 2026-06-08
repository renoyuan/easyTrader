with open("D:\\code\\opensource\\easyTrader\\trader\\gui\\main_window.py", "r", encoding="utf-8") as f:
    content = f.read()

old = """            entry = tk.Entry(
                row, bg=COLOR_CARD_BG, fg=COLOR_PRIMARY,
                font=FONT_NORMAL, bd=0, relief=tk.FLAT,
                width=50, state="readonly", readonlybackground=COLOR_CARD_BG,
            )
            entry.insert(0, value)
            entry.pack(side=tk.LEFT, padx=(6, 0))"""

new = """            tk.Label(
                row, text=value, bg=COLOR_CARD_BG, fg=COLOR_PRIMARY,
                font=FONT_NORMAL, anchor=tk.W
            ).pack(side=tk.LEFT, padx=(6, 0))"""

if old in content:
    content = content.replace(old, new)
    with open("D:\\code\\opensource\\easyTrader\\trader\\gui\\main_window.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("Fixed about labels!")
else:
    print("Not found!")
    idx = content.find("tk.Entry(")
    print("Around:", repr(content[idx-30:idx+200]))
