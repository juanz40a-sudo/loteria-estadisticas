#!/usr/bin/env python3
"""Añade a datos/ los sorteos nuevos publicados en El Mundo.

Lee https://www.elmundo.es/loterias/resultados.html, extrae el último
resultado de La Primitiva, Bonoloto, Euromillones y El Gordo, y los guarda
en datos/<juego>_nuevos.csv (si la fecha no existe ya en datos/datos.json).
Después hay que ejecutar build_data.py para regenerar index.html.

Uso:
  python3 scripts/actualizar.py            # añade los sorteos nuevos
  python3 scripts/actualizar.py --dry-run  # solo muestra lo que encontraría
"""
import csv
import html
import json
import os
import re
import sys
import urllib.request
from datetime import date

URL = 'https://www.elmundo.es/loterias/resultados.html'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, 'datos')

MESES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
         'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12}


def descargar():
    req = urllib.request.Request(URL, headers={'User-Agent': UA, 'Accept-Language': 'es-ES,es;q=0.9'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode('utf-8', errors='ignore')


def bloques(pagina):
    """Devuelve {slug: lista de tokens de texto} de cada bloque de sorteo."""
    marcas = list(re.finditer(r'ue-c-lottery-raffle--([a-z0-9-]+)', pagina))
    res = {}
    for k, m in enumerate(marcas):
        slug = m.group(1)
        if slug in res:
            continue
        fin = marcas[k + 1].start() if k + 1 < len(marcas) else m.start() + 6000
        txt = re.sub(r'<[^>]+>', '|', pagina[m.start():fin])
        txt = html.unescape(txt)
        tokens = [t.strip() for t in txt.split('|') if t.strip()]
        res[slug] = tokens
    return res


def fecha_es(texto):
    """'Jueves, 19 noviembre 2026' -> '19/11/2026'."""
    m = re.search(r'(\d{1,2})\s+([a-záéíóú]+)\s+(\d{4})', texto.lower())
    if not m or m.group(2) not in MESES:
        raise ValueError('Fecha no reconocida: %r' % texto)
    d = date(int(m.group(3)), MESES[m.group(2)], int(m.group(1)))
    return d.strftime('%d/%m/%Y')


def numeros_tras(tokens, etiqueta=None):
    """Números (1-2 cifras) seguidos a partir de una posición dada."""
    out = []
    for t in tokens:
        if re.fullmatch(r'\d{1,2}', t):
            out.append(int(t))
        else:
            break
    return out


def extraer(tokens, n_principales, rango):
    """Localiza la fecha y los números principales de un bloque."""
    fecha = next(t for t in tokens if re.search(r'\d{4}', t) and re.search(r'[a-z]', t.lower()))
    i = tokens.index(fecha) + 1
    nums = []
    while i < len(tokens) and len(nums) < n_principales and re.fullmatch(r'\d{1,2}', tokens[i]):
        nums.append(int(tokens[i]))
        i += 1
    if len(nums) != n_principales:
        raise ValueError('Se esperaban %d números y hay %d' % (n_principales, len(nums)))
    if any(not (rango[0] <= n <= rango[1]) for n in nums):
        raise ValueError('Número fuera de rango: %s' % nums)
    return fecha_es(fecha), nums, tokens[i:]


def tras_etiqueta(resto, etiqueta):
    for k, t in enumerate(resto):
        if t.lower().startswith(etiqueta.lower()) and k + 1 < len(resto):
            m = re.fullmatch(r'\d{1,2}', resto[k + 1])
            if m:
                return int(resto[k + 1])
    return None


def leer_primitiva(tokens):
    f, nums, resto = extraer(tokens, 6, (1, 49))
    comp = tras_etiqueta(resto, 'Complementario')
    rei = tras_etiqueta(resto, 'Reintegro')
    joker = None
    for k, t in enumerate(resto):
        if t.lower().startswith('joker') and k + 1 < len(resto) and re.fullmatch(r'\d{7}', resto[k + 1]):
            joker = resto[k + 1]
    if comp is None or rei is None:
        raise ValueError('Primitiva: falta complementario o reintegro')
    return 'primitiva', [f] + nums + [comp, rei, joker or '']


def leer_bonoloto(tokens):
    f, nums, resto = extraer(tokens, 6, (1, 49))
    comp = tras_etiqueta(resto, 'Complementario')
    rei = tras_etiqueta(resto, 'Reintegro')
    if comp is None or rei is None:
        raise ValueError('Bonoloto: falta complementario o reintegro')
    return 'bonoloto', [f] + nums + [comp, rei]


def leer_euromillones(tokens):
    f, nums, resto = extraer(tokens, 7, (1, 50))
    principales, estrellas = nums[:5], nums[5:]
    if any(not (1 <= e <= 12) for e in estrellas):
        raise ValueError('Euromillones: estrellas fuera de rango %s' % estrellas)
    return 'euromillones', [f] + principales + ['', '%02d' % estrellas[0], '%02d' % estrellas[1]]


def leer_gordo(tokens):
    f, nums, resto = extraer(tokens, 5, (0, 54))
    clave = tras_etiqueta(resto, 'Clave')
    if clave is None or not (0 <= clave <= 9):
        raise ValueError('El Gordo: clave no válida')
    return 'elgordo', [f] + nums + [clave]


LECTORES = {
    'la-primitiva': leer_primitiva,
    'bonoloto': leer_bonoloto,
    'euromillones': leer_euromillones,
    'gordo-primitiva': leer_gordo,
}
# juego -> (nombre de archivo, cabecera que tienen los CSV históricos)
ARCHIVOS = {
    'primitiva': 'primitiva_nuevos.csv',
    'bonoloto': 'bonoloto_nuevos.csv',
    'euromillones': 'euromillones_nuevos.csv',
    'elgordo': 'el-gordo-de-la-primitiva_nuevos.csv',
}


def fechas_existentes():
    """Fechas ya guardadas, en datos.json y en los *_nuevos.csv."""
    with open(os.path.join(DATOS, 'datos.json'), encoding='utf-8') as f:
        d = json.load(f)
    res = {}
    for juego, filas in d['sorteos'].items():
        res[juego] = set(fila['f'] for fila in filas)
    for juego, nombre in ARCHIVOS.items():
        ruta = os.path.join(DATOS, nombre)
        if not os.path.exists(ruta):
            continue
        with open(ruta, encoding='utf-8') as f:
            for fila in csv.reader(f):
                if fila and re.fullmatch(r'\d{2}/\d{2}/\d{4}', fila[0].strip()):
                    res.setdefault(juego, set()).add(iso(fila[0].strip()))
    return res


def iso(fecha_dd_mm_yyyy):
    d, m, a = fecha_dd_mm_yyyy.split('/')
    return '%s-%s-%s' % (a, m, d)


def main():
    dry = '--dry-run' in sys.argv
    pagina = descargar()
    encontrados = {}
    bl = bloques(pagina)
    for slug, lector in LECTORES.items():
        if slug not in bl:
            raise SystemExit('No encuentro el bloque de %s en la página. Puede haber cambiado.' % slug)
        juego, fila = lector(bl[slug])
        encontrados[juego] = fila

    existentes = fechas_existentes()
    nuevos = 0
    for juego, fila in encontrados.items():
        fecha = iso(fila[0])
        estado = 'ya existe' if fecha in existentes.get(juego, set()) else 'NUEVO'
        print('%-13s %s  %s' % (juego, fila[0], estado), fila[1:])
        if estado == 'NUEVO':
            nuevos += 1
            if not dry:
                ruta = os.path.join(DATOS, ARCHIVOS[juego])
                nuevo_archivo = not os.path.exists(ruta)
                with open(ruta, 'a', newline='', encoding='utf-8') as f:
                    w = csv.writer(f)
                    w.writerow(fila)
                print('   -> añadido a', ARCHIVOS[juego])
    print('Sorteos nuevos: %d' % nuevos)


if __name__ == '__main__':
    main()
