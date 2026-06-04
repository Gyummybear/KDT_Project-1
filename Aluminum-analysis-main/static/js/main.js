(function () {
  window.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".mineral-card, .issue-row").forEach((item) => {
      item.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.currentTarget.click();
        }
      });
    });
  });
})();

