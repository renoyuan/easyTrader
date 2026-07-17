
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""乘联会月度销量采集 v2 - 使用 cloudscraper 绕过反爬"""
import re, time, cloudscraper, pandas as pd
from bs4 import BeautifulSoup

BASE_LIST = 'https://www.cpcaauto.com/news.php?types=csjd&page={page}'
START, END, SAVE = 2016, 2026, '乘联会2016-2026月度销量数据.csv'
DELAY = 3.0

scraper = cloudscraper.create_scraper(browser={'browser':'chrome','platform':'windows','desktop':True})

def get(url, d=DELAY, retry=2):
    time.sleep(d)
    try:
        r = scraper.get(url, timeout=30)
        r.encoding = 'utf-8'
        return BeautifulSoup(r.text, 'lxml')
    except Exception as e:
        if retry: return get(url, d+1, retry-1)
        print(f'Fail: {e}'); return None

def main():
    print('Init...')
    get('https://www.cpcaauto.com/', 2)
    
    links = []
    page, empty = 1, 0
    while True:
        print(f'Page {page}...')
        soup = get(BASE_LIST.format(page=page))
        if not soup: break
        
        found = False
        for a in soup.find_all('a'):
            title = a.get_text(strip=True)
            href = a.get('href','')
            if not title or len(title)<5: continue
            if not any(k in title for k in ['月度','月销量','厂商','月报']): continue
            m = re.search(r'(\d{4})[年-](\d{1,2})月', title)
            if not m: continue
            y, mo = int(m.group(1)), int(m.group(2))
            if not (START <= y <= END): continue
            id_m = re.search(r'(?:an?id|id)=(\d+)', href)
            if not id_m: continue
            links.append({'date':f'{y}-{mo:02d}','year':y,'month':mo,'title':title,
                          'anid':id_m.group(1),'url':f'https://www.cpcaauto.com/show.php?anid={id_m.group(1)}'})
            found = True
        
        if not found:
            empty += 1
            if empty >= 3: print('连续3页无数据，停止'); break
        else: empty = 0
        page += 1
    
    # 去重
    seen = set()
    links = [l for l in links if not (l['date'] in seen or seen.add(l['date']))]
    links.sort(key=lambda x:(x['year'],x['month']))
    print(f'共 {len(links)} 条')
    
    if not links: print('无数据'); return
    
    data = []
    for i, item in enumerate(links, 1):
        print(f'[{i}/{len(links)}] {item["date"]} {item["title"]}')
        soup = get(item['url'], 3)
        if not soup: continue
        text = soup.get_text(' ', strip=True)
        row = {'date':item['date'],'title':item['title'],'url':item['url']}
        
        def ext(p): m = re.search(p, text); return float(m.group(1)) if m else None
        row['零售总量_万辆'] = ext(r'零售销量达([\d.]+)万辆')
        
        yoy = ext(r'同比增长([\d.]+)%')
        yoy_d = ext(r'同比下降([\d.]+)%')
        row['零售同比%'] = yoy if yoy else (-yoy_d if yoy_d else None)
        
        mom = ext(r'环比增长([\d.]+)%')
        mom_d = ext(r'环比下降([\d.]+)%')
        row['零售环比%'] = mom if mom else (-mom_d if mom_d else None)
        
        row['轿车_万辆'] = ext(r'轿车销量([\d.]+)万辆')
        row['SUV_万辆'] = ext(r'SUV销量([\d.]+)万辆')
        row['MPV_万辆'] = ext(r'MPV销量([\d.]+)万辆')
        row['新能源销量_万辆'] = ext(r'新能源狭义乘用车销量([\d.]+)万辆')
        row['新能源渗透率%'] = ext(r'渗透率达([\d.]+)%')
        row['当年累计零售_万辆'] = ext(r'累计[销量达]*([\d.]+)万辆')
        
        data.append(row)
        if i % 10 == 0:
            pd.DataFrame(data).to_csv(SAVE, encoding='utf-8-sig', index=False)
    
    df = pd.DataFrame(data)
    df.to_csv(SAVE, encoding='utf-8-sig', index=False)
    print(f'\n完成！{len(data)} 条 -> {SAVE}')

if __name__ == '__main__':
    main()
