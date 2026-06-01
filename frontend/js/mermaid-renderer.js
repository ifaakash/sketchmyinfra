/**
 * Client-side Mermaid diagram rendering.
 * Renders Mermaid code to SVG in the browser — no backend needed.
 */

let mermaidReady = false;
let mermaidLoadPromise = null;

/**
 * Lazy-load Mermaid.js from CDN on first use.
 */
function loadMermaid() {
  if (mermaidLoadPromise) return mermaidLoadPromise;

  mermaidLoadPromise = new Promise((resolve, reject) => {
    if (window.mermaid) {
      mermaidReady = true;
      resolve();
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js';
    script.onload = () => {
      window.mermaid.initialize({
        startOnLoad: false,
        theme: 'base',
        themeVariables: {
          primaryColor: '#dbeafe',
          primaryTextColor: '#1e40af',
          primaryBorderColor: '#3b82f6',
          lineColor: '#64748b',
          secondaryColor: '#f0fdf4',
          tertiaryColor: '#fef3c7',
          fontFamily: 'Inter, system-ui, sans-serif',
        },
        flowchart: { curve: 'basis', padding: 20 },
        sequence: { mirrorActors: false },
      });
      mermaidReady = true;
      resolve();
    };
    script.onerror = () => {
      mermaidLoadPromise = null;
      reject(new Error('Failed to load Mermaid.js from CDN'));
    };
    document.head.appendChild(script);
  });

  return mermaidLoadPromise;
}

/**
 * Render Mermaid code to an SVG data URI.
 * @param {string} code - Mermaid diagram source
 * @returns {Promise<{image: string, format: string}>}
 */
async function renderMermaid(code) {
  await loadMermaid();

  const id = 'mermaid-' + Date.now();

  try {
    const { svg } = await window.mermaid.render(id, code);
    const dataUri = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svg)));
    return { image: dataUri, format: 'svg' };
  } catch (err) {
    throw new Error('Mermaid render error: ' + (err.message || 'Invalid diagram syntax'));
  }
}

/**
 * Convert an SVG data URI to a PNG data URI via canvas.
 * Used for PNG download of Mermaid diagrams.
 * @param {string} svgDataUri - SVG as data URI
 * @returns {Promise<string>} PNG data URI
 */
function svgToPngDataUri(svgDataUri) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const scale = 2; // 2x for retina
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;
      const ctx = canvas.getContext('2d');
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0);
      resolve(canvas.toDataURL('image/png'));
    };
    img.onerror = () => reject(new Error('Failed to convert SVG to PNG'));
    img.src = svgDataUri;
  });
}
