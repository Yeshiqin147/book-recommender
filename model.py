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
def load_books() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "books.csv")
    df["cover"] = df["ISBN"].apply(cover_url)
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
