/**
 * LENIS SMOOTH-SCROLL CONTROLLER
 */
import Lenis from 'lenis';

export function initLenis() {
  window.scrollTo(0, 0);

  const lenis = new Lenis({
    smoothWheel: true,
    duration: 1.2,
    easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t))
  });

  let scrollEnabled = true;

  function raf(time) {
    if (scrollEnabled) {
      lenis.raf(time);
    }
    requestAnimationFrame(raf);
  }
  requestAnimationFrame(raf);

  function stopScroll() {
    scrollEnabled = false;
    lenis.stop();
    document.documentElement.style.position = 'relative';
    document.documentElement.style.overflow = 'hidden';
    document.documentElement.style.height = '100%';
  }

  function startScroll() {
    scrollEnabled = true;
    lenis.start();
    document.documentElement.style.removeProperty('position');
    document.documentElement.style.removeProperty('overflow');
    document.documentElement.style.removeProperty('height');
  }

  function scrollToId(id) {
    const el = document.getElementById(id);
    if (!el) return;
    scrollEnabled = false;
    setTimeout(() => {
      const top = el.getBoundingClientRect().top + window.pageYOffset;
      window.scrollTo({ top, behavior: 'smooth' });
      setTimeout(() => {
        scrollEnabled = true;
      }, 300);
    }, 50);
  }

  return { lenis, stopScroll, startScroll, scrollToId };
}
