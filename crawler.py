#!/usr/bin/env python3
import argparse
import json
import os
import time
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


BASE_URL = "https://foolad24.com"
LIST_PATH = "/supplier-list"


@dataclass
class SupplierRow:
    title: str
    ceo: str
    user_code: str
    membership_date: str
    user_type: str
    address: str
    trade: str
    service: str
    start_year: str
    registration_number: str
    national_id: str
    economic_code: str
    description: str
    website: str
    email: str
    phone: str
    office_address: str
    office_phone: str
    office_description: str
    warehouse_address: str
    warehouse_description: str
    detail_url: str
    scraped_at: str


def _make_session(cookie_header: str = "") -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
            )
        }
    )
    if cookie_header:
        session.headers["Cookie"] = cookie_header
    return session


def _get_soup(session: requests.Session, url: str, retries: int = 3) -> BeautifulSoup:
    last_exc: Optional[Exception] = None
    for _ in range(max(1, retries)):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            time.sleep(2)
    if last_exc:
        raise last_exc
    raise RuntimeError("Failed to fetch URL")


def _extract_title_and_url(card: BeautifulSoup) -> Optional[Dict[str, str]]:
    link = card.select_one(
        "div.col-md-9.supplier-card_info > div > div:nth-child(1) > h3 > a"
    )
    if not link:
        return None
    title = link.get_text(strip=True)
    href = link.get("href", "").strip()
    if not title or not href:
        return None
    return {"title": title, "detail_url": urljoin(BASE_URL, href)}


def _extract_ceo(card: BeautifulSoup) -> str:
    ceo = card.select_one(
        "div.col-md-9.supplier-card_info > div > div:nth-child(1) > h4"
    )
    return ceo.get_text(strip=True) if ceo else ""


def _extract_text(card: BeautifulSoup, selector: str) -> str:
    node = card.select_one(selector)
    return node.get_text(" ", strip=True) if node else ""


def _extract_span_list(card: BeautifulSoup, selector: str) -> str:
    node = card.select_one(selector)
    if not node:
        return ""
    spans = [s.get_text(strip=True) for s in node.select("span") if s.get_text(strip=True)]
    if spans:
        return ", ".join(spans)
    return node.get_text(" ", strip=True)


def _extract_text_from_soup(soup: BeautifulSoup, selector: str) -> str:
    node = soup.select_one(selector)
    return node.get_text(" ", strip=True) if node else ""


def _extract_link_text(soup: BeautifulSoup, selector: str) -> str:
    node = soup.select_one(selector)
    if not node:
        return ""
    return node.get("href", "").strip() or node.get_text(" ", strip=True)


def _extract_card_fields(card: BeautifulSoup) -> Dict[str, str]:
    base = "div.col-md-9.supplier-card_info > div"
    return {
        "user_code": _extract_text(card, f"{base} > div:nth-child(2) > p"),
        "membership_date": _extract_text(card, f"{base} > div:nth-child(3) > p"),
        "user_type": _extract_text(card, f"{base} > div:nth-child(4) > p"),
        "address": _extract_text(card, f"{base} > div:nth-child(5) > p"),
        "trade": _extract_span_list(
            card, f"{base} > div.col-md-12.supplier_col > p"
        ),
        "service": _extract_span_list(card, f"{base} > div:nth-child(7) > p"),
    }


def _extract_info_fields(soup: BeautifulSoup) -> Dict[str, str]:
    return {
        "start_year": _extract_text_from_soup(
            soup, "#profile-basic > div > div > div > div:nth-child(5) > div > p"
        ),
        "registration_number": _extract_text_from_soup(
            soup, "#profile-basic > div > div > div > div:nth-child(7) > div > p"
        ),
        "national_id": _extract_text_from_soup(
            soup, "#profile-basic > div > div > div > div:nth-child(4) > div > p"
        ),
        "economic_code": _extract_text_from_soup(
            soup, "#profile-basic > div > div > div > div:nth-child(6) > div > p"
        ),
        "description": _extract_text_from_soup(
            soup,
            "#profile-basic > div > div > div > div.col-md-12.align-items-baseline > div > p",
        ),
        "website": _extract_link_text(
            soup, "#profile-social > div > div > div > div:nth-child(1) > div > p > a"
        ),
        "email": _extract_text_from_soup(
            soup, "#profile-social > div > div > div > div:nth-child(2) > div > p"
        ),
        "phone": _extract_link_text(
            soup, "#profile-social > div > div > div > div:nth-child(3) > div > p > a"
        ),
        "office_address": _extract_text_from_soup(
            soup,
            "#profile-addresses > div.profile-card.card.overflow-hidden > div > "
            "div:nth-child(1) > div:nth-child(1) > div > p",
        ),
        "office_phone": _extract_text_from_soup(
            soup,
            "#profile-addresses > div.profile-card.card.overflow-hidden > div > "
            "div:nth-child(1) > div.col-md-6 > div > p",
        ),
        "office_description": _extract_text_from_soup(
            soup,
            "#profile-addresses > div.profile-card.card.overflow-hidden > div > "
            "div:nth-child(1) > div:nth-child(3) > div > p",
        ),
        "warehouse_address": _extract_text_from_soup(
            soup,
            "#profile-addresses > div.profile-card.card.overflow-hidden > div > "
            "div.profile-card__grid.row.py-3.odd-row > div:nth-child(1) > div > p",
        ),
        "warehouse_description": _extract_text_from_soup(
            soup,
            "#profile-addresses > div.profile-card.card.overflow-hidden > div > "
            "div.profile-card__grid.row.py-3.odd-row > div:nth-child(2) > div > p",
        ),
    }


def _iter_list_pages(
    session: requests.Session, start_url: str, start_page: int, end_page: int
) -> Iterable[Dict[str, str]]:
    if start_page > 0 and end_page > 0:
        for page in range(start_page, end_page + 1):
            yield {"page": str(page), "url": f"{start_url}?page={page}"}
        return

    if start_page > 0:
        next_url = f"{start_url}?page={start_page}"
        page_index = start_page
    else:
        next_url = start_url
        page_index = 1
    seen = set()
    while next_url and next_url not in seen:
        seen.add(next_url)
        soup = _get_soup(session, next_url)
        parsed = urlparse(next_url)
        page_qs = parse_qs(parsed.query).get("page", [])
        page_value = page_qs[0] if page_qs else str(page_index)
        yield {"page": page_value, "url": next_url}
        next_link = soup.select_one("ul.pagination li a[rel='next']")
        if next_link and next_link.get("href"):
            next_url = urljoin(BASE_URL, next_link["href"])
        else:
            next_url = ""
        page_index += 1


def _load_checkpoint(path: str) -> Dict[str, str]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_checkpoint(path: str, page: str, url: str) -> None:
    payload = {"last_page": page, "last_url": url, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _load_existing_rows(path: str) -> List[SupplierRow]:
    if not os.path.exists(path):
        return []
    df = pd.read_excel(path)
    rows: List[SupplierRow] = []
    for _, row in df.iterrows():
        data = row.to_dict()
        rows.append(
            SupplierRow(
                title=str(data.get("title", "")),
                ceo=str(data.get("ceo", "")),
                user_code=str(data.get("user_code", "")),
                membership_date=str(data.get("membership_date", "")),
                user_type=str(data.get("user_type", "")),
                address=str(data.get("address", "")),
                trade=str(data.get("trade", "")),
                service=str(data.get("service", "")),
                start_year=str(data.get("start_year", "")),
                registration_number=str(data.get("registration_number", "")),
                national_id=str(data.get("national_id", "")),
                economic_code=str(data.get("economic_code", "")),
                description=str(data.get("description", "")),
                website=str(data.get("website", "")),
                email=str(data.get("email", "")),
                phone=str(data.get("phone", "")),
                office_address=str(data.get("office_address", "")),
                office_phone=str(data.get("office_phone", "")),
                office_description=str(data.get("office_description", "")),
                warehouse_address=str(data.get("warehouse_address", "")),
                warehouse_description=str(data.get("warehouse_description", "")),
                detail_url=str(data.get("detail_url", "")),
                scraped_at=str(data.get("scraped_at", "")),
            )
        )
    return rows


def crawl_pages(
    delay_seconds: float,
    start_page: int,
    end_page: int,
    cookie_header: str,
    min_page: int,
    initial_rows: List[SupplierRow],
) -> Iterable[Dict[str, object]]:
    session = _make_session(cookie_header)
    items: List[SupplierRow] = list(initial_rows)
    start_url = urljoin(BASE_URL, LIST_PATH)

    for page_info in _iter_list_pages(session, start_url, start_page, end_page):
        page_num = int(page_info["page"])
        if min_page and page_num < min_page:
            continue
        list_url = page_info["url"]
        soup = _get_soup(session, list_url)
        cards = soup.select("div.row > div:has(div.supplier-card_info)")
        for card in cards:
            title_url = _extract_title_and_url(card)
            if not title_url:
                continue
            ceo = _extract_ceo(card)
            detail_url = title_url["detail_url"]
            fields = _extract_card_fields(card)
            info_url = detail_url.rstrip("/") + "/info"
            try:
                info_soup = _get_soup(session, info_url)
            except requests.HTTPError as exc:
                status = getattr(exc.response, "status_code", None)
                if status == 404:
                    info_fields = {
                        "start_year": "",
                        "registration_number": "",
                        "national_id": "",
                        "economic_code": "",
                        "description": "",
                        "website": "",
                        "email": "",
                        "phone": "",
                        "office_address": "",
                        "office_phone": "",
                        "office_description": "",
                        "warehouse_address": "",
                        "warehouse_description": "",
                    }
                else:
                    raise
            else:
                info_fields = _extract_info_fields(info_soup)
            items.append(
                SupplierRow(
                    title=title_url["title"],
                    ceo=ceo,
                    user_code=fields["user_code"],
                    membership_date=fields["membership_date"],
                    user_type=fields["user_type"],
                    address=fields["address"],
                    trade=fields["trade"],
                    service=fields["service"],
                    start_year=info_fields["start_year"],
                    registration_number=info_fields["registration_number"],
                    national_id=info_fields["national_id"],
                    economic_code=info_fields["economic_code"],
                    description=info_fields["description"],
                    website=info_fields["website"],
                    email=info_fields["email"],
                    phone=info_fields["phone"],
                    office_address=info_fields["office_address"],
                    office_phone=info_fields["office_phone"],
                    office_description=info_fields["office_description"],
                    warehouse_address=info_fields["warehouse_address"],
                    warehouse_description=info_fields["warehouse_description"],
                    detail_url=detail_url,
                    scraped_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                )
            )
            time.sleep(delay_seconds)
        yield {"page": page_info["page"], "url": list_url, "all": items}


def _validate_output_path(path: str) -> None:
    if not path.lower().endswith(".xlsx"):
        raise ValueError("Output path must end with .xlsx")


def write_excel(rows: List[SupplierRow], output_path: str) -> None:
    _validate_output_path(output_path)
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    data = [asdict(r) for r in rows]
    for row in data:
        for key, value in row.items():
            if isinstance(value, str):
                cleaned = []
                for ch in value:
                    if ch in ("\n", "\t"):
                        cleaned.append(ch)
                        continue
                    cat = unicodedata.category(ch)
                    if cat.startswith("C"):
                        continue
                    cleaned.append(ch)
                row[key] = "".join(cleaned)
    df = pd.DataFrame(data)
    df.to_excel(output_path, index=False)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl foolad24 suppliers to Excel.")
    parser.add_argument(
        "--output",
        default="output/suppliers.xlsx",
        help="Excel output path (default: output/suppliers.xlsx)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between detail page requests in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--run-every-min",
        type=float,
        default=0,
        help="If > 0, repeats crawl every N minutes.",
    )
    parser.add_argument(
        "--cookie",
        default="",
        help="Raw Cookie header for logged-in access (needed for phone field).",
    )
    parser.add_argument(
        "--cookie-file",
        default="",
        help="Path to a file containing the raw Cookie header.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last saved page using checkpoint file.",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=0,
        help="Start page number (inclusive). Use with --end-page.",
    )
    parser.add_argument(
        "--end-page",
        type=int,
        default=0,
        help="End page number (inclusive). Use with --start-page.",
    )
    return parser.parse_args()

def _read_cookie_from_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        raw = handle.read().strip()
    if not raw:
        return ""
    if "Cookie:" in raw:
        raw = raw.split("Cookie:", 1)[1].strip()
    if "set-cookie" not in raw.lower() and "\n" not in raw:
        return raw
    cookies: List[str] = []
    lines = raw.splitlines()
    for idx, line in enumerate(lines):
        lowered = line.lower().strip()
        if lowered == "set-cookie":
            if idx + 1 < len(lines):
                candidate = lines[idx + 1].strip()
                if candidate:
                    cookies.append(candidate)
            continue
        if lowered.startswith("set-cookie"):
            parts = line.split(None, 1)
            if len(parts) == 2:
                candidate = parts[1].strip()
                if candidate:
                    cookies.append(candidate)
    if not cookies:
        return ""
    pairs: List[str] = []
    for cookie in cookies:
        first = cookie.split(";", 1)[0].strip()
        if first:
            pairs.append(first)
    return "; ".join(pairs)


def main() -> None:
    args = _parse_args()
    cookie_header = args.cookie.strip()
    if not cookie_header and args.cookie_file:
        cookie_header = _read_cookie_from_file(args.cookie_file)
    checkpoint_path = f"{args.output}.checkpoint.json"
    resume_page = 0
    if args.resume:
        checkpoint = _load_checkpoint(checkpoint_path)
        resume_page = int(checkpoint.get("last_page", 0)) if checkpoint else 0
    rows = _load_existing_rows(args.output) if args.resume else []
    effective_start_page = args.start_page
    if resume_page and args.start_page <= 0:
        effective_start_page = resume_page + 1
    while True:
        for page_result in crawl_pages(
            args.delay,
            effective_start_page,
            args.end_page,
            cookie_header,
            resume_page + 1 if resume_page else 0,
            rows,
        ):
            rows = page_result["all"]
            write_excel(rows, args.output)
            _write_checkpoint(
                checkpoint_path, str(page_result["page"]), page_result["url"]
            )
        if args.run_every_min <= 0:
            break
        time.sleep(args.run_every_min * 60)


if __name__ == "__main__":
    main()
