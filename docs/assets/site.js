(function () {
  const html = document.documentElement;
  const THEME_KEY = 'ef-theme';

  function applyTheme(t) {
    html.setAttribute('data-theme', t);
    localStorage.setItem(THEME_KEY, t);
    document.querySelectorAll('#themeBtn, .theme-btn').forEach(function (btn) {
      btn.textContent = t === 'dark' ? '☀ Light' : '🌙 Dark';
    });
  }

  applyTheme(localStorage.getItem(THEME_KEY) || 'dark');

  document.querySelectorAll('#themeBtn, .theme-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      applyTheme(html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
    });
  });

  // Guide pages use #sidebar (a table-of-contents panel); every other page
  // uses #mobileDrawer (a copy of the header nav) for the same off-canvas
  // mobile menu pattern.
  var sidebar = document.getElementById('sidebar') || document.getElementById('mobileDrawer');
  var overlay = document.getElementById('sidebarOverlay') || document.getElementById('navOverlay');
  var menuBtn = document.getElementById('menuBtn');

  function openSidebar() {
    if (sidebar) sidebar.classList.add('open');
    if (overlay) overlay.classList.add('visible');
  }
  function closeSidebar() {
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('visible');
  }

  if (menuBtn) menuBtn.addEventListener('click', openSidebar);
  if (overlay) overlay.addEventListener('click', closeSidebar);

  if (sidebar) {
    sidebar.querySelectorAll('.sidebar-link').forEach(function (link) {
      link.addEventListener('click', function () {
        if (window.innerWidth < 900) closeSidebar();
      });
    });
  }

  var spySections = document.querySelectorAll('[data-doc-section]');
  var spyLinks = document.querySelectorAll('.sidebar-link[href^="#"]');
  if (spySections.length && spyLinks.length) {
    var obs = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          if (e.isIntersecting) {
            var id = e.target.id;
            spyLinks.forEach(function (l) {
              l.classList.toggle('active', l.getAttribute('href') === '#' + id);
            });
          }
        });
      },
      { rootMargin: '-12% 0px -65% 0px' }
    );
    spySections.forEach(function (s) {
      obs.observe(s);
    });
  }
})();
