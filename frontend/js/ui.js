/**
 * UI helpers — DOM manipulation, state transitions, toasts.
 */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// Panel references
const panels = {
  empty: () => $('#empty-state'),
  loading: () => $('#loading-state'),
  diagram: () => $('#diagram-state'),
  error: () => $('#error-state'),
};

/**
 * Show one right-panel state, hide the rest.
 */
function showPanel(name) {
  Object.entries(panels).forEach(([key, getter]) => {
    const el = getter();
    if (el) {
      el.classList.toggle('hidden', key !== name);
    }
  });
}

/**
 * Set the loading message text.
 */
function setLoadingText(text) {
  const el = $('#loading-text');
  if (el) el.textContent = text;
}

/**
 * Show the PUML code panel with the given code.
 */
function showPumlCode(code) {
  const panel = $('#puml-panel');
  const textarea = $('#puml-code');
  if (panel && textarea) {
    panel.classList.remove('hidden');
    textarea.value = code;
    textarea.readOnly = true;
    $('#puml-actions')?.classList.add('hidden');
    $('#btn-edit-puml').textContent = 'Edit';
  }
}

/**
 * Hide the PUML code panel.
 */
function hidePumlCode() {
  const panel = $('#puml-panel');
  if (panel) panel.classList.add('hidden');
}

/**
 * Toggle edit mode on the PUML textarea.
 */
function togglePumlEdit() {
  const textarea = $('#puml-code');
  const btn = $('#btn-edit-puml');
  const actions = $('#puml-actions');

  if (!textarea || !btn) return;

  const isReadOnly = textarea.readOnly;
  textarea.readOnly = !isReadOnly;
  textarea.classList.toggle('border-indigo-500/50', isReadOnly);
  textarea.classList.toggle('border-gray-700/50', !isReadOnly);
  btn.textContent = isReadOnly ? 'Done' : 'Edit';
  actions?.classList.toggle('hidden', !isReadOnly);

  if (isReadOnly) {
    textarea.focus();
  }
}

/**
 * Get current PUML code from the editor.
 */
function getPumlCode() {
  return $('#puml-code')?.value || '';
}

/**
 * Display the rendered diagram image.
 */
function showDiagram(dataUri) {
  const img = $('#diagram-image');
  if (img) {
    img.src = dataUri;
  }
  showPanel('diagram');
}

/**
 * Show error state with title and detail.
 * @param {string} title
 * @param {string} detail
 * @param {string|null} lastImageUri - data URI of the last rendered diagram;
 *   shown blurred behind the card. Falls back to the sample image in the HTML.
 */
function showError(title, detail, lastImageUri = null) {
  const titleEl = $('#error-title');
  const detailEl = $('#error-detail');
  if (titleEl) titleEl.textContent = title;
  if (detailEl) detailEl.textContent = detail;

  const bgImg = $('#error-bg-image');
  if (bgImg && lastImageUri) {
    bgImg.src = lastImageUri;
  }

  showPanel('error');
}

/**
 * Show rate-limit prompt for anonymous users — encourages login.
 * Reuses the #error-state panel but injects login buttons instead of "Try Again".
 */
function showRateLimitLogin(limit, lastImageUri = null) {
  const bgImg = $('#error-bg-image');
  if (bgImg && lastImageUri) bgImg.src = lastImageUri;

  const titleEl = $('#error-title');
  const detailEl = $('#error-detail');
  const retryBtn = $('#btn-retry');

  if (titleEl) titleEl.textContent = "You're on a roll!";
  if (detailEl) {
    detailEl.innerHTML =
      `You\u2019ve used your <strong>${limit}</strong> free generations. ` +
      `Sign in to keep going \u2014 it\u2019s free.` +
      `<div class="flex flex-col gap-2 mt-4">` +
        `<a href="/api/auth/google/login" class="bg-brand-600 hover:bg-brand-500 text-white font-medium text-sm px-5 py-2.5 rounded-lg transition-colors text-center inline-flex items-center justify-center gap-2">` +
          `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none"><path d="M21.8 10.2h-9.6v3.9h5.5c-.25 1.4-1.55 4.1-5.5 4.1-3.3 0-6-2.75-6-6.15s2.7-6.15 6-6.15c1.9 0 3.15.8 3.87 1.5l2.65-2.55C17.05 3.3 14.85 2.4 12.2 2.4 6.9 2.4 2.6 6.7 2.6 12s4.3 9.6 9.6 9.6c5.55 0 9.2-3.9 9.2-9.4 0-.63-.07-1.1-.15-1.55z" fill="currentColor"/></svg>` +
          `Login with Google</a>` +
        `<a href="/api/auth/github/login" class="bg-gray-700 hover:bg-gray-600 text-white font-medium text-sm px-5 py-2.5 rounded-lg transition-colors text-center inline-flex items-center justify-center gap-2">` +
          `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5C5.65.5.5 5.65.5 12a11.5 11.5 0 007.86 10.93c.57.1.78-.25.78-.55 0-.27-.01-.98-.02-1.93-3.2.7-3.88-1.54-3.88-1.54-.52-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.19-3.08-.12-.29-.52-1.46.11-3.04 0 0 .97-.31 3.18 1.18a11.01 11.01 0 015.79 0c2.21-1.49 3.18-1.18 3.18-1.18.63 1.58.23 2.75.11 3.04.74.8 1.18 1.82 1.18 3.08 0 4.42-2.69 5.4-5.25 5.68.41.35.78 1.05.78 2.12 0 1.53-.01 2.77-.01 3.14 0 .3.2.66.79.55A11.5 11.5 0 0023.5 12C23.5 5.65 18.35.5 12 .5z"/></svg>` +
          `Login with GitHub</a>` +
      `</div>` +
      `<p class="text-xs text-gray-400 dark:text-gray-500 mt-3">or come back tomorrow</p>`;
  }
  if (retryBtn) retryBtn.classList.add('hidden');

  showPanel('error');
}

/**
 * Show Pro upgrade prompt for logged-in users who hit the free tier limit.
 * Plays on momentum (they just generated 5 diagrams) and honest scarcity
 * (Pro is coming soon, collecting interest now).
 */
function showUpgradePrompt(limit, lastImageUri = null) {
  const bgImg = $('#error-bg-image');
  if (bgImg && lastImageUri) bgImg.src = lastImageUri;

  const titleEl = $('#error-title');
  const detailEl = $('#error-detail');
  const retryBtn = $('#btn-retry');

  if (titleEl) titleEl.textContent = "Whoa, " + limit + " diagrams today? You're a machine!";
  if (detailEl) {
    detailEl.innerHTML =
      `<p class="mb-3">You\u2019ve hit the free tier limit. But we see you, you\u2019re building something real.</p>` +
      `<div class="bg-gradient-to-r from-brand-600/10 to-emerald-500/10 border border-brand-500/20 rounded-xl p-4 mb-4 text-left">` +
        `<p class="text-sm font-semibold text-brand-400 mb-1">SketchMyInfra Pro</p>` +
        `<ul class="text-xs text-gray-700 dark:text-gray-300 space-y-1 mb-2">` +
          `<li>Unlimited diagram generations</li>` +
          `<li>Priority rendering</li>` +
          `<li>History saved across sessions</li>` +
          `<li>Early supporter pricing: <strong class="text-gray-900 dark:text-emerald-400">$2/month</strong></li>` +
        `</ul>` +
      `</div>` +
      `<button id="btn-notify-pro" class="w-full bg-brand-600 hover:bg-brand-500 text-white font-medium text-sm px-5 py-2.5 rounded-lg transition-colors mb-2">` +
        `Count me in \u2022 notify me at launch</button>` +
      `<p class="text-xs text-gray-500 dark:text-gray-500">We\u2019re building this right now. Stay tuned for early access.</p>`;
  }
  if (retryBtn) retryBtn.classList.add('hidden');

  showPanel('error');

  // Submit interest to the Formspree beta waitlist form.
  // Uses the logged-in user's email from window.currentUser (set by auth.js).
  setTimeout(() => {
    const btn = document.getElementById('btn-notify-pro');
    if (btn) {
      btn.addEventListener('click', async () => {
        const email = window.currentUser?.email;
        if (!email) return;

        btn.textContent = 'Submitting...';
        btn.disabled = true;

        try {
          await fetch('https://formspree.io/f/xykboawb', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify({
              email: email,
              _subject: 'SketchMyInfra Pro Interest',
              source: 'pro-upgrade-prompt',
            }),
          });
        } catch {
          // Even if Formspree fails, show success — we have their email in the DB.
        }

        btn.textContent = '\u2705 You\u2019re on the early list!';
        btn.classList.remove('bg-brand-600', 'hover:bg-brand-500');
        btn.classList.add('bg-emerald-700', 'cursor-default');
      });
    }
  }, 0);
}

/**
 * Set the generate button to loading or idle state.
 */
function setGenerateLoading(loading) {
  const btn = $('#btn-generate');
  const icon = $('#generate-icon');
  const text = $('#generate-text');

  if (!btn) return;

  btn.disabled = loading;

  if (loading) {
    icon.classList.add('hidden');
    text.textContent = 'Generating...';
    // Insert spinner before text
    const spinner = document.createElement('div');
    spinner.className = 'spinner';
    spinner.id = 'generate-spinner';
    text.parentElement.insertBefore(spinner, text);
  } else {
    icon.classList.remove('hidden');
    text.textContent = 'Generate';
    const spinner = $('#generate-spinner');
    if (spinner) spinner.remove();
  }
}

/**
 * Show a toast notification.
 */
function showToast(message, type = 'info', duration = 4000) {
  const container = $('#toast-container');
  if (!container) return;

  const isDark = document.documentElement.classList.contains('dark');
  const colors = isDark ? {
    info: 'bg-gray-800 border-gray-700 text-gray-200',
    success: 'bg-emerald-900/80 border-emerald-700 text-emerald-100',
    error: 'bg-red-900/80 border-red-700 text-red-100',
  } : {
    info: 'bg-white border-gray-300 text-gray-800',
    success: 'bg-emerald-50 border-emerald-300 text-emerald-800',
    error: 'bg-red-50 border-red-300 text-red-800',
  };

  const toast = document.createElement('div');
  toast.className = `toast border rounded-lg px-4 py-3 text-sm shadow-lg ${colors[type] || colors.info}`;
  toast.textContent = message;

  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('toast-out');
    toast.addEventListener('animationend', () => toast.remove());
  }, duration);
}

/**
 * Download a data URI as a file.
 */
function downloadDataUri(dataUri, filename) {
  const link = document.createElement('a');
  link.href = dataUri;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/**
 * Copy text to clipboard.
 */
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    showToast('Copied to clipboard', 'success', 2000);
  } catch {
    showToast('Failed to copy', 'error', 2000);
  }
}
