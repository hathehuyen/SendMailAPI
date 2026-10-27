# SendMailAPI

API gửi email tối giản viết bằng **Flask**: nhận nội dung văn bản qua HTTP, gửi tới danh sách người
nhận được cấu hình sẵn trên server, và ghi log mọi lần gửi (thành công / thất bại) vào **MariaDB**.

> ⚠️ Đây là dự án **legacy**, viết cho **Python 2.7** (2016). Đọc mục
> [Hạn chế và Roadmap](#hạn-chế-và-roadmap) trước khi triển khai production.

## Mục lục

- [Tổng quan](#tổng-quan)
- [Kiến trúc](#kiến-trúc)
- [Công nghệ sử dụng](#công-nghệ-sử-dụng)
- [Cài đặt](#cài-đặt)
- [Cấu hình](#cấu-hình)
- [API Reference](#api-reference)
- [Cơ sở dữ liệu](#cơ-sở-dữ-liệu)
- [Kiểm thử cục bộ](#kiểm-thử-cục-bộ)
- [Hạn chế và Roadmap](#hạn-chế-và-roadmap)
- [Lịch sử dự án](#lịch-sử-dự-án)

## Tổng quan

| | |
|---|---|
| **Mục đích** | Nhận text qua HTTP → chuyển thành email → gửi cho recipient cố định → log vào DB |
| **Entry point** | `run.py` |
| **Endpoints** | `GET /`, `POST /send` |
| **SMTP** | MTA nội bộ tại `localhost:25` (không auth, không TLS) |
| **Lưu trữ** | MariaDB / MySQL, bảng `maillog` |
| **Ngôn ngữ** | Python 2.7 (`print` statement + implicit relative import) |

Điểm thiết kế đáng chú ý: **người gửi (`FROM`) và người nhận (`RCPT_TO`) không lấy từ request** mà lấy
từ config của server. Client chỉ gửi được *nội dung*. Nhờ vậy API không thể bị dùng làm open relay để
spam người ngoài — nhưng cũng có nghĩa mỗi deployment chỉ gửi được về một danh sách cố định.

## Kiến trúc

### Cấu trúc thư mục

```
SendMailAPI/
├── run.py                              # Entry point: app.run(host="0.0.0.0") → port 5000
├── setup.py                            # Metadata package, install_requires=['Flask']
├── sendmail_api/
│   ├── __init__.py                     # Tạo Flask app, load config, route '/', rồi import api
│   ├── config.py                       # DefaultConfig: SUBJECT, FROM, RCPT_TO
│   └── api/
│       ├── __init__.py                 # import send → kéo theo route của package con
│       └── send/
│           ├── __init__.py             # import sendapi → đăng ký route '/send'
│           └── sendapi.py              # Handler: SMTP + ghi log MariaDB
└── .idea/                              # Cấu hình PyCharm (Python 2.7 SDK)
```

### Thành phần

| Thành phần | Vai trò |
|---|---|
| `sendmail_api/__init__.py` | **Application object**. Tạo `app = Flask(__name__)`, nạp `DefaultConfig`, khai báo route `GET /`, rồi `import api` để kích hoạt đăng ký các route còn lại. |
| `sendmail_api/config.py` | **Cấu hình tĩnh** dưới dạng class (pattern `app.config.from_object`). Chỉ 3 khoá: `SUBJECT`, `FROM`, `RCPT_TO`. |
| `sendmail_api/api/` | **Package chứa các nhóm endpoint**. Hiện chỉ có nhóm `send`. |
| `sendmail_api/api/send/sendapi.py` | **Business logic**: dựng MIME message, gửi qua SMTP local, ghi log vào MariaDB. |
| `run.py` | **Dev server runner** — không dùng cho production. |

### Cách đăng ký route (không dùng Blueprint)

Dự án dùng pattern **"module-import side effect"** — phổ biến trước khi Flask Blueprint ra đời:

```
run.py
  └─ import sendmail_api        → tạo `app`
       └─ import api            (sendmail_api/api/__init__.py)
            └─ import send      (…/api/send/__init__.py)
                 └─ import sendapi   (…/send/sendapi.py)
                      └─ @app.route('/send')   ← route gắn vào `app` ngay tại đây
```

Hệ quả:

- `sendapi.py` **import `app` từ package cha** (`from sendmail_api import app`) → tạo phụ thuộc vòng
  (circular import), được "chữa" bằng cách đặt `import api` ở **cuối** `sendmail_api/__init__.py`.
- Thêm endpoint mới = thêm package con + `import` nó trong `api/__init__.py`. Không có URL prefix tự động.
- `import send`, `import sendapi` là **implicit relative import** → chỉ chạy trên Python 2.

### Luồng xử lý `POST /send`

```
Client                Flask             sendapi.py                  SMTP localhost:25     MariaDB
   │                    │                    │                            │                 │
   ├─ POST /send ──────►│                    │                            │                 │
   │   msg="..."        ├─ sendmail() ──────►│                            │                 │
   │                    │                    ├─ MIMEMultipart('alternative')
   │                    │                    ├─ Subject / From / To ← app.config
   │                    │                    ├─ attach MIMEText(msg, 'plain')
   │                    │                    ├─ SMTP('localhost') ──────►│                 │
   │                    │                    ├─ sendmail(...) ───────────►│ relay đi tiếp   │
   │                    │                    ├─ quit() ──────────────────►│                 │
   │                    │                    ├─ INSERT maillog(..., sent=1) ───────────────►│
   │◄─ {"result": true} ┤◄───────────────────┤                            │                 │
   │                    │                    │                            │                 │
   │      nếu bất kỳ bước nào lỗi            │                            │                 │
   │                    │                    ├─ except: print(exc)        │                 │
   │                    │                    ├─ INSERT maillog(..., sent=0) ───────────────►│
   │◄─ {"result": false}┤◄───────────────────┤                            │                 │
```

Lưu ý: **mọi lỗi đều trả HTTP 200** — kết quả thật nằm ở field `result` trong JSON body.

## Công nghệ sử dụng

| Thư viện | Dùng cho | Khai báo trong `setup.py`? |
|---|---|---|
| `Flask` | Web framework, routing, config, `jsonify` | ✅ Có |
| `mysql-connector-python` (`mysql.connector`) | Kết nối + ghi log MariaDB | ❌ **Thiếu** — phải cài thủ công |
| `smtplib`, `email.mime.*` | Dựng & gửi email | ✅ stdlib |
| `datetime` | Timestamp cho log | ✅ stdlib |

Yêu cầu môi trường:

- **Python 2.7** — bắt buộc. Code dùng `print "..."` và implicit relative import nên **không chạy được trên Python 3**.
- MTA / relay lắng nghe ở `localhost:25` (Postfix, Exim, Sendmail… hoặc `smtpd.DebuggingServer` khi test).
- MariaDB / MySQL có bảng `maillog`.

## Cài đặt

```bash
# 1. Cài dependency (driver DB chưa được khai báo trong setup.py)
pip install Flask mysql-connector-python

# 2. Cài package ở chế độ develop
pip install -e .

# 3. Chạy dev server
python run.py
# → Serving on http://0.0.0.0:5000
```

Tạo bảng log (chạy một lần trên MariaDB):

```sql
CREATE TABLE maillog (
    time    DATETIME NOT NULL,
    content TEXT     NOT NULL,
    sent    BOOLEAN  NOT NULL
);
```

## Cấu hình

### Config của ứng dụng — `sendmail_api/config.py`

| Khoá | Giá trị mặc định | Ý nghĩa |
|---|---|---|
| `SUBJECT` | `System Email` | Tiêu đề email |
| `FROM` | `noreply@daylacaigivay.tk` | Địa chỉ gửi (header *From* + envelope sender) |
| `RCPT_TO` | `hathehuyen@gmail.com` | Danh sách người nhận, **phân tách bằng dấu phẩy** → được `.split(",")` khi gửi |

Sửa file này rồi restart app để áp dụng. Khi deploy có thể override bằng cách trỏ
`app.config.from_object(...)` sang một class khác.

### Cấu hình hard-code — `sendmail_api/api/send/sendapi.py`

Các thông số sau **chưa** được đưa vào config, đang viết cứng trong code:

| Thông số | Giá trị hiện tại |
|---|---|
| SMTP host | `localhost` (port mặc định 25) |
| DB host | `128.199.136.222` |
| DB user / password | `maillog` / `maillog` |
| DB name | `maillog` |
| Bảng | `maillog (time, content, sent)` |

> 🔴 **Cảnh báo bảo mật:** credentials DB đang nằm plaintext trong source và **đã bị commit vào git
> history**. Cần rotate password và chuyển sang biến môi trường (xem [Roadmap](#hạn-chế-và-roadmap)).

## API Reference

Base URL (dev): `http://localhost:5000`

### `GET /` — Health check

Trả về chuỗi `Send Mail API` nếu app load thành công.

```bash
curl http://localhost:5000/
# Send Mail API
```

### `POST /send` — Gửi email

Gửi nội dung text tới toàn bộ recipient trong `RCPT_TO` và ghi log vào `maillog`.

**Request**

| Field | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| `msg` | string | ✅ | Nội dung email (plain text). Đọc qua `request.values` → nhận cả **form body** lẫn **query string** |

```bash
# form-urlencoded (khuyến nghị)
curl -X POST http://localhost:5000/send \
     -d "msg=Server CPU vượt ngưỡng 90% lúc 10:32"

# query string (cũng hoạt động, vì handler dùng request.values)
curl -X POST "http://localhost:5000/send?msg=hello"
```

**Response**

| HTTP | Body | Ý nghĩa |
|---|---|---|
| `200` | `{"result": true}` | Gửi SMTP thành công **và** đã ghi log `sent = 1` |
| `200` | `{"result": false}` | Có exception ở bất kỳ bước nào; đã cố ghi log `sent = 0` |
| `500` | HTML error page | Lỗi không bắt được — điển hình là **thiếu field `msg`**: `request.values['msg']` ném `KeyError` ngay trong nhánh `except`, thoát khỏi `try/except` |

Email được dựng dạng `multipart/alternative` nhưng **chỉ có một part** `text/plain` (khung sẵn để bổ
sung bản HTML sau này).

## Cơ sở dữ liệu

Mỗi lần gọi `/send` sinh **đúng một** row trong `maillog`, kể cả khi gửi thất bại.

| Cột | Kiểu | Mô tả |
|---|---|---|
| `time` | `DATETIME` | Thời điểm xử lý, `datetime.now()` **theo giờ server app** (không phải giờ DB) |
| `content` | `TEXT` | Nội dung `msg` gốc |
| `sent` | `BOOLEAN` | `1` = gửi thành công, `0` = thất bại |

```sql
-- 20 lần gửi gần nhất
SELECT time, sent, LEFT(content, 60) AS preview
FROM maillog
ORDER BY time DESC
LIMIT 20;
```

## Kiểm thử cục bộ

Dự án **không có test suite**. Để thử end-to-end mà không cần MTA thật, dựng SMTP server giả in ra stdout:

```bash
# Terminal 1 — SMTP giả (Python 2)
sudo python -m smtpd -n -c DebuggingServer localhost:25

# Terminal 2 — app
python run.py

# Terminal 3 — gọi API
curl -X POST http://localhost:5000/send -d "msg=test message"
# → {"result": true}, và Terminal 1 in ra nội dung email
```

Nếu chưa có MariaDB, cần sửa tạm phần `mariadb.connect(...)` hoặc dựng DB local — hiện **chưa có cơ
chế mock / dependency injection**.

Checklist verify sau khi deploy:

- [ ] `GET /` trả `Send Mail API`
- [ ] `POST /send` với `msg` hợp lệ trả `{"result": true}`
- [ ] Email đến hộp thư trong `RCPT_TO` (kiểm tra cả Spam — `FROM` dùng domain `.tk`)
- [ ] Có row mới trong `maillog` với `sent = 1`
- [ ] Tắt SMTP → gọi lại → `{"result": false}` và có row `sent = 0`

## Hạn chế và Roadmap

### 🔴 Bảo mật

- **Credentials DB hard-code** trong `sendapi.py` và đã nằm trong git history → rotate ngay, chuyển sang
  `os.environ` / `app.config`, thêm `config.example.py`.
- **Không có authentication** trên `/send`. Rủi ro bị lạm dụng gửi email hàng loạt vào hộp thư của chủ
  server (DoS mailbox / mất uy tín domain). Cần API key hoặc IP allowlist.
- **SMTP không TLS, không auth** — chỉ an toàn khi `localhost` thật sự là máy tin cậy.
- **Không giới hạn kích thước `msg`** → có thể gửi payload lớn làm phình bảng `maillog`.

### 🟠 Chất lượng code

- **Python 2.7 đã EOL** (01/2020). Cần port sang Python 3: `print(...)`, explicit relative import
  (`from . import sendapi`), và thay các package đã bị bỏ.
- **Circular import** giữa `sendmail_api/__init__.py` và `sendapi.py` — nên chuyển sang **Flask
  Blueprint** để có `url_prefix` và tránh side-effect import.
- **Không có test, không có CI, không có logging chuẩn** (chỉ `print`).
- **`setup.py` thiếu `mysql-connector-python`** → cài qua `pip` xong vẫn lỗi lúc runtime.
- **Không có `.gitignore`** → dễ commit nhầm `venv/`, `*.pyc`.
- **Trả HTTP 200 cho cả trường hợp lỗi** — khó cho monitoring; nên dùng 4xx/5xx kèm `result`.
- **Thiếu `msg` gây 500** thay vì 400.

### Đề xuất thứ tự khắc phục

1. Rotate credentials DB + đưa cấu hình vào biến môi trường.
2. Port sang Python 3, thêm `requirements.txt` và pin version.
3. Chuyển route sang Blueprint, validate input (`msg` bắt buộc, max length), trả mã lỗi đúng.
4. Tách phần gửi mail + ghi log thành service riêng để test được (mock SMTP & DB).
5. Thêm `pytest` + CI, thêm `.gitignore`, `.env.example`.
6. Thêm auth (API key) cho `/send`.

## Lịch sử dự án

Khởi tạo tháng 10/2016 bởi [HuyenHa](https://github.com/hathehuyen). Bài toán: một máy chủ cần bắn
cảnh báo về hộp thư cá nhân mà không phải cấu hình SMTP client ở từng nơi.

| Ngày | Commit | Nội dung |
|---|---|---|
| 2016-10-21 | `init` → `start sendmail API` | Khởi tạo repo, dựng khung Flask |
| 2016-10-21 | `Add smtp lib setup` | Tích hợp `smtplib` + MIME |
| 2016-10-21 | `Code refactor` ×3 | Tách package `sendmail_api/api/send` |
| 2016-10-21 | `Create README.md` | Thêm README |
| 2016-11-04 | `Save log to database` | **Commit gần nhất** — thêm ghi log MariaDB |

Dự án hiện **không còn được bảo trì** (commit cuối 11/2016).

