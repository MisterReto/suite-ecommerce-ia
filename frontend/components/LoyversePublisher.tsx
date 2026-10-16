"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { wakeServices } from "@/lib/service-readiness";

type Api = <T>(path: string, method?: string, body?: unknown, timeout?: number) => Promise<T>;
type Store = { id: string; name: string };
type Connection = { id: string; name: string; merchant_name: string; stores: Store[];
  default_store_id: string; status: string; checked_at: number };
type Tested = { test_token: string; merchant_name: string; stores: Store[] };
type Selection = { kind: "simple" | "family" | "variant"; sku: string };
type Row = Selection & { name: string; category: string; brand: string; variants: number;
  price: string | number; comparison: string; available?: boolean; deleted?: boolean; parent_sku: string };
type Item = { sku: string; name: string; price: number; barcode: string; description: string;
  category: string; brand: string; attribute: [string, string] | null; action: string;
  image_name: string | null; image_url?: string };
type Review = { preview_token: string; previews: (Selection & { parent_name: string; items: Item[] })[];
  errors: { selection: Selection; message: string }[]; omitted: Selection[];
  connection_name: string; merchant_name: string; store_name: string };
type Job = { id: string; batch_id: string; selection: Selection; status: string; progress: number;
  connection_name: string; store_name: string; message: string; uncertain: boolean; attempts: number;
  log_saved: boolean; pause_requested: boolean; events: { action: string; sku: string; message: string }[] };
const kinds: Record<Selection["kind"], string> = { simple: "Simple", family: "Familia completa", variant: "Variante" };
const comparisonLabels: Record<string, string> = { existing: "Ya existe", missing: "Falta", partial: "Familia parcial" };
const states: Record<string, string> = { queued: "En cola", processing: "Publicando", paused: "En pausa",
  cancelling: "Deteniendo", cancelled: "Cancelado", failed: "Fallido", completed: "Completado" };
const identity = (row: Selection) => row.kind + ":" + row.sku;
const active = (job: Job) => ["queued", "processing", "cancelling"].includes(job.status);

export default function LoyversePublisher({ api, isAdmin, online }: { api: Api; isAdmin: boolean; online: boolean }) {
  const [tab, setTab] = useState("catalog");
  const [connections, setConnections] = useState<Connection[]>([]);
  const [connectionId, setConnectionId] = useState("");
  const [storeId, setStoreId] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [token, setToken] = useState("");
  const [tested, setTested] = useState<Tested>();
  const [defaultStore, setDefaultStore] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [brands, setBrands] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [kind, setKind] = useState("");
  const [comparison, setComparison] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Row[]>([]);
  const [images, setImages] = useState(true);
  const [createCategories, setCreateCategories] = useState(false);
  const [review, setReview] = useState<Review>();
  const [confirmation, setConfirmation] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobsPage, setJobsPage] = useState(0);
  const [jobsTotal, setJobsTotal] = useState(0);
  const [jobsSummary, setJobsSummary] = useState<Record<string, number>>({});
  const [pendingControl, setPendingControl] = useState<{ job: Job; action: "resume" | "retry" }>();
  const [deleting, setDeleting] = useState<Connection>();
  const [busy, setBusy] = useState(false);
  const [reading, setReading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const guard = useRef(false);
  const revision = useRef(0);
  const jobsRevision = useRef(0);
  const requestKeys = useRef(new Map<string, string>());
  const destination = connections.find(c => c.id === connectionId);
  const disabled = busy || !online;
  const clearReview = () => { setReview(undefined); setConfirmation(""); };

  const attempt = async (action: () => Promise<void>) => {
    if (guard.current || !online) return;
    guard.current = true; setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (e) { setError((e as Error).message); }
    finally { guard.current = false; setBusy(false); }
  };
  const loadConnections = useCallback(async () => {
    const result = await api<{ connections: Connection[] }>("/api/loyverse/connections");
    setConnections(result.connections);
  }, [api]);
  const loadJobs = useCallback(async (page = jobsPage) => {
    const version = ++jobsRevision.current;
    const result = await api<{ jobs: Job[]; total: number; summary: Record<string, number> }>(
      "/api/loyverse/jobs?offset=" + page * 50 + "&limit=50");
    if (version === jobsRevision.current) {
      setJobs(result.jobs); setJobsTotal(result.total); setJobsSummary(result.summary);
    }
  }, [api, jobsPage]);
  useEffect(() => {
    void loadConnections().catch(e => setError(e.message));
  }, [loadConnections]);
  useEffect(() => {
    void loadJobs().catch(e => setError(e.message));
  }, [loadJobs]);
  useEffect(() => {
    if (!connections.some(c => c.id === connectionId)) {
      setConnectionId(connections[0]?.id || ""); setStoreId(connections[0]?.default_store_id || "");
    }
  }, [connections, connectionId]);
  useEffect(() => {
    ++revision.current; setRows([]); setSelected([]); setReview(undefined); setConfirmation(""); setOffset(0);
  }, [connectionId, storeId]);
  const loadCatalog = useCallback(async (refresh = false) => {
    if (!connectionId || !storeId || !["catalog", "remote"].includes(tab)) return;
    const version = ++revision.current; setReading(true);
    const query = new URLSearchParams({ connection_id: connectionId, store_id: storeId,
      q, category, brand: tab === "remote" ? "" : brand, kind: tab === "remote" ? "" : kind,
      comparison: tab === "remote" ? "" : comparison, remote: String(tab === "remote"),
      offset: String(offset), limit: "50", refresh: String(refresh) });
    try {
      const result = await api<{ rows: Row[]; total: number; brands: string[]; categories: string[]; summary: Record<string, number> }>(
        "/api/loyverse/catalog?" + query, "GET", undefined, 240_000);
      if (version === revision.current) {
        setRows(result.rows); setTotal(result.total); setBrands(result.brands); setCategories(result.categories); setSummary(result.summary);
      }
    } finally { if (version === revision.current) setReading(false); }
  }, [connectionId, storeId, tab, q, category, brand, kind, comparison, offset, api]);
  useEffect(() => {
    if (!online) return;
    const timer = setTimeout(() => void loadCatalog().catch(e => setError(e.message)), 350);
    return () => clearTimeout(timer);
  }, [loadCatalog, online]);
  const hasActive = jobs.some(active) || ["queued", "processing", "cancelling"].some(s => (jobsSummary[s] || 0) > 0);
  useEffect(() => {
    if (!hasActive || !online) return;
    let fetching = false;
    const timer = setInterval(async () => {
      if (fetching) return;
      fetching = true;
      try { wakeServices(true); await loadJobs(); } catch (e) { setError((e as Error).message); }
      finally { fetching = false; }
    }, 5000);
    return () => clearInterval(timer);
  }, [hasActive, online, loadJobs]);
  const toggle = (row: Row) => {
    setSelected(previous => previous.some(s => identity(s) === identity(row))
      ? previous.filter(s => identity(s) !== identity(row)) : [...previous, row]); clearReview();
  };
  const sendControl = async (job: Job, action: string, confirmed = "") => {
    await api("/api/loyverse/jobs/" + job.id + "/control", "POST", { action, confirmation: confirmed }); await loadJobs();
  };
  const prepare = () => attempt(async () => {
    clearReview();
    const result = await api<Review>("/api/loyverse/preview", "POST", { connection_id: connectionId,
      store_id: storeId, selections: selected.map(({ kind, sku }) => ({ kind, sku })),
      options: { images, create_categories: createCategories } }, 330_000);
    setReview(result);
  });
  const publish = () => attempt(async () => {
    if (!review || confirmation !== "PUBLICAR") return;
    let key = requestKeys.current.get(review.preview_token);
    if (!key) { key = crypto.randomUUID(); requestKeys.current.set(review.preview_token, key); }
    await api("/api/loyverse/jobs", "POST", { preview_token: review.preview_token, request_key: key, confirmation });
    clearReview(); setSelected([]); setJobsPage(0); await loadJobs(0); setTab("jobs"); setNotice("Lote guardado en cola para la cuenta y sucursal revisadas.");
  });

  return <div className="ly-publisher" aria-label="Loyverse POS">
    <section className="p-card">
      <h2>Loyverse POS</h2>
      <p>Compara Google Sheets y publica artículos con su imagen principal.</p>
      <p className="p-muted">El catálogo se comparte entre sucursales de una misma cuenta. La sucursal elegida determina dónde estarán disponibles las variantes nuevas. La sincronización automática de inventario está desactivada.</p>
      <div className="ly-destination">
        <label className="p-form-field">Conexión<select value={connectionId} disabled={disabled}
          onChange={e => { setConnectionId(e.target.value); setStoreId(connections.find(c => c.id === e.target.value)?.default_store_id || ""); }}>
          <option value="">Selecciona una conexión</option>{connections.map(c => <option key={c.id} value={c.id}>{c.name} · {c.merchant_name}</option>)}</select></label>
        <label className="p-form-field">Sucursal de destino<select value={storeId} disabled={disabled || !destination}
          onChange={e => setStoreId(e.target.value)}><option value="">Selecciona una sucursal</option>
          {destination?.stores.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      </div>
      <div className="ly-tabs" role="group" aria-label="Herramientas Loyverse">{[
        ["catalog", "Comparar y publicar"], ["remote", "Catálogo Loyverse"], ["jobs", "Progreso y resultados"], ["connections", "Configuración de conexiones"],
      ].map(([value, label]) => <button type="button" key={value} className={"button " + (tab === value ? "primary" : "secondary")}
        aria-pressed={tab === value} onClick={() => { ++revision.current; setTab(value); setRows([]); setOffset(0); setCategory(""); }}>{label}</button>)}</div>
    </section>
    {error && <div className="p-alert danger" role="alert">{error}</div>}
    {notice && <div className="p-alert" role="status">{notice}</div>}
    {(busy || reading) && <p role="status">Preparando la operación…</p>}
    {!connections.length && tab !== "connections" && <section className="p-card"><p>Agrega y prueba una conexión para comenzar.</p>
      <button type="button" className="button primary" onClick={() => setTab("connections")}>Configurar Loyverse</button></section>}

    {tab === "connections" && <section className="p-card"><h3>Configuración de conexiones</h3>
      <p>Cada conexión es personal y permite elegir cualquiera de las sucursales de esa cuenta.</p>
      {connections.map(c => <article key={c.id} className="ly-result"><h4>{c.name}</h4>
        <p>{c.merchant_name} · {c.stores.length} sucursales · {c.status === "connected" ? "Conexión verificada" : "Requiere revisión"}</p>
        <small>Última prueba: {new Date(c.checked_at * 1000).toLocaleString("es-MX")}</small>
        {isAdmin && <div className="p-toolbar"><button type="button" className="button secondary" disabled={disabled} onClick={() => {
          setEditing(c.id); setName(c.name); setToken(""); setTested(undefined); setDefaultStore(c.default_store_id);
        }}>Editar o volver a probar</button><button type="button" className="button secondary" disabled={disabled} onClick={() => setDeleting(c)}>Eliminar conexión</button></div>}
      </article>)}
      {deleting && <div className="p-alert" role="alert"><p>¿Eliminar la conexión {deleting.name}? Sus trabajos pendientes se detendrán.</p>
        <button type="button" className="button secondary" disabled={disabled} onClick={() => setDeleting(undefined)}>Volver</button>{" "}
        <button type="button" className="button primary" disabled={disabled} onClick={() => void attempt(async () => {
          await api("/api/loyverse/connections/" + deleting.id, "DELETE"); setDeleting(undefined); clearReview(); await loadConnections(); await loadJobs();
        })}>Confirmar eliminación</button></div>}
      {isAdmin ? <div className="ly-connection-form"><h4>{editing ? "Actualizar conexión" : "Agregar conexión"}</h4>
        <label className="p-form-field">Nombre de la conexión<input value={name} maxLength={80} onChange={e => setName(e.target.value)} placeholder="Cuenta Rincón de Asia" /></label>
        <label className="p-form-field">{editing ? "Token nuevo (opcional)" : "Token API de Loyverse"}<input type="password" value={token}
          autoComplete="new-password" spellCheck={false} onChange={e => { setToken(e.target.value); setTested(undefined); }} /></label>
        <p className="p-muted">El token se guarda cifrado. No volverá a mostrarse después de guardarlo.</p>
        <div className="p-toolbar"><button type="button" className="button secondary" disabled={disabled || !token && !editing} onClick={() => void attempt(async () => {
          try {
            const result = await api<Tested>("/api/loyverse/connections/test", "POST", { token: token || null, connection_id: editing }, 120_000);
            setTested(result); setDefaultStore(previous => result.stores.some(s => s.id === previous) ? previous : result.stores[0]?.id || "");
          } finally { setToken(""); }
        })}>Probar conexión y consultar sucursales</button>
        {editing && <button type="button" className="button secondary" disabled={disabled} onClick={() => { setEditing(null); setName(""); setToken(""); setTested(undefined); }}>Agregar otra cuenta</button>}</div>
        {tested && <><p role="status">Conexión correcta: {tested.merchant_name}</p>
          <label className="p-form-field">Sucursal predeterminada<select value={defaultStore} onChange={e => setDefaultStore(e.target.value)}>
            {tested.stores.map(s => <option value={s.id} key={s.id}>{s.name}</option>)}</select></label>
          <button type="button" className="button primary" disabled={disabled || !name.trim() || !defaultStore} onClick={() => void attempt(async () => {
            const result = await api<{ connection: Connection }>("/api/loyverse/connections", "POST", {
              test_token: tested.test_token, name, store_id: defaultStore, connection_id: editing });
            await loadConnections(); setConnectionId(result.connection.id); setStoreId(defaultStore);
            setTested(undefined); setEditing(null); setName(""); setNotice("Conexión guardada.");
          })}>Guardar conexión verificada</button></>}
      </div> : <p>Solo los administradores pueden administrar conexiones y publicar.</p>}
    </section>}

    {["catalog", "remote"].includes(tab) && destination && <section className="p-card">
      <h3>{tab === "catalog" ? "Comparar Sheets con Loyverse" : "Artículos existentes en Loyverse"}</h3>
      {tab === "catalog" && <p>{summary.existing || 0} existentes · {summary.missing || 0} faltantes · {summary.partial || 0} familias parciales</p>}
      <div className="ly-filters">
        <label className="p-form-field">Buscar por nombre o SKU<input value={q} onChange={e => { setQ(e.target.value); setOffset(0); }} /></label>
        <label className="p-form-field">Categoría<select value={category} onChange={e => { setCategory(e.target.value); setOffset(0); }}>
          <option value="">Todas</option>{categories.map(c => <option key={c}>{c}</option>)}</select></label>
        {tab === "catalog" && <><label className="p-form-field">Marca<select value={brand} onChange={e => { setBrand(e.target.value); setOffset(0); }}>
          <option value="">Todas</option>{brands.map(b => <option key={b}>{b}</option>)}</select></label>
          <label className="p-form-field">Tipo<select value={kind} onChange={e => { setKind(e.target.value); setOffset(0); }}>
            <option value="">Todos</option>{Object.entries(kinds).map(([v, label]) => <option value={v} key={v}>{label}</option>)}</select></label>
          <label className="p-form-field">Comparación<select value={comparison} onChange={e => { setComparison(e.target.value); setOffset(0); }}>
            <option value="">Todos</option>{Object.entries(comparisonLabels).map(([v, label]) => <option value={v} key={v}>{label}</option>)}</select></label></>}
      </div>
      <div className="p-toolbar"><button type="button" className="button secondary" disabled={disabled || reading} onClick={() => void attempt(() => loadCatalog(true))}>Actualizar comparación</button>
        {tab === "catalog" && <button type="button" className="button secondary" disabled={disabled || !isAdmin} onClick={() => {
          setSelected(previous => [...previous, ...rows.filter(r => !previous.some(p => identity(p) === identity(r)))]); clearReview();
        }}>Seleccionar página</button>}</div>
      <p>{total} resultados{tab === "catalog" && " · " + selected.length + " selecciones"}</p>
      {!reading && !rows.length && <p>No hay productos que coincidan con estos filtros.</p>}
      {rows.map((row, index) => <article className="ly-result" key={row.sku + ":" + index}>
        <div className="ly-product-row">{tab === "catalog" && <input type="checkbox" aria-label={"Seleccionar " + row.sku} disabled={disabled || !isAdmin}
          checked={selected.some(s => identity(s) === identity(row))} onChange={() => toggle(row)} />}
          <div><strong>{row.name}</strong><p><code>{row.sku || "Sin SKU"}</code>{row.kind && " · " + kinds[row.kind]}</p>
            <small>{row.brand} {row.category} · {row.price ?? "Sin precio"}</small>
            {tab === "catalog" ? <p>{comparisonLabels[row.comparison]}{row.kind === "family" && " · " + row.variants + " variantes"}</p>
              : <p>{row.deleted ? "Eliminado en Loyverse" : row.available ? "Disponible en esta sucursal" : "No disponible en esta sucursal"}</p>}
          </div></div></article>)}
      <div className="p-toolbar"><button type="button" className="button secondary" disabled={disabled || offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Anterior</button>
        <button type="button" className="button secondary" disabled={disabled || offset + rows.length >= total} onClick={() => setOffset(offset + 50)}>Siguiente</button></div>
      {tab === "catalog" && <><div className="ly-selected">{selected.map(s => <button type="button" key={identity(s)} className="button secondary" disabled={disabled} onClick={() => toggle(s)} aria-label={"Quitar " + s.sku}>{s.sku} ×</button>)}</div>
        <fieldset className="ly-options"><legend>Preparar publicación</legend>
          <label><input type="checkbox" checked={images} disabled={disabled} onChange={e => { setImages(e.target.checked); clearReview(); }} /> Incluir imagen principal de Drive</label>
          <label><input type="checkbox" checked={createCategories} disabled={disabled} onChange={e => { setCreateCategories(e.target.checked); clearReview(); }} /> Crear categorías faltantes</label>
        </fieldset><p className="p-muted">Se conservarán precios y existencias de artículos existentes. Las variantes faltantes se agregan a su familia.</p>
        <button type="button" className="button primary" disabled={disabled || !isAdmin || !selected.length || selected.length > 300} onClick={() => void prepare()}>Revisar datos e imágenes</button>
        {selected.length > 300 && <p role="alert">Selecciona hasta 300 productos, familias o variantes por lote.</p>}</>}
    </section>}

    {review && tab === "catalog" && <section className="p-card" aria-label="Vista previa Loyverse"><h3>Revisar publicación real</h3>
      <p><strong>{review.connection_name}</strong> · {review.merchant_name} · Sucursal: <strong>{review.store_name}</strong></p>
      <div className="p-alert"><p>Loyverse no tiene borradores. Los artículos se crearán en el catálogo de esta cuenta y las variantes nuevas quedarán disponibles en la sucursal elegida. Las demás sucursales conservarán los artículos que ya tenían.</p></div>
      {!!review.omitted.length && <p>Se omitieron variantes ya incluidas en familias seleccionadas.</p>}
      {review.errors.map((e, i) => <p key={i} role="alert">{e.selection.sku}: {e.message}</p>)}
      {review.previews.map(p => <article key={identity(p)} className="ly-result"><h4>{p.parent_name} · {kinds[p.kind]}</h4>
        {p.items.map(item => <div key={item.sku} className="ly-preview-item">
          {item.image_url && <img src={item.image_url} width={160} height={160} loading="lazy" alt={"Imagen principal de " + item.sku} />}
          <div><strong>{item.name}</strong><p>SKU: {item.sku} · {item.action === "create" ? "Se creará" : "Ya existe; se conservará"}</p>
            <p>Precio nuevo: {item.price} · Código de barras: {item.barcode || "Sin código"}</p><p>{item.brand} · {item.category}</p>
            {item.attribute && <p>{item.attribute[0]}: {item.attribute[1]}</p>}
            <details><summary>Descripción</summary><p className="ly-description">{item.description || "Sin descripción"}</p></details>
            <p>{images ? item.image_name || "Sin imagen nueva para este artículo" : "Publicación sin imagen"}</p></div>
        </div>)}</article>)}
      {isAdmin && <><label className="p-form-field">Escribe PUBLICAR para confirmar estos artículos y su destino<input value={confirmation} autoComplete="off" disabled={disabled} onChange={e => setConfirmation(e.target.value)} /></label>
        <button type="button" className="button primary" disabled={disabled || confirmation !== "PUBLICAR" || !!review.errors.length || !review.previews.length} onClick={() => void publish()}>Confirmar y publicar selección</button></>}
    </section>}

    {tab === "jobs" && <section className="p-card"><h3>Progreso y resultados</h3>
      <button type="button" className="button secondary" disabled={disabled} onClick={() => void attempt(() => loadJobs())}>Actualizar trabajos</button>
      <p>{jobsTotal} trabajos · {jobsSummary.completed || 0} completados · {jobsSummary.failed || 0} fallidos · {(jobsSummary.queued || 0) + (jobsSummary.processing || 0)} pendientes</p>
      <div className="p-toolbar" aria-label="Páginas de resultados Loyverse">
        <button type="button" className="button secondary" disabled={disabled || jobsPage === 0} onClick={() => setJobsPage(p => p - 1)}>Trabajos anteriores</button>
        <span>Página {jobsPage + 1} de {Math.max(1, Math.ceil(jobsTotal / 50))}</span>
        <button type="button" className="button secondary" disabled={disabled || (jobsPage + 1) * 50 >= jobsTotal} onClick={() => setJobsPage(p => p + 1)}>Más resultados</button>
      </div>
      {!jobs.length && <p>Aún no hay publicaciones de Loyverse.</p>}
      {pendingControl && <div className="p-alert"><p>{pendingControl.action === "retry" ? "Reintentar" : "Reanudar"} {pendingControl.job.selection.sku} en {pendingControl.job.connection_name} / {pendingControl.job.store_name}.</p>
        <p>Se comprobarán de nuevo los SKU antes de crear artículos o variantes faltantes.</p>
        <label className="p-form-field">Escribe PUBLICAR<input value={confirmation} onChange={e => setConfirmation(e.target.value)} /></label>
        <button type="button" className="button primary" disabled={disabled || confirmation !== "PUBLICAR"} onClick={() => void attempt(async () => {
          await sendControl(pendingControl.job, pendingControl.action, confirmation); setPendingControl(undefined); setConfirmation("");
        })}>Confirmar {pendingControl.action === "retry" ? "reintento" : "reanudación"}</button>{" "}
        <button type="button" className="button secondary" onClick={() => { setPendingControl(undefined); setConfirmation(""); }}>Volver</button></div>}
      {jobs.map(job => <article key={job.id} className="ly-result"><h4>{job.selection.sku} · {states[job.status] || job.status}</h4>
        <p>{job.connection_name} · {job.store_name}</p><progress value={job.progress} max={100} aria-label={"Progreso " + job.selection.sku} />
        <p>{job.message}</p><p>Intento {job.attempts} de 3{job.pause_requested && active(job) ? " · Pausa solicitada" : ""}</p>
        {job.uncertain && <p>Una operación perdió su respuesta. El reintento consultará primero el catálogo completo.</p>}
        <details><summary>Resultados y errores</summary>{job.events.map((e, i) => <p key={i}>{e.sku} · {e.message}</p>)}
          <p>{job.log_saved ? "Registro guardado también en Google Drive." : "Registro conservado en la aplicación."}</p>
          <a className="button secondary" href={"/api/loyverse/jobs/" + job.id + "/log"}>Descargar registro</a></details>
        {isAdmin && <div className="p-toolbar">{["queued", "processing"].includes(job.status) && <button type="button" className="button secondary" disabled={disabled || job.pause_requested}
          onClick={() => void attempt(() => sendControl(job, "pause"))}>Pausar</button>}
          {(active(job) || job.status === "paused") && <button type="button" className="button secondary" disabled={disabled} onClick={() => void attempt(() => sendControl(job, "cancel"))}>Cancelar pendientes</button>}
          {(job.status === "paused" || job.status === "failed" && job.attempts < 3) && <button type="button" className="button secondary" disabled={disabled}
            onClick={() => { setPendingControl({ job, action: job.status === "paused" ? "resume" : "retry" }); setConfirmation(""); }}>{job.status === "paused" ? "Reanudar" : "Reintentar fallido"}</button>}
        </div>}
      </article>)}
    </section>}
  </div>;
}
