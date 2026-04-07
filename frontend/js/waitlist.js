/**
 * SketchMyInfra — Waitlist landing page script.
 * Handles: theme toggle, navbar, scroll reveal, mobile menu, form submission.
 */

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initNavbar();
  initScrollReveal();
  initMobileMenu();
  initWaitlistForm();
});

// ===== Theme =====

function initTheme() {
  const stored = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = stored ? stored === 'dark' : prefersDark;
  document.documentElement.classList.toggle('dark', isDark);

  document.getElementById('btn-theme')?.addEventListener('click', toggleTheme);
  document.getElementById('btn-theme-mobile')?.addEventListener('click', toggleTheme);
}

function toggleTheme() {
  const html = document.documentElement;
  html.classList.add('transitioning');
  setTimeout(() => html.classList.remove('transitioning'), 350);

  const isDark = html.classList.toggle('dark');
  localStorage.setItem('theme', isDark ? 'dark' : 'light');
}

// ===== Navbar scroll =====

function initNavbar() {
  const navbar = document.getElementById('navbar');
  if (!navbar) return;

  const onScroll = () => {
    navbar.classList.toggle('scrolled', window.scrollY > 40);
  };

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

// ===== Scroll reveal =====

function initScrollReveal() {
  const sections = document.querySelectorAll('#features, #how-it-works, #testimonials, #generator');
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

// ===== Mobile menu =====

function initMobileMenu() {
  document.getElementById('btn-mobile-menu')?.addEventListener('click', () => {
    document.getElementById('mobile-menu')?.classList.toggle('hidden');
  });

  document.querySelectorAll('#mobile-menu a').forEach(link => {
    link.addEventListener('click', () => {
      document.getElementById('mobile-menu')?.classList.add('hidden');
    });
  });
}

// ===== Waitlist form =====

function initWaitlistForm() {
  const form = document.getElementById('waitlist-form');
  const success = document.getElementById('waitlist-success');
  if (!form || !success) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = form.querySelector('input[type="email"]');
    const button = form.querySelector('button[type="submit"]');
    if (!email?.value) return;

    // Show loading state
    const originalText = button.textContent;
    button.textContent = 'Joining...';
    button.disabled = true;

    try {
      const response = await fetch(form.action, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({
          email: email.value,
          _subject: 'New SketchMyInfra Beta Signup'
        })
      });

      if (response.ok) {
        form.classList.add('hidden');
        success.classList.remove('hidden');
      } else {
        button.textContent = 'Try again';
        button.disabled = false;
        setTimeout(() => { button.textContent = originalText; }, 2000);
      }
    } catch {
      // If Formspree isn't configured yet, show success anyway for demo
      form.classList.add('hidden');
      success.classList.remove('hidden');
    }
  });
}
