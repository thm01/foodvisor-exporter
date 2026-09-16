#!/usr/bin/env python3
"""Crée un XLSX et un CSV lisibles, sans dépendance externe."""
import argparse
import os
import csv
import datetime as dt
import json
from pathlib import Path
import zipfile
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
from i18n import TRANSLATIONS

MACROS = [('calories_100g', 1), ('proteins_100g', 4), ('carbs_100g', 4), ('lipids_100g', 9), ('fibers_100g', 2)]
LABELS = ['Calories (kcal)', 'Protéines (g)', 'Glucides (g)', 'Lipides (g)', 'Fibres (g)']
TYPES = {'breakfast': 'Petit-déjeuner', 'lunch': 'Déjeuner', 'dinner': 'Dîner', 'snack': 'Collation'}


def total(rows, index):
    values = [r[index] for r in rows]
    return sum(values) if values and all(v is not None for v in values) else None


def column(n):
    result = ''
    while n:
        n, mod = divmod(n - 1, 26)
        result = chr(65 + mod) + result
    return result


def make_xlsx(path, sheets):
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    styles = f'''<styleSheet xmlns="{ns}">
      <fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>
      <fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF235A67"/><bgColor indexed="64"/></patternFill></fill></fills>
      <borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
      <cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf><xf numFmtId="2" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>
      <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
    </styleSheet>'''
    with zipfile.ZipFile(path, 'x', zipfile.ZIP_DEFLATED) as z:
        overrides = ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1, len(sheets)+1))
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+overrides+'</Types>')
        z.writestr('_rels/.rels', f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/styles.xml', styles)
        entries = ''.join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i,(name,_,_) in enumerate(sheets,1))
        z.writestr('xl/workbook.xml', f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>{entries}</sheets></workbook>')
        entries = ''.join(f'<Relationship Id="rId{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1))
        z.writestr('xl/_rels/workbook.xml.rels', f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{entries}<Relationship Id="styles" Type="{rel}/styles" Target="styles.xml"/></Relationships>')
        for i,(name,rows,widths) in enumerate(sheets,1):
            last = f'{column(len(rows[0]))}{len(rows)}'
            parts = [f'<worksheet xmlns="{ns}"><dimension ref="A1:{last}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>']
            parts += [f'<col min="{n}" max="{n}" width="{w}" customWidth="1"/>' for n,w in enumerate(widths,1)]
            parts.append('</cols><sheetData>')
            for rn,row in enumerate(rows,1):
                parts.append(f'<row r="{rn}"'+(' ht="32" customHeight="1"' if rn==1 else '')+'>')
                for cn,value in enumerate(row,1):
                    if value is None: continue
                    ref=f'{column(cn)}{rn}'
                    if isinstance(value,(float,int)):
                        parts.append(f'<c r="{ref}" s="2"><v>{value}</v></c>')
                    else:
                        text=''.join(c for c in str(value) if ord(c)>=32 or c in '\n\r\t')
                        parts.append(f'<c r="{ref}" s="{1 if rn==1 else 0}" t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>')
                parts.append('</row>')
            parts.append(f'</sheetData><autoFilter ref="A1:{last}"/></worksheet>')
            z.writestr(f'xl/worksheets/sheet{i}.xml',''.join(parts))
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None
        for f in z.namelist(): ET.fromstring(z.read(f))


def create(source, base, language='fr'):
    if language not in TRANSLATIONS:
        raise ValueError(f'Unsupported export language: {language}')
    labels = TRANSLATIONS[language]['export']
    def tr(value):
        return labels.get(value, value)
    os.umask(0o077)
    data=json.loads(source.read_text()); foods=data['food_info_by_id']
    rows=[]; meal_rows=[]
    def visit(node, date, meal, factor=1., parent=''):
        own=node.get('serving_amount')
        factor *= own if own is not None else 1.
        main=node.get('main_food') or {}; info=foods.get(main.get('food_id'),{})
        name=node.get('name') or info.get('display_name') or info.get('category_name') or tr('Aliment sans nom')
        if main:
            q=main.get('quantity'); grams=q*factor if q is not None else None
            nutrients=[info.get(k)*grams/100/co if info.get(k) is not None and grams is not None else None for k,co in MACROS]
            unit=next((u for u in info.get('units',[]) if u.get('unit_id')==main.get('unit_id')), {})
            units=grams/unit['g_per_unit'] if grams is not None and unit.get('g_per_unit') else None
            rows.append([date,meal,name,parent,grams,units,unit.get('name',''),*nutrients,
                         tr('Complet') if all(v is not None for v in nutrients) else tr('Valeurs manquantes'),main.get('food_id','')])
        for child in node.get('sub_foods',[]): visit(child,date,meal,factor,(parent+' > ' if parent else '')+name)
    for meal in data['macro_meals']:
        offset=len(rows); date=meal['meal_date'];label=tr(TYPES.get(meal['meal_type'],meal['meal_type']))
        for node in meal.get('sub_foods',[]):visit(node,date,label)
        local=rows[offset:]
        meal_rows.append([date,label,len(local),*[total(local,i) for i in range(7,12)],
                          tr('Complet') if local and all(r[12]==tr('Complet') for r in local) else tr('Valeurs manquantes')])
    day_rows=[]
    water={v['date']:v['water_ml'] for v in data.get('water_trackers',[])}
    start=dt.date.fromisoformat(data['metadata']['start']);end=dt.date.fromisoformat(data['metadata']['end'])
    for n in range((end-start).days+1):
        day=str(start+dt.timedelta(days=n)); local=[r for r in rows if r[0]==day]
        day_rows.append([day,sum(r[0]==day for r in meal_rows),len(local),*[total(local,i) for i in range(7,12)],water.get(day),
                         tr('Aucun repas enregistré') if not local else (tr('Complet') if all(r[12]==tr('Complet') for r in local) else tr('Valeurs manquantes'))])
    headers=['Date','Repas','Aliment','Dans le plat','Masse calculée (g)','Nombre d’unités','Unité',*LABELS,'Disponibilité des valeurs','Identifiant alimentaire']
    notes=[['Sujet','Explication'],
           ['Période',tr('Du {start} au {end} inclus. {meals} repas ; {foods} fiches alimentaires.').format(start=start, end=end, meals=len(meal_rows), foods=len(foods))],
           ['Lecture','Par jour : synthèse. Par repas : totaux. Aliments : lignes détaillées filtrables. Eau : volumes enregistrés.'],
           ['Portions','Masse = main_food.quantity × serving_amount × multiplicateurs des plats parents, conformément au calcul nutritionnel de l’application.'],
           ['Unités','Nombre d’unités = masse calculée / g_per_unit. La masse équivalente est celle utilisée par Foodvisor pour les nutriments, y compris pour les liquides.'],
           ['Macronutriments','Valeurs Foodvisor converties en grammes : protéines /4, glucides /4, lipides /9, fibres /2, puis ajustées à la masse consommée.'],
           ['Plats composés','Chaque composante main_food est comptée une fois, puis ses sous-aliments. La colonne Dans le plat indique les relations.'],
           ['Valeurs absentes','Cellule vide = valeur absente. Un total est vide si au moins une de ses composantes est inconnue ; les absences ne sont pas transformées en zéro.'],
           ['Jours vides', ', '.join(data['metadata']['days_without_meals']) or tr('Aucun')],
           ['Eau','L’onglet Eau affiche uniquement les volumes enregistrés. Une cellule vide ne signifie pas zéro consommation.'],
           ['Précision','Affichage à deux décimales ; les totaux sont calculés avant arrondi. Aucune comparaison visuelle avec les totaux affichés dans l’application n’a été faite.'],
           ['Source','JSON fusionné Foodvisor conservé séparément pour tous les champs bruts et les détails non affichés ici.']]
    sheets=[('Par jour',[['Date','Repas enregistrés','Lignes alimentaires',*LABELS,'Eau enregistrée (ml)','Disponibilité des valeurs']]+day_rows,[15,18,20,18,18,18,18,18,23,28]),
            ('Par repas',[['Date','Repas','Lignes alimentaires',*LABELS,'Disponibilité des valeurs']]+meal_rows,[15,22,20,18,18,18,18,18,28]),
            ('Aliments',[headers]+rows,[15,22,58,45,22,20,20,18,18,18,18,18,28,38]),
            ('Eau',[['Date','Eau enregistrée (ml)']]+[[k,v] for k,v in sorted(water.items())],[15,24]),
            ('À lire',notes,[26,120])]
    headers = [tr(value) for value in headers]
    notes = [[tr(value) for value in row] for row in notes]
    sheets = [(tr(name), [[tr(value) if row_index == 0 else value for value in row]
                          for row_index, row in enumerate(content)], widths)
              for name, content, widths in sheets]
    sheets[-1] = (sheets[-1][0], notes, sheets[-1][2])
    make_xlsx(base.with_suffix('.xlsx'),sheets)
    with base.with_suffix('.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f,delimiter=';');w.writerow(headers)
        for row in rows:
            vals=[]
            for v in row:
                if isinstance(v,(int,float)):v=f'{v:.6f}'.rstrip('0').rstrip('.').replace('.',',')
                elif isinstance(v,str) and v.startswith(('=','+','-','@')):v="'"+v
                vals.append(v)
            w.writerow(vals)
    assert len(meal_rows)==len(data['macro_meals']) and len(day_rows)==(end-start).days+1
    for i in range(5):
        if all(r[7+i] is not None for r in rows):
            assert abs(sum(r[7+i] for r in rows)-sum(r[3+i] for r in meal_rows))<1e-6
            assert abs(sum(r[7+i] for r in rows)-sum(r[3+i] or 0 for r in day_rows))<1e-6
    with base.with_suffix('.csv').open(encoding='utf-8-sig',newline='') as f: assert len(list(csv.reader(f,delimiter=';')))==len(rows)+1
    print(json.dumps({'xlsx':str(base.with_suffix('.xlsx')),'csv':str(base.with_suffix('.csv')),'lignes_aliments':len(rows),'repas':len(meal_rows),'jours':len(day_rows),'valeurs_incompletes':sum(r[12]!=tr('Complet') for r in rows)},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output-base',type=Path,required=True)
    parser.add_argument('--language', choices=TRANSLATIONS, default='fr')
    args=parser.parse_args()
    create(args.source,args.output_base,args.language)
