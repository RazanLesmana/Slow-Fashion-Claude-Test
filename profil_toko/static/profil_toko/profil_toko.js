/* Modul profil toko: tab produk, edit/tutup toko, hapus size chart (AJAX). */
document.addEventListener("DOMContentLoaded", () => {
  initCounters();
  initStoreTabs();
  initStoreEdit();
  initStoreClose();
  initSizeChartDelete();
});

function initCounters() {
  document.querySelectorAll("[data-counter-for]").forEach((counter) => {
    const input = document.getElementById(counter.dataset.counterFor);
    if (!input) return;
    const update = () => { counter.textContent = input.value.length; };
    input.addEventListener("input", update);
    update();
  });
}

/* ---------- Tab Semua / Tersedia / Terjual tanpa reload ---------- */
function initStoreTabs() {
  const page = document.getElementById("store-page");
  const tabs = document.querySelectorAll("#store-tabs [data-tab]");
  const grid = document.getElementById("store-products");
  if (!page || !grid || !tabs.length) return;

  const emptyText = {
    semua: "Toko ini belum punya listing.",
    tersedia: "Belum ada produk yang tersedia.",
    terjual: "Belum ada produk yang terjual.",
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", async () => {
      const status = tab.dataset.tab;
      tabs.forEach((t) => {
        const active = t === tab;
        t.classList.toggle("active", active);
        t.setAttribute("aria-selected", active ? "true" : "false");
      });

      grid.classList.add("is-loading");
      const result = await getJSON(`${page.dataset.productsUrl}?status=${encodeURIComponent(status)}`);
      grid.classList.remove("is-loading");
      if (!result.success) {
        showToast(result.message, "error");
        return;
      }

      Object.entries(result.counts || {}).forEach(([key, value]) => {
        const el = document.querySelector(`[data-count="${key}"]`);
        if (el) el.textContent = value;
      });

      grid.replaceChildren();
      if (!result.products.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        const title = document.createElement("h3");
        title.textContent = "Belum ada produk";
        const text = document.createElement("p");
        text.textContent = emptyText[status];
        empty.append(title, text);
        grid.appendChild(empty);
        return;
      }
      result.products.forEach((product) => grid.appendChild(renderProductCard(product)));
    });
  });
}

/* ---------- Edit profil toko (AJAX) ---------- */
function initStoreEdit() {
  const form = document.getElementById("store-edit-form");
  const openBtn = document.getElementById("store-edit-btn");
  if (!form || !openBtn) return;
  const cancelBtn = document.getElementById("store-edit-cancel");

  const setOpen = (open) => {
    form.hidden = !open;
    openBtn.hidden = open;
    if (open) form.querySelector("input").focus();
  };
  openBtn.addEventListener("click", () => setOpen(true));
  cancelBtn.addEventListener("click", () => setOpen(false));

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    form.querySelectorAll("[data-errors-for]").forEach((box) => box.replaceChildren());
    form.querySelectorAll(".field.has-error").forEach((field) => field.classList.remove("has-error"));

    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    const result = await postJSON(form.action, new FormData(form));
    submit.disabled = false;

    if (!result.success) {
      Object.entries(result.errors || {}).forEach(([name, errors]) => {
        const box = form.querySelector(`[data-errors-for="${name}"]`);
        if (!box) return;
        box.closest(".field").classList.add("has-error");
        errors.forEach((err) => {
          const p = document.createElement("p");
          p.className = "field-error";
          p.textContent = err.message;
          box.appendChild(p);
        });
      });
      showToast(result.message, "error");
      return;
    }

    const store = result.store;
    const set = (key, value) => {
      const el = document.querySelector(`[data-store="${key}"]`);
      if (el) el.textContent = value;
    };
    set("name", store.name);
    set("city", store.city);
    set("initial", store.initial);
    const desc = document.querySelector('[data-store="description"]');
    desc.textContent = store.description;
    desc.hidden = !store.description;
    const wa = document.querySelector('[data-store="whatsapp"]');
    if (wa && store.whatsapp_url) wa.href = store.whatsapp_url;
    form.querySelector('[name="whatsapp_number"]').value = store.whatsapp_number;
    document.title = `${store.name} · LaPAKAIAN`;

    setOpen(false);
    showToast(result.message, "success");
  });
}

/* ---------- Tutup toko (AJAX + konfirmasi) ---------- */
function initStoreClose() {
  const button = document.getElementById("store-close-btn");
  if (!button) return;
  button.addEventListener("click", async () => {
    const ok = await confirmDialog(
      "Toko akan dihapus dan mode seller dinonaktifkan. Listing-mu tidak akan tampil di katalog.",
      { title: "Tutup toko", confirmText: "Tutup toko", danger: true }
    );
    if (!ok) return;
    button.disabled = true;
    const result = await postJSON(button.dataset.url);
    if (!result.success) {
      button.disabled = false;
      showToast(result.message, "error");
      return;
    }
    showToast(result.message, "success");
    document.querySelectorAll("[data-seller-nav]").forEach((el) => { el.hidden = true; });
    setTimeout(() => { window.location.href = result.redirect_url; }, 800);
  });
}

/* ---------- Hapus size chart (AJAX + konfirmasi) ---------- */
function initSizeChartDelete() {
  document.querySelectorAll("[data-chart-delete]").forEach((button) => {
    button.addEventListener("click", async () => {
      const ok = await confirmDialog(`Hapus size chart ${button.dataset.label}?`, {
        title: "Hapus size chart", confirmText: "Hapus", danger: true,
      });
      if (!ok) return;
      button.disabled = true;
      const result = await postJSON(button.dataset.url);
      if (!result.success) {
        button.disabled = false;
        showToast(result.message, "error");
        return;
      }
      showToast(result.message, "success");

      const row = button.closest("[data-chart-row]");
      const group = row.closest("[data-group]");
      row.remove();
      if (!group.querySelector("[data-chart-row]")) group.remove();
      const empty = document.getElementById("size-chart-empty");
      if (empty && !document.querySelector("[data-group]")) empty.hidden = false;
    });
  });
}
