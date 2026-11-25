"use client";

import { useEffect, useRef, useState } from "react";

type Api = <T>(path: string, method?: string, body?: unknown) => Promise<T>;
type Row = { key?: string; sku: string; category: string; outcome?: string; remote_status?: string };
type Job = { id: string; status: string; progress: number; mode: "preview" | "apply"; message: string;
  counts: Record<string, number>; rows?: Row[]; more?: boolean };
const base = "/api/woocommerce/reconciliation";
const labels: Record<string,string> = { match:"Coinciden", missing:"Faltan en WooCommerce",
  remove:"Bajas propuestas · mover a borrador", publish_local:"Marcar publicado en la app",
  unpublish_local:"Quitar estado publicado en la app", conflict:"Coincidencia ambigua o SKU duplicado",
  independent:"Solo en WooCommerce", unverified:"Sin evidencia de creación por la app",
  orphan:"Revisar variante o padre", retired:"Baja ya aplicada", family_review:"Revisar familia con variantes",
  review:"Revisión manual", changed:"Aplicado", stale:"Cambió desde la vista previa", uncertain:"Verificar resultado en WooCommerce",
  queued:"En cola", processing:"En proceso", cancelling:"Deteniendo", cancelled:"Cancelado", failed:"Fallido", completed:"Terminado" };
const eligible = (category: string) => ["remove","publish_local","unpublish_local"].includes(category);
const active = (job?: Job) => !!job && ["queued","processing","cancelling"].includes(job.status);

export default function WooCommerceReconciliation({api,online}:{api: Api; online: boolean}) {
  const [job,setJob] = useState<Job>();
  const [page,setPage] = useState(0);
  const [last,setLast] = useState<string | null>(null);
  const [keys,setKeys] = useState<string[]>([]);
  const [all,setAll] = useState(false);
  const [confirm,setConfirm] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const client = useRef(api);
  client.current = api;
  useEffect(() => {
    let live = true;
    if (online) client.current<{job: Job | null; last_sync:string | null}>(base).then(result => {
      if (live) { setJob(result.job || undefined); setLast(result.last_sync); }
    }).catch(e => { if (live) setError(e.message); });
    return () => { live=false; };
  },[online]);
  const id = job?.id, status = job?.status;
  useEffect(() => {
    if (!id || !online) return;
    let live=true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const result = await client.current<Job>(base+"/"+id+"?page="+page);
        if (live) {
          setJob(result); setError("");
          if (result.mode==="apply" && result.status==="completed") {
            const info = await client.current<{last_sync:string | null}>(base);
            if (live) setLast(info.last_sync);
          }
          if (active(result)) timer=setTimeout(refresh,5000);
        }
      } catch(e) {
        if (live) { setError((e as Error).message); if (["queued","processing","cancelling"].includes(status || "")) timer=setTimeout(refresh,10000); }
      }
    }
    void refresh();
    return () => { live=false; clearTimeout(timer); };
  },[id,page,online,status]);
  useEffect(() => {
    if (confirm) dialog.current?.showModal();
    else dialog.current?.close();
  },[confirm]);
  async function submit(path:string,body?:unknown) {
    if (busy) return;
    setBusy(true); setError(""); setConfirm(false);
    try {
      const result=await api<Job>(path,"POST",body);
      setJob(result); setPage(0); setKeys([]); setAll(false);
    } catch(e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const canReview = job?.mode==="preview" && job.status==="completed" && !!job.rows;
  const total = Object.values(job?.counts || {}).reduce((n,v)=>n+v,0);
  const available = Object.entries(job?.counts || {}).reduce((n,[k,v])=>n+(eligible(k)?v:0),0);
  return <section className="p-card" aria-label="Sincronización del catálogo">
    <button className="button" disabled={!online || busy || active(job)} onClick={()=>void submit(base)}>Sincronizar catálogo con WooCommerce</button>
    <p className="p-muted">La vista previa compara el catálogo. Las bajas confirmadas pasan a borrador en la tienda.</p>
    <p>Última sincronización aplicada: {last ? new Date(last).toLocaleString("es-MX") : "Sin registro"}</p>
    {error && <p role="alert" className="p-alert danger">{error}</p>}
    {job && <>
      <h3>{job.mode==="preview" ? "Vista previa" : "Resultado de sincronización"} · {labels[job.status] || job.status}</h3>
      {active(job) && <><progress max={100} value={job.progress} aria-label="Avance de la sincronización"/>
        <button className="button secondary" disabled={busy || job.status==="cancelling"} onClick={()=>void submit(base+"/"+job.id+"/cancel")}>Cancelar sincronización</button></>}
      {(active(job) || job.status==="failed") && <p role="status">{job.message}</p>}
      {!!total && <><p>{job.mode==="preview" ? "Registros analizados" : "Resultados registrados"}: {total}</p>
        <ul>{Object.entries(job.counts).map(([k,v])=><li key={k}>{labels[k] || k}: {v}</li>)}</ul></>}
      {job.rows?.map((row,i)=><p key={row.key || i}>
        {canReview && eligible(row.category) && row.key && <input type="checkbox" aria-label={"Seleccionar "+row.sku}
          disabled={all || busy} checked={all || keys.includes(row.key)} onChange={e=>setKeys(old=>e.target.checked?[...old,row.key!]:old.filter(x=>x!==row.key))}/>}
        {" "}<strong>{row.sku || "Sin SKU"}</strong> · {labels[row.category]}{row.outcome && " · "+labels[row.outcome]}</p>)}
      {(page>0 || job.more) && <div className="p-toolbar">
        <button disabled={page===0} onClick={()=>setPage(page-1)}>Anterior</button><span>Página {page+1}</span>
        <button disabled={!job.more} onClick={()=>setPage(page+1)}>Siguiente</button></div>}
      {canReview && available>0 && <><label><input type="checkbox" checked={all} onChange={e=>setAll(e.target.checked)}/> Seleccionar todos los cambios elegibles ({available})</label>
        <button className="button secondary" disabled={busy || (!all && !keys.length)} onClick={()=>setConfirm(true)}>Revisar selección</button></>}
    </>}
    <dialog ref={dialog} onCancel={()=>setConfirm(false)}>
      <h3>Confirmar cambios de catálogo</h3><p>Aplicar {all ? available : keys.length} cambios seleccionados. Cada baja seleccionada moverá ese producto a borrador en WooCommerce. Los ajustes de publicación se guardarán en la app.</p>
      <div className="p-toolbar"><button autoFocus onClick={()=>setConfirm(false)}>Volver</button>
        <button className="button" disabled={busy} onClick={()=>job && void submit(base+"/"+job.id+"/apply",{confirm:true,all,keys:all?[]:keys})}>Confirmar y aplicar</button></div>
    </dialog>
  </section>;
}
