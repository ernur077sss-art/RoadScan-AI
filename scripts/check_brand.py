"""Verify the actual written CSS foreground/background tokens, including semantic states."""
import re
from pathlib import Path
from scripts.brand_preview import ratio


def check():
    css = (Path(__file__).resolve().parents[1] / 'web/app/globals.css').read_text()
    for theme, selector in [('light', ':root'), ('dark', '.dark')]:
        tokens = {}
        for block in re.findall(re.escape(selector) + r'\s*\{([^}]+)\}', css):
            for name, l, c, h in re.findall(r'--([\w-]+):\s*oklch\(([.\d]+)\s+([.\d]+)\s+([.\d]+)\)', block):
                tokens[name] = tuple(map(float, [l, c, h]))
        pairs = [('foreground', b, 4.5) for b in ['background', 'card', 'secondary', 'muted']]
        pairs += [('muted-foreground', b, 4.5) for b in ['background', 'card', 'secondary', 'muted', 'brand-soft']]
        pairs += [('primary', b, 4.5) for b in ['background', 'card', 'brand-soft']]
        pairs += [(x + '-foreground', x, 4.5) for x in ['primary', 'destructive']]
        pairs += [('warning-fg', 'warning-bg', 4.5), ('danger-text', 'danger-soft', 4.5), ('ring', 'background', 3), ('control-border', 'input', 3)]
        values = []
        for fg, bg, threshold in pairs:
            contrast = ratio(tokens[fg], tokens[bg])
            assert contrast >= threshold, f'{theme}: {fg}/{bg} {contrast:.2f} < {threshold}'
            values.append(contrast)
        print(f'{theme}: {len(values)} pairs passed; minimum {min(values):.2f}:1')


if __name__ == '__main__':
    check()
