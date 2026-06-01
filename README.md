# Tiki Product Fetcher

Script tải ~200k sản phẩm từ API Tiki, lưu thành các file JSON (1000 sản phẩm/file).

---

## Cấu trúc output

```
output_json/
├── products_batch_0000.json    # 1000 sản phẩm
├── products_batch_0001.json    # 1000 sản phẩm
├── ...
├── products_batch_0199.json    # ~200 file cho 200k sản phẩm
├── errors.jsonl                # Sản phẩm lỗi + lý do
└── progress.json               # Resume checkpoint
```

### Cấu trúc mỗi sản phẩm trong JSON

```json
{
  "id": 246724021,
  "name": "Tên sản phẩm",
  "url_key": "ten-san-pham-abc123",
  "price": 150000,
  "description": "Mô tả đã được làm sạch HTML, rút gọn tối đa 2000 ký tự...",
  "images": [
    "https://salt.tikicdn.com/ts/product/.../abc.jpg",
    "https://salt.tikicdn.com/ts/product/.../def.jpg"
  ]
}
```

### Cấu trúc file lỗi (errors.jsonl)

```json
{"product_id": "123456", "error": "HTTP 404 Not Found", "timestamp": "2024-01-15T10:30:00"}
{"product_id": "789012", "error": "Timeout after 3 attempts", "timestamp": "2024-01-15T10:30:05"}
```

---

## Ước tính thời gian

| Concurrent | Tốc độ ước tính | Thời gian 200k sản phẩm |
|-----------|----------------|------------------------|
| 10        | ~8 req/s       | ~7 giờ                 |
| 20        | ~15 req/s      | ~4 giờ                 |
| 30        | ~20 req/s      | ~3 giờ                 |

> **Lưu ý:** Tiki có rate limit. Nếu gặp nhiều lỗi 429, giảm `--concurrent`.

---

## Các loại lỗi và ý nghĩa

| Lỗi | Ý nghĩa | Xử lý |
|-----|---------|-------|
| `HTTP 404 Not Found` | Sản phẩm không tồn tại | Skip, không retry |
| `HTTP 429` | Rate limited | Tự động retry với delay |
| `Timeout` | API quá chậm | Retry tự động |
| `Network error` | Mất kết nối | Retry tự động |
| `JSON parse error` | Response không hợp lệ | Ghi log, cần kiểm tra thủ công |
