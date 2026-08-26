# پرتال مرکزی ورود، استانداردسازی و بررسی داده مدارس

پروژه‌ای **مستقل** برای جمع‌آوری، استانداردسازی و اعتبارسنجی فایل‌های Excel
ثبت‌نام مدارس، بدون هیچ‌گونه اتصال یا نوشتنی به سیستم اصلی مدیریت مدرسه.

> فلسفه‌ی پروژه: اکسل مدرسه یک ورودی نامنظم است؛ این پرتال آن را بدون حذف
> بی‌صدا، بدون ادغام اشتباه افراد و بدون وابستگی به تصمیم‌های نهایی سیستم
> اصلی، به داده‌ای امن، استاندارد، قابل‌پیگیری و آماده‌ی آینده تبدیل می‌کند.

---

## معماری کلی

```
frontend/        React + TypeScript + Vite + Tailwind + shadcn/ui
backend/         Django 5 + DRF + simplejwt (gunicorn)
PostgreSQL 16    دیتابیس
Caddy            Reverse proxy لبه با HTTPS خودکار (پورت ۸۰/۴۴۳)
nginx            فقط سرو استاتیک فرانت روی شبکه‌ی داخلی داکر
```

> در توسعه‌ی محلی، Vite (پورت ۵۱۷۳) و `runserver` جنگو مستقیم اجرا می‌شوند.
> در پروداکشن، Caddy لبه‌ی بیرونی است و همه‌ی درخواست‌های `/api/`،
> `/admin/` و `/static/` را مستقیم به بک‌اند پروکسی می‌کند؛ کانتینر
> فرانت فقط فایل‌های استاتیک SPA را سرو می‌کند.

- **احراز هویت:** JWT در کوکی `HttpOnly + Secure` + CSRF به‌صورت double-submit.
  هیچ توکنی در `localStorage` ذخیره نمی‌شود.
- **جداسازی داده:** `school_id` هرگز از درخواست کاربر خوانده نمی‌شود؛ همیشه
  از `request.user.school_tenant` استخراج می‌شود.
- **ذخیره‌ی فایل خام:** خارج از هر مسیر عمومی، با نام UUID، با مجوز `0640`،
  بدون URL عمومی، دانلود فقط از ویوی احراز هویت‌شده.
- **پردازش اکسل:** فقط `openpyxl` در حالت `read_only=True`؛ پانداس ممنوع
  است (صفرهای ابتدایی کد ملی/تلفن را خراب می‌کند).

اسناد تکمیلی:

- [تصمیم‌های معماری (ADR)](docs/decisions.md)
- [واژه‌نامه](docs/glossary.md)
- [مرور API](docs/api.md)
- [عیب‌یابی](docs/troubleshooting.md)
- [معیارهای عملکرد](docs/performance.md)
- [پشتیبان‌گیری و بازیابی](docs/backup-restore.md)
- [چک‌لیست معیار پذیرش](docs/acceptance-checklist.md)

---

## پیش‌نیازها

- Docker و Docker Compose (برای استقرار ساده)
- یا به‌صورت محلی: Python 3.11+، Node 20+، PostgreSQL 14+

---

## اجرای سریع با Docker

```bash
cp .env.example .env
# .env را ویرایش کنید و حداقل SECRET_KEY و POSTGRES_PASSWORD را مقادیر
# قوی بگذارید. DEBUG=0 و DJANGO_SECURE=1 را برای تولید فعال کنید.

docker compose up -d --build
```

ایجاد **اولین مدیر فنی** (هیچ کاربری خودکار ساخته نمی‌شود):

```bash
docker compose run --rm backend python manage.py createsuperuser
```

ایجاد یک مدرسه و حساب مسئول آن:

```bash
docker compose -f docker-compose.yml run --rm backend \
  python manage.py create_school_operator
# به‌صورت تعاملی نام مدرسه، کد خارجی، نام کاربری و رمز را می‌پرسد.
# یا غیرتعاملی:
docker compose run --rm backend \
  python manage.py create_school_operator \
    --school-name "دبستان الف" --school-code "SCHOOL-01" \
    --username "op01" --password "StrongPass@123"
```

سپس:

- فرانت: <http://localhost:8080>
- پنل ادمین جنگو: <http://localhost:8080/admin/>
- مستندات تعاملی API (Swagger): <http://localhost:8080/api/docs/>

> در محیط تولید حتماً `DEBUG=0` و `DJANGO_SECURE=1` را تنظیم کنید و
> دامنه‌ی واقعی را در `ALLOWED_HOSTS` و `CORS_ALLOWED_ORIGINS` بگذارید.

---

## اجرای محلی بدون داکر

### بک‌اند

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# متغیرهای دیتابیس
export POSTGRES_DB=school_intake POSTGRES_USER=intake \
       POSTGRES_PASSWORD=intake POSTGRES_HOST=localhost
export SECRET_KEY="dev-secret-change-me"
export DEBUG=1 ALLOWED_HOSTS=localhost,127.0.0.1 COOKIE_SECURE=0
export PRIVATE_STORAGE_ROOT=/tmp/intake-private

python manage.py migrate
python manage.py createsuperuser
python manage.py create_school_operator   # تعاملی
python manage.py runserver 0.0.0.0:8000
```

### فرانت

```bash
cd frontend
npm install
npm run dev
```

Vite روی <http://localhost:5173> بالا می‌آید و `/api` را به
`http://localhost:8000` پروکسی می‌کند (same-origin، کوکی‌ها کار می‌کنند).

---

## ساختار مخزن

```
.
├── backend/
│   ├── config/              # تنظیمات، URLها، میدلور CSRF
│   ├── apps/
│   │   ├── core/            # مدل پایه، permissions، mixin ایزولیشن
│   │   ├── audit/           # AuditLog + سرویس ثبت
│   │   ├── accounts/        # PortalUser، احراز هویت JWT کوکی
│   │   ├── schools/         # SchoolTenant + مدیریت اپراتورها
│   │   └── intake/          # ImportBatch, MappingProfile, سرویس اکسل
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/             # کلاینت fetch با refresh خودکار + تایپ‌ها
│       ├── auth/            # AuthContext
│       ├── components/ui/   # اجزای shadcn/ui (Button, Card, Table, ...)
│       ├── components/      # AppShell، DataTable و ...
│       └── pages/           # Login، Dashboard، Batches، UploadWizard ...
├── docs/
├── docker-compose.yml
└── Makefile
```

---

## متغیرهای محیطی

همه‌ی متغیرها در [`.env.example`](.env.example) توضیح داده شده‌اند.
موارد الزامی برای تولید:

- `SECRET_KEY` — رشته‌ی تصادفی بلند (حداقل ۵۰ کاراکتر)
- `DEBUG=0`، `DJANGO_SECURE=1`
- `ALLOWED_HOSTS` با دامنه‌ی واقعی
- `POSTGRES_PASSWORD` قوی
- `CORS_ALLOWED_ORIGINS` با دامنه‌ی واقعی فرانت (در صورت استقرار هم‌دامنه از طریق nginx لازم نیست)

---

## تست‌ها

```bash
cd backend
source .venv/bin/activate
pytest
```

تست‌ها پوشش می‌دهند: ورود موفق/ناموفق، کوکی‌های HttpOnly، محافظت CSRF،
دسترسی‌نداشتن اپراتور به پنل ادمین، ایزولیشن کامل مدرسه (فهرست، جزئیات و
دانلود فایل خام بین مدرسه‌ها)، رد فرمت‌های غیر `.xlsx`، اعتبارسنجی سال
تحصیلی، و کشف ستون‌های تکراری با حفظ صفر ابتدایی کد ملی.

---

## پشتیبان‌گیری و بازیابی

راهنمای کامل در [`docs/backup-restore.md`](docs/backup-restore.md). خلاصه:

```bash
docker compose exec -T db pg_dump -U intake -d school_intake -Fc > backups/db.dump
```

بک‌آپ‌های حاوی داده‌ی حساس باید با AES256 رمزنگاری شوند (دستور دقیق در
سند).

---

## وضعیت فازها

- [x] **فاز ۰ — اسکلت و زیرساخت**
  - کاربر سفارشی، احراز هویت JWT کوکی + CSRF، مدرسه و نقش‌ها
  - ایزولیشن پایه، فرانت RTL فارسی، داکر، تست‌ها و مستندات
  - **بدون داده‌ی دمو**؛ اولین ادمین با `createsuperuser`
- [x] **فاز ۱ — آپلود امن فایل**
  - مدل `ImportBatch`, `MappingProfile`
  - ذخیره‌ی خصوصی با UUID، اعتبارسنجی نوع/حجم/ساختار
  - کشف برگه‌ها و ستون‌ها با openpyxl
  - Upload Wizard سه‌گامه در فرانت (فایل → برگه/هدر → بررسی ستون‌ها)
  - دانلود امن فایل خام با کنترل مدرسه
  - ثبت تمام عملیات در AuditLog
- [x] **فاز ۲ — Mapping ستون‌ها**
  - واژگان استاندارد ۶۰+ فیلد در گروه‌های هویت/ثبت‌نام/تماس/پدر/مادر/سوابق
  - نرمال‌سازی عنوان (ي/ك، ارقام فارسی، فاصله‌های نامرئی)
  - پیشنهاد هوشمند با تشخیص موقعیت برای ستون‌های تکراری
  - صفحه‌ی Mapping در فرانت: نمونه مقادیر، فیلتر (همه/نگاشت‌نشده/تکراری)،
    انتخاب دستی، ذخیره به‌عنوان پروفایل، پذیرش یک‌جای پیشنهادها
- [x] **فاز ۳ — Extract / Stage / Normalize**
  - مدل‌های `ImportRow`, `StagedStudent`, `StagedGuardian`
  - ذخیره‌ی `raw_data` و `normalized_data` کنار هم (هیچ سطری حذف نمی‌شود)
  - نرمال‌سازی: کد ملی با چک‌سام ایران، متن فارسی، موبایل، تاریخ شمسی/میلادی، جنسیت، پایه
  - `field_provenance` برای هر فیلد (منبع: batch/row/column/raw/normalized)
  - پردازش سطر-به-سطر با `transaction.atomic` و savepoint مستقل
  - endpointهای `/process/`, `/students/`, `/rows/`
  - صفحه‌ی «دانش‌آموزان و پردازش» در فرانت با جدول TanStack، فیلتر وضعیت و آمار
- [x] **فاز ۴ — Validation و وضعیت‌ها**
  - موتور اعتبارسنجی cross-row: تکرار قطعی با کد ملی (درون و بین Batchها)، تکرار احتمالی با نام+تاریخ تولد یا موبایل
  - هیچ ادغام خودکاری انجام نمی‌شود؛ فقط هشدار با ارجاع به رکوردهای مشابه
  - گردش‌کار وضعیت: incomplete / needs_review / pending_placement / validated / approved
  - endpointهای `/revalidate/` و `/approve/` (تأیید نهایی تا رفع نقص‌ها مسدود است)
  - صفحه‌ی «موارد نیازمند بررسی» با تب‌های ناقص/نیازمند بررسی/مشکوک به تکرار/در انتظار کلاس/معتبر
  - دکمه‌ی تأیید نهایی مدرسه با پیام خطای شفاف
- [x] **فاز ۵ — اصلاح دستی و گردش کار بررسی**
  - endpoint `PATCH /intake/students/{id}/` با اعتبارسنجی دلیل برای فیلدهای حساس
    (نام، نام خانوادگی، کد ملی، تاریخ تولد، جنسیت، پایه، شماره تماس ضروری)
  - **raw_data در `ImportRow` هرگز تغییر نمی‌کند**؛ فقط `StagedStudent` و
    `field_provenance` به‌روزرسانی می‌شوند
  - به‌روزرسانی `field_provenance` با `last_edited_by`, `last_edited_at`, `edit_reason`
  - AuditLog غنی: چه کسی/چه زمانی/کدام فیلد/مقدار قبل/مقدار جدید/دلیل/مدرسه/Batch/Student
  - اجرای خودکار نرمال‌سازی/اعتبارسنجی و محاسبه‌ی وضعیت بعد از هر ویرایش
  - مدل **`DuplicateResolution`** با چهار تصمیم: confirmed_duplicate،
    confirmed_distinct_people، corrected_source_data، needs_follow_up
  - Resolve کردن هشدار هویتی **بدون Merge یا حذف خودکار**؛ صرفاً ثبت نظر انسان
  - تا حل‌وفصل همه‌ی هشدارهای هویتی، تأیید نهایی Batch ممکن نیست
  - کد ملی در لیست‌ها Masked و فقط در فرم ویرایش (برای کاربر مجاز) کامل است
  - دیالوگ ویرایش: نمایش مقدار خام اکسل در کنار مقدار نرمال‌شده، نشان «حساس»
  - دیالوگ «رفع ابهام» با چهار تصمیم و توضیح اجباری
  - ۱۲ تست شامل: الزام دلیل، تغییر وضعیت، ثبت Audit، عدم تغییر raw_data،
    Resolve بدون Merge، انسداد Approve تا رفع هشدارها، و ایزولیشن مدرسه
- [x] **فاز ۶ — گزارش و خروجی**
  - گزارش خطاها (.xlsx): ردیف/نام/کد ملی/پایه/وضعیت/خطاها/هشدارها/پیشنهاد اقدام
  - خروجی استاندارد (.xlsx): شیت «دانش‌آموزان» با ۲۲ ستون استاندارد + شیت «والدین»
  - خروجی استاندارد نسخه‌بندی‌شده (.json) با `schema_version = "1.0"`،
    `external_code` مدرسه، و هش فایل برای اتصال آینده
  - محافظت در برابر **Formula Injection** (پیشوند `'` برای مقادیر شروع‌شونده با
    `=`, `+`, `-`, `@`, Tab, CR)
  - endpointها از ایزولیشن مدرسه ارث می‌برند (۴۰۴ برای مدرسه‌ی دیگر)
  - هر دانلود در AuditLog ثبت می‌شود
  - دانلود قبل از پردازش با ۴۰۰ رد می‌شود
  - صفحه‌ی «گزارش‌ها و خروجی» در فرانت با سه کارت دانلود
  - ۷ تست جدید: ایمنی سلول، فرمت/تعداد شیت، نسخه‌بندی قرارداد، ایزولیشن،
    ثبت Audit، و انسداد قبل از پردازش
- [x] **فاز ۷ — داشبورد و پنل ادمین**
  - `GET /dashboard/` با آمار مدرسه (یا همه برای ادمین): تعداد Batch/دانش‌آموز/تأییدشده، شمارش وضعیت‌ها، ۱۰ فایل اخیر
  - `GET/POST /admin/schools/` و `PATCH /admin/schools/{id}` برای مدیر فنی
  - `GET/POST /admin/operators/` و `PATCH /admin/operators/{id}` با رمز حداقل ۱۰ کاراکتر
  - `GET /admin/audit-log/` با فیلتر بر اساس action/entity/school
  - همه‌ی endpointهای ادمین با `IsSystemAdmin` محافظت می‌شوند (۴۰۳ برای اپراتور)
  - داشبورد در فرانت با کارت‌های آماری، فهرست فایل‌های اخیر و توزیع وضعیت
  - صفحه‌ی «مدرسه‌ها و اپراتورها» با دیالوگ‌های ساخت
  - صفحه‌ی «لاگ امنیتی» با فیلتر و نمایش انسان‌خواندنی actionها
  - منوی کناری بر اساس نقش (admin/operator) تغییر می‌کند
  - ۴ تست جدید برای داشبورد، ایزولیشن، ساخت مدرسه+اپراتور و لاگ
- [x] **فاز ۸ — استحکام نهایی و استقرار**
  - فایل `docker-compose.prod.yml` با چهار سرویس: db/backend/frontend/caddy
  - Caddyfile با HTTPS خودکار، HSTS و هدرهای امنیتی
  - `.env.example` کامل بدون هیچ secret واقعی
  - endpoint سلامت `/healthz/` بدون افشای داده
  - راهنمای گام‌به‌گام استقرار روی Ubuntu 24.04 با SSH امن، UFW، بکاپ شبانه
  - چک‌لیست امنیتی قبل از اولین داده‌ی واقعی
  - فایل `.dockerignore` برای بک‌اند
  - تأیید ۷۰ تست و بیلد موفق هر دو فرانت و بک

- [x] **فاز ۸+ — سخت‌سازی نهایی**
  - اجبار تغییر رمز در اولین ورود (`must_change_password`): اپراتورهای
    تازه‌ساخت‌شده توسط ادمین تا تغییر رمز موقت نمی‌توانند از سامانه استفاده کنند
  - endpoint امن `POST /auth/change-password/` با اعتبارسنجی رمز فعلی و
    اعمال قوانین قدرت رمز جنگو
  - دیالوگ تغییر رمز در فرانت (حالت اجباری غیرقابل بستن + حالت اختیاری
    از منوی کاربری)
  - ثبت تغییر رمز در AuditLog
  - فیلد `must_change_password` در خروجی `/auth/me/`
  - **۷۰ تست پاس** (۵ تست جدید برای جریان تغییر رمز)
  - هر ۱۸ معیار پذیرش تیک خوردند
