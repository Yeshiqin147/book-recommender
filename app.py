"""
书籍个性化推荐 - Streamlit 主程序（行为驱动版）
运行：streamlit run app.py

推荐机制：不靠"打分"，而是根据用户的
  搜索词、浏览/点击、停留时长 做粗糙个性化推荐（内容匹配 + 热度兜底）。
"""
import html
import time

import pandas as pd
import streamlit as st

from model import (
    load_books, load_catalog, load_catalog_with_popularity,
    popular_chinese_books, popular_books, recommend_implicit,
    CN_COVER_COLORS, recommend, mf_recommend,
)

st.set_page_config(page_title="书籍推荐小助手", page_icon="📚", layout="wide")

# ---------- 会话状态（行为足迹） ----------
if "behavior" not in st.session_state:
    st.session_state.behavior = {}   # {ISBN: {"clicks":int, "dwell":float, "ts":float}}
if "search_log" not in st.session_state:
    st.session_state.search_log = []   # 最近搜索词


def _now():
    return time.time()


def log_search(term):
    """记录搜索词（最近 10 个，去连续重复）"""
    term = (term or "").strip()
    if not term:
        return
    if not st.session_state.search_log or \
            st.session_state.search_log[-1].strip().lower() != term.lower():
        st.session_state.search_log.append(term)
        st.session_state.search_log = st.session_state.search_log[-10:]


def log_view(isbn):
    """记录一次浏览/点击：点击次数 +1，停留时长累计"""
    beh = st.session_state.behavior
    now = _now()
    if isbn in beh:
        beh[isbn]["clicks"] += 1
        beh[isbn]["dwell"] += min(max(now - beh[isbn]["ts"], 0), 300)
    else:
        beh[isbn] = {"clicks": 1, "dwell": 0.0}
    beh[isbn]["ts"] = now


# ---------- 卡片渲染 ----------
def cn_cover_html(row):
    color = CN_COVER_COLORS.get(row.get("Category", ""), "#5A5A7A")
    title = html.escape(row["Book-Title"])
    author = html.escape(str(row["Book-Author"]))
    cat = html.escape(str(row.get("Category", "")))
    return (
        f'<div style="width:100px;height:150px;background:{color};border-radius:6px;'
        f'color:#fff;display:flex;flex-direction:column;justify-content:center;'
        f'align-items:center;padding:10px;text-align:center;box-shadow:0 2px 8px '
        f'rgba(0,0,0,.25);font-family:\'Microsoft YaHei\',sans-serif;flex-shrink:0;">'
        f'<div style="font-size:12px;font-weight:bold;line-height:1.35;'
        f'word-break:break-all;">《{title}》</div>'
        f'<div style="font-size:10px;opacity:.9;margin-top:8px;">{author}</div>'
        f'<div style="font-size:8px;opacity:.75;margin-top:auto;background:rgba(255,255,255,.22);'
        f'border-radius:3px;padding:1px 6px;">{cat}</div></div>'
    )


def render_book_card(row, rank=None, browse_key=None):
    """渲染单本书卡片；browse_key 提供时附带"我在看这本"按钮（记录行为）"""
    col_img, col_info = st.columns([1, 3])
    with col_img:
        if row.get("is_chinese", False):
            st.markdown(cn_cover_html(row), unsafe_allow_html=True)
        else:
            st.image(row["cover"], width=100)
    with col_info:
        title = f"**《{row['Book-Title']}》**"
        if rank:
            title = f"**#{rank} {title}**"
        st.markdown(title)
        st.write(f"✍️ {row['Book-Author']} · {int(row['Year-Of-Publication'])}")
        st.write(f"🏛️ {row['Publisher']}")
        if row.get("is_chinese", False):
            st.write(
                f"⭐ 豆瓣 {row['douban_rating']:.1f} · "
                f"{int(row['rating_count']):,}人评分 · 分类：{row['Category']}"
            )
        elif "avg_rating" in row and pd.notna(row.get("avg_rating")):
            st.write(f"⭐ 平均 {row['avg_rating']:.1f}/10 · {int(row['n_ratings'])}人评分")
        if browse_key:
            if st.button("👁 我在看这本", key=f"browse_{browse_key}"):
                log_view(browse_key)
                st.rerun()


def show_interest_tags(catalog):
    """展示用户当前的兴趣标签（搜索词 + 浏览分类）"""
    tags = list(st.session_state.search_log[-5:])
    seen = set(tags)
    for isbn in st.session_state.behavior:
        r = catalog[catalog["ISBN"] == isbn]
        if r.empty:
            continue
        cat = r.iloc[0].get("Category", "")
        if cat and cat not in seen:
            tags.append(f"分类·{cat}")
            seen.add(f"分类·{cat}")
    if tags:
        st.caption("你的兴趣标签：" + "  /  ".join(tags[:8]))


# ---------- 侧边栏 ----------
with st.sidebar:
    st.header("🔍 找一本书（中英文都可搜）")
    catalog = load_catalog()
    books = load_books()

    keyword = st.text_input(
        "搜书名 / 作者 / 出版社",
        placeholder="例如：活着 / 三体 / Harry Potter",
    )
    log_search(keyword)

    def _search(df, kw):
        kw = kw.strip().lower()
        if not kw:
            return df
        return df[
            df["Book-Title"].astype(str).str.lower().str.contains(kw, na=False)
            | df["Book-Author"].astype(str).str.lower().str.contains(kw, na=False)
            | df["Publisher"].astype(str).str.lower().str.contains(kw, na=False)
        ]

    candidates = _search(catalog, keyword).head(100)

    if len(candidates) == 0:
        st.warning("没有找到匹配的书，换个关键词试试")
    else:
        lang_flag = lambda r: "🇨🇳" if r.get("is_chinese") else "📘"
        options = {f"—— 请选择一本书 ——": None}
        options.update({
            f"{lang_flag(row)} {row['Book-Title']} - {row['Book-Author']}": row["ISBN"]
            for _, row in candidates.iterrows()
        })
        selected_label = st.selectbox("选择一本书查看", list(options.keys()))
        selected_isbn = options[selected_label]
        if selected_isbn is None:
            st.caption("输入关键词搜索，再从列表里点开一本书，会自动记入足迹")
        else:
            log_view(selected_isbn)
            selected_book = catalog[catalog["ISBN"] == selected_isbn].iloc[0]
            col_i, col_t = st.columns([1, 2])
            with col_i:
                if selected_book.get("is_chinese", False):
                    st.markdown(cn_cover_html(selected_book), unsafe_allow_html=True)
                else:
                    st.image(selected_book["cover"], width=100)
            with col_t:
                st.write(f"**《{selected_book['Book-Title']}》**")
                st.write(f"✍️ {selected_book['Book-Author']} · {int(selected_book['Year-Of-Publication'])}")
                if selected_book.get("is_chinese", False):
                    st.write(
                        f"⭐ 豆瓣 {selected_book['douban_rating']:.1f} · "
                        f"{int(selected_book['rating_count']):,}人评分 · {selected_book['Category']}"
                    )
                st.caption("已记入你的浏览足迹 ✓")

    st.divider()
    st.subheader(f"📋 我的足迹（{len(st.session_state.behavior)} 本）")
    if st.session_state.behavior:
        for isbn, info in list(st.session_state.behavior.items()):
            r = catalog[catalog["ISBN"] == isbn]
            if r.empty:
                continue
            rr = r.iloc[0]
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(rr["Book-Title"])
            c2.write(f"{info['clicks']}次 · {info['dwell']:.0f}s")
            if c3.button("✕", key=f"rm_{isbn}"):
                del st.session_state.behavior[isbn]
                st.rerun()
    else:
        st.info("浏览或搜索一些书，我会据此为你推荐")

    if st.button("🧹 清空足迹"):
        st.session_state.behavior = {}
        st.session_state.search_log = []
        st.rerun()


# ---------- 主区 ----------
st.title("📚 书籍个性化推荐小助手")
st.caption(
    "不用打分 · 根据你的 搜索 / 浏览 / 点击 / 停留 自动推荐 · 支持中英文"
)

has_behavior = bool(st.session_state.behavior) or bool(st.session_state.search_log)

if has_behavior:
    st.subheader("🎯 为你推荐（基于你的行为）")
    show_interest_tags(catalog)
    recs = recommend_implicit(st.session_state.behavior, st.session_state.search_log, n=8)
    if len(recs) == 0:
        st.info("再浏览几本书，推荐会越来越准")
    else:
        for i, row in recs.iterrows():
            render_book_card(row, rank=i + 1, browse_key=row["ISBN"])
            st.divider()
else:
    st.subheader("🔥 大家都在读（点『我在看这本』表达兴趣，推荐会实时变化）")
    pop = popular_books(n=6)
    for i, row in pop.iterrows():
        render_book_card(row, browse_key=row["ISBN"])
        st.divider()

    st.subheader("🇨🇳 中文书目精选（真实豆瓣高分书）")
    st.caption("书目与评分为豆瓣读书公开数据 · 精选常用书目演示")
    cn_pop = popular_chinese_books(n=8)
    for i, row in cn_pop.iterrows():
        render_book_card(row, rank=i + 1, browse_key=row["ISBN"])
        st.divider()

# ---------- 算法实验（保留对比功能） ----------
with st.expander("📊 算法实验：SVD vs ItemCF（打分推荐对比）", expanded=False):
    st.markdown(
        "这里是**传统打分推荐**的对比实验，用于展示矩阵分解与协同过滤的效果。"
    )
    algo = st.radio(
        "推荐算法",
        ["矩阵分解 SVD（评分更准）", "物品协同过滤 ItemCF（召回更广）"],
        index=0, horizontal=True,
    )
    algo_key = "mf" if algo.startswith("矩阵分解") else "itemcf"

    en_books = books
    kw2 = st.text_input("🔍 搜英文书名/作者", placeholder="Harry Potter")
    cand2 = _search(en_books, kw2).head(100)
    if len(cand2) == 0:
        st.warning("没有匹配的英文书")
    else:
        opts2 = {f"{r['Book-Title']} - {r['Book-Author']}": r["ISBN"] for _, r in cand2.iterrows()}
        sel2 = st.selectbox("选择一本英文书打分", list(opts2.keys()), key="algo_select")
        isbn2 = opts2[sel2]
        rat = st.slider("评分", 1, 10, 8, key="algo_rating")
        if st.button("➕ 添加评分", key="algo_add"):
            st.session_state.setdefault("algo_ratings", {})[isbn2] = rat
            st.success("已记录")
        if st.session_state.get("algo_ratings"):
            st.write("已评：", {books[books['ISBN']==k]['Book-Title'].iloc[0]: v
                                for k, v in st.session_state["algo_ratings"].items()})
            if st.button("🎯 出推荐", key="algo_go"):
                recs2 = recommend(st.session_state["algo_ratings"], n=6) if algo_key == "itemcf" \
                    else mf_recommend(st.session_state["algo_ratings"], n=6)
                if len(recs2) == 0:
                    st.warning("数据不足")
                else:
                    for i, row in recs2.iterrows():
                        render_book_card(row, rank=i + 1)

    with st.expander("评估结论（RMSE / Recall / 覆盖率）", expanded=True):
        st.markdown(
            "| 指标 | 矩阵分解 SVD | 物品协同过滤 |\n"
            "|---|---|---|\n"
            "| RMSE（↓ 好） | **1.51** | 1.64 |\n"
            "| Recall@10（↑ 好） | 0.06 | **0.17** |\n"
            "| 覆盖率（↑ 好） | 0.58 | **0.71** |\n\n"
            "*`python evaluate.py` 可复现。*"
        )
