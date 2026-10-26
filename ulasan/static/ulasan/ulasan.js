/* Modul ulasan: kirim, sort, edit inline, dan hapus ulasan tanpa reload. */
(() => {
  function starsEl(rating) {
    const wrap = document.createElement("span");
    wrap.className = "stars";
    wrap.setAttribute("aria-label", `${rating} dari 5 bintang`);
    for (let i = 1; i <= 5; i++) {
      const star = document.createElement("span");
      star.className = "star" + (i <= Math.round(rating) ? " on" : "");
      star.setAttribute("aria-hidden", "true");
      star.textContent = "★";
      wrap.appendChild(star);
    }
    return wrap;
  }

  /* Struktur sama dengan ulasan/partials/review_item.html */
  function renderReview(r) {
    const li = document.createElement("li");
    li.className = "review-item";
    li.dataset.reviewId = r.id;

    const meta = document.createElement("div");
    meta.className = "review-meta";
    const avatar = document.createElement("span");
    avatar.className = "avatar review-avatar";
    avatar.textContent = r.author.charAt(0);
    const who = document.createElement("div");
    who.className = "review-who";
    const author = document.createElement("strong");
    author.className = "review-author";
    author.textContent = r.author;
    const date = document.createElement("span");
    date.className = "muted review-date";
    date.textContent = r.created_display + (r.edited ? " · diedit" : "");
    who.append(author, date);
    meta.append(avatar, who, starsEl(r.rating));

    const comment = document.createElement("p");
    comment.className = "review-comment";
    comment.textContent = r.comment;

    li.append(meta, comment);
    if (r.is_owner) {
      const actions = document.createElement("div");
      actions.className = "review-actions";
      const edit = document.createElement("button");
      edit.type = "button";
      edit.className = "link-btn underline";
      edit.dataset.reviewEdit = "";
      edit.dataset.url = r.edit_url;
      edit.textContent = "Edit";
      const del = document.createElement("button");
      del.type = "button";
      del.className = "link-btn underline danger";
      del.dataset.reviewDelete = "";
      del.dataset.url = r.delete_url;
      del.textContent = "Hapus";
      actions.append(edit, del);
      li.appendChild(actions);
    }
    li._review = r;
    return li;
  }

  function updateSummary(block, summary) {
    if (!summary) return;
    block.querySelector("[data-summary-avg]").textContent = summary.count ? summary.average.toFixed(1) : "–";
    block.querySelector("[data-summary-count]").textContent = summary.count;
    const stars = starsEl(summary.average);
    stars.dataset.summaryStars = "";
    stars.removeAttribute("aria-label");
    stars.setAttribute("aria-hidden", "true");
    block.querySelector("[data-summary-stars]").replaceWith(stars);
  }

  function refreshEmpty(block) {
    const list = block.querySelector("[data-review-list]");
    block.querySelector("[data-review-empty]").hidden = list.children.length > 0;
  }

  function showFormError(form, result) {
    const box = form.querySelector("[data-form-error]");
    const errors = result.errors || {};
    const messages = Object.values(errors).flat().map((e) => e.message);
    box.textContent = messages.length ? messages.join(" ") : result.message;
    box.hidden = false;
    showToast(result.message, "error");
  }

  function setOwnReviewState(block, hasReview) {
    const form = block.querySelector("[data-review-form]");
    const note = block.querySelector("[data-already-note]");
    if (form) form.hidden = hasReview;
    if (note) note.hidden = !hasReview;
  }

  async function loadReviews(block) {
    const sort = block.querySelector("[data-review-sort]").value;
    block.classList.add("is-loading");
    const result = await getJSON(`${block.dataset.listUrl}&sort=${encodeURIComponent(sort)}`);
    block.classList.remove("is-loading");
    if (!result.success) {
      showToast(result.message, "error");
      return;
    }
    const list = block.querySelector("[data-review-list]");
    list.replaceChildren(...result.reviews.map(renderReview));
    updateSummary(block, result.summary);
    refreshEmpty(block);
  }

  function initCreate(block) {
    const form = block.querySelector("[data-review-form]");
    if (!form) return;
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      form.querySelector("[data-form-error]").hidden = true;
      const submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      const result = await postJSON(form.action, new FormData(form));
      submit.disabled = false;
      if (!result.success) {
        showFormError(form, result);
        return;
      }
      const item = renderReview(result.review);
      item.classList.add("is-new");
      block.querySelector("[data-review-list]").prepend(item);
      setTimeout(() => item.classList.remove("is-new"), 1500);
      updateSummary(block, result.summary);
      refreshEmpty(block);
      form.reset();
      setOwnReviewState(block, true);
      showToast(result.message, "success");
    });
  }

  function openEditor(block, item, button) {
    if (item.querySelector(".review-edit-form")) return;
    const review = item._review || {
      rating: item.querySelectorAll(".review-meta .star.on").length,
      comment: item.querySelector(".review-comment").innerText,
    };
    const kind = block.dataset.kind;
    const id = item.dataset.reviewId;

    const form = document.createElement("form");
    form.className = "review-edit-form";
    form.noValidate = true;
    form.action = button.dataset.url;
    const values = [5, 4, 3, 2, 1].map((v) => `
      <input type="radio" name="rating" id="${kind}-edit-${id}-${v}" value="${v}" ${v === review.rating ? "checked" : ""}>
      <label for="${kind}-edit-${id}-${v}" title="${v} bintang"><span aria-hidden="true">★</span><span class="visually-hidden">${v} bintang</span></label>`).join("");
    form.innerHTML = `
      <fieldset class="star-input"><legend class="field-label">Rating</legend><div class="star-input-row">${values}</div></fieldset>
      <div class="field"><label for="${kind}-edit-comment-${id}">Komentar</label>
        <textarea name="comment" id="${kind}-edit-comment-${id}" rows="3" maxlength="1000"></textarea></div>
      <p class="field-error" data-form-error hidden></p>
      <div class="btn-row">
        <button type="submit" class="btn-primary btn-sm">Simpan</button>
        <button type="button" class="btn-outline btn-sm" data-edit-cancel>Batal</button>
      </div>`;
    form.querySelector("textarea").value = review.comment;

    const view = [item.querySelector(".review-comment"), item.querySelector(".review-actions")];
    view.forEach((el) => { el.hidden = true; });
    item.appendChild(form);
    form.querySelector("textarea").focus();

    form.querySelector("[data-edit-cancel]").addEventListener("click", () => {
      form.remove();
      view.forEach((el) => { el.hidden = false; });
    });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const result = await postJSON(form.action, new FormData(form));
      if (!result.success) {
        showFormError(form, result);
        return;
      }
      item.replaceWith(renderReview(result.review));
      updateSummary(block, result.summary);
      showToast(result.message, "success");
    });
  }

  async function deleteReview(block, item, button) {
    const ok = await confirmDialog("Ulasan ini akan dihapus permanen.", {
      title: "Hapus ulasan", confirmText: "Hapus", danger: true,
    });
    if (!ok) return;
    button.disabled = true;
    const result = await postJSON(button.dataset.url);
    if (!result.success) {
      button.disabled = false;
      showToast(result.message, "error");
      return;
    }
    item.remove();
    updateSummary(block, result.summary);
    refreshEmpty(block);
    setOwnReviewState(block, false);
    showToast(result.message, "success");
  }

  function initBlock(block) {
    initCreate(block);
    block.querySelector("[data-review-sort]").addEventListener("change", () => loadReviews(block));
    block.addEventListener("click", (e) => {
      const edit = e.target.closest("[data-review-edit]");
      const del = e.target.closest("[data-review-delete]");
      if (edit) openEditor(block, edit.closest(".review-item"), edit);
      if (del) deleteReview(block, del.closest(".review-item"), del);
    });
  }

  const init = () => document.querySelectorAll("[data-reviews]").forEach(initBlock);
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
