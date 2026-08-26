# راهنمای استقرار روی سرور اوبونتو ۲۴.۰۴

این راهنما گام‌به‌گام پیکربندی سرور تازه برای اجرای پرتال ورود داده را شرح می‌دهد.
پس از پایان این راهنما، سامانه با HTTPS روی دامنه‌ی شما در دسترس خواهد بود و
پشتیبان‌گیری منظم انجام می‌شود.

## ۱) پیش‌نیازهای سرور

- Ubuntu Server 24.04 LTS
- حداقل ۲ vCPU و ۴ گیگابایت RAM (۵۰ گیگ SSD)
- دسترسی `sudo`
- یک دامنه یا زیردامنه (مثلاً `import.example.ir`) که DNS آن به IP سرور وصل باشد.

روی سرور محلی به‌جای نصب جداگانه‌ی Python/Node/PostgreSQL، فقط Docker لازم است:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg ufw git
```

نصب Docker Engine و Compose plugin:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
docker --version && docker compose version
```

## ۲) امن‌سازی SSH و فایروال

```bash
# فقط کلید، بدون ورود با رمز
sudo sed -i 's/#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

# فایروال
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

> هیچ‌گاه پورت‌های 5432 (PostgreSQL)، 8000 (Django) یا 5173 (Vite) را باز نکنید.
> در `docker-compose.prod.yml` فقط Caddy روی 80/443 به اینترنت وصل است.

## ۳) گرفتن کد و تنظیم `.env`

```bash
git clone <your-repo-url> /opt/intake-portal
cd /opt/intake-portal
cp .env.example .env
nano .env
```

حداقل مقادیری که باید تغییر کنید:

- `SECRET_KEY` — خروجی `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`
- `POSTGRES_PASSWORD` — یک رمز قوی
- `ALLOWED_HOSTS` و `CSRF_TRUSTED_ORIGINS` و `DOMAIN` — دامنه‌ی واقعی

## ۴) اجرای استک

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

اولین اجرا چند دقیقه طول می‌کشد (build ایمیج‌ها + migrate + collectstatic).
بعد از آماده‌شدن کانتینرها، اولین مدیر فنی را بسازید:

```bash
docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
```

ساخت یک مدرسه و اپراتور (بدون نیاز به لاگین):

```bash
docker compose -f docker-compose.prod.yml exec backend \
  python manage.py create_school_operator
```

## ۵) بررسی سلامت

```bash
curl -fsS https://import.example.com/healthz/
# {"status": "ok"}
```

- لاگ‌ها: `docker compose -f docker-compose.prod.yml logs -f --tail=200`
- وضعیت کانتینرها: `docker compose -f docker-compose.prod.yml ps`
- مهاجرت‌ها: `docker compose -f docker-compose.prod.yml exec backend python manage.py showmigrations`

## ۶) به‌روزرسانی نسخه

```bash
cd /opt/intake-portal
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec backend python manage.py migrate --noinput
docker compose -f docker-compose.prod.yml exec backend python manage.py collectstatic --noinput
```

## ۷) پشتیبان‌گیری خودکار

یک اسکریپت پشتیبان شبانه بسازید:

```bash
sudo mkdir -p /opt/intake-portal/backups
sudo tee /etc/cron.d/intake-backup >/dev/null <<'EOF'
0 3 * * * root cd /opt/intake-portal && docker compose -f docker-compose.prod.yml exec -T db pg_dump -U intake intake | gzip > backups/db-$(date +\%F).sql.gz && tar czf backups/files-$(date +\%F).tar.gz -C /var/lib/docker/volumes/intake-portal_private_files/_data .
EOF
```

برای نگه‌داری ۷ روزه:

```bash
0 4 * * * root find /opt/intake-portal/backups -mtime +7 -delete
```

**پشتیبان‌ها باید خارج از همان سرور نگه‌داری شوند** (مثلاً با `rclone`
به S3 یا یک فضای ابری دیگر). بدون خام‌کردن پایگاه داده و تست
restore، پشتیبان قابل اتکا نیست. هر سه ماه یک‌بار فایل پشتیبان را در یک
محیط آزمایشی بازیابی و سلامت داده را تأیید کنید.

برای رمزنگاری پشتیبان‌ها (توصیه‌ی اکید برای داده‌ی حساس):
[backup-restore.md](backup-restore.md).

## ۸) مانیتورینگ پایه

- فضای دیسک: `df -h` و هشدار روی ۸۵٪
- وضعیت کانتینرها: `docker ps`
- لاگ‌های Django در `docker compose logs backend`
- خطا‌های ۵xx در لاگ Caddy: `docker compose logs caddy`

## ۹) چک‌لیست امنیتی قبل از اولین داده‌ی واقعی

- [ ] `DEBUG=0`
- [ ] `SECRET_KEY` قوی و خارج از Git
- [ ] HTTPS فعال و HSTS هدر می‌شود
- [ ] کوکی‌ها `Secure`, `HttpOnly` هستند
- [ ] CSRF فعال و `CSRF_TRUSTED_ORIGINS` درست تنظیم شده
- [ ] پورت‌های Postgres/Django به اینترنت باز نیستند
- [ ] فایل‌های Excel خارج از مسیر public ذخیره می‌شوند
- [ ] Rate limit روی لاگین فعال است
- [ ] رمز اولیه‌ی اپراتور تصادفی و در اولین فرصت تعویض می‌شود
- [ ] AuditLog فعال است
- [ ] پشتیبان خارج از سرور و تست restore انجام شده
