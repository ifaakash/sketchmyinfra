/**
 * Gallery — renders curated example diagrams from static images.
 */

const GALLERY_ITEMS = [
  {
    prompt: "AWS SSM Session Manager port forwarding — secure bastion-free access to private resources",
    img: "flows/ssm-port-forwarding.png",
  },
  {
    prompt: "AWS EventBridge event-driven architecture — routing events between services with rules and targets",
    img: "flows/eventbridge.png",
  },
  {
    prompt: "Dev and prod environment separation — isolated workloads sharing a single cluster",
    img: "flows/dev-and-prod.png",
  },
];

function initGallery() {
  const grid = document.getElementById('gallery-grid');
  if (!grid) return;
  GALLERY_ITEMS.forEach((item) => grid.appendChild(buildCard(item)));
}

function buildCard(item) {
  const card = document.createElement('div');
  card.className = 'gallery-card border border-gray-200 dark:border-gray-800 rounded-2xl overflow-hidden bg-white/5 dark:bg-white/[0.02]';

  card.innerHTML = `
    <div class="gallery-img-wrapper relative bg-gray-100 dark:bg-gray-900 cursor-zoom-in group" style="height:160px;"
         onclick="openLightbox('${escapeHtml(item.img)}', '${escapeHtml(item.prompt)}')">
      <img src="${escapeHtml(item.img)}"
           alt="${escapeHtml(item.prompt)}"
           class="w-full h-full object-contain p-3">
      <div class="absolute inset-0 hidden group-hover:flex items-center justify-center bg-black/20">
        <span class="bg-black/60 text-white text-xs px-2 py-1 rounded-md">Click to zoom</span>
      </div>
    </div>
    <div class="px-5 py-4 border-t border-gray-200 dark:border-gray-800">
      <p class="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
        <span class="font-mono text-brand-400 mr-1.5">&gt;</span>${escapeHtml(item.prompt)}
      </p>
    </div>
  `;
  return card;
}

function openLightbox(src, caption) {
  const lb = document.getElementById('gallery-lightbox');
  lb.querySelector('.lb-img').src = src;
  lb.querySelector('.lb-caption').textContent = caption;
  lb.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeLightbox() {
  document.getElementById('gallery-lightbox').classList.add('hidden');
  document.body.style.overflow = '';
}

function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/'/g, '&#39;').replace(/"/g, '&quot;');
}

document.addEventListener('DOMContentLoaded', initGallery);
