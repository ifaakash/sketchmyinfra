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
// Graph IR of the diagram on screen, for "Open in Editor". The API only sends
// it to Pro users; currentEditable says whether the diagram could be edited
// at all, so free users still see the button (and the upsell). Both reset
// whenever the shown diagram didn't come straight from a generation.
let currentIr = null;
let currentGenerationId = null;
let currentEditable = false;
// Generation row behind the diagram on screen, IR or not: what the rating,
// download tracking and sign-in claim refer to. Null once the diagram on
// screen isn't the generated one (hand-edited code, history, New).
let currentDiagramGenerationId = null;

// Marketing sections moved to /about/. URL fragments never reach the server,
// so old links like /#features can only be redirected here, client-side.
// hashchange covers fragment-only navigation, which doesn't reload the page.
const MOVED_SECTIONS = ['features', 'how-it-works', 'gallery', 'testimonials', 'blog'];
function redirectMovedSection() {
  if (MOVED_SECTIONS.includes(window.location.hash.slice(1))) {
    window.location.replace('/about/' + window.location.hash);
  }
}
redirectMovedSection();
window.addEventListener('hashchange', redirectMovedSection);

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  bindEvents();
  initNavbar();
  initScrollReveal();
  renderHistory();
  prefillPromptFromUrl();

  if (USE_MOCKS) {
    showToast('Running in mock mode (localhost)', 'info', 3000);
  }
});

// Shareable "try this prompt" links: /?prompt=... fills the input. It never
// generates on its own, so link previews and crawlers don't spend the quota.
const MAX_PROMPT_LENGTH = 2000; // matches GenerateRequest.prompt in the API
function prefillPromptFromUrl() {
  const prompt = new URLSearchParams(window.location.search).get('prompt')?.trim();
  const input = $('#prompt-input');
  if (!prompt || !input) return;
  input.value = prompt.slice(0, MAX_PROMPT_LENGTH);
  input.focus();
}

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
  $('#btn-open-editor')?.addEventListener('click', handleOpenEditor);
  bindProModal();
  bindSignInModal();
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
        }).then(r => {
          // Anonymous users get a 401 here; without this check share_id is
          // undefined and they land on /draw/edit/undefined
          if (!r.ok) throw new Error(`Drawing create failed: ${r.status}`);
          return r.json();
        });

        window.location.href = `/draw/edit/${drawing.share_id}`;
      } catch (drawErr) {
        // Fallback: hand the scene over via localStorage. Only /draw/new reads
        // it — /draw/ is the gallery.
        localStorage.setItem('smi_excalidraw_import', JSON.stringify(result.excalidraw_data));
        window.location.href = '/draw/new';
      }
      return;
    }

    // Graph track (PlantUML or D2) — image already rendered server-side
    currentCode = result.code || '';
    currentPuml = currentCode;
    currentImageUri = result.image || '';
    setEditableIr(result.ir, result.generation_id, result.editable);
    showPumlCode(currentCode);
    setCodeLabel(currentRenderer);

    // Show result
    showDiagram(currentImageUri);
    setDiagramGeneration(result.generation_id);
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
    // Hand-edited code has drifted from the IR, so the editor would open
    // the original diagram, not this one
    setEditableIr(null);
    setDiagramGeneration(null);

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
  setEditableIr(null);
  setDiagramGeneration(null);
  hidePumlCode();
  showPanel('empty');
  input?.focus();
}

function setCodeLabel(renderer) {
  const codeLabel = $('#puml-label');
  if (codeLabel) {
    const labels = { plantuml: 'PlantUML Code', d2: 'D2 Code', mermaid: 'Mermaid Code' };
    codeLabel.textContent = labels[renderer] || 'Diagram Code';
  }
}

/**
 * Track the generation behind the diagram on screen and offer the rating
 * for it. Pass null when the diagram on screen didn't come from it.
 */
function setDiagramGeneration(generationId, { askRating = true } = {}) {
  currentDiagramGenerationId = generationId || null;
  if (currentDiagramGenerationId && askRating) showRatingRow(currentDiagramGenerationId);
  else hideRatingRow();
}

/*
 * Keep the diagram across sign-in. OAuth is a full-page redirect, so the
 * diagram on screen is stashed when a login link is clicked (auth.js) and
 * claimed into the account when the page comes back signed in. The image
 * goes too so it shows without a re-render; it's dropped if storage is full.
 */
const PENDING_CLAIM_KEY = 'smi_pending_claim';

function stashPendingClaim() {
  if (window.currentUser || !currentDiagramGenerationId) return;
  const stash = {
    generation_id: currentDiagramGenerationId,
    renderer: currentRenderer,
    imageDataUri: currentImageUri,
  };
  try {
    localStorage.setItem(PENDING_CLAIM_KEY, JSON.stringify(stash));
  } catch {
    try {
      localStorage.setItem(PENDING_CLAIM_KEY, JSON.stringify({ ...stash, imageDataUri: null }));
    } catch { /* storage blocked: sign-in still works, the diagram just isn't carried over */ }
  }
}

async function claimPendingDiagram() {
  let stash = null;
  try {
    stash = JSON.parse(localStorage.getItem(PENDING_CLAIM_KEY));
    localStorage.removeItem(PENDING_CLAIM_KEY);
  } catch { /* unreadable stash: nothing to claim */ }
  if (!stash?.generation_id) return;

  let claim;
  try {
    claim = await apiClaimGeneration(stash.generation_id);
  } catch {
    return; // too old, other network or already someone else's: nothing to restore
  }
  // Don't replace a diagram they started on this page while the claim ran
  if (currentImageUri || isGenerating) return;

  let image = stash.imageDataUri;
  if (!image && claim.code) {
    try {
      showPanel('loading');
      setLoadingText('Restoring your diagram...');
      const result = claim.renderer === 'd2'
        ? await apiRenderD2(claim.code, 'svg')
        : await apiRender(claim.code, 'svg');
      image = result.image;
    } catch {
      showPanel('empty');
      return;
    }
  }
  if (!image) return;

  currentPrompt = claim.prompt;
  currentRenderer = claim.renderer;
  currentCode = claim.code || '';
  currentPuml = currentCode;
  currentImageUri = image;
  const input = $('#prompt-input');
  if (input) input.value = claim.prompt;
  showPumlCode(currentCode);
  setCodeLabel(currentRenderer);
  setEditableIr(claim.ir, claim.generation_id, claim.editable);
  showDiagram(image);
  // They already saw (and maybe answered) the rating before signing in
  setDiagramGeneration(claim.generation_id, { askRating: false });
  if (typeof loadHistoryFromAPI === 'function') loadHistoryFromAPI();

  showToast(
    claim.ir ? 'Saved to your account. Open in Editor is unlocked.' : 'Saved to your account.',
    'success',
    4000,
  );
}

/**
 * Track the IR behind the diagram on screen; "Open in Editor" shows for any
 * editable (graph-track) generation, IR or not.
 */
function setEditableIr(ir, generationId = null, editable = !!ir) {
  currentIr = ir || null;
  currentGenerationId = ir ? generationId : null;
  currentEditable = !!editable;
  $('#btn-open-editor')?.classList.toggle('hidden', !currentEditable);
}

/**
 * Open the current diagram in the draw-app as editable shapes. The IR goes
 * over via localStorage (same origin); /draw/new imports it. For PlantUML the
 * rendered SVG goes too, so the editor can copy its layout and icons and open
 * on the picture the user is looking at. A new tab keeps this result open.
 */
function handleOpenEditor() {
  if (!currentEditable) return;
  // Pro feature, enforced by the API: free users get no IR. Signed-out users
  // are offered sign-in (new accounts start on a Pro trial); signed-in users
  // without Pro get the waitlist upsell.
  if (!isProUser()) {
    if (window.currentUser) showProModal();
    else showSignInModal();
    return;
  }
  // Pro, but this diagram was generated before they signed in
  if (!currentIr) {
    showToast('Generate the diagram again to open it in the editor', 'info', 4000);
    return;
  }
  const payload = {
    ir: currentIr,
    generation_id: currentGenerationId,
    title: currentIr.title || currentIr.graph?.title || currentPrompt.slice(0, 60) || 'Generated Diagram',
    svg: currentRenderer === 'plantuml' ? currentImageUri : null,
  };
  try {
    localStorage.setItem('smi_ir_import', JSON.stringify(payload));
  } catch (err) {
    // Likely over quota: the SVG (with embedded icons) is the big part.
    // Without it the editor still opens, just auto-laid-out.
    try {
      localStorage.setItem('smi_ir_import', JSON.stringify({ ...payload, svg: null }));
    } catch (err2) {
      showToast('Could not open the editor (browser storage is full or blocked)', 'error', 4000);
      return;
    }
  }
  window.open('/draw/new', '_blank');
}

/**
 * Download the current diagram.
 * SVG: use the already-rendered data URI directly.
 * PNG: convert SVG to PNG client-side via Canvas (works for all renderers).
 */
async function handleDownload(format) {
  if (!currentImageUri) {
    showToast('No diagram to download', 'error', 2000);
    return;
  }

  const timestamp = new Date().toISOString().slice(0, 10);
  const filename = `sketchmyinfra-${timestamp}.${format}`;

  if (format === 'png') {
    showToast('Preparing PNG…', 'info', 2000);
    try {
      const pngUri = await svgToPngDataUri(currentImageUri);
      downloadDataUri(pngUri, filename);
      showToast(`Downloaded ${filename}`, 'success', 2000);
      afterDownload();
    } catch (err) {
      showToast('PNG export failed — try SVG instead', 'error', 3000);
    }
    return;
  }

  downloadDataUri(currentImageUri, filename);
  showToast(`Downloaded ${filename}`, 'success', 2000);
  afterDownload();
}

/**
 * They got what they came for: count it, and offer to keep the diagram.
 */
function afterDownload() {
  // Only a fresh generation can be claimed, so only it gets the "keep it" offer
  if (!currentDiagramGenerationId) return;
  apiMarkDownloaded(currentDiagramGenerationId);
  setTimeout(showSaveNudge, 800);
}

/**
 * Theme — initialize from localStorage, defaulting to light.
 */
function initTheme() {
  // Light is the default; dark only when the user has picked it with the toggle
  const isDark = localStorage.getItem('theme') === 'dark';

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
