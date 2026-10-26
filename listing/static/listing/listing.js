/* Modul listing: preview foto, galeri, aksi status/hapus via AJAX. */
document.addEventListener("DOMContentLoaded", () => {
  initPhotoSlots();
  initGallery();
  initCategoryFilter();
  initStatusButtons();
  initDeleteButtons();
});

/* ---------- Form: preview foto sebelum upload ---------- */
function initPhotoSlots() {
  const slots = Array.from(document.querySelectorAll("[data-photo-slot]"));
  if (!slots.length) return;
  const drop = document.getElementById("photo-drop");
  const pick = document.getElementById("photo-pick");

  const showPreview = (slot, file) => {
    const img = slot.querySelector(".photo-preview");
    const empty = slot.querySelector(".photo-slot-empty");
    const clear = slot.querySelector(".photo-clear");
    if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
    if (file) {
      const url = URL.createObjectURL(file);
      img.dataset.objectUrl = url;
      img.src = url;
      img.hidden = false;
      if (empty) empty.hidden = true;
      if (clear) clear.hidden = false;
      slot.classList.add("filled");
    } else if (!img.dataset.initialSrc) {
      img.removeAttribute("src");
      img.hidden = true;
      if (empty) empty.hidden = false;
      if (clear) clear.hidden = true;
      slot.classList.remove("filled");
    } else {
      img.src = img.dataset.initialSrc;
    }
  };

  const isValidImage = (file) => {
    if (!file.type.startsWith("image/")) {
      showToast(`${file.name} bukan file gambar.`, "error");
      return false;
    }
    if (file.size > 5 * 1024 * 1024) {
      showToast(`${file.name} lebih dari 5 MB.`, "error");
      return false;
    }
    return true;
  };

  slots.forEach((slot) => {
    const input = slot.querySelector(".photo-input");
    const img = slot.querySelector(".photo-preview");
    if (img.getAttribute("src")) img.dataset.initialSrc = img.getAttribute("src");

    input.addEventListener("change", () => {
      const file = input.files[0];
      if (file && !isValidImage(file)) {
        input.value = "";
        showPreview(slot, null);
        return;
      }
      showPreview(slot, file || null);
    });

    const clear = slot.querySelector(".photo-clear");
    if (clear) {
      clear.addEventListener("click", () => {
        input.value = "";
        showPreview(slot, null);
      });
    }
  });

  const emptySlots = () => slots.filter((slot) => !slot.classList.contains("filled"));

  if (pick) {
    pick.addEventListener("click", () => {
      const slot = emptySlots()[0];
      if (slot) slot.querySelector(".photo-input").click();
      else showToast("Maksimal 5 foto per produk.", "error");
    });
  }

  if (drop) {
    ["dragenter", "dragover"].forEach((type) => drop.addEventListener(type, (e) => {
      e.preventDefault();
      drop.classList.add("dragover");
    }));
    ["dragleave", "drop"].forEach((type) => drop.addEventListener(type, (e) => {
      e.preventDefault();
      drop.classList.remove("dragover");
    }));
    drop.addEventListener("drop", (e) => {
      const files = Array.from(e.dataTransfer.files).filter(isValidImage);
      const targets = emptySlots();
      if (files.length > targets.length) showToast("Maksimal 5 foto per produk.", "error");
      files.slice(0, targets.length).forEach((file, i) => {
        const input = targets[i].querySelector(".photo-input");
        const transfer = new DataTransfer();
        transfer.items.add(file);
        input.files = transfer.files;
        showPreview(targets[i], file);
      });
    });
  }
}

/* ---------- Detail: klik thumbnail ganti gambar utama ---------- */
function initGallery() {
  const main = document.getElementById("gallery-main-img");
  const thumbs = document.querySelectorAll(".gallery-thumb");
  if (!main || !thumbs.length) return;
  thumbs.forEach((thumb) => {
    thumb.addEventListener("click", () => {
      main.src = thumb.dataset.src;
      main.alt = thumb.dataset.alt;
      thumbs.forEach((t) => t.classList.toggle("active", t === thumb));
    });
  });
}

/* ---------- My Listings: filter kategori langsung terapkan ---------- */
function initCategoryFilter() {
  const form = document.getElementById("category-filter");
  if (!form) return;
  form.querySelector("select").addEventListener("change", () => form.submit());
}

function updateCounts(counts) {
  if (!counts) return;
  Object.entries(counts).forEach(([key, value]) => {
    document.querySelectorAll(`[data-count="${key}"]`).forEach((el) => {
      el.textContent = value;
    });
  });
}

function refreshEmptyState() {
  const table = document.getElementById("listing-table");
  if (!table) return;
  const hasRows = table.querySelector("[data-product-row]") !== null;
  document.getElementById("listing-empty").hidden = hasRows;
  table.querySelector(".listing-row-head").hidden = !hasRows;
}

/* ---------- Tandai Sold / Tandai Aktif ---------- */
function initStatusButtons() {
  const page = document.getElementById("my-listings");
  const filterStatus = page ? page.dataset.selectedStatus : "";

  document.querySelectorAll("[data-status-toggle]").forEach((button) => {
    button.addEventListener("click", async () => {
      const toSold = button.dataset.status === "active";
      const url = toSold ? button.dataset.soldUrl : button.dataset.activeUrl;
      button.disabled = true;
      const result = await postJSON(url);
      button.disabled = false;

      if (!result.success) {
        showToast(result.message, "error");
        return;
      }
      showToast(result.message, "success");
      updateCounts(result.counts);

      const row = button.closest("[data-product-row]");
      const scope = row || document;
      button.dataset.status = result.status;
      button.textContent = result.status === "active" ? "Tandai Sold" : "Tandai Aktif";

      scope.querySelectorAll("[data-status-badge]").forEach((badge) => {
        if (row) {
          badge.textContent = result.status_display;
          badge.classList.toggle("badge-active", result.status === "active");
          badge.classList.toggle("badge-sold", result.status === "sold");
        } else {
          badge.hidden = result.status !== "sold";
        }
      });
      const gallery = document.querySelector(".gallery-main");
      if (!row && gallery) gallery.classList.toggle("is-sold", result.status === "sold");

      if (row) {
        row.dataset.status = result.status;
        // Kalau daftar sedang difilter per status, baris yang tidak cocok lagi dihilangkan.
        if (filterStatus && filterStatus !== result.status) {
          row.remove();
          refreshEmptyState();
        }
      }
    });
  });
}

/* ---------- Hapus produk ---------- */
function initDeleteButtons() {
  document.querySelectorAll("[data-delete]").forEach((button) => {
    button.addEventListener("click", async () => {
      const ok = await confirmDialog(
        `"${button.dataset.name}" akan dihapus permanen beserta fotonya.`,
        { title: "Hapus produk", confirmText: "Hapus", danger: true }
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

      const row = button.closest("[data-product-row]");
      if (row) {
        row.remove();
        updateCounts(result.counts);
        refreshEmptyState();
      } else {
        // Di halaman detail: produk sudah tidak ada, kembali ke My Listings.
        setTimeout(() => { window.location.href = result.redirect_url; }, 700);
      }
    });
  });
}
