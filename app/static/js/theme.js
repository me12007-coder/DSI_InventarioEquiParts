/* =========================================================
   EQUI-PARTS S&S — Selector de tema Claro / Oscuro
   La preferencia se guarda localmente en el navegador.
   ========================================================= */
(function () {
  const STORAGE_KEY = 'equiparts-theme';
  const root = document.documentElement;

  function normalizeTheme(value) {
    return value === 'dark' ? 'dark' : 'light';
  }

  function savedTheme() {
    try {
      return normalizeTheme(localStorage.getItem(STORAGE_KEY));
    } catch (_) {
      return 'light';
    }
  }

  function applyTheme(theme, persist) {
    const current = normalizeTheme(theme);
    root.dataset.theme = current;
    root.style.colorScheme = current;

    if (persist) {
      try { localStorage.setItem(STORAGE_KEY, current); } catch (_) {}
    }

    document.querySelectorAll('[data-theme-switcher]').forEach((picker) => {
      picker.dataset.currentTheme = current;

      const triggerIcon = picker.querySelector('[data-theme-trigger-icon]');
      const triggerLabel = picker.querySelector('[data-theme-trigger-label]');
      if (triggerIcon) {
        triggerIcon.className = current === 'dark'
          ? 'bi bi-moon-stars-fill'
          : 'bi bi-sun-fill';
      }
      if (triggerLabel) triggerLabel.textContent = current === 'dark' ? 'Oscuro' : 'Claro';

      picker.querySelectorAll('[data-set-style]').forEach(option => option.addEventListener('click', () => applyStyle(option.dataset.setStyle, root.dataset.accent, true)));
      picker.querySelectorAll('[data-set-accent]').forEach(option => option.addEventListener('click', () => applyStyle(root.dataset.uiStyle, option.dataset.setAccent, true)));
      picker.querySelectorAll('[data-set-theme]').forEach((option) => {
        const selected = option.dataset.setTheme === current;
        option.classList.toggle('active', selected);
        option.setAttribute('aria-pressed', selected ? 'true' : 'false');
        const check = option.querySelector('.theme-option-check');
        if (check) check.classList.toggle('visible', selected);
      });
    });

    // Mantiene legibles los gráficos Chart.js al cambiar de tema.
    if (window.Chart) {
      const dark = current === 'dark';
      Chart.defaults.color = dark ? '#aeb9c0' : '#66717d';
      Chart.defaults.borderColor = dark ? '#35424c' : '#e2e5e9';
      try {
        const instances = Chart.instances ? Object.values(Chart.instances) : [];
        instances.forEach((chart) => chart && chart.update('none'));
      } catch (_) {}
    }

    window.dispatchEvent(new CustomEvent('equiparts:themechange', { detail: { theme: current } }));
  }

  const accents = ['blue','green','lilac','pink','peach'];
  function applyStyle(style, accent, persist) {
    style = style === 'expressive' ? 'expressive' : 'classic';
    accent = accents.includes(accent) ? accent : 'blue';
    root.dataset.uiStyle = style;
    root.dataset.accent = accent;
    if (persist) { try { localStorage.setItem('equiparts-style', style); localStorage.setItem('equiparts-accent', accent); } catch (_) {} }
    document.querySelectorAll('[data-set-style]').forEach(b => {b.classList.toggle('active', b.dataset.setStyle === style); b.setAttribute('aria-pressed', String(b.dataset.setStyle === style));});
    document.querySelectorAll('[data-set-accent]').forEach(b => {b.classList.toggle('active', b.dataset.setAccent === accent); b.setAttribute('aria-pressed', String(b.dataset.setAccent === accent));});
  }
  const loadPref = key => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  applyStyle(loadPref('equiparts-style'), loadPref('equiparts-accent'), false);

  // Se ejecuta antes de pintar el body para evitar el destello del tema claro.
  applyTheme(savedTheme(), false);

  function closeAll(except) {
    document.querySelectorAll('[data-theme-switcher].open').forEach((picker) => {
      if (picker !== except) {
        picker.classList.remove('open');
        const trigger = picker.querySelector('[data-theme-trigger]');
        if (trigger) trigger.setAttribute('aria-expanded', 'false');
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    applyTheme(savedTheme(), false);
    applyStyle(loadPref('equiparts-style'), loadPref('equiparts-accent'), false);
    document.querySelectorAll('[data-theme-switcher]').forEach((picker) => {
      const trigger = picker.querySelector('[data-theme-trigger]');
      if (!trigger) return;

      trigger.addEventListener('click', function (event) {
        event.stopPropagation();
        const willOpen = !picker.classList.contains('open');
        closeAll(picker);
        picker.classList.toggle('open', willOpen);
        trigger.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
      });

      picker.querySelectorAll('[data-set-theme]').forEach((option) => {
        option.addEventListener('click', function () {
          applyTheme(option.dataset.setTheme, true);
          picker.classList.remove('open');
          trigger.setAttribute('aria-expanded', 'false');
        });
      });
    });

    document.addEventListener('click', function () { closeAll(); });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') closeAll();
    });
  });

  window.EquiPartsTheme = { apply: (theme) => applyTheme(theme, true), current: () => root.dataset.theme || 'light' };
})();
