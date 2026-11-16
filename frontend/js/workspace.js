/**
 * Workspace layout state.
 *  - Phones (<768px): one pane at a time, picked by the bottom tab bar.
 *    #workspace[data-view] = prompt | diagram | code
 *  - Desktop: the code column can be hidden. #workspace[data-code] = open | closed
 * CSS in workspace.css does the actual showing/hiding.
 */

const CODE_PREF_KEY = 'smi_code_panel';

function setWorkspaceView(view) {
  const ws = document.getElementById('workspace');
  if (!ws) return;
  if (view === 'code' && !hasCode()) view = 'diagram';
  ws.dataset.view = view;
  document.querySelectorAll('#mobile-tabs [data-view]').forEach(tab => {
    tab.setAttribute('aria-selected', String(tab.dataset.view === view));
  });
}

function hasCode() {
  const panel = document.getElementById('puml-panel');
  return !!panel && !panel.classList.contains('hidden');
}

/** Called by ui.js whenever the code panel is shown or hidden. */
function setCodeAvailable(available) {
  const tab = document.querySelector('#mobile-tabs [data-view="code"]');
  if (tab) tab.disabled = !available;
  const ws = document.getElementById('workspace');
  if (!available && ws?.dataset.view === 'code') setWorkspaceView('diagram');
}

function setCodePanelOpen(open, remember = false) {
  const ws = document.getElementById('workspace');
  if (!ws) return;
  ws.dataset.code = open ? 'open' : 'closed';
  document.getElementById('btn-toggle-code')?.setAttribute('aria-pressed', String(open));
  if (remember) {
    try { localStorage.setItem(CODE_PREF_KEY, open ? 'open' : 'closed'); } catch { /* storage blocked */ }
  }
}

function initWorkspace() {
  document.querySelectorAll('#mobile-tabs [data-view]').forEach(tab => {
    tab.addEventListener('click', () => setWorkspaceView(tab.dataset.view));
  });

  // Code column: the visitor's last choice, else open only on wide screens
  // where the canvas still gets enough room next to it.
  let pref = null;
  try { pref = localStorage.getItem(CODE_PREF_KEY); } catch { /* storage blocked */ }
  setCodePanelOpen(pref ? pref === 'open' : window.matchMedia('(min-width: 1280px)').matches);

  document.getElementById('btn-toggle-code')?.addEventListener('click', () => {
    const open = document.getElementById('workspace')?.dataset.code !== 'open';
    setCodePanelOpen(open, true);
  });
}

document.addEventListener('DOMContentLoaded', initWorkspace);
