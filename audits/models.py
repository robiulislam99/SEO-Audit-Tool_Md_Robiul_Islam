# audits/models.py

from django.db import models
from django.core.validators import URLValidator
from django.utils import timezone


class Audit(models.Model):
    """
    One record per audit request.
    Represents a single URL being checked, its overall status, and final score.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    url = models.URLField(
        max_length=500,
        validators=[URLValidator()],
        help_text="The website URL being audited"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Current state of this audit job"
    )

    score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Overall SEO score out of 100 (null until audit completes)"
    )

    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Populated only if status is 'failed' — stores what went wrong"
    )

    error_type = models.CharField(
        max_length=30,
        null=True,
        blank=True,
        help_text="Machine-readable error category, e.g. 'timeout', 'dns_error'"
    )

    created_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the audit was requested"
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the audit finished (success or failure)"
    )

    class Meta:
        ordering = ['-created_at']  # newest audits first
        verbose_name = "Audit"
        verbose_name_plural = "Audits"

    def __str__(self):
        return f"{self.url} — {self.status} ({self.score if self.score is not None else 'N/A'})"

    def mark_completed(self, score):
        """Convenience method to mark an audit as finished with a score."""
        self.status = self.Status.COMPLETED
        self.score = score
        self.completed_at = timezone.now()
        self.save()

    def mark_failed(self, error_message, error_type="unknown"):
        """Convenience method to mark an audit as failed."""
        self.status = self.Status.FAILED
        self.error_message = error_message
        self.error_type = error_type
        self.completed_at = timezone.now()
        self.save()


class AuditResult(models.Model):
    """
    One record per individual SEO check performed within an Audit.
    E.g. "Title tag check", "Meta description check", "H1 heading check", etc.
    """

    class Category(models.TextChoices):
        TECHNICAL = 'technical', 'Technical'
        ON_PAGE = 'on_page', 'On-Page'
        PERFORMANCE = 'performance', 'Performance'
        SOCIAL = 'social', 'Social'
        STRUCTURED_DATA = 'structured_data', 'Structured Data'
        ACCESSIBILITY = 'accessibility', 'Accessibility'

    class Severity(models.TextChoices):
        PASS_ = 'pass', 'Pass'
        WARNING = 'warning', 'Warning'
        FAIL = 'fail', 'Fail'

    audit = models.ForeignKey(
        Audit,
        on_delete=models.CASCADE,
        related_name='results',
        help_text="The parent audit this result belongs to"
    )

    check_name = models.CharField(
        max_length=100,
        help_text="Short identifier, e.g. 'title_tag', 'meta_description', 'h1_heading'"
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.ON_PAGE,
    )

    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.PASS_,
    )

    passed = models.BooleanField(
        default=False,
        help_text="True if this check passed, False otherwise"
    )

    message = models.CharField(
        max_length=500,
        help_text="Human-readable explanation, e.g. 'Title is 72 characters — too long'"
    )

    affected_element = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="The specific tag/element this check refers to, e.g. '<title>' or 'img[src=\"/logo.png\"]'"
    )

    recommendation = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="Actionable suggestion for fixing this issue, shown only when severity != pass"
    )

    details = models.JSONField(
        null=True,
        blank=True,
        help_text="Optional structured extra data, e.g. list of image URLs missing alt text"
    )

    class Meta:
        ordering = ['category', 'check_name']
        verbose_name = "Audit Result"
        verbose_name_plural = "Audit Results"

    def __str__(self):
        return f"[{self.severity}] {self.check_name} ({self.audit.url})"