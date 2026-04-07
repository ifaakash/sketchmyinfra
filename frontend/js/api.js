/**
 * API client — calls backend or falls back to mocks on localhost.
 */

const API_BASE = '';
const USE_MOCKS = !window.location.hostname || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

async function handleResponse(response) {
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || data.error || `Request failed (${response.status})`);
  }
  return data;
}

/**
 * Generate PUML code from a natural language prompt.
 * @param {string} prompt - User's architecture description
 * @param {string|null} context - Previous PUML code for iteration
 * @returns {Promise<{puml: string, prompt_used: string}>}
 */
async function apiGenerate(prompt, context = null) {
  if (USE_MOCKS) {
    return mockGenerate(prompt, context);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);

  try {
    const response = await fetch(`${API_BASE}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, context }),
      signal: controller.signal
    });
    return handleResponse(response);
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Render PUML code into an image.
 * @param {string} puml - PlantUML source code
 * @param {string} format - 'png' or 'svg'
 * @returns {Promise<{image: string, format: string}>}
 */
async function apiRender(puml, format = 'png') {
  if (USE_MOCKS) {
    return mockRender(puml, format);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);

  try {
    const response = await fetch(`${API_BASE}/api/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ puml, format }),
      signal: controller.signal
    });
    return handleResponse(response);
  } finally {
    clearTimeout(timeout);
  }
}
