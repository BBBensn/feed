/* bensn.js — shared across all bensn.me pages */

(function() {
  const BLOBS = [
    { color: '#00A6FB', w: 520, h: 460, x: 0.72, y: 0.08, vx: 0.16, vy: 0.11 },
    { color: '#FF0051', w: 460, h: 400, x: 0.10, y: 0.65, vx: -0.13, vy: -0.15 },
    { color: '#00A6FB', w: 320, h: 280, x: 0.45, y: 0.45, vx: 0.09, vy: -0.18 },
    { color: '#FF0051', w: 280, h: 260, x: 0.80, y: 0.75, vx: -0.20, vy: 0.08 },
  ];

  const container = document.getElementById('blobs');
  if (!container) return;

  const els = BLOBS.map(b => {
    const el = document.createElement('div');
    el.className = 'blob';
    el.style.width = b.w + 'px';
    el.style.height = b.h + 'px';
    el.style.background = b.color;
    container.appendChild(el);
    return el;
  });

  const state = BLOBS.map(b => ({ ...b }));

  function tick() {
    const W = window.innerWidth;
    const H = window.innerHeight;
    state.forEach((b, i) => {
      b.x += b.vx * 0.0025;
      b.y += b.vy * 0.0025;
      const maxX = 1 - b.w / W;
      const maxY = 1 - b.h / H;
      if (b.x <= 0) { b.x = 0; b.vx = Math.abs(b.vx); }
      if (b.x >= maxX) { b.x = maxX; b.vx = -Math.abs(b.vx); }
      if (b.y <= 0) { b.y = 0; b.vy = Math.abs(b.vy); }
      if (b.y >= maxY) { b.y = maxY; b.vy = -Math.abs(b.vy); }
      els[i].style.transform = 'translate(' + Math.round(b.x * W) + 'px,' + Math.round(b.y * H) + 'px)';
    });
    requestAnimationFrame(tick);
  }
  tick();
})();
