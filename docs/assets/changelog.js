(function () {
  var body = document.getElementById("changelog-body");
  var status = document.getElementById("changelog-status");
  if (!body || !status) return;

  var root = document.documentElement;
  var fallbackMd =
    root.getAttribute("data-changelog-fallback") ||
    "https://raw.githubusercontent.com/SirStig/EncodeForge/HEAD/CHANGELOG.md";

  var primary = new URL(
    "changelog.md",
    document.querySelector('link[rel="canonical"]')?.href || window.location.href
  ).href;

  function loadText(url) {
    return fetch(url, { cache: "no-cache" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.text();
    });
  }

  function showError() {
    status.innerHTML =
      "Changelog could not be loaded. For local preview, copy the repo root <code>CHANGELOG.md</code> to <code>docs/changelog.md</code> (or <code>_site/changelog.md</code> after build). " +
      '<a href="https://github.com/SirStig/EncodeForge/blob/HEAD/CHANGELOG.md" target="_blank" rel="noopener">View on GitHub ↗</a>';
    status.classList.add("banner");
  }

  loadText(primary)
    .then(function (text) {
      return { text: text, source: "deploy" };
    })
    .catch(function () {
      return loadText(fallbackMd).then(function (text) {
        return { text: text, source: "github" };
      });
    })
    .then(function (pack) {
      if (typeof marked !== "undefined" && marked.parse) {
        body.innerHTML = marked.parse(pack.text);
      } else {
        throw new Error("marked not loaded");
      }
      var h2s = body.querySelectorAll("h2");
      h2s.forEach(function (h) {
        var m = /\[([^\]]+)\]/.exec(h.textContent || "");
        if (!m) return;
        var slug = "release-" + m[1].replace(/\./g, "-").toLowerCase();
        h.id = slug;
      });
      function scrollToHash() {
        var raw = location.hash.replace(/^#/, "");
        if (!raw) return;
        var id = decodeURIComponent(raw);
        var el = document.getElementById(id);
        if (el) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
      window.addEventListener("hashchange", scrollToHash);
      requestAnimationFrame(function () {
        scrollToHash();
        setTimeout(scrollToHash, 80);
      });
      status.textContent =
        pack.source === "deploy"
          ? "Source: changelog.md (shipped with this site)."
          : "Source: CHANGELOG.md (loaded from GitHub).";
    })
    .catch(showError);
})();
