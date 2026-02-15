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
    "14": "童書/青少年文學",
    "17": "語言學習",
    "18": "考試用書",
    "19": "電腦資訊",
    "20": "專業/教科書/政府出版品",
    "22": "影視偶像",
    "24": "國中小參考書",
}

NEW_BOOKS_URL_TEMPLATE = "https://www.books.com.tw/web/books_nbtopm_{code}"
PREORDER_URL = "https://www.books.com.tw/web/sys_prebooks/books/"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

REQUEST_DELAY = 1.5  # seconds between requests
REQUEST_TIMEOUT = 30  # seconds
