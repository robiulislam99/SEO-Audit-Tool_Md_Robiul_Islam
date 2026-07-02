# audits/forms.py

from django import forms


class AuditSubmitForm(forms.Form):
    url = forms.URLField(
        label="Website URL",
        widget=forms.URLInput(attrs={
            "placeholder": "https://example.com",
            "class": "w-full rounded-2xl border border-slate-200 bg-white/90 px-4 py-3 text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-teal-500 focus:ring-4 focus:ring-teal-500/15",
        }),
    )
    target_keyword = forms.CharField(
        label="Target keyword (optional)",
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. seo audit tool",
            "class": "w-full rounded-2xl border border-slate-200 bg-white/90 px-4 py-3 text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-teal-500 focus:ring-4 focus:ring-teal-500/15",
        }),
    )