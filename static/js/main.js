function setTheme(theme) {
  localStorage.setItem("vb-theme", theme);
  var resolved = theme;
  if (theme === "system") {
    resolved = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.documentElement.setAttribute("data-theme", resolved);
  updateThemeIcon();
}

function cycleTheme() {
  var current = localStorage.getItem("vb-theme") || "system";
  var order = ["light", "dark", "system"];
  var next = order[(order.indexOf(current) + 1) % order.length];
  setTheme(next);
}

function updateThemeIcon() {
  var btn = document.getElementById("themeToggleBtn");
  if (!btn) return;
  var current = localStorage.getItem("vb-theme") || "system";
  var icons = { light: "☀️", dark: "🌙", system: "🖥️" };
  btn.textContent = icons[current] || "🖥️";
  btn.title = "Theme: " + current + " (click to change)";
}

document.addEventListener("DOMContentLoaded", function () {
  updateThemeIcon();

  var navToggle = document.getElementById("navToggle");
  var navLinks = document.getElementById("navLinks");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      navLinks.classList.toggle("open");
    });
  }

  // Fade/slide content in as it enters the viewport
  var els = document.querySelectorAll(".animate-on-scroll");
  if ("IntersectionObserver" in window && els.length) {
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("animate-in");
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });
    els.forEach(function (el) { obs.observe(el); });
  } else {
    els.forEach(function (el) { el.classList.add("animate-in"); });
  }

  // Auto-dismiss alerts
  document.querySelectorAll(".alert[data-autohide]").forEach(function (el) {
    setTimeout(function () { el.style.display = "none"; }, 6000);
  });
});
