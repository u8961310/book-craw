"""靜態 HTML 頁面產生器，供 GitHub Pages 部署。"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from book_craw.scraper import Book

log = logging.getLogger(__name__)


def generate_weekly_page(
    books_by_category: dict[str, list[Book]],
    page_date: date,
    output_dir: Path,
) -> Path:
    """產生當週書單 HTML，回傳輸出檔案路徑。"""
    total = sum(len(v) for v in books_by_category.values())
    date_str = page_date.isoformat()

    cards: list[str] = []
    for category, books in books_by_category.items():
        if not books:
            continue
        cards.append(
            f'<h2 class="cat-title">{category}（{len(books)} 本）</h2>'
        )
        for book in books:
            img_html = ""
            if book.image_url:
                img_html = (
                    f'<img src="{book.image_url}" alt="" class="cover">'
                )
            meta_parts = []
            if book.pub_date:
                meta_parts.append(book.pub_date)
            if book.author:
                meta_parts.append(book.author)
            if book.publisher:
                meta_parts.append(book.publisher)
            if book.price:
                meta_parts.append(book.price)
            meta = " / ".join(meta_parts)
            cards.append(
                f'<div class="card">'
                f"{img_html}"
                f"<div class=\"card-body\">"
                f'<a href="{book.url}" target="_blank" class="book-title">{book.title}</a>'
                f'<span class="meta">{meta}</span>'
                f"</div></div>"
            )

    html = f"""<!DOCTYPE html>
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
  <h1>📚 博客來新書書單 — {date_str}</h1>
  <p class="summary">共 {total} 本書</p>
  {"".join(cards)}
</div>
</body>
</html>"""

    books_dir = output_dir / "books"
    books_dir.mkdir(parents=True, exist_ok=True)
    out_path = books_dir / f"{date_str}.html"
    out_path.write_text(html, encoding="utf-8")
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
        date_str = f.stem  # e.g. "2026-02-15"
        rows.append(
            f'<li><a href="books/{date_str}.html">{date_str} 書單</a></li>'
        )

    if not rows:
        list_html = "<p>目前尚無書單。</p>"
    else:
        list_html = f'<ul class="index-list">{"".join(rows)}</ul>'

    html = f"""<!DOCTYPE html>
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
  <h1>📚 博客來新書書單</h1>
  <p class="summary">歷史書單列表（共 {len(files)} 期）</p>
  {list_html}
</div>
</body>
</html>"""

    out_path = output_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    log.info("Generated index page: %s (%d entries)", out_path, len(files))
    return out_path


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
.cat-title{border-bottom:2px solid #e63946;padding-bottom:4px;margin:32px 0 16px}
.card{display:flex;background:#fff;border:1px solid #eee;border-radius:6px;
  padding:12px;margin-bottom:12px;gap:12px}
.card .cover{width:80px;height:auto;flex-shrink:0;border-radius:3px}
.card-body{display:flex;flex-direction:column;gap:4px}
.book-title{font-size:15px;color:#1d3557;text-decoration:none;font-weight:bold}
.book-title:hover{text-decoration:underline}
.meta{font-size:13px;color:#666}
.index-list{list-style:none;padding:0}
.index-list li{padding:12px 16px;background:#fff;border:1px solid #eee;
  border-radius:6px;margin-bottom:8px}
.index-list a{color:#1d3557;text-decoration:none;font-weight:600;font-size:16px}
.index-list a:hover{color:#e63946}
@media(max-width:600px){
  .card{flex-direction:column;align-items:flex-start}
  .card .cover{width:60px}
}"""
