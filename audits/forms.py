# audits/forms.py

from django import forms


class AuditSubmitForm(forms.Form):
    url = forms.URLField(
        label="Website URL",
        widget=forms.URLInput(attrs={
            "placeholder": "https://example.com",
            "class": "w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
        }),
    )
    target_keyword = forms.CharField(
        label="Target keyword (optional)",
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. seo audit tool",
            "class": "w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500",
        }),
    )