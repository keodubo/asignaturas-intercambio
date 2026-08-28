(function (root) {
  function versionedAssetUrl(url, version) {
    if (!version) return url;
    const separator = url.includes("?") ? "&" : "?";
    return `${url}${separator}v=${encodeURIComponent(version)}`;
  }

  const api = { versionedAssetUrl };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.WebuiAssets = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
