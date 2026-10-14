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
