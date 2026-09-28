"""靜態 HTML 頁面產生器，供 GitHub Pages 部署。

每期頁面把書籍資料嵌在 <script id="book-data">，由前端 JS 負責搜尋、分類、排序、折扣篩選。
下一期的 NEW 標記、跨期去重、統計頁、--rebuild 都從這份 JSON 讀回資料。
"""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import date
from pathlib import Path

from book_craw.config import CATEGORY_GROUPS
from book_craw.scraper import Book

log = logging.getLogger(__name__)

_DATA_RE = re.compile(
    r'<script id="book-data" type="application/json">(.*?)</script>', re.DOTALL
)


def _book_to_dict(book: Book, is_new: bool = False) -> dict:
    return {
        "title": book.title,
        "url": book.url,
        "author": book.author,
        "publisher": book.publisher,
        "price": book.price,
        "image_url": book.image_url,
        "pub_date": book.pub_date,
        "new": is_new,
    }


def _dump_json_for_script(data: object) -> str:
    """JSON 放進 <script> 內：跳脫 < > & 成 \\u 序列，瀏覽器 JSON.parse 可直接讀。"""
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
    )


def _read_page_data(path: Path) -> dict[str, list[dict]] | None:
    """讀回某期頁面的 book-data。

    舊版頁面用 html.escape 跳脫過（& 變 &amp;），要先 unescape；
    新版用 \\u 跳脫，沒有 & 字元，unescape 不影響。
    """
    m = _DATA_RE.search(path.read_text(encoding="utf-8"))
    if not m:
        return None
    return json.loads(html.unescape(m.group(1)))


def _weekly_files(output_dir: Path) -> list[Path]:
    books_dir = output_dir / "books"
    if not books_dir.exists():
        return []
    return sorted(books_dir.glob("*.html"))


def _load_previous_data(output_dir: Path, current_date_str: str) -> dict[str, list[dict]] | None:
    """讀取前一期的 book-data JSON。"""
    prev_files = [f for f in _weekly_files(output_dir) if f.stem < current_date_str]
    if not prev_files:
        return None
    return _read_page_data(prev_files[-1])


def load_previous_urls(output_dir: Path, current_date_str: str) -> set[str]:
    """回傳所有過去期數出現過的書籍 URL（去除 query string），用於跨期去重。"""
    urls: set[str] = set()
    for f in _weekly_files(output_dir):
        if f.stem >= current_date_str:
            continue
        data = _read_page_data(f)
        if data:
            urls.update(b["url"].split("?")[0] for books in data.values() for b in books)
    return urls


def _load_previous_titles(output_dir: Path, current_date_str: str) -> set[str]:
    """回傳前一期所有書籍的書名集合，用於 NEW 標記。"""
    data = _load_previous_data(output_dir, current_date_str)
    if not data:
        return set()
    return {b["title"] for books in data.values() for b in books}


def _category_order(books_by_category: dict[str, list[Book]]) -> list[str]:
    """依 CATEGORY_GROUPS 順序排出有書的分類，未分群的補在後面。"""
    order: list[str] = []
    for _, members in CATEGORY_GROUPS:
        for c in members:
            if books_by_category.get(c) and c not in order:
                order.append(c)
    for c, books in books_by_category.items():
        if books and c not in order:
            order.append(c)
    return order


def generate_weekly_page(
    books_by_category: dict[str, list[Book]],
    page_date: date,
    output_dir: Path,
    warnings: list[str] | None = None,
) -> Path:
    """產生當週書單 HTML，回傳輸出檔案路徑。"""
    date_str = page_date.isoformat()
    prev_titles = _load_previous_titles(output_dir, date_str)

    json_data: dict[str, list[dict]] = {}
    for category in _category_order(books_by_category):
        json_data[category] = [
            _book_to_dict(b, is_new=bool(prev_titles) and b.title not in prev_titles)
            for b in books_by_category[category]
        ]
    total = sum(len(v) for v in json_data.values())

    warn_html = ""
    if warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in warnings)
        warn_html = f'<div class="warn" role="status"><strong>本期爬取異常</strong><ul>{items}</ul></div>'

    body = f"""
<header class="top">
  <div class="wrap top-row">
    <a href="../index.html" class="brand" aria-label="返回首頁">博客來新書</a>
    <span class="top-date">{date_str}</span>
    <button type="button" class="icon-btn theme-btn" aria-label="切換深色模式">{_MOON_SVG}</button>
  </div>
  <div class="wrap">
    <label class="search">
      {_SEARCH_SVG}
      <input id="q" type="search" placeholder="搜尋書名、作者、出版社" autocomplete="off" enterkeyhint="search">
    </label>
  </div>
  <div class="wrap"><div class="chips-scroll"><div class="chips" id="chips" role="tablist" aria-label="分類"></div></div></div>
</header>
<main class="wrap">
  {warn_html}
  <div class="controls">
    <label class="ctl">排序
      <select id="sort">
        <option value="date">最新出版</option>
        <option value="price">價格低→高</option>
        <option value="discount">折扣最深</option>
      </select>
    </label>
    <label class="ctl">折扣
      <select id="disc">
        <option value="100">不限</option>
        <option value="79">≤79折</option>
        <option value="75">≤75折</option>
        <option value="66">≤66折</option>
      </select>
    </label>
    <span class="result-count"><b id="count">{total}</b> 本</span>
  </div>
  <div id="list"></div>
  <noscript><p class="empty">這個頁面需要啟用 JavaScript 才能顯示書單。</p></noscript>
</main>
<script id="book-data" type="application/json">{_dump_json_for_script(json_data)}</script>
<script>{_WEEKLY_JS}</script>"""

    page_html = _page(f"書單 {date_str}", body, extra_css=_WEEKLY_CSS)
    books_dir = output_dir / "books"
    books_dir.mkdir(parents=True, exist_ok=True)
    out_path = books_dir / f"{date_str}.html"
    out_path.write_text(page_html, encoding="utf-8")
    log.info("Generated weekly page: %s", out_path)
    return out_path


def generate_index_page(output_dir: Path) -> Path:
    """掃描 books/ 目錄產生首頁：每期一張卡片（日期、本數、前幾張封面）。"""
    files = sorted(_weekly_files(output_dir), reverse=True)

    cards: list[str] = []
    for f in files:
        data = _read_page_data(f) or {}
        books = [b for bs in data.values() for b in bs]
        covers = [b["image_url"] for b in books if b.get("image_url")][:4]
        thumbs = "".join(
            f'<img src="{html.escape(u, quote=True)}" alt="" loading="lazy" width="54" height="76">'
            for u in covers
        )
        new_count = sum(1 for b in books if b.get("new"))
        new_html = f'<span class="idx-new">NEW {new_count}</span>' if new_count else ""
        cards.append(
            f'<a class="idx-card" href="books/{f.stem}.html">'
            f'<div class="idx-head"><span class="idx-date">{f.stem}</span>{new_html}</div>'
            f'<span class="idx-count">{len(books)} 本・{len(data)} 個分類</span>'
            f'<div class="idx-thumbs">{thumbs}</div></a>'
        )

    list_html = f'<div class="idx-grid">{"".join(cards)}</div>' if cards else '<p class="empty">目前尚無書單。</p>'

    body = f"""
<header class="top">
  <div class="wrap top-row">
    <span class="brand">博客來新書</span>
    <a class="top-link" href="stats.html">統計</a>
    <button type="button" class="icon-btn theme-btn" aria-label="切換深色模式">{_MOON_SVG}</button>
  </div>
</header>
<main class="wrap">
  <h1 class="page-title">歷史書單</h1>
  <p class="page-sub">每週一更新，共 {len(files)} 期</p>
  {list_html}
</main>"""

    out_path = output_dir / "index.html"
    out_path.write_text(_page("博客來新書書單", body, extra_css=_INDEX_CSS), encoding="utf-8")
    log.info("Generated index page: %s (%d entries)", out_path, len(files))
    return out_path


def generate_stats_page(output_dir: Path) -> Path:
    """從各期 book-data JSON 產生統計頁面。"""
    weekly_stats: list[tuple[str, int]] = []
    category_totals: dict[str, int] = {}
    for f in _weekly_files(output_dir):
        data = _read_page_data(f)
        if data is None:
            continue
        week_total = 0
        for cat, books in data.items():
            week_total += len(books)
            category_totals[cat] = category_totals.get(cat, 0) + len(books)
        weekly_stats.append((f.stem, week_total))

    total_weeks = len(weekly_stats)
    total_books = sum(c for _, c in weekly_stats)
    latest_count = weekly_stats[-1][1] if weekly_stats else 0
    avg = round(total_books / total_weeks) if total_weeks else 0

    def stat(value: int, label: str) -> str:
        return (
            f'<div class="stat"><span class="stat-v" data-count="{value}">{value}</span>'
            f'<span class="stat-l">{label}</span></div>'
        )

    summary = (
        '<div class="stats">'
        + stat(latest_count, "本期書數")
        + stat(avg, "平均每期")
        + stat(total_books, "累計書數")
        + stat(total_weeks, "總期數")
        + "</div>"
    )

    # 趨勢：所有期數塞進一個畫面寬（不用左右滑），點／滑過某期在上方顯示數字；X 軸只在換月時標月份
    max_week = max((c for _, c in weekly_stats), default=1) or 1
    col_parts: list[str] = []
    prev_month = ""
    last_label_i = -99
    for i, (d, c) in enumerate(weekly_stats):
        month = d[:7]
        label = ""
        # 換月才標；離上一個標籤太近（< 3 期）就跳過，避免文字重疊
        if month != prev_month and i - last_label_i >= 3:
            m = int(d[5:7])
            label = f'<span class="col-m">{m}月</span>'
            last_label_i = i
        prev_month = month
        diff = c - weekly_stats[i - 1][1] if i else 0
        col_parts.append(
            f'<button type="button" class="col" data-d="{d}" data-v="{c}" data-diff="{diff if i else ""}" '
            f'aria-label="{d}：{c} 本" style="--h:{c / max_week * 100:.1f}%;--i:{i}">'
            f'<span class="col-bar"></span>{label}</button>'
        )
    if col_parts:
        trend = (
            '<div class="trend">'
            '<div class="trend-cap" aria-live="polite"><span id="cap-d"></span>'
            '<b id="cap-v"></b><span class="cap-u">本</span><span id="cap-diff"></span></div>'
            f'<div class="trend-bars">{"".join(col_parts)}</div>'
            '<p class="trend-hint">點選或按住左右拖曳，看各期書數</p></div>'
        )
    else:
        trend = '<p class="empty">尚無資料</p>'

    # 分類累計排行：手機上標籤放在長條上方，避免擠壓
    ranked = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    max_cat = ranked[0][1] if ranked else 1
    def bar(cat: str, count: int) -> str:
        return (
            f'<div class="bar"><div class="bar-top"><span>{html.escape(cat)}</span><b>{count}</b></div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{count / max_cat * 100:.1f}%"></div></div></div>'
        )

    top_n = 12
    bars = "".join(bar(c, n) for c, n in ranked[:top_n])
    rest = ranked[top_n:]
    if rest:
        bars += (
            f'<details class="more"><summary>其他 {len(rest)} 個分類</summary>'
            f'<div class="bars">{"".join(bar(c, n) for c, n in rest)}</div></details>'
        )

    body = f"""
<header class="top">
  <div class="wrap top-row">
    <a href="index.html" class="brand" aria-label="返回首頁">博客來新書</a>
    <span class="top-date">統計</span>
    <button type="button" class="icon-btn theme-btn" aria-label="切換深色模式">{_MOON_SVG}</button>
  </div>
</header>
<main class="wrap">
  <h1 class="page-title">書單統計</h1>
  {summary}
  <h2 class="sec-title">每期書數</h2>
  {trend}
  <h2 class="sec-title">各分類累計</h2>
  <div class="bars">{bars}</div>
</main>
<script>{_STATS_JS}</script>"""

    out_path = output_dir / "stats.html"
    out_path.write_text(_page("書單統計", body, extra_css=_STATS_CSS), encoding="utf-8")
    log.info("Generated stats page: %s", out_path)
    return out_path


def rebuild_all(output_dir: Path) -> int:
    """不重新爬取，用各期頁面內的 book-data 把全部頁面換成目前版型。回傳重建期數。"""
    files = _weekly_files(output_dir)
    count = 0
    # 由舊到新重建，NEW 標記才會以「前一期」比對
    for f in files:
        data = _read_page_data(f)
        if data is None:
            log.warning("Skip %s: no book-data", f)
            continue
        books_by_category = {
            cat: [
                Book(
                    title=b.get("title", ""),
                    url=b.get("url", ""),
                    author=b.get("author", ""),
                    publisher=b.get("publisher", ""),
                    price=b.get("price", ""),
                    image_url=b.get("image_url", ""),
                    category=cat,
                    pub_date=b.get("pub_date", ""),
                )
                for b in books
            ]
            for cat, books in data.items()
        }
        generate_weekly_page(books_by_category, date.fromisoformat(f.stem), output_dir)
        count += 1
    generate_index_page(output_dir)
    generate_stats_page(output_dir)
    return count


# ---------------------------------------------------------------------------
# 版型：書店紙本風（米白底、深棕字、博客來紅強調），支援深色模式
# 文字對比皆 ≥ 4.5:1（muted：淺色 #5c4a3a on #fffdf9 ≈ 8.9:1；深色 #c9bba9 on #221c16 ≈ 9.6:1）
# ---------------------------------------------------------------------------

_MOON_SVG = (
    '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>'
)
_SEARCH_SVG = (
    '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" '
    'stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/>'
    '<path d="m20 20-3.5-3.5"/></svg>'
)

# 在繪製前套用主題，避免深色模式閃白
_THEME_HEAD_JS = """(function(){try{var t=localStorage.getItem('theme');if(t)document.documentElement.dataset.theme=t;}catch(e){}})();"""
_THEME_TOGGLE_JS = """(function(){var b=document.querySelector('.theme-btn');if(!b)return;b.addEventListener('click',function(){var r=document.documentElement;var dark=r.dataset.theme?r.dataset.theme==='dark':matchMedia('(prefers-color-scheme: dark)').matches;var n=dark?'light':'dark';r.dataset.theme=n;try{localStorage.setItem('theme',n);}catch(e){}});})();"""


def _page(title: str, body: str, extra_css: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>{html.escape(title)}</title>
<script>{_THEME_HEAD_JS}</script>
<style>
{_BASE_CSS}
{extra_css}
</style>
</head>
<body>
{body}
<script>{_THEME_TOGGLE_JS}</script>
</body>
</html>"""


_BASE_CSS = """\
:root{--bg:#f7f3ec;--surface:#fffdf9;--surface-2:#efe7da;--text:#2b2118;--muted:#5c4a3a;
  --line:#d9cfc0;--accent:#a8201a;--accent-ink:#fff;--warn-bg:#fff4dc;--warn-line:#c98a12;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#17130f;--surface:#221c16;--surface-2:#2e261e;
  --text:#efe7dc;--muted:#c9bba9;--line:#4a3f33;--accent:#f08a7e;--accent-ink:#1b0f0d;--warn-bg:#3a2c12;--warn-line:#e0a534;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#17130f;--surface:#221c16;--surface-2:#2e261e;
  --text:#efe7dc;--muted:#c9bba9;--line:#4a3f33;--accent:#f08a7e;--accent-ink:#1b0f0d;--warn-bg:#3a2c12;--warn-line:#e0a534;color-scheme:dark}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{font-family:-apple-system,BlinkMacSystemFont,"PingFang TC","Microsoft JhengHei","Noto Sans TC",sans-serif;
  background:var(--bg);color:var(--text);line-height:1.6;font-size:15px}
a{color:inherit}
.wrap{max-width:1080px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left));padding-right:max(16px,env(safe-area-inset-right))}
.top{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--line)}
.top-row{display:flex;align-items:center;gap:12px;min-height:52px}
.brand{font-weight:700;font-size:17px;text-decoration:none;color:var(--text)}
.top-date{color:var(--muted);font-size:14px;margin-right:auto}
.top-link{margin-left:auto;color:var(--accent);font-weight:600;text-decoration:none;padding:10px 4px}
.icon-btn{width:44px;height:44px;display:inline-grid;place-items:center;border:1px solid var(--line);
  background:var(--surface);color:var(--text);border-radius:10px;cursor:pointer}
.icon-btn:focus-visible,.chip:focus-visible,select:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.page-title{font-size:24px;margin:24px 0 4px}
.page-sub{color:var(--muted);margin-bottom:20px}
.sec-title{font-size:18px;margin:32px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--accent)}
.empty{color:var(--muted);text-align:center;padding:48px 0}
"""

_WEEKLY_CSS = """\
.search{display:flex;align-items:center;gap:8px;background:var(--surface);border:1px solid var(--line);
  border-radius:12px;padding:0 12px;min-height:44px;color:var(--muted);margin-bottom:10px}
.search input{flex:1;border:0;background:transparent;color:var(--text);font:inherit;font-size:16px;min-width:0;outline:none;padding:10px 0}
.search:focus-within{border-color:var(--accent)}
.chips-scroll{overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;padding-bottom:10px}
.chips-scroll::-webkit-scrollbar{display:none}
.chips{display:flex;gap:8px;width:max-content}
.chip{flex:none;display:inline-flex;align-items:center;gap:6px;min-height:40px;padding:0 14px;border-radius:20px;
  border:1px solid var(--line);background:var(--surface);color:var(--text);font:inherit;font-size:14px;cursor:pointer;white-space:nowrap}
.chip span{font-size:12px;color:var(--muted)}
.chip[aria-selected="true"]{background:var(--text);color:var(--bg);border-color:var(--text)}
.chip[aria-selected="true"] span{color:inherit;opacity:.85}
.controls{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;margin:14px 0 6px}
.ctl{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:14px}
.ctl select{font:inherit;font-size:14px;color:var(--text);background:var(--surface);border:1px solid var(--line);
  border-radius:8px;min-height:40px;padding:0 8px}
.result-count{margin-left:auto;color:var(--muted);font-size:14px}
.result-count b{color:var(--text)}
.cat-title{display:flex;align-items:baseline;gap:8px;font-size:18px;margin:28px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--accent);scroll-margin-top:170px}
.cat-title small{font-size:13px;color:var(--muted);font-weight:400}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:16px;margin:12px 0 8px}
.card{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--line);border-radius:10px;
  overflow:hidden;text-decoration:none;color:var(--text);transition:border-color .15s}
.card:hover{border-color:var(--accent)}
.cover{aspect-ratio:3/4;background:var(--surface-2);display:grid;place-items:center;padding:10px}
.cover img{max-width:100%;max-height:100%;object-fit:contain;box-shadow:0 2px 6px rgba(0,0,0,.18)}
.cover .no-cover{color:var(--muted);font-size:12px}
.info{display:flex;flex-direction:column;gap:3px;padding:10px 12px 12px;flex:1}
.t{font-weight:700;font-size:14px;line-height:1.45;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.new{display:inline-block;background:var(--accent);color:var(--accent-ink);font-size:11px;font-weight:700;
  padding:0 6px;border-radius:4px;margin-right:4px;vertical-align:1px;line-height:1.6}
.by{font-size:13px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.row{display:flex;align-items:baseline;justify-content:space-between;gap:6px;margin-top:auto;padding-top:6px}
.price{font-size:14px;color:var(--text)}
.price em{font-style:normal;color:var(--accent);font-weight:700;margin-right:4px}
.d{font-size:12px;color:var(--muted)}
.card{animation:card-in .3s ease-out both}
@keyframes card-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.card{animation:none}}
.warn{background:var(--warn-bg);border:1px solid var(--warn-line);border-radius:10px;padding:12px 14px;margin-top:14px;font-size:14px}
.warn ul{margin:4px 0 0 18px}
@media (min-width:900px){.chips{flex-wrap:wrap;width:auto}}
@media (max-width:560px){
  .grid{grid-template-columns:1fr 1fr;gap:10px}
  .chip{min-height:44px}
  .info{padding:8px 10px 10px}
  .t{font-size:14px}
  .ctl select{min-height:44px}
}
"""

_INDEX_CSS = """\
.idx-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;margin-bottom:40px}
.idx-card{display:flex;flex-direction:column;gap:6px;background:var(--surface);border:1px solid var(--line);
  border-radius:12px;padding:14px 16px;text-decoration:none;color:var(--text)}
.idx-card:hover{border-color:var(--accent)}
.idx-head{display:flex;align-items:center;gap:8px}
.idx-date{font-size:18px;font-weight:700}
.idx-new{font-size:12px;font-weight:700;color:var(--accent-ink);background:var(--accent);padding:0 6px;border-radius:4px}
.idx-count{color:var(--muted);font-size:14px}
.idx-thumbs{display:flex;gap:8px;margin-top:6px;min-height:76px}
.idx-thumbs img{width:54px;height:76px;object-fit:cover;border-radius:3px;background:var(--surface-2)}
"""

_STATS_CSS = """\
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:16px}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;display:flex;flex-direction:column}
.stat-v{font-size:28px;font-weight:700;line-height:1.2}
.stat:first-child .stat-v{color:var(--accent)}
.stat-l{font-size:13px;color:var(--muted)}
.trend{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 14px 10px}
.trend-cap{display:flex;align-items:baseline;gap:6px;min-height:34px;flex-wrap:wrap}
#cap-d{color:var(--muted);font-size:14px}
#cap-v{font-size:26px;line-height:1.1}
.cap-u{color:var(--muted);font-size:14px}
#cap-diff{font-size:13px;color:var(--muted);margin-left:4px}
.trend-bars{display:flex;align-items:flex-end;gap:2px;height:200px;margin:10px 0 24px;border-bottom:1px solid var(--line);
  touch-action:pan-y;user-select:none;-webkit-user-select:none}
.col{position:relative;flex:1 1 0;min-width:0;height:100%;display:flex;align-items:flex-end;
  background:none;border:0;padding:0;cursor:pointer;-webkit-tap-highlight-color:transparent}
.col-bar{display:block;width:100%;height:var(--h);min-height:2px;background:var(--accent);opacity:.5;
  border-radius:3px 3px 0 0;transform-origin:bottom;transition:opacity .2s}
.col:hover .col-bar,.col.on .col-bar{opacity:1}
.col:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.col-m{position:absolute;left:0;top:100%;margin-top:4px;font-size:12px;color:var(--muted);white-space:nowrap;pointer-events:none}
.trend-hint{font-size:12px;color:var(--muted);text-align:right}
.bars{display:flex;flex-direction:column;gap:10px;margin-bottom:40px}
.bar-top{display:flex;justify-content:space-between;font-size:14px}
.bar-top b{font-weight:600}
.bar-track{height:10px;background:var(--surface-2);border-radius:5px;overflow:hidden;margin-top:3px}
.bar-fill{height:100%;background:var(--accent);border-radius:5px;transform-origin:left}
/* 動畫：JS 載入後加 .anim 才播放，沒有 JS 時直接顯示完整圖表 */
.anim .col-bar{animation:grow-y .6s cubic-bezier(.2,.8,.2,1) both;animation-delay:calc(var(--i) * 25ms)}
.anim .bar-fill{transform:scaleX(0);transition:transform .8s cubic-bezier(.2,.8,.2,1)}
.anim .bar.in .bar-fill{transform:scaleX(1);transition-delay:calc(var(--i,0) * 40ms)}
#cap-v.bump{animation:bump .3s ease-out}
@keyframes grow-y{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes bump{from{transform:translateY(4px);opacity:.3}to{transform:none;opacity:1}}
@media (prefers-reduced-motion:reduce){.anim .col-bar,#cap-v.bump{animation:none}.anim .bar-fill{transform:none;transition:none}}
.more summary{cursor:pointer;color:var(--accent);font-weight:600;padding:10px 0;min-height:44px}
.more .bars{margin:6px 0 0}
@media (max-width:560px){.stats{grid-template-columns:1fr 1fr}.stat-v{font-size:24px}}
"""

_STATS_JS = r"""
(function(){
  var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  var main=document.querySelector('main');
  if(!reduce) main.classList.add('anim');

  // 摘要數字從 0 跳到實際值
  if(!reduce) document.querySelectorAll('.stat-v[data-count]').forEach(function(el){
    var end=+el.dataset.count, t0=null;
    function step(t){ if(!t0) t0=t; var p=Math.min((t-t0)/700,1);
      el.textContent=Math.round(end*(1-Math.pow(1-p,3))); if(p<1) requestAnimationFrame(step); }
    el.textContent='0'; requestAnimationFrame(step);
  });

  // 趨勢圖：點／滑過某一期，上方顯示該期書數與前一期差距
  var cols=[].slice.call(document.querySelectorAll('.col'));
  var capD=document.getElementById('cap-d'), capV=document.getElementById('cap-v'), capDiff=document.getElementById('cap-diff');
  function pick(c){
    if(!c||c.classList.contains('on')) return;
    cols.forEach(function(x){x.classList.toggle('on',x===c);x.tabIndex=x===c?0:-1;});
    capD.textContent=c.dataset.d+(c===cols[cols.length-1]?'（最新）':'');
    capV.textContent=c.dataset.v;
    capV.classList.remove('bump'); void capV.offsetWidth; capV.classList.add('bump');
    var d=c.dataset.diff; capDiff.textContent=d===''?'':'比前一期 '+(+d>0?'+':'')+d;
  }
  cols.forEach(function(c){ c.addEventListener('focus',function(){pick(c);}); });
  // 長條很細（手機上約 7px），改成依手指／滑鼠的水平位置選最近的一期，可以按住拖曳
  var area=document.querySelector('.trend-bars'), dragging=false;
  function at(e){
    var r=area.getBoundingClientRect();
    var i=Math.floor((e.clientX-r.left)/r.width*cols.length);
    pick(cols[Math.max(0,Math.min(cols.length-1,i))]);
  }
  if(area){
    area.addEventListener('pointerdown',function(e){dragging=true;at(e);});
    area.addEventListener('pointermove',function(e){if(dragging||e.pointerType==='mouse')at(e);});
    ['pointerup','pointercancel','pointerleave'].forEach(function(t){area.addEventListener(t,function(){dragging=false;});});
  }
  pick(cols[cols.length-1]);
  // 鍵盤：左右鍵切換期數
  if(area) area.addEventListener('keydown',function(e){
    var i=cols.indexOf(document.activeElement); if(i<0) return;
    var n=e.key==='ArrowLeft'?i-1:e.key==='ArrowRight'?i+1:-1;
    if(n>=0&&n<cols.length){e.preventDefault();cols[n].focus();}
  });

  // 分類排行：捲到畫面內才伸長
  var bars=document.querySelectorAll('.bar');
  if(reduce||!('IntersectionObserver' in window)){bars.forEach(function(b){b.classList.add('in');});return;}
  var io=new IntersectionObserver(function(es){es.forEach(function(e){
    if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}});},{threshold:.2});
  bars.forEach(function(b,i){b.style.setProperty('--i',i%12);io.observe(b);});
  document.querySelectorAll('.more').forEach(function(d){d.addEventListener('toggle',function(){
    d.querySelectorAll('.bar').forEach(function(b){b.classList.add('in');});});});
})();
"""

_WEEKLY_JS = r"""
(function(){
  var data=JSON.parse(document.getElementById('book-data').textContent);
  var cats=Object.keys(data), books=[];
  cats.forEach(function(c){data[c].forEach(function(b){
    var d=/(\d+)\s*折/.exec(b.price||''), p=/(\d+)\s*元/.exec(b.price||'');
    books.push({b:b,cat:c,disc:d?+d[1]:100,yuan:p?+p[1]:Infinity,
      text:(b.title+' '+b.author+' '+b.publisher).toLowerCase()});
  });});
  var state={q:'',cat:'all',sort:'date',disc:100};
  var $=function(id){return document.getElementById(id);};
  var esc=function(s){return String(s||'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
  var safeUrl=function(u){return /^https?:\/\//.test(u||'')?u:'';};

  var chips=$('chips');
  chips.innerHTML=[['all','全部',books.length]].concat(cats.map(function(c){return [c,c,data[c].length];}))
    .map(function(x){return '<button type="button" class="chip" role="tab" aria-selected="'+(x[0]==='all')+'" data-cat="'+esc(x[0])+'">'+esc(x[1])+'<span>'+x[2]+'</span></button>';}).join('');
  chips.addEventListener('click',function(e){
    var btn=e.target.closest('.chip'); if(!btn) return;
    chips.querySelectorAll('.chip').forEach(function(x){x.setAttribute('aria-selected',x===btn);});
    btn.scrollIntoView({inline:'nearest',block:'nearest'});
    state.cat=btn.dataset.cat; draw(); window.scrollTo({top:0});
  });
  $('q').addEventListener('input',function(e){state.q=e.target.value.trim().toLowerCase();draw();});
  $('sort').addEventListener('change',function(e){state.sort=e.target.value;draw();});
  $('disc').addEventListener('change',function(e){state.disc=+e.target.value;draw();});

  var cmp={
    date:function(a,b){return (b.b.pub_date||'').localeCompare(a.b.pub_date||'');},
    price:function(a,b){return a.yuan-b.yuan;},
    discount:function(a,b){return a.disc-b.disc;}
  };
  function card(x){
    var b=x.b, url=safeUrl(b.url), img=safeUrl(b.image_url);
    var price=x.disc<100?'<em>'+x.disc+'折</em>'+(isFinite(x.yuan)?x.yuan+'元':''):(isFinite(x.yuan)?x.yuan+'元':'');
    return '<a class="card" href="'+esc(url)+'" target="_blank" rel="noopener" title="'+esc(b.title)+'">'+
      '<div class="cover">'+(img?'<img src="'+esc(img)+'" alt="" loading="lazy" decoding="async">':'<span class="no-cover">無封面</span>')+'</div>'+
      '<div class="info"><span class="t">'+(b.new?'<span class="new">NEW</span>':'')+esc(b.title)+'</span>'+
      '<span class="by">'+esc([b.author,b.publisher].filter(Boolean).join('・'))+'</span>'+
      '<div class="row"><span class="price">'+price+'</span><span class="d">'+esc((b.pub_date||'').slice(5))+(x.cat==='預購書'&&b.pub_date?' 上市':'')+'</span></div></div></a>';
  }
  function draw(){
    var r=books.filter(function(x){
      return (state.cat==='all'||x.cat===state.cat)&&x.disc<=state.disc&&(!state.q||x.text.indexOf(state.q)>=0);
    }).sort(cmp[state.sort]);
    $('count').textContent=r.length;
    var out='';
    if(!r.length){out='<p class="empty">找不到符合的書，換個關鍵字或條件試試</p>';}
    else if(state.cat==='all'&&!state.q){
      // 全部＋未搜尋：按分類分段，段內照排序
      cats.forEach(function(c){
        var g=r.filter(function(x){return x.cat===c;}); if(!g.length) return;
        out+='<h2 class="cat-title">'+esc(c)+'<small>'+g.length+' 本</small></h2><div class="grid">'+g.map(card).join('')+'</div>';
      });
    } else {
      // 攤平顯示時，同一本書可能同時在兩個分類，依網址去重
      var seen={};
      r=r.filter(function(x){var k=(x.b.url||'').split('?')[0];if(seen[k])return false;seen[k]=1;return true;});
      $('count').textContent=r.length;
      out='<div class="grid">'+r.map(card).join('')+'</div>';
    }
    $('list').innerHTML=out;
  }
  draw();
})();
"""
