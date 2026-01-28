# Foolad24 Supplier Crawler

این اسکریپت لیست تامین‌کنندگان را از `foolad24.com` کرال می‌کند و خروجی را در فایل اکسل ذخیره می‌کند.

## نصب

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## اجرا

```bash
python crawler.py --output output/suppliers.xlsx --delay 2
```

برای اجرای دوره‌ای:

```bash
python crawler.py --output output/suppliers.xlsx --delay 2 --run-every-min 60
```

## ستون‌های خروجی

- title: عنوان تامین‌کننده
- ceo: مدیرعامل
- user_code: کد کاربری
- membership_date: تاریخ عضویت
- user_type: نوع کاربر
- address: آدرس
- trade: trade
- detail_url: لینک صفحه جزئیات
- scraped_at: زمان کرال (UTC)
