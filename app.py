"""
书籍个性化推荐 - Streamlit 主程序
运行：streamlit run app.py
"""
import html
import pandas as pd
import streamlit as st

from model import (
    load_books, load_chinese_books, load_catalog, popular_chinese_books,
    CN_COVER_COLORS, popular_books, recommend, mf_recommend,
)

st.set_page_config(page_title="书籍推荐小助手", page_icon="📚", layout="wide")

if "my_ratings" not in st.session_state:
    st.session_state.my_ratings = {}


def cn_cover_html(row):
    """为中文书生成一张样式书封（按分类配色）"""
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


def render_book_card(row, rank=None):
    """渲染单本书的卡片：左封面 + 右信息"""
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


# ---------- 侧边栏 ----------
with st.sidebar:
    algo = st.radio(
        "🔀 推荐算法",
        ["矩阵分解 SVD（评分更准）", "物品协同过滤 ItemCF（召回更广）"],
        index=0,
        help="SVD 预测评分更准；ItemCF 找回你喜欢的书、覆盖更广",
    )
    algo_key = "mf" if algo.startswith("矩阵分解") else "itemcf"

    st.header("✍️ 给你看过的书打分")
    books = load_books()

    keyword = st.text_input("🔍 搜书名/作者", placeholder="例如：Harry Potter")

    candidates = books
    if keyword:
        kw = keyword.lower()
        mask = (
            books["Book-Title"].str.lower().str.contains(kw, na=False)
            | books["Book-Author"].str.lower().str.contains(kw, na=False)
        )
        candidates = books[mask].head(100)

    if len(candidates) == 0:
        st.warning("没有找到匹配的书，换个关键词试试")
        selected_book = None
    else:
        options = {
            f"{row['Book-Title']} - {row['Book-Author']}": row["ISBN"]
            for _, row in candidates.iterrows()
        }
        selected_label = st.selectbox("选择一本书", list(options.keys()))
        selected_isbn = options[selected_label]
        selected_book = books[books["ISBN"] == selected_isbn].iloc[0]

        rating = st.slider("你给这本书打几分？", 1, 10, 8)

        if st.button("➕ 添加我的评分", use_container_width=True):
            st.session_state.my_ratings[selected_isbn] = rating
            st.success(f"已记录：《{selected_book['Book-Title']}》 {rating}分")

    st.divider()
    st.subheader(f"📖 我已评过 {len(st.session_state.my_ratings)} 本书")
    if st.session_state.my_ratings:
        for isbn, r in list(st.session_state.my_ratings.items()):
            row = books[books["ISBN"] == isbn].iloc[0]
            col1, col2 = st.columns([4, 1])
            col1.write(f"《{row['Book-Title']}》 - {r}分")
            if col2.button("❌", key=f"del_{isbn}"):
                del st.session_state.my_ratings[isbn]
                st.rerun()
    else:
        st.info("先打 3-5 本书的分，再点下方按钮拿推荐")

    if st.button("🎯 获取我的专属推荐", type="primary", use_container_width=True):
        if len(st.session_state.my_ratings) < 1:
            st.warning("至少打 1 本书的分才能推荐哦")


# ---------- 主区 ----------
st.title("📚 书籍个性化推荐小助手")
st.caption("基于 Book-Crossing 数据集 · 支持 物品协同过滤（ItemCF）与 矩阵分解（SVD） 两种算法")

with st.expander("🧪 两种算法怎么选？评估结论在这里", expanded=False):
    st.markdown(
        "**评估口径**：评分 8:2 切分；RMSE 衡量评分预测误差，Recall@10 衡量能否找回用户真正喜欢的书。\n\n"
        "| 指标 | 矩阵分解 SVD | 物品协同过滤 |\n"
        "|---|---|---|\n"
        "| RMSE（↓ 好） | **1.51** | 1.64 |\n"
        "| Recall@10（↑ 好） | 0.06 | **0.17** |\n"
        "| 覆盖率（↑ 好） | 0.58 | **0.71** |\n\n"
        "**结论**：SVD 预测评分更准，但 ItemCF 在召回与多样性上更强。两者存在权衡，你可切换体验差异。\n\n"
        "*运行 `python evaluate.py` 可复现以上数字。*"
    )

if st.session_state.my_ratings:
    st.subheader(f"🎯 为你推荐（{algo}）")
    recs = recommend(st.session_state.my_ratings, n=10) if algo_key == "itemcf" \
        else mf_recommend(st.session_state.my_ratings, n=10)
    if len(recs) == 0:
        st.warning("数据不足，换几本书再试试")
    else:
        for i, row in recs.iterrows():
            render_book_card(row, rank=i + 1)
            st.divider()
else:
    st.subheader("🔥 大家都在读（你可以先从这些书里挑几本打分）")
    pop = popular_books(n=10)
    for i, row in pop.iterrows():
        render_book_card(row)
        st.divider()

    st.subheader("🇨🇳 中文书目精选（真实豆瓣高分书）")
    st.caption("书目与评分为豆瓣读书公开数据 · 精选常用书目演示")
    cn_pop = popular_chinese_books(n=12)
    for i, row in cn_pop.iterrows():
        render_book_card(row, rank=i + 1)
        st.divider()
