import pandas as pd

df = pd.read_csv(
    "data/douban_raw/douban_dataset(text information)/bookreviews_cleaned.txt",
    sep="\t",
    nrows=100,
)
print("列名:", df.columns.tolist())
print("行数:", len(df))
print()
print("前5行:")
for i, row in df.head(5).iterrows():
    print(f"  book_id={row['book_id']}, rating={row['rating']}")
    print(f"  labels={str(row['labels'])[:100]}")
    print()
