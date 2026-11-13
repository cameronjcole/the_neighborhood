// Shared UI behavior: toasts, copy buttons, and confirm dialogs.
(function () {
  const toasts = document.querySelector(".toasts");

  function dismiss(toast) {
    toast.classList.add("is-leaving");
    toast.addEventListener("animationend", () => toast.remove(), { once: true });
  }

  function arm(toast) {
    toast.querySelector(".toast-close")?.addEventListener("click", () => dismiss(toast));
    // Errors stay until dismissed; everything else fades on its own.
    if (!toast.classList.contains("toast-error")) setTimeout(() => dismiss(toast), 4500);
  }

  window.showToast = function (message, category = "success") {
    const toast = document.createElement("div");
    toast.className = `toast toast-${category}`;
    toast.setAttribute("role", "status");
    const icon = category === "success" ? '<path d="M20 6 9 17l-5-5"/>' : '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>';
    toast.innerHTML =
      `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${icon}</svg>` +
      `<span></span><button type="button" class="toast-close" aria-label="Dismiss">` +
      `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>`;
    toast.querySelector("span").textContent = message;
    toasts.appendChild(toast);
    arm(toast);
  };

  document.querySelectorAll(".toast").forEach(arm);

  // Copy: data-copy="text" or data-copy-target="#input".
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-copy], [data-copy-target]");
    if (!btn) return;
    const target = btn.dataset.copyTarget && document.querySelector(btn.dataset.copyTarget);
    const text = target ? target.value : btn.dataset.copy;
    navigator.clipboard.writeText(text).then(
      () => showToast(btn.dataset.copyMessage || "Link copied to clipboard"),
      () => { target?.select(); showToast("Couldn't copy automatically. The link is selected.", "error"); }
    );
  });

  // Confirm: <form data-confirm="body" data-confirm-title="..." data-confirm-action="Delete">.
  const dialog = document.getElementById("confirm-dialog");
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (!form.dataset.confirm || form.dataset.confirmed) return;
    e.preventDefault();
    dialog.querySelector("#confirm-title").textContent = form.dataset.confirmTitle || "Are you sure?";
    dialog.querySelector("#confirm-body").textContent = form.dataset.confirm;
    dialog.querySelector("#confirm-ok").textContent = form.dataset.confirmAction || "Confirm";
    dialog.returnValue = "";
    dialog.showModal();
    dialog.addEventListener("close", () => {
      if (dialog.returnValue === "ok") {
        form.dataset.confirmed = "1";
        form.submit();
      }
    }, { once: true });
  });
  // Clicking the backdrop closes the dialog.
  dialog.addEventListener("click", (e) => { if (e.target === dialog) dialog.close("cancel"); });
})();
