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
})();
