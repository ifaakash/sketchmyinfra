/* Admin dashboard client.
 *
 * Plain globals, no modules or build step — matching frontend/js/api.js.
 *
 * Every view is (mount, load): mount() builds the static chrome (filter
 * controls) once, load() fetches and fills only the data region. Splitting them
 * keeps a debounced search box from being destroyed mid-keystroke when its own
 * input triggers a re-render.
 */

'use strict';

const PER_PAGE = 15;
const REQUEST_TIMEOUT_MS = 30000;
const KEY_STORAGE = 'admin_key';

const ROUTES = ['overview', 'users', 'generations'];
const DEFAULT_ROUTE = 'overview';

const STATUS_LABELS = {
  success: 'success',
  gemini_error: 'gemini error',
  autofix_failed: 'autofix failed',
  render_error: 'render error',
  mermaid_error: 'mermaid error',
};

const state = {
  key: null,
  route: null,     // route currently mounted
  params: {},      // query params from the hash
};

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------------------
// Escaping
// ---------------------------------------------------------------------------

// Two separate helpers on purpose. The textContent->innerHTML trick escapes
// & < > but NOT quotes, so reusing it for attribute values let a prompt
// containing a double quote break out of title="...". escapeAttr covers quotes.
function escapeHtml(value) {
  const div = document.createElement('div');
  div.textContent = value == null ? '' : String(value);
  return div.innerHTML;
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

async function adminGet(path, params) {
  const query = new URLSearchParams({ key: state.key });
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== '' && v !== null && v !== undefined) query.set(k, v);
  });

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(`/api/admin${path}?${query}`, { signal: controller.signal });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const err = new Error(body.detail || `HTTP ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('Request timed out');
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

const num = (n) => (typeof n === 'number' ? n.toLocaleString() : '-');

function dateTime(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  return isNaN(d) ? '-' : d.toLocaleString();
}

function relative(iso) {
  if (!iso) return 'never';
  const diff = Date.now() - new Date(iso).getTime();
  if (isNaN(diff)) return '-';
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

function statusBadge(status) {
  const label = STATUS_LABELS[status] || String(status).replace(/_/g, ' ');
  return `<span class="badge ${escapeAttr(status)}">${escapeHtml(label)}</span>`;
}

// Failure-rate thresholds carried over from the original dashboard.
function rateClass(rate) {
  return rate > 20 ? 'danger' : rate > 5 ? 'warning' : 'success';
}

function statCard(value, label, variant) {
  return `<div class="card${variant ? ' ' + variant : ''}">
    <div class="value">${escapeHtml(value)}</div>
    <div class="label">${escapeHtml(label)}</div>
  </div>`;
}

function emptyState(message) {
  return `<div class="empty-state">${escapeHtml(message)}</div>`;
}

// ---------------------------------------------------------------------------
// Routing — the hash carries route + filters + page, so any view is linkable
// and survives a reload or the back button.
// ---------------------------------------------------------------------------

function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [path, queryString] = raw.split('?');
  const route = ROUTES.includes(path) ? path : DEFAULT_ROUTE;
  const params = {};
  new URLSearchParams(queryString || '').forEach((v, k) => { params[k] = v; });
  return { route, params };
}

function buildHash(route, params) {
  const query = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== '' && v !== null && v !== undefined) query.set(k, v);
  });
  const qs = query.toString();
  return `#/${route}${qs ? '?' + qs : ''}`;
}

function go(route, params) {
  location.hash = buildHash(route, params);
}

/** Merge params into the current route's hash. Resets to page 1 unless the
 *  caller is explicitly changing the page — changing a filter while on page 7
 *  would otherwise land on an empty page. */
function setParams(patch) {
  const next = Object.assign({}, state.params, patch);
  if (!('page' in patch)) delete next.page;
  Object.keys(next).forEach((k) => {
    if (next[k] === '' || next[k] == null) delete next[k];
  });
  go(state.route, next);
}

const VIEWS = {};  // route -> { mount, load }

async function handleRoute() {
  const { route, params } = parseHash();
  const routeChanged = route !== state.route;
  state.route = route;
  state.params = params;

  document.querySelectorAll('#nav a').forEach((a) => {
    a.classList.toggle('active', a.dataset.route === route);
  });

  const view = VIEWS[route];
  if (routeChanged) {
    $('view').innerHTML = '';
    view.mount();
  } else if (view.sync) {
    view.sync();
  }
  await view.load();
}

// ---------------------------------------------------------------------------
// Data-region helpers
// ---------------------------------------------------------------------------

function showLoading(el) {
  el.innerHTML = '<div class="loading">Loading…</div>';
}

function setStatus(message, isError) {
  const el = $('status');
  el.textContent = message;
  el.className = 'status-msg' + (isError ? ' error' : '');
}

/** Run a fetch into a container, routing failures to the container and the
 *  status line so no view has to repeat try/catch. */
async function fill(el, fetcher, renderer) {
  showLoading(el);
  try {
    const data = await fetcher();
    el.innerHTML = renderer(data);
    setStatus(`Updated ${new Date().toLocaleTimeString()}`);
    return data;
  } catch (e) {
    if (e.status === 403) return signOut('Session rejected — key is invalid.');
    el.innerHTML = emptyState(e.message);
    setStatus(e.message, true);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Pager
// ---------------------------------------------------------------------------

/** Page numbers to show: always first and last, plus a window around the
 *  current page, with '…' standing in for the skipped runs. */
function pageWindow(current, total) {
  const pages = new Set([1, total, current]);
  for (let d = 1; d <= 2; d++) {
    if (current - d >= 1) pages.add(current - d);
    if (current + d <= total) pages.add(current + d);
  }
  const sorted = [...pages].sort((a, b) => a - b);
  const out = [];
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push('gap');
    out.push(p);
  });
  return out;
}

function renderPager(meta) {
  const { page, per_page: perPage, total, total_pages: totalPages } = meta;
  const first = total === 0 ? 0 : (page - 1) * perPage + 1;
  const last = Math.min(page * perPage, total);

  const buttons = pageWindow(page, totalPages).map((p) =>
    p === 'gap'
      ? '<span class="gap">…</span>'
      : `<button data-page="${p}"${p === page ? ' class="current"' : ''}>${p}</button>`
  ).join('');

  return `<div class="pager">
    <button data-page="${page - 1}"${page <= 1 ? ' disabled' : ''}>&laquo; Prev</button>
    ${buttons}
    <button data-page="${page + 1}"${page >= totalPages ? ' disabled' : ''}>Next &raquo;</button>
    <span class="summary">Showing ${num(first)}–${num(last)} of ${num(total)}</span>
  </div>`;
}

/** One delegated listener per data region handles every pager button, so
 *  re-rendering the table never leaves stale listeners behind. */
function bindPager(container) {
  container.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-page]');
    if (!btn || btn.disabled) return;
    setParams({ page: btn.dataset.page });
  });
}

const currentPage = () => Math.max(1, parseInt(state.params.page, 10) || 1);

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------

function breakdown(counts, classFor) {
  const entries = Object.entries(counts || {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return '<p class="dim" style="font-size:.8rem">No data yet.</p>';
  const max = entries[0][1] || 1;
  const total = entries.reduce((sum, [, v]) => sum + v, 0);
  return '<div class="breakdown">' + entries.map(([k, v]) => {
    const share = total ? ((v / total) * 100).toFixed(1) : '0.0';
    return `<div class="breakdown-row">
      <div class="breakdown-head">
        <span class="k">${escapeHtml(STATUS_LABELS[k] || k)}</span>
        <span class="v">${num(v)} · ${share}%</span>
      </div>
      <div class="breakdown-track">
        <div class="breakdown-fill ${classFor ? classFor(k) : ''}" style="width:${(v / max) * 100}%"></div>
      </div>
    </div>`;
  }).join('') + '</div>';
}

/** Stacked bar chart in plain HTML/flexbox rather than SVG.
 *  An SVG with width:100% scales its text along with the bars, so the axis
 *  labels grow with the viewport; flex columns keep the type at a fixed size
 *  and stay responsive for free. */
function trendChart(points) {
  const max = Math.max(1, ...points.map((p) => p.total));

  const cols = points.map((p) => {
    const tip = `${p.date} · ${p.total} total, ${p.success} ok, ${p.failed} failed`;
    const stackHeight = (p.total / max) * 100;
    const segs = p.total === 0
      ? ''
      : `<div class="chart-seg bad" style="flex:${p.failed}"></div>` +
        `<div class="chart-seg ok" style="flex:${p.success}"></div>`;
    return `<div class="chart-col" title="${escapeAttr(tip)}">
      <div class="chart-stack${p.total === 0 ? ' empty' : ''}" style="height:${stackHeight}%">${segs}</div>
    </div>`;
  }).join('');

  const labels = points.map((p, i) => {
    // Label every other day so 14 columns don't collide on narrow screens.
    const day = i % 2 === 0 ? new Date(p.date + 'T00:00:00Z').getUTCDate() : '';
    return `<div class="chart-label">${day}</div>`;
  }).join('');

  return `<div class="chart-plot">${cols}</div>
    <div class="chart-labels">${labels}</div>
    <div class="legend">
      <span><i class="swatch" style="background:var(--ok)"></i>Success</span>
      <span><i class="swatch" style="background:var(--bad)"></i>Failed</span>
      <span class="dim">Peak ${num(max)}/day · hover a bar for detail</span>
    </div>`;
}


function renderOverview(d) {
  return `
    <h2>Platform</h2>
    <div class="cards">
      ${statCard(num(d.total_users), 'Total Users')}
      ${statCard(num(d.new_users_7d), 'New Users (7d)')}
      ${statCard(num(d.total_generations), 'Total Generations')}
      ${statCard(num(d.generations_24h), 'Generations (24h)')}
      ${statCard(num(d.generations_7d), 'Generations (7d)')}
      ${statCard(num(d.total_drawings), 'Drawings')}
      ${statCard(num(d.total_feedback), 'Feedback')}
    </div>

    <h2>Generation health</h2>
    <div class="cards">
      ${statCard(num(d.success_count), 'Successful', 'success')}
      ${statCard(num(d.failure_count), 'Failed', 'danger')}
      ${statCard(d.failure_rate + '%', 'Failure Rate', rateClass(d.failure_rate))}
    </div>

    <h2>Last 14 days</h2>
    <div class="panel">${trendChart(d.trend || [])}</div>

    <h2>Breakdowns</h2>
    <div class="panels">
      <div class="panel">
        <h3>By status</h3>
        ${breakdown(d.status_counts, (k) => (k === 'success' ? 'ok' : 'bad'))}
      </div>
      <div class="panel"><h3>By renderer</h3>${breakdown(d.renderer_counts)}</div>
      <div class="panel"><h3>By category</h3>${breakdown(d.category_counts)}</div>
    </div>`;
}

VIEWS.overview = {
  mount() {
    $('view').innerHTML = '<div id="overviewData"></div>';
  },
  load() {
    return fill($('overviewData'), () => adminGet('/stats'), renderOverview);
  },
};

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

const USER_SORTS = [
  ['newest', 'Newest first'],
  ['oldest', 'Oldest first'],
  ['most_generations', 'Most generations'],
  ['recently_active', 'Recently active'],
];

function avatarCell(user) {
  const initial = (user.name || user.email || '?').trim().charAt(0).toUpperCase();
  const img = user.avatar_url
    ? `<img class="avatar" src="${escapeAttr(user.avatar_url)}" alt="" referrerpolicy="no-referrer">`
    : `<span class="avatar avatar-fallback">${escapeHtml(initial)}</span>`;
  return `<div class="user-cell">${img}<span>${escapeHtml(user.name || '—')}</span></div>`;
}

function renderUsers(res) {
  if (!res.items.length) return emptyState('No users match these filters.');

  const rows = res.items.map((u) => `<tr class="clickable" data-user-id="${escapeAttr(u.id)}"
        title="View this user's generations">
      <td>${avatarCell(u)}</td>
      <td class="truncate narrow" title="${escapeAttr(u.email)}">${escapeHtml(u.email)}</td>
      <td>${escapeHtml(u.oauth_provider)}</td>
      <td><span class="badge${u.tier === 'pro' ? ' tier-pro' : ''}">${escapeHtml(u.tier)}</span></td>
      <td class="nowrap">${escapeHtml(dateTime(u.created_at))}</td>
      <td class="nowrap">${num(u.generation_count)}</td>
      <td class="nowrap dim">${escapeHtml(relative(u.last_generation_at))}</td>
    </tr>`).join('');

  return `<div class="table-wrap"><table>
      <thead><tr>
        <th>Name</th><th>Email</th><th>Provider</th><th>Tier</th>
        <th>Signed up</th><th>Generations</th><th>Last active</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    ${renderPager(res.meta)}`;
}

VIEWS.users = {
  mount() {
    $('view').innerHTML = `
      <h2>Users</h2>
      <div class="filters">
        <input type="search" id="userSearch" placeholder="Search email or name…">
        <select id="userTier">
          <option value="">All tiers</option>
          <option value="free">Free</option>
          <option value="pro">Pro</option>
        </select>
        <select id="userSort">
          ${USER_SORTS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}
        </select>
      </div>
      <div id="usersData"></div>`;

    let debounce;
    $('userSearch').addEventListener('input', (e) => {
      clearTimeout(debounce);
      const value = e.target.value;
      debounce = setTimeout(() => setParams({ q: value }), 300);
    });
    $('userTier').addEventListener('change', (e) => setParams({ tier: e.target.value }));
    $('userSort').addEventListener('change', (e) => setParams({ sort: e.target.value }));

    const data = $('usersData');
    bindPager(data);
    data.addEventListener('click', (e) => {
      const row = e.target.closest('tr[data-user-id]');
      if (row) go('generations', { user_id: row.dataset.userId });
    });

    this.sync();
  },

  /** Push hash state back into the controls (for back/forward navigation),
   *  skipping whichever control the user is currently typing in. */
  sync() {
    const set = (el, value) => {
      if (el && el !== document.activeElement && el.value !== value) el.value = value;
    };
    set($('userSearch'), state.params.q || '');
    set($('userTier'), state.params.tier || '');
    set($('userSort'), state.params.sort || 'newest');
  },

  load() {
    return fill($('usersData'), () => adminGet('/users', {
      page: currentPage(),
      per_page: PER_PAGE,
      q: state.params.q,
      tier: state.params.tier,
      sort: state.params.sort || 'newest',
    }), renderUsers);
  },
};

// ---------------------------------------------------------------------------
// Generations
// ---------------------------------------------------------------------------

const STATUS_OPTIONS = [
  ['', 'All statuses'],
  ['failed', 'All failures'],
  ['success', 'Success'],
  ['gemini_error', 'Gemini error'],
  ['autofix_failed', 'Autofix failed'],
  ['render_error', 'Render error'],
  ['mermaid_error', 'Mermaid error'],
];

const RENDERER_OPTIONS = [
  ['', 'All renderers'],
  ['plantuml', 'PlantUML'],
  ['d2', 'D2'],
  ['excalidraw', 'Excalidraw'],
];

function userCell(g) {
  if (g.user_email) {
    return `<span class="truncate narrow" title="${escapeAttr(g.user_email)}"
      >${escapeHtml(g.user_email)}</span>`;
  }
  const ip = g.ip_address ? ` · ${escapeHtml(g.ip_address)}` : '';
  return `<span class="dim nowrap">anon${ip}</span>`;
}

function renderGenerations(res) {
  // The filter chip needs a human label; the API echoes the email on each row,
  // so take it from the first result and fall back to the raw id when empty.
  updateUserChip(res.items.length ? res.items[0].user_email : null);

  if (!res.items.length) return emptyState('No generations match these filters.');

  const rows = res.items.map((g) => `<tr class="clickable" data-id="${escapeAttr(g.id)}"
        title="Open full detail">
      <td class="nowrap">${escapeHtml(dateTime(g.created_at))}</td>
      <td>${userCell(g)}</td>
      <td>${statusBadge(g.status)}</td>
      <td class="nowrap">${escapeHtml(g.renderer)}</td>
      <td class="nowrap dim">${escapeHtml(g.category || '—')}</td>
      <td class="truncate" title="${escapeAttr(g.prompt)}">${escapeHtml(g.prompt)}</td>
      <td class="truncate narrow error-cell" title="${escapeAttr(g.error_message || '')}"
        >${escapeHtml(g.error_message || '—')}</td>
    </tr>`).join('');

  return `<div class="table-wrap"><table>
      <thead><tr>
        <th>Time</th><th>User</th><th>Status</th><th>Renderer</th>
        <th>Category</th><th>Prompt</th><th>Error</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    ${renderPager(res.meta)}`;
}

function updateUserChip(email) {
  const host = $('userChip');
  if (!host) return;
  const id = state.params.user_id;
  if (!id) { host.innerHTML = ''; return; }
  host.innerHTML = `<span class="chip">Filtered to ${escapeHtml(email || id)}
    <button data-clear-user title="Clear user filter">&times;</button></span>`;
}

VIEWS.generations = {
  mount() {
    $('view').innerHTML = `
      <h2>Generations</h2>
      <div class="filters">
        <input type="search" id="genSearch" placeholder="Search prompt text…">
        <select id="genStatus">
          ${STATUS_OPTIONS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}
        </select>
        <select id="genRenderer">
          ${RENDERER_OPTIONS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}
        </select>
        <label class="check"><input type="checkbox" id="genAnon"> Anonymous only</label>
        <span id="userChip"></span>
      </div>
      <div id="gensData"></div>`;

    let debounce;
    $('genSearch').addEventListener('input', (e) => {
      clearTimeout(debounce);
      const value = e.target.value;
      debounce = setTimeout(() => setParams({ q: value }), 300);
    });
    $('genStatus').addEventListener('change', (e) => setParams({ status: e.target.value }));
    $('genRenderer').addEventListener('change', (e) => setParams({ renderer: e.target.value }));
    // user_id and anonymous are mutually exclusive server-side; clear the
    // user filter when switching to anonymous so the UI can't lie.
    $('genAnon').addEventListener('change', (e) => setParams({
      anonymous: e.target.checked ? 'true' : '',
      user_id: e.target.checked ? '' : state.params.user_id,
    }));
    $('userChip').addEventListener('click', (e) => {
      if (e.target.closest('[data-clear-user]')) setParams({ user_id: '' });
    });

    const data = $('gensData');
    bindPager(data);
    data.addEventListener('click', (e) => {
      const row = e.target.closest('tr[data-id]');
      if (row) openDetail(row.dataset.id);
    });

    this.sync();
  },

  sync() {
    const set = (el, value) => {
      if (el && el !== document.activeElement && el.value !== value) el.value = value;
    };
    set($('genSearch'), state.params.q || '');
    set($('genStatus'), state.params.status || '');
    set($('genRenderer'), state.params.renderer || '');
    $('genAnon').checked = state.params.anonymous === 'true';
    updateUserChip(null);
  },

  load() {
    return fill($('gensData'), () => adminGet('/generations', {
      page: currentPage(),
      per_page: PER_PAGE,
      status: state.params.status,
      renderer: state.params.renderer,
      q: state.params.q,
      user_id: state.params.user_id,
      anonymous: state.params.anonymous,
    }), renderGenerations);
  },
};

// ---------------------------------------------------------------------------
// Detail modal
// ---------------------------------------------------------------------------

function field(label, value, className) {
  if (value === null || value === undefined || value === '') return '';
  return `<div class="field">
    <div class="k">${escapeHtml(label)}</div>
    <pre class="${className || ''}">${escapeHtml(value)}</pre>
  </div>`;
}

function renderDetail(g) {
  return `
    <div class="meta-grid">
      <div><div class="k dim">Status</div>${statusBadge(g.status)}</div>
      <div><div class="k dim">Renderer</div>${escapeHtml(g.renderer)}</div>
      <div><div class="k dim">Category</div>${escapeHtml(g.category || '—')}</div>
      <div><div class="k dim">When</div>${escapeHtml(dateTime(g.created_at))}</div>
      <div><div class="k dim">User</div>${escapeHtml(g.user_email || 'anonymous')}</div>
      <div><div class="k dim">IP</div><span class="mono">${escapeHtml(g.ip_address || '—')}</span></div>
    </div>
    ${field('Prompt', g.prompt)}
    ${field('Error', g.error_message, 'err')}
    ${field('Generated code', g.puml_code)}
    ${field('IR data', g.ir_data ? JSON.stringify(g.ir_data, null, 2) : null)}
    <div class="field"><div class="k">Generation ID</div>
      <pre class="mono">${escapeHtml(g.id)}</pre></div>`;
}

async function openDetail(id) {
  $('detailModal').classList.add('open');
  showLoading($('modalBody'));
  try {
    const data = await adminGet(`/generations/${encodeURIComponent(id)}`);
    $('modalBody').innerHTML = renderDetail(data);
  } catch (e) {
    $('modalBody').innerHTML = emptyState(e.message);
  }
}

function closeDetail() {
  $('detailModal').classList.remove('open');
  $('modalBody').innerHTML = '';
}

// ---------------------------------------------------------------------------
// Session
// ---------------------------------------------------------------------------

function gateStatus(message, isError) {
  const el = $('gateStatus');
  el.textContent = message || '';
  el.className = 'status-msg' + (isError ? ' error' : '');
}

async function unlock() {
  const key = $('apiKey').value.trim();
  if (!key) return gateStatus('Enter an API key', true);

  const btn = $('unlockBtn');
  btn.disabled = true;
  btn.textContent = 'Checking…';
  gateStatus('');

  state.key = key;
  try {
    // /stats is the cheapest way to prove the key before committing it.
    await adminGet('/stats');
    sessionStorage.setItem(KEY_STORAGE, key);
    enterShell();
  } catch (e) {
    state.key = null;
    gateStatus(e.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Unlock';
  }
}

function enterShell() {
  $('keyGate').style.display = 'none';
  $('shell').classList.add('visible');
  if (!location.hash) {
    location.replace('#/' + DEFAULT_ROUTE);   // replace: don't add a history entry
  }
  handleRoute();
}

function signOut(message) {
  sessionStorage.removeItem(KEY_STORAGE);
  state.key = null;
  state.route = null;
  closeDetail();
  $('shell').classList.remove('visible');
  $('keyGate').style.display = 'flex';
  $('apiKey').value = '';
  gateStatus(message || '', Boolean(message));
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

$('unlockBtn').addEventListener('click', unlock);
$('apiKey').addEventListener('keydown', (e) => { if (e.key === 'Enter') unlock(); });
$('refreshBtn').addEventListener('click', () => VIEWS[state.route].load());
$('signOutBtn').addEventListener('click', () => signOut());
$('modalCloseBtn').addEventListener('click', closeDetail);
$('detailModal').addEventListener('click', (e) => {
  if (e.target === $('detailModal')) closeDetail();   // click the backdrop
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && $('detailModal').classList.contains('open')) closeDetail();
});
window.addEventListener('hashchange', () => {
  if (state.key) handleRoute();
});

const savedKey = sessionStorage.getItem(KEY_STORAGE);
if (savedKey) {
  state.key = savedKey;
  enterShell();
}
