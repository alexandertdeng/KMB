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

  // ---- Click-to-zoom images: <a data-zoom href="large.jpg"><img></a> ----
  var zoomLinks = document.querySelectorAll('a[data-zoom]');
  if (zoomLinks.length && window.HTMLDialogElement) {
    var zoom = document.createElement('dialog');
    zoom.className = 'kmb-zoom';
    zoom.innerHTML = '<button class="kmb-zoom-close" type="button" aria-label="Close">&times;</button><img alt="">';
    document.body.appendChild(zoom);
    var zoomImg = zoom.querySelector('img');
    zoomLinks.forEach(function (a) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        zoomImg.src = a.href;
        zoomImg.alt = (a.querySelector('img') || {}).alt || '';
        zoom.showModal();
      });
    });
    // Close on the button or a click outside the picture (Esc works natively)
    zoom.addEventListener('click', function (e) { if (e.target !== zoomImg) zoom.close(); });
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

  // ---- Newsletter: show the email fallback only if Klaviyo's form never loads ----
  document.querySelectorAll('.kmb-signup').forEach(function (s) {
    var form = s.querySelector('[class^="klaviyo-form-"]');
    var alt = s.querySelector('.kmb-signup-alt');
    if (!form || !alt) return;
    alt.hidden = true;
    setTimeout(function () { if (!form.children.length) alt.hidden = false; }, 6000);
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
