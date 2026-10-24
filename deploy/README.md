# استقرار بهوش

## پیش‌نیاز
- Docker و Docker Compose
- Postgres (روی سرور موجود است) یا سرویس db در compose
- Nginx برای دامنه behoosh.hashpa.com

## مراحل

۱. کلون ریپو روی سرور:
```bash
git clone git@gitlab.radeai.info:am_mohammadi/behoosh.git
cd behoosh
```

۲. ساخت فایل محیط:
```bash
cp deploy/env/api.env.example .env
# DATABASE_URL را پر کن. API_TOKEN یا یک رشته تصادفی بلند باشد یا AUTH_LEGACY_TOKEN=false.
# مقدار نمونه CHANGE_ME پذیرفته نمی‌شود.
```

۳. بالا آوردن سرویس‌ها:
```bash
cd deploy
docker compose up -d --build
```

مایگریشن‌ها خودکار قبل از بالا آمدن API اجرا می‌شوند (`python -m app.db.migrate`).
وضعیت: `docker compose exec api python -m app.db.migrate --status`

۴. ساخت کاربر اولیه:
```bash
docker compose exec api python -m app.db.seed
```

۵. Nginx:
```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/behoosh
sudo ln -s /etc/nginx/sites-available/behoosh /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

۶. گواهی SSL:
```bash
sudo certbot --nginx -d behoosh.hashpa.com
```

## آدرس‌ها پس از استقرار
- داشبورد: https://behoosh.hashpa.com
- API: https://behoosh.hashpa.com/api/health
- MCP: https://behoosh.hashpa.com/mcp/
