// Open external links in the chapter body in a new tab, so clicking a code
// link (GitHub) or any off-site reference doesn't navigate away from the book.
// Internal chapter links are relative and are left untouched. Scoped to the
// content area so the menu-bar "back to isuruwijesiri.com" link keeps normal
// same-tab navigation.
(function () {
  function openExternalInNewTab() {
    var content = document.getElementById("content");
    if (!content) return;
    var links = content.querySelectorAll('a[href^="http://"], a[href^="https://"]');
    links.forEach(function (a) {
      if (a.hostname && a.hostname !== window.location.hostname) {
        a.target = "_blank";
        a.rel = "noopener noreferrer";
      }
    });
  }
  if (document.readyState !== "loading") openExternalInNewTab();
  else document.addEventListener("DOMContentLoaded", openExternalInNewTab);
})();
