/**
 * SketchMyInfra — App entry point.
 * Wires events to API calls to UI updates.
 */

// Current state
let currentPuml = '';
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

  // Example chips
  $$('.example-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const prompt = chip.dataset.prompt;
      const input = $('#prompt-input');
      if (input) {
        input.value = prompt;
        input.focus();
      }
    });
  });

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
  const sections = $$('#features, #how-it-works, #testimonials');
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
 * Main generate flow: prompt -> PUML -> render -> display.
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

  try {
    // Phase 1: Generate PUML
    setGenerateLoading(true);
    showPanel('loading');
    setLoadingText('Generating PlantUML code...');

    const genResult = await apiGenerate(prompt, currentPuml || null);
    currentPuml = genResult.puml;
    showPumlCode(currentPuml);

    // Phase 2: Render diagram
    setLoadingText('Rendering diagram...');
    const renderResult = await apiRender(currentPuml, 'svg');
    currentImageUri = renderResult.image;

    // Show result
    showDiagram(currentImageUri);
    showToast('Diagram generated successfully', 'success', 2000);

    // Add to history
    historyAdd({
      prompt: currentPrompt,
      puml: currentPuml,
      imageDataUri: currentImageUri,
    });

  } catch (err) {
    showError('Generation Failed', err.message || 'Something went wrong. Please try again.');
    showToast(err.message || 'Generation failed', 'error', 4000);
  } finally {
    setGenerateLoading(false);
    isGenerating = false;
  }
}

/**
 * Re-render with edited PUML code (skips AI).
 */
async function handleReRender() {
  const puml = getPumlCode();
  if (!puml.trim()) {
    showToast('No PlantUML code to render', 'error', 3000);
    return;
  }

  if (isGenerating) return;
  isGenerating = true;

  try {
    showPanel('loading');
    setLoadingText('Rendering diagram...');

    const result = await apiRender(puml, 'svg');
    currentPuml = puml;
    currentImageUri = result.image;

    showDiagram(currentImageUri);
    showToast('Diagram re-rendered', 'success', 2000);

    historyAdd({
      prompt: currentPrompt || 'Manual PUML edit',
      puml: currentPuml,
      imageDataUri: currentImageUri,
    });

  } catch (err) {
    showError('Render Failed', err.message || 'Failed to render the diagram.');
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
  currentImageUri = '';
  currentPrompt = '';
  hidePumlCode();
  showPanel('empty');
  input?.focus();
}

/**
 * Download the current diagram.
 */
function handleDownload(format) {
  if (!currentImageUri) {
    showToast('No diagram to download', 'error', 2000);
    return;
  }

  const timestamp = new Date().toISOString().slice(0, 10);
  const filename = `sketchmyinfra-${timestamp}.${format === 'png' ? 'png' : 'svg'}`;

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
