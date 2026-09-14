// Adds a "back to isuruwijesiri.com" button to the mdBook menu bar so the book,
// when served under the blog domain at /harness-engineering-101/, always offers
// a way back to the main site. Appended to the left button group on every page.
(function () {
  function addBackLink() {
    var bar = document.querySelector(".menu-bar .left-buttons");
    if (!bar || document.getElementById("site-home-link")) return;
    var a = document.createElement("a");
    a.id = "site-home-link";
    a.href = "https://isuruwijesiri.com/";
    a.title = "Back to isuruwijesiri.com";
    a.setAttribute("aria-label", "Back to isuruwijesiri.com");
    a.textContent = "← isuruwijesiri.com";
    a.style.cssText =
      "display:inline-flex;align-items:center;padding:0 10px;color:var(--icons);text-decoration:none;white-space:nowrap;";
    bar.appendChild(a);
  }
  if (document.readyState !== "loading") addBackLink();
  else document.addEventListener("DOMContentLoaded", addBackLink);
})();
