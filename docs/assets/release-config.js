(function (g) {
  var owner = 'SirStig';
  var repo = 'EncodeForge';
  g.EncodeForgeReleaseConfig = {
    owner: owner,
    repo: repo,
    defaultTag: 'v0.5.0-alpha-2',
    apiUrl: 'https://api.github.com/repos/' + owner + '/' + repo + '/releases?per_page=100',
    releaseIndexUrl: 'https://github.com/' + owner + '/' + repo + '/releases',
    downloadUrl: function (tag, file) {
      return (
        'https://github.com/' +
        this.owner +
        '/' +
        this.repo +
        '/releases/download/' +
        tag +
        '/' +
        encodeURIComponent(file)
      );
    },
    // Homepage Windows button uses direct .exe URL only when this filename exists on defaultTag; else downloads.html.
    defaultReleaseAssets: {
      macArmZip: 'encodeforge-macos-arm.zip',
      windowsExe: null,
    },
    previewReleases: [],
  };
})(typeof window !== 'undefined' ? window : globalThis);
