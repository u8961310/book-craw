"""靜態 HTML 頁面產生器，供 GitHub Pages 部署。"""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import date
from pathlib import Path

from book_craw.scraper import Book

log = logging.getLogger(__name__)


def _book_to_dict(book: Book) -> dict:
    return {
        "title": book.title,
        "url": book.url,
        "author": book.author,
        "publisher": book.publisher,
        "price": book.price,
        "image_url": book.image_url,
        "pub_date": book.pub_date,
    }


def _load_previous_titles(output_dir: Path, current_date_str: str) -> set[str]:
    """讀取前一期 HTML 的 book-data JSON，回傳書名集合。"""
    books_dir = output_dir / "books"
    if not books_dir.exists():
        return set()
    htmls = sorted(books_dir.glob("*.html"))
    prev_files = [f for f in htmls if f.stem < current_date_str]
    if not prev_files:
        return set()
    prev_html = prev_files[-1].read_text(encoding="utf-8")
    m = re.search(
        r'<script id="book-data" type="application/json">(.*?)</script>',
        prev_html,
        re.DOTALL,
    )
    if not m:
        return set()
    data: dict[str, list[dict]] = json.loads(m.group(1))
    return {b["title"] for books in data.values() for b in books}


def generate_weekly_page(
    books_by_category: dict[str, list[Book]],
    page_date: date,
    output_dir: Path,
) -> Path:
    """產生當週書單 HTML，回傳輸出檔案路徑。"""
    total = sum(len(v) for v in books_by_category.values())
    date_str = page_date.isoformat()

    # 準備 JSON 資料
    json_data: dict[str, list[dict]] = {}
    for category, books in books_by_category.items():
        if books:
            json_data[category] = [_book_to_dict(b) for b in books]

    # 載入前一期書名做 NEW 比對
    prev_titles = _load_previous_titles(output_dir, date_str)

    # 收集分類名稱（有書的）
    categories = [c for c, b in books_by_category.items() if b]

    # 分類篩選按鈕
    filter_buttons = ['<button class="filter-btn active" data-cat="all">全部</button>']
    for cat in categories:
        escaped = html.escape(cat, quote=True)
        filter_buttons.append(
            f'<button class="filter-btn" data-cat="{escaped}">{escaped}</button>'
        )
    filter_bar = f'<div class="filter-bar">{"".join(filter_buttons)}</div>'

    cards: list[str] = []
    for category, books in books_by_category.items():
        if not books:
            continue
        escaped_cat = html.escape(category, quote=True)
        cards.append(
            f'<h2 class="cat-title" data-category="{escaped_cat}">'
            f"{escaped_cat}（{len(books)} 本）</h2>"
        )
        cards.append(f'<div class="grid" data-category="{escaped_cat}">')
        for book in books:
            img_html = ""
            if book.image_url:
                img_html = (
                    f'<img src="{book.image_url}" alt="" class="cover">'
                )
            meta_parts = []
            if book.author:
                meta_parts.append(book.author)
            if book.publisher:
                meta_parts.append(book.publisher)
            if book.price:
                meta_parts.append(book.price)
            meta = " / ".join(meta_parts)
            new_badge = ""
            if prev_titles and book.title not in prev_titles:
                new_badge = '<span class="badge-new">NEW</span>'
            date_html = ""
            if book.pub_date:
                date_html = f'<span class="pub-date">{book.pub_date}</span>'
            cards.append(
                f'<div class="card">'
                f"{img_html}"
                f'<div class="card-body">'
                f'<a href="{book.url}" target="_blank" class="book-title">{html.escape(book.title)}</a>'
                f"{new_badge}"
                f'<span class="meta">{html.escape(meta)}</span>'
                f"{date_html}"
                f"</div></div>"
            )
        cards.append("</div>")

    json_script = (
        '<script id="book-data" type="application/json">'
        + html.escape(json.dumps(json_data, ensure_ascii=False), quote=False)
        + "</script>"
    )

    filter_js = """<script>
(function(){
  var btns=document.querySelectorAll('.filter-btn');
  btns.forEach(function(btn){
    btn.addEventListener('click',function(){
      btns.forEach(function(b){b.classList.remove('active')});
      btn.classList.add('active');
      var cat=btn.getAttribute('data-cat');
      document.querySelectorAll('[data-category]').forEach(function(el){
        el.style.display=(cat==='all'||el.getAttribute('data-category')===cat)?'':'none';
      });
    });
  });
})();
</script>"""

    page_html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>書單 {date_str}</title>
<style>
{_css()}
</style>
</head>
<body>
<div class="container">
  <a href="../index.html" class="back-link">&larr; 返回首頁</a>
  <h1>博客來新書書單 — {date_str}</h1>
  <p class="summary">共 {total} 本書</p>
  {filter_bar}
  {"".join(cards)}
</div>
{json_script}
{filter_js}
</body>
</html>"""

    books_dir = output_dir / "books"
    books_dir.mkdir(parents=True, exist_ok=True)
    out_path = books_dir / f"{date_str}.html"
    out_path.write_text(page_html, encoding="utf-8")
    log.info("Generated weekly page: %s", out_path)
    return out_path


def generate_index_page(output_dir: Path) -> Path:
    """掃描 books/ 目錄產生首頁索引。"""
    books_dir = output_dir / "books"
    if not books_dir.exists():
        books_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(books_dir.glob("*.html"), reverse=True)

    rows: list[str] = []
    for f in files:
        date_str = f.stem
        rows.append(
            f'<li><a href="books/{date_str}.html">{date_str} 書單</a></li>'
        )

    if not rows:
        list_html = "<p>目前尚無書單。</p>"
    else:
        list_html = f'<ul class="index-list">{"".join(rows)}</ul>'

    html_content = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>博客來新書書單</title>
<style>
{_css()}
</style>
</head>
<body>
<div class="container">
  <h1>博客來新書書單</h1>
  <p class="summary">歷史書單列表（共 {len(files)} 期）</p>
  <nav class="nav-links"><a href="stats.html">統計</a></nav>
  {list_html}
</div>
</body>
</html>"""

    out_path = output_dir / "index.html"
    out_path.write_text(html_content, encoding="utf-8")
    log.info("Generated index page: %s (%d entries)", out_path, len(files))
    return out_path


def generate_stats_page(output_dir: Path) -> Path:
    """掃描 books/*.html 的 book-data JSON 產生統計頁面。"""
    books_dir = output_dir / "books"
    if not books_dir.exists():
        books_dir.mkdir(parents=True, exist_ok=True)

    weekly_stats: list[tuple[str, int]] = []  # (date_str, count)
    category_totals: dict[str, int] = {}

    for f in sorted(books_dir.glob("*.html")):
        content = f.read_text(encoding="utf-8")
        m = re.search(
            r'<script id="book-data" type="application/json">(.*?)</script>',
            content,
            re.DOTALL,
        )
        if not m:
            continue
        data: dict[str, list[dict]] = json.loads(html.unescape(m.group(1)))
        week_total = 0
        for cat, books in data.items():
            count = len(books)
            week_total += count
            category_totals[cat] = category_totals.get(cat, 0) + count
        weekly_stats.append((f.stem, week_total))

    total_weeks = len(weekly_stats)
    total_books = sum(c for _, c in weekly_stats)
    max_weekly = max((c for _, c in weekly_stats), default=1) or 1

    # 每期書籍數量長條圖
    weekly_bars: list[str] = []
    for date_str, count in weekly_stats:
        pct = count / max_weekly * 100
        weekly_bars.append(
            f'<div class="bar-row">'
            f'<span class="bar-label">{date_str}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div>'
            f'<span class="bar-value">{count}</span>'
            f"</div>"
        )

    # 分類累計排行
    sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    max_cat = sorted_cats[0][1] if sorted_cats else 1
    cat_bars: list[str] = []
    for cat, count in sorted_cats:
        pct = count / max_cat * 100
        cat_bars.append(
            f'<div class="bar-row">'
            f'<span class="bar-label">{html.escape(cat)}</span>'
            f'<div class="bar-track"><div class="bar-fill cat-fill" style="width:{pct:.1f}%"></div></div>'
            f'<span class="bar-value">{count}</span>'
            f"</div>"
        )

    page_html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>書單統計</title>
<style>
{_css()}
{_stats_css()}
</style>
</head>
<body>
<div class="container">
  <a href="index.html" class="back-link">&larr; 返回首頁</a>
  <h1>書單統計</h1>
  <p class="summary">共 {total_weeks} 期，{total_books} 本書</p>

  <h2 class="cat-title">每期書籍數量</h2>
  <div class="chart">{"".join(weekly_bars)}</div>

  <h2 class="cat-title">各分類累計書籍數量</h2>
  <div class="chart">{"".join(cat_bars)}</div>
</div>
</body>
</html>"""

    out_path = output_dir / "stats.html"
    out_path.write_text(page_html, encoding="utf-8")
    log.info("Generated stats page: %s", out_path)
    return out_path


def _stats_css() -> str:
    return """\
.chart{margin-bottom:32px}
.bar-row{display:flex;align-items:center;margin-bottom:6px;gap:8px}
.bar-label{width:120px;flex-shrink:0;font-size:13px;text-align:right;color:#555}
.bar-track{flex:1;background:#eee;border-radius:4px;height:22px;overflow:hidden}
.bar-fill{height:100%;background:#1d3557;border-radius:4px;transition:width .3s}
.bar-fill.cat-fill{background:#e63946}
.bar-value{width:40px;font-size:13px;color:#555}"""


def _css() -> str:
    return """\
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  background:#f5f5f5;color:#333;line-height:1.6}
.container{max-width:960px;margin:0 auto;padding:24px 16px}
h1{margin-bottom:8px;color:#1d3557}
.summary{color:#666;margin-bottom:24px}
.back-link{display:inline-block;margin-bottom:16px;color:#e63946;text-decoration:none;font-weight:600}
.back-link:hover{text-decoration:underline}
.nav-links{margin-bottom:16px}
.nav-links a{color:#e63946;text-decoration:none;font-weight:600;font-size:15px}
.nav-links a:hover{text-decoration:underline}
.cat-title{border-bottom:2px solid #e63946;padding-bottom:4px;margin:32px 0 16px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px;margin-bottom:24px}
.card{display:flex;flex-direction:column;background:#fff;border:1px solid #eee;border-radius:6px;
  padding:10px;text-align:center}
.card .cover{width:100%;max-width:140px;height:auto;margin:0 auto 8px;border-radius:3px}
.card-body{display:flex;flex-direction:column;gap:4px}
.book-title{font-size:14px;color:#1d3557;text-decoration:none;font-weight:bold;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.book-title:hover{text-decoration:underline}
.meta{font-size:12px;color:#666}
.pub-date{font-size:11px;color:#999;margin-top:auto}
.badge-new{display:inline-block;background:#e63946;color:#fff;font-size:11px;
  font-weight:bold;padding:1px 6px;border-radius:3px;margin-left:6px;vertical-align:middle}
.filter-bar{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}
.filter-btn{border:1px solid #1d3557;background:#fff;color:#1d3557;padding:4px 14px;
  border-radius:16px;cursor:pointer;font-size:13px;transition:all .2s}
.filter-btn:hover{background:#1d3557;color:#fff}
.filter-btn.active{background:#1d3557;color:#fff}
.index-list{list-style:none;padding:0}
.index-list li{padding:12px 16px;background:#fff;border:1px solid #eee;
  border-radius:6px;margin-bottom:8px}
.index-list a{color:#1d3557;text-decoration:none;font-weight:600;font-size:16px}
.index-list a:hover{color:#e63946}
@media(max-width:600px){
  .grid{grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px}
  .bar-label{width:80px;font-size:11px}
}"""
