const navigationLinks = [...document.querySelectorAll('.nav-link')];
// Only local anchors participate; archive links can point back to the homepage.
const localNavigation = navigationLinks.filter(link => link.pathname === window.location.pathname && link.hash && document.getElementById(link.hash.slice(1)));
const pageNavigation = navigationLinks.find(link => link.hasAttribute('data-current-page'));
const sections = localNavigation.map(link => document.getElementById(link.hash.slice(1)));
const sidebar = document.querySelector('.sidebar');
const masthead = document.querySelector('.page-header');
const hero = document.querySelector('.hero');
const contentSheet = document.querySelector('.content-sheet');
const coverEdge = document.querySelector('.cover-edge');
const mobileLayout = window.matchMedia('(max-width: 767px)');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

function updateLayout() {
  const navigationHeight = mobileLayout.matches ? sidebar.getBoundingClientRect().height : 0;
  const mastheadHeight = masthead?.getBoundingClientRect().height ?? 0;
  const heroHeight = hero?.getBoundingClientRect().height ?? 0;
  const headerBottom = navigationHeight + (mobileLayout.matches ? 0 : mastheadHeight);
  // On short viewports, reveal the full cover before holding it in place.
  const heroTop = Math.min(headerBottom, window.innerHeight - heroHeight);
  const root = document.documentElement.style;
  root.setProperty('--navigation-height', `${navigationHeight}px`);
  root.setProperty('--masthead-height', `${mastheadHeight}px`);
  root.setProperty('--hero-sticky-top', `${heroTop}px`);
  updateActiveSection();
}

function updateActiveSection() {
  if (!sections.length || document.documentElement.classList.contains('viewer-open')) return;
  const headerBottom = (mobileLayout.matches ? sidebar : masthead)?.getBoundingClientRect().bottom ?? 0;
  const offset = headerBottom + (coverEdge?.offsetHeight ?? 0) + 48;
  // Covered content must not capture keyboard focus beneath the project layer.
  if (hero && contentSheet) hero.inert = !reducedMotion.matches && contentSheet.getBoundingClientRect().top <= headerBottom + 1;
  let currentId = pageNavigation ? null : sections[0].id;
  for (const section of sections) {
    if (section.getBoundingClientRect().top <= offset) currentId = section.id;
  }
  if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 4) {
    currentId = sections.at(-1).id;
  }
  for (const link of navigationLinks) {
    const active = currentId ? localNavigation.includes(link) && link.hash === `#${currentId}` : link === pageNavigation;
    link.classList.toggle('is-active', active);
    if (active) link.setAttribute('aria-current', currentId ? 'location' : 'page');
    else link.removeAttribute('aria-current');
  }
}

let scheduled = false;
function scheduleUpdate() {
  if (scheduled) return;
  scheduled = true;
  requestAnimationFrame(() => {
    updateActiveSection();
    scheduled = false;
  });
}
window.addEventListener('scroll', scheduleUpdate, { passive: true });
window.addEventListener('resize', updateLayout);
reducedMotion.addEventListener('change', updateLayout);
const layoutObserver = new ResizeObserver(updateLayout);
[sidebar, masthead, hero].filter(Boolean).forEach(element => layoutObserver.observe(element));
updateLayout();
