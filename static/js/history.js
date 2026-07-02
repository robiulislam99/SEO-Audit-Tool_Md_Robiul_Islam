const modal = document.getElementById("confirm-modal");
const modalTitle = document.getElementById("confirm-modal-title");
const modalMessage = document.getElementById("confirm-modal-message");
const modalCancel = document.getElementById("confirm-modal-cancel");
const modalSubmit = document.getElementById("confirm-modal-submit");
let pendingForm = null;

function closeModal() {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
    pendingForm = null;
}

document.querySelectorAll(".js-danger-form").forEach((form) => {
    form.addEventListener("submit", (event) => {
        event.preventDefault();
        pendingForm = form;

        const trigger = event.submitter || form.querySelector("button[type='submit']");
        modalTitle.textContent = trigger.dataset.confirmTitle || "Confirm action";
        modalMessage.textContent = trigger.dataset.confirmMessage || "This action cannot be undone.";
        modalSubmit.textContent = trigger.dataset.confirmAction || "Confirm";

        modal.classList.remove("hidden");
        modal.classList.add("flex");
    });
});

modalCancel.addEventListener("click", closeModal);
modal.addEventListener("click", (event) => {
    if (event.target === modal) {
        closeModal();
    }
});
modalSubmit.addEventListener("click", () => {
    if (pendingForm) {
        pendingForm.submit();
    }
});
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) {
        closeModal();
    }
});
