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

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/134.0.0.0 Safari/537.36"
)

REQUEST_DELAY_MIN = 3  # 隨機間隔下限（秒）
REQUEST_DELAY_MAX = 6  # 隨機間隔上限（秒）
REQUEST_TIMEOUT = 30  # 請求逾時（秒）
REQUEST_MAX_RETRIES = 3  # 被擋時最多重試次數

# 模擬瀏覽器的完整 HTTP headers
REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Referer": "https://www.books.com.tw/",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Google Chrome";v="134", "Chromium";v="134", "Not:A-Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}
