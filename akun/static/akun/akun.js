/* Modul akun: edit bio, toggle seller, hapus akun (AJAX, tanpa reload). */
document.addEventListener("DOMContentLoaded", () => {
  initBioEditor();
  initSellerToggle();
  initDeleteAccount();
});

function initBioEditor() {
  const form = document.getElementById("bio-form");
  if (!form) return;
  const text = document.getElementById("bio-text");
  const editBtn = document.getElementById("bio-edit-btn");
  const cancelBtn = document.getElementById("bio-cancel-btn");
  const textarea = form.querySelector("textarea");
  const counter = document.getElementById("bio-count");
  const error = document.getElementById("bio-error");

  const setEditing = (editing) => {
    form.hidden = !editing;
    text.hidden = editing;
    editBtn.hidden = editing;
    error.hidden = true;
    if (editing) textarea.focus();
  };

  editBtn.addEventListener("click", () => setEditing(true));
  cancelBtn.addEventListener("click", () => {
    textarea.value = text.classList.contains("muted") ? "" : text.textContent;
    counter.textContent = textarea.value.length;
    setEditing(false);
  });
  textarea.addEventListener("input", () => {
    counter.textContent = textarea.value.length;
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    const result = await postJSON(form.action, new FormData(form));
    submit.disabled = false;

    if (result.success) {
      const bio = result.bio || "";
      text.textContent = bio || text.dataset.emptyText;
      text.classList.toggle("muted", !bio);
      setEditing(false);
      showToast(result.message, "success");
    } else {
      const bioErrors = result.errors && result.errors.bio;
      error.textContent = bioErrors ? bioErrors.map((err) => err.message).join(" ") : result.message;
      error.hidden = false;
      showToast(result.message, "error");
    }
  });
}

function initSellerToggle() {
  const button = document.getElementById("toggleSeller");
  if (!button) return;
  const status = document.getElementById("seller-status");
  const desc = document.getElementById("seller-desc");

  button.addEventListener("click", async () => {
    button.disabled = true;
    const result = await postJSON(button.dataset.url);
    button.disabled = false;

    if (!result.success) {
      showToast(result.message, "error");
      return;
    }

    showToast(result.message, "success");
    if (result.redirect_url) {
      // Seller baru tanpa toko diarahkan ke halaman Buka Toko.
      setTimeout(() => { window.location.href = result.redirect_url; }, 700);
    }

    status.textContent = result.status_display;
    status.classList.toggle("badge-active", result.is_seller);
    desc.textContent = result.is_seller ? desc.dataset.sellerText : desc.dataset.buyerText;
    button.textContent = result.is_seller ? "Nonaktifkan Seller" : "Jadi Seller";
    button.classList.toggle("btn-primary", !result.is_seller);
    button.classList.toggle("btn-outline", result.is_seller);
    // Menu seller di navbar dan di kartu ini ikut tampil/tersembunyi.
    document.querySelectorAll("[data-seller-nav]").forEach((el) => {
      el.hidden = !result.is_seller;
    });
  });
}

function initDeleteAccount() {
  const button = document.getElementById("delete-account-btn");
  if (!button) return;

  button.addEventListener("click", async () => {
    const ok = await confirmDialog(
      "Akun dan semua data milikmu akan dihapus permanen. Lanjutkan?",
      { title: "Hapus akun", confirmText: "Hapus akun", danger: true }
    );
    if (!ok) return;

    button.disabled = true;
    const result = await postJSON(button.dataset.url);
    if (result.success) {
      showToast(result.message, "success");
      setTimeout(() => { window.location.href = result.redirect_url; }, 700);
    } else {
      button.disabled = false;
      showToast(result.message, "error");
    }
  });
}
