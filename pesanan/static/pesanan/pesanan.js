/*
 * Modul pesanan: tambah/hapus keranjang, checkout, tab & aksi status pesanan.
 * Dimuat langsung di halaman pesanan, atau sekali lewat slot tombol keranjang.
 */
(() => {
  if (window.__pesananLoaded) return;
  window.__pesananLoaded = true;

  // Slot bisa memuat <link> CSS di tengah halaman; pindahkan ke <head>.
  document.querySelectorAll('body link[rel="stylesheet"][href*="pesanan/pesanan"]').forEach((link) => {
    document.head.appendChild(link);
  });

  function setCartCount(count) {
    if (count === undefined) return;
    document.querySelectorAll("[data-cart-count]").forEach((badge) => {
      badge.textContent = count;
      badge.hidden = !count;
    });
  }

  /* ---------- Tambah ke keranjang (slot di detail produk / wishlist) ---------- */
  document.addEventListener("click", async (e) => {
    const button = e.target.closest("[data-cart-add]");
    if (!button) return;
    button.disabled = true;
    const result = await postJSON(button.dataset.url);
    setCartCount(result.cart_count);

    const alreadyInCart = !result.success && result.cart_count !== undefined;
    if (!result.success && !alreadyInCart) {
      button.disabled = false;
      showToast(result.message, "error");
      return;
    }
    showToast(result.message, result.success ? "success" : "info");
    const link = document.createElement("a");
    link.href = button.dataset.cartUrl;
    link.className = button.className.replace("btn-primary", "btn-outline");
    link.textContent = "Lihat keranjang";
    button.replaceWith(link);
  });

  /* ---------- Halaman keranjang: hapus item ---------- */
  function initCart() {
    const page = document.getElementById("cart-page");
    if (!page) return;

    page.addEventListener("click", async (e) => {
      const button = e.target.closest("[data-cart-remove]");
      if (!button) return;
      button.disabled = true;
      const result = await postJSON(button.dataset.url);
      if (!result.success) {
        button.disabled = false;
        showToast(result.message, "error");
        return;
      }

      const line = button.closest("[data-cart-line]");
      const group = line.closest("[data-cart-group]");
      line.remove();
      if (!group.querySelector("[data-cart-line]")) group.remove();

      ["item_count", "store_count", "subtotal_display"].forEach((key) => {
        page.querySelectorAll(`[data-summary="${key}"]`).forEach((el) => { el.textContent = result[key]; });
      });
      const hasItems = result.item_count > 0;
      document.getElementById("checkout-btn").hidden = !hasItems;
      document.getElementById("checkout-btn-disabled").hidden = hasItems;
      document.getElementById("cart-heading").hidden = !hasItems;

      const anyLine = page.querySelector("[data-cart-line]");
      document.getElementById("cart-layout").hidden = !anyLine;
      document.getElementById("cart-empty").hidden = Boolean(anyLine);

      setCartCount(result.cart_count);
      showToast(result.message, "success");
    });
  }

  /* ---------- Checkout: cegah klik ganda ---------- */
  function initCheckout() {
    const form = document.getElementById("checkout-form");
    if (!form) return;
    form.addEventListener("submit", () => {
      const pay = document.getElementById("pay-btn");
      pay.disabled = true;
      pay.textContent = "Memproses...";
    });
  }

  /* ---------- Daftar pesanan ---------- */
  const STEPS = ["Diproses", "Dikirim", "Selesai"];
  const ACTION_LABELS = { ship: "Tandai dikirim", complete: "Pesanan diterima", cancel: "Batalkan" };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function actionButtons(order, block) {
    const box = el("div", block ? "order-actions detail-actions-col" : "order-actions");
    ["ship", "complete", "cancel"].forEach((action) => {
      const url = order.actions[action];
      if (!url) return;
      let className;
      if (block) className = action === "cancel" ? "btn-danger btn-block" : "btn-primary btn-block";
      else className = action === "cancel" ? "link-btn underline danger" : "btn-primary btn-sm";
      const label = block && action === "cancel" ? "Batalkan pesanan" : ACTION_LABELS[action];
      const button = el("button", className, label);
      button.type = "button";
      button.dataset.orderAction = action;
      button.dataset.url = url;
      box.appendChild(button);
    });
    return box;
  }

  function statusBadge(order) {
    return el("span", `badge status-badge status-${order.status}`, order.status_display);
  }

  /* Struktur sama dengan pesanan/partials/order_row.html */
  function renderOrderRow(order, role) {
    const row = el("article", "order-row");
    row.dataset.orderRow = "";
    row.dataset.code = order.code;
    row.dataset.status = order.status;

    const thumb = el("a", "cart-thumb order-thumb");
    thumb.href = order.detail_url;
    thumb.tabIndex = -1;
    thumb.setAttribute("aria-hidden", "true");
    if (order.thumb_url) {
      const img = el("img");
      img.src = order.thumb_url;
      img.alt = "";
      thumb.appendChild(img);
    }

    const main = el("div", "order-main");
    const title = el("a", "order-title", order.title);
    title.href = order.detail_url;
    const who = role === "seller" ? order.buyer : order.store_name;
    main.append(title, el("p", "order-meta", `${order.code} · ${order.created_display} · ${who}`));

    const side = el("div", "order-side");
    if (role === "seller" && order.status !== "dibatalkan") {
      const stepper = el("ol", "stepper");
      stepper.setAttribute("aria-label", `Status: ${order.status_display}`);
      STEPS.forEach((label, i) => stepper.appendChild(el("li", order.step_index >= i ? "done" : "", label)));
      side.appendChild(stepper);
    } else {
      side.appendChild(statusBadge(order));
    }
    side.appendChild(actionButtons(order, false));

    row.append(thumb, main, el("span", "order-total", order.total_display), side);
    return row;
  }

  function updateCounts(counts) {
    if (!counts) return;
    Object.entries(counts).forEach(([key, value]) => {
      document.querySelectorAll(`#order-tabs [data-count="${key}"]`).forEach((node) => { node.textContent = value; });
    });
  }

  function refreshEmpty() {
    const list = document.getElementById("order-list");
    const empty = document.getElementById("orders-empty");
    if (list && empty) empty.hidden = list.children.length > 0;
  }

  function initOrderList() {
    const page = document.getElementById("orders-page");
    if (!page) return;
    const list = document.getElementById("order-list");
    const tabs = page.querySelectorAll("#order-tabs [data-status]");
    page.dataset.activeStatus = "";

    tabs.forEach((tab) => {
      tab.addEventListener("click", async () => {
        tabs.forEach((t) => {
          t.classList.toggle("active", t === tab);
          t.setAttribute("aria-selected", t === tab ? "true" : "false");
        });
        page.dataset.activeStatus = tab.dataset.status;
        const params = new URLSearchParams({ role: page.dataset.role, status: tab.dataset.status });
        list.classList.add("is-loading");
        const result = await getJSON(`${page.dataset.jsonUrl}?${params}`);
        list.classList.remove("is-loading");
        if (!result.success) {
          showToast(result.message, "error");
          return;
        }
        list.replaceChildren(...result.orders.map((order) => renderOrderRow(order, page.dataset.role)));
        updateCounts(result.counts);
        refreshEmpty();
      });
    });
  }

  /* ---------- Aksi status: kirim, selesai, batal ---------- */
  const TIMELINE_TEXT = {
    dikirim: "Dikirim",
    selesai: "Selesai (diterima pembeli)",
    dibatalkan: "Dibatalkan",
  };

  document.addEventListener("click", async (e) => {
    const button = e.target.closest("[data-order-action]");
    if (!button) return;
    const action = button.dataset.orderAction;

    if (action === "cancel") {
      const ok = await confirmDialog(
        "Pesanan akan dibatalkan dan barangnya kembali dijual. Lanjutkan?",
        { title: "Batalkan pesanan", confirmText: "Batalkan", cancelText: "Kembali", danger: true }
      );
      if (!ok) return;
    }

    button.disabled = true;
    const result = await postJSON(button.dataset.url);
    if (!result.success) {
      button.disabled = false;
      showToast(result.message, "error");
      return;
    }
    showToast(result.message, "success");
    const order = result.order;

    const row = button.closest("[data-order-row]");
    if (row) {
      const page = document.getElementById("orders-page");
      const filter = page.dataset.activeStatus;
      if (filter && filter !== order.status) row.remove();
      else row.replaceWith(renderOrderRow(order, page.dataset.role));
      updateCounts(result.counts);
      refreshEmpty();
      return;
    }

    // Halaman detail pesanan
    const badge = document.querySelector("[data-detail-status]");
    if (badge) {
      badge.className = `badge status-badge status-${order.status}`;
      badge.textContent = order.status_display;
    }
    const actions = document.getElementById("detail-actions");
    if (actions) {
      const fresh = actionButtons(order, true);
      fresh.id = "detail-actions";
      actions.replaceWith(fresh);
    }
    const timeline = document.querySelector(".timeline");
    if (timeline && TIMELINE_TEXT[order.status]) {
      const li = el("li", "done", `${TIMELINE_TEXT[order.status]} `);
      li.appendChild(el("span", "muted", "Baru saja"));
      timeline.appendChild(li);
    }
  });

  const init = () => { initCart(); initCheckout(); initOrderList(); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
