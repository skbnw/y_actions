"""
update_media_url_lists.py v1.0

機能メモ:
- 追加: Yahoo!ニュース提供社一覧から最新の媒体URLを取得し、url配下のCSVを更新
- 追加: 既存のgroup割り当てを可能な限り引き継ぎ、新規媒体のみ少ないgroupへ自動配分
- 追加: 追加・削除・名称変更の差分をurl/outputへ日時付きCSVで保存
"""

from __future__ import annotations

import csv
import html
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


SOURCE_URL = "https://news.yahoo.co.jp/media"
GROUPS = list("abcdefgh")
REPO_ROOT = Path(__file__).resolve().parents[2]
URL_DIR = REPO_ROOT / "url"
GROUP_CSV = URL_DIR / "media_url_group.csv"
ALL_CSV = URL_DIR / "media_url_all.csv"
OUTPUT_DIR = URL_DIR / "output"


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def slug_from_url(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def absolute_media_url(href: str) -> str | None:
    if href.startswith("/media/"):
        href = "https://news.yahoo.co.jp" + href
    if not href.startswith("https://news.yahoo.co.jp/media/"):
        return None
    slug = slug_from_url(href)
    if not re.fullmatch(r"[A-Za-z0-9_]+", slug):
        return None
    return f"https://news.yahoo.co.jp/media/{slug}"


class YahooMediaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self._seen: set[str] = set()
        self._anchor: dict[str, object] | None = None
        self._company_parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {name: value or "" for name, value in attrs}
        class_name = attr.get("class", "")

        if tag == "a":
            media_url = absolute_media_url(attr.get("href", ""))
            if media_url:
                self._anchor = {"url": media_url, "parts": []}
                return

        if "sc-1a60xef-2" in class_name and self.rows:
            self._company_parts = []

    def handle_data(self, data: str) -> None:
        if self._anchor is not None:
            self._anchor["parts"].append(data)  # type: ignore[index, union-attr]
        if self._company_parts is not None:
            self._company_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._anchor is not None:
            media_url = str(self._anchor["url"])
            slug = slug_from_url(media_url)
            title = normalize_text("".join(self._anchor["parts"]))  # type: ignore[index]
            if title and slug not in self._seen:
                self.rows.append(
                    {
                        "media_jp": title,
                        "media_en": slug,
                        "url": media_url,
                        "company": "",
                    }
                )
                self._seen.add(slug)
            self._anchor = None

        if self._company_parts is not None:
            company = normalize_text("".join(self._company_parts))
            if company and self.rows and not self.rows[-1].get("company"):
                self.rows[-1]["company"] = company
            self._company_parts = None


def fetch_media_rows() -> list[dict[str, str]]:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        body = response.read().decode(charset, errors="replace")

    parser = YahooMediaParser()
    parser.feed(body)
    rows = parser.rows

    if len(rows) < 500:
        raise RuntimeError(f"媒体一覧の取得件数が少なすぎます: {len(rows)}件")

    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(fieldnames), lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)


def assign_new_group(group_counts: Counter[str]) -> str:
    group = min(GROUPS, key=lambda item: (group_counts[item], item))
    group_counts[group] += 1
    return group


def build_group_rows(
    current_rows: list[dict[str, str]],
    old_group_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    current_by_slug = {row["media_en"]: row for row in current_rows}
    old_by_slug = {
        slug_from_url(row.get("url", "")): row
        for row in old_group_rows
        if row.get("url")
    }

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    group_counts: Counter[str] = Counter()
    changes: list[dict[str, object]] = []
    used_existing_slugs: set[str] = set()

    for old_row in old_group_rows:
        slug = slug_from_url(old_row.get("url", ""))
        if slug in used_existing_slugs:
            continue
        current = current_by_slug.get(slug)
        if not current:
            continue
        used_existing_slugs.add(slug)

        group = old_row.get("group", "")
        if group not in GROUPS:
            group = assign_new_group(group_counts)
        else:
            group_counts[group] += 1

        grouped[group].append(
            {
                "group": group,
                "media_jp": current["media_jp"],
                "media_en": current["media_en"],
                "url": current["url"],
            }
        )

        if old_row.get("media_jp") != current["media_jp"]:
            changes.append(
                {
                    "status": "renamed",
                    "media_en": slug,
                    "old_group": old_row.get("group", ""),
                    "new_group": group,
                    "old_media_jp": old_row.get("media_jp", ""),
                    "new_media_jp": current["media_jp"],
                    "url": current["url"],
                }
            )

    old_slugs = set(old_by_slug)
    current_slugs = {row["media_en"] for row in current_rows}

    for current in current_rows:
        slug = current["media_en"]
        if slug in old_slugs:
            continue
        group = assign_new_group(group_counts)
        grouped[group].append(
            {
                "group": group,
                "media_jp": current["media_jp"],
                "media_en": current["media_en"],
                "url": current["url"],
            }
        )
        changes.append(
            {
                "status": "added",
                "media_en": slug,
                "old_group": "",
                "new_group": group,
                "old_media_jp": "",
                "new_media_jp": current["media_jp"],
                "url": current["url"],
            }
        )

    for slug, old_row in old_by_slug.items():
        if slug in current_slugs:
            continue
        changes.append(
            {
                "status": "removed",
                "media_en": slug,
                "old_group": old_row.get("group", ""),
                "new_group": "",
                "old_media_jp": old_row.get("media_jp", ""),
                "new_media_jp": "",
                "url": old_row.get("url", ""),
            }
        )

    flattened: list[dict[str, object]] = []
    number = 1
    for group in GROUPS:
        for row in grouped[group]:
            flattened.append({"num": number, **row})
            number += 1

    return flattened, changes


def main() -> int:
    current_rows = fetch_media_rows()
    old_group_rows = read_csv(GROUP_CSV)

    group_rows, changes = build_group_rows(current_rows, old_group_rows)
    all_rows = [{"media": row["media_en"], "url": row["url"]} for row in current_rows]

    write_csv(GROUP_CSV, ["num", "group", "media_jp", "media_en", "url"], group_rows)
    write_csv(ALL_CSV, ["media", "url"], all_rows)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    diff_path = OUTPUT_DIR / f"media_url_update_diff_{timestamp}.csv"
    write_csv(
        diff_path,
        ["status", "media_en", "old_group", "new_group", "old_media_jp", "new_media_jp", "url"],
        changes,
    )

    counts = Counter(row["group"] for row in group_rows)
    print(f"source_count={len(current_rows)}")
    print(f"group_csv_count={len(group_rows)}")
    print(f"all_csv_count={len(all_rows)}")
    print("group_counts=" + ",".join(f"{group}:{counts[group]}" for group in GROUPS))
    print(f"diff={diff_path}")
    print(
        "changes="
        + ",".join(
            f"{status}:{sum(1 for row in changes if row['status'] == status)}"
            for status in ["added", "removed", "renamed"]
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
