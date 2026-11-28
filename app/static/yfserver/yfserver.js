/* yfserver design system – Farbmodus (auto / hell / dunkel).
   Im <head> ohne defer einbinden, damit die Seite nicht kurz im falschen Modus aufblitzt.
   Umschalter: <div class="yf-seg" data-yf-theme><button data-mode="auto">…</button>…</div> */
(() => {
  const KEY = 'yf-theme', root = document.documentElement;
  const read = () => { try { return localStorage.getItem(KEY) || 'auto'; } catch { return 'auto'; } };
  function apply(mode) {
    if (mode === 'auto') root.removeAttribute('data-theme'); else root.dataset.theme = mode;
    document.querySelectorAll('[data-yf-theme] [data-mode]').forEach(b => b.setAttribute('aria-pressed', b.dataset.mode === mode));
  }
  apply(read());
  addEventListener('DOMContentLoaded', () => {
    apply(read());
    document.querySelectorAll('[data-yf-theme] [data-mode]').forEach(b => b.addEventListener('click', () => {
      try { localStorage.setItem(KEY, b.dataset.mode); } catch {}
      apply(b.dataset.mode);
    }));
  });
})();
