# -*- coding: utf-8 -*-
"""批量从 Open Library 拉热门英文书数据（书名/作者/简介/出版年）
用法：python fetch_ol_books.py
输出：data/processed/ol_books.csv
"""
import urllib.request, json, csv, sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROXY = urllib.request.ProxyHandler({'http': 'http://127.0.0.1:7897', 'https': 'http://127.0.0.1:7897'})
OPENER = urllib.request.build_opener(PROXY)
UA = {'User-Agent': 'Yuejian/1.0 (course project; contact: student@example.com)'}

# 热门分类，每个分类拉200本，按评分人数排序
SUBJECTS = [
    "fantasy", "mystery", "romance", "science_fiction",
    "history", "biography", "self_help", "business",
    "horror", "classics", "philosophy", "poetry",
    "science", "religion", "humor",
]

def ol_get(url, retries=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.loads(OPENER.open(req, timeout=20).read())
        except Exception as e:
            wait = 3 * (i + 1)
            print(f"    retry {i+1}/{retries} after {wait}s: {e}", flush=True)
            time.sleep(wait)

def search_subject(subject, limit=500):
    """按 subject 搜索，按评分人数降序"""
    url = (f"https://openlibrary.org/search.json?subject={subject}"
           f"&limit={limit}&fields=key,title,author_name,first_publish_year,"
           f"ratings_count,ratings_average,subject,isbn"
           f"&sort=rating")
    d = ol_get(url)
    return d.get('docs', [])

def get_works_desc(works_key):
    """拉 works detail 拿 description"""
    url = f"https://openlibrary.org{works_key}.json"
    d = ol_get(url)
    desc = d.get('description', '')
    if isinstance(desc, dict):
        desc = desc.get('value', '')
    return desc or ''

def main():
    # 1. 批量搜索各分类
    all_books = {}
    for subj in SUBJECTS:
        print(f"searching subject: {subj}...", flush=True)
        try:
            docs = search_subject(subj, limit=500)
            print(f"  got {len(docs)} docs", flush=True)
            for d in docs:
                key = d.get('key')
                if not key or key in all_books:
                    continue
                rc = d.get('ratings_count', 0) or 0
                if rc < 50:  # 过滤太冷门
                    continue
                isbns = d.get('isbn', [])
                all_books[key] = {
                    'key': key,
                    'title': d.get('title', ''),
                    'author': (d.get('author_name') or [''])[0],
                    'year': d.get('first_publish_year', 0) or 0,
                    'ratings_count': rc,
                    'rating_avg': d.get('ratings_average', 0) or 0,
                    'subject': subj,
                    'isbn': isbns[0] if isbns else '',
                }
        except Exception as e:
            print(f"  FAIL: {e}", flush=True)
        time.sleep(1)

    print(f"\n=== total candidates (rc>=50): {len(all_books)} ===", flush=True)

    # 2. 按评分人数排序，取前2000本拉简介
    sorted_books = sorted(all_books.values(), key=lambda x: -x['ratings_count'])
    TOP_N = 2000
    selected = sorted_books[:TOP_N]
    print(f"fetching descriptions for top {TOP_N}...", flush=True)

    rows = []
    consecutive_fails = 0
    for i, b in enumerate(selected):
        try:
            desc = get_works_desc(b['key'])
            consecutive_fails = 0
            time.sleep(1.0)  # 避免限流
        except Exception as e:
            desc = ''
            consecutive_fails += 1
            print(f"  [{i}] desc FAIL for {b['title']}: {e}", flush=True)
            if consecutive_fails >= 5:
                print("  too many consecutive fails, sleeping 15s...", flush=True)
                time.sleep(15)
                consecutive_fails = 0
        rows.append({
            'isbn': b['isbn'] or f"OL{b['key'].split('/')[-1]}",
            'title': b['title'],
            'author': b['author'],
            'year': b['year'],
            'rating': round(b['rating_avg'], 2) if b['rating_avg'] else 0,
            'rc': b['ratings_count'],
            'subject': b['subject'],
            'desc': desc,
        })
        if (i+1) % 50 == 0:
            print(f"  progress {i+1}/{TOP_N}, with_desc={sum(1 for r in rows if r['desc'])}", flush=True)

    # 3. 写 CSV
    out = "data/processed/ol_books.csv"
    os.makedirs("data/processed", exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=['isbn','title','author','year','rating','rc','subject','desc'])
        w.writeheader()
        w.writerows(rows)
    with_desc = sum(1 for r in rows if r['desc'])
    print(f"\nwritten {out}: {len(rows)} books, with_desc={with_desc}", flush=True)

if __name__ == "__main__":
    main()
