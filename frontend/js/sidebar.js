/** Responsive navigation shell. Business/data modules are independent of this UI. */
const sidebar = document.getElementById('app-sidebar');
const toggle = document.getElementById('sidebar-toggle');
const close = document.getElementById('sidebar-close');
const backdrop = document.getElementById('sidebar-backdrop');
const mobile = window.matchMedia('(max-width: 1023px)');

if (sidebar && toggle && close && backdrop) {
  function setOpen(open, restoreFocus = true) {
    const isOpen = mobile.matches && open;
    document.body.classList.toggle('sidebar-open', isOpen);
    toggle.setAttribute('aria-expanded', String(isOpen));
    backdrop.hidden = !isOpen;
    // Inert prevents keyboard access to navigation while its drawer is hidden.
    sidebar.inert = mobile.matches && !isOpen;
    if (isOpen) close.focus();
    else if (restoreFocus && mobile.matches) toggle.focus();
  }
  toggle.addEventListener('click', () => setOpen(!document.body.classList.contains('sidebar-open')));
  close.addEventListener('click', () => setOpen(false));
  backdrop.addEventListener('click', () => setOpen(false));
  sidebar.querySelectorAll('a').forEach(link => link.addEventListener('click', () => {
    if (mobile.matches) setOpen(false, false);
  }));
  document.addEventListener('keydown', event => {
    if (!mobile.matches || !document.body.classList.contains('sidebar-open')) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      setOpen(false);
    } else if (event.key === 'Tab') {
      const focusable = [...sidebar.querySelectorAll('a[href], button:not([disabled])')];
      const first = focusable[0];
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault(); first.focus();
      }
    }
  });
  mobile.addEventListener('change', () => setOpen(false, false));
  setOpen(false, false);
}
