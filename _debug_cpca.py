# -*- coding: utf-8 -*-
import requests, re
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.cpcaauto.com/',
}
s = requests.Session()

# 首页
print('===== 首页 =====')
r = s.get('https://www.cpcaauto.com/', headers=headers, timeout=20)
print(f'状态: {r.status_code}, 编码: {r.encoding}')

# 列表页
print('\n===== 列表第1页 =====')
r2 = s.get('https://www.cpcaauto.com/news.php?types=csjd&page=1', headers=headers, timeout=20)
r2.encoding = 'utf-8'
text = r2.text

print(f'页面长度: {len(text)} 字符')

# 1. 检查 anid= 的出现
anid_count = text.count('anid=')
print(f'字符串 "anid=" 出现次数: {anid_count}')

# 2. 检查 【月度排名】
target = '\u3010\u6708\u5ea6\u6392\u540d\u3011'
count_monthly = text.count(target)
print(f'字符串 "【月度排名】" 出现次数: {count_monthly}')

# 3. 看看链接到底是什么样
soup = BeautifulSoup(text, 'lxml')
all_a = soup.find_all('a')
print(f'\n页面中总 <a> 标签数: {len(all_a)}')

# 看看前15个链接
for i, a in enumerate(all_a[:20]):
    href = a.get('href', '')
    title = a.get_text(strip=True)[:40]
    print(f'  [{i}] href=[{href}] title=[{title}]')

# 看看页面实际内容（前3000字符）
print('\n===== 页面原始HTML前3000字符 =====')
print(text[:3000])
