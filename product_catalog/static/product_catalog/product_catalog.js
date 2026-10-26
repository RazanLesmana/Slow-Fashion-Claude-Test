/*
 * Modul katalog & wishlist. Dimuat sekali per halaman lewat template tag
 * {% wishlist_js %} (dari slot tombol wishlist atau halaman katalog/wishlist).
 */
(() => {
  const dataEl = document.getElementById("wishlist-data");
  const data = dataEl ? JSON.parse(dataEl.textContent) : { ids: [], toggle_url: "" };
  const wishlistIds = new Set(data.ids);
  const heartSVG = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M12 20.5s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.7c0 5.6-7.5 10.2-7.5 10.2z"/></svg>';

  const isAuthenticated = () => document.body.dataset.authenticated === "true";

  function setButtonState(button, active) {
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
    button.setAttribute("aria-label", active ? "Hapus dari wishlist" : "Simpan ke wishlist");
  }

  /* Kartu yang dibangun JS (renderProductCard, mis. tab toko) ikut diberi tombol hati. */
  document.addEventListener("lapakaian:card-rendered", (e) => {
    const { card, product } = e.detail;
    const media = card.querySelector(".product-media");
    if (!media || media.querySelector(".wish-btn")) return;

    let button;
    if (isAuthenticated()) {
      button = document.createElement("button");
      button.type = "button";
      button.dataset.wishlistToggle = "";
      button.dataset.productId = product.id;
      button.dataset.url = data.toggle_url.replace(/\/0\/$/, `/${product.id}/`);
      setButtonState(button, wishlistIds.has(product.id));
    } else {
      button = document.createElement("a");
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      button.href = `${document.body.dataset.loginUrl}?next=${next}`;
      button.setAttribute("aria-label", "Masuk untuk menyimpan ke wishlist");
    }
    button.className = "wish-btn" + (button.classList.contains("is-active") ? " is-active" : "");
    button.innerHTML = `${heartSVG}<span class="wish-label">Wishlist</span>`;
    media.appendChild(button);
  });

  /* Toggle wishlist (event delegation, jadi juga berlaku untuk kartu baru). */
  document.addEventListener("click", async (e) => {
    const button = e.target.closest("[data-wishlist-toggle]");
    if (!button) return;
    e.preventDefault();
    button.disabled = true;
    const result = await postJSON(button.dataset.url);
    button.disabled = false;
    if (!result.success) {
      showToast(result.message, "error");
      return;
    }

    const id = Number(button.dataset.productId);
    if (result.in_wishlist) wishlistIds.add(id); else wishlistIds.delete(id);
    document.querySelectorAll(`[data-wishlist-toggle][data-product-id="${id}"]`).forEach((btn) => {
      setButtonState(btn, result.in_wishlist);
    });
    showToast(result.message, "success");

    // Di halaman Wishlist, barang yang di-unwishlist langsung hilang.
    if (!result.in_wishlist) {
      const item = document.querySelector(`[data-wishlist-item][data-product-id="${id}"]`);
      if (item) removeWishlistItem(item, result.count);
    }
  });

  function removeWishlistItem(item, count) {
    item.remove();
    const counter = document.getElementById("wishlist-count");
    if (counter && count !== undefined) counter.textContent = count;
    const grid = document.getElementById("wishlist-grid");
    if (grid && !grid.querySelector("[data-wishlist-item]")) {
      const template = document.getElementById("wishlist-empty-template");
      grid.replaceChildren(template.content.cloneNode(true));
    }
  }

  function initWishlistPage() {
    document.querySelectorAll("[data-wishlist-item]").forEach((item) => {
      const text = item.querySelector("[data-note-text]");
      const form = item.querySelector("[data-note-form]");
      const editBtn = item.querySelector("[data-note-edit]");
      const input = form.querySelector('[name="note"]');

      const setEditing = (editing) => {
        form.hidden = !editing;
        text.hidden = editing;
        editBtn.hidden = editing;
        if (editing) input.focus();
      };
      editBtn.addEventListener("click", () => setEditing(true));
      item.querySelector("[data-note-cancel]").addEventListener("click", () => {
        input.value = text.classList.contains("muted") ? "" : text.textContent;
        setEditing(false);
      });

      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const result = await postJSON(form.action, new FormData(form));
        if (!result.success) {
          const errors = result.errors && result.errors.note;
          showToast(errors ? errors.map((err) => err.message).join(" ") : result.message, "error");
          return;
        }
        text.textContent = result.note || text.dataset.emptyText;
        text.classList.toggle("muted", !result.note);
        setEditing(false);
        showToast(result.message, "success");
      });

      item.querySelector("[data-remove]").addEventListener("click", async (e) => {
        const button = e.currentTarget;
        button.disabled = true;
        const result = await postJSON(button.dataset.url);
        if (!result.success) {
          button.disabled = false;
          showToast(result.message, "error");
          return;
        }
        wishlistIds.delete(Number(item.dataset.productId));
        removeWishlistItem(item, result.count);
        showToast(result.message, "success");
      });
    });
  }

  /* Katalog: filter langsung diterapkan, panel filter di mobile. */
  function initKatalog() {
    const form = document.getElementById("katalog-filter");
    if (!form) return;
    form.querySelectorAll("[data-autosubmit]").forEach((input) => {
      input.addEventListener("change", () => form.requestSubmit());
    });
    // Jangan kirim parameter kosong supaya URL tetap rapi.
    form.addEventListener("submit", () => {
      form.querySelectorAll("input, select").forEach((input) => {
        if ((input.type === "radio" || input.type === "checkbox") ? false : !input.value) input.disabled = true;
      });
      form.querySelectorAll('input[name="category"][value=""]').forEach((input) => {
        if (input.checked) input.disabled = true;
      });
    });

    const toggle = document.getElementById("katalog-filter-toggle");
    const sidebar = document.getElementById("katalog-sidebar");
    if (toggle && sidebar) {
      toggle.addEventListener("click", () => {
        const open = sidebar.classList.toggle("open");
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }
  }

  const init = () => { initWishlistPage(); initKatalog(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
