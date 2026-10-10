"""Generate six OKLCH candidates and verify semantic token contrast before showing them."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PALETTES = [
    ('Тёплая бумага', 'Ivory Linen · спокойная терракота', 30, .12, .48, 75, .005),
    ('Персиковый город', 'Peach Comfort · мягкий и открытый', 30, .16, .53, 45, .02),
    ('Песчаный берег', 'Sand Club · сдержанный и тёплый', 50, .07, .42, 85, .01),
    ('Добрый сосед', 'Авторская · кирпичный акцент', 42, .14, .49, 65, .008),
    ('Солнечный двор', 'Авторская · охра и сливочный фон', 70, .105, .46, 85, .015),
    ('Зелёный квартал', 'Авторская · шалфей и тёплая бумага', 150, .075, .43, 85, .008),
]


def rgb(color):
    l, c, h = color
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    x, y, z = (l + .3963377774*a + .2158037573*b)**3, (l - .1055613458*a - .0638541728*b)**3, (l - .0894841775*a - 1.291485548*b)**3
    return [min(1, max(0, v)) for v in [4.0767416621*x - 3.3077115913*y + .2309699292*z, -1.2684380046*x + 2.6097574011*y - .3413193965*z, -.0041960863*x - .7034186147*y + 1.707614701*z]]


def ratio(a, b):
    lum = lambda col: sum(v*w for v, w in zip(rgb(col), [.2126, .7152, .0722]))
    x, y = sorted([lum(a), lum(b)])
    return (y + .05) / (x + .05)


def css(c):
    return f'oklch({c[0]:.3f} {c[1]:.3f} {c[2]})'


def hexcolor(c):
    srgb = lambda x: 12.92*x if x <= .0031308 else 1.055*x**(1/2.4)-.055
    return '#' + ''.join(f'{round(srgb(x)*255):02X}' for x in rgb(c))


def tokens(palette, dark):
    _, _, h, c, lightness, bh, bc = palette
    bg = (.17, bc, bh) if dark else (.98, bc, bh)
    fg = (.96, bc, bh) if dark else (.22, .015, bh)
    card = (.22, bc, bh) if dark else (1, 0, 0)
    primary = (.78, c*.75, h) if dark else (lightness, c, h)
    primary_fg = (.16, .005, bh) if dark else (.99, 0, 0)
    secondary = (.28, bc+.005, bh) if dark else (.94, bc+.005, bh)
    muted = (.26, bc, bh) if dark else (.95, bc, bh)
    muted_fg = (.76, .012, bh) if dark else (.44, .014, bh)
    t = {'background': bg, 'foreground': fg, 'card': card, 'card-foreground': fg, 'popover': card, 'popover-foreground': fg, 'primary': primary, 'primary-foreground': primary_fg, 'secondary': secondary, 'secondary-foreground': fg, 'muted': muted, 'muted-foreground': muted_fg, 'accent': secondary, 'accent-foreground': fg, 'destructive': (.51, .19, 25), 'destructive-foreground': (.99, 0, 0), 'border': (.44, bc, bh) if dark else (.80, bc, bh), 'input': card, 'ring': primary}
    pairs = [('foreground', b, 4.5) for b in ['background', 'card', 'popover', 'muted']]
    pairs += [('muted-foreground', b, 4.5) for b in ['background', 'card', 'muted']]
    pairs += [(b+'-foreground', b, 4.5) for b in ['primary', 'secondary', 'accent', 'destructive']]
    pairs += [('primary', 'background', 4.5), ('ring', 'background', 3), ('border', 'background', 1.5)]
    checks = {}
    for f, b, target in pairs:
        r = ratio(t[f], t[b])
        assert r >= target, (palette[0], dark, f, b, r)
        checks[f + '/' + b] = round(r, 2)
    return {k: css(v) for k, v in t.items()} | {'radius': '.75rem'}, checks


def generate():
    path = ROOT / '.brand-preview'
    path.mkdir(exist_ok=True)
    candidates = []
    for p in PALETTES:
        light, lc = tokens(p, False)
        dark, dc = tokens(p, True)
        seeds = [(.98,p[6],p[5]), (1,0,0), (p[4],p[3],p[2]), (.85,p[3]*.5,p[2]), (.22,.015,p[5])]
        candidates.append({'name':p[0], 'vibe':p[1], 'light':light, 'dark':dark, 'checks':{'light':lc,'dark':dc}, 'seeds':[{'oklch':css(c),'hex':hexcolor(c)} for c in seeds]})
    (path / 'palettes.json').write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
    html = '''<!doctype html><html lang="ru" data-theme="light"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Народный контроль · выбор оформления</title><style>
    *{box-sizing:border-box}body{margin:0;background:#eeece8;color:#262321;font:16px/1.6 system-ui}header.top{position:sticky;top:0;z-index:2;background:#fff;padding:20px max(24px,calc((100vw - 1000px)/2));display:flex;justify-content:space-between;gap:20px;border-bottom:1px solid #aaa}h1{font-size:20px;margin:0}small{font-size:14px}main{max-width:1000px;margin:auto;padding:32px 24px;display:grid;gap:32px}article{background:var(--background);color:var(--foreground);border:1px solid var(--border);border-radius:20px;overflow:hidden}.head{padding:24px;border-bottom:1px solid var(--border)}h2{margin:0;font-size:24px}.muted{color:var(--muted-foreground)}.ui{padding:32px;display:grid;grid-template-columns:1.15fr 1fr;gap:32px}h3{font-size:30px;line-height:1.2;margin:0 0 16px}.card{padding:24px;background:var(--card);border:1px solid var(--border);border-radius:var(--radius)}button{font:inherit;min-height:44px;padding:10px 18px;border:1px solid var(--border);border-radius:12px;cursor:pointer}button:focus-visible,input:focus-visible{outline:3px solid var(--ring);outline-offset:3px}.primary{color:var(--primary-foreground);background:var(--primary);border:0}.secondary{color:var(--foreground);background:var(--secondary)}input{width:100%;padding:12px;background:var(--input);color:var(--foreground);border:1px solid var(--border);border-radius:8px;font:inherit}.swatches{display:flex;gap:8px;padding:0 24px 24px}.swatch{flex:1}.color{height:42px;border-radius:6px;border:1px solid var(--border)}.checks{border-top:1px solid var(--border);padding:16px 24px;color:var(--muted-foreground);font-size:13px}.num{color:var(--primary);font-weight:700}.tag{background:var(--accent);padding:5px 10px;border-radius:8px;font-size:13px}label{display:block;margin:20px 0 8px} @media(max-width:650px){.ui{grid-template-columns:1fr;padding:24px}.swatches{flex-wrap:wrap}.head h2{font-size:21px}}
    </style><header class="top"><div><h1>Народный контроль</h1><small>6 вариантов · один и тот же экран · примеры, не реальные обращения</small></div><button id="toggle">Тёмная тема</button></header><main id="list"></main><script>
    const palettes=PALETTES;let theme='light';function render(){document.getElementById('list').innerHTML=palettes.map((p,i)=>`<article style="${Object.entries(p[theme]).map(([k,v])=>`--${k}:${v}`).join(';')}"><div class="head"><h2><span class="num">0${i+1}</span> ${p.name}</h2><small class="muted">${p.vibe}</small></div><div class="ui"><div><small class="muted">СЕМЕЙ · ВМЕСТЕ ЗА НАШ ГОРОД</small><h3>Хорошие дороги начинаются с внимания.</h3><p>Заметили проблему? Покажите её на фото и карте. Мы передадим обращение инспектору.</p><button class="primary" type="button">Сообщить о проблеме</button><label for="address-${i}">Где находится дефект?</label><input id="address-${i}" placeholder="Улица и ближайший ориентир"><p class="muted">Точку можно уточнить на карте.</p></div><div class="card"><span class="tag">Пример · на проверке</span><h3 style="font-size:23px;margin-top:20px">Яма рядом с остановкой</h3><p class="muted">Улица Абая, Семей</p><hr style="border:0;border-top:1px solid var(--border)"><p>Обращение получено. Ответ инспектора появится здесь.</p><button class="secondary" type="button">Мои обращения</button></div></div><div class="swatches">${p.seeds.map(s=>`<div class="swatch"><div class="color" style="background:${s.oklch}"></div><small>${s.hex}</small></div>`).join('')}</div><div class="checks">Контраст AA проверен · текст ${p.checks[theme]['foreground/background']}:1 · кнопка ${p.checks[theme]['primary-foreground/primary']}:1 · подсказки ${p.checks[theme]['muted-foreground/background']}:1</div></article>`).join('')}document.getElementById('toggle').onclick=()=>{theme=theme==='light'?'dark':'light';document.getElementById('toggle').textContent=theme==='light'?'Тёмная тема':'Светлая тема';render()};render();</script></html>'''
    (path/'index.html').write_text(html.replace('PALETTES', json.dumps(candidates,ensure_ascii=False)))
    print('Generated 6 palettes; all light/dark contrast checks pass.')


if __name__ == '__main__':
    generate()
