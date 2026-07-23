(function () {
  var cfg = window.EncodeForgeReleaseConfig;
  var ua = navigator.userAgent.toLowerCase();
  var dl = document.getElementById('download-btn');
  if (!dl || !cfg) return;

  var tag = cfg.defaultTag;
  var previews = cfg.previewReleases || [];
  var pendingDefault = previews.some(function (p) {
    return p.tag_name === tag && p.pending;
  });
  var assets = cfg.defaultReleaseAssets || {};
  var winExe = assets.windowsAsset ? cfg.downloadUrl(tag, assets.windowsAsset) : null;
  var macDownload = assets.macArmZip ? cfg.downloadUrl(tag, assets.macArmZip) : null;
  var downloadsPage = 'downloads.html';

  if (/linux/.test(ua)) {
    dl.textContent = 'Linux downloads';
    dl.href = downloadsPage;
    return;
  }

  if (/mac|darwin/.test(ua)) {
    if (pendingDefault || !macDownload) {
      dl.textContent = 'Download for macOS';
      dl.href = downloadsPage;
    } else {
      dl.href = macDownload;
      dl.textContent = 'Download for macOS (Apple Silicon)';
      if (navigator.userAgentData && typeof navigator.userAgentData.getHighEntropyValues === 'function') {
        navigator.userAgentData
          .getHighEntropyValues(['architecture'])
          .then(function (h) {
            if (h.architecture && h.architecture !== 'arm') {
              dl.textContent = 'macOS Intel — downloads';
              dl.href = downloadsPage;
            }
          })
          .catch(function () {});
      }
    }
    return;
  }

  dl.textContent = 'Download for Windows';
  dl.href = winExe || downloadsPage;
})();
