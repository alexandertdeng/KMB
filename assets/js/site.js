(function () {
  // ---- Mobile menu + dropdowns ----
  var btn = document.querySelector('.kmb-menu-btn');
  var nav = document.getElementById('kmb-nav');
  if (btn && nav) {
    btn.addEventListener('click', function () {
      var open = btn.getAttribute('aria-expanded') !== 'true';
      btn.setAttribute('aria-expanded', open);
      nav.classList.toggle('is-open', open);
    });
  }
  var subs = document.querySelectorAll('.kmb-nav .has-sub');
  function closeAll(except) {
    subs.forEach(function (li) {
      if (li === except) return;
      li.classList.remove('is-open');
      li.querySelector('.kmb-nav-link').setAttribute('aria-expanded', 'false');
    });
  }
  subs.forEach(function (li) {
    var trigger = li.querySelector('.kmb-nav-link');
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = !li.classList.contains('is-open');
      closeAll(li);
      li.classList.toggle('is-open', open);
      trigger.setAttribute('aria-expanded', open);
    });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.kmb-nav')) closeAll();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAll();
  });

  // ---- Floating donate button ----
  var fab = document.querySelector('.kmb-donate-fab');
  if (fab) {
    var toggle = function () { fab.classList.toggle('kmb-show', window.scrollY > 520); };
    window.addEventListener('scroll', toggle, { passive: true });
    toggle();
  }

  // ---- Product gallery thumbnails ----
  document.querySelectorAll('[data-gallery]').forEach(function (g) {
    var main = g.querySelector('[data-gallery-main]');
    g.querySelectorAll('.kmb-product-thumbs button').forEach(function (b) {
      b.addEventListener('click', function () {
        main.src = b.getAttribute('data-src');
        g.querySelectorAll('.kmb-product-thumbs button').forEach(function (x) { x.removeAttribute('aria-current'); });
        b.setAttribute('aria-current', 'true');
      });
    });
  });

  // ---- Order by email: builds a pre-filled message from the chosen options ----
  document.querySelectorAll('[data-order]').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var lines = ['Product: ' + form.getAttribute('data-product')];
      form.querySelectorAll('select, input').forEach(function (f) { lines.push(f.name + ': ' + f.value); });
      var body = 'Hi Keep Me Breathing team,\n\nI would like to order:\n\n' + lines.join('\n') +
        '\n\nMy name:\nDelivery address:\n\nThank you!';
      window.location.href = 'mailto:' + form.getAttribute('data-email') +
        '?subject=' + encodeURIComponent('Shop order: ' + form.getAttribute('data-product')) +
        '&body=' + encodeURIComponent(body);
    });
  });

  // ---- Category filter chips (updates page) ----
  var chips = document.querySelectorAll('.kmb-chip');
  chips.forEach(function (chip) {
    chip.addEventListener('click', function () {
      var cat = chip.getAttribute('data-cat');
      chips.forEach(function (c) { c.setAttribute('aria-pressed', c === chip); });
      document.querySelectorAll('[data-cats]').forEach(function (t) {
        t.hidden = cat && ('|' + t.getAttribute('data-cats') + '|').indexOf('|' + cat + '|') === -1;
      });
    });
  });
})();
