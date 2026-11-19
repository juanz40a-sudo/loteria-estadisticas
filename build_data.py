import csv, json, re, glob, os
from datetime import datetime
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'datos')

def fecha(s):
    s = s.strip()
    return datetime.strptime(s, '%d/%m/%Y').strftime('%Y-%m-%d')

def leer(patron, nums, extra_fn):
    out = {}
    for path in sorted(glob.glob(os.path.join(D, patron))):
        with open(path, encoding='utf-8', errors='ignore') as f:
            for row in csv.reader(f):
                if not row or not re.match(r'^\d{1,2}/\d{1,2}/\d{4}$', row[0].strip()):
                    continue
                try:
                    f_ = fecha(row[0])
                except ValueError:
                    continue
                n = extra_fn(row, 'n')
                if n is None:
                    continue
                out[f_] = n
    return [dict(f=k, **v) for k, v in sorted(out.items(), reverse=True)]

def ints(xs):
    return [int(x) for x in xs if x.strip().isdigit()]

def primitiva(row, _):
    nums = ints(row[1:7])
    if len(nums) != 6: return None
    c = ints(row[7:8]); r = ints(row[8:9]); j = row[9].strip() if len(row) > 9 else ''
    return dict(n=nums, c=c[0] if c else None, r=r[0] if r else None, j=j or None)

def bonoloto(row, _):
    nums = ints(row[1:7])
    if len(nums) != 6: return None
    c = ints(row[7:8]); r = ints(row[8:9])
    return dict(n=nums, c=c[0] if c else None, r=r[0] if r else None)

def euromillones(row, _):
    nums = ints(row[1:6])
    if len(nums) != 5: return None
    est = ints(row[7:9])
    if len(est) != 2: return None
    return dict(n=nums, e=est)

def gordo(row, _):
    nums = ints(row[1:6])
    if len(nums) != 5: return None
    cl = ints(row[6:7])
    return dict(n=nums, clave=cl[0] if cl else None)

sorteos = {
    'primitiva': leer('primitiva_*.csv', 6, primitiva),
    'bonoloto': leer('bonoloto_*.csv', 6, bonoloto),
    'euromillones': leer('euromillones_*.csv', 5, euromillones),
    'elgordo': leer('el-gordo-de-la-primitiva_*.csv', 5, gordo),
}
navidad = []
with open(os.path.join(D, 'navidad_gordo.csv'), encoding='utf-8') as f:
    for r in csv.DictReader(f):
        navidad.append(dict(a=int(r['año']), n=r['numero_gordo'], fuente=r['fuente'], nota=r['nota']))
out = dict(sorteos=sorteos, navidad=navidad)
with open(os.path.join(D, 'datos.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
for k, v in sorteos.items():
    print(k, len(v), v[0]['f'], v[-1]['f'])
print('navidad', len(navidad), navidad[0]['a'], navidad[-1]['a'])

# --- generar index.html a partir de la plantilla ---
ROOT = os.path.dirname(os.path.abspath(__file__))
plantilla = open(os.path.join(ROOT, 'src', 'plantilla.html'), encoding='utf-8').read()
logo = open(os.path.join(ROOT, 'src', 'logo.svg'), encoding='utf-8').read().strip()
logo = logo.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
html = plantilla.replace('/*__DATOS__*/null', json.dumps(out, ensure_ascii=False, separators=(',', ':')))
html = html.replace('__LOGO__', logo)
with open(os.path.join(ROOT, 'index.html'), 'w', encoding='utf-8') as f:
    f.write(html)
print('index.html', len(html))
