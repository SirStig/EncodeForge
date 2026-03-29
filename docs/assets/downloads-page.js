(function () {
  var cfg = window.EncodeForgeReleaseConfig;
  if (!cfg) return;

  var sel = document.getElementById('versionSelect');
  var leadEl = document.getElementById('downloadVersionLead');
  var grid = document.getElementById('downloadGrid');
  var statusEl = document.getElementById('downloadFetchStatus');
  if (!sel || !grid) return;

  function usesNewInstallerLayout(tag) {
    var t = (tag || '').replace(/^v/i, '');
    return /^0\.5\./.test(t);
  }

  function displayVersionFromTag(tag) {
    var v = String(tag || '')
      .replace(/^v/i, '')
      .trim();
    var alpha = v.match(/^(.*)-alpha-(\d+)$/i);
    if (alpha) return alpha[1] + ' Alpha ' + alpha[2];
    var beta = v.match(/^(.*)-beta-(\d+)$/i);
    if (beta) return beta[1] + ' Beta ' + beta[2];
    return v;
  }

  function parseTime(iso) {
    var n = Date.parse(iso || '');
    return isNaN(n) ? 0 : n;
  }

  function changelogHashForTag(tag) {
    return 'release-' + String(tag || '').replace(/^v/i, '').replace(/\./g, '-').toLowerCase();
  }

  function normalizeApiRelease(r) {
    return {
      tag_name: r.tag_name,
      name: r.name || r.tag_name,
      prerelease: !!r.prerelease,
      published_at: r.published_at || '',
      html_url: r.html_url || cfg.releaseIndexUrl,
      assets: (r.assets || []).map(function (a) {
        return { name: a.name };
      }),
      pending: false,
      _source: 'api',
    };
  }

  function normalizePreview(p) {
    return {
      tag_name: p.tag_name,
      name: p.name || p.tag_name,
      prerelease: !!p.prerelease,
      published_at: p.published_at || '',
      html_url:
        'https://github.com/' + cfg.owner + '/' + cfg.repo + '/releases/tag/' + encodeURIComponent(p.tag_name),
      assets: (p.plannedAssets || []).map(function (x) {
        return { name: typeof x === 'string' ? x : x.name };
      }),
      pending: !!p.pending,
      _source: 'preview',
    };
  }

  function mergeReleases(apiList, previews) {
    var byTag = {};
    (apiList || []).forEach(function (r) {
      byTag[r.tag_name] = normalizeApiRelease(r);
    });
    (previews || []).forEach(function (p) {
      if (byTag[p.tag_name]) return;
      byTag[p.tag_name] = normalizePreview(p);
    });
    return Object.keys(byTag)
      .map(function (k) {
        return byTag[k];
      })
      .sort(function (a, b) {
        return parseTime(b.published_at) - parseTime(a.published_at);
      });
  }

  function pickSlots(names) {
    var n = names.slice();
    function first(pred) {
      for (var i = 0; i < n.length; i++) {
        if (pred(n[i])) {
          var x = n[i];
          n.splice(i, 1);
          return x;
        }
      }
      return null;
    }
    var win =
      first(function (f) {
        return /windows.*\.exe$/i.test(f);
      }) ||
      first(function (f) {
        return /^EncodeForge\.exe$/i.test(f);
      }) ||
      first(function (f) {
        return /\.exe$/i.test(f);
      });
    var macArm =
      first(function (f) {
        return /macos-arm|apple-?silicon|arm64.*\.zip$/i.test(f);
      }) ||
      first(function (f) {
        return /\.zip$/i.test(f) && /mac/i.test(f);
      });
    var macIntel =
      first(function (f) {
        return /\.dmg$/i.test(f) && /(x64|intel|amd64)/i.test(f);
      }) || first(function (f) {
        return /\.dmg$/i.test(f) && !/arm64/i.test(f);
      });
    var deb = first(function (f) {
      return /\.deb$/i.test(f);
    });
    var rpm = first(function (f) {
      return /\.rpm$/i.test(f);
    });
    var appimage = first(function (f) {
      return /\.AppImage$/i.test(f);
    });
    return { win: win, macArm: macArm, macIntel: macIntel, deb: deb, rpm: rpm, appimage: appimage };
  }

  function linkRow(href, label, primary, pending) {
    var li = document.createElement('li');
    if (pending || !href) {
      var sp = document.createElement('span');
      sp.className = 'dl-btn dl-btn-soon';
      sp.textContent = label + (pending ? ' — coming soon' : '');
      li.appendChild(sp);
      return li;
    }
    var a = document.createElement('a');
    a.className = 'dl-btn' + (primary ? ' dl-btn-primary' : '');
    a.href = href;
    a.rel = 'noopener';
    a.textContent = label;
    li.appendChild(a);
    return li;
  }

  function column(title, items) {
    var col = document.createElement('div');
    col.className = 'download-column';
    var h = document.createElement('h2');
    h.className = 'download-os';
    h.textContent = title;
    col.appendChild(h);
    var ul = document.createElement('ul');
    ul.className = 'download-list';
    items.forEach(function (fn) {
      ul.appendChild(fn());
    });
    col.appendChild(ul);
    return col;
  }

  function renderRelease(rel) {
    grid.innerHTML = '';
    var tag = rel.tag_name;
    var pending = rel.pending;
    var names = rel.assets.map(function (a) {
      return a.name;
    });
    var slots = pickSlots(names);
    var line = usesNewInstallerLayout(tag);

    function url(file) {
      if (!file) return null;
      return cfg.downloadUrl(tag, file);
    }

    if (line) {
      grid.appendChild(
        column('macOS', [
          function () {
            return linkRow(
              url(slots.macArm),
              'Apple Silicon (.zip)',
              true,
              pending || !slots.macArm
            );
          },
          function () {
            return linkRow(null, 'Intel 64-bit (.zip)', false, true);
          },
        ])
      );
      grid.appendChild(
        column('Windows', [
          function () {
            return linkRow(url(slots.win), 'Executable (.exe)', true, pending || !slots.win);
          },
        ])
      );
      grid.appendChild(
        column('Linux', [
          function () {
            return linkRow(null, '.deb (Debian / Ubuntu)', false, true);
          },
          function () {
            return linkRow(null, '.rpm (Fedora / RHEL)', false, true);
          },
          function () {
            return linkRow(null, 'AppImage', false, true);
          },
        ])
      );
    } else {
      grid.appendChild(
        column('Windows', [
          function () {
            return linkRow(url(slots.win), slots.win ? 'Installer (.exe)' : 'Windows (.exe)', true, !slots.win);
          },
        ])
      );
      grid.appendChild(
        column('macOS', [
          function () {
            var f = slots.macArm || slots.macIntel;
            var lbl = f
              ? slots.macArm
                ? /dmg/i.test(f)
                  ? 'Apple Silicon (.dmg)'
                  : 'Apple Silicon (.zip)'
                : 'Intel (.dmg)'
              : 'No macOS asset for this release';
            return linkRow(url(f), lbl, !!f, !f);
          },
        ])
      );
      grid.appendChild(
        column('Linux', [
          function () {
            return linkRow(url(slots.deb), slots.deb ? 'Debian / Ubuntu (.deb)' : '.deb', !!slots.deb, !slots.deb);
          },
          function () {
            return linkRow(url(slots.rpm), slots.rpm ? 'Fedora / RHEL (.rpm)' : '.rpm', !!slots.rpm, !slots.rpm);
          },
          function () {
            return linkRow(url(slots.appimage), 'AppImage', !!slots.appimage, !slots.appimage);
          },
        ])
      );
    }

    if (leadEl) {
      leadEl.replaceChildren();
      var st = document.createElement('strong');
      st.textContent = displayVersionFromTag(tag);
      leadEl.appendChild(st);
      leadEl.appendChild(
        document.createTextNode(
          ' — ' +
            (pending
              ? 'downloads will go live here as soon as this version is published.'
              : 'choose a platform below; each button opens the file from GitHub.')
        )
      );
      leadEl.appendChild(document.createElement('br'));
      var cl = document.createElement('a');
      cl.href = 'changelog.html#' + changelogHashForTag(tag);
      cl.textContent = 'Changelog for this version';
      leadEl.appendChild(cl);
    }
  }

  var allReleases = [];

  function onSelect() {
    var tag = sel.value;
    var rel = allReleases.find(function (r) {
      return r.tag_name === tag;
    });
    if (rel) renderRelease(rel);
  }

  sel.addEventListener('change', onSelect);

  function populateSelect(list) {
    sel.innerHTML = '';
    list.forEach(function (r, i) {
      var o = document.createElement('option');
      o.value = r.tag_name;
      var label = displayVersionFromTag(r.tag_name);
      if (i === 0) label += ' (Latest)';
      o.textContent = label;
      sel.appendChild(o);
    });
  }

  function defaultSelectedTag(list) {
    var want = cfg.defaultTag;
    if (list.some(function (r) {
      return r.tag_name === want;
    })) {
      return want;
    }
    return list[0] ? list[0].tag_name : '';
  }

  fetch(cfg.apiUrl)
    .then(function (res) {
      if (!res.ok) throw new Error('GitHub API ' + res.status);
      return res.json();
    })
    .then(function (data) {
      if (!Array.isArray(data)) throw new Error('bad payload');
      allReleases = mergeReleases(data, cfg.previewReleases || []);
      if (statusEl) statusEl.textContent = '';
      populateSelect(allReleases);
      var def = defaultSelectedTag(allReleases);
      sel.value = def;
      onSelect();
    })
    .catch(function () {
      allReleases = mergeReleases([], cfg.previewReleases || []);
      if (statusEl) {
        statusEl.textContent =
          'Could not load live releases from GitHub; showing bundled version list. ';
        var a = document.createElement('a');
        a.href = cfg.releaseIndexUrl;
        a.target = '_blank';
        a.rel = 'noopener';
        a.textContent = 'Open releases ↗';
        statusEl.appendChild(a);
      }
      populateSelect(allReleases);
      var def = defaultSelectedTag(allReleases);
      if (def) sel.value = def;
      onSelect();
    });
})();
