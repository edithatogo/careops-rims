import base64
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    dax_path = ROOT / 'config' / 'native-canonical-check.dax'
    dax_content = dax_path.read_text(encoding='utf-8')
    b64_dax = base64.b64encode(dax_content.encode('utf-8')).decode('ascii')

    js_code = f"""async (page) => {{
  // 1. Set the query text into the active visible Monaco editor
  const setRes = await page.evaluate((b64) => {{
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    const script = new TextDecoder().decode(bytes);
    const iframe = document.querySelector('iframe[data-testid="iframe-page-modeling"]') || document.querySelector('iframe[name="iframe-page-modeling"]');
    if (!iframe) return {{ error: 'No modeling iframe found' }};
    const win = iframe.contentWindow;
    const editors = win.monaco.editor.getEditors();
    const visible = editors.find(e => {{
      const n = e.getDomNode();
      return n && n.offsetWidth > 0 && n.offsetHeight > 0;
    }});
    if (!visible) return {{ error: 'No visible editor' }};
    visible.setValue(script);
    return {{
      modelUri: visible.getModel().uri.toString(),
      length: visible.getValue().length,
      lines: visible.getValue().split('\\n').length
    }};
  }}, "{b64_dax}");
  
  console.log('Set editor result:', JSON.stringify(setRes));
  if (setRes.error) return JSON.stringify(setRes);

  // Wait 2 seconds for editor syntax check
  await page.waitForTimeout(2000);

  // 2. Click the Run button
  const clickRes = await page.evaluate(() => {{
    const iframe = document.querySelector('iframe[data-testid="iframe-page-modeling"]') || document.querySelector('iframe[name="iframe-page-modeling"]');
    const doc = iframe.contentDocument || iframe.contentWindow.document;
    const btns = Array.from(doc.querySelectorAll('button'));
    const runBtn = btns.find(b => b.innerText.trim() === 'Run');
    if (!runBtn) return {{ error: 'Run button not found' }};
    runBtn.click();
    return {{ clicked: true }};
  }});
  console.log('Clicked Run button:', JSON.stringify(clickRes));

  // 3. Wait for execution to finish
  await page.waitForTimeout(8000);

  // 4. Extract results
  const results = await page.evaluate(() => {{
    const iframe = document.querySelector('iframe[data-testid="iframe-page-modeling"]') || document.querySelector('iframe[name="iframe-page-modeling"]');
    const doc = iframe.contentDocument || iframe.contentWindow.document;
    
    // Check for error banner or message
    const errorBanner = doc.querySelector('.error-bar, .dax-error-message, [role=alert]');
    const errorText = errorBanner ? errorBanner.innerText.trim() : null;

    // Check result dropdown if present
    const resultDropdown = doc.querySelector('[role=combobox]');
    const resultDropdownText = resultDropdown ? resultDropdown.innerText.trim() : null;

    // Extract table headers and cells
    const headerElements = Array.from(doc.querySelectorAll('.table-header, .grid-header, [role=columnheader]'));
    const headers = headerElements.map(el => el.innerText.trim()).filter(t => t.length > 0);

    const cellElements = Array.from(doc.querySelectorAll('.table-cell, .grid-cell, [role=gridcell]'));
    const cells = cellElements.map(el => el.innerText.trim());

    return {{
      errorText,
      resultDropdownText,
      headers,
      cellsCount: cells.length,
      cells: cells.slice(0, 100)
    }};
  }});

  return JSON.stringify({{ setRes, clickRes, results }}, null, 2);
}}"""

    js_file = ROOT / 'private' / 'ops' / 'run_dax_step.js'
    js_file.parent.mkdir(parents=True, exist_ok=True)
    js_file.write_text(js_code, encoding='utf-8')

    print("Running DAX execution via playwright-cli...")
    res = subprocess.run(
        ['playwright-cli', '-s=chrome', 'run-code', f'--filename={js_file}'],
        capture_output=True,
        text=True
    )
    print("STDOUT:")
    print(res.stdout)
    if res.stderr:
        print("STDERR:")
        print(res.stderr)

if __name__ == '__main__':
    main()
