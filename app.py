"""
书籍个性化推荐 - Streamlit 主程序
运行：streamlit run app.py
"""
import pandas as pd
import streamlit as st

from model import load_books, popular_books, recommend

st.set_page_config(page_title="书籍推荐小助手", page_icon="📚", layout="wide")

if "my_ratings" not in st.session_state:
    st.session_state.my_ratings = {}


def render_book_card(row, rank=None):
    """渲染单本书的卡片：左封面 + 右信息"""
    col_img, col_info = st.columns([1, 3])
    with col_img:
        st.image(row["cover"], width=100)
    with col_info:
        title = f"**《{row['Book-Title']}》**"
        if rank:
            title = f"**#{rank} {title}**"
        st.markdown(title)
        st.write(f"✍️ {row['Book-Author']} · {int(row['Year-Of-Publication'])}")
        st.write(f"🏛️ {row['Publisher']}")
        if "avg_rating" in row and pd.notna(row.get("avg_rating")):
            st.write(f"⭐ 平均 {row['avg_rating']:.1f}/10 · {int(row['n_ratings'])}人评分")


# ---------- 侧边栏 ----------
with st.sidebar:
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
st.caption("基于 Book-Crossing 数据集 · 物品协同过滤（Item-based CF）")

if st.session_state.my_ratings:
    st.subheader("🎯 为你推荐")
    recs = recommend(st.session_state.my_ratings, n=10)
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
