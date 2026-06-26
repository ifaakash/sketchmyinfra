/**
 * SketchMyInfra — App entry point.
 * Wires events to API calls to UI updates.
 */

// Current state
let currentPuml = '';
let currentCode = '';
let currentRenderer = 'plantuml';
let currentImageUri = '';
let currentPrompt = '';
let isGenerating = false;

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  bindEvents();
  initNavbar();
  initScrollReveal();
  renderHistory();

  if (USE_MOCKS) {
    showToast('Running in mock mode (localhost)', 'info', 3000);
  }
});

function bindEvents() {
  // Generate button
  $('#btn-generate')?.addEventListener('click', handleGenerate);

  // Ctrl+Enter to generate
  $('#prompt-input')?.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleGenerate();
    }
  });

  // Example chips (including template items)
  $$('.example-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.dataset.prompt;
      if (!prompt) return;
      const input = $('#prompt-input');
      if (input) {
        input.value = prompt;
        input.focus();
        // Collapse templates panel after selection
        const panel = $('#templates-panel');
        if (panel && !panel.classList.contains('hidden')) {
          panel.classList.add('hidden');
          $('#templates-chevron')?.classList.remove('rotate-180');
        }
      }
    });
  });

  // Templates panel toggle
  const btnTemplates = $('#btn-show-templates');
  const templatesPanel = $('#templates-panel');
  const chevron = $('#templates-chevron');
  if (btnTemplates && templatesPanel) {
    btnTemplates.addEventListener('click', () => {
      const isHidden = templatesPanel.classList.toggle('hidden');
      chevron?.classList.toggle('rotate-180', !isHidden);
    });
  }

  // PUML actions
  $('#btn-edit-puml')?.addEventListener('click', togglePumlEdit);
  $('#btn-copy-puml')?.addEventListener('click', () => copyToClipboard(getPumlCode()));
  $('#btn-render')?.addEventListener('click', handleReRender);

  // Diagram actions
  $('#btn-download-png')?.addEventListener('click', () => handleDownload('png'));
  $('#btn-download-svg')?.addEventListener('click', () => handleDownload('svg'));
  $('#btn-iterate')?.addEventListener('click', handleIterate);
  $('#btn-new')?.addEventListener('click', handleNew);
  $('#btn-retry')?.addEventListener('click', handleGenerate);

  // History
  $('#btn-clear-history')?.addEventListener('click', () => {
    historyClear();
    showToast('History cleared', 'info', 2000);
  });

  // Image zoom
  $('#diagram-image')?.addEventListener('click', () => {
    const modal = $('#zoom-modal');
    const zoomImg = $('#zoom-image');
    if (modal && zoomImg && currentImageUri) {
      zoomImg.src = currentImageUri;
      modal.classList.remove('hidden');
    }
  });

  $('#zoom-modal')?.addEventListener('click', () => {
    $('#zoom-modal')?.classList.add('hidden');
  });

  // Theme toggle
  $('#btn-theme')?.addEventListener('click', toggleTheme);
  $('#btn-theme-mobile')?.addEventListener('click', toggleTheme);

  // Mobile menu toggle
  $('#btn-mobile-menu')?.addEventListener('click', () => {
    const menu = $('#mobile-menu');
    if (menu) menu.classList.toggle('hidden');
  });

  // Close mobile menu on link click
  $$('#mobile-menu a').forEach(link => {
    link.addEventListener('click', () => {
      $('#mobile-menu')?.classList.add('hidden');
    });
  });
}

/**
 * Navbar — add background on scroll.
 */
function initNavbar() {
  const navbar = $('#navbar');
  if (!navbar) return;

  const onScroll = () => {
    if (window.scrollY > 40) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  };

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

/**
 * Scroll reveal — animate sections into view.
 */
function initScrollReveal() {
  const sections = $$('#features, #how-it-works, #testimonials, #blog, #gallery');
  if (!sections.length) return;

  sections.forEach(s => s.classList.add('reveal'));

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  sections.forEach(s => observer.observe(s));
}

/**
 * Main generate flow: prompt -> v2 pipeline (Gemini IR -> code generator -> render).
 * V2 returns server-rendered images for PlantUML/D2, or Excalidraw JSON for spatial diagrams.
 */
async function handleGenerate() {
  const input = $('#prompt-input');
  const prompt = input?.value?.trim();

  if (!prompt) {
    showToast('Please describe an architecture to generate', 'error', 3000);
    input?.focus();
    return;
  }

  if (isGenerating) return;
  isGenerating = true;
  currentPrompt = prompt;

  // After 10s still generating, hint that AI is working
  const progressHint = setTimeout(() => {
    if (isGenerating) setLoadingText('AI is analyzing your prompt...');
  }, 10000);

  try {
    setGenerateLoading(true);
    showPanel('loading');
    setLoadingText('Generating diagram...');

    const result = await apiGenerate(prompt);
    currentRenderer = result.renderer || 'plantuml';

    // Excalidraw track — redirect to draw editor
    if (currentRenderer === 'excalidraw' && result.excalidraw_data) {
      setLoadingText('Opening in diagram editor...');
      try {
        // Create a drawing from the Excalidraw data
        const drawing = await fetch(`${API_BASE}/api/drawings`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: result.category.replace(/_/g, ' ') + ' diagram',
            data: result.excalidraw_data,
          }),
          credentials: 'include',
        }).then(r => r.json());

        window.location.href = `/draw/edit/${drawing.share_id || drawing.id}`;
      } catch (drawErr) {
        // Fallback: store in localStorage and open draw app
        localStorage.setItem('smi_excalidraw_import', JSON.stringify(result.excalidraw_data));
        window.location.href = '/draw/';
      }
      return;
    }

    // Graph track (PlantUML or D2) — image already rendered server-side
    currentCode = result.code || '';
    currentPuml = currentCode;
    currentImageUri = result.image || '';
    showPumlCode(currentCode);

    // Update code panel label
    const codeLabel = $('#puml-label');
    if (codeLabel) {
      const labels = { plantuml: 'PlantUML Code', d2: 'D2 Code', mermaid: 'Mermaid Code' };
      codeLabel.textContent = labels[currentRenderer] || 'Diagram Code';
    }

    // Show result
    showDiagram(currentImageUri);
    showToast('Diagram generated successfully', 'success', 2000);
    $('#btn-retry')?.classList.remove('hidden');

    // Nudge for feedback after 3rd generation (once only, logged-in users)
    if (window.currentUser && !localStorage.getItem('smi_feedback_nudged')) {
      const count = parseInt(localStorage.getItem('smi_gen_count') || '0') + 1;
      localStorage.setItem('smi_gen_count', String(count));
      if (count >= 3) {
        localStorage.setItem('smi_feedback_nudged', '1');
        setTimeout(() => showFeedbackNudge(), 2000);
      }
    }

    // Add to history
    historyAdd({
      prompt: currentPrompt,
      puml: currentCode,
      renderer: currentRenderer,
      imageDataUri: currentImageUri,
    });

  } catch (err) {
    if (err.rateLimited) {
      if (!err.authenticated) {
        showRateLimitLogin(err.limit, currentImageUri || null);
      } else {
        showUpgradePrompt(err.limit, currentImageUri || null);
      }
    } else {
      showError(
        'Couldn\'t render this one',
        err.message || 'Try simplifying your prompt or breaking the architecture into smaller parts.',
        currentImageUri || null
      );
    }
    showToast(err.message || 'Generation failed', 'error', 4000);
  } finally {
    clearTimeout(progressHint);
    setGenerateLoading(false);
    isGenerating = false;
  }
}

/**
 * Detect renderer from code content (fallback when currentRenderer may be stale).
 */
function detectRenderer(code) {
  const trimmed = code.trim();
  if (trimmed.startsWith('@startuml')) return 'plantuml';
  // D2 detection: look for D2-specific patterns
  if (trimmed.includes('shape: sequence_diagram') || trimmed.includes('shape: sql_table') ||
      trimmed.includes('shape: class') || trimmed.includes('shape: cylinder') ||
      /^\w+\s*:\s*"/.test(trimmed) || /^\w+\s*->\s*\w+/.test(trimmed)) {
    return 'd2';
  }
  return currentRenderer || 'plantuml';
}

/**
 * Re-render with edited diagram code (skips AI).
 */
async function handleReRender() {
  const code = getPumlCode();
  if (!code.trim()) {
    showToast('No diagram code to render', 'error', 3000);
    return;
  }

  if (isGenerating) return;
  isGenerating = true;

  try {
    showPanel('loading');
    setLoadingText('Rendering diagram...');

    // Auto-detect renderer from code content
    currentRenderer = detectRenderer(code);

    let result;
    if (currentRenderer === 'd2') {
      result = await apiRenderD2(code, 'svg');
    } else {
      result = await apiRender(code, 'svg');
    }
    currentCode = code;
    currentPuml = code;
    currentImageUri = result.image;

    showDiagram(currentImageUri);
    showToast('Diagram re-rendered', 'success', 2000);

    historyAdd({
      prompt: currentPrompt || 'Manual edit',
      puml: currentCode,
      renderer: currentRenderer,
      imageDataUri: currentImageUri,
    });

  } catch (err) {
    showError('Oops! That\'s a tricky one.', err.message || 'The render hit a snag — try generating again.', currentImageUri || null);
    showToast(err.message || 'Render failed', 'error', 4000);
  } finally {
    isGenerating = false;
  }
}

/**
 * Iterate — focus prompt input with previous prompt.
 */
function handleIterate() {
  const input = $('#prompt-input');
  if (input) {
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  }
  // Scroll to generator section
  document.getElementById('generator')?.scrollIntoView({ behavior: 'smooth' });
  showToast('Edit your prompt and generate again', 'info', 2000);
}

/**
 * New diagram — clear everything.
 */
function handleNew() {
  const input = $('#prompt-input');
  if (input) input.value = '';
  currentPuml = '';
  currentCode = '';
  currentRenderer = 'plantuml';
  currentImageUri = '';
  currentPrompt = '';
  hidePumlCode();
  showPanel('empty');
  input?.focus();
}

/**
 * Download the current diagram.
 * SVG: use the already-rendered data URI directly.
 * PNG: request a fresh PNG render from the backend (currentImageUri is always SVG).
 */
async function handleDownload(format) {
  if (!currentImageUri || !currentCode) {
    showToast('No diagram to download', 'error', 2000);
    return;
  }

  const timestamp = new Date().toISOString().slice(0, 10);
  const filename = `sketchmyinfra-${timestamp}.${format}`;

  if (format === 'png') {
    showToast('Preparing PNG…', 'info', 2000);
    try {
      let pngUri;
      if (currentRenderer === 'd2') {
        const result = await apiRenderD2(currentCode, 'png');
        pngUri = result.image;
      } else {
        const result = await apiRender(currentCode, 'png');
        pngUri = result.image;
      }
      downloadDataUri(pngUri, filename);
      showToast(`Downloaded ${filename}`, 'success', 2000);
    } catch (err) {
      showToast('PNG export failed — try SVG instead', 'error', 3000);
    }
    return;
  }

  downloadDataUri(currentImageUri, filename);
  showToast(`Downloaded ${filename}`, 'success', 2000);
}

/**
 * Theme — initialize from localStorage or system preference.
 */
function initTheme() {
  const stored = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = stored ? stored === 'dark' : prefersDark;

  document.documentElement.classList.toggle('dark', isDark);
}

/**
 * Toggle between light and dark theme.
 */
function toggleTheme() {
  const html = document.documentElement;

  // Enable smooth transition for all elements
  html.classList.add('transitioning');
  setTimeout(() => html.classList.remove('transitioning'), 350);

  const isDark = html.classList.toggle('dark');
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
}
