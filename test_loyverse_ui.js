// Exercise the actual browser script with a tiny DOM and simulated network.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
class Element{
  constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.options=[];this.disabled=false;this.checked=false;this.value='';this.textContent='';}
  append(child){this.children.push(child);}
  add(option){this.options.push(option);if(!this.value)this.value=option.value;}
  replaceChildren(){this.children=[];this.options=[];this.value='';}
  setAttribute(){}
  scrollIntoView(){}
  querySelectorAll(selector){const all=this.children.flatMap(c=>[c,...c.querySelectorAll('input')]);return all.filter(c=>c.tag==='input'&&(selector!=='input:checked'||c.checked));}
}
async function check(lostResponse){
  const ids=['rows','store','token','confirm','apply','selection','preview','connect','disconnect','resume','progress','status'];
  const elements=Object.fromEntries(ids.map(k=>[k,new Element()]));
  const connectButtons=[new Element('button'),new Element('button')];
  const calls=[],messages=[];let written=false;
  Object.defineProperty(elements.status,'textContent',{get(){return messages.at(-1)||'';},set(value){messages.push(value);}});
  const finished={id:'job',state:'done',total:1,done:1,created:['A'],completed:[],error:null,uncertain:null};
  const sandbox={AbortController,clearTimeout,setTimeout:(fn,ms)=>setTimeout(fn,ms===2000?0:ms),
    Option:function(name,value){this.name=name;this.value=value;},
    document:{getElementById:id=>elements[id],createElement:tag=>new Element(tag),querySelectorAll:()=>connectButtons},
    fetch:async(path,options)=>{
      calls.push([path,options.method||'GET']);
      let result;
      if(path.includes('upload-status'))result={job:written?finished:null};
      else if(path.endsWith('/connect'))result={stores:[{id:'s',name:'Sucursal'}]};
      else if(path.endsWith('/preview'))result={id:'preview',rows:[{sku:'A',name:'Ramen',drive:1,eligible:true,status:'Crear producto'}]};
      else if(path.endsWith('/apply')){written=true;if(lostResponse)throw new TypeError('network disconnected');result={...finished,state:'queued',done:0,created:[],phase:'Preparando subida'};}
      return{ok:true,json:async()=>result};
    }};
  vm.runInNewContext(fs.readFileSync('static/loyverse.js','utf8'),sandbox);
  await new Promise(r=>setTimeout(r,5));
  elements.token.value='fake-token';await elements.connect.onsubmit({preventDefault(){}});
  await elements.preview.onclick();
  const input=elements.rows.querySelectorAll('input')[0];input.checked=true;
  elements.confirm.checked=true;elements.confirm.onchange();
  assert.equal(elements.apply.disabled,false);
  await elements.apply.onclick();
  if(lostResponse){assert.equal(elements.apply.disabled,true);await elements.resume.onclick();}
  else assert(messages.some(m=>m.includes('0/1 confirmados')),'progress must appear before completion');
  assert.equal(calls.filter(([p])=>p.endsWith('/apply')).length,1,'never resend after a lost response');
  assert(elements.status.textContent.includes('creados: A'),'confirmed result is visible');
  assert.equal(elements.preview.disabled,false,'controls recover after completion');
}
(async()=>{await check(false);await check(true);process.stdout.write('Loyverse UI: progress and lost-response recovery passed\n');})().catch(e=>{process.stderr.write(e.stack+'\n');process.exit(1);});
