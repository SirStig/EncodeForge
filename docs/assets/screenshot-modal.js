(function () {
  var triggers = document.querySelectorAll('[data-modal-target]');
  if (!triggers.length) return;

  function openModal(id) {
    var m = document.getElementById(id);
    if (m) {
      m.classList.add('open');
      document.body.style.overflow = 'hidden';
    }
  }

  function closeModal(id) {
    var m = document.getElementById(id);
    if (m) {
      m.classList.remove('open');
      document.body.style.overflow = '';
    }
  }

  triggers.forEach(function (el) {
    el.addEventListener('click', function () {
      openModal(el.getAttribute('data-modal-target'));
    });
  });

  document.querySelectorAll('.modal').forEach(function (m) {
    m.addEventListener('click', function () {
      closeModal(m.id);
    });
  });

  document.querySelectorAll('img[data-hide-on-error]').forEach(function (img) {
    img.addEventListener('error', function () {
      var item = img.closest('.screenshot-item');
      if (item) item.style.display = 'none';
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal.open').forEach(function (m) {
        m.classList.remove('open');
        document.body.style.overflow = '';
      });
    }
  });
})();
