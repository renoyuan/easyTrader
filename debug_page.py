#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests, re
from bs4 import BeautifulSoup

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.cpcaauto.com/",
}
s = requests.Session()
s.get("https://www.cpcaauto.com/", headers=headers, timeout=15)

resp = s.get("https://www.cpcaauto.com/news.php?types=csjd&page=1", headers=headers, timeout=15)
resp.encoding = "utf-8"
soup = BeautifulSoup(resp.text, "lxml")

print("=== 所有带 anid 的链接 ===")
a_tags = soup.select('a[href*="anid="]')
print(f"共 {len(a_tags)} 个")
for a in a_tags:
    title = a.get_text(strip=True)
    href = a.get("href", "")
    print(f"  [{title[:50]}] -> {href}")

print("\n=== 所有链接（前30） ===")
all_a = soup.find_all("a")
for a in all_a[:30]:
    title = a.get_text(strip=True)
    href = a.get("href", "")
    if title and href and "javascript" not in href:
        print(f"  [{title[:40]}] -> {href}")
