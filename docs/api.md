# مرور API نسخه‌ی اول

همه‌ی مسیر‌ها با پیشوند `/api/v1/` هستند. احراز هویت با کوکی JWT و
محافظت CSRF انجام می‌شود. خطاها به‌صورت JSON و با کد‌های استاندارد HTTP
برمی‌گردند.

## احراز هویت

| Method | Path | توضیح |
|---|---|---|
| POST | `/auth/login/` | ورود با `username` و `password`. کوکی‌ها ست می‌شوند. |
| POST | `/auth/logout/` | خروج؛ توکن refresh بلاک و کوکی‌ها پاک می‌شود. |
| POST | `/auth/refresh/` | تمدید خودکار توکن (فرانت به‌صورت داخلی استفاده می‌کند). |
| GET  | `/auth/me/` | اطلاعات کاربر لاگین‌شده (نقش، مدرسه). |

## مدارس و اپراتورها (فقط system_admin)

| Method | Path | توضیح |
|---|---|---|
| GET/POST | `/schools/` | فهرست/ایجاد مدرسه |
| PATCH | `/schools/{id}/` | ویرایش مدرسه |
| POST | `/schools/{id}/deactivate/` | غیرفعال‌سازی مدرسه |
| GET/POST | `/schools/operators/` | فهرست/ایجاد مسئول |
| POST | `/schools/operators/{id}/deactivate/` | غیرفعال‌سازی مسئول |

## ورود داده (Intake)

| Method | Path | توضیح |
|---|---|---|
| GET | `/intake/canonical-fields/` | فهرست فیلدهای استاندارد و گروه‌بندی UI |
| GET/POST | `/intake/batches/` | فهرست Batchهای مدرسه‌ی کاربر |
| POST | `/intake/batches/upload/` | آپلود فایل + سال تحصیلی |
| GET | `/intake/batches/{id}/` | جزئیات Batch |
| POST | `/intake/batches/{id}/select-sheet/` | انتخاب Sheet |
| POST | `/intake/batches/{id}/select-header/` | انتخاب ردیف هدر |
| GET | `/intake/batches/{id}/row-count/` | شمارش ردیف‌های داده (سقف ۵۰۰۰) |
| POST | `/intake/batches/{id}/mapping/` | ذخیره نگاشت (و در صورت نیاز ساخت پروفایل) |
| GET | `/intake/batches/{id}/original-file/` | دانلود امن فایل خام |
| POST | `/intake/batches/{id}/archive/` | بایگانی |
| GET/POST | `/intake/mapping-profiles/` | پروفایل‌های نگاشت مدرسه |

> قاعده: برای `school_operator`، مدرسه‌ی مقصد همیشه از
> `request.user.school_tenant` می‌آید. ارسال `school` در بدنه یا کوئری
> توسط این نقش نادیده گرفته می‌شود.

مسیر‌های پردازش (`/process/`، `/approve/`) و خروجی‌ها در فازهای بعدی
به این جدول اضافه می‌شوند.

## فرمت خطاها

```json
{
  "detail": "پیام عمومی"
}
```

یا برای خطای اعتبار فیلد:

```json
{
  "field_name": ["پیام خطا"]
}
```

خطاهای اعتبارسنجی داده‌ی ردیف‌ها ساختاریافته‌تر هستند (در فاز ۴):

```json
{
  "code": "E-NID-CHECKSUM",
  "severity": "error",
  "field": "student.national_id",
  "message": "کد ملی واردشده معتبر نیست.",
  "source_column": "کدملی",
  "source_row": 42
}
```

## مستند تعاملی

پس از اجرای بک‌اند:

- Swagger UI: `/api/docs/`
- Schema: `/api/schema/`

## مثال فراخوانی با cURL

```bash
# ورود
curl -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"op01","password":"Operator@12345"}'

CSRF=$(grep csrf_token cookies.txt | awk '{print $7}')

# آپلود
curl -b cookies.txt -H "X-CSRFToken: $CSRF" \
  -F "file=@sample.xlsx" \
  -F "academic_year_label=1405-1406" \
  http://localhost:8000/api/v1/intake/batches/upload/
```
