# -*- coding: utf-8 -*-
"""把 中英文书目 + 简介 + 聚合评分/热度 打包为 PWA 前端用的 books.json
用法：python build_pwa_data.py
"""
import json
import math
from pathlib import Path

import pandas as pd

from pwa_titles_zh import EN_TITLE_ZH, norm_en_title

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "processed"
OUT = ROOT / "pwa" / "books.json"


def infer_tags(title, title_zh, desc, category):
    """根据书名/中文译名/简介推断 内容分类 category、风格 style、篇幅 length。
    中文书已有 category 时保留；英文书与风格/篇幅均为关键词粗推断（仅用于筛选）。"""
    text = (str(title) + " " + str(title_zh) + " " + str(desc)).lower()

    # ---- 内容分类 ----
    if category:
        cat = category
    elif any(k in text for k in ["sci-fi", "science fiction", "dystopian", "space",
                                  "robot", "futur", "alien", "time travel", "科幻"]):
        cat = "科幻"
    elif any(k in text for k in ["history", "historical", "war", "wwii", "world war",
                                  "medieval", "ancient", "历史", "战争"]):
        cat = "历史"
    elif any(k in text for k in ["psycholog", "mind", "emotion", "心理"]):
        cat = "心理"
    elif any(k in text for k in ["business", "management", "econom", "marketing",
                                  "money", "商业", "经济", "管理"]):
        cat = "商业"
    elif any(k in text for k in ["science", "nature", "physics", "biolog", "math",
                                  "scientist", "科学", "自然"]):
        cat = "科普"
    elif any(k in text for k in ["children", "young adult", "picture book", "fairy",
                                  "picture", "童", "童话"]):
        cat = "童书"
    elif any(k in text for k in ["philosoph", "ethic", "moral", "哲学"]):
        cat = "哲学"
    else:
        cat = "文学"

    # ---- 风格标签 ----
    if any(k in text for k in ["mystery", "thriller", "detective", "crime", "murder",
                                "suspense", "悬疑", "侦探", "推理", "谋杀"]):
        style = "悬疑"
    elif any(k in text for k in ["fantasy", "magic", "wizard", "dragon", "vampire",
                                  "supernatural", "奇幻", "魔法"]):
        style = "奇幻"
    elif any(k in text for k in ["romance", "love story", "lover", "恋", "爱情"]):
        style = "爱情"
    elif any(k in text for k in ["horror", "ghost", "zombie", "恐怖", "鬼"]):
        style = "恐怖"
    elif any(k in text for k in ["biography", "memoir", "autobiography", "self portrait",
                                  "自传", "回忆录"]):
        style = "传记"
    elif any(k in text for k in ["self-help", "inspirational", "motivational", "self help",
                                  "励志", "成功", "修养"]):
        style = "励志"
    elif cat == "科幻":
        style = "科幻"
    elif cat == "童书":
        style = "治愈"
    else:
        style = "小说"

    # ---- 篇幅（粗分，非真实字数） ----
    if cat == "童书" or any(k in text for k in ["picture book", "poetry", "anthology",
                                                "绘本", "诗集", "短篇"]):
        length = "短篇"
    elif cat in ("商业", "心理", "哲学", "科普"):
        length = "中篇"
    else:
        length = "长篇"

    return cat, style, length


def main():
    en = pd.read_csv(DATA / "books.csv", dtype={"ISBN": str})
    cn = pd.read_csv(DATA / "chinese_books.csv", encoding="utf-8", dtype={"ISBN": str})
    desc = pd.read_csv(DATA / "en_descriptions.csv", encoding="utf-8", dtype={"ISBN": str})
    desc = desc.drop_duplicates(subset=["ISBN"], keep="last")
    ratings = pd.read_csv(DATA / "ratings.csv", dtype={"ISBN": str})

    # 英文书：从评分聚合 平均分/评分人数/热度
    agg = ratings.groupby("ISBN").agg(n=("Book-Rating", "count"),
                                      avg=("Book-Rating", "mean")).reset_index()
    en = en.merge(agg, on="ISBN", how="left")

    records = []
    for _, r in en.iterrows():
        isbn = str(r["ISBN"])
        n = float(r["n"]) if pd.notna(r["n"]) else 0.0
        avg = float(r["avg"]) if pd.notna(r["avg"]) else 0.0
        pop = avg * math.log1p(n) if n > 0 else 0.0
        d = desc.loc[desc["ISBN"] == isbn, "description"]
        description = (d.iloc[0] if len(d) and isinstance(d.iloc[0], str) else "") or ""
        t_zh = EN_TITLE_ZH.get(norm_en_title(r["Book-Title"]), "")
        cat, style, length = infer_tags(r["Book-Title"], t_zh, description, "")
        records.append({
            "isbn": isbn, "title": str(r["Book-Title"]), "title_zh": t_zh,
            "author": str(r["Book-Author"]),
            "year": int(r["Year-Of-Publication"]) if pd.notna(r["Year-Of-Publication"]) else 0,
            "publisher": str(r["Publisher"]), "lang": "en", "category": cat,
            "style": style, "length": length,
            "rating": round(avg, 2), "rc": int(n), "desc": description.strip(), "pop": pop,
        })

    max_pop_en = max((x["pop"] for x in records), default=0.0)
    for x in records:
        x["pop_en"] = x["pop"]

    cn_records = []
    for _, r in cn.iterrows():
        rb = float(r["douban_rating"]) if pd.notna(r["douban_rating"]) else 0.0
        rc = float(r["rating_count"]) if pd.notna(r["rating_count"]) else 0.0
        pop = rb * math.log1p(rc) if rc > 0 else 0.0
        description = (r["description"] if isinstance(r["description"], str) else "") or ""
        cat, style, length = infer_tags(r["Book-Title"], "", description, str(r["Category"]))
        cn_records.append({
            "isbn": str(r["ISBN"]), "title": str(r["Book-Title"]), "title_zh": "",
            "author": str(r["Book-Author"]),
            "year": int(r["Year-Of-Publication"]) if pd.notna(r["Year-Of-Publication"]) else 0,
            "publisher": str(r["Publisher"]), "lang": "cn", "category": cat,
            "style": style, "length": length,
            "rating": round(rb, 2), "rc": int(rc), "desc": description.strip(), "pop": pop,
        })

    max_pop_cn = max((x["pop"] for x in cn_records), default=0.0)
    max_pop = max(max_pop_en, max_pop_cn)
    for x in records:
        x["pop"] = round(x["pop"] / max_pop, 4) if max_pop > 0 else 0.0
    for x in cn_records:
        x["pop"] = round(x["pop"] / max_pop, 4) if max_pop > 0 else 0.0

    payload = {
        "books": records + cn_records,
        "meta": {"total": len(records) + len(cn_records),
                 "en": len(records), "cn": len(cn_records),
                 "with_desc": sum(1 for x in records + cn_records if x["desc"])},
    }
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"written {OUT} total={payload['meta']['total']} en={payload['meta']['en']} "
          f"cn={payload['meta']['cn']} with_desc={payload['meta']['with_desc']}")


if __name__ == "__main__":
    main()
