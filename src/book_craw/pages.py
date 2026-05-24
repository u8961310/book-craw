"""靜態 HTML 頁面產生器，供 GitHub Pages 部署。"""

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


def _load_previous_data(output_dir: Path, current_date_str: str) -> dict[str, list[dict]] | None:
    """讀取前一期 HTML 的 book-data JSON，回傳原始資料。"""
    books_dir = output_dir / "books"
    if not books_dir.exists():
        return None
    htmls = sorted(books_dir.glob("*.html"))
    prev_files = [f for f in htmls if f.stem < current_date_str]
    if not prev_files:
        return None
    prev_html = prev_files[-1].read_text(encoding="utf-8")
    m = re.search(
        r'<script id="book-data" type="application/json">(.*?)</script>',
        prev_html,
        re.DOTALL,
    )
    if not m:
        return None
    return json.loads(m.group(1))


def load_previous_urls(output_dir: Path, current_date_str: str) -> set[str]:
    """回傳前一期所有書籍的 URL（去除 query string），用於去重。"""
    data = _load_previous_data(output_dir, current_date_str)
    if not data:
        return set()
    return {b["url"].split("?")[0] for books in data.values() for b in books}


def _load_previous_titles(output_dir: Path, current_date_str: str) -> set[str]:
    """回傳前一期所有書籍的書名集合，用於 NEW 標記。"""
    data = _load_previous_data(output_dir, current_date_str)
    if not data:
        return set()
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

    # 細分類篩選按鈕（依當期實際有書的分類動態渲染）
    grouped_cats: set[str] = set()
    cat_order: list[str] = []  # 依 CATEGORY_GROUPS 順序排
    for _, members in CATEGORY_GROUPS:
        grouped_cats.update(members)
        for c in members:
            if c in books_by_category and books_by_category[c] and c not in cat_order:
                cat_order.append(c)
    # 補上未分群但有書的分類
    for c in books_by_category:
        if books_by_category[c] and c not in grouped_cats and c not in cat_order:
            cat_order.append(c)

    filter_buttons = ['<button class="filter-btn active" data-cat="all">全部</button>']
    for c in cat_order:
        escaped = html.escape(c, quote=True)
        count = len(books_by_category[c])
        filter_buttons.append(
            f'<button class="filter-btn" data-cat="{escaped}">'
            f'{escaped}<span class="filter-count">{count}</span></button>'
        )
    filter_bar = f'<div class="filter-bar">{"".join(filter_buttons)}</div>'

    cards: list[str] = []

    def _render_books(category: str, books: list[Book], group_name: str) -> None:
        escaped_cat = html.escape(category, quote=True)
        escaped_grp = html.escape(group_name, quote=True)
        cards.append(
            f'<h3 class="sub-cat-title" data-cat="{escaped_cat}" data-group="{escaped_grp}">'
            f"{escaped_cat}（{len(books)} 本）</h3>"
        )
        cards.append(f'<div class="grid" data-cat="{escaped_cat}" data-group="{escaped_grp}">')
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

    for group_name, members in CATEGORY_GROUPS:
        group_cats = [(c, books_by_category[c]) for c in members
                      if c in books_by_category and books_by_category[c]]
        if not group_cats:
            continue
        group_total = sum(len(b) for _, b in group_cats)
        escaped_grp = html.escape(group_name, quote=True)
        cards.append(
            f'<h2 class="group-title" data-group="{escaped_grp}">'
            f"{escaped_grp}"
            f'<span class="group-count">共 {group_total} 本</span></h2>'
        )
        for category, books in group_cats:
            _render_books(category, books, group_name)

    # 未分群的分類
    for category, books in books_by_category.items():
        if not books or category in grouped_cats:
            continue
        _render_books(category, books, category)

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
      // 細分類元素：標 data-cat 的 h3 與 grid
      document.querySelectorAll('[data-cat]').forEach(function(el){
        if(el.classList.contains('filter-btn')) return;
        el.style.display=(cat==='all'||el.getAttribute('data-cat')===cat)?'':'none';
      });
      // 群組標題：只在「全部」時顯示，篩單一分類時隱藏
      document.querySelectorAll('.group-title').forEach(function(el){
        el.style.display=(cat==='all')?'':'none';
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

    # 彙總數據
    total_weeks = len(weekly_stats)
    total_books = sum(c for _, c in weekly_stats)
    latest_count = weekly_stats[-1][1] if weekly_stats else 0
    # 計算有書的群組數量
    group_count = sum(
        1 for _, members in CATEGORY_GROUPS
        if any(c in category_totals for c in members)
    )

    # --- 1. 摘要卡片（頂部 4 個數字卡片橫排） ---
    summary_cards = (
        '<div class="stats-cards">'
        f'<div class="stat-card"><span class="stat-value">{total_weeks}</span>'
        f'<span class="stat-label">總期數</span></div>'
        f'<div class="stat-card"><span class="stat-value">{total_books}</span>'
        f'<span class="stat-label">總書數</span></div>'
        f'<div class="stat-card"><span class="stat-value">{latest_count}</span>'
        f'<span class="stat-label">本期新增</span></div>'
        f'<div class="stat-card"><span class="stat-value">{group_count}</span>'
        f'<span class="stat-label">群組數量</span></div>'
        '</div>'
    )

    # --- 2. 群組級統計長條圖（用 CATEGORY_GROUPS 聚合各群組合計） ---
    group_colors = ["#1d3557", "#e63946", "#457b9d", "#2a9d8f", "#e9c46a", "#f4a261"]
    group_totals: list[tuple[str, int, str]] = []  # (群組名, 合計, 顏色)
    for idx, (group_name, members) in enumerate(CATEGORY_GROUPS):
        gtotal = sum(category_totals.get(c, 0) for c in members)
        if gtotal > 0:
            color = group_colors[idx % len(group_colors)]
            group_totals.append((group_name, gtotal, color))

    max_group = max((t for _, t, _ in group_totals), default=1) or 1
    group_bars: list[str] = []
    for gname, gtotal, gcolor in group_totals:
        pct = gtotal / max_group * 100
        group_bars.append(
            f'<div class="bar-row">'
            f'<span class="bar-label">{html.escape(gname)}</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%;background:{gcolor}"></div></div>'
            f'<span class="bar-value">{gtotal}</span>'
            f"</div>"
        )

    # --- 3. 群組內子分類排行（按群組分區，跳過只有 1 個子分類的群組） ---
    group_sections: list[str] = []
    for idx, (group_name, members) in enumerate(CATEGORY_GROUPS):
        # 收集該群組內有資料的子分類
        sub_cats = [(c, category_totals[c]) for c in members if c in category_totals and category_totals[c] > 0]
        if not sub_cats or len(sub_cats) <= 1:
            continue
        # 依數量降冪排序，長條比例相對於群組內最大值
        sub_cats.sort(key=lambda x: x[1], reverse=True)
        local_max = sub_cats[0][1]
        color = group_colors[idx % len(group_colors)]
        bars: list[str] = []
        for cat, count in sub_cats:
            pct = count / local_max * 100
            bars.append(
                f'<div class="bar-row">'
                f'<span class="bar-label">{html.escape(cat)}</span>'
                f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%;background:{color}"></div></div>'
                f'<span class="bar-value">{count}</span>'
                f"</div>"
            )
        group_sections.append(
            f'<h3 class="group-title">{html.escape(group_name)}</h3>'
            f'<div class="chart">{"".join(bars)}</div>'
        )

    # --- 4. 每期趨勢折線圖（SVG polyline，只有 1 期時退化成長條圖） ---
    trend_html: str
    if len(weekly_stats) <= 1:
        # 只有 1 期時改用長條圖顯示
        bars_list: list[str] = []
        for date_str, count in weekly_stats:
            bars_list.append(
                f'<div class="bar-row">'
                f'<span class="bar-label">{date_str}</span>'
                f'<div class="bar-track"><div class="bar-fill" style="width:100%"></div></div>'
                f'<span class="bar-value">{count}</span>'
                f"</div>"
            )
        trend_html = f'<div class="chart">{"".join(bars_list)}</div>'
    else:
        # 多期時用 SVG 折線圖
        svg_w, svg_h = 800, 300
        pad_l, pad_r, pad_t, pad_b = 50, 30, 30, 60  # 左右上下邊距
        chart_w = svg_w - pad_l - pad_r
        chart_h = svg_h - pad_t - pad_b
        n = len(weekly_stats)
        max_val = max(c for _, c in weekly_stats) or 1

        # 計算各資料點的 SVG 座標
        points: list[tuple[float, float]] = []
        for i, (_, count) in enumerate(weekly_stats):
            x = pad_l + (i / (n - 1)) * chart_w
            y = pad_t + chart_h - (count / max_val) * chart_h
            points.append((x, y))

        polyline_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)

        # Y 軸水平格線（分 4 等份）
        grid_lines: list[str] = []
        for j in range(5):
            gy = pad_t + chart_h * j / 4
            gval = int(max_val * (4 - j) / 4)
            grid_lines.append(
                f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{svg_w - pad_r}" y2="{gy:.1f}" stroke="#e0e0e0" stroke-dasharray="4"/>'
                f'<text x="{pad_l - 8}" y="{gy:.1f}" text-anchor="end" dy="4" fill="#999" font-size="11">{gval}</text>'
            )

        # 資料點（圓點）、數值標籤、X 軸日期標籤
        dots: list[str] = []
        labels: list[str] = []
        x_labels: list[str] = []
        for i, ((date_str, count), (x, y)) in enumerate(zip(weekly_stats, points)):
            dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#e63946"/>')
            labels.append(f'<text x="{x:.1f}" y="{y:.1f}" dy="-10" text-anchor="middle" fill="#333" font-size="11" font-weight="bold">{count}</text>')
            # X 軸日期標籤（旋轉 -35° 避免重疊）
            x_labels.append(f'<text x="{x:.1f}" y="{svg_h - 5}" text-anchor="end" fill="#666" font-size="10" transform="rotate(-35 {x:.1f} {svg_h - 5})">{date_str}</text>')

        trend_html = (
            f'<div class="trend-chart">'
            f'<svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg">'
            f'{"".join(grid_lines)}'
            f'<polyline points="{polyline_pts}" fill="none" stroke="#1d3557" stroke-width="2.5" stroke-linejoin="round"/>'
            f'{"".join(dots)}{"".join(labels)}{"".join(x_labels)}'
            f'</svg></div>'
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

  {summary_cards}

  <h2 class="cat-title">每期書籍趨勢</h2>
  {trend_html}

  <h2 class="cat-title">各群組累計書籍數量</h2>
  <div class="chart">{"".join(group_bars)}</div>

  <h2 class="cat-title">群組內子分類排行</h2>
  {"".join(group_sections)}
</div>
</body>
</html>"""

    out_path = output_dir / "stats.html"
    out_path.write_text(page_html, encoding="utf-8")
    log.info("Generated stats page: %s", out_path)
    return out_path


def _stats_css() -> str:
    """統計頁面專用 CSS：摘要卡片、長條圖、SVG 折線圖、RWD 手機版。"""
    return """\
.stats-cards{display:flex;gap:16px;margin-bottom:32px;flex-wrap:wrap}
.stat-card{flex:1;min-width:120px;background:#fff;border:1px solid #eee;border-radius:8px;
  padding:20px 16px;text-align:center;display:flex;flex-direction:column;gap:4px}
.stat-value{font-size:32px;font-weight:bold;color:#1d3557;line-height:1.2}
.stat-label{font-size:13px;color:#888}
.chart{margin-bottom:32px}
.bar-row{display:flex;align-items:center;margin-bottom:6px;gap:8px}
.bar-label{width:160px;flex-shrink:0;font-size:13px;text-align:right;color:#555}
.bar-track{flex:1;background:#eee;border-radius:4px;height:22px;overflow:hidden}
.bar-fill{height:100%;background:#1d3557;border-radius:4px;transition:width .3s}
.bar-value{width:48px;font-size:13px;color:#555}
.trend-chart{margin-bottom:32px}
.trend-chart svg{width:100%;height:auto;background:#fff;border:1px solid #eee;border-radius:8px}
@media(max-width:600px){
  .stats-cards{display:grid;grid-template-columns:1fr 1fr;gap:10px}
  .stat-value{font-size:24px}
  .bar-label{width:100px;font-size:11px}
}"""


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
.group-title{background:#1d3557;color:#fff;padding:10px 16px;border-radius:6px;margin:32px 0 12px;font-size:18px}
.group-count{font-size:13px;color:#a8dadc;margin-left:10px;font-weight:normal}
.sub-cat-title{border-bottom:2px solid #e63946;padding-bottom:4px;margin:20px 0 12px;font-size:16px}
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
.filter-btn{display:inline-flex;align-items:center;gap:6px;
  border:1px solid #1d3557;background:#fff;color:#1d3557;padding:4px 12px;
  border-radius:16px;cursor:pointer;font-size:13px;transition:all .2s}
.filter-btn:hover{background:#1d3557;color:#fff}
.filter-btn.active{background:#1d3557;color:#fff}
.filter-count{display:inline-block;background:rgba(29,53,87,.12);color:inherit;
  font-size:11px;padding:1px 6px;border-radius:10px;line-height:1.4}
.filter-btn:hover .filter-count,.filter-btn.active .filter-count{background:rgba(255,255,255,.25)}
.index-list{list-style:none;padding:0}
.index-list li{padding:12px 16px;background:#fff;border:1px solid #eee;
  border-radius:6px;margin-bottom:8px}
.index-list a{color:#1d3557;text-decoration:none;font-weight:600;font-size:16px}
.index-list a:hover{color:#e63946}
@media(max-width:600px){
  .grid{grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px}
  .bar-label{width:80px;font-size:11px}
}"""
