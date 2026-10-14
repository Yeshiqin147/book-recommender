# 📚 书籍个性化推荐小助手

基于 **Book-Crossing** 公开数据集，使用 **物品协同过滤（Item-based Collaborative Filtering）**，通过 **Streamlit** 构建的 Web 应用。
一键部署到云端后，任何人打开浏览器链接即可使用。

---

## 一、本地运行步骤

### 1. 安装依赖
```powershell
pip install -r requirements.txt
```

### 2. 下载数据
1. 打开 http://www2.informatik.uni-freiburg.de/~cziegler/BX/BX-CSV-Dump.zip
2. 解压后把 `BX-Books.csv` 和 `BX-Book-Ratings.csv` 放到 `data/` 目录

### 3. 预处理数据（生成精简版小文件）
```powershell
python preprocess.py
```
会在 `data/processed/` 下生成 `books.csv` 和 `ratings.csv`。

### 4. 启动应用
```powershell
streamlit run app.py
```
浏览器会自动打开 http://localhost:8501

---

## 二、部署到公网（让别人电脑也能访问）

### 1. 把代码推到 GitHub
- 在 GitHub 新建一个仓库，例如 `book-recommender`
- 把本文件夹内容 push 上去（`data/processed/` 下的小文件一定要包含）

### 2. 用 Streamlit Community Cloud 一键部署
1. 打开 https://share.streamlit.io/ ，用 GitHub 账号登录
2. 点 **"New app"** → 选你的仓库 → 主文件选 `app.py`
3. 点 **Deploy**，等 1-2 分钟
4. 得到一个公网链接，形如 `https://你的用户名-book-recommender.streamlit.app`

把这个链接发给老师同学，他们在任何电脑/手机上用浏览器打开就能用，不需要装任何东西。

---

## 三、项目结构
```
book-recommender/
├── app.py              # Streamlit 主程序（页面+交互）
├── model.py           # 推荐模型（Item-based CF）
├── preprocess.py      # 数据预处理脚本
├── requirements.txt    # 依赖清单
├── data/
│   ├── BX-Books.csv       # 原始数据（本地下载，不进 Git）
│   ├── BX-Book-Ratings.csv
│   └── processed/
│       ├── books.csv      # 预处理后小文件（要进 Git）
│       └── ratings.csv
└── README.md
```

## 四、作业讲解要点
- **算法**：基于物品的协同过滤（Item-based CF），用余弦相似度度量书与书之间的相似性
- **数据**：Book-Crossing，27万用户 × 27万本书 × 115万条评分
- **评估思路**：可讲 Precision@K、Recall@K、覆盖率；冷启动问题用热门书单兜底
