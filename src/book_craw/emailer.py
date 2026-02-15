"""HTML 郵件產生與 Gmail SMTP 寄送。"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from book_craw.scraper import Book

log = logging.getLogger(__name__)


def build_html(books_by_category: dict[str, list[Book]]) -> str:
    """Build an HTML email body from scraped books grouped by category."""
    parts: list[str] = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'></head>",
        "<body style='font-family:sans-serif;max-width:800px;margin:auto;'>",
        "<h1 style='color:#333;'>📚 博客來新書通知</h1>",
        "<p style='margin-bottom:16px;'>"
        "<a href='https://u8961310.github.io/book-craw/index.html' "
        "style='color:#e63946;font-weight:bold;'>線上瀏覽歷史書單</a></p>",
    ]

    for category, books in books_by_category.items():
        if not books:
            continue
        parts.append(
            f"<h2 style='border-bottom:2px solid #e63946;padding-bottom:4px;'>"
            f"{category}（{len(books)} 本）</h2>"
        )
        for book in books:
            img_html = ""
            if book.image_url:
                img_html = (
                    f"<img src='{book.image_url}' alt='' "
                    f"style='width:80px;height:auto;margin-right:12px;float:left;'>"
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

            parts.append(
                f"<div style='overflow:hidden;margin-bottom:16px;padding:8px;"
                f"border:1px solid #eee;border-radius:4px;'>"
                f"{img_html}"
                f"<div>"
                f"<a href='{book.url}' style='font-size:15px;color:#1d3557;"
                f"text-decoration:none;font-weight:bold;'>{book.title}</a><br>"
                f"<span style='font-size:13px;color:#666;'>{meta}</span>"
                f"</div></div>"
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
