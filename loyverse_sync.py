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


def name_key(value):
    import unicodedata
    normalized = unicodedata.normalize('NFKD', text(value)).casefold()
    return ' '.join(''.join(c for c in normalized if not unicodedata.combining(c)).split())


def plan_catalog(rows, items, levels, store, stores):
    """Add explicit creation actions for new simple products and complete families.

    Creation starts at zero stock. Existing stock remains a separate reviewed write.
    Never extend an existing family implicitly or change existing item metadata.
    """
    import bleach
    stock_plan = plan_stock(rows, items, levels, store)
    by_sku = {p['sku']: p for p in stock_plan}
    row_index = defaultdict(list)
    families = defaultdict(list)
    for row in rows:
        row_index[text(row.get('sku'))].append(row)
        if text(row.get('sku_padre')) and not is_variable_parent(row):
            families[text(row['sku_padre'])].append(row)
    remote_names = {name_key(i.get('item_name')) for i in items if not i.get('deleted_at')}
    remote_refs = {text(i.get('reference_id')) for i in items if not i.get('deleted_at')}
    local_names = Counter(name_key(text(r.get('nombre_producto'))[:64]) for r in rows
                          if not text(r.get('sku_padre')))
    result, handled = [], set()
    active_stores = sorted(s['id'] for s in stores if not s.get('deleted_at'))
    if store not in active_stores:
        raise ValueError('La sucursal ya no está disponible.')
    for entry in stock_plan:
        row = row_index[entry['sku']][0]
        parent = text(row.get('sku_padre'))
        if entry['status'] != 'No existe en Loyverse':
            result.append(dict(entry, action='stock'))
            continue
        key = parent or entry['sku']
        if key in handled:
            continue
        handled.add(key)
        children = families[parent] if parent else [row]
        planned = [by_sku[text(c.get('sku'))] for c in children]
        # Avoid duplicate stock actions for existing members of partially matched families.
        creation = dict(entry, sku=key, action='create', eligible=False, variant_id=None,
                        detail='', price=None, drive='Por variación' if parent else entry['drive'], loyverse=None)
        result.append(creation)
        try:
            if parent:
                candidates = row_index[parent]
                if len(candidates) != 1 or not is_variable_parent(candidates[0]):
                    raise ValueError('Falta un padre único en Drive para esta familia')
                source = candidates[0]
                if any(p['status'] != 'No existe en Loyverse' for p in planned):
                    raise ValueError('Familia parcialmente existente o con conflictos: revisar antes de crear')
            else:
                source = row
                if text(row.get('tipo')).casefold() in {'variation', 'variación', 'variacion', 'variante'}:
                    raise ValueError('La variación necesita un SKU padre')
            if any(p['status'] != 'No existe en Loyverse' for p in planned):
                raise ValueError('SKU o código duplicado: revisar antes de crear')
            name = text(source.get('nombre_producto'))[:64]
            if not name:
                raise ValueError('Falta el nombre del producto')
            if name_key(name) in remote_names or key in remote_refs:
                raise ValueError('Posible producto existente por nombre o referencia: revisar SKU')
            if local_names[name_key(name)] != 1:
                raise ValueError('Nombre repetido en Drive: revisar antes de crear')
            if len(key) > 128 or not 1 <= len(children) <= 100:
                raise ValueError('Referencia demasiado larga o familia de más de 100 variaciones')
            payload = {'item_name': name, 'reference_id': key, 'track_stock': True,
                       'sold_by_weight': False, 'is_composite': False, 'variants': []}
            description = bleach.clean(text(source.get('descripcion_larga')) or text(source.get('descripcion_corta')),
                                       tags=[], strip=True)
            if description:
                payload['description'] = description[:32768]
            options = set()
            attributes = {text(c.get('atributo_nombre')) for c in children if text(c.get('atributo_nombre'))}
            if parent:
                if len(attributes) > 1:
                    raise ValueError('Las variaciones necesitan el mismo nombre de atributo')
                payload['option1_name'] = next(iter(attributes), 'Presentación')
            details = []
            for child in children:
                sku = text(child.get('sku'))
                if not 1 <= len(sku) <= 40:
                    raise ValueError('Loyverse requiere SKU de 1 a 40 caracteres')
                price = quantity(child.get('precio'))
                variant = {'sku': sku, 'reference_variant_id': sku, 'default_pricing_type': 'FIXED',
                           'default_price': price, 'stores': [{'store_id': sid, 'pricing_type': 'FIXED',
                           'price': price, 'available_for_sale': sid == store} for sid in active_stores]}
                code = text(child.get('codigo_barras'))
                if code:
                    if not isinstance(child.get('codigo_barras'), str):
                        raise ValueError('Guarda el código de barras como texto en Drive para conservar sus ceros')
                    if len(code) > 128:
                        raise ValueError('El código de barras supera 128 caracteres')
                    variant['barcode'] = code
                if parent:
                    option = text(child.get('atributo_valor'))
                    if not 1 <= len(option) <= 20 or name_key(option) in options:
                        raise ValueError('Cada variación necesita un atributo único de 1 a 20 caracteres')
                    options.add(name_key(option))
                    variant['option1_value'] = option
                payload['variants'].append(variant)
                details.append(f'{sku}: ${price:.2f}' + (f" ({variant['option1_value']})" if parent else ''))
            creation.update(name=name, eligible=True, status='Crear familia' if parent else 'Crear producto',
                            detail='; '.join(details) + '. Stock inicial: 0. Después compara para enviar existencias.',
                            price=' / '.join(f"${v['default_price']:.2f}" for v in payload['variants']), payload=payload)
        except ValueError as exc:
            creation.update(status=str(exc), eligible=False)
    return result
