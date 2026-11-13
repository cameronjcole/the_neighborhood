// Attendee page: select events and export them.
(function () {
  const picks = Array.from(document.querySelectorAll(".pick"));
  if (!picks.length) return;

  const selectAll = document.getElementById("select-all");
  const bar = document.getElementById("selection-bar");
  const countEl = document.getElementById("selected-count");
  const addBtn = document.getElementById("add-selected");
  const menu = document.getElementById("add-menu");
  const googleSub = document.getElementById("google-sub");
  const hint = document.getElementById("google-hint");

  const selected = () => picks.filter((p) => p.checked);

  function setMenu(open) {
    menu.hidden = !open;
    addBtn.setAttribute("aria-expanded", String(open));
  }

  function refresh() {
    const n = selected().length;
    countEl.textContent = n;
    selectAll.checked = n === picks.length;
    selectAll.indeterminate = n > 0 && n < picks.length;
    picks.forEach((p) => p.closest(".event-card").classList.toggle("is-selected", p.checked));
    bar.classList.toggle("is-visible", n > 0);
    bar.setAttribute("aria-hidden", String(n === 0));
    document.body.classList.toggle("has-selection", n > 0);
    googleSub.textContent = n > 1 ? "Download a file to import" : "Opens Google with the event";
    if (n === 0) setMenu(false);
  }

  function downloadIcs(ids) {
    window.location.href = `${window.ICS_URL}?ids=${ids.join(",")}`;
  }

  selectAll.addEventListener("change", () => {
    picks.forEach((p) => (p.checked = selectAll.checked));
    refresh();
  });
  picks.forEach((p) => p.addEventListener("change", refresh));

  // Clicking anywhere on a card (except its links and buttons) toggles it.
  document.querySelectorAll(".event-card").forEach((card) => {
    card.addEventListener("click", (e) => {
      if (e.target.closest("a, button, label")) return;
      const pick = card.querySelector(".pick");
      pick.checked = !pick.checked;
      refresh();
    });
  });

  document.getElementById("clear-selection").addEventListener("click", () => {
    picks.forEach((p) => (p.checked = false));
    refresh();
  });

  addBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    setMenu(menu.hidden);
  });
  document.addEventListener("click", (e) => { if (!menu.contains(e.target)) setMenu(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setMenu(false); });

  menu.addEventListener("click", (e) => {
    const item = e.target.closest("[data-target]");
    if (!item) return;
    const chosen = selected();
    hint.hidden = true;
    if (item.dataset.target === "ics") {
      downloadIcs(chosen.map((p) => p.value));
      showToast(`Downloading ${chosen.length} event${chosen.length === 1 ? "" : "s"}`);
    } else if (chosen.length === 1) {
      // Google only supports adding one event per link.
      window.open(chosen[0].closest(".event-card").dataset.google, "_blank", "noopener");
    } else {
      downloadIcs(chosen.map((p) => p.value));
      hint.hidden = false;
      hint.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    setMenu(false);
  });

  refresh();
})();
