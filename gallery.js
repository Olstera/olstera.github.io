const viewer = document.querySelector('.image-viewer');

// Keep the direct image links usable if modal dialogs are unavailable.
if (viewer && typeof viewer.showModal === 'function') {
  const image = viewer.querySelector('.viewer-image');
  const scrollArea = viewer.querySelector('.viewer-scroll');
  const title = viewer.querySelector('#viewer-title');
  const zoom = viewer.querySelector('.viewer-zoom');
  const close = viewer.querySelector('.viewer-close');
  let trigger;
  let backgroundY = 0;
  let backgroundX = 0;
  let backdropPress = false;

  function resetZoom() {
    viewer.classList.remove('is-zoomed');
    zoom.textContent = 'Масштаб 100%';
    zoom.setAttribute('aria-pressed', 'false');
  }

  for (const link of document.querySelectorAll('[data-gallery]')) {
    link.setAttribute('aria-haspopup', 'dialog');
    link.addEventListener('click', event => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
      event.preventDefault();
      trigger = link;
      const original = link.querySelector('img');
      image.src = link.href;
      image.alt = original.alt;
      image.style.setProperty('--image-native-width', `${original.naturalWidth || original.width}px`);
      title.textContent = link.dataset.caption;
      resetZoom();
      backgroundY = window.scrollY;
      backgroundX = window.scrollX;
      // Fixed-body locking also prevents the page beneath from scrolling on touch devices.
      document.body.style.top = `-${backgroundY}px`;
      document.documentElement.classList.add('viewer-open');
      viewer.showModal();
      scrollArea.scrollTop = 0;
      scrollArea.scrollLeft = 0;
      close.focus({ preventScroll: true });
    });
  }

  zoom.addEventListener('click', () => {
    const enlarged = viewer.classList.toggle('is-zoomed');
    zoom.textContent = enlarged ? 'Вписать по\u00a0ширине' : 'Масштаб 100%';
    zoom.setAttribute('aria-pressed', String(enlarged));
    scrollArea.scrollTop = 0;
    scrollArea.scrollLeft = 0;
  });
  close.addEventListener('click', () => viewer.close());
  // Only a complete click outside the dialog closes it, never an image drag.
  function outside(event) {
    const rect = viewer.getBoundingClientRect();
    return event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
  }
  viewer.addEventListener('pointerdown', event => { backdropPress = outside(event); });
  viewer.addEventListener('click', event => {
    if (backdropPress && outside(event)) viewer.close();
    backdropPress = false;
  });
  viewer.addEventListener('close', () => {
    document.documentElement.classList.remove('viewer-open');
    document.body.style.top = '';
    // Override smooth scrolling so closing restores the exact reading position.
    const rootStyle = document.documentElement.style;
    const priorBehavior = rootStyle.scrollBehavior;
    rootStyle.scrollBehavior = 'auto';
    window.scrollTo(backgroundX, backgroundY);
    rootStyle.scrollBehavior = priorBehavior;
    trigger?.focus({ preventScroll: true });
    image.removeAttribute('src');
    resetZoom();
  });
}
