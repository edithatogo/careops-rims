import json
import base64
import subprocess
import os

def build_single_line_measures():
    with open('powerbi/CHHHS Research Publications.SemanticModel/definition/tables/Publication.tmdl', 'r') as f:
        lines = f.read().splitlines()

    measure_blocks = []
    current = []
    in_m = False
    for line in lines:
        s = line.strip()
        if s.startswith('measure '):
            if current:
                measure_blocks.append(current)
                current = []
            in_m = True
        elif s.startswith('partition ') or s.startswith('table ') or s.startswith('column '):
            if current:
                measure_blocks.append(current)
                current = []
            in_m = False
        
        if in_m:
            current.append(line)

    if current:
        measure_blocks.append(current)

    print(f"Parsed {len(measure_blocks)} measures")

    formatted_measures = []
    for b in measure_blocks:
        header = b[0].strip()
        parts = header.split('=', 1)
        m_decl = parts[0].strip()
        first_dax = parts[1].strip() if len(parts) > 1 else ''
        
        dax_tokens = []
        if first_dax:
            dax_tokens.append(first_dax)
            
        props = []
        for l in b[1:]:
            s = l.strip()
            if s.startswith('formatString:') or s.startswith('lineageTag:'):
                props.append(s)
            elif s:
                dax_tokens.append(s)

        single_line_dax = ' '.join(dax_tokens)
        m_tmdl = f"\t\t{m_decl} = {single_line_dax}"
        for p in props:
            m_tmdl += f"\n\t\t\t{p}"
        formatted_measures.append(m_tmdl)

    tmdl = "createOrReplace\n\n\tref table Publication\n\n" + "\n\n".join(formatted_measures)
    return tmdl

def main():
    tmdl = build_single_line_measures()
    with open('private/ops/2026-09-15-measures-singleline.tmdl', 'w') as f:
        f.write(tmdl)

    print(f"TMDL size: {len(tmdl)} chars")

    b64 = base64.b64encode(tmdl.encode('utf-8')).decode('ascii')

    js_code = f"""async (page) => {{
  const res = await page.evaluate(async (b64) => {{
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    const script = new TextDecoder().decode(bytes);
    
    const frame = document.querySelector("iframe[name='iframe-page-modeling']");
    const win = frame.contentWindow;
    const doc = frame.contentDocument || win.document;
    const editors = win.monaco.editor.getEditors();
    const tmdlEditor = editors.find(e => e.getModel().getLanguageId() === 'tmdl');
    
    tmdlEditor.setValue(script);
    
    await new Promise(r => setTimeout(r, 2500));
    
    const markers = win.monaco.editor.getModelMarkers({{}});
    const errors = markers.filter(m => m.severity === 8).map(m => ({{ msg: m.message, line: m.startLineNumber }}));
    const applyBtn = doc.querySelector('#tmdl-apply-button');
    
    return {{
      editorLength: tmdlEditor.getValue().length,
      markersCount: markers.length,
      errorsCount: errors.length,
      errors: errors,
      applyDisabled: applyBtn ? applyBtn.disabled : null
    }};
  }}, "{b64}");
  return JSON.stringify(res);
}}"""

    js_path = 'private/ops/deploy_measures_test.js'
    with open(js_path, 'w') as f:
        f.write(js_code)

    res = subprocess.run(['/opt/homebrew/bin/playwright-cli', '-s=chrome', 'run-code', f'--filename={js_path}'], capture_output=True, text=True)
    print("OUTPUT:")
    print(res.stdout)
    if res.stderr:
        print("STDERR:", res.stderr)

if __name__ == '__main__':
    main()
