# book-craw

博客來新書/預購書爬蟲，自動爬取中文書分類的近期新書，過濾最近 7 天內出版的書籍，透過 Gmail 寄送 HTML 書單郵件，並可產生靜態頁面部署到 GitHub Pages 供線上瀏覽歷史書單。

## 功能

- 爬取博客來 21 個分類的「近期新書」區塊
- 爬取預購書資訊
- 自動過濾最近 30 天內出版的書籍
- 擷取書名、作者、出版社、出版日期、價格、封面圖
- 產生 HTML 格式書單郵件，透過 Gmail SMTP 寄出
- 支援 GitHub Actions 每週自動執行
- 產生靜態 HTML 書單頁面，部署到 GitHub Pages 瀏覽歷史書單

## 支援分類

商業理財、藝術設計、人文社科、自然科普、心理勵志、醫療保健、飲食、生活風格、旅遊、宗教命理、親子教養、童書/青少年文學、語言學習、考試用書、電腦資訊、專業/教科書/政府出版品、國中小參考書

## 安裝

需要 Python 3.12+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
# 安裝 uv（如果還沒有）
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone 專案
git clone https://github.com/your-username/book-craw.git
cd book-craw

# 安裝依賴
uv sync
```

## 設定 Gmail

1. 前往 [Google 帳戶](https://myaccount.google.com/) → **安全性**
2. 開啟**兩步驟驗證**
3. 搜尋「應用程式密碼」→ 建立一組（名稱填 `book-craw`）
4. 複製 16 碼密碼

建立 `.env` 檔案：

```bash
cp .env.example .env
```

編輯 `.env`，填入實際值：

```
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=abcdefghijklmnop
EMAIL_TO=recipient@example.com
```

> `EMAIL_TO` 支援多位收件人，用逗號分隔：`a@gmail.com,b@gmail.com`

## 使用方式

```bash
# 爬取全部分類 + 預購書，寄送郵件
uv run python -m book_craw

# 只輸出 HTML 到終端，不寄信（測試用）
uv run python -m book_craw --dry-run

# 只爬指定分類（代碼見下表）
uv run python -m book_craw --category 01 --category 19

# 不含預購書
uv run python -m book_craw --no-preorders

# 組合使用
uv run python -m book_craw --dry-run --category 19 --no-preorders

# 產生靜態 HTML 頁面到指定目錄
uv run python -m book_craw --pages ./site --dry-run --category 19

# --pages 可與 email 同時使用（爬一次，產頁面 + 寄信）
uv run python -m book_craw --pages ./site
```

### 分類代碼表

| 代碼 | 分類 | 代碼 | 分類 |
|------|------|------|------|
| 02 | 商業理財 | 12 | 宗教命理 |
| 03 | 藝術設計 | 13 | 親子教養 |
| 04 | 人文社科 | 14 | 童書/青少年文學 |
| 06 | 自然科普 | 17 | 語言學習 |
| 07 | 心理勵志 | 18 | 考試用書 |
| 08 | 醫療保健 | 19 | 電腦資訊 |
| 09 | 飲食 | 20 | 專業/教科書/政府出版品 |
| 10 | 生活風格 | 24 | 國中小參考書 |
| 11 | 旅遊 | | |

## 部署到 GitHub Actions

專案已包含 `.github/workflows/weekly-books.yml`，每週一台北時間 09:00 自動執行。

### 設定步驟

1. 將專案推到 GitHub

   ```bash
   git remote add origin https://github.com/your-username/book-craw.git
   git push -u origin main
   ```

2. 到 GitHub repo 頁面 → **Settings** → **Secrets and variables** → **Actions**

3. 新增以下三個 Repository secrets：

   | Name | 值 |
   |------|-----|
   | `GMAIL_USER` | 你的 Gmail 帳號 |
   | `GMAIL_APP_PASSWORD` | 16 碼應用程式密碼 |
   | `EMAIL_TO` | 收件人 Email |

4. 手動測試：到 **Actions** → **Weekly Books Notification** → **Run workflow**

### 啟用 GitHub Pages

Workflow 每次執行會自動將書單靜態頁面推送到 `gh-pages` 分支。要啟用 GitHub Pages：

1. 到 GitHub repo → **Settings** → **Pages**
2. **Source** 選擇 **Deploy from a branch**
3. **Branch** 選擇 `gh-pages`，目錄選 `/ (root)`，按 **Save**
4. 幾分鐘後即可在 `https://<username>.github.io/book-craw/` 瀏覽書單

### 修改排程

編輯 `.github/workflows/weekly-books.yml` 中的 cron 表達式：

```yaml
schedule:
  - cron: "0 1 * * 1"  # UTC 01:00 週一 = 台北 09:00 週一
```

常用範例：
- `"0 1 * * 1"` — 每週一
- `"0 1 * * 1,4"` — 每週一、四
- `"0 1 1 * *"` — 每月 1 號

## 專案結構

```
book-craw/
├── .github/workflows/
│   └── weekly-books.yml    # GitHub Actions 排程 + gh-pages 部署
├── src/book_craw/
│   ├── __init__.py
│   ├── __main__.py         # python -m book_craw 進入點
│   ├── config.py           # 分類代碼、URL、常數設定
│   ├── emailer.py          # HTML 郵件產生與 SMTP 寄送
│   ├── main.py             # CLI 主程式
│   ├── pages.py            # 靜態 HTML 頁面產生器（GitHub Pages）
│   └── scraper.py          # 網頁爬取與解析
├── .env.example            # 環境變數範本
├── pyproject.toml
└── README.md
```
