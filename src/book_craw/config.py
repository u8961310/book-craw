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

CHINA_CATEGORIES: dict[str, str] = {
    "02": "藝術設計",
    "03": "史地",
    "04": "社會科學",
    "05": "哲學/宗教",
    "06": "商業理財",
    "07": "語言學習",
    "08": "醫療保健",
    "09": "旅遊/休閒/飲食/手作",
    "10": "自然科普與應用科學",
    "11": "電腦資訊",
    "12": "童書/親子教養",
    "13": "考試/教輔",
}
CHINA_NEW_BOOKS_URL_TEMPLATE = "https://www.books.com.tw/web/china_nbtopm_{code}/"

# 電子中文書新書分類（代碼 → 分類名稱）
EBOOK_CATEGORIES: dict[str, str] = {
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
EBOOK_NEW_URL_TEMPLATE = "https://www.books.com.tw/web/cebook_new/{code}/"

EXTRA_SOURCES: dict[str, str] = {
    "簡體電子書新書": "https://www.books.com.tw/web/cebook_china",
}

CATEGORY_GROUPS: list[tuple[str, list[str]]] = [
    ("中文書新書", list(CATEGORIES.values())),
    ("簡體書新書", [f"簡體-{v}" for v in CHINA_CATEGORIES.values()]),
    ("電子中文書新書", [f"電子書-{v}" for v in EBOOK_CATEGORIES.values()]),
    ("簡體電子書新書", ["簡體電子書新書"]),
    ("預購書", ["預購書"]),
]

# 需要跨期去重的分類（沒有日期過濾的來源）
DEDUP_CATEGORIES: set[str] = (
    {f"簡體-{v}" for v in CHINA_CATEGORIES.values()}
    | {"簡體電子書新書"}
)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

REQUEST_DELAY = 2.5  # seconds between requests
REQUEST_TIMEOUT = 30  # seconds
