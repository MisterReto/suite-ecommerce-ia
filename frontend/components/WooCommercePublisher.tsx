"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { wakeServices } from "@/lib/service-readiness";

type Selection = { kind: "simple" | "family" | "variant"; sku: string };
type Row = Selection & { name: string; brand: string; category: string; price: string; variants: number; parent_sku: string };
type Options = { images: boolean; stock: boolean; tags: boolean; allow_published_family: boolean };
type Item = { sku: string; name: string; price: string; stock: string; brand: string; category: string;
  tags: string; images: { id: string; name: string }[]; attribute: [string, string] | null };
type Preview = Selection & { parent_sku: string; parent_name: string; items: Item[]; new_status: string };
type Review = { mode: "single" | "batch"; previews: Preview[]; preview_token: string; store: string;
  errors: { selection: Selection; message: string }[]; omitted: Selection[] };
type Job = { id: string; batch_id: string | null; status: string; progress: number; message: string;
  uncertain: boolean; selection: Selection; events: { action: string; sku?: string; id?: number; mensaje?: string }[] };
type Connection = { configured: boolean; images_configured: boolean; missing: string[]; media_missing: string[]; store: string };
type Props = { isAdmin: boolean; online: boolean;
  api: <T>(path: string, method?: string, body?: unknown, timeout?: number) => Promise<T> };
const labels = { simple: "Simple", family: "Familia completa", variant: "Variante" };
const states: Record<string, string> = { queued: "En cola", processing: "Cargando", cancelling: "Deteniendo",
  completed: "Completado", failed: "Fallido", cancelled: "Detenido" };
const active = (job: Job) => ["queued", "processing", "cancelling"].includes(job.status);
const identity = (row: Selection) => row.kind + ":" + row.sku;

export default function WooCommercePublisher({ isAdmin, online, api }: Props) {
  const [connection, setConnection] = useState<Connection>();
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [brands, setBrands] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [kind, setKind] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Row[]>([]);
  const [options, setOptions] = useState<Options>({ images: true, stock: false, tags: false, allow_published_family: false });
  const [review, setReview] = useState<Review>();
  const [confirmed, setConfirmed] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [checkedUncertainty, setCheckedUncertainty] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const submitting = useRef(false);
  const requestKeys = useRef(new Map<string, string>());
  const catalogVersion = useRef(0);

  const attempt = async (action: () => Promise<void>) => {
    if (submitting.current || !online) return;
    submitting.current = true; setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (e) { setError((e as Error).message); }
    finally { submitting.current = false; setBusy(false); }
  };
  const loadCatalog = useCallback(async () => {
    const version = ++catalogVersion.current;
    setCatalogLoading(true);
    const query = new URLSearchParams({ q, brand, category, kind, offset: String(offset), limit: "50" });
    try {
      const result = await api<{ rows: Row[]; total: number; brands: string[]; categories: string[] }>(
        "/api/woocommerce/catalog?" + query, "GET", undefined, 180_000);
      if (version !== catalogVersion.current) return;
      setRows(result.rows); setTotal(result.total); setBrands(result.brands); setCategories(result.categories);
    } finally { if (version === catalogVersion.current) setCatalogLoading(false); }
  }, [q, brand, category, kind, offset, api]);
  const loadJobs = useCallback(async () => {
    const result = await api<{ jobs: Job[] }>("/api/woocommerce/jobs");
    setJobs(result.jobs);
  }, [api]);
  useEffect(() => {
    let stopped = false;
    api<Connection>("/api/woocommerce/connection").then(result => { if (!stopped) setConnection(result); })
      .catch(e => { if (!stopped) setError(e.message); });
    loadJobs().catch(e => { if (!stopped) setError(e.message); });
    return () => { stopped = true; };
  }, [api, loadJobs]);
  useEffect(() => {
    if (!online) return;
    const timer = setTimeout(() => { void loadCatalog().catch(e => setError(e.message)); }, 300);
    return () => clearTimeout(timer);
  }, [loadCatalog, online]);
  const hasActive = jobs.some(active);
  useEffect(() => {
    if (!hasActive || !online) return;
    let stopped = false, reading = false;
    const timer = setInterval(async () => {
      if (reading) return;
      reading = true;
      try {
        wakeServices(true);
        const result = await api<{ jobs: Job[] }>("/api/woocommerce/jobs");
        if (!stopped) setJobs(result.jobs);
      } catch (e) { if (!stopped) setError((e as Error).message); }
      finally { reading = false; }
    }, 4000);
    return () => { stopped = true; clearInterval(timer); };
  }, [hasActive, online, api]);

  const clearReview = () => { setReview(undefined); setConfirmed(false); };
  const toggle = (row: Row) => {
    setSelected(previous => previous.some(item => identity(item) === identity(row))
      ? previous.filter(item => identity(item) !== identity(row)) : [...previous, row]);
    clearReview();
  };
  const changeOption = (name: keyof Options, value: boolean) => {
    setOptions(previous => ({ ...previous, [name]: value })); clearReview();
  };
  const prepare = () => attempt(async () => {
    if (!selected.length) return;
    if (selected.length === 1) {
      const selection = { kind: selected[0].kind, sku: selected[0].sku };
      const result = await api<{ preview: Preview; preview_token: string; store: string }>(
        "/api/woocommerce/preview", "POST", { selection, options }, 330_000);
      setReview({ mode: "single", previews: [result.preview], preview_token: result.preview_token,
        store: result.store, errors: [], omitted: [] });
    } else {
      const result = await api<Omit<Review, "mode">>("/api/woocommerce/batch-preview", "POST",
        { selections: selected.map(({ kind, sku }) => ({ kind, sku })), options }, 330_000);
      setReview({ ...result, mode: "batch" });
    }
    setConfirmed(false);
  });
  const submit = () => attempt(async () => {
    if (!review || !confirmed) return;
    let request_key = requestKeys.current.get(review.preview_token);
    if (!request_key) { request_key = crypto.randomUUID(); requestKeys.current.set(review.preview_token, request_key); }
    wakeServices(true);
    await api(review.mode === "single" ? "/api/woocommerce/jobs" : "/api/woocommerce/batch-jobs", "POST",
      { preview_token: review.preview_token, request_key, confirm: true });
    setConfirmed(false);
    setNotice("Carga en cola. Puedes seguir usando la aplicación; los productos nuevos se crean como borradores.");
    await loadJobs();
  });
  const retry = (job: Job) => attempt(async () => {
    wakeServices(true);
    await api("/api/platform/jobs/" + job.id + "/retry", "POST", { confirm: true,
      request_key: crypto.randomUUID(), uncertainty_reviewed: !!checkedUncertainty[job.id] });
    await loadJobs();
  });
  const disabled = busy || catalogLoading || !online;
  const canSubmit = isAdmin && connection?.configured && (!options.images || connection.images_configured);

  return <div className="wc-publisher" aria-label="Publicación en WooCommerce">
    <section className="p-card">
      <h2>Publicar en WooCommerce</h2>
      <p>Selecciona productos de Sheets y revisa la carga. Las imágenes se relacionan por el SKU real de Drive.</p>
      <p className="p-muted">Productos nuevos: borradores. Productos existentes: se conservan.</p>
      {connection && <p role="status">Tienda: {connection.store || "Pendiente de configurar"} · {connection.configured ? "Configurada" : "Faltan credenciales"}</p>}
      {isAdmin && connection && (!connection.configured || !connection.images_configured) && <details>
        <summary>Configuración de conexión</summary>
        <p>El administrador debe configurar en Render: {[...connection.missing, ...connection.media_missing].join(", ")}.</p>
      </details>}
      {isAdmin && <button type="button" className="button secondary" disabled={disabled || !connection?.configured}
        onClick={() => void attempt(async () => {
          const result = await api<{ message: string }>("/api/woocommerce/connection/test", "POST"); setNotice(result.message);
        })}>Comprobar conexión</button>}
    </section>
    {error && <div className="p-alert danger" role="alert">{error}</div>}
    {notice && <div className="p-alert" role="status">{notice}</div>}
    {(busy || catalogLoading) && <p role="status">Preparando la operación…</p>}
    <section className="p-card">
      <h3>Seleccionar productos</h3>
      <div className="p-toolbar">
        <label className="p-form-field">Buscar por nombre o SKU<input value={q} onChange={e => { setQ(e.target.value); setOffset(0); }} /></label>
        <label className="p-form-field">Categoría<select value={category} onChange={e => { setCategory(e.target.value); setOffset(0); }}>
          <option value="">Todas</option>{categories.map(value => <option key={value}>{value}</option>)}</select></label>
        <label className="p-form-field">Marca<select value={brand} onChange={e => { setBrand(e.target.value); setOffset(0); }}>
          <option value="">Todas</option>{brands.map(value => <option key={value}>{value}</option>)}</select></label>
        <label className="p-form-field">Tipo<select value={kind} onChange={e => { setKind(e.target.value); setOffset(0); }}>
          <option value="">Todos</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      </div>
      <p>{total} resultados · {selected.length} selecciones</p>
      <div className="wc-results">
        {rows.map(row => <label className="wc-row" key={identity(row)}>
          <input type="checkbox" checked={selected.some(item => identity(item) === identity(row))}
            onChange={() => toggle(row)} disabled={disabled} aria-label={"Seleccionar " + labels[row.kind] + " " + row.sku} />
          <span><strong>{row.name}</strong><br /><code>{row.sku}</code> · {labels[row.kind]}
            {row.kind === "family" && " · " + row.variants + " variantes"}<br />
            <small>{row.brand} · {row.category} {row.price && " · " + row.price}</small></span>
        </label>)}
      </div>
      <div className="p-toolbar">
        <button type="button" className="button secondary" disabled={disabled || offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Anterior</button>
        <button type="button" className="button secondary" disabled={disabled || offset + rows.length >= total} onClick={() => setOffset(offset + 50)}>Siguiente</button>
        <button type="button" className="button secondary" disabled={disabled || !rows.length} onClick={() => {
          setSelected(previous => [...previous, ...rows.filter(row => !previous.some(item => identity(item) === identity(row)))]); clearReview();
        }}>Seleccionar página</button>
        <button type="button" className="button secondary" disabled={disabled || !selected.length} onClick={() => { setSelected([]); clearReview(); }}>Limpiar selección</button>
      </div>
      {!!selected.length && <div className="p-toolbar" aria-label="Selección actual">{selected.map(row =>
        <button type="button" className="button secondary" key={identity(row)} disabled={disabled}
          aria-label={"Quitar " + row.sku} onClick={() => toggle(row)}>{row.sku} ×</button>)}</div>}
      <fieldset className="wc-options"><legend>Incluir en la carga</legend>
        <label><input type="checkbox" checked={options.images} onChange={e => changeOption("images", e.target.checked)} disabled={disabled} /> Imágenes</label>
        <label><input type="checkbox" checked={options.stock} onChange={e => changeOption("stock", e.target.checked)} disabled={disabled} /> Inventario</label>
        <label><input type="checkbox" checked={options.tags} onChange={e => changeOption("tags", e.target.checked)} disabled={disabled} /> Etiquetas</label>
      </fieldset>
      <details><summary>Familias ya publicadas</summary><label>
        <input type="checkbox" checked={options.allow_published_family} onChange={e => changeOption("allow_published_family", e.target.checked)} disabled={disabled} />
        Permitir añadir variantes a familias ya publicadas. Estas variantes podrían quedar visibles al crearlas.
      </label></details>
      <button type="button" className="button primary" disabled={disabled || !selected.length || selected.length > 100}
        onClick={() => void prepare()}>Revisar vista previa</button>
      {selected.length > 100 && <p role="alert">Selecciona hasta 100 productos, familias o variantes por lote.</p>}
    </section>
    {review && <section className="p-card" aria-label="Vista previa de la carga">
      <h3>Vista previa</h3><p>{review.store} · {review.previews.length} selecciones · borradores</p>
      {!!review.omitted.length && <p>Se excluyeron {review.omitted.length} selecciones duplicadas o variantes incluidas en una familia seleccionada.</p>}
      {review.errors.map((item, index) => <p role="alert" key={index}>{item.selection.sku}: {item.message}</p>)}
      {review.previews.map(preview => <article key={identity(preview)} className="wc-preview">
        <h4>{preview.parent_name} · {labels[preview.kind]}</h4>
        {preview.items.map(item => <div key={item.sku}>
          <strong>{item.name}</strong> · <code>{item.sku}</code><p>Precio: {item.price} · {item.brand} · {item.category}</p>
          {options.stock && <p>Inventario: {item.stock || "Sin dato"}</p>}
          {options.tags && <p>Etiquetas: {item.tags || "Sin etiquetas"}</p>}
          {item.attribute && <p>{item.attribute[0]}: {item.attribute[1]}</p>}
          {options.images && <p>Imágenes: {item.images.map(image => image.name).join(", ")}</p>}
        </div>)}
      </article>)}
      <label><input type="checkbox" checked={confirmed} disabled={disabled || !!review.errors.length || !canSubmit}
        onChange={e => setConfirmed(e.target.checked)} /> Confirmo esta carga en WooCommerce con las opciones revisadas.</label>
      <button type="button" className="button primary" disabled={disabled || !confirmed || !!review.errors.length || !canSubmit}
        onClick={() => void submit()}>{review.mode === "single" ? "Cargar selección" : "Cargar lote"}</button>
    </section>}
    <section className="p-card">
      <h3>Progreso y resultados</h3>
      <button type="button" className="button secondary" disabled={disabled} onClick={() => void attempt(loadJobs)}>Actualizar cargas</button>
      {!jobs.length && <p>Aún no hay cargas de WooCommerce.</p>}
      {jobs.map(job => <article className="wc-preview" key={job.id}>
        <h4>{job.selection?.sku} · {states[job.status] || job.status}</h4>
        <progress value={job.progress} max={100} aria-label={"Progreso " + job.selection?.sku} />
        <p>{job.message}</p>
        <details><summary>Ver resultados</summary>{job.events.map((event, index) => <p key={index}>
          {event.action} {event.sku} {event.id ? "· ID " + event.id : ""} {event.mensaje}</p>)}</details>
        {job.status === "failed" && isAdmin && <>
          {job.uncertain && <label><input type="checkbox" checked={!!checkedUncertainty[job.id]}
            onChange={e => setCheckedUncertainty(previous => ({ ...previous, [job.id]: e.target.checked }))} />
            Revisé el SKU y los medios en la tienda después de la interrupción.</label>}
          <button type="button" className="button secondary" disabled={disabled || job.uncertain && !checkedUncertainty[job.id]}
            onClick={() => void retry(job)}>Reintentar fallido</button>
        </>}
        {active(job) && isAdmin && <button type="button" className="button secondary" disabled={disabled}
          onClick={() => void attempt(async () => { await api("/api/platform/jobs/" + job.id + "/cancel", "POST", { confirm: true }); await loadJobs(); })}>Detener carga</button>}
      </article>)}
    </section>
  </div>;
}
