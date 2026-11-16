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
  // Phones show one pane at a time: anything happening on the canvas
  // (loading, result, error) brings the Diagram tab forward
  if (name !== 'empty' && typeof setWorkspaceView === 'function') {
    setWorkspaceView('diagram');
  }
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
  if (typeof setCodeAvailable === 'function') setCodeAvailable(true);
}

/**
 * Hide the PUML code panel.
 */
function hidePumlCode() {
  const panel = $('#puml-panel');
  if (panel) panel.classList.add('hidden');
  if (typeof setCodeAvailable === 'function') setCodeAvailable(false);
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
  textarea.classList.toggle('border-smi-accent', isReadOnly);
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

const SVG_DATA_PREFIX = 'data:image/svg+xml;base64,';

/** Size from the root's width/height attributes in px; null if missing or %. */
function svgAttrSize(svg) {
  const attr = (name) => {
    const v = svg.getAttribute(name);
    return v && !v.trim().endsWith('%') ? parseFloat(v) : NaN;
  };
  const [w, h] = [attr('width'), attr('height')];
  return w > 0 && h > 0 ? { w, h } : null;
}

/**
 * Size of an <svg> root in px: its width/height attributes, else its viewBox.
 * Returns null when neither gives a usable size.
 */
function svgSize(svg) {
  let { w, h } = svgAttrSize(svg) || {};
  if (!(w > 0 && h > 0)) {
    const vb = (svg.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    [w, h] = [vb[2], vb[3]];
  }
  return w > 0 && h > 0 ? { w, h } : null;
}

/** Parse an SVG data URI into its root <svg> element, or null. */
function parseSvgDataUri(dataUri) {
  if (!dataUri?.startsWith(SVG_DATA_PREFIX)) return null;
  try {
    const bytes = Uint8Array.from(atob(dataUri.slice(SVG_DATA_PREFIX.length)), c => c.charCodeAt(0));
    const doc = new DOMParser().parseFromString(new TextDecoder().decode(bytes), 'image/svg+xml');
    const svg = doc.documentElement;
    return svg.nodeName === 'svg' && !doc.querySelector('parsererror') ? svg : null;
  } catch {
    return null;
  }
}

/**
 * D2 omits width/height on its outer <svg> (only viewBox, so it "fits to
 * screen"). As an <img> that has no natural size: it collapses in the canvas
 * stage and draws at a default size on a <canvas>. Give it the viewBox size.
 * PlantUML SVGs already carry a size and come back unchanged.
 */
function withIntrinsicSize(dataUri) {
  const svg = parseSvgDataUri(dataUri);
  if (!svg || svgAttrSize(svg)) return dataUri;
  const size = svgSize(svg);
  if (!size) return dataUri;
  svg.setAttribute('width', size.w);
  svg.setAttribute('height', size.h);
  const bytes = new TextEncoder().encode(new XMLSerializer().serializeToString(svg));
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return SVG_DATA_PREFIX + btoa(binary);
}

/**
 * Display the rendered diagram image.
 */
function showDiagram(dataUri) {
  const img = $('#diagram-image');
  if (img) {
    img.src = withIntrinsicSize(dataUri);
  }
  showPanel('diagram');
  // canvas.js fits on the image's load event; an image that is already
  // loaded (same src again) won't fire it, so fit now too
  if (img?.complete) window.diagramCanvas?.fit();
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

const GOOGLE_ICON = `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none"><path d="M21.8 10.2h-9.6v3.9h5.5c-.25 1.4-1.55 4.1-5.5 4.1-3.3 0-6-2.75-6-6.15s2.7-6.15 6-6.15c1.9 0 3.15.8 3.87 1.5l2.65-2.55C17.05 3.3 14.85 2.4 12.2 2.4 6.9 2.4 2.6 6.7 2.6 12s4.3 9.6 9.6 9.6c5.55 0 9.2-3.9 9.2-9.4 0-.63-.07-1.1-.15-1.55z" fill="currentColor"/></svg>`;
const GITHUB_ICON = `<svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5C5.65.5.5 5.65.5 12a11.5 11.5 0 007.86 10.93c.57.1.78-.25.78-.55 0-.27-.01-.98-.02-1.93-3.2.7-3.88-1.54-3.88-1.54-.52-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.76 2.7 1.25 3.36.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.19-3.08-.12-.29-.52-1.46.11-3.04 0 0 .97-.31 3.18 1.18a11.01 11.01 0 015.79 0c2.21-1.49 3.18-1.18 3.18-1.18.63 1.58.23 2.75.11 3.04.74.8 1.18 1.82 1.18 3.08 0 4.42-2.69 5.4-5.25 5.68.41.35.78 1.05.78 2.12 0 1.53-.01 2.77-.01 3.14 0 .3.2.66.79.55A11.5 11.5 0 0023.5 12C23.5 5.65 18.35.5 12 .5z"/></svg>`;

/**
 * Google + GitHub sign-in buttons. auth.js stashes the diagram on screen when
 * any /api/auth/.../login link is clicked, so these need no handlers.
 * @param {string} size - 'md' (cards, modals) or 'sm' (toasts)
 */
function signInButtonsHtml(size = 'md') {
  const pad = size === 'sm' ? 'text-xs px-3 py-1.5' : 'text-sm px-5 py-2.5';
  const base = `${pad} font-medium rounded-lg transition-colors text-center inline-flex items-center justify-center gap-2 no-underline`;
  return (
    `<a href="/api/auth/google/login" class="bg-smi-accent hover:bg-smi-accent-hover text-smi-on-accent ${base}">${GOOGLE_ICON}Login with Google</a>` +
    `<a href="/api/auth/github/login" class="bg-smi-strong hover:bg-smi-strong-hover text-smi-on-strong ${base}">${GITHUB_ICON}Login with GitHub</a>`
  );
}

const SAVE_NUDGE_KEY = 'smi_save_nudged';

/**
 * "Keep this diagram" toast for anonymous users, after a download or a 👍.
 * Once per browser: it's an offer, not a wall.
 */
function showSaveNudge() {
  if (window.currentUser) return;
  try {
    if (localStorage.getItem(SAVE_NUDGE_KEY)) return;
    localStorage.setItem(SAVE_NUDGE_KEY, '1');
  } catch {
    return; // storage blocked: can't remember it was shown, so don't risk nagging
  }

  const container = $('#toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = 'border rounded-xl px-5 py-4 shadow-lg bg-smi-surface border-smi-border text-sm max-w-sm';
  toast.innerHTML = `
    <p class="font-semibold text-smi-ink mb-1">Keep this diagram</p>
    <p class="text-smi-ink-2 text-xs mb-3">Right now it only lives in this browser. Sign in to save it to your account. New accounts get a free Pro trial to edit it too.</p>
    <div class="flex flex-wrap gap-2">
      ${signInButtonsHtml('sm')}
      <button type="button" class="text-xs font-semibold px-3 py-1.5 rounded-lg text-smi-ink-3 hover:text-smi-ink transition-colors">Not now</button>
    </div>
  `;
  toast.querySelector('button')?.addEventListener('click', () => toast.remove());
  container.appendChild(toast);
  setTimeout(() => { if (toast.parentNode) toast.remove(); }, 20000);
}

/**
 * Anonymous click on Open in Editor: sign in (with the Pro trial) instead of
 * the waitlist, which is for signed-in users whose trial has ended.
 */
function showSignInModal() {
  const modal = $('#signin-modal');
  if (!modal) return;
  const buttons = $('#signin-modal-buttons');
  if (buttons && !buttons.childElementCount) buttons.innerHTML = signInButtonsHtml();
  modal.classList.remove('hidden');
}

function hideSignInModal() {
  $('#signin-modal')?.classList.add('hidden');
}

function bindSignInModal() {
  const modal = $('#signin-modal');
  if (!modal) return;

  $('#signin-modal-close')?.addEventListener('click', hideSignInModal);
  modal.addEventListener('click', (e) => { if (e.target === modal) hideSignInModal(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) hideSignInModal();
  });
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
      `<div class="flex flex-col gap-2 mt-4">${signInButtonsHtml()}</div>` +
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
      `<div class="bg-smi-accent-soft border border-smi-border rounded-xl p-4 mb-4 text-left">` +
        `<p class="text-sm font-semibold text-smi-accent-text mb-1">SketchMyInfra Pro</p>` +
        `<ul class="text-xs text-gray-700 dark:text-gray-300 space-y-1 mb-2">` +
          `<li>Unlimited diagram generations</li>` +
          `<li>Priority rendering</li>` +
          `<li>History saved across sessions</li>` +
          `<li>Early supporter pricing: <strong class="text-gray-900 dark:text-emerald-400">$5/month</strong></li>` +
        `</ul>` +
      `</div>` +
      `<button id="btn-notify-pro" class="w-full bg-smi-accent hover:bg-smi-accent-hover text-smi-on-accent font-medium text-sm px-5 py-2.5 rounded-lg transition-colors mb-2">` +
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
        btn.classList.remove('bg-smi-accent', 'hover:bg-smi-accent-hover', 'text-smi-on-accent');
        btn.classList.add('bg-emerald-700', 'text-white', 'cursor-default');
      });
    }
  }, 0);
}

const PRO_INTEREST_KEY = 'smi_pro_interest';

/**
 * Same rule as the backend's _check_rate_limit: tier "pro" with no expiry,
 * or a trial that hasn't ended yet.
 */
function isProUser(user = window.currentUser) {
  if (!user || user.tier !== 'pro') return false;
  return !user.trial_expires_at || new Date(user.trial_expires_at) > new Date();
}

/**
 * Upsell for Open in Editor. Payments aren't live, so it records interest
 * (Formspree, tagged by source) instead of selling.
 */
function showProModal() {
  const modal = $('#pro-modal');
  if (!modal) return;

  const signedIn = !!window.currentUser?.email;
  const alreadyJoined = localStorage.getItem(PRO_INTEREST_KEY) === '1';
  $('#pro-interest-email')?.classList.toggle('hidden', signedIn);
  $('#pro-interest-form')?.classList.toggle('hidden', alreadyJoined);
  $('#pro-interest-done')?.classList.toggle('hidden', !alreadyJoined);
  $('#pro-interest-error')?.classList.add('hidden');

  modal.classList.remove('hidden');
  if (!signedIn && !alreadyJoined) $('#pro-interest-email')?.focus();
}

function hideProModal() {
  $('#pro-modal')?.classList.add('hidden');
}

function bindProModal() {
  const modal = $('#pro-modal');
  if (!modal) return;

  $('#pro-modal-close')?.addEventListener('click', hideProModal);
  // Backdrop click closes; clicks inside the card don't
  modal.addEventListener('click', (e) => { if (e.target === modal) hideProModal(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) hideProModal();
  });

  $('#pro-interest-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = $('#pro-interest-submit');
    const errorEl = $('#pro-interest-error');
    const email = (window.currentUser?.email || $('#pro-interest-email')?.value || '').trim();

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errorEl.textContent = 'Enter a valid email address.';
      errorEl.classList.remove('hidden');
      return;
    }

    btn.disabled = true;
    btn.textContent = 'Submitting...';
    errorEl.classList.add('hidden');

    try {
      const res = await fetch('https://formspree.io/f/xykboawb', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({
          email,
          _subject: 'SketchMyInfra Pro Interest (Open in Editor)',
          source: 'open-in-editor',
          signed_in: !!window.currentUser,
        }),
      });
      // Unlike the rate-limit prompt, a signed-out user's email exists
      // nowhere else, so a failed submit must not look like success
      if (!res.ok) throw new Error(`Formspree ${res.status}`);

      localStorage.setItem(PRO_INTEREST_KEY, '1');
      $('#pro-interest-form')?.classList.add('hidden');
      $('#pro-interest-done')?.classList.remove('hidden');
    } catch {
      errorEl.textContent = 'Something went wrong. Please try again.';
      errorEl.classList.remove('hidden');
    } finally {
      btn.disabled = false;
      btn.textContent = "I'm interested, notify me";
    }
  });
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
 * Download a Blob as a file. A short blob: URL, not a data: URL — Chrome caps
 * URLs at 2MB and a 2x PNG of a real diagram is well past that.
 */
function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  setTimeout(() => URL.revokeObjectURL(url), 0);
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

// Largest canvas Safari will draw (16.7M px); bigger ones come out blank
const MAX_CANVAS_PIXELS = 16777216;

/**
 * Convert an SVG data URI to a PNG Blob via Canvas, at 2x for retina unless
 * that would exceed the canvas limit. The size comes from the SVG itself:
 * an <img>'s width/height is a 300x150 guess for a size-less (D2) SVG.
 */
function svgToPngBlob(svgDataUri) {
  return new Promise((resolve, reject) => {
    const svg = parseSvgDataUri(svgDataUri);
    const size = svg && svgSize(svg);
    if (!size) {
      reject(new Error('Not an SVG with a known size'));
      return;
    }
    const img = new Image();
    img.onload = () => {
      const { w, h } = size;
      const scale = Math.min(2, Math.sqrt(MAX_CANVAS_PIXELS / (w * h)));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(w * scale);
      canvas.height = Math.round(h * scale);
      const ctx = canvas.getContext('2d');
      // Diagrams assume a light background; PNG would otherwise be transparent
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0, w, h);
      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error('Diagram too large for PNG'))),
        'image/png',
      );
    };
    img.onerror = () => reject(new Error('Failed to convert SVG to PNG'));
    img.src = withIntrinsicSize(svgDataUri);
  });
}
