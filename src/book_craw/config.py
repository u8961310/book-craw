"""博客來新書爬蟲設定。"""

CATEGORIES: dict[str, str] = {
    "02": "商業理財",
    "03": "藝術設計",
    "04": "人文社科",
    "06": "自然科普",
    "07": "心理勵志",
    "08": "醫療保健",
    "09": "飲食",
    "10": "生活風格",
    "11": "旅遊",
    "12": "宗教命理",
    "13": "親子教養",
    "17": "語言學習",
    "18": "考試用書",
    "19": "電腦資訊",
    "20": "專業/教科書/政府出版品",
    "24": "國中小參考書",
}

NEW_BOOKS_URL_TEMPLATE = "https://www.books.com.tw/web/books_nbtopm_{code}"
PREORDER_URL = "https://www.books.com.tw/web/sys_prebooks/books/"

EXTRA_SOURCES: dict[str, str] = {}

CATEGORY_GROUPS: list[tuple[str, list[str]]] = [
    ("中文書新書", list(CATEGORIES.values())),
    ("預購書", ["預購書"]),
]

# 需要跨期去重的分類（沒有日期過濾的來源）
DEDUP_CATEGORIES: set[str] = set()

REQUEST_DELAY_MIN = 3  # 隨機間隔下限（秒）
REQUEST_DELAY_MAX = 6  # 隨機間隔上限（秒）
REQUEST_TIMEOUT = 60  # 請求逾時（秒），Firecrawl 代理渲染較慢
REQUEST_MAX_RETRIES = 3  # 被擋時最多重試次數

# 博客來的 Cloudflare 會對 GitHub Actions runner IP 直接判定為機器人（IP 信譽層），
# 連 curl_cffi 模擬瀏覽器 TLS 指紋都繞不過，改走 Firecrawl 的代理服務抓取。
FIRECRAWL_API_URL = "https://api.firecrawl.dev/v1/scrape"
