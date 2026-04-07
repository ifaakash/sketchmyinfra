/**
 * Session history — tracks generated diagrams in memory.
 */

const diagramHistory = [];
let activeHistoryIndex = -1;

/**
 * Add a diagram generation to history.
 */
function historyAdd(entry) {
  diagramHistory.unshift({
    prompt: entry.prompt,
    puml: entry.puml,
    imageDataUri: entry.imageDataUri,
    timestamp: new Date(),
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

    return `
      <div class="history-item ${isActive ? 'active' : ''}" data-index="${i}">
        <div class="flex-1 min-w-0">
          <p class="text-xs text-gray-300 truncate">${escapeHtml(truncated)}</p>
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
 */
function restoreFromHistory(index) {
  const entry = historyGet(index);
  if (!entry) return;

  activeHistoryIndex = index;
  renderHistory();

  // Restore UI state
  const promptInput = document.getElementById('prompt-input');
  if (promptInput) promptInput.value = entry.prompt;

  showPumlCode(entry.puml);
  showDiagram(entry.imageDataUri);
}

/**
 * Escape HTML to prevent XSS in history rendering.
 */
function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
