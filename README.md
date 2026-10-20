# 📚 书籍个性化推荐小助手

基于 **Book-Crossing** 公开数据集，实现 **物品协同过滤（Item-based CF）** 与 **矩阵分解（SVD）** 两种推荐算法，通过 **Streamlit** 构建的 Web 应用。
页面可一键切换算法对比效果；一键部署到云端后，任何人打开浏览器链接即可使用。

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
├── app.py              # Streamlit 主程序（页面+交互，可切换两种算法）
├── model.py           # 推荐模型（ItemCF + 矩阵分解 SVD）
├── preprocess.py      # 数据预处理脚本
├── evaluate.py        # 模型评估（RMSE / Recall@K / 覆盖率）
├── requirements.txt    # 依赖清单
├── data/
│   ├── BX-Books.csv       # 原始数据（本地下载，不进 Git）
│   ├── BX-Book-Ratings.csv
│   └── processed/
│       ├── books.csv      # 预处理后小文件（要进 Git）
│       └── ratings.csv
└── README.md
```

## 四、算法说明

### 1. 物品协同过滤（Item-based CF）
- 用 (用户, 书, 评分) 构建稀疏评分矩阵，计算**书与书的余弦相似度**
- 用户打分后，找与已读书最相似的书，加权求和得到推荐分

### 2. 矩阵分解（SVD）
- 把 (用户×书) 评分矩阵分解成两个低维潜因子矩阵：`R ≈ U·Vᵀ`
- 预测公式：`r̂_ui = μ + b_u + b_i + p_u·q_iᵀ`
  - `μ` 全局平均分，`b_u` 用户偏置，`b_i` 书偏置，`p_u`/`q_i` 潜因子向量
- **新用户折叠（fold-in）**：用户打分后不重训模型，用岭回归反解其潜因子向量
  `p_u = (QᵀQ + λI)⁻¹Qᵀ(r − μ − b_u − b_i)`，秒级响应

## 五、评估结果（`python evaluate.py` 可复现）

口径：评分 8:2 随机切分训练/测试；RMSE 衡量评分预测误差，Recall@10 衡量能否找回用户真正喜欢的书（用户级留出法）。

| 指标 | 矩阵分解 SVD | 物品协同过滤 |
|---|---|---|
| RMSE（↓ 好） | **1.51** | 1.64 |
| Recall@10（↑ 好） | 0.06 | **0.17** |
| 覆盖率（↑ 好） | 0.58 | **0.71** |

**结论**：SVD 预测评分更准，ItemCF 在召回用户喜欢的书与多样性上更强，两者存在权衡。

## 六、作业讲解要点
- **算法**：ItemCF（余弦相似度）与 矩阵分解 SVD（潜因子 + 正则 + 折叠），可切换对比
- **数据**：Book-Crossing，27万用户 × 27万本书 × 115万条评分（本项目用过滤后的精简子集）
- **评估**：RMSE / MAE（预测精度）、Recall@K、覆盖率（推荐质量）；冷启动问题用热门书单兜底
- **进阶话题**：稀疏性导致命中率偏低、SVD 的流行度偏置、预测精度与多样性的权衡
