# -*- coding: utf-8 -*-
"""第三轮：专攻言情小说细分分类"""
import urllib.request, json, csv, sys, io, time, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROXY = urllib.request.ProxyHandler({'http': 'http://127.0.0.1:7897', 'https': 'http://127.0.0.1:7897'})
OPENER = urllib.request.build_opener(PROXY)
UA = {'User-Agent': 'Yuejian/1.0 (course project)'}

SUBJECTS = [
    "contemporary_romance", "historical_romance", "paranormal_romance",
    "regency_romance", "romantic_suspense", "romantic_comedy",
    "love_stories", "chick_lit", "urban_fantasy_romance",
    "romance_novels", "romance_authors", "victorian_romance",
    "medieval_romance", "western_romance", "sports_romance",
    "billionaire_romance", "vampire_romance", "werewolf_romance",
    "time_travel_romance", "friends_to_lovers", "enemies_to_lovers",
    "second_chance_romance", "fake_relationship_romance",
    "small_town_romance", "royal_romance", "mafia_romance",
]

def ol_get(url, retries=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.loads(OPENER.open(req, timeout=20).read())
        except Exception as e:
            wait = 3 * (i + 1)
            print(f"    retry {i+1}/{retries}: {e}", flush=True)
            time.sleep(wait)

def search_subject(subject, limit=500):
    url = (f"https://openlibrary.org/search.json?subject={subject}"
           f"&limit={limit}&fields=key,title,author_name,first_publish_year,"
           f"ratings_count,ratings_average,subject,isbn"
           f"&sort=rating")
    d = ol_get(url)
    return d.get('docs', [])

def get_works_desc(works_key):
    url = f"https://openlibrary.org{works_key}.json"
    d = ol_get(url)
    desc = d.get('description', '')
    if isinstance(desc, dict):
        desc = desc.get('value', '')
    return desc or ''

def main():
    existing_isbns = set()
    for f in ["data/processed/ol_books.csv", "data/processed/ol_books2.csv"]:
        if os.path.exists(f):
            with open(f, encoding='utf-8-sig') as fp:
                for row in csv.DictReader(fp):
                    existing_isbns.add(row.get('isbn',''))

    all_books = {}
    for subj in SUBJECTS:
        print(f"searching: {subj}...", flush=True)
        try:
            docs = search_subject(subj, limit=500)
            print(f"  got {len(docs)} docs", flush=True)
            for d in docs:
                key = d.get('key')
                if not key: continue
                rc = d.get('ratings_count', 0) or 0
                if rc < 20: continue
                isbns = d.get('isbn', [])
                isbn = isbns[0] if isbns else ''
                if isbn and isbn in existing_isbns: continue
                if key in all_books: continue
                all_books[key] = {
                    'key': key, 'title': d.get('title', ''),
                    'author': (d.get('author_name') or [''])[0],
                    'year': d.get('first_publish_year', 0) or 0,
                    'ratings_count': rc,
                    'rating_avg': d.get('ratings_average', 0) or 0,
                    'subject': subj, 'isbn': isbn,
                }
        except Exception as e:
            print(f"  FAIL: {e}", flush=True)
        time.sleep(1)

    print(f"\n=== new romance candidates: {len(all_books)} ===", flush=True)
    sorted_books = sorted(all_books.values(), key=lambda x: -x['ratings_count'])
    TOP_N = min(len(sorted_books), 2000)
    selected = sorted_books[:TOP_N]
    print(f"fetching descriptions for top {TOP_N}...", flush=True)

    rows = []
    fails = 0
    for i, b in enumerate(selected):
        try:
            desc = get_works_desc(b['key'])
            fails = 0
            time.sleep(0.6)
        except:
            desc = ''
            fails += 1
            if fails >= 5:
                print("  sleep 15s...", flush=True)
                time.sleep(15)
                fails = 0
        rows.append({
            'isbn': b['isbn'] or f"OL{b['key'].split('/')[-1]}",
            'title': b['title'], 'author': b['author'],
            'year': b['year'],
            'rating': round(b['rating_avg'], 2) if b['rating_avg'] else 0,
            'rc': b['ratings_count'], 'subject': b['subject'], 'desc': desc,
        })
        if (i+1) % 100 == 0:
            print(f"  progress {i+1}/{TOP_N}, with_desc={sum(1 for r in rows if r['desc'])}", flush=True)

    out = "data/processed/ol_romance.csv"
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=['isbn','title','author','year','rating','rc','subject','desc'])
        w.writeheader()
        w.writerows(rows)
    with_desc = sum(1 for r in rows if r['desc'])
    print(f"\nwritten {out}: {len(rows)} books, with_desc={with_desc}", flush=True)

if __name__ == "__main__":
    main()
