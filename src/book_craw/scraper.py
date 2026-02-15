"""博客來新書/預購書爬蟲。"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date, timedelta

import httpx
from bs4 import BeautifulSoup

from book_craw.config import (
    CATEGORIES,
    NEW_BOOKS_URL_TEMPLATE,
    PREORDER_URL,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

log = logging.getLogger(__name__)


@dataclass
class Book:
    title: str
    url: str
    author: str = ""
    publisher: str = ""
    price: str = ""
    image_url: str = ""
    category: str = ""
    pub_date: str = ""  # e.g. "2026-02-13"


def fetch_page(url: str) -> str:
    """GET a page and return decoded HTML."""
    headers = {"User-Agent": USER_AGENT}
    resp = httpx.get(url, headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def _parse_recent_books(html: str, category: str = "") -> list[Book]:
    """Parse the '近期新書' section which contains pub dates."""
    soup = BeautifulSoup(html, "lxml")
    books: list[Book] = []

    # Find the 近期新書 section
    h3 = None
    for tag in soup.find_all("h3"):
        if "近期新書" in tag.get_text():
            h3 = tag
            break
    if h3 is None:
        log.warning("Could not find '近期新書' section (category=%s)", category)
        return books

    section = h3.find_parent("div", class_=re.compile(r"mod_a"))
    if section is None:
        return books

    for item_div in section.find_all("div", class_="item"):
        # Title & URL
        h4 = item_div.find("h4")
        if not h4:
            continue
        link = h4.find("a", href=re.compile(r"/products/"))
        if not link:
            continue
        title = link.get_text(strip=True)
        href = link["href"]
        if not href.startswith("http"):
            href = "https://www.books.com.tw" + href

        # Author
        author = ""
        author_link = item_div.find("a", href=re.compile(r"adv_author"))
        if author_link:
            author = author_link.get_text(strip=True)

        # Publisher & pub date from <li class="info">
        publisher = ""
        pub_date = ""
        info_li = item_div.find("li", class_="info")
        if info_li:
            pub_link = info_li.find("a", href=re.compile(r"pubid"))
            if pub_link:
                publisher = pub_link.get_text(strip=True)
            info_text = info_li.get_text()
            m = re.search(r"出版日期：(\d{4}-\d{2}-\d{2})", info_text)
            if m:
                pub_date = m.group(1)

        # Price
        price = ""
        price_box = item_div.find("div", class_="price_box") or item_div
        price_text = price_box.get_text()
        m = re.search(r"(\d+)\s*折\s*(\d+)\s*元", price_text)
        if m:
            price = f"{m.group(1)}折 {m.group(2)}元"

        # Cover image
        image_url = ""
        img = item_div.find("img", class_="cover")
        if img and img.get("src"):
            image_url = img["src"]
            if image_url.startswith("//"):
                image_url = "https:" + image_url

        books.append(
            Book(
                title=title,
                url=href,
                author=author,
                publisher=publisher,
                price=price,
                image_url=image_url,
                category=category,
                pub_date=pub_date,
            )
        )

    log.info("Parsed %d books from 近期新書 (category=%s)", len(books), category)
    return books


def _filter_recent(books: list[Book], days: int = 7) -> list[Book]:
    """Keep only books published within the last N days."""
    cutoff = date.today() - timedelta(days=days)
    result = []
    for b in books:
        if not b.pub_date:
            continue
        try:
            pub = date.fromisoformat(b.pub_date)
        except ValueError:
            continue
        if pub >= cutoff:
            result.append(b)
    log.info("Filtered to %d books published after %s", len(result), cutoff)
    return result


def scrape_category(code: str, recent_days: int = 7) -> list[Book]:
    """Scrape new books for a single category, filtered to last N days."""
    name = CATEGORIES.get(code, code)
    url = NEW_BOOKS_URL_TEMPLATE.format(code=code)
    log.info("Fetching category %s (%s): %s", code, name, url)
    html = fetch_page(url)
    books = _parse_recent_books(html, category=name)
    books = _filter_recent(books, days=recent_days)
    return books


def scrape_preorders() -> list[Book]:
    """Scrape pre-order books (no date filter)."""
    log.info("Fetching pre-orders: %s", PREORDER_URL)
    html = fetch_page(PREORDER_URL)
    return _parse_recent_books(html, category="預購書")


def scrape_all(
    categories: list[str] | None = None,
    include_preorders: bool = True,
    recent_days: int = 7,
) -> dict[str, list[Book]]:
    """Scrape all (or selected) categories plus pre-orders."""
    codes = categories or list(CATEGORIES.keys())
    result: dict[str, list[Book]] = {}

    for code in codes:
        name = CATEGORIES.get(code, code)
        try:
            result[name] = scrape_category(code, recent_days=recent_days)
        except Exception:
            log.exception("Failed to scrape category %s (%s)", code, name)
            result[name] = []
        time.sleep(REQUEST_DELAY)

    if include_preorders:
        try:
            result["預購書"] = scrape_preorders()
        except Exception:
            log.exception("Failed to scrape pre-orders")
            result["預購書"] = []

    total = sum(len(v) for v in result.values())
    log.info("Total: %d books across %d categories", total, len(result))
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    books = scrape_category("19")
    for b in books[:10]:
        print(f"  {b.pub_date} | {b.title} | {b.author} | {b.publisher} | {b.price}")
    print(f"... {len(books)} books within last 7 days in 電腦資訊")
