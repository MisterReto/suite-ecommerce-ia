(() => {
  'use strict';
  const el = id => document.getElementById(id);
  const labels = {in_sync:'En sincronía',inventory_mismatch:'Stock/precio distinto',stock_unmanaged:'Sin conteo en tienda',stock_inherited:'Stock compartido con padre',content_difference:'Nombre distinto',missing_in_woocommerce:'Falta en tienda',variable_parent:'Portada sin stock propio',duplicate:'SKU duplicado'};
  function storeStock(row) {
    if (row.status === 'variable_parent') return '—';
    if (row.stock_source === 'parent') return row.woocommerce_stock == null ? 'Compartido · cantidad no informada' : row.woocommerce_stock + ' · compartido con ' + (row.stock_parent_sku || 'padre');
    if (row.woocommerce_stock != null) return row.woocommerce_stock;
    const availability = {instock:'Disponible',outofstock:'Agotado',onbackorder:'Bajo pedido'};
    return (availability[row.stock_status] || 'No informado') + ' · sin conteo';
  }
  const money = value => value == null ? '—' : '$' + Number(value).toLocaleString('es-MX', {minimumFractionDigits:2,maximumFractionDigits:2});
  function notice(text, error=false) { el('msg').textContent=text; el('msg').classList.toggle('error',error); }
  async function jsonRequest(path, body) {
    const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Sesión caducada. Abre Inventario desde la Suite y conecta Drive.');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudo completar la operación.');
    return data;
  }
  function selectionCount() { el('selection-count').textContent=document.querySelectorAll('.bulk-check:checked').length+' seleccionados'; }
  document.querySelectorAll('.bulk-check').forEach(input=>input.addEventListener('change',selectionCount));
  document.querySelectorAll('.bulk-stock').forEach(input=>input.addEventListener('input',()=>{
    document.querySelector('.bulk-check[data-sku="'+CSS.escape(input.dataset.sku)+'"]').checked=true;
    selectionCount();
  }));
  function updateStock(result, initial) {
    const sku = result.sku, old = Number(result.old_stock), stock = Number(result.new_stock);
    const cell=document.querySelector('[data-stock="'+CSS.escape(sku)+'"]');
    if (cell) {
      cell.textContent=stock;
      const input=document.querySelector('.bulk-stock[data-sku="'+CSS.escape(sku)+'"]');
      if (input && Number(input.value)===old) input.value=stock;
    }
    const retail=el('retail-value');
    retail.dataset.value=Number(retail.dataset.value)+(stock-old)*Number(result.unit_price || 0);
    retail.textContent=money(retail.dataset.value);
    el('units').textContent=Number(el('units').textContent)+stock-old;
    el('low-stock').textContent=Number(el('low-stock').textContent)+Number(stock>=1&&stock<=3)-Number(old>=1&&old<=3);
    el('out-of-stock').textContent=Number(el('out-of-stock').textContent)+Number(stock===0)-Number(old===0);
    if (initial) {
      const status=document.querySelector('[data-count-status="'+CSS.escape(sku)+'"]');
      if (status && status.textContent==='Pendiente') {
        el('pending-count').textContent=Math.max(0,Number(el('pending-count').textContent)-1);
        status.textContent='✅ Ya contado';
      }
    }
    el('review-status').textContent='El inventario cambió. Pulsa Revisar para actualizar la comparación.';
    el('review-table').hidden=true;
    el('review-summary').replaceChildren();
  }
  let historySequence=0;
  async function history(sku) {
    const sequence=++historySequence;
    el('m-sku').value=sku; el('history-title').textContent=sku;
    el('history-rows').replaceChildren();
    const url=new URL(location.href);url.pathname='/inventory-hub';url.searchParams.set('sku',sku);window.history.replaceState(null,'',url);
    try {
      const data=await jsonRequest('/inventory-history?sku='+encodeURIComponent(sku));
      if (sequence!==historySequence) return;
      renderRows(el('history-rows'),data.rows.map(row=>['timestamp','movement_id','tipo','cantidad','stock_anterior','stock_nuevo','motivo','referencia','usuario'].map(key=>row[key])));
      if (!data.rows.length) renderRows(el('history-rows'),[['Aún no hay movimientos para este SKU.']]);
    } catch(error) { if (sequence===historySequence) notice(error.message,true); }
  }
  document.querySelectorAll('[data-history]').forEach(button=>button.addEventListener('click',()=>history(button.dataset.history)));
  function renderRows(target, rows) {
    const fragment=document.createDocumentFragment();
    rows.forEach(values=>{const tr=document.createElement('tr');values.forEach(value=>{const td=document.createElement('td');td.textContent=value==null?'—':String(value);tr.appendChild(td);});fragment.appendChild(tr);});
    target.replaceChildren(fragment);
  }
  let writing=false;
  async function busy(button, work, write=false) {
    if (button.disabled || (write && writing)) return;
    const label=button.textContent;button.disabled=true;button.textContent='Procesando…';
    if (write) {writing=true;el('bulk-btn').disabled=true;el('save-btn').disabled=true;}
    try { await work(); } catch(error) { notice(error.message,true); }
    finally {button.disabled=false;button.textContent=label;if(write){writing=false;el('bulk-btn').disabled=false;el('save-btn').disabled=false;}}
  }
  el('bulk-btn').addEventListener('click',()=>{
    const selected=[...document.querySelectorAll('.bulk-check:checked')];
    if (!selected.length) return notice('Selecciona los SKU que vas a contar.',true);
    const counts=selected.map(input=>({sku:input.dataset.sku,stock:document.querySelector('.bulk-stock[data-sku="'+CSS.escape(input.dataset.sku)+'"]').value}));
    if (!confirm('Guardar el stock físico final de '+counts.length+' SKU en Drive?')) return;
    busy(el('bulk-btn'),async()=>{
      const data=await jsonRequest('/inventory-count-bulk',{counts});
      data.result.results.forEach(result=>updateStock(result,true));
      selected.forEach(input=>input.checked=false);selectionCount();notice(data.message);
      if (el('m-sku').value) await history(el('m-sku').value);
    },true);
  });
  el('save-btn').addEventListener('click',()=>busy(el('save-btn'),async()=>{
    const data=await jsonRequest('/inventory-movement',{sku:el('m-sku').value,movement_type:el('m-type').value,quantity:el('m-qty').value,reason:el('m-reason').value,reference:el('m-ref').value});
    updateStock(data.movement,el('m-type').value==='Inventario inicial');notice(data.message);await history(data.movement.sku);
  },true));
  el('review-btn').addEventListener('click',()=>busy(el('review-btn'),async()=>{
    el('review-status').textContent='Consultando WooCommerce. Mantén esta página abierta…';
    try {
      const data=await jsonRequest('/inventory-review',{});
      const messages=[data.visibility.warning];
      if (data.source_stock.warning) messages.push(data.source_stock.warning);
      if (data.duplicates.length) messages.push('SKU duplicados: '+data.duplicates.join(', '));
      el('review-status').textContent=messages.filter(Boolean).join(' ');
      el('review-summary').replaceChildren();
      Object.entries(data.summary).forEach(([status,count])=>{
        const card=document.createElement('div');card.className='metric';
        const number=document.createElement('b');number.textContent=count;
        const label=document.createElement('span');label.textContent=labels[status]||status;
        card.append(number,label);el('review-summary').appendChild(card);
      });
      renderRows(el('review-rows'),data.rows.map(row=>[row.sku,row.name,labels[row.status]||row.status,row.inventory_stock,storeStock(row),money(row.inventory_price),money(row.woocommerce_price),row.stock_preview.reason]));
      el('review-table').hidden=false;
    } catch(error) {el('review-status').textContent=error.message;throw error;}
  }));
})();

