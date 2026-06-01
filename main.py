#!/usr/bin/env python3
"""
Tiki Product Fetcher - Phiên bản đơn giản
==========================================
Cài đặt: pip install requests pandas beautifulsoup4 lxml
Cách dùng: python fetch_tiki_simple.py
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ── Cấu hình ──────────────────────────────────────────────
INPUT_CSV         = "products-0-200000.csv"
OUTPUT_DIR        = Path("output_json")
PRODUCTS_PER_FILE = 1000
MAX_WORKERS       = 20      # Số thread song song
TIMEOUT           = 15      # Giây timeout mỗi request
MAX_RETRIES       = 3

API_URL = "https://api.tiki.vn/product-detail/api/v1/products/{}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://tiki.vn/",
}
# ──────────────────────────────────────────────────────────


def clean_description(html: str, max_chars: int = 2000) -> str:
    """
    Xóa HTML tags (requests.json() đã tự decode unicode \u003c → < rồi),
    gộp khoảng trắng, rút gọn còn tối đa max_chars ký tự.
    """
    if not html:
        return ""
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rfind(" ")
    return text[: cut if cut > max_chars * 0.8 else max_chars] + "…"


def fetch_one(product_id: str) -> tuple[str, dict | None, str | None]:
    """Fetch 1 sản phẩm. Trả về (id, data, error)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(API_URL.format(product_id), headers=HEADERS, timeout=TIMEOUT)

            if r.status_code == 200:
                raw = r.json()
                images = raw.get("images") or []
                data = {
                    "id":          raw.get("id"),
                    "name":        raw.get("name", ""),
                    "url_key":     raw.get("url_key", ""),
                    "price":       raw.get("price"),
                    "description": clean_description(raw.get("description", "")),
                    "images":      [
                        img.get("base_url") or img.get("large_url") or img.get("url", "")
                        for img in images if isinstance(img, dict)
                    ],
                }
                return product_id, data, None

            elif r.status_code == 404:
                return product_id, None, "HTTP 404 Not Found"

            elif r.status_code == 429:
                time.sleep(5 * attempt)

            else:
                time.sleep(2 * attempt)

        except requests.Timeout:
            time.sleep(2 * attempt)
        except Exception as e:
            time.sleep(2 * attempt)
            if attempt == MAX_RETRIES:
                return product_id, None, f"Error: {e}"

    return product_id, None, f"Failed after {MAX_RETRIES} retries"


def save_batch(products: list, batch_idx: int):
    path = OUTPUT_DIR / f"products_batch_{batch_idx:04d}.json"
    path.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → Saved {len(products)} products → {path.name}")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    error_file = OUTPUT_DIR / "errors.jsonl"

    # ── Đọc IDs ──
    df = pd.read_csv(INPUT_CSV, dtype=str)
    id_col = next((c for c in df.columns if "id" in c.lower()), df.columns[0])
    all_ids = df[id_col].dropna().unique().tolist()
    print(f"Tổng số sản phẩm: {len(all_ids):,}")

    # ── Resume: bỏ qua ID đã có trong output ──
    done_ids = set()
    for f in OUTPUT_DIR.glob("products_batch_*.json"):
        for p in json.loads(f.read_text(encoding="utf-8")):
            done_ids.add(str(p["id"]))
    remaining = [pid for pid in all_ids if pid not in done_ids]
    print(f"Còn lại cần fetch: {len(remaining):,}\n")

    # ── Fetch song song ──
    batch, batch_idx = [], len(list(OUTPUT_DIR.glob("products_batch_*.json")))
    success = error = 0
    start = time.time()

    with open(error_file, "a", encoding="utf-8") as err_fh:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            futures = {pool.submit(fetch_one, pid): pid for pid in remaining}

            for i, future in enumerate(as_completed(futures), 1):
                pid, data, err = future.result()

                if data:
                    batch.append(data)
                    success += 1
                    if len(batch) >= PRODUCTS_PER_FILE:
                        save_batch(batch, batch_idx)
                        batch_idx += 1
                        batch = []
                else:
                    error += 1
                    err_fh.write(json.dumps({
                        "product_id": pid,
                        "error": err,
                        "timestamp": datetime.now().isoformat(),
                    }, ensure_ascii=False) + "\n")
                    err_fh.flush()

                # Progress mỗi 500 sản phẩm
                if i % 500 == 0:
                    elapsed = time.time() - start
                    rate = i / elapsed
                    eta = (len(remaining) - i) / rate / 60
                    print(f"[{i:,}/{len(remaining):,}] ✓{success:,} ✗{error:,} | {rate:.1f} req/s | ETA {eta:.0f} phút")

    # Lưu batch cuối
    if batch:
        save_batch(batch, batch_idx)

    elapsed = (time.time() - start) / 60
    print(f"\n{'='*50}")
    print(f"Xong! Thành công: {success:,} | Lỗi: {error:,} | Thời gian: {elapsed:.0f} phút")
    print(f"Output: {OUTPUT_DIR.resolve()}")
    print(f"Lỗi:    {error_file.resolve()}")


if __name__ == "__main__":
    main()