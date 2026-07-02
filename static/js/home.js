function getCookie(name) {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
    return match ? match[2] : null;
}

const csrftoken = getCookie('csrftoken');
const formSection = document.getElementById('form-section');
const loadingSection = document.getElementById('loading-section');
const errorSection = document.getElementById('error-section');
const reportSection = document.getElementById('report-section');
const submitBtn = document.getElementById('submit-btn');
const formError = document.getElementById('form-error');

const ERROR_MESSAGES = {
    timeout: {
        title: "This site took too long to respond",
        hint: "Some sites are slow or block automated tools. Try again in a moment, or try a different page on the same site.",
    },
    dns_error: {
        title: "We couldn't find that website",
        hint: "Double-check the URL is spelled correctly, including 'https://' at the start.",
    },
    connection_refused: {
        title: "The site refused the connection",
        hint: "It may be down right now, or blocking automated visitors. Try again later.",
    },
    ssl_error: {
        title: "This site has a security certificate issue",
        hint: "We couldn't load it securely, so the audit couldn't run.",
    },
    invalid_url: {
        title: "That doesn't look like a valid URL",
        hint: "Make sure it starts with http:// or https:// and includes a valid domain.",
    },
    unknown: {
        title: "Something went wrong",
        hint: "An unexpected error occurred while auditing this site. Please try again.",
    },
};

function showFormError(message) {
    formError.textContent = message;
    formError.classList.remove('hidden');
}

function hideFormError() {
    formError.classList.add('hidden');
}

function resetSubmitButton() {
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<span>Run audit</span><span aria-hidden="true" class="transition group-hover:translate-x-0.5">→</span>';
}

function isLikelyValidUrl(value) {
    try {
        const parsed = new URL(value);
        return parsed.protocol === "http:" || parsed.protocol === "https:";
    } catch {
        return false;
    }
}

submitBtn.addEventListener('click', async () => {
    let url = document.getElementById('url-input').value.trim();
    const keyword = document.getElementById('keyword-input').value.trim();

    hideFormError();

    if (!url) {
        showFormError("Please enter a URL to audit.");
        return;
    }

    if (!/^https?:\/\//i.test(url)) {
        url = "https://" + url;
    }

    if (!isLikelyValidUrl(url)) {
        showFormError("That doesn't look like a valid URL. Example: https://example.com");
        return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>Starting audit...</span>';

    try {
        const res = await fetch("/audits/api/submit/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrftoken,
            },
            body: JSON.stringify({ url: url, target_keyword: keyword }),
        });

        const data = await res.json();

        if (!res.ok) {
            showFormError(data.error || "Something went wrong. Please try again.");
            resetSubmitButton();
            return;
        }

        formSection.classList.add('hidden');
        loadingSection.classList.remove('hidden');
        document.getElementById('loading-url').textContent = url;

        startLoadingAnimation();
        pollAuditStatus(data.audit_id, Date.now());
    } catch (err) {
        showFormError("Network error — check your connection and try again.");
        resetSubmitButton();
    }
});

function startLoadingAnimation() {
    const steps = ["step-1", "step-2", "step-3"];
    const labels = ["Fetching page...", "Analyzing SEO...", "Calculating score..."];
    let current = 0;

    steps.forEach(id => document.getElementById(id).className = "rounded-2xl border border-slate-200 bg-white px-3 py-3 text-center");
    document.getElementById(steps[0]).className = "rounded-2xl border border-teal-200 bg-teal-50 px-3 py-3 text-center text-teal-700";
    document.getElementById('loading-step').textContent = labels[0];

    window._loadingInterval = setInterval(() => {
        current = Math.min(current + 1, steps.length - 1);
        steps.forEach(id => document.getElementById(id).className = "rounded-2xl border border-slate-200 bg-white px-3 py-3 text-center");
        document.getElementById(steps[current]).className = "rounded-2xl border border-teal-200 bg-teal-50 px-3 py-3 text-center text-teal-700";
        document.getElementById('loading-step').textContent = labels[current];
    }, 2500);
}

function stopLoadingAnimation() {
    if (window._loadingInterval) {
        clearInterval(window._loadingInterval);
        window._loadingInterval = null;
    }
}

async function pollAuditStatus(auditId, startTime) {
    const elapsed = Date.now() - startTime;

    if (elapsed > 300000) {
        showError("timeout");
        return;
    }

    try {
        const res = await fetch(`/audits/api/${auditId}/status/`);
        const data = await res.json();

        if (data.status === "completed") {
            stopLoadingAnimation();
            fetchAndRenderReport(auditId);
            return;
        }

        if (data.status === "failed") {
            showError(data.error_type, data.error_message);
            return;
        }

        setTimeout(() => pollAuditStatus(auditId, startTime), 2000);
    } catch (err) {
        setTimeout(() => pollAuditStatus(auditId, startTime), 3000);
    }
}

function showError(errorType, customMessage) {
    loadingSection.classList.add('hidden');
    errorSection.classList.remove('hidden');

    const info = ERROR_MESSAGES[errorType] || ERROR_MESSAGES.unknown;
    document.getElementById('error-title').textContent = info.title;
    document.getElementById('error-message').textContent = customMessage || info.hint;
}

async function fetchAndRenderReport(auditId) {
    try {
        const res = await fetch(`/audits/api/${auditId}/report/`);
        const data = await res.json();

        if (!res.ok) {
            showError("unknown", "The report couldn't be loaded. Please try again.");
            return;
        }

        renderReport(data);
        loadingSection.classList.add('hidden');
        reportSection.classList.remove('hidden');
    } catch (err) {
        showError("unknown", "The report couldn't be loaded. Please try again.");
    }
}

function severityBadge(severity) {
    if (severity === "pass") {
        return { icon: "&check;", classes: "bg-emerald-100 text-emerald-700" };
    }
    if (severity === "warning") {
        return { icon: "!", classes: "bg-amber-100 text-amber-700" };
    }
    return { icon: "&times;", classes: "bg-rose-100 text-rose-700" };
}

function renderReport(data) {
    const passed = data.results.filter(r => r.severity === "pass");
    const warnings = data.results.filter(r => r.severity === "warning");
    const failed = data.results.filter(r => r.severity === "fail");

    let scoreColorClass = "border-rose-500 text-rose-600";
    let scoreLabel = "Poor";
    if (data.score >= 80) {
        scoreColorClass = "border-emerald-500 text-emerald-600";
        scoreLabel = "Strong";
    } else if (data.score >= 50) {
        scoreColorClass = "border-amber-500 text-amber-600";
        scoreLabel = "Needs improvement";
    }
    const [borderClass, textClass] = scoreColorClass.split(' ');

    const resultsHtml = data.results.map(r => {
        const badge = severityBadge(r.severity);
        return `
            <div class="p-4 sm:p-5 flex items-start gap-3 sm:gap-4">
                <span class="mt-0.5 flex-shrink-0 w-7 h-7 rounded-full ${badge.classes} flex items-center justify-center text-sm font-bold">
                    ${badge.icon}
                </span>
                <div class="flex-1">
                    <p class="text-sm font-semibold text-slate-900">${escapeHtml(r.check_name.replace(/_/g, ' '))}</p>
                    <p class="mt-1 text-sm leading-6 text-slate-600">${escapeHtml(r.message)}</p>
                    ${r.affected_element ? `<p class="mt-2 inline-block rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-500">${escapeHtml(r.affected_element)}</p>` : ''}
                    ${r.recommendation ? `<p class="mt-2 text-sm font-medium text-teal-700">Recommendation: ${escapeHtml(r.recommendation)}</p>` : ''}
                </div>
            </div>
        `;
    }).join('');

    reportSection.innerHTML = `
        <div class="mb-6">
            <div class="flex flex-wrap items-center gap-3">
                <button onclick="resetForm()" class="inline-flex items-center gap-2 text-sm font-semibold text-teal-700 hover:text-teal-800">
                    <span aria-hidden="true">&larr;</span>
                    <span>Run another audit</span>
                </button>
                <a href="/audits/${data.audit_id}/report/pdf/" class="inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-4 py-2 text-sm font-semibold text-teal-800 transition hover:bg-teal-100" target="_blank" rel="noopener">
                    <span aria-hidden="true">⬇</span>
                    <span>Download Report</span>
                </a>
            </div>
        </div>

        <div class="glass-panel rounded-[2rem] p-6 sm:p-8 mb-8 text-center">
            <div class="mx-auto flex max-w-3xl flex-col items-center gap-6">
                <div class="inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-teal-700">Audit complete</div>
                <div>
                    <p class="text-sm font-medium text-slate-500 mb-2 break-all">${escapeHtml(data.url)}</p>
                    <h2 class="section-title text-3xl font-bold text-slate-900 sm:text-4xl">Your SEO score is ready.</h2>
                </div>
                <div class="mx-auto flex h-36 w-36 items-center justify-center rounded-full border-8 bg-white ${borderClass}">
                    <span class="text-5xl font-bold ${textClass}">${data.score}</span>
                </div>
                <div>
                    <p class="text-lg font-semibold ${textClass}">${scoreLabel}</p>
                    <p class="mt-1 text-sm text-slate-500">Audited on ${escapeHtml(data.completed_at || '')}</p>
                </div>
            </div>
        </div>

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-3 mb-8">
            <div class="glass-panel rounded-3xl p-5 text-center">
                <p class="text-2xl font-bold text-emerald-700">${passed.length}</p>
                <p class="text-sm text-slate-600">Passed checks</p>
            </div>
            <div class="glass-panel rounded-3xl p-5 text-center">
                <p class="text-2xl font-bold text-amber-700">${warnings.length}</p>
                <p class="text-sm text-slate-600">Warnings</p>
            </div>
            <div class="glass-panel rounded-3xl p-5 text-center">
                <p class="text-2xl font-bold text-rose-700">${failed.length}</p>
                <p class="text-sm text-slate-600">Failed checks</p>
            </div>
        </div>

        <div class="glass-panel overflow-hidden rounded-[2rem] divide-y divide-slate-200/70">
            ${resultsHtml}
        </div>
    `;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function resetForm() {
    stopLoadingAnimation();
    errorSection.classList.add('hidden');
    reportSection.classList.add('hidden');
    reportSection.innerHTML = '';
    formSection.classList.remove('hidden');
    document.getElementById('url-input').value = '';
    document.getElementById('keyword-input').value = '';
    hideFormError();
    resetSubmitButton();
    loadingSection.classList.add('hidden');
}
