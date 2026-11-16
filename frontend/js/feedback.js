/**
 * Feedback — floating FAB + live cards in testimonials grid + generation nudge.
 * The actual form lives on /feedback/ page (standalone).
 * This file handles: FAB visibility, loading feedback into testimonials, nudge toast.
 */

function initFeedback() {
  loadFeedback();
}

async function loadFeedback() {
  try {
    const res = await fetch('/api/feedback');
    if (!res.ok) return;
    const items = await res.json();

    const list = document.getElementById('feedback-list');
    if (!list) return;

    if (!items.length) {
      list.innerHTML = '';
      return;
    }

    list.innerHTML = items.map(fb => {
      const avatar = fb.avatar_url
        ? `<img src="${escapeAttr(fb.avatar_url)}" class="w-9 h-9 rounded-full object-cover" alt="">`
        : `<div class="w-9 h-9 bg-brand-600 rounded-full flex items-center justify-center text-sm font-bold text-white">${escapeHtml((fb.name || '?')[0].toUpperCase())}</div>`;

      return `
        <div class="testimonial-card relative">
          <span class="absolute top-4 right-4 inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Verified user</span>
          <div class="flex items-center gap-1 mb-3">${renderStars(fb.rating)}</div>
          <p class="text-sm text-gray-700 dark:text-gray-300 leading-relaxed mb-4">"${escapeHtml(fb.message)}"</p>
          <div class="flex items-center gap-3">
            ${avatar}
            <div>
              <p class="text-sm font-medium">${escapeHtml(fb.name)}</p>
              <p class="text-xs text-gray-500">SketchMyInfra user</p>
            </div>
          </div>
        </div>`;
    }).join('');
    document.getElementById('testimonials')?.classList.replace('hidden', 'flex');
  } catch { /* silent */ }
}

function renderStars(n) {
  return Array.from({ length: 5 }, (_, i) =>
    `<svg class="w-4 h-4 ${i < n ? 'text-amber-400' : 'text-gray-300 dark:text-gray-700'}" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>`
  ).join('');
}

function escapeHtml(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeAttr(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/** Called from auth.js — show FAB for all visitors */
function showFeedbackForm() {
  const fab = document.getElementById('feedback-fab');
  if (fab) fab.classList.remove('hidden');
}

/** Rich toast nudge — called from app.js after 3rd generation */
function showFeedbackNudge() {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'border rounded-xl px-5 py-4 shadow-lg bg-brand-600/10 border-brand-500/30 text-sm max-w-sm';
  toast.innerHTML = `
    <p class="font-semibold text-brand-400 mb-1">Enjoying SketchMyInfra?</p>
    <p class="text-gray-400 text-xs mb-3">You've generated 3 diagrams! We'd love your feedback — it takes 30 seconds.</p>
    <div class="flex gap-2">
      <a href="/feedback/" class="text-xs font-semibold px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white transition-colors no-underline">Share feedback</a>
      <button onclick="this.closest('.border').remove()"
        class="text-xs font-semibold px-3 py-1.5 rounded-lg text-gray-500 hover:text-gray-300 transition-colors">Later</button>
    </div>
  `;
  container.appendChild(toast);
  setTimeout(() => { if (toast.parentNode) toast.remove(); }, 15000);
}

/*
 * Inline rating under a freshly generated diagram (#rating-row). Anyone can
 * rate, signed in or not. 👎 is recorded on the click, then the reason chips
 * refine it, so a vote counts even if they never press Send.
 */
let ratingGenerationId = null;

function showRatingRow(generationId) {
  if (!generationId) {
    hideRatingRow();
    return;
  }
  ratingGenerationId = generationId;
  document.getElementById('rating-ask')?.classList.remove('hidden');
  document.getElementById('rating-reasons')?.classList.add('hidden');
  document.getElementById('rating-thanks')?.classList.add('hidden');
  document.querySelectorAll('.rating-reason').forEach(chip => setReasonPressed(chip, false));
  const comment = document.getElementById('rating-comment');
  if (comment) comment.value = '';
  document.getElementById('rating-row')?.classList.remove('hidden');
}

function hideRatingRow() {
  ratingGenerationId = null;
  document.getElementById('rating-row')?.classList.add('hidden');
}

function setReasonPressed(chip, pressed) {
  chip.setAttribute('aria-pressed', String(pressed));
  chip.classList.toggle('border-smi-accent', pressed);
  chip.classList.toggle('text-smi-accent-text', pressed);
  chip.classList.toggle('bg-smi-selected', pressed);
  chip.classList.toggle('border-smi-border', !pressed);
  chip.classList.toggle('text-smi-ink-2', !pressed);
  chip.classList.toggle('bg-smi-surface', !pressed);
}

function showRatingThanks(text) {
  document.getElementById('rating-ask')?.classList.add('hidden');
  document.getElementById('rating-reasons')?.classList.add('hidden');
  const thanks = document.getElementById('rating-thanks');
  if (thanks) {
    thanks.textContent = text;
    thanks.classList.remove('hidden');
  }
}

function bindRatingRow() {
  document.querySelectorAll('.rating-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (!ratingGenerationId) return;
      const rating = Number(btn.dataset.rating);
      apiRateGeneration(ratingGenerationId, { rating });
      if (rating === 1) {
        showRatingThanks('Thanks!');
        setTimeout(showSaveNudge, 600);
      } else {
        document.getElementById('rating-ask')?.classList.add('hidden');
        document.getElementById('rating-reasons')?.classList.remove('hidden');
      }
    });
  });

  document.querySelectorAll('.rating-reason').forEach(chip => {
    chip.addEventListener('click', () => {
      setReasonPressed(chip, chip.getAttribute('aria-pressed') !== 'true');
    });
  });

  document.getElementById('rating-reasons')?.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!ratingGenerationId) return;
    const reasons = [...document.querySelectorAll('.rating-reason[aria-pressed="true"]')]
      .map(chip => chip.dataset.reason);
    const comment = document.getElementById('rating-comment')?.value.trim() || undefined;
    apiRateGeneration(ratingGenerationId, { rating: -1, reasons, comment });
    showRatingThanks('Thanks, this helps fix it.');
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initFeedback();
  bindRatingRow();
});
