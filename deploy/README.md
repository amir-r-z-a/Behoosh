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
cp .env.example .env
# DATABASE_URL و API_TOKEN را پر کن
```

۳. بالا آوردن سرویس‌ها:
```bash
cd deploy
docker compose up -d --build
```

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
