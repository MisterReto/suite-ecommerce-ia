'use strict';
const $=id=>document.getElementById(id);
let previewId=null, working=false;
async function call(action,data){
  const res=await fetch('/loyverse/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result=await res.json(); if(!res.ok)throw new Error(result.error||'Error de conexión');return result;
}
function selected(){return [...$('rows').querySelectorAll('input:checked')].map(c=>c.dataset.sku);}
function controls(){
  const count=selected().length;
  $('selection').textContent=count+' seleccionados (máximo 20 productos o familias).';
  $('apply').disabled=working||!previewId||!$('confirm').checked||count<1||count>20;
  $('preview').disabled=working||!$('store').value;
  $('store').disabled=working||!$('store').options.length;
  $('confirm').disabled=working;
  document.querySelectorAll('#connect button').forEach(b=>b.disabled=working);
  $('rows').querySelectorAll('input').forEach(c=>c.disabled=working||c.dataset.eligible!=='true');
}
function invalidate(){previewId=null;$('confirm').checked=false;$('rows').replaceChildren();controls();}
function message(value){$('status').textContent=value;$('status').scrollIntoView({block:'nearest'});}
async function busy(fn){working=true;controls();try{await fn();}catch(e){message(e.message);}finally{working=false;controls();}}
$('connect').onsubmit=e=>{e.preventDefault();busy(async()=>{invalidate();$('store').replaceChildren();const token=$('token').value;$('token').value='';const r=await call('connect',{token});for(const s of r.stores)$('store').add(new Option(s.name,s.id));message('Conectado. Selecciona una sucursal y compara.');});};
$('disconnect').onclick=()=>busy(async()=>{await call('disconnect',{});invalidate();$('store').replaceChildren();message('Token eliminado de la sesión.');});
$('store').onchange=invalidate;
$('confirm').onchange=controls;
$('rows').onchange=controls;
$('preview').onclick=()=>busy(async()=>{
  invalidate();message('Consultando Drive y Loyverse…');
  const r=await call('preview',{store:$('store').value});previewId=r.id;
  let eligible=0;
  for(const p of r.rows){
    const tr=document.createElement('tr'),td=document.createElement('td');
    if(p.eligible){
      const c=document.createElement('input');c.type='checkbox';c.dataset.eligible='true';c.dataset.sku=p.sku;c.setAttribute('aria-label','Seleccionar '+p.sku);td.append(c);eligible++;
    }else{td.textContent='No disponible';td.title=p.status;}
    tr.append(td);
    for(const v of [p.sku,p.name,p.drive,p.loyverse,p.price,p.status,p.detail]){const cell=document.createElement('td');cell.textContent=v??'—';tr.append(cell);}
    $('rows').append(tr);
  }
  message(eligible?eligible+' productos o familias disponibles. Revisa acciones y precios, selecciona y confirma. La revisión vence en 5 minutos.':'No hay filas disponibles. La columna Estado explica qué debes corregir.');
});
$('apply').onclick=()=>busy(async()=>{
  if(!$('confirm').checked)throw new Error('Confirma que revisaste los productos y cantidades.');
  const skus=selected();if(!skus.length||skus.length>20)throw new Error('Selecciona entre 1 y 20 productos o familias.');
  const id=previewId;previewId=null;
  const r=await call('apply',{id,skus});
  message('Productos/familias creados: '+((r.created||[]).join(', ')||'ninguno')+'. Stock actualizado: '+((r.completed||[]).join(', ')||'ninguno')+'. '+(r.error||'Operación terminada.')+(r.uncertain?' Por verificar: '+r.uncertain+'.':'')+' Vuelve a comparar para verificar y enviar existencias a los productos nuevos.');
});
controls();
