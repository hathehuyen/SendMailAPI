# SendMailAPI

Dịch vụ HTTP chuyển văn bản thành email: nhận nội dung qua REST API, gửi tới danh sách người nhận do
quản trị viên cấu hình, và ghi lại mọi lần gửi vào cơ sở dữ liệu để phục vụ kiểm toán.

SendMailAPI được thiết kế cho các tác vụ cảnh báo hệ thống: một ứng dụng giám sát chỉ cần thực hiện
một lời gọi HTTP, không phải cấu hình SMTP client ở từng nơi và không cần quyền truy cập vào hộp thư.

## Mục lục

- [Tính năng](#tính-năng)
- [Kiến trúc](#kiến-trúc)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cài đặt](#cài-đặt)
- [Cấu hình](#cấu-hình)
- [API Reference](#api-reference)
- [Cơ sở dữ liệu](#cơ-sở-dữ-liệu)
- [Triển khai](#triển-khai)
- [Kiểm thử](#kiểm-thử)
- [Mở rộng](#mở-rộng)

## Tính năng

| | |
|---|---|
| **Gửi email qua HTTP** | Một endpoint duy nhất `POST /send` nhận văn bản và chuyển thành email. |
| **Người nhận do server quyết định** | `FROM` và `RCPT_TO` nằm trong cấu hình; client chỉ gửi được nội dung. |
| **Xác thực API key** | Header `X-API-Key` hoặc `Authorization: Bearer`, so sánh constant-time. |
| **Kiểm tra đầu vào** | Bắt buộc, không rỗng, giới hạn độ dài; lỗi trả JSON kèm HTTP status phù hợp. |
| **Linh hoạt transport** | Relay nội bộ, STARTTLS, SMTPS, xác thực username/password. |
| **UTF-8** | Nội dung tiếng Việt và emoji được giữ nguyên trong toàn bộ đường đi. |
| **Audit trail** | Mỗi lần gọi ghi một dòng vào bảng `maillog`, kể cả khi gửi thất bại. |
| **Cấu hình qua biến môi trường** | Cùng một artifact triển khai được cho nhiều môi trường. |
| **Application factory + Blueprint** | Không phụ thuộc trạng thái toàn cục, thuận lợi cho kiểm thử và chạy đa worker. |

## Kiến trúc

### Phân tầng

```
                     HTTP client
                          │  POST /send   (X-API-Key / Bearer)
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  API layer            sendmail_api/api/send/sendapi.py           │
│  Xác thực · kiểm tra dữ liệu · ánh xạ kết quả sang HTTP status   │
└──────────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        ▼                                   ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│  Service layer            │   │  Service layer            │
│  services/mailer.py       │   │  services/mail_log.py     │
│  Dựng MIME · giao tiếp    │   │  Ghi audit trail          │
│  SMTP                     │   │  (MariaDB / MySQL)        │
└───────────────────────────┘   └───────────────────────────┘
        │                                   │
        ▼                                   ▼
   SMTP server                       bảng maillog
```

Tầng dịch vụ không phụ thuộc HTTP: có thể tái sử dụng cho CLI, worker hàng đợi hoặc kiểm thử độc lập.

### Cấu trúc thư mục

```
SendMailAPI/
├── run.py                          # Entry point cho môi trường phát triển
├── setup.py                        # Metadata package + dependency
├── requirements.txt                # Dependency runtime
├── requirements-dev.txt            # Dependency runtime + pytest
├── pytest.ini                      # Cấu hình pytest
├── .env.example                    # Mẫu biến môi trường
├── sendmail_api/
│   ├── __init__.py                 # create_app(): factory, logging, error handler
│   ├── config.py                   # DefaultConfig đọc từ biến môi trường
│   ├── auth.py                     # Decorator require_api_key
│   ├── api/
│   │   ├── __init__.py             # Gộp các blueprint thành api_blueprint
│   │   └── send/
│   │       ├── __init__.py         # Export send_blueprint
│   │       └── sendapi.py          # View POST /send
│   └── services/
│       ├── __init__.py
│       ├── mailer.py               # parse_recipients · build_message · send_mail
│       └── mail_log.py             # save_log
└── tests/
    ├── conftest.py                 # Fixture app / client / headers
    ├── test_health.py              # Endpoint liveness
    ├── test_send.py                # Hợp đồng HTTP của POST /send
    ├── test_mailer.py              # SMTP và dựng MIME
    └── test_mail_log.py            # Ghi audit trail
```

### Trách nhiệm từng module

| Module | Trách nhiệm |
|---|---|
| `sendmail_api/__init__.py` | `create_app()` dựng Flask app, nạp cấu hình, cấu hình logging, kiểm tra cấu hình bắt buộc, đăng ký blueprint và khai báo `GET /`. |
| `sendmail_api/config.py` | `DefaultConfig` ánh xạ biến môi trường sang cấu hình ứng dụng, có kiểm tra kiểu. |
| `sendmail_api/auth.py` | `require_api_key` — chặn request thiếu hoặc sai API key. |
| `sendmail_api/api/__init__.py` | Tập hợp blueprint của các nhóm endpoint thành một `api_blueprint`. |
| `sendmail_api/api/send/sendapi.py` | View `POST /send`: đọc `msg`, kiểm tra, gọi service, dựng response. |
| `sendmail_api/services/mailer.py` | Tiền xử lý danh sách người nhận, dựng MIME message UTF-8, gửi qua SMTP. |
| `sendmail_api/services/mail_log.py` | Ghi một dòng vào `maillog` với `sent` là kết quả thực tế. |
| `run.py` | Chạy Flask dev server; production dùng WSGI server. |

### Vòng đời một request `POST /send`

1. **Cấu hình được kiểm tra lúc khởi động.** Nếu thiếu `SEND_API_KEY`, `FROM` hoặc `RCPT_TO`, ứng
   dụng dừng ngay với `RuntimeError` thay vì phục vụ request trong trạng thái thiếu cấu hình.
2. **Xác thực.** `require_api_key` đọc khoá từ `X-API-Key` hoặc `Authorization: Bearer`. Khoá được so
   sánh constant-time; sai hoặc thiếu → `401`.
3. **Đọc nội dung.** `msg` được lấy theo thứ tự ưu tiên: JSON body → form field → query string.
4. **Kiểm tra dữ liệu.** Thiếu, không phải chuỗi, rỗng hoặc vượt `MAX_MESSAGE_LENGTH` → `400`.
5. **Gửi.** `send_mail()` chuẩn hoá danh sách người nhận, dựng MIME message UTF-8 và bàn giao cho SMTP
   server. Lỗi SMTP → `502`.
6. **Ghi audit.** `save_log()` ghi một dòng vào `maillog` với `sent = 1` hoặc `0`. Việc ghi log là
   best-effort: nếu thất bại, response báo `"logged": false` nhưng kết quả gửi vẫn được giữ nguyên.

## Yêu cầu hệ thống

| Thành phần | Yêu cầu |
|---|---|
| Python | 3.8 trở lên (đã kiểm thử trên 3.11) |
| Thư viện | `Flask>=2.2`, `mysql-connector-python>=8.0` |
| SMTP | Một SMTP server truy cập được: relay nội bộ (`localhost:25`), STARTTLS (`587`) hoặc SMTPS (`465`) |
| Cơ sở dữ liệu | MariaDB / MySQL với bảng `maillog` |

## Cài đặt

```bash
git clone https://github.com/hathehuyen/SendMailAPI.git
cd SendMailAPI

python3 -m venv .venv
source .venv/bin/activate

# Runtime + công cụ kiểm thử
pip install -r requirements-dev.txt

# Hoặc chỉ cài package runtime
# pip install -r requirements.txt
```

### Tạo bảng audit

```sql
CREATE TABLE maillog (
    time    DATETIME NOT NULL,
    content TEXT     NOT NULL,
    sent    BOOLEAN  NOT NULL,
    INDEX idx_maillog_time (time)
);
```

### Khởi động

```bash
cp .env.example .env
# Sửa .env: SEND_API_KEY, FROM, RCPT_TO, SMTP_*, DB_*

set -a; source .env; set +a

python run.py
# hoặc để Flask tự phát hiện factory
flask --app sendmail_api run
```

Ứng dụng lắng nghe tại `http://0.0.0.0:5000`. Biến `HOST`, `PORT`, `DEBUG` điều khiển dev server.

## Cấu hình

Toàn bộ cấu hình đến từ biến môi trường. `.env` chỉ là tệp mẫu — ứng dụng không tự nạp, hãy export
biến (như ví dụ trên) hoặc truyền qua `EnvironmentFile` của systemd.

### Bắt buộc

| Biến | Mô tả |
|---|---|
| `SEND_API_KEY` | Khoá chia sẻ cho mọi request ghi. Nên dài, ngẫu nhiên và được luân chuyển định kỳ. |
| `FROM` | Địa chỉ gửi, dùng cho cả header *From* và envelope sender. |
| `RCPT_TO` | Danh sách người nhận, phân tách bằng dấu phẩy. Hỗ trợ `Tên <email>`; khoảng trắng và dấu phẩy thừa được bỏ qua. |

### HTTP và xác thực

| Biến | Mặc định | Mô tả |
|---|---|---|
| `MAX_CONTENT_LENGTH` | `1048576` | Kích thước tối đa của request body (byte). Vượt → `413`. |
| `MAX_MESSAGE_LENGTH` | `10000` | Độ dài tối đa của `msg` (ký tự). Vượt → `400`. |
| `LOG_LEVEL` | `INFO` | Mức log: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |

### Nội dung email

| Biến | Mặc định | Mô tả |
|---|---|---|
| `SUBJECT` | `System Email` | Tiêu đề email. |

### SMTP

| Biến | Mặc định | Mô tả |
|---|---|---|
| `SMTP_HOST` | `localhost` | Hostname SMTP server. |
| `SMTP_PORT` | `25` | Cổng SMTP. |
| `SMTP_TIMEOUT` | `10` | Timeout kết nối (giây). |
| `SMTP_USERNAME` | *(rỗng)* | Nếu đặt, ứng dụng sẽ xác thực SMTP bằng thông tin này. |
| `SMTP_PASSWORD` | *(rỗng)* | Mật khẩu tương ứng. |
| `SMTP_USE_STARTTLS` | `false` | Nâng cấp kết nối bằng STARTTLS trước khi gửi. |
| `SMTP_USE_SSL` | `false` | Dùng SMTPS (TLS ngay từ đầu). |

### Cơ sở dữ liệu

| Biến | Mặc định | Mô tả |
|---|---|---|
| `DB_HOST` | `localhost` | Host của MariaDB/MySQL. |
| `DB_PORT` | `3306` | Cổng kết nối. |
| `DB_USER` | *(rỗng)* | Tài khoản đăng nhập. |
| `DB_PASSWORD` | *(rỗng)* | Mật khẩu. |
| `DB_NAME` | `maillog` | Tên database. |
| `DB_TIMEOUT` | `10` | Timeout kết nối (giây). |

## API Reference

Base URL: `http://<host>:<port>`

### Xác thực

Mọi request tới `POST /send` phải kèm API key ở một trong hai dạng:

```http
X-API-Key: <SEND_API_KEY>
```

```http
Authorization: Bearer <SEND_API_KEY>
```

Khoá được so sánh bằng `hmac.compare_digest`, do đó thời gian phản hồi không làm lộ giá trị đúng.

### `GET /` — Liveness

Xác nhận dịch vụ đã khởi động và nạp cấu hình thành công. Không yêu cầu xác thực.

```bash
curl http://localhost:5000/
```

```json
{"service": "sendmail_api", "status": "ok", "version": "2.0.0"}
```

### `POST /send` — Gửi email

Gửi nội dung tới toàn bộ người nhận trong `RCPT_TO` và ghi một dòng audit.

**Request body**

| Field | Kiểu | Bắt buộc | Mô tả |
|---|---|---|---|
| `msg` | string | Có | Nội dung email dạng plain text. |

`msg` được đọc theo thứ tự ưu tiên: **JSON body**, sau đó tới **query string** hoặc **form field**. Nhờ
vậy cùng một endpoint phục vụ được cả client hiện đại và các script cũ chỉ biết gửi form.

```bash
# JSON (khuyến nghị)
curl -X POST http://localhost:5000/send \
     -H "X-API-Key: $SEND_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"msg": "CPU trên web-01 vượt 95% lúc 10:32"}'

# Form-urlencoded
curl -X POST http://localhost:5000/send \
     -H "X-API-Key: $SEND_API_KEY" \
     -d 'msg=Disk usage on db-01 is above 90%'

# Query string
curl -X POST "http://localhost:5000/send?msg=hello" -H "X-API-Key: $SEND_API_KEY"
```

**Response thành công — `200`**

```json
{"logged": true, "recipients": 2, "result": true}
```

| Field | Ý nghĩa |
|---|---|
| `result` | `true` khi SMTP server đã nhận message. |
| `recipients` | Số địa chỉ trong envelope. |
| `logged` | `true` nếu dòng audit đã ghi được; `false` nếu database không truy cập được. |

`logged: false` **không** có nghĩa là gửi thất bại — email đã được bàn giao cho SMTP server. Hãy dùng
giá trị này để đối soát khi database gặp sự cố.

**Response lỗi**

| HTTP | `error` | Nguyên nhân |
|---|---|---|
| `400` | `invalid_request` | Thiếu `msg`, không phải chuỗi, rỗng, hoặc vượt `MAX_MESSAGE_LENGTH`. |
| `401` | `unauthorized` | Thiếu hoặc sai API key. |
| `404` | — | Đường dẫn không tồn tại. |
| `405` | — | Dùng sai phương thức (ví dụ `GET /send`). |
| `413` | `payload_too_large` | Request body vượt `MAX_CONTENT_LENGTH`. |
| `502` | `smtp_error` | Không kết nối được SMTP server hoặc server từ chối message. |

```json
{"error": "invalid_request", "message": "Field 'msg' is required.", "result": false}
```

Chi tiết kỹ thuật của lỗi SMTP/DB được ghi vào log phía server, không trả về cho client. Riêng `404` và
`405` do Flask sinh ra ở định dạng HTML mặc định.

## Cơ sở dữ liệu

Mỗi lần gọi `/send` sinh **đúng một** dòng trong `maillog`, kể cả khi gửi thất bại.

| Cột | Kiểu | Mô tả |
|---|---|---|
| `time` | `DATETIME` | Thời điểm xử lý theo giờ server ứng dụng (độ chính xác tới giây). |
| `content` | `TEXT` | Nội dung `msg` gốc. |
| `sent` | `BOOLEAN` | `1` = gửi thành công, `0` = thất bại. |

```sql
-- 20 lần gửi gần nhất
SELECT time, sent, LEFT(content, 60) AS preview
FROM maillog
ORDER BY time DESC
LIMIT 20;

-- Tỉ lệ gửi thành công trong 7 ngày
SELECT DATE(time) AS day, SUM(sent) / COUNT(*) AS success_rate
FROM maillog
WHERE time >= NOW() - INTERVAL 7 DAY
GROUP BY DATE(time);
```

Bảng tăng tuyến tính theo lưu lượng, nên đặt chính sách lưu trữ phù hợp, ví dụ:

```sql
DELETE FROM maillog WHERE time < NOW() - INTERVAL 90 DAY;
```

## Triển khai

Chạy bằng WSGI server với nhiều worker; cấu hình được đọc một lần khi mỗi worker khởi động nên các
worker cần cùng biến môi trường.

```bash
pip install gunicorn
gunicorn "sendmail_api:create_app()" \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 30 \
    --access-logfile -
```

Ví dụ unit file cho systemd:

```ini
[Unit]
Description=SendMailAPI
After=network.target

[Service]
User=sendmail
WorkingDirectory=/opt/sendmail_api
EnvironmentFile=/etc/sendmail_api.env
ExecStart=/opt/sendmail_api/.venv/bin/gunicorn "sendmail_api:create_app()" \
          --bind 127.0.0.1:8000 --workers 4 --timeout 30
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Đặt dịch vụ sau reverse proxy (nginx, Caddy) để có TLS và giới hạn tần suất. Tệp `/etc/sendmail_api.env`
nên có quyền `600` vì chứa `SEND_API_KEY` và mật khẩu database.

**Health check:** dùng `GET /` cho liveness/readiness probe.

## Kiểm thử

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Bộ kiểm thử không truy cập mạng: SMTP client và driver database được thay bằng mock, nên chạy được
trong CI mà không cần SMTP server hay MariaDB.

| Tệp | Phạm vi |
|---|---|
| `tests/test_health.py` | Liveness, route không tồn tại, sai phương thức. |
| `tests/test_send.py` | Xác thực, ba dạng payload, validate, mã lỗi, hành vi khi SMTP/DB lỗi. |
| `tests/test_mailer.py` | Chuẩn hoá danh sách người nhận, dựng MIME UTF-8, STARTTLS/SMTPS, ánh xạ lỗi. |
| `tests/test_mail_log.py` | Câu lệnh INSERT, tham số kết nối, rollback và đóng kết nối. |

Chạy một nhóm cụ thể:

```bash
python -m pytest tests/test_send.py -v
python -m pytest -k "audit"
```

## Mở rộng

### Thêm một endpoint mới

1. Tạo package `sendmail_api/api/<tên>/` với `__init__.py` export blueprint và một module view.
2. Đăng ký blueprint trong `sendmail_api/api/__init__.py`:

```python
from sendmail_api.api.<tên> import <tên>_blueprint

api_blueprint.register_blueprint(<tên>_blueprint)
```

3. Đặt logic nghiệp vụ trong `sendmail_api/services/`, không viết trực tiếp trong view, để giữ khả
   năng kiểm thử độc lập với HTTP.

### Thay đổi transport hoặc lưu trữ

`services/mailer.py` và `services/mail_log.py` là ranh giới duy nhất tiếp xúc với SMTP và database.
Thay thế hai module này (hoặc bổ sung implementer mới) là đủ để chuyển sang nhà cung cấp email API
hoặc một hệ quản trị cơ sở dữ liệu khác, không cần sửa tầng API.


