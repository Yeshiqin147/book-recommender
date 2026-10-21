"""
书籍推荐 - Streamlit 主程序
运行：streamlit run app.py

推荐机制（内部）：根据你的搜索、浏览记录做个性化推荐。
页面侧只呈现"为你推荐"，不暴露内部算法。
"""
import html
import time
import zlib

import pandas as pd
import streamlit as st

from model import (
    load_catalog, popular_chinese_books, popular_books,
    recommend_implicit, CN_COVER_COLORS,
)

st.set_page_config(page_title="书籍推荐", page_icon="📚", layout="wide")

# ---------- 会话状态（浏览记录） ----------
if "behavior" not in st.session_state:
    st.session_state.behavior = {}   # {ISBN: {"clicks", "dwell", "ts"}}
if "search_log" not in st.session_state:
    st.session_state.search_log = []


def _now():
    return time.time()


def log_search(term):
    term = (term or "").strip()
    if not term:
        return
    if not st.session_state.search_log or \
            st.session_state.search_log[-1].strip().lower() != term.lower():
        st.session_state.search_log.append(term)
        st.session_state.search_log = st.session_state.search_log[-10:]


def log_view(isbn):
    beh = st.session_state.behavior
    now = _now()
    if isbn in beh:
        beh[isbn]["clicks"] += 1
        beh[isbn]["dwell"] += min(max(now - beh[isbn]["ts"], 0), 300)
    else:
        beh[isbn] = {"clicks": 1, "dwell": 0.0}
    beh[isbn]["ts"] = now


# ---------- 封面（本地生成，不依赖外网，任何电脑都能显示） ----------
EN_COVER_COLORS = [
    "#2E86AB", "#B23A48", "#3A7D44", "#9C6644", "#5D576B",
    "#2C7DA0", "#8A5A44", "#6D597A", "#4E8098", "#B08D57",
]


def cover_html(row, width=110, height=165):
    if row.get("is_chinese", False):
        color = CN_COVER_COLORS.get(str(row.get("Category", "")), "#5A5A7A")
        chip = "🇨🇳 " + str(row.get("Category", ""))
    else:
        color = EN_COVER_COLORS[zlib.crc32(str(row["ISBN"]).encode()) % len(EN_COVER_COLORS)]
        chip = "EN"
    title = html.escape(str(row["Book-Title"]))
    author = html.escape(str(row["Book-Author"]))
    fs = 12 if width >= 110 else 11
    return (
        f'<div style="width:{width}px;height:{height}px;border-radius:8px;flex-shrink:0;'
        f'background:linear-gradient(150deg,{color} 0%,{color}cc 100%);color:#fff;'
        f'display:flex;flex-direction:column;align-items:center;padding:10px;text-align:center;'
        f'box-shadow:2px 3px 10px rgba(0,0,0,.30);'
        f'font-family:\'Microsoft YaHei\',sans-serif;">'
        f'<div style="font-size:9px;opacity:.85;background:rgba(255,255,255,.22);'
        f'border-radius:3px;padding:1px 7px;max-width:100%;overflow:hidden;'
        f'white-space:nowrap;text-overflow:ellipsis;">{chip}</div>'
        f'<div style="flex:1;display:flex;flex-direction:column;justify-content:center;">'
        f'<div style="font-size:{fs}px;font-weight:bold;line-height:1.3;'
        f'word-break:break-all;">《{title}》</div></div>'
        f'<div style="font-size:9px;opacity:.9;max-width:100%;overflow:hidden;'
        f'white-space:nowrap;text-overflow:ellipsis;">{author}</div></div>'
    )


# ---------- 图书详情弹窗 ----------
@st.dialog("📖 图书详情", width="large")
def show_book_detail(row):
    col_i, col_t = st.columns([1, 2])
    with col_i:
        st.markdown(cover_html(row, width=140, height=210), unsafe_allow_html=True)
    with col_t:
        st.markdown(f"### 《{row['Book-Title']}》")
        st.write(f"**作者**：{row['Book-Author']}")
        st.write(f"**出版社**：{row['Publisher']}（{int(row['Year-Of-Publication'])}）")
        if row.get("is_chinese", False):
            st.write(f"**豆瓣评分**：⭐ {row['douban_rating']:.1f} · "
                     f"{int(row['rating_count']):,} 人评分")
            st.write(f"**分类**：{row['Category']}")
        st.write(f"**ISBN**：{row['ISBN']}")
    st.divider()
    desc = row.get("description") if "description" in row else ""
    if isinstance(desc, str) and desc.strip():
        st.markdown("**内容简介**")
        st.write(desc)
    else:
        st.caption("（本书暂无内容简介）")


# ---------- 卡片 ----------
def render_book_card(row, rank=None):
    col_img, col_info = st.columns([1, 3.4])
    with col_img:
        st.markdown(cover_html(row), unsafe_allow_html=True)
    with col_info:
        head = f"**#{rank} 《{row['Book-Title']}》**" if rank else f"**《{row['Book-Title']}》**"
        st.markdown(head)
        st.write(f"✍️ {row['Book-Author']} · {int(row['Year-Of-Publication'])}")
        st.write(f"🏛️ {row['Publisher']}")
        if row.get("is_chinese", False):
            st.write(f"⭐ 豆瓣 {row['douban_rating']:.1f} · {int(row['rating_count']):,} 人评分")
        elif "avg_rating" in row and pd.notna(row.get("avg_rating")):
            st.write(f"⭐ 读者平均 {row['avg_rating']:.1f}/10 · {int(row['n_ratings'])} 人评分")
        desc = row.get("description") if "description" in row else ""
        if isinstance(desc, str) and desc.strip():
            short = desc if len(desc) <= 64 else desc[:64] + "…"
            st.caption(short)
        if st.button("📖 查看详情", key=f"detail_{row['ISBN']}", use_container_width=True):
            log_view(row["ISBN"])
            show_book_detail(row)


# ---------- 侧边栏 ----------
with st.sidebar:
    st.header("🔍 找一本书（中英文都可搜）")
    catalog = load_catalog()

    keyword = st.text_input(
        "搜书名 / 作者 / 出版社",
        placeholder="例如：活着 / 三体 / Harry",
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
        flag = lambda r: "🇨🇳" if r.get("is_chinese") else "📘"
        options = {"—— 请选择一本书 ——": None}
        options.update({
            f"{flag(row)} {row['Book-Title']} - {row['Book-Author']}": row["ISBN"]
            for _, row in candidates.iterrows()
        })
        selected_label = st.selectbox("选择一本书查看", list(options.keys()))
        selected_isbn = options[selected_label]
        if selected_isbn is None:
            st.caption("输入关键词搜索，从列表点开一本书，可看详情并自动加入浏览记录")
        else:
            log_view(selected_isbn)
            row = catalog[catalog["ISBN"] == selected_isbn].iloc[0]
            col_i, col_t = st.columns([1, 2])
            with col_i:
                st.markdown(cover_html(row, width=100, height=150), unsafe_allow_html=True)
            with col_t:
                st.write(f"**《{row['Book-Title']}》**")
                st.write(f"{row['Book-Author']} · {int(row['Year-Of-Publication'])}")
                if row.get("is_chinese", False):
                    st.caption(f"⭐ 豆瓣 {row['douban_rating']:.1f} · {row['Category']}")
                st.caption("已加入浏览记录 ✓")

    st.divider()
    st.subheader("📚 你的浏览记录")
    if st.session_state.behavior:
        for isbn, _info in list(st.session_state.behavior.items()):
            r = catalog[catalog["ISBN"] == isbn]
            if r.empty:
                continue
            rr = r.iloc[0]
            c1, c2 = st.columns([4, 1])
            c1.write(rr["Book-Title"])
            if c2.button("✕", key=f"rm_{isbn}"):
                del st.session_state.behavior[isbn]
                st.rerun()
    else:
        st.info("点开书的『查看详情』，会自动加入浏览记录")
    if st.button("🧹 清空浏览记录"):
        st.session_state.behavior = {}
        st.session_state.search_log = []
        st.rerun()


# ---------- 主区 ----------
st.title("📚 书籍推荐")
st.caption("根据你的浏览自动推荐你喜欢的书 · 支持中英文书目")

has_behavior = bool(st.session_state.behavior) or bool(st.session_state.search_log)

if has_behavior:
    st.subheader("🎯 为你推荐")
    st.caption("根据你搜过和浏览过的书，为你挑选可能喜欢的书")
    recs = recommend_implicit(st.session_state.behavior, st.session_state.search_log, n=8)
    if len(recs) == 0:
        st.info("再点开几本书，推荐会更准")
    else:
        for i, row in recs.iterrows():
            render_book_card(row, rank=i + 1)
            st.divider()
else:
    st.subheader("🔥 大家都在读")
    for _, row in popular_books(n=6).iterrows():
        render_book_card(row)
        st.divider()

    st.subheader("🇨🇳 中文书目精选")
    st.caption("真实豆瓣高分书，点开即可查看详情")
    for i, row in popular_chinese_books(n=8).iterrows():
        render_book_card(row, rank=i + 1)
        st.divider()
