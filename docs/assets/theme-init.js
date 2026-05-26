(function () {
  var KEY = "fairdatahive-theme";

  function resolve() {
    var stored = localStorage.getItem(KEY);
    if (stored === "light" || stored === "dark") return stored;
    return window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
  }

  function apply(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var logo = document.querySelector(".sidebar-brand .mark img");
    if (logo) {
      logo.src =
        theme === "light" ? "assets/logo-light.svg" : "assets/logo.svg";
    }
    var btn = document.querySelector(".theme-toggle");
    if (btn) {
      btn.setAttribute("aria-pressed", theme === "light" ? "true" : "false");
      btn.title = theme === "light" ? "Switch to dark mode" : "Switch to light mode";
      var label = btn.querySelector(".theme-toggle-label");
      if (label) label.textContent = theme === "light" ? "Dark" : "Light";
      var icon = btn.querySelector(".theme-toggle-icon");
      if (icon) icon.textContent = theme === "light" ? "☀" : "☽";
    }
  }

  apply(resolve());

  window.addEventListener("storage", function (e) {
    if (e.key === KEY && (e.newValue === "light" || e.newValue === "dark")) {
      apply(e.newValue);
    }
  });

  window.fairdatahiveTheme = {
    KEY: KEY,
    get: function () {
      return document.documentElement.getAttribute("data-theme") || "dark";
    },
    set: function (theme) {
      localStorage.setItem(KEY, theme);
      apply(theme);
      window.dispatchEvent(
        new CustomEvent("fairdatahive-theme-change", { detail: theme })
      );
    },
    toggle: function () {
      var next = this.get() === "light" ? "dark" : "light";
      this.set(next);
      return next;
    },
  };

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.querySelector(".theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        window.fairdatahiveTheme.toggle();
      });
      apply(window.fairdatahiveTheme.get());
    }
  });
})();
