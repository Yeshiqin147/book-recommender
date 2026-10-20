"""
模型评估：对比 Item-based CF 与 矩阵分解(SVD)

两套口径（都可直接写进作业报告）：

A) 评分预测精度 —— 数据 8:2 随机切分训练/测试，
   两种算法都对测试集的 (用户,书) 预测评分，
   比较 RMSE / MAE（数值越小越准）。

B) 推荐命中 Recall@K —— 用户级留出法：
   对活跃用户，留出一半"喜欢的书"作为目标，
   用另一半+其余评分做种子，看 Top-K 推荐里能找回多少目标书。
   同时报告推荐覆盖率（覆盖的书占全书比例）。

用法：python evaluate.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

from model import DATA_DIR  # noqa: E402

THRESHOLD = 7  # 视为"喜欢"的评分阈值
SEED = 42


# ---------- 数据准备 ----------
def load_split(test_ratio=0.2):
    ratings = pd.read_csv(DATA_DIR / "ratings.csv")
    books = pd.read_csv(DATA_DIR / "books.csv")
    rng = np.random.default_rng(SEED)
    train_idx = rng.random(len(ratings)) >= test_ratio
    train, test = ratings[train_idx], ratings[~train_idx]
    return train, test, books


# ---------- ItemCF ----------
def itemcf_fit(train):
    """基于训练集构建书-书余弦相似度矩阵"""
    isbns = train["ISBN"].unique()
    users = train["User-ID"].unique()
    isbn_to_idx = {i: k for k, i in enumerate(isbns)}
    user_to_idx = {u: k for k, u in enumerate(users)}
    R = np.zeros((len(users), len(isbns)), dtype=np.float32)
    for _, (u, i, r) in train[["User-ID", "ISBN", "Book-Rating"]].iterrows():
        R[user_to_idx[u], isbn_to_idx[i]] = r
    norms = np.sqrt((R ** 2).sum(axis=0))
    norms[norms == 0] = 1e-8
    sim = (R.T @ R) / np.outer(norms, norms)
    np.fill_diagonal(sim, 0.0)
    return isbn_to_idx, user_to_idx, sim


def itemcf_predict(uid, iid, user_to_idx, isbn_to_idx, sim, ratings_df,
                   user_items_cache):
    """物品协同过滤的评分预测：用用户评过的相似书做加权平均"""
    u_idx = user_to_idx.get(uid)
    i_idx = isbn_to_idx.get(iid)
    if u_idx is None or i_idx is None:
        return np.nan
    # 用户评过的书（索引 + 评分）
    if uid not in user_items_cache:
        sub = ratings_df[ratings_df["User-ID"] == uid]
        user_items_cache[uid] = (sub["ISBN"].map(isbn_to_idx).values,
                                 sub["Book-Rating"].values)
    rated_idx, rated_val = user_items_cache[uid]
    if len(rated_idx) == 0:
        return np.nan
    s = sim[i_idx, rated_idx]
    mask = (s > 0) & (rated_idx != i_idx)
    if not mask.any():
        return np.nan
    w = s[mask]
    v = rated_val[mask]
    return float((w @ v) / w.sum())


def itemcf_rec(user_seed, isbn_to_idx, sim, k):
    """用种子评分给一个用户出 Top-K 推荐（ItemCF 打分排序）"""
    n = sim.shape[0]
    user_vec = np.zeros(n)
    for isbn, r in user_seed.items():
        if isbn in isbn_to_idx:
            user_vec[isbn_to_idx[isbn]] = r
    scores = sim.T @ user_vec
    rated_idx = {isbn_to_idx[i] for i in user_seed if i in isbn_to_idx}
    order = np.argsort(-scores)
    recs = []
    for idx in order:
        if scores[idx] <= 0 or idx in rated_idx:
            continue
        recs.append(idx)
        if len(recs) >= k:
            break
    return recs


# ---------- MF ----------
def mf_fit(train):
    from surprise import Dataset, Reader, SVD

    reader = Reader(rating_scale=(1, 10))
    data = Dataset.load_from_df(
        train[["User-ID", "ISBN", "Book-Rating"]], reader
    )
    trainset = data.build_full_trainset()
    algo = SVD(n_factors=30, random_state=42)
    algo.fit(trainset)
    mapping = {}
    for i_inner in range(trainset.n_items):
        isbn = trainset.to_raw_iid(i_inner)
        mapping[isbn] = (algo.qi[i_inner], algo.bi[i_inner])
    return algo, mapping


def mf_rec(user_seed, algo, mapping, k, lam=0.06):
    """用 fold-in 给一个用户出 Top-K 推荐（MF）"""
    gm = algo.trainset.global_mean
    rated = {i: r for i, r in user_seed.items() if i in mapping}
    if not rated:
        return []
    user_bias = float(np.mean(list(rated.values())) - gm)
    items = list(rated.keys())
    Q = np.stack([mapping[i][0] for i in items])
    r_adj = np.array([
        rated[i] - gm - user_bias - mapping[i][1] for i in items
    ])
    kdim = Q.shape[1]
    p_u = np.linalg.solve(Q.T @ Q + lam * np.eye(kdim), Q.T @ r_adj)
    scored = []
    for isbn, (qi, bi) in mapping.items():
        scored.append((gm + user_bias + bi + float(qi @ p_u), isbn))
    scored.sort(reverse=True)
    recs = [isbn for score, isbn in scored if isbn not in rated][:k]
    return recs


# ---------- A) 评分预测精度 ----------
def eval_prediction(train, test):
    # MF：SVD 预测所有测试评分
    algo, mapping = mf_fit(train)
    y_true = test["Book-Rating"].values.astype(float)
    y_pred_mf = np.array([
        algo.predict(r["User-ID"], r["ISBN"]).est
        for _, r in test.iterrows()
    ])
    mf_rmse = float(np.sqrt(((y_true - y_pred_mf) ** 2).mean()))
    mf_mae = float(np.abs(y_true - y_pred_mf).mean())

    # ItemCF：物品加权平均预测
    isbn_to_idx, user_to_idx, sim = itemcf_fit(train)
    cache = {}
    preds = []
    for _, r in test.iterrows():
        preds.append(itemcf_predict(r["User-ID"], r["ISBN"], user_to_idx,
                                    isbn_to_idx, sim, train, cache))
    preds = np.array(preds, dtype=float)
    valid = ~np.isnan(preds)
    err = y_true[valid] - preds[valid]
    icf_rmse = float(np.sqrt((err ** 2).mean()))
    icf_mae = float(np.abs(err).mean())

    print("\n=== A) 评分预测精度（8:2 切分，同测试集）===")
    print(f"  矩阵分解 SVD : RMSE = {mf_rmse:.4f}   MAE = {mf_mae:.4f}")
    print(f"  物品协同过滤 : RMSE = {icf_rmse:.4f}   MAE = {icf_mae:.4f}"
          f"（可预测 {valid.sum()}/{len(test)} 条）")
    return {"SVD": (mf_rmse, mf_mae), "ItemCF": (icf_rmse, icf_mae)}


# ---------- B) 推荐命中 Recall@K ----------
def eval_ranking(train, test, books, n_users=300, k=10):
    # 每个用户"喜欢"(>=7)的书
    liked = test[test["Book-Rating"] >= THRESHOLD].groupby("User-ID")["ISBN"].apply(list)
    liked = liked[liked.map(len) >= 2]  # 至少 2 本喜欢的书，才够留出
    rng = np.random.default_rng(7)
    if len(liked) > n_users:
        liked = liked.sample(n_users, random_state=rng)

    isbn_to_idx, _, sim = itemcf_fit(train)
    idx_to_isbn = {v: k for k, v in isbn_to_idx.items()}
    algo, mapping = mf_fit(train)

    results = {}
    for name, rec_func in [
        ("ItemCF", lambda seed: [idx_to_isbn[i] for i in itemcf_rec(seed, isbn_to_idx, sim, k)]),
        ("SVD", lambda seed: mf_rec(seed, algo, mapping, k)),
    ]:
        recalls, cover = [], set()
        for u, ls in liked.items():
            ls = sorted(ls)  # 排序保证留出可复现
            half = len(ls) // 2
            target = set(ls[:half])
            # 种子：用户全部训练评分（真实评分），补上留出用的喜欢书
            sub = train[train["User-ID"] == u]
            seed = dict(zip(sub["ISBN"], sub["Book-Rating"]))
            for b in ls[half:]:
                if b not in seed:
                    seed[b] = 8
            rec_isbns = rec_func(seed)
            hits = set(rec_isbns) & target
            recalls.append(len(hits) / len(target))
            cover.update(rec_isbns)
        coverage = len(cover) / len(books)
        results[name] = (float(np.mean(recalls)), coverage)
        print(f"  {name:6s}: Recall@{k} = {np.mean(recalls):.3f}  覆盖率 = {coverage:.3f}"
              f"（覆盖 {len(cover)}/{len(books)} 本）")
    return results


# ---------- 主流程 ----------
def main():
    train, test, books = load_split()
    print(f"评分总数: {len(train)+len(test)} | 训练: {len(train)} | 测试: {len(test)}")

    eval_prediction(train, test)

    print(f"\n=== B) 推荐命中 Recall@{10}（用户级留出，喜欢阈值>=7）===")
    eval_ranking(train, test, books)

    print("\n评估完成")


if __name__ == "__main__":
    main()
