(function () {
  function enableCameraHints() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach((input) => {
      input.setAttribute("accept", "image/*");
      input.setAttribute("capture", "environment");
    });
  }

  window.addEventListener("load", () => {
    enableCameraHints();
    const observer = new MutationObserver(enableCameraHints);
    observer.observe(document.body, { childList: true, subtree: true });
  });
})();