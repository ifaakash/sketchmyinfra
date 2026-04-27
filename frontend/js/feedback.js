/**
 * Feedback — star rating form + live display of user feedback.
 * Form shown only when user is logged in. Feedback list is public.
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
  const statusEl = document.getElementById('feedback-status');

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
    document.getElementById('feedback-form-wrapper').classList.add('hidden');
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
  el.className = 'mt-2 text-sm ' + colorClass;
  el.classList.remove('hidden');
}

async function loadFeedback() {
  try {
    const res = await fetch('/api/feedback');
    if (!res.ok) return;
    const items = await res.json();

    const list = document.getElementById('feedback-list');
    const empty = document.getElementById('feedback-empty');

    if (!items.length) {
      empty.classList.remove('hidden');
      return;
    }

    empty.classList.add('hidden');
    list.innerHTML = items.map(fb => `
      <div class="border border-gray-200 dark:border-gray-800 rounded-xl p-5 bg-white/5 dark:bg-white/[0.02]">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-3">
            ${fb.avatar_url
              ? `<img src="${escapeAttr(fb.avatar_url)}" class="w-8 h-8 rounded-full" alt="">`
              : `<div class="w-8 h-8 bg-brand-600 rounded-full flex items-center justify-center text-xs font-bold text-white">${escapeHtml((fb.name || '?')[0].toUpperCase())}</div>`
            }
            <span class="text-sm font-medium">${escapeHtml(fb.name)}</span>
          </div>
          <div class="flex gap-0.5">${renderStars(fb.rating)}</div>
        </div>
        <p class="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">${escapeHtml(fb.message)}</p>
      </div>
    `).join('');
  } catch { /* silent */ }
}

function renderStars(n) {
  return Array.from({ length: 5 }, (_, i) =>
    `<svg class="w-4 h-4 ${i < n ? 'text-amber-400' : 'text-gray-300 dark:text-gray-700'}" fill="currentColor" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>`
  ).join('');
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeAttr(s) {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/** Called from auth.js when user state is known */
function showFeedbackForm(isLoggedIn) {
  const wrapper = document.getElementById('feedback-form-wrapper');
  if (wrapper) wrapper.classList.toggle('hidden', !isLoggedIn);
}

document.addEventListener('DOMContentLoaded', initFeedback);
