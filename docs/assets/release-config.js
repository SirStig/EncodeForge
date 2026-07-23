(function (g) {
  var owner = 'SirStig';
  var repo = 'EncodeForge';
  g.EncodeForgeReleaseConfig = {
    owner: owner,
    repo: repo,
    defaultTag: 'v0.5.0',
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
    defaultReleaseAssets: {
      macArmZip: 'EncodeForge-0.5.0-macos.dmg',
      windowsAsset: 'EncodeForge-0.5.0-windows-x64.exe',
    },
    previewReleases: [],
  };
})(typeof window !== 'undefined' ? window : globalThis);
