# راهنمای پشتیبان‌گیری و بازیابی (Backup & Restore)

این پرتال دو نوع داده‌ی حیاتی دارد:

1. **پایگاه‌داده PostgreSQL** — شامل کاربران، Batchها، ردیف‌های خام،
   داده‌ی نرمال‌شده، پرونده‌های دانش‌آموزان، Mappingها و Audit log.
2. **فایل‌های خصوصی Excel خام** — در مسیر `PRIVATE_STORAGE_ROOT`
   (در داکر volume به نام `private_files`).

هیوقت یکی بدون دیگری بک‌آپ کامل نیست: بدون فایل خام، منشأ داده قابل
اثبات نیست؛ بدون دیتابیس، نگاشت و اعتبارسنجی از دست می‌رود.

---

## ۱. پشتیبان‌گیری از دیتابیس

به‌صورت دستی:

```bash
docker compose exec -T db \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc \
  > "backups/db-$(date +%F-%H%M).dump"
```

یا از اسکریپت آماده‌ی `backend/scripts/backup.sh` استفاده کنید که هم پایگاه
داده و هم فایل‌های خصوصی را پشتیبان می‌گیرد و می‌تواند با GPG رمزنگاری کند:

```bash
# یک‌بار دستی اجرا کنید تا از کار کردنش مطمئن شوید:
sudo BACKUP_DIR=/var/backups/intake /opt/intake-portal/backend/scripts/backup.sh

# در cron هر شب ساعت ۳:
echo "0 3 * * * root BACKUP_DIR=/var/backups/intake /opt/intake-portal/backend/scripts/backup.sh >> /var/log/intake-backup.log 2>&1" \
  | sudo tee /etc/cron.d/intake-backup
```

متغیرهای قابل تنظیم اسکریپت: `BACKUP_DIR`، `RETENTION_DAYS`،
`POSTGRES_DB`، `POSTGRES_USER`، `PRIVATE_VOLUME` و
`BACKUP_PASSPHRASE_FILE` (برای رمزنگاری GPG).

- `-Fc` فرمت فشرده‌ی سفارشی PostgreSQL است که برای restore سریع و
  انتخابی مناسب است.
- بک‌آپ‌ها را خارج از همان سرور (مثلاً S3 یا storage مجزا) نگه دارید.
- دوره‌ی نگه‌داری پیشنهادی: روزانه ۱۴ روز، هفتگی ۸ هفته.

### رمزنگاری بک‌آپ حساس

این پرتال حاوی داده‌ی حساس کودکان است؛ بک‌آپ‌ها را قبل از خروج از
سرور رمز کنید:

```bash
# پایگاه‌داده
docker compose exec -T db pg_dump -U intake -d intake -Fc \
  | gpg --symmetric --cipher-algo AES256 --batch --yes \
        --passphrase-file /root/.backup-passphrase \
  > "backups/db-$(date +%F).dump.gpg"

# فایل‌های خصوصی
tar -czf - -C /var/lib/docker/volumes/.../_data . \
  | gpg --symmetric --cipher-algo AES256 --batch --yes \
        --passphrase-file /root/.backup-passphrase \
  > "backups/files-$(date +%F).tar.gz.gpg"
```

عبارت عبور (`/root/.backup-passphrase`) باید روی یک سامانه‌ی مدیریت رمز
(مانند Vault یا یک secret manager) نگه‌داری شود و هرگز کنار بک‌آپ قرار
نگیرد.

بازیابی فایل رمزشده:

```bash
gpg -d backups/db-2026-08-22.dump.gpg \
  | docker compose exec -T db pg_restore -U intake -d intake --no-owner
```

## ۲. پشتیبان‌گیری از فایل‌های خصوصی

```bash
docker run --rm \
  -v school-intake_private_files:/data:ro \
  -v "$(pwd)/backups:/backup" \
  alpine tar -czf "/backup/files-$(date +%F-%H%M).tar.gz" -C /data .
```

نام volume ممکن است بسته به نام پروژه متفاوت باشد؛ با
`docker volume ls` بررسی کنید.

## ۳. بازیابی دیتابیس

**هشدار:** این کار داده‌ی فعلی را جایگزین می‌کند.

```bash
# ۱. توقف backend برای جلوگیری از نوشتن هم‌زمان
docker compose stop backend

# ۲. (در صورت نیاز) خالی‌کردن دیتابیس موجود
docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS $POSTGRES_DB;" \
  -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;"

# ۳. بازیابی از فایل dump
cat backups/db-YYYY-MM-DD-HHMM.dump | \
  docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner

# ۴. اجرای migration برای اطمینان از سازگاری اسکیما
docker compose run --rm backend python manage.py migrate

# ۵. شروع مجدد
docker compose start backend
```

## ۴. بازیابی فایل‌های خصوصی

```bash
docker run --rm \
  -v school-intake_private_files:/data \
  -v "$(pwd)/backups:/backup:ro" \
  alpine sh -c "rm -rf /data/* && tar -xzf /backup/files-YYYY-MM-DD-HHMM.tar.gz -C /data"
```

## ۵. تست بازیابی (مهم!)

یک بک‌آپ که هرگز بازیابی نشده، بک‌آپ محسوب نمی‌شود. به‌صورت دوره‌ای
(مثلاً ماهانه) در یک محیط staging:

1. یک نمونه‌ی خالی از stack را بالا بیاورید.
2. آخرین dump را restore کنید.
3. فایل‌های خصوصی را restore کنید.
4. بررسی کنید که:
   - کاربران می‌توانند لاگین کنند؛
   - Batchها و ردیف‌ها در دسترس‌اند؛
   - فایل خام یک Batch قابل دانلود است؛
   - تعداد رکوردها با انتظار تطبیق دارد.

## ۶. امنیت بک‌آپ‌ها

- فایل‌های بک‌آپ حاوی داده‌ی حساس کودکان‌اند؛ آن‌ها را با رمز نگه‌داری
  کنید (مثلاً `gpg --symmetric` یا encryption سمت S3).
- دسترسی به مسیر بک‌آپ محدود به کاربر مورد اعتماد باشد.
- هرگز بک‌آپ را در مخزن گیت یا روی فضای عمومی قرار ندهید.
