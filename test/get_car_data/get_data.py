import requests
import time
import re
import pandas as pd
from bs4 import BeautifulSoup

# ===================== 配置区 =====================
BASE_LIST_URL = "https://www.cpcaauto.com/news.php?types=csjd&page={page}"
DETAIL_URL_TPL = "https://www.cpcaauto.com/newslist.php?types=csjd&id={anid}"
START_YEAR = 2016
END_YEAR = 2026
SAVE_CSV = "乘联会2016-2026月度销量数据.csv"
PAGE_DELAY = 2.5
DETAIL_DELAY = 3.0
MAX_RETRY = 2

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.cpcaauto.com/",
    "Origin": "https://www.cpcaauto.com",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
}
session = requests.Session()
# ==================================================

def get_html(url, delay=1, retry=0):
    time.sleep(delay)
    try:
        resp = session.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        if retry < MAX_RETRY:
            print(f"请求失败 {url}，重试{retry+1}次: {str(e)}")
            time.sleep(1)
            return get_html(url, delay+1, retry+1)
        else:
            print(f"多次请求失败，跳过 {url}")
            return None

def fetch_all_month_links():
    print("访问首页初始化Cookie...")
    get_html("https://www.cpcaauto.com/", delay=2)
    all_links = []
    page = 1
    while True:
        print(f"正在抓取列表第{page}页")
        soup = get_html(BASE_LIST_URL.format(page=page), delay=PAGE_DELAY)
        if not soup:
            break
        # 只提取带 anid 新闻链接
        a_tags = soup.select('a[href*="anid="]')
        if not a_tags:
            print("当前页无新闻链接，翻页终止")
            break

        page_has_data = False
        for a in a_tags:
            title = a.get_text(strip=True)
            href = a["href"]

            # 只保留月度排名快报
            if "【月度排名】" not in title:
                continue

            # 从标题提取年月 例：【月度排名】2026年6月厂商销量排名快报
            date_match = re.search(r"(\d{4})年(\d{1,2})月", title)
            if not date_match:
                continue
            year = int(date_match.group(1))
            month = int(date_match.group(2))
            if not (START_YEAR <= year <= END_YEAR):
                continue

            # 关键修复：列表页链接是 anid，不是 nid
            anid_match = re.search(r"anid=(\d+)", href)
            if not anid_match:
                continue
            anid = anid_match.group(1)

            item = {
                "year": year,
                "month": month,
                "date_str": f"{year}-{month:02d}",
                "title": title,
                "anid": anid,
                "detail_url": DETAIL_URL_TPL.format(anid=anid)
            }
            all_links.append(item)
            page_has_data = True

        # 连续3页没有月度数据才停止，避免提前退出
        if not page_has_data:
            if page > 3:
                print("连续多页无月度快报，停止翻页")
                break
        page += 1

    all_links.sort(key=lambda x: (x["year"], x["month"]))
    print(f"列表采集完毕，共获取 {len(all_links)} 份月度报告")
    return all_links

def parse_detail_page(item):
    soup = get_html(item["detail_url"], delay=DETAIL_DELAY)
    if not soup:
        return None
    full_text = soup.get_text(" ", strip=True)
    row = {
        "date": item["date_str"],
        "year": item["year"],
        "month": item["month"],
        "title": item["title"],
        "url": item["detail_url"]
    }
    # 狭义零售总量
    ret_total = re.search(r"零售销量达([\d\.]+)万辆", full_text)
    row["零售总量_万辆"] = float(ret_total.group(1)) if ret_total else None
    # 同比正负
    yoy_up = re.search(r"同比增长([\d\.]+)%", full_text)
    yoy_down = re.search(r"同比下降([\d\.]+)%", full_text)
    if yoy_up:
        row["零售同比%"] = float(yoy_up.group(1))
    elif yoy_down:
        row["零售同比%"] = -float(yoy_down.group(1))
    else:
        row["零售同比%"] = None
    # 环比正负
    mom_up = re.search(r"环比增长([\d\.]+)%", full_text)
    mom_down = re.search(r"环比下降([\d\.]+)%", full_text)
    if mom_up:
        row["零售环比%"] = float(mom_up.group(1))
    elif mom_down:
        row["零售环比%"] = -float(mom_down.group(1))
    else:
        row["零售环比%"] = None
    # 分车型
    car = re.search(r"轿车销量([\d\.]+)万辆", full_text)
    suv = re.search(r"SUV销量([\d\.]+)万辆", full_text)
    mpv = re.search(r"MPV销量([\d\.]+)万辆", full_text)
    row["轿车_万辆"] = float(car.group(1)) if car else None
    row["SUV_万辆"] = float(suv.group(1)) if suv else None
    row["MPV_万辆"] = float(mpv.group(1)) if mpv else None
    # 新能源
    new_energy = re.search(r"新能源狭义乘用车销量([\d\.]+)万辆", full_text)
    pen = re.search(r"渗透率达([\d\.]+)%", full_text)
    row["新能源销量_万辆"] = float(new_energy.group(1)) if new_energy else None
    row["新能源渗透率%"] = float(pen.group(1)) if pen else None
    # 累计零售
    cum = re.search(r"1-(\d+)月累计销量([\d\.]+)万辆", full_text)
    row["当年累计零售_万辆"] = float(cum.group(2)) if cum else None
    return row

def main():
    link_list = fetch_all_month_links()
    if len(link_list) == 0:
        print("未抓到任何月度数据链接，程序退出")
        return
    data_result = []
    for idx, item in enumerate(link_list, start=1):
        print(f"[{idx}/{len(link_list)}] 解析 {item['date_str']} {item['title']}")
        line = parse_detail_page(item)
        if line:
            data_result.append(line)
        if idx % 10 == 0:
            pd.DataFrame(data_result).to_csv(SAVE_CSV, encoding="utf-8-sig", index=False)
            print(f"断点已保存至 {SAVE_CSV}")
    df = pd.DataFrame(data_result)
    df.to_csv(SAVE_CSV, encoding="utf-8-sig", index=False)
    print(f"\n===== 爬取完成 =====")
    print(f"成功解析 {len(data_result)} 个月数据")
    print(f"文件输出：{SAVE_CSV}")
    print(df.head())

if __name__ == "__main__":
    main()