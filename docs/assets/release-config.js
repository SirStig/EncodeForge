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
    // Tags that are not on GitHub yet: shown in the picker with "coming soon" binaries.
    // After you publish the release, remove that entry here so the API is the single source of truth.
    previewReleases: [
      {
        tag_name: 'v0.5.0-alpha-2',
        name: 'v0.5.0 Alpha 2 (PySide6)',
        prerelease: true,
        published_at: '2026-03-25T12:00:00Z',
        pending: true,
        plannedAssets: [
          { name: 'encodeforge-macos-arm.zip' },
          { name: 'EncodeForge.exe' },
        ],
      },
    ],
  };
})(typeof window !== 'undefined' ? window : globalThis);

