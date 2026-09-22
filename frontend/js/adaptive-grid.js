/**
 * ADAPTIVE GRID SCALE-UP ABOVE 1920PX
 * RetailPulse DWH
 */
export function applyAdaptiveGrid() {
  const FONT_BASE = 16, baseWidth = 1920, coef = 0.6666;
  const w = window.innerWidth;
  const widthReduction = ((baseWidth - w) / baseWidth) * 100;
  const size = FONT_BASE - (FONT_BASE * (widthReduction * coef)) / 100;
  if (size > FONT_BASE) {
    document.documentElement.style.fontSize = size + 'px';
  } else {
    document.documentElement.style.removeProperty('font-size');
  }
}

applyAdaptiveGrid();
window.addEventListener('resize', applyAdaptiveGrid);
