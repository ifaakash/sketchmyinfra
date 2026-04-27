/**
 * Feedback — floating button + modal form + live cards in testimonials grid.
 * Form shown via floating button (logged-in users only).
 * Feedback cards render inside #feedback-list in the testimonials section.
 */

let selectedRating = 0;

function initFeedback() {
  loadFeedback();

  const stars = document.querySelectorAll('#feedback-stars svg');
  stars.forEach(star => {
    star.addEventListener('click', () => {
      selectedRating = parseInt(star.dataset.star);
      updateStars();
    });
  });

  const btn = document.getElementById('feedback-submit');
  if (btn) btn.addEventListener('click', submitFeedback);
}

function updateStars() {
  document.querySelectorAll('#feedback-stars svg').forEach(star => {
    const val = parseInt(star.dataset.star);
    if (val <= selectedRating) {
      star.classList.remove('text-gray-300', 'dark:text-gray-700');
      star.classList.add('text-amber-400');
    } else {
      star.classList.add('text-gray-300', 'dark:text-gray-700');
      star.classList.remove('text-amber-400');
    }
  });
}

async function submitFeedback() {
  const message = document.getElementById('feedback-message').value.trim();

  if (!selectedRating) {
    showFeedbackStatus('Please select a rating', 'text-red-400');
    return;
  }
  if (!message) {
    showFeedbackStatus('Please write a message', 'text-red-400');
    return;
  }

  const btn = document.getElementById('feedback-submit');
  btn.disabled = true;

  try {
    const res = await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ rating: selectedRating, message }),
    });

    if (res.status === 409) {
      showFeedbackStatus('You have already submitted feedback. Thank you!', 'text-amber-400');
      return;
    }
    if (!res.ok) throw new Error('Failed to submit');

    showFeedbackStatus('Thank you for your feedback!', 'text-emerald-400');
    document.getElementById('feedback-message').value = '';
    selectedRating = 0;
    updateStars();

    // Close modal after a brief delay
    setTimeout(() => {
      document.getElementById('feedback-modal').classList.add('hidden');
      document.body.style.overflow = '';
    }, 1500);

    loadFeedback();
  } catch {
    showFeedbackStatus('Something went wrong. Please try again.', 'text-red-400');
  } finally {
    btn.disabled = false;
  }
}

function showFeedbackStatus(msg, colorClass) {
  const el = document.getElementById('feedback-status');
  el.textContent = msg;
  el.className = 'mt-2 text-sm text-center ' + colorClass;
  el.classList.remove('hidden');
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

/** Called from auth.js when user state is known */
function showFeedbackForm(isLoggedIn) {
  const fab = document.getElementById('feedback-fab');
  if (fab) fab.classList.toggle('hidden', !isLoggedIn);
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
      <button onclick="document.getElementById('feedback-modal').classList.remove('hidden');document.body.style.overflow='hidden';this.closest('.border').remove()"
        class="text-xs font-semibold px-3 py-1.5 rounded-lg bg-brand-600 hover:bg-brand-500 text-white transition-colors">Share feedback</button>
      <button onclick="this.closest('.border').remove()"
        class="text-xs font-semibold px-3 py-1.5 rounded-lg text-gray-500 hover:text-gray-300 transition-colors">Later</button>
    </div>
  `;
  container.appendChild(toast);

  // Auto-dismiss after 15 seconds
  setTimeout(() => { if (toast.parentNode) toast.remove(); }, 15000);
}

document.addEventListener('DOMContentLoaded', initFeedback);
