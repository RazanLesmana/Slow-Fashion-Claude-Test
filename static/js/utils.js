/*
 * JS bersama LaPAKAIAN (vanilla, tanpa framework).
 * Di-load di base.html sebelum {% block extra_js %}, jadi semua fungsi
 * di sini bisa dipakai langsung oleh JS tiap modul.
 */

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return decodeURIComponent(parts.pop().split(";").shift());
  return null;
}

/*
 * POST ke endpoint AJAX dengan header X-CSRFToken lalu parse JSON.
 * `data` boleh FormData, objek biasa (dikirim sebagai form-urlencoded supaya
 * terbaca di request.POST), atau kosong. Selalu mengembalikan objek berisi
 * minimal { success, message } dan `status` HTTP, tidak pernah throw.
 */
async function postJSON(url, data) {
  let body;
  if (data instanceof FormData) {
    body = data;
  } else if (data) {
    body = new URLSearchParams();
    Object.entries(data).forEach(([key, val]) => {
      if (Array.isArray(val)) val.forEach((v) => body.append(key, v));
      else if (val !== undefined && val !== null) body.append(key, val);
    });
  }

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCookie("csrftoken") || "",
        "X-Requested-With": "XMLHttpRequest",
        Accept: "application/json",
      },
      credentials: "same-origin",
      body,
    });
    return await parseJSONResponse(res);
  } catch (err) {
    return { success: false, status: 0, message: "Gagal terhubung ke server." };
  }
}

async function getJSON(url) {
  try {
    const res = await fetch(url, {
      headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    });
    return await parseJSONResponse(res);
  } catch (err) {
    return { success: false, status: 0, message: "Gagal terhubung ke server." };
  }
}

async function parseJSONResponse(res) {
  const type = res.headers.get("Content-Type") || "";
  if (type.includes("application/json")) {
    const json = await res.json();
    if (json && typeof json === "object" && !Array.isArray(json)) {
      if (json.success === undefined) json.success = res.ok;
      json.status = res.status;
      return json;
    }
    return { success: res.ok, status: res.status, data: json };
  }
  let message = "Terjadi kesalahan. Coba lagi.";
  if (res.status === 403) message = "Kamu tidak punya akses untuk aksi ini.";
  else if (res.status === 404) message = "Data tidak ditemukan.";
  else if (res.redirected || res.status === 401) message = "Silakan masuk terlebih dahulu.";
  return { success: false, status: res.status, message };
}

function showToast(message, type = "success") {
  if (!message) return;
  let container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.setAttribute("role", type === "error" ? "alert" : "status");
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add("toast-hide");
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

function formatRupiah(value) {
  const amount = Math.round(Number(value) || 0);
  const sign = amount < 0 ? "-" : "";
  return `${sign}Rp${Math.abs(amount).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".")}`;
}

/*
 * Dialog konfirmasi (modal vanilla). Mengembalikan Promise<boolean>.
 */
function confirmDialog(message, { title = "Konfirmasi", confirmText = "Ya", cancelText = "Batal", danger = false } = {}) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true">
        <h2 class="modal-title"></h2>
        <p class="modal-message"></p>
        <div class="btn-row">
          <button type="button" class="${danger ? "btn-danger" : "btn-primary"}" data-modal-confirm></button>
          <button type="button" class="btn-outline" data-modal-cancel></button>
        </div>
      </div>`;
    overlay.querySelector(".modal-title").textContent = title;
    overlay.querySelector(".modal-message").textContent = message;
    overlay.querySelector("[data-modal-confirm]").textContent = confirmText;
    overlay.querySelector("[data-modal-cancel]").textContent = cancelText;

    const close = (result) => {
      document.removeEventListener("keydown", onKey);
      overlay.remove();
      resolve(result);
    };
    const onKey = (e) => { if (e.key === "Escape") close(false); };

    overlay.addEventListener("click", (e) => { if (e.target === overlay) close(false); });
    overlay.querySelector("[data-modal-confirm]").addEventListener("click", () => close(true));
    overlay.querySelector("[data-modal-cancel]").addEventListener("click", () => close(false));
    document.addEventListener("keydown", onKey);
    document.body.appendChild(overlay);
    overlay.querySelector("[data-modal-confirm]").focus();
  });
}

/*
 * Bangun kartu produk dari data JSON (lihat listing/utils.py product_card_data).
 * Strukturnya sama dengan templates/partials/product_card.html.
 * Setelah kartu dibuat, event "lapakaian:card-rendered" dikirim supaya modul
 * lain (mis. wishlist) bisa menambahkan elemennya sendiri ke kartu.
 */
function renderProductCard(p) {
  const card = document.createElement("article");
  card.className = "product-card" + (p.status === "sold" ? " is-sold" : "");
  card.dataset.productId = p.id;

  const media = document.createElement("div");
  media.className = "product-media";

  const imgLink = document.createElement("a");
  imgLink.href = p.detail_url;
  imgLink.className = "product-image";
  imgLink.setAttribute("aria-label", p.name);
  if (p.image_url) {
    const img = document.createElement("img");
    img.src = p.image_url;
    img.alt = p.name;
    img.loading = "lazy";
    imgLink.appendChild(img);
  }
  media.appendChild(imgLink);

  if (p.status === "sold") {
    const flag = document.createElement("span");
    flag.className = "badge badge-sold product-flag";
    flag.textContent = "Sold";
    media.appendChild(flag);
  }

  const info = document.createElement("div");
  info.className = "product-info";

  const name = document.createElement("a");
  name.href = p.detail_url;
  name.className = "product-name";
  name.textContent = p.name;

  const price = document.createElement("div");
  price.className = "price";
  price.textContent = p.price_display || formatRupiah(p.price);

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = [p.brand, p.size, p.condition_display].filter(Boolean).join(" · ");

  info.append(name, price, meta);
  card.append(media, info);

  document.dispatchEvent(new CustomEvent("lapakaian:card-rendered", { detail: { card, product: p } }));
  return card;
}

/* Navbar: hamburger mobile dan dropdown kategori. */
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".nav-toggle");
  const links = document.getElementById("nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => {
      const open = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  document.querySelectorAll(".nav-dropdown").forEach((dropdown) => {
    const button = dropdown.querySelector(".nav-dropdown-toggle");
    button.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = dropdown.classList.toggle("open");
      button.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });
  document.addEventListener("click", () => {
    document.querySelectorAll(".nav-dropdown.open").forEach((d) => {
      d.classList.remove("open");
      d.querySelector(".nav-dropdown-toggle").setAttribute("aria-expanded", "false");
    });
  });

  // Pesan Django (messages) ikut hilang sendiri setelah beberapa detik.
  document.querySelectorAll(".messages .message").forEach((msg) => {
    setTimeout(() => msg.remove(), 5000);
  });
});
