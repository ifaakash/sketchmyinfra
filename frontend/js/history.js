/**
 * Session history — in-memory for anonymous users, API-backed for logged-in users.
 */

const diagramHistory = [];
let activeHistoryIndex = -1;

/**
 * Add a diagram generation to history (in-memory, both anon and logged-in).
 */
function historyAdd(entry) {
  diagramHistory.unshift({
    prompt: entry.prompt,
    puml: entry.puml,
    imageDataUri: entry.imageDataUri,
    timestamp: new Date(),
    fromApi: false,
  });
  activeHistoryIndex = 0;
  renderHistory();
}

/**
 * Get a history entry by index.
 */
function historyGet(index) {
  return diagramHistory[index] || null;
}

/**
 * Clear all history.
 */
function historyClear() {
  diagramHistory.length = 0;
  activeHistoryIndex = -1;
  renderHistory();
}

/**
 * Load history from the API for logged-in users.
 * Prepends API entries that aren't already in the in-memory list.
 */
async function loadHistoryFromAPI() {
  try {
    const res = await fetch('/api/history', { credentials: 'include' });
    if (!res.ok) return;

    const data = await res.json();
    if (!data.items?.length) return;

    // Track existing in-memory prompts to avoid duplicates
    const existingPrompts = new Set(diagramHistory.map(e => e.puml));

    let added = 0;
    for (const item of data.items) {
      if (existingPrompts.has(item.puml_code)) continue;
      diagramHistory.push({
        prompt: item.prompt,
        puml: item.puml_code,
        imageDataUri: null,       // not stored — will re-render on click
        timestamp: new Date(item.created_at),
        fromApi: true,
      });
      added++;
    }

    if (added > 0) renderHistory();
  } catch {
    // Non-critical — silently ignore
  }
}

/**
 * Render the history sidebar.
 */
function renderHistory() {
  const list = document.getElementById('history-list');
  const empty = document.getElementById('history-empty');
  if (!list) return;

  if (diagramHistory.length === 0) {
    list.innerHTML = '';
    if (empty) {
      list.appendChild(empty);
      empty.classList.remove('hidden');
    }
    return;
  }

  if (empty) empty.classList.add('hidden');

  list.innerHTML = diagramHistory.map((entry, i) => {
    const time = entry.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const truncated = entry.prompt.length > 50 ? entry.prompt.slice(0, 50) + '...' : entry.prompt;
    const isActive = i === activeHistoryIndex;
    const badge = entry.fromApi && !entry.imageDataUri
      ? `<span class="text-[9px] text-gray-500 ml-1">saved</span>`
      : '';

    return `
      <div class="history-item ${isActive ? 'active' : ''}" data-index="${i}">
        <div class="flex-1 min-w-0">
          <p class="text-xs text-gray-300 truncate">${escapeHtml(truncated)}${badge}</p>
          <p class="text-[10px] text-gray-600 mt-0.5">${time}</p>
        </div>
      </div>
    `;
  }).join('');

  // Bind click events
  list.querySelectorAll('.history-item').forEach(item => {
    item.addEventListener('click', () => {
      const index = parseInt(item.dataset.index, 10);
      restoreFromHistory(index);
    });
  });
}

/**
 * Restore a diagram from history.
 * If the entry came from the API and has no cached image, re-render the PUML.
 */
async function restoreFromHistory(index) {
  const entry = historyGet(index);
  if (!entry) return;

  activeHistoryIndex = index;
  renderHistory();

  const promptInput = document.getElementById('prompt-input');
  if (promptInput) promptInput.value = entry.prompt;

  showPumlCode(entry.puml);

  if (entry.imageDataUri) {
    showDiagram(entry.imageDataUri);
    return;
  }

  // No cached image (API entry) — re-render from PUML
  try {
    showPanel('loading');
    setLoadingText('Rendering saved diagram...');
    const result = await apiRender(entry.puml, 'svg');
    entry.imageDataUri = result.image;  // cache for next click
    // Update app state so download/iterate work
    if (typeof currentPuml !== 'undefined') {
      currentPuml = entry.puml;
      currentImageUri = result.image;
      currentPrompt = entry.prompt;
    }
    showDiagram(result.image);
  } catch (err) {
    showError('Render failed', err.message || 'Could not render saved diagram.', null);
  }
}

/**
 * Escape HTML to prevent XSS in history rendering.
 */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
