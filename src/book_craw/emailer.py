"""HTML 郵件產生與 Gmail SMTP 寄送。"""

from __future__ import annotations

import html
import logging
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from book_craw.config import CATEGORY_GROUPS
from book_craw.scraper import Book

log = logging.getLogger(__name__)

PAGES_BASE_URL = "https://u8961310.github.io/book-craw"
MAX_BOOKS_PER_CATEGORY = 5

# 與書單頁同一套「書店紙本風」色票；文字對比皆 ≥ 4.5:1
_TEXT = "#2b2118"
_MUTED = "#5c4a3a"
_ACCENT = "#a8201a"
_LINE = "#e6ddd0"


def _full_list_url() -> str:
    """Return the URL for today's full book list on GitHub Pages."""
    return f"{PAGES_BASE_URL}/books/{date.today().isoformat()}.html"


def _render_category(category: str, books: list[Book], full_url: str) -> list[str]:
    parts = [
        f"<h2 style='border-bottom:2px solid {_ACCENT};padding-bottom:4px;"
        f"font-size:16px;margin:20px 0 8px;color:{_TEXT};'>"
        f"{html.escape(category)}（{len(books)} 本）</h2>"
    ]
    shown = books[:MAX_BOOKS_PER_CATEGORY]
    for book in shown:
        meta = " / ".join(p for p in (book.author, book.price) if p)
        parts.append(
            f"<div style='margin:8px 0;padding:6px 0;border-bottom:1px solid {_LINE};'>"
            f"<a href='{html.escape(book.url, quote=True)}' style='font-size:14px;color:{_TEXT};"
            f"text-decoration:none;font-weight:bold;'>{html.escape(book.title)}</a><br>"
            f"<span style='font-size:13px;color:{_MUTED};'>{html.escape(meta)}</span>"
            f"</div>"
        )
    remaining = len(books) - len(shown)
    if remaining > 0:
        parts.append(
            f"<p style='margin:8px 0 16px;'>"
            f"<a href='{full_url}' style='color:{_ACCENT};font-size:13px;'>"
            f"還有 {remaining} 本 →</a></p>"
        )
    return parts


def build_html(books_by_category: dict[str, list[Book]], warnings: list[str] | None = None) -> str:
    """Build an HTML email body from scraped books grouped by category."""
    total = sum(len(v) for v in books_by_category.values())
    full_url = _full_list_url()

    parts: list[str] = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'></head>",
        f"<body style='font-family:-apple-system,\"PingFang TC\",\"Microsoft JhengHei\",sans-serif;"
        f"max-width:720px;margin:auto;padding:16px;color:{_TEXT};background:#fffdf9;'>",
        f"<h1 style='color:{_TEXT};margin-bottom:4px;font-size:22px;'>📚 博客來新書通知</h1>",
        f"<p style='color:{_MUTED};margin:0 0 12px;'>本週共 {total} 本新書</p>",
    ]

    if warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in warnings)
        parts.append(
            "<div style='background:#fff4dc;border:1px solid #c98a12;border-radius:6px;"
            f"padding:10px 14px;margin-bottom:16px;font-size:14px;color:{_TEXT};'>"
            f"<strong>本期爬取異常</strong><ul style='margin:4px 0 0 18px;padding:0;'>{items}</ul></div>"
        )

    parts.append(
        f"<p style='margin-bottom:20px;'>"
        f"<a href='{full_url}' "
        f"style='display:inline-block;background:{_ACCENT};color:#fff;padding:10px 22px;"
        f"border-radius:6px;text-decoration:none;font-weight:bold;'>查看完整書單（可搜尋、篩選）</a></p>"
    )

    grouped_cats: set[str] = set()
    for _, members in CATEGORY_GROUPS:
        grouped_cats.update(members)

    ordered = [c for _, members in CATEGORY_GROUPS for c in members]
    ordered += [c for c in books_by_category if c not in grouped_cats]
    seen: set[str] = set()
    for category in ordered:
        if category in seen or not books_by_category.get(category):
            continue
        seen.add(category)
        parts.extend(_render_category(category, books_by_category[category], full_url))

    parts.append(
        f"<hr style='border:none;border-top:1px solid {_LINE};margin:24px 0 12px;'>"
        f"<p style='font-size:13px;color:{_MUTED};text-align:center;'>"
        f"<a href='{PAGES_BASE_URL}/index.html' style='color:{_MUTED};'>歷史書單</a>"
        f"</p>"
    )
    parts.append("</body></html>")
    return "\n".join(parts)


def send_email(html: str, subject: str = "博客來新書通知") -> None:
    """Send HTML email via Gmail SMTP."""
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pass = os.environ["GMAIL_APP_PASSWORD"]
    email_to = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = email_to
    msg.attach(MIMEText(html, "html", "utf-8"))

    log.info("Sending email to %s ...", email_to)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, email_to.split(","), msg.as_string())
    log.info("Email sent successfully.")
