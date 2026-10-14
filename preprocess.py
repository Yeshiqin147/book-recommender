"""
数据预处理脚本：
读取原始 Book-Crossing 三个 CSV，过滤稀疏数据，输出精简版到 data/processed/
用法：
    1. 下载 http://www2.informatik.uni-freiburg.de/~cziegler/BX/BX-CSV-Dump.zip
    2. 解压后把 BX-Books.csv, BX-Book-Ratings.csv 放到 data/ 目录
    3. 运行: python preprocess.py
"""
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
OUT_DIR = DATA_DIR / "processed"
OUT_DIR.mkdir(exist_ok=True)


def main():
    # Book-Crossing 的 CSV 是 ; 分隔，拉丁-1 编码
    books = pd.read_csv(
        DATA_DIR / "BX-Books.csv",
        sep=";",
        encoding="latin-1",
        on_bad_lines="skip",
    )
    ratings = pd.read_csv(
        DATA_DIR / "BX-Book-Ratings.csv",
        sep=";",
        encoding="latin-1",
        on_bad_lines="skip",
    )

    # 规范化列名
    books.columns = [c.strip('"') for c in books.columns]
    ratings.columns = [c.strip('"') for c in ratings.columns]

    print(f"原始书籍数: {len(books)}, 原始评分数: {len(ratings)}")

    # 只保留显式评分（0 是 implicit，过滤掉）
    ratings = ratings[ratings["Book-Rating"] > 0]

    # 过滤：一本书至少被 50 人评分，一个用户至少评过 5 本书
    book_counts = ratings["ISBN"].value_counts()
    popular_isbns = book_counts[book_counts >= 50].index
    ratings = ratings[ratings["ISBN"].isin(popular_isbns)]

    user_counts = ratings["User-ID"].value_counts()
    active_users = user_counts[user_counts >= 5].index
    ratings = ratings[ratings["User-ID"].isin(active_users)]

    # 合并书籍信息
    books = books[books["ISBN"].isin(ratings["ISBN"])]
    books = books[["ISBN", "Book-Title", "Book-Author", "Year-Of-Publication", "Publisher"]]

    print(f"过滤后书籍数: {len(books)}, 评分数: {len(ratings)}, 用户数: {ratings['User-ID'].nunique()}")

    # 保存
    books.to_csv(OUT_DIR / "books.csv", index=False, encoding="utf-8")
    ratings.to_csv(OUT_DIR / "ratings.csv", index=False, encoding="utf-8")
    print(f"已保存到 {OUT_DIR}")


if __name__ == "__main__":
    main()
