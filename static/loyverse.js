'use strict';
const $=id=>document.getElementById(id);
let previewId=null, working=false, activeJob=null;
async function request(path, options={}, timeout=15000){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);
  try{
    const res=await fetch(path,{...options,signal:controller.signal,cache:'no-store'});
    let result;try{result=await res.json();}catch{throw new Error('El servidor devolvió una respuesta incompleta. Consulta el progreso antes de volver a enviar.');}
    if(!res.ok){const error=new Error(result.error||'Error de conexión');error.status=res.status;throw error;}return result;
  }catch(e){if(e.name==='AbortError')throw new Error('La respuesta tardó demasiado. Consulta el progreso; la subida puede seguir en curso.');throw e;}
  finally{clearTimeout(timer);}
}
async function call(action,data){
  return request('/loyverse/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)},action==='preview'?120000:action==='connect'?60000:15000);
}
function selected(){return [...$('rows').querySelectorAll('input:checked')].map(c=>c.dataset.sku);}
function controls(){
  const count=selected().length;
  $('selection').textContent=count+' seleccionados (máximo 20 productos o familias).';
  $('apply').disabled=working||!!activeJob||!previewId||!$('confirm').checked||count<1||count>20;
  $('preview').disabled=working||!!activeJob||!$('store').value;
  $('store').disabled=working||!!activeJob||!$('store').options.length;
  $('confirm').disabled=working||!!activeJob;
  document.querySelectorAll('#connect button').forEach(b=>b.disabled=working||!!activeJob);
  $('resume').disabled=working;
  $('rows').querySelectorAll('input').forEach(c=>c.disabled=working||!!activeJob||c.dataset.eligible!=='true');
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

function showJob(job){
  const bar=$('progress');bar.hidden=false;bar.max=Math.max(1,job.total);bar.value=job.done;
  if(['queued','running'].includes(job.state)){
    message(job.done+'/'+job.total+' confirmados. '+job.phase+(job.current?' — '+job.current:'')+'. Puedes consultar el progreso si pierdes la conexión.');
    return;
  }
  message('Productos/familias creados: '+((job.created||[]).join(', ')||'ninguno')+'. Stock actualizado: '+((job.completed||[]).join(', ')||'ninguno')+'. '+(job.error||'Subida terminada.')+(job.uncertain?' Por verificar: '+job.uncertain+'.':'')+' Vuelve a comparar para verificar los resultados.');
}
async function monitor(job){
  const stopAt=Date.now()+720000;
  activeJob=job.id;controls();
  while(true){
    showJob(job);
    if(!['queued','running'].includes(job.state)){activeJob=null;controls();return;}
    if(Date.now()>stopAt)throw new Error('La subida sigue pendiente. Pulsa Consultar progreso; no vuelvas a enviar los mismos productos.');
    await new Promise(resolve=>setTimeout(resolve,2000));
    const state=await statusRequest('/loyverse-upload-status?job_id='+encodeURIComponent(activeJob));
    if(!state.job)throw new Error('No se pudo recuperar la subida. Consulta el progreso antes de reenviar.');
    job=state.job;
  }
}
async function statusRequest(path){
  try{return await request(path);}
  catch(e){
    if([401,404].includes(e.status)){activeJob=null;previewId=null;controls();}
    throw e;
  }
}
async function recover(){
  const r=await statusRequest('/loyverse-upload-status');
  if(!r.job){activeJob=null;message('No hay una subida en curso en esta sesión. Si el servicio reinició, compara con Loyverse antes de enviar de nuevo.');return;}
  await monitor(r.job);
}
$('resume').onclick=()=>busy(recover);
$('apply').onclick=()=>busy(async()=>{
  if(!$('confirm').checked)throw new Error('Confirma que revisaste los productos y cantidades.');
  const skus=selected();if(!skus.length||skus.length>20)throw new Error('Selecciona entre 1 y 20 productos o familias.');
  const id=previewId;previewId=null;activeJob='pending';
  message('Iniciando subida de '+skus.length+' productos o familias…');
  try{await monitor(await call('apply',{id,skus}));}
  catch(e){message(e.message+' Pulsa Consultar progreso para recuperar el resultado.');}
});
controls();
// Reloading the page observes the existing job; it never resubmits a batch.
busy(async()=>{const r=await statusRequest('/loyverse-upload-status');if(r.job)await monitor(r.job);});
