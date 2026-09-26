// Mobile menu toggle
document.addEventListener("DOMContentLoaded", () => {
  const btn = document.querySelector(".nav-toggle");
  const nav = document.getElementById("main-nav");
  if (btn && nav) {
    btn.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  // "Copy" buttons on the donate page (bank account numbers, etc.)
  document.querySelectorAll("[data-copy]").forEach((el) => {
    el.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(el.dataset.copy);
        const old = el.textContent;
        el.textContent = "Copied!";
        setTimeout(() => (el.textContent = old), 1500);
      } catch (e) { /* clipboard not available — ignore */ }
    });
  });
});

// Facebook video: swap the play button for Facebook's player only when pressed.
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".video-play");
  if (!btn) return;
  const frame = document.createElement("iframe");
  frame.src = btn.dataset.src;
  frame.title = btn.dataset.title || "Video";
  frame.allow = "autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share";
  frame.allowFullscreen = true;
  frame.setAttribute("scrolling", "no");
  btn.replaceWith(frame);
});
