// Resident page: select events and export them.
(function () {
  const picks = Array.from(document.querySelectorAll(".pick"));
  const selectAll = document.getElementById("select-all");
  const countEl = document.getElementById("selected-count");
  const addBtn = document.getElementById("add-selected");
  const menu = document.getElementById("add-menu");
  const hint = document.getElementById("google-hint");

  if (picks.length) {
    function selected() {
      return picks.filter((p) => p.checked);
    }

    function refresh() {
      const n = selected().length;
      countEl.textContent = `${n} selected`;
      addBtn.disabled = n === 0;
      selectAll.checked = n === picks.length;
      selectAll.indeterminate = n > 0 && n < picks.length;
      picks.forEach((p) => p.closest(".event").classList.toggle("selected", p.checked));
      if (n === 0) menu.hidden = true;
    }

    function downloadIcs(ids) {
      window.location.href = `${window.ICS_URL}?ids=${ids.join(",")}`;
    }

    selectAll.addEventListener("change", () => {
      picks.forEach((p) => (p.checked = selectAll.checked));
      refresh();
    });
    picks.forEach((p) => p.addEventListener("change", refresh));

    addBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      menu.hidden = !menu.hidden;
    });
    document.addEventListener("click", () => (menu.hidden = true));

    menu.addEventListener("click", (e) => {
      const target = e.target.dataset.target;
      if (!target) return;
      const chosen = selected();
      const ids = chosen.map((p) => p.value);
      hint.hidden = true;
      if (target === "ics") {
        downloadIcs(ids);
      } else if (chosen.length === 1) {
        // Google only supports adding one event per link.
        window.open(chosen[0].closest(".event").dataset.google, "_blank", "noopener");
      } else {
        downloadIcs(ids);
        hint.hidden = false;
      }
      menu.hidden = true;
    });

    refresh();
  }

  const copyFeed = document.getElementById("copy-feed");
  copyFeed.addEventListener("click", () => {
    navigator.clipboard.writeText(copyFeed.dataset.url).then(() => {
      copyFeed.textContent = "Copied!";
      setTimeout(() => (copyFeed.textContent = "Copy feed URL for Google"), 1500);
    });
  });
})();
