# -*- coding: utf-8 -*-
import json, io, sys, os, hashlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from cn_add import CN_ADD

DATA = 'books.json'
d = json.load(open(DATA, encoding='utf-8'))
books = d['books']

def key(b):
    return (b['title'].strip(), (b.get('author') or '').strip())

existing = {key(b) for b in books}

def pop_of(title):
    h = int(hashlib.md5(title.encode('utf-8')).hexdigest()[:8], 16)
    return round(0.5 + (h % 4500) / 10000, 4)  # 0.50 - 0.95

added, dup = 0, 0
seq = 1000
for title, author, year, subcat, length, rating, rc, desc in CN_ADD:
    k = (title.strip(), author.strip())
    if k in existing:
        dup += 1
        continue
    seq += 1
    books.append({
        'isbn': f'CNR{seq}',
        'title': title,
        'title_zh': '',
        'author': author,
        'year': year,
        'publisher': '中文言情',
        'lang': 'cn',
        'subcat': subcat,
        'length': length,
        'rating': rating,
        'rc': rc,
        'desc': desc,
        'pop': pop_of(title),
    })
    existing.add(k)
    added += 1

en = sum(1 for b in books if b['lang'] == 'en')
cn = sum(1 for b in books if b['lang'] == 'cn')
with_desc = sum(1 for b in books if (b.get('desc') or '').strip())
d['meta'] = {'total': len(books), 'en': en, 'cn': cn, 'with_desc': with_desc}

json.dump(d, open(DATA, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(f'added={added} dup={dup} total={len(books)} en={en} cn={cn} with_desc={with_desc}')
# 中文分类分布
from collections import Counter
cc = Counter(b['subcat'] for b in books if b['lang'] == 'cn')
print('cn subcat:', dict(cc))
