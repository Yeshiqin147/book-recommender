# -*- coding: utf-8 -*-
"""
拉取英文书内容简介：Wikipedia 摘要（真实公开数据）。
- 清理标题杂质（括号/后缀）→ 搜索标题+作者 → 取最匹配词条 → 拉摘要
- 结果三态：ok(有简介) / no(确实无公开简介) / retry(限流或网络失败，不写入，重跑补)
- 写入 data/processed/en_descriptions.csv（ISBN, description），断点续传
用法：python fetch_en_descriptions.py
"""
import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data" / "processed"
books_csv = DATA / "books.csv"
out_csv = DATA / "en_descriptions.csv"

PROXY = os.environ.get("FETCH_PROXY") or os.environ.get("https_proxy") \
    or os.environ.get("http_proxy") or "http://127.0.0.1:7897"
UA = "BookRecommend/1.0 (educational project; doubao agent)"
_opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
)

STOP = set(("the a an of and or to in on for with by at from is was are as it its "
            "this that s d t novel paperback hardcover bestseller book club").split())


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    return _opener.open(req, timeout=15).read().decode("utf-8", "ignore")


def _tokens(s: str):
    return set(w for w in re.split(r"[^A-Za-z0-9]+", (s or "").lower()) if w and w not in STOP)


def clean_title(t: str) -> str:
    t = re.sub(r"\([^)]*\)", " ", t)          # 去掉括号内容 (Paperback) 等
    t = re.split(r"[:\-]", t)[0]               # 从冒号/短横处截断
    t = re.sub(r"\[\w*\]", " ", t)
    t = re.sub(r"\b(an?|the) (novel|book|story|tale)\b", " ", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


def _search(title: str, author: str):
    q = urllib.parse.quote(f'"{title}" {author}')
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&srlimit=5&format=json"
    try:
        d = json.loads(_get(url))
        return d.get("query", {}).get("search", []) or []
    except Exception:
        return None


def _best_page(hits, title: str):
    tt = _tokens(title)
    if not tt:
        return None
    best, best_score = None, 0
    for h in hits:
        inter = len(tt & _tokens(h.get("title", "")))
        if inter > best_score:
            best, best_score = h["title"], inter
    return best if best_score >= 1 else None


def _summary(page_title: str):
    pt = urllib.parse.quote(page_title.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{pt}"
    try:
        d = json.loads(_get(url))
        e = d.get("extract", "")
        if isinstance(e, str) and e.strip():
            return e.strip()[:2000]
        return ""
    except Exception:
        return None


def fetch_book(title: str, author: str):
    """返回 ('ok', 简介) / ('no','') / ('retry','')"""
    ct = clean_title(title)
    hits = _search(ct, author)
    if hits is None:
        return ("retry", "")
    page = _best_page(hits, ct)
    if not page:
        return ("no", "")
    txt = _summary(page)
    if txt is None:
        return ("retry", "")
    if txt:
        return ("ok", txt)
    return ("no", "")


def main():
    books = pd.read_csv(books_csv)
    done = {}
    if out_csv.exists():
        prev = pd.read_csv(out_csv, encoding="utf-8")
        # 只把“有简介”的算 done；空简介的重新拉（更好的匹配会补上）
        done = {str(i): d for i, d in zip(prev["ISBN"], prev["description"])}
        nonempty = {k for k, v in done.items() if isinstance(v, str) and v.strip()}
    else:
        nonempty = set()

    rows = books[~books["ISBN"].astype(str).isin(nonempty)]
    print(f"total={len(books)} done={len(nonempty)} remaining={len(rows)}", flush=True)

    new_file = not out_csv.exists()
    f = open(out_csv, "a", newline="", encoding="utf-8")
    w = csv.writer(f)
    if new_file:
        w.writerow(["ISBN", "description"])

    ok = no = retry = 0
    for n, (_, r) in enumerate(rows.iterrows(), 1):
        isbn = str(r["ISBN"])
        status, desc = fetch_book(str(r["Book-Title"]), str(r["Book-Author"]))
        if status == "retry":
            retry += 1
            continue
        w.writerow([isbn, desc])
        f.flush()
        if status == "ok":
            ok += 1
        else:
            no += 1
        if n % 25 == 0 or n == len(rows):
            print(f"[{time.strftime('%H:%M:%S')}] {n}/{len(rows)} ok={ok} no={no} retry={retry}", flush=True)
        time.sleep(0.5)
    f.close()
    print(f"DONE ok={ok} no={no} retry={retry} (retry 未写，可重跑)", flush=True)


if __name__ == "__main__":
    main()
