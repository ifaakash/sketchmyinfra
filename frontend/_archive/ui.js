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
 */
function showError(title, detail) {
  const titleEl = $('#error-title');
  const detailEl = $('#error-detail');
  if (titleEl) titleEl.textContent = title;
  if (detailEl) detailEl.textContent = detail;
  showPanel('error');
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
