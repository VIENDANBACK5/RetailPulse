/**
 * LIQUID REVEAL HERO CANVAS EFFECT
 */
export function initLiquidReveal(wrapId = 'liquid-wrap', canvasId = 'liquid-canvas') {
  const liquidWrap = document.getElementById(wrapId);
  const liquidCanvas = document.getElementById(canvasId);

  if (!liquidWrap || !liquidCanvas || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return;
  }

  const ctx = liquidCanvas.getContext('2d', { willReadFrequently: true });
  const brushRadius = 143;
  const decay = 0.016;

  let width = 0, height = 0, dpr = 1;
  let coverCanvas = document.createElement('canvas');
  let coverCtx = coverCanvas.getContext('2d');
  let brushCanvas = document.createElement('canvas');
  let brushCtx = brushCanvas.getContext('2d');

  const afterImage = new Image();
  afterImage.crossOrigin = 'anonymous';
  afterImage.src = 'https://api.getlayers.ai/storage/v1/object/public/public/assets/lumora-e8b711fc68/hero/before.jpg';

  let imgLoaded = false;
  afterImage.onload = () => {
    imgLoaded = true;
    drawCover();
  };

  function resize() {
    const rect = liquidWrap.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = Math.round(rect.width * dpr);
    height = Math.round(rect.height * dpr);

    liquidCanvas.width = width;
    liquidCanvas.height = height;
    coverCanvas.width = width;
    coverCanvas.height = height;

    const radius = brushRadius * dpr;
    const diam = Math.ceil(radius * 2);
    brushCanvas.width = diam;
    brushCanvas.height = diam;

    if (imgLoaded) drawCover();
  }

  function drawCover() {
    if (!width || !height || !imgLoaded) return;
    const imgRatio = afterImage.naturalWidth / afterImage.naturalHeight;
    const canvasRatio = width / height;
    let sWidth, sHeight, sx, sy;

    if (canvasRatio > imgRatio) {
      sWidth = afterImage.naturalWidth;
      sHeight = afterImage.naturalWidth / canvasRatio;
      sx = 0;
      sy = (afterImage.naturalHeight - sHeight) / 2;
    } else {
      sHeight = afterImage.naturalHeight;
      sWidth = afterImage.naturalHeight * canvasRatio;
      sx = (afterImage.naturalWidth - sWidth) / 2;
      sy = 0;
    }
    coverCtx.drawImage(afterImage, sx, sy, sWidth, sHeight, 0, 0, width, height);
  }

  window.addEventListener('resize', resize);
  resize();

  let points = [];
  let lastPoint = null;
  let idle = 0;

  window.addEventListener('pointermove', (e) => {
    const rect = liquidCanvas.getBoundingClientRect();
    const px = (e.clientX - rect.left) * dpr;
    const py = (e.clientY - rect.top) * dpr;
    const radius = brushRadius * dpr;

    if (px < -radius || py < -radius || px > width + radius || py > height + radius) {
      lastPoint = null;
      return;
    }

    if (!lastPoint) {
      lastPoint = { x: px, y: py };
      points.push({ x: px, y: py });
      return;
    }

    const dist = Math.hypot(px - lastPoint.x, py - lastPoint.y);
    const step = Math.max(radius * 0.3, 1);
    const n = Math.min(Math.ceil(dist / step), 60);

    for (let i = 1; i <= n; i++) {
      points.push({
        x: lastPoint.x + (px - lastPoint.x) * (i / n),
        y: lastPoint.y + (py - lastPoint.y) * (i / n)
      });
    }
    lastPoint = { x: px, y: py };
  });

  function stamp(x, y) {
    const radius = brushRadius * dpr;
    const diam = Math.ceil(radius * 2);

    brushCtx.clearRect(0, 0, diam, diam);
    brushCtx.globalCompositeOperation = 'source-over';

    const grad = brushCtx.createRadialGradient(radius, radius, 0, radius, radius, radius);
    grad.addColorStop(0, 'rgba(255, 255, 255, 1)');
    grad.addColorStop(0.55, 'rgba(255, 255, 255, 0.82)');
    grad.addColorStop(1, 'rgba(255, 255, 255, 0)');
    brushCtx.fillStyle = grad;
    brushCtx.fillRect(0, 0, diam, diam);

    brushCtx.globalCompositeOperation = 'source-in';
    brushCtx.drawImage(coverCanvas, x - radius, y - radius, diam, diam, 0, 0, diam, diam);

    ctx.globalCompositeOperation = 'source-over';
    ctx.drawImage(brushCanvas, x - radius, y - radius);
  }

  function renderLoop() {
    if (!imgLoaded) {
      requestAnimationFrame(renderLoop);
      return;
    }

    const hasPoints = points.length > 0;
    if (hasPoints) {
      idle = 0;
    } else {
      idle++;
    }

    if (idle <= 120) {
      const fade = hasPoints ? decay : Math.min(decay + idle * 0.004, 0.5);
      ctx.globalCompositeOperation = 'destination-out';
      ctx.fillStyle = `rgba(0, 0, 0, ${fade})`;
      ctx.fillRect(0, 0, width, height);

      if (hasPoints) {
        while (points.length) {
          const p = points.shift();
          stamp(p.x, p.y);
        }
      }

      if (idle === 120) {
        ctx.clearRect(0, 0, width, height);
      }
    }
    requestAnimationFrame(renderLoop);
  }
  requestAnimationFrame(renderLoop);
}
