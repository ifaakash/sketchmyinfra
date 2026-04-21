/**
 * SketchMyInfra — auth widget.
 *
 * On page load, asks the backend who the user is via /api/auth/me.
 * Renders either the provider login buttons or an avatar+logout pill
 * into the #auth-slot div in the navbar.
 *
 * Depends on: nothing (pure DOM). Loads after ui.js so `$` is available,
 * but also works without it.
 */

// Global the rest of the app can read (currently just used for debugging).
window.currentUser = null;

document.addEventListener('DOMContentLoaded', () => {
  // In local mock mode we don't have a real backend, so skip and show nothing.
  // USE_MOCKS is declared in api.js which loads before auth.js.
  if (typeof USE_MOCKS !== 'undefined' && USE_MOCKS) {
    return;
  }
  refreshAuth();
});

async function refreshAuth() {
  try {
    const res = await fetch('/api/auth/me', {
      credentials: 'include',
    });
    if (res.ok) {
      const user = await res.json();
      window.currentUser = user;
      renderLoggedIn(user);
    } else {
      window.currentUser = null;
      renderLoggedOut();
    }
  } catch (err) {
    // Network hiccup — treat as logged out so the UI still works.
    window.currentUser = null;
    renderLoggedOut();
  }
}

function renderLoggedOut() {
  const googleSvg = `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none"><path d="M21.8 10.2h-9.6v3.9h5.5c-.25 1.4-1.55 4.1-5.5 4.1-3.3 0-6-2.75-6-6.15s2.7-6.15 6-6.15c1.9 0 3.15.8 3.87 1.5l2.65-2.55C17.05 3.3 14.85 2.4 12.2 2.4 6.9 2.4 2.6 6.7 2.6 12s4.3 9.6 9.6 9.6c5.55 0 9.2-3.9 9.2-9.4 0-.63-.07-1.1-.15-1.55z" fill="currentColor"/></svg>`;
  const githubSvg = `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5C5.65.5.5 5.65.5 12a11.5 11.5 0 007.86 10.93c.57.1.78-.25.78-.55 0-.27-.01-.98-.02-1.93-3.2.7-3.88-1.54-3.88-1.54-.52-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.19-3.08-.12-.29-.52-1.46.11-3.04 0 0 .97-.31 3.18 1.18a11.01 11.01 0 015.79 0c2.21-1.49 3.18-1.18 3.18-1.18.63 1.58.23 2.75.11 3.04.74.8 1.18 1.82 1.18 3.08 0 4.42-2.69 5.4-5.25 5.68.41.35.78 1.05.78 2.12 0 1.53-.01 2.77-.01 3.14 0 .3.2.66.79.55A11.5 11.5 0 0023.5 12C23.5 5.65 18.35.5 12 .5z"/></svg>`;

  const slot = document.getElementById('auth-slot');
  if (slot) {
    slot.innerHTML = `
      <a href="/api/auth/google/login"
         class="text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors flex items-center gap-2"
         title="Login with Google">${googleSvg}Google</a>
      <a href="/api/auth/github/login"
         class="text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors flex items-center gap-2"
         title="Login with GitHub">${githubSvg}GitHub</a>
    `;
  }

  const mobileSlot = document.getElementById('auth-slot-mobile');
  if (mobileSlot) {
    mobileSlot.innerHTML = `
      <a href="/api/auth/google/login"
         class="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white py-2 transition-colors">
        ${googleSvg}Login with Google</a>
      <a href="/api/auth/github/login"
         class="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white py-2 transition-colors">
        ${githubSvg}Login with GitHub</a>
    `;
  }
}

function renderLoggedIn(user) {
  // Avatar: prefer provider-supplied URL, fall back to initial in a colored circle.
  const initial = (user.name || user.email || '?').trim().charAt(0).toUpperCase();
  const isPro = user.tier === 'pro';

  const avatarHtml = user.avatar_url
    ? `<img src="${escapeHtml(user.avatar_url)}" alt="" class="w-8 h-8 rounded-full object-cover" />`
    : `<div class="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-sm font-bold text-white">${escapeHtml(initial)}</div>`;

  const proBadge = isPro
    ? `<span class="text-xs font-semibold px-1.5 py-0.5 rounded-md bg-gradient-to-r from-amber-400 to-orange-400 text-white leading-none">PRO</span>`
    : '';

  const slot = document.getElementById('auth-slot');
  if (slot) {
    slot.innerHTML = `
      <div class="flex items-center gap-2">
        <div class="relative">${avatarHtml}${isPro ? `<span class="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-amber-400 border-2 border-white dark:border-gray-900"></span>` : ''}</div>
        <span class="text-sm font-medium text-gray-700 dark:text-gray-300 hidden lg:block">${escapeHtml(user.name || user.email)}</span>
        ${proBadge}
        <button id="btn-logout"
                class="text-sm font-medium text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-3 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
          Logout
        </button>
      </div>
    `;
    document.getElementById('btn-logout')?.addEventListener('click', handleLogout);
  }

  const mobileSlot = document.getElementById('auth-slot-mobile');
  if (mobileSlot) {
    mobileSlot.innerHTML = `
      <div class="flex items-center gap-3 py-2">
        <div class="relative">${avatarHtml}${isPro ? `<span class="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-amber-400 border-2 border-white dark:border-gray-900"></span>` : ''}</div>
        <span class="text-sm font-medium text-gray-700 dark:text-gray-300 flex-1">${escapeHtml(user.name || user.email)}</span>
        ${proBadge}
        <button id="btn-logout-mobile"
                class="text-sm font-medium text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-3 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
          Logout
        </button>
      </div>
    `;
    document.getElementById('btn-logout-mobile')?.addEventListener('click', handleLogout);
  }
}

async function handleLogout() {
  try {
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include',
    });
  } catch (err) {
    // Even if the network call fails, re-render — the cookie may still be gone.
  }
  window.currentUser = null;
  renderLoggedOut();
}

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
