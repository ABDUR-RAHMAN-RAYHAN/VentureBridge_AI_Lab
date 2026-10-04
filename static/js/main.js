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

/* ---------- Notification bell dropdown ---------- */
function vbCsrfToken() {
  var meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : "";
}

function vbToggleNotifications() {
  var panel = document.getElementById("notifPanel");
  if (!panel) return;
  var willOpen = panel.style.display === "none";
  panel.style.display = willOpen ? "block" : "none";
  if (willOpen) vbLoadNotifications();
}

function vbLoadNotifications() {
  var list = document.getElementById("notifPanelList");
  if (!list) return;
  fetch("/notifications/feed", { headers: { "X-Requested-With": "XMLHttpRequest" } })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      list.innerHTML = "";
      if (!data.items || !data.items.length) {
        var empty = document.createElement("p");
        empty.className = "text-muted";
        empty.style.padding = ".8rem";
        empty.textContent = "You're all caught up.";
        list.appendChild(empty);
        vbUpdateBadge(0);
        return;
      }
      // Built as real DOM nodes (not innerHTML string concatenation) so a
      // notification's title/message/url can never break out of an HTML
      // attribute no matter what characters it contains (e.g. a URL or
      // message with a quote in it used to silently corrupt the markup and
      // make the click handler a no-op).
      data.items.forEach(function (n) {
        var a = document.createElement("a");
        a.className = n.is_read ? "notif-panel-item" : "notif-panel-item unread";
        a.href = "javascript:void(0)";
        a.addEventListener("click", function () {
          vbOpenNotification(n.id, n.url);
        });

        var title = document.createElement("span");
        title.className = "notif-title";
        title.textContent = n.title;
        a.appendChild(title);

        if (n.message) {
          var msg = document.createElement("span");
          msg.className = "notif-msg";
          msg.textContent = n.message;
          a.appendChild(msg);
        }

        var time = document.createElement("span");
        time.className = "notif-time";
        time.textContent = n.created_at;
        a.appendChild(time);

        list.appendChild(a);
      });
      vbUpdateBadge(data.unread_count);
    })
    .catch(function () {
      list.innerHTML = "";
      var err = document.createElement("p");
      err.className = "text-muted";
      err.style.padding = ".8rem";
      err.textContent = "Couldn't load notifications.";
      list.appendChild(err);
    });
}

function vbUpdateBadge(count) {
  var btn = document.getElementById("notifBellBtn");
  if (!btn) return;
  var existing = btn.querySelector(".notif-badge");
  if (count > 0) {
    var text = count < 100 ? String(count) : "99+";
    if (existing) {
      existing.textContent = text;
    } else {
      var span = document.createElement("span");
      span.className = "notif-badge";
      span.textContent = text;
      btn.appendChild(span);
    }
  } else if (existing) {
    existing.remove();
  }
}

function vbOpenNotification(id, url) {
  fetch("/notifications/" + id + "/read", {
    method: "POST",
    headers: { "X-CSRFToken": vbCsrfToken(), "X-Requested-With": "XMLHttpRequest" },
  }).finally(function () {
    window.location.href = url || "/notifications";
  });
}

function vbMarkAllNotificationsRead() {
  fetch("/notifications/read-all", {
    method: "POST",
    headers: { "X-CSRFToken": vbCsrfToken(), "X-Requested-With": "XMLHttpRequest" },
  }).then(function () {
    vbLoadNotifications();
  });
}

function vbEscape(str) {
  var div = document.createElement("div");
  div.textContent = str == null ? "" : str;
  return div.innerHTML;
}

document.addEventListener("DOMContentLoaded", function () {
  document.addEventListener("click", function (e) {
    var dropdown = document.getElementById("notifDropdown");
    var panel = document.getElementById("notifPanel");
    if (!dropdown || !panel || panel.style.display === "none") return;
    if (!dropdown.contains(e.target)) panel.style.display = "none";
  });
});
