function pollStatus() {
    fetch(window.AUDIT_STATUS_URL)
        .then((res) => res.json())
        .then((data) => {
            document.getElementById("status-text").textContent = `Status: ${data.status}...`;

            if (data.status === "completed") {
                window.location.href = data.redirect_url;
            } else if (data.status === "failed") {
                document.getElementById("status-text").textContent = `Audit failed: ${data.error_message}`;
            } else {
                setTimeout(pollStatus, 2000);
            }
        })
        .catch(() => {
            setTimeout(pollStatus, 2000);
        });
}

pollStatus();
