# audits/tasks.py
from scraper.playwright_scraper import scrape_page, PageScrapeError
from .models import Audit

def run_audit(audit_id):
    audit = Audit.objects.get(id=audit_id)
    audit.status = Audit.Status.RUNNING
    audit.save()

    try:
        page_data = scrape_page(audit.url)
        # next step: pass page_data into your checker functions (scraper/checks.py)
        # then calculate score and call audit.mark_completed(score)
    except PageScrapeError as e:
        audit.mark_failed(str(e))