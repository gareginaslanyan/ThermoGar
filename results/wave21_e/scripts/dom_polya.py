"""21-E: which element draws the frame of st.selectbox / st.multiselect in 1.62.

Streamlit 1.62 builds these fields on react-aria, not on BaseWeb, so a
``[data-baseweb="select"]`` selector finds nothing. The script opens the app
(port 8635), walks the subtree of the first visible stSelectbox and
stMultiSelect and prints every element with a border or a background, with
its tag, data-testid, classes and computed border.

    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe -B -X utf8 results\\wave21_e\\scripts\\dom_polya.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kadry  # noqa: E402

mgs = kadry.mgs

WALK_JS = r"""
(testid) => {
  const root = [...document.querySelectorAll(`[data-testid="${testid}"]`)]
    .find(e => e.offsetParent !== null);
  if (!root) return null;
  const out = [];
  const walk = (el, depth) => {
    const s = getComputedStyle(el);
    const bw = parseFloat(s.borderTopWidth);
    const bg = s.backgroundColor;
    if (bw > 0 || (bg && bg !== 'rgba(0, 0, 0, 0)')) {
      out.push({depth, tag: el.tagName.toLowerCase(), testid: el.dataset.testid || null,
                role: el.getAttribute('role'), cls: (el.className && el.className.baseVal === undefined ? el.className : '').slice(0, 80),
                border: `${s.borderTopWidth} ${s.borderTopStyle} ${s.borderTopColor}`, bg});
    }
    for (const child of el.children) walk(child, depth + 1);
  };
  walk(root, 0);
  return out;
}
"""


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        page = browser.new_page(viewport=dict(kadry.VIEWPORT))
        page.goto(f"http://127.0.0.1:{kadry.PORT}/", wait_until="domcontentloaded")
        page.get_by_role("tab", name="Расчёты", exact=True).wait_for(timeout=mgs.CALC_TIMEOUT_MS)
        mgs.wait_idle(page)
        expand = page.locator('[data-testid="stExpandSidebarButton"]')
        if expand.count() and expand.first.is_visible():
            expand.first.click()
            mgs.wait_idle(page)
        result = {"stSelectbox": page.evaluate(WALK_JS, "stSelectbox")}
        mgs.open_tab(page, "Энергии")
        result["stMultiSelect"] = page.evaluate(WALK_JS, "stMultiSelect")
        print(json.dumps(result, ensure_ascii=False, indent=1))
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
