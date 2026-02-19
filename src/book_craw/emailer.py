"""HTML 郵件產生與 Gmail SMTP 寄送。"""

from __future__ import annotations

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


def _full_list_url() -> str:
    """Return the URL for today's full book list on GitHub Pages."""
    return f"{PAGES_BASE_URL}/books/{date.today().isoformat()}.html"


def build_html(books_by_category: dict[str, list[Book]]) -> str:
    """Build an HTML email body from scraped books grouped by category."""
    total = sum(len(v) for v in books_by_category.values())
    full_url = _full_list_url()

    parts: list[str] = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'></head>",
        "<body style='font-family:sans-serif;max-width:800px;margin:auto;padding:16px;'>",
        "<h1 style='color:#333;margin-bottom:4px;'>📚 博客來新書通知</h1>",
        f"<p style='color:#666;margin-bottom:12px;'>本週共 {total} 本新書</p>",
        f"<p style='margin-bottom:20px;'>"
        f"<a href='{full_url}' "
        f"style='display:inline-block;background:#e63946;color:#fff;padding:8px 20px;"
        f"border-radius:4px;text-decoration:none;font-weight:bold;'>查看完整書單</a></p>",
    ]

    # Collect categories not in any group (fallback)
    grouped_cats: set[str] = set()
    for _, members in CATEGORY_GROUPS:
        grouped_cats.update(members)

    for group_name, members in CATEGORY_GROUPS:
        # Collect sub-categories in this group that have books
        group_cats = [(c, books_by_category[c]) for c in members
                      if c in books_by_category and books_by_category[c]]
        if not group_cats:
            continue

        group_total = sum(len(b) for _, b in group_cats)
        parts.append(
            f"<div style='margin:28px 0 12px;padding:8px 12px;"
            f"background:#1d3557;border-radius:4px;'>"
            f"<span style='color:#fff;font-size:16px;font-weight:bold;'>"
            f"{group_name}</span>"
            f"<span style='color:#a8dadc;font-size:13px;margin-left:8px;'>"
            f"共 {group_total} 本</span></div>"
        )

        for category, books in group_cats:
            parts.append(
                f"<h2 style='border-bottom:2px solid #e63946;padding-bottom:4px;"
                f"font-size:16px;margin-top:12px;'>"
                f"{category}（{len(books)} 本）</h2>"
            )
            shown = books[:MAX_BOOKS_PER_CATEGORY]
            for book in shown:
                meta_parts = []
                if book.author:
                    meta_parts.append(book.author)
                if book.price:
                    meta_parts.append(book.price)
                meta = " / ".join(meta_parts)

                parts.append(
                    f"<div style='margin:8px 0;padding:6px 0;border-bottom:1px solid #f0f0f0;'>"
                    f"<a href='{book.url}' style='font-size:14px;color:#1d3557;"
                    f"text-decoration:none;font-weight:bold;'>{book.title}</a><br>"
                    f"<span style='font-size:12px;color:#888;'>{meta}</span>"
                    f"</div>"
                )
            remaining = len(books) - len(shown)
            if remaining > 0:
                parts.append(
                    f"<p style='margin:8px 0 16px;'>"
                    f"<a href='{full_url}' style='color:#e63946;font-size:13px;'>"
                    f"還有 {remaining} 本 →</a></p>"
                )

    # Any ungrouped categories
    for category, books in books_by_category.items():
        if not books or category in grouped_cats:
            continue
        parts.append(
            f"<h2 style='border-bottom:2px solid #e63946;padding-bottom:4px;font-size:16px;'>"
            f"{category}（{len(books)} 本）</h2>"
        )
        shown = books[:MAX_BOOKS_PER_CATEGORY]
        for book in shown:
            meta_parts = []
            if book.author:
                meta_parts.append(book.author)
            if book.price:
                meta_parts.append(book.price)
            meta = " / ".join(meta_parts)
            parts.append(
                f"<div style='margin:8px 0;padding:6px 0;border-bottom:1px solid #f0f0f0;'>"
                f"<a href='{book.url}' style='font-size:14px;color:#1d3557;"
                f"text-decoration:none;font-weight:bold;'>{book.title}</a><br>"
                f"<span style='font-size:12px;color:#888;'>{meta}</span>"
                f"</div>"
            )
        remaining = len(books) - len(shown)
        if remaining > 0:
            parts.append(
                f"<p style='margin:8px 0 16px;'>"
                f"<a href='{full_url}' style='color:#e63946;font-size:13px;'>"
                f"還有 {remaining} 本 →</a></p>"
            )

    parts.append(
        f"<hr style='border:none;border-top:1px solid #eee;margin:24px 0 12px;'>"
        f"<p style='font-size:12px;color:#aaa;text-align:center;'>"
        f"<a href='{PAGES_BASE_URL}/index.html' style='color:#aaa;'>歷史書單</a>"
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
