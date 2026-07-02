# SEO Audit Tool

A web-based SEO auditing tool built with Django and Playwright. Enter any URL, and the tool scrapes the page, runs a series of SEO checks (title length, meta description, heading structure, image alt text, keyword usage), and returns a scored report with actionable suggestions — all without leaving the page.

---

## Features

- Single-page, no-reload UI (Tailwind CSS + vanilla JavaScript + fetch API)
- Background audit processing via Django-Q2 (no page freezing while scraping)
- Playwright-based scraping — handles JS-rendered pages
- Weighted 0–100 SEO scoring system
- Categorized, human-readable pass/fail results
- Classified error handling (timeout, DNS failure, SSL issues, connection refused) with friendly messages
- Audit history stored in SQLite, viewable via Django admin

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.0 |
| Background jobs | Django-Q2 (uses Django's own DB as the broker — no Redis needed) |
| Scraping | Playwright (Python, sync API) |
| Database | SQLite |
| Frontend | HTML + Tailwind CSS (CDN) + vanilla JavaScript |

---

## Prerequisites

Before you start, make sure you have:

- **Python 3.10+** installed (`python3 --version`)
- **pip** installed
- Internet access (for installing packages and Playwright's browser binaries)

No Node.js, no npm, no database server installation required — SQLite ships with Python, and Tailwind is loaded via CDN.

---

## Setup — Step by Step

Run these commands in order, from the project root folder.

### 1. Clone / navigate into the project folder

```bash
git clone https://github.com/robiulislam99/SEO-Audit-Tool_Md_Robiul_Islam.git seo_audit_tool
cd seo_audit_tool
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv

# Activate it:
# macOS / Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

You should see `(venv)` appear at the start of your terminal prompt.

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` isn't present yet, install manually:

```bash
pip install django djangorestframework beautifulsoup4 requests playwright django-q2 python-decouple weasyprint
```

### 4. Install Playwright's browser binaries

This is a **separate step** from `pip install playwright` — it downloads the actual Chromium browser Playwright drives.

```bash
playwright install chromium
```

> **If this fails with an SSL/certificate error** (common on corporate or campus networks that intercept HTTPS traffic), try:
> ```bash
> NODE_OPTIONS="--use-system-ca" playwright install chromium
> ```
> If that still fails, try a different network (e.g. a mobile hotspot), or see the **Troubleshooting** section below.

### 5. Create your `.env` file

In the project root (same folder as `manage.py`), create a file named `.env`:

```env
SECRET_KEY=django-insecure-replace-this-with-your-own-key
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
```

> You can generate a proper secret key with:
> ```bash
> python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
> ```

### 6. Run database migrations

```bash
python manage.py migrate
```

This creates all tables, including Django-Q2's internal task tables and the app's `Audit` / `AuditResult` tables.

### 7. Create an admin user (optional but recommended)

```bash
python manage.py createsuperuser
```

Follow the prompts to set a username, email, and password. This lets you log into `/admin` and inspect audit records directly.

---

## Running the Project

The app needs **two processes running at the same time**, in two separate terminal windows (both with the virtual environment activated).

**Terminal 1 — Django dev server:**
```bash
source venv/bin/activate      # Windows: venv\Scripts\activate
python manage.py runserver
```

**Terminal 2 — Django-Q2 background worker:**
```bash
source venv/bin/activate      # Windows: venv\Scripts\activate
python manage.py qcluster
```

> The worker process (`qcluster`) is what actually runs the Playwright scraper and SEO analysis in the background. If you skip this step, audits will get stuck on "pending" forever — the web server alone cannot process them.

Once both are running, open your browser to:

```
http://127.0.0.1:8000
```

You should see the SEO Audit Tool homepage with a URL input field.

---

## How to Use It

1. Enter a full URL (e.g. `https://example.com`) into the input field
2. *(Optional)* Enter a target keyword to check keyword usage in the title/meta/H1
3. Click **Run Audit**
4. Watch the loading screen — it polls the backend every 2 seconds
5. Once complete, you'll see:
   - An overall score (0–100), color-coded green/amber/red
   - A pass/fail count summary
   - A detailed, categorized breakdown of every check with an explanation

If something goes wrong (invalid URL, site unreachable, timeout), you'll see a specific, friendly error message rather than a generic failure.

---

## Project Structure

```
seo_audit_tool/
├── manage.py
├── .env                        # not committed — create this yourself (see Step 5)
├── requirements.txt
├── db.sqlite3                  # created automatically after migrate
│
├── seo_project/                 # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── core/                        # landing page + shared templates
│   ├── templates/core/
│   │   ├── base.html
│   │   └── home.html
│   └── views.py
│
├── audits/                      # audit models, views, background task
│   ├── models.py                 # Audit, AuditResult
│   ├── views.py                  # form + JSON API views
│   ├── urls.py
│   ├── tasks.py                  # background job (scrape -> analyze -> save)
│   ├── forms.py
│   └── templates/audits/
│       ├── loading.html
│       └── report.html
│
└── scraper/                     # scraping + SEO analysis logic
    ├── playwright_scraper.py     # scrape_page() — Playwright wrapper
    └── checks.py                 # analyze_seo() — SEO scoring engine
```

---

## Admin Panel

Visit `http://127.0.0.1:8000/admin` and log in with the superuser you created in Step 7. From there you can:

- View every submitted audit and its status
- Inspect individual check results per audit
- Manually delete/reset stuck or failed audits during development

---

## Troubleshooting

**`playwright install` fails with `UNABLE_TO_VERIFY_LEAF_SIGNATURE`**
This means your network is intercepting HTTPS traffic (common on corporate/campus networks). Run:
```bash
NODE_OPTIONS="--use-system-ca" playwright install chromium
```
If that doesn't work, try installing from a different network (e.g. mobile hotspot). This only affects the Playwright *installation* step — it does not require `sudo`.

**Audits get stuck on "pending" and never complete**
The background worker isn't running. Make sure `python manage.py qcluster` is active in a separate terminal — this is required for audits to actually process.

**`django_q` tables don't exist / migration errors**
Make sure `django_q` is in `INSTALLED_APPS` in `settings.py`, then re-run:
```bash
python manage.py migrate
```

**CSRF errors when submitting the form via JavaScript**
Make sure you're running the app through `http://127.0.0.1:8000` (not opening the HTML file directly) — Django's CSRF cookie only works when served through Django itself.

**"This site can't be reached" / DNS errors on every audit**
Check your own internet connection first — the scraper needs outbound access to reach the URL you're auditing.

---

## Notes on Design Choices

- **SQLite** is used for simplicity and zero setup. It comfortably handles this app's write pattern (one audit at a time, processed sequentially by the background worker). See the *Future Improvements* section below for scaling notes.
- **Django-Q2** was chosen over Celery + Redis because it can use the existing Django database as its task broker — no extra services to install or run for a project at this scale.
- **Tailwind is loaded via CDN**, not compiled locally — this avoids requiring Node.js/npm entirely, which keeps setup to "just Python."

---

## Future Improvements (Not Yet Implemented)

- Multi-page site crawling (currently audits one URL at a time)
- PDF export of reports (WeasyPrint is installed but not yet wired up)
- PostgreSQL support for concurrent multi-user usage
- Scheduled re-audits and email alerts
- Core Web Vitals via Playwright's performance APIs

---

## License

This project was built as part of an internship assignment. Feel free to adapt or extend it.