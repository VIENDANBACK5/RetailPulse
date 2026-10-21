"""Render the actual HTML slides and verify assets, fit and navigation."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    dest = ROOT / "evidence/presentation"
    dest.mkdir(parents=True, exist_ok=True)
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page.goto((ROOT / "docs/presentation/RetailPulse.html").as_uri())
        assert page.locator(".slide").count() == 15
        for i in range(15):
            page.evaluate("(i)=>show(i)", i)
            page.locator(".slide.active img").evaluate_all("imgs => Promise.all(imgs.map(i => i.decode()))")
            state = page.evaluate("""()=>{const s=document.querySelector('.slide.active');const c=s.querySelector('.content');
              return {title:s.querySelector('h1').innerText,bottom:c.getBoundingClientRect().bottom,
                width:s.getBoundingClientRect().width,height:s.getBoundingClientRect().height,
                images:[...s.querySelectorAll('img')].map(x=>({src:x.getAttribute('src'),ok:x.complete&&x.naturalWidth>0})),
                overflow:s.scrollWidth>s.clientWidth}}""")
            page.screenshot(path=str(dest / f"{i+1:02}.png"))
            checks.append({"slide": i + 1, **state})
        page.keyboard.press("Home")
        page.keyboard.press("ArrowRight")
        assert page.locator(".slide.active").get_attribute("id") == "slide-2"
        page.set_viewport_size({"width": 1200, "height": 1100})
        page.goto((ROOT / "docs/architecture/RetailPulse_HLD_v4.svg").as_uri())
        page.screenshot(path=str(ROOT / "docs/architecture/RetailPulse_HLD_v4.png"))
        browser.close()
    passed = all(x["bottom"] < 660 and x["width"] == 1280 and x["height"] == 720
                 and not x["overflow"] and all(y["ok"] for y in x["images"]) for x in checks)
    report = {"execution": "REAL_CHROME_RENDER", "slides": checks, "navigation": "PASS", "status": "PASS" if passed else "FAIL"}
    (dest / "render_check.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"HTML presentation: {len(checks)} slides; {report['status']}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
