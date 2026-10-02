'use strict';
const $=id=>document.getElementById(id);
let previewId=null;
async function call(action,data){
  const res=await fetch('/loyverse/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result=await res.json(); if(!res.ok)throw new Error(result.error||'Error de conexión');return result;
}
function invalidate(){previewId=null;$('apply').disabled=true;$('confirm').checked=false;$('rows').replaceChildren();}
async function busy(fn){document.querySelectorAll('button').forEach(b=>b.disabled=true);try{await fn();}catch(e){$('status').textContent=e.message;}finally{document.querySelectorAll('button').forEach(b=>b.disabled=false);$('preview').disabled=!$('store').value;$('apply').disabled=!previewId;}}
$('connect').onsubmit=e=>{e.preventDefault();busy(async()=>{invalidate();$('store').replaceChildren();const token=$('token').value;$('token').value='';const r=await call('connect',{token});for(const s of r.stores){const o=new Option(s.name,s.id);$('store').add(o);}$('store').disabled=false;$('status').textContent='Conectado. Selecciona una sucursal y compara.';});};
$('disconnect').onclick=()=>busy(async()=>{await call('disconnect',{});invalidate();$('store').replaceChildren();$('store').disabled=true;$('status').textContent='Token eliminado de la sesión.';});
$('store').onchange=invalidate;
$('preview').onclick=()=>busy(async()=>{invalidate();$('status').textContent='Consultando Drive y Loyverse…';const r=await call('preview',{store:$('store').value});previewId=r.id;for(const p of r.rows){const tr=document.createElement('tr');const td=document.createElement('td');const c=document.createElement('input');c.type='checkbox';c.disabled=!p.eligible;c.dataset.sku=p.sku;c.setAttribute('aria-label','Enviar '+p.sku);td.append(c);tr.append(td);for(const v of [p.sku,p.name,p.drive,p.loyverse,p.status]){const cell=document.createElement('td');cell.textContent=v??'—';tr.append(cell);}$('rows').append(tr);}$('status').textContent='Revisión lista. Selecciona hasta 20 SKU. Vence en 5 minutos.';});
$('apply').onclick=()=>busy(async()=>{if(!$('confirm').checked)throw new Error('Confirma que las cantidades de Drive son correctas.');const skus=[...$('rows').querySelectorAll('input:checked')].map(c=>c.dataset.sku);if(!skus.length||skus.length>20)throw new Error('Selecciona entre 1 y 20 SKU.');const id=previewId;previewId=null;const r=await call('apply',{id,skus});$('status').textContent='Confirmados: '+(r.completed||[]).join(', ')+'. '+(r.error||'Sincronización terminada.')+(r.uncertain?' SKU por verificar: '+r.uncertain:'')+' Vuelve a comparar para comprobar el resultado.';});
