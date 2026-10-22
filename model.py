"""
推荐模型：基于物品的协同过滤（Item-based CF）
核心思路：
    1. 用 (user, book, rating) 三元组构建稀疏评分矩阵
    2. 计算书与书之间的余弦相似度
    3. 用户打过分的书 → 找相似书 → 加权求和得到推荐分
"""
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from surprise import Dataset, Reader, SVD

DATA_DIR = Path(__file__).parent / "data" / "processed"

# 占位封面（Open Library 找不到时显示）
PLACEHOLDER_COVER = "https://via.placeholder.com/120x180?text=No+Cover"


def cover_url(isbn: str) -> str:
    """根据 ISBN 构造 Open Library 封面 URL"""
    return f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"


@st.cache_data
def load_en_descriptions() -> pd.DataFrame:
    """英文书简介（由 fetch_en_descriptions.py 从真实书目接口拉取并缓存）"""
    p = DATA_DIR / "en_descriptions.csv"
    if p.exists():
        return pd.read_csv(p, encoding="utf-8")
    return pd.DataFrame(columns=["ISBN", "description"])


@st.cache_data
def load_books() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "books.csv")
    df["cover"] = df["ISBN"].apply(cover_url)
    d = load_en_descriptions()
    if not d.empty:
        df = df.merge(d, on="ISBN", how="left")
    else:
        df["description"] = pd.NA
    return df


@st.cache_data
def load_ratings() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "ratings.csv")


# 中文书封面配色（按分类）
CN_COVER_COLORS = {
    "文学": "#5B8DB8", "科幻": "#3E7CB1", "历史": "#9A6B4F",
    "社科": "#6B8E5A", "商业": "#C77E4B", "心理": "#7D6BA6",
    "散文": "#8FA6A0", "古典": "#A0522D", "热门": "#C2574E",
    "童书": "#E8A87C", "科普": "#4E8D7C", "哲学": "#5A5A7A",
}


@st.cache_data
def load_chinese_books() -> pd.DataFrame:
    """加载中文书目（真实豆瓣高分精选，评分与书目为豆瓣公开数据）"""
    df = pd.read_csv(DATA_DIR / "chinese_books.csv", encoding="utf-8")
    df["Language"] = "Chinese"
    df["is_chinese"] = True
    return df


@st.cache_data
def load_catalog() -> pd.DataFrame:
    """合并中英文书目，作为检索/展示的完整目录"""
    en = load_books()
    en["Language"] = "English"
    en["is_chinese"] = False
    en["Category"] = ""
    en["douban_rating"] = pd.NA
    en["rating_count"] = pd.NA
    cn = load_chinese_books()
    return pd.concat([en, cn], ignore_index=True)


def popular_chinese_books(n: int = 10) -> pd.DataFrame:
    """按豆瓣评分 + 评分人数排序的中文热门书"""
    cn = load_chinese_books().copy()
    cn["popularity"] = cn["douban_rating"] * (cn["rating_count"] / 1000).clip(lower=1)
    return cn.sort_values("popularity", ascending=False).head(n).reset_index(drop=True)


# ============================================================
# 隐式行为推荐（根据搜索 / 浏览 / 点击 / 停留时长做"粗糙"个性化）
# 思路：不再让用户"打分"，而是从行为里找兴趣信号——
#   - 搜索词：命中书名/作者/分类/出版社 → 加兴趣分
#   - 浏览/点击过的书：其分类、作者相同的书 → 加权加兴趣分
#   - 停留时长：看得越久，权重越大
#   - 热度兜底：没有明确兴趣时仍能推热门书
# 中英文书都能参与（分类/作者/关键词匹配），无需用户显式评分。
# ============================================================

@st.cache_data
def load_catalog_with_popularity() -> pd.DataFrame:
    """合并目录 + 统一的流行度得分（0-1），供行为推荐兜底"""
    cat = load_catalog()
    ratings = load_ratings()
    agg = ratings.groupby("ISBN").agg(
        n=("Book-Rating", "count"), avg=("Book-Rating", "mean")
    ).reset_index()
    n_arr = agg["n"].astype(float).values
    agg["pop_en"] = agg["avg"].astype(float).values * np.log1p(n_arr)
    cat = cat.merge(agg[["ISBN", "pop_en"]], on="ISBN", how="left")
    rc_arr = cat["rating_count"].fillna(0).astype(float).values
    cat["pop_cn"] = cat["douban_rating"].fillna(0).astype(float).values * np.log1p(rc_arr)
    cat["pop_raw"] = cat["pop_en"].fillna(cat["pop_cn"]).fillna(0.0)
    mx = cat["pop_raw"].max()
    cat["pop"] = (cat["pop_raw"] / mx).fillna(0.0) if mx > 0 else 0.0
    return cat


def recommend_implicit(behavior: dict, search_terms: list, n: int = 10) -> pd.DataFrame:
    """
    行为驱动的粗糙个性化推荐。
    behavior: {ISBN: {"clicks": int, "dwell": float(秒)}}
    search_terms: 用户搜索过的关键词列表
    """
    cat = load_catalog_with_popularity()
    isbns = cat["ISBN"].tolist()
    score = np.zeros(len(cat))

    interacted = set()
    for isbn, info in (behavior or {}).items():
        idx = cat.index[cat["ISBN"] == isbn]
        if len(idx) == 0:
            continue
        interacted.add(isbn)
        w = 0.5 + 0.15 * int(info.get("clicks", 1))
        w *= min(1 + float(info.get("dwell", 0)) / 60.0, 3.0)  # 停留加成
        r = cat.iloc[idx[0]]
        cate = r["Category"] if pd.notna(r["Category"]) else ""
        author = str(r["Book-Author"])
        if cate:
            score[cat["Category"] == cate] += w * 2.0
        if author:
            score[cat["Book-Author"].astype(str) == author] += w * 1.5

    for t in (search_terms or []):
        t = str(t).strip().lower()
        if not t:
            continue
        m = (
            cat["Book-Title"].astype(str).str.lower().str.contains(t, na=False)
            | cat["Book-Author"].astype(str).str.lower().str.contains(t, na=False)
            | cat["Category"].astype(str).str.lower().str.contains(t, na=False)
            | cat["Publisher"].astype(str).str.lower().str.contains(t, na=False)
        )
        score[m] += 1.0

    # 热度兜底，避免冷门书完全刷不出来
    score = score + 0.25 * cat["pop"].values

    mask = ~cat["ISBN"].isin(interacted)
    res = cat[mask].copy()
    res["score"] = score[mask]
    return res.sort_values("score", ascending=False).head(n).reset_index(drop=True)


@st.cache_resource
def build_knn_index():
    """
    构建 item-item 相似度矩阵（书之间的余弦相似度）
    """
    ratings = load_ratings()
    books = load_books()

    ratings = ratings.merge(books[["ISBN"]], on="ISBN")

    isbns = ratings["ISBN"].unique()
    users = ratings["User-ID"].unique()
    isbn_to_idx = {isbn: i for i, isbn in enumerate(isbns)}
    user_to_idx = {u: i for i, u in enumerate(users)}

    n_books = len(isbns)
    n_users = len(users)

    row = ratings["User-ID"].map(user_to_idx).values
    col = ratings["ISBN"].map(isbn_to_idx).values
    data = ratings["Book-Rating"].values.astype(float)

    R = np.zeros((n_users, n_books), dtype=np.float32)
    R[row, col] = data

    norms = np.sqrt((R ** 2).sum(axis=0))
    norms[norms == 0] = 1e-8

    sim = (R.T @ R) / np.outer(norms, norms)
    np.fill_diagonal(sim, 0.0)

    book_idx_to_isbn = {v: k for k, v in isbn_to_idx.items()}
    isbn_row = pd.DataFrame({
        "ISBN": [book_idx_to_isbn[i] for i in range(n_books)],
        "book_idx": range(n_books),
    })
    book_info = books.merge(isbn_row, on="ISBN")

    return isbn_to_idx, book_info, sim


def recommend(user_ratings: dict, n: int = 10) -> pd.DataFrame:
    isbn_to_idx, book_info, sim = build_knn_index()

    rated_idx = [isbn_to_idx[isbn] for isbn in user_ratings.keys() if isbn in isbn_to_idx]
    if not rated_idx:
        return pd.DataFrame()

    user_vec = np.zeros(sim.shape[1])
    for isbn, rating in user_ratings.items():
        if isbn in isbn_to_idx:
            user_vec[isbn_to_idx[isbn]] = rating

    scores = sim.T @ user_vec

    for idx in rated_idx:
        scores[idx] = -1

    top_idx = np.argsort(-scores)[:n]
    result = book_info.iloc[top_idx].copy()
    result["score"] = scores[top_idx]
    return result.reset_index(drop=True)


def popular_books(n: int = 10) -> pd.DataFrame:
    ratings = load_ratings()
    books = load_books()

    agg = ratings.groupby("ISBN").agg(
        n_ratings=("Book-Rating", "count"),
        avg_rating=("Book-Rating", "mean"),
    ).reset_index()

    agg = agg[agg["n_ratings"] >= 100]
    agg["popularity"] = agg["avg_rating"] * np.log1p(agg["n_ratings"])
    top = agg.sort_values("popularity", ascending=False).head(n)
    return books.merge(top, on="ISBN")


# ============================================================
# 矩阵分解（Matrix Factorization / SVD）
# 思路：把 (用户×书) 评分矩阵分解成两个低维潜因子矩阵 U·Vᵀ，
#      书之间的相似度体现在共享的潜因子上，能捕捉更深的偏好。
# 预测公式：r̂_ui = μ + b_u + b_i + p_u · q_iᵀ
#    μ  全局平均分
#    b_u 用户偏置，b_i 书偏置
#    p_u 用户潜因子向量，q_i 书潜因子向量
#
# 新用户折叠（fold-in）：用户打分后不重训模型，而是用岭回归
#   反解他的潜因子向量：
#   p_u = (QᵀQ + λI)⁻¹ Qᵀ (r − μ − b_u − b_i)
#   其中 Q 是他评过分的那些书的潜因子矩阵。
# ============================================================

MF_FACTORS = 30
MF_REG = 0.06  # 折叠时的岭回归正则 λ


@st.cache_resource
def build_mf_model():
    """训练 SVD，返回 (algo, isbn_to_qi, isbn_to_bi)"""
    ratings = load_ratings()
    books = load_books()
    ratings = ratings.merge(books[["ISBN"]], on="ISBN")

    reader = Reader(rating_scale=(1, 10))
    data = Dataset.load_from_df(
        ratings[["User-ID", "ISBN", "Book-Rating"]], reader
    )
    trainset = data.build_full_trainset()
    algo = SVD(n_factors=MF_FACTORS, random_state=42)
    algo.fit(trainset)

    # 把书潜因子和偏置按 ISBN 索引好
    isbn_to_qi = {}
    isbn_to_bi = {}
    for i_inner in range(trainset.n_items):
        isbn = trainset.to_raw_iid(i_inner)
        isbn_to_qi[isbn] = algo.qi[i_inner]
        isbn_to_bi[isbn] = algo.bi[i_inner]

    return algo, isbn_to_qi, isbn_to_bi


def mf_recommend(user_ratings: dict, n: int = 10) -> pd.DataFrame:
    """
    用矩阵分解给新用户推荐。
    user_ratings: {ISBN: 评分}
    """
    algo, isbn_to_qi, isbn_to_bi = build_mf_model()
    global_mean = algo.trainset.global_mean

    # 评过分的书
    rated = {isbn: r for isbn, r in user_ratings.items() if isbn in isbn_to_qi}
    if not rated:
        return pd.DataFrame()

    # 估计用户偏置：新用户评分的均值相对全局均值的偏移
    user_bias = float(np.mean(list(rated.values())) - global_mean)

    # 折叠：用评过分的书估计用户潜因子向量
    items = list(rated.keys())
    Q = np.stack([isbn_to_qi[isbn] for isbn in items])  # (m, k)
    r_adj = np.array([
        rated[isbn] - global_mean - user_bias - isbn_to_bi[isbn]
        for isbn in items
    ])
    k = Q.shape[1]
    p_u = np.linalg.solve(
        Q.T @ Q + MF_REG * np.eye(k),
        Q.T @ r_adj,
    )

    # 对所有书打分（用 books 里的 ISBN，保证封面信息齐全）
    books = load_books()
    isbns = books["ISBN"].tolist()
    scores = []
    for isbn in isbns:
        if isbn not in isbn_to_qi:
            scores.append(-1.0)
            continue
        score = (
            global_mean
            + user_bias
            + isbn_to_bi[isbn]
            + float(isbn_to_qi[isbn] @ p_u)
        )
        scores.append(score)

    result = books.copy()
    result["score"] = scores
    # 排除已经评过分的书
    result = result[~result["ISBN"].isin(rated)]
    result = result.sort_values("score", ascending=False).head(n)
    return result.reset_index(drop=True)
