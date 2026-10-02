"""Deterministic, fail-closed matching. Parent covers never carry stock."""
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from inventory_schema import is_variable_parent


def text(value):
    return str(value or '').strip()


def barcode(value):
    value = text(value)
    return value.zfill(14) if value.isdigit() and len(value) in (8, 12, 13, 14) else value


def quantity(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > Decimal('9999999.999'):
            raise ValueError()
        return float(result)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Cantidad inválida para Loyverse.') from None


def plan_stock(rows, items, levels, store):
    skus, codes = defaultdict(list), defaultdict(list)
    for item in items:
        if item.get('deleted_at'):
            continue
        for variant in item.get('variants', []):
            if variant.get('deleted_at'):
                continue
            pair = (item, variant)
            if text(variant.get('sku')):
                skus[text(variant['sku'])].append(pair)
            if barcode(variant.get('barcode')):
                codes[barcode(variant['barcode'])].append(pair)
    local_skus = Counter(text(r.get('sku')) for r in rows)
    local_codes = Counter(barcode(r.get('codigo_barras')) for r in rows if not is_variable_parent(r) and barcode(r.get('codigo_barras')))
    stock = {(v['variant_id'], v['store_id']): v for v in levels}
    plan = []
    for row in rows:
        if is_variable_parent(row):
            continue
        sku, code = text(row.get('sku')), barcode(row.get('codigo_barras'))
        entry = {'sku': sku, 'name': text(row.get('nombre_producto')), 'drive': row.get('Existencias'),
                 'loyverse': None, 'variant_id': None, 'status': '', 'eligible': False}
        plan.append(entry)
        if not sku or local_skus[sku] != 1 or (code and local_codes[code] != 1):
            entry['status'] = 'SKU o código duplicado en Drive'
            continue
        by_sku, by_code = skus.get(sku, []), codes.get(code, [])
        candidates = {v['variant_id']: (i, v) for i, v in by_sku + by_code}
        if len(by_sku) > 1 or len(by_code) > 1 or len(candidates) > 1:
            entry['status'] = 'Conflicto de SKU / código de barras'
            continue
        if not candidates:
            entry['status'] = 'No existe en Loyverse'
            continue
        item, variant = next(iter(candidates.values()))
        remote_code = barcode(variant.get('barcode'))
        if code and remote_code and code != remote_code:
            entry['status'] = 'El código no coincide con el SKU'
            continue
        entry['variant_id'] = variant['variant_id']
        level = stock.get((variant['variant_id'], store))
        if not item.get('track_stock') or item.get('is_composite') or not level or level.get('in_stock') is None:
            entry['status'] = 'Sin stock propio verificable en esta sucursal'
            continue
        entry['loyverse'] = level['in_stock']
        entry['updated_at'] = level.get('updated_at')
        try:
            entry['drive'] = quantity(row.get('Existencias'))
            quantity(entry['loyverse'])
        except ValueError:
            entry['status'] = 'Cantidad inválida; corregir antes de sincronizar'
            continue
        entry['eligible'] = entry['drive'] != entry['loyverse']
        entry['status'] = 'Actualizar stock' if entry['eligible'] else 'Sin cambios'
    counts = Counter(p['variant_id'] for p in plan if p['variant_id'])
    for entry in plan:
        if entry['variant_id'] and counts[entry['variant_id']] > 1:
            entry.update(eligible=False, status='Varios productos de Drive apuntan a la misma variación')
    return plan
