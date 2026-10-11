"use client";
// Herramientas nativas: reutilizan las APIs establecidas, con confirmación antes de escribir.
// La publicación se pausa entre grupos; ninguna respuesta perdida se reintenta sola.
import { useEffect, useRef, useState } from "react";
import { Loader2, Play, Square } from "lucide-react";

type Tool = "count" | "media" | "publication";
type Row = {
  sku: string; nombre_producto: string; Marca: string; categorias: string;
  Existencias: number; precio: number; counted: boolean; variable_parent: boolean;
};
type Inventory = {
  rows: Row[]; total: number; pending: number; movement_types: string[];
  summary: { products: number; units: number; retail_value: number; low_stock: number; out_of_stock: number };
};
type History = { timestamp: string; tipo: string; cantidad: number; stock_anterior: number;
  stock_nuevo: number; motivo: string; referencia: string; usuario: string };
type Review = { rows: { sku: string; name: string; status: string; inventory_stock: number | null;
  woocommerce_stock: number | null; inventory_price: number | null; woocommerce_price: number | null }[];
  summary: Record<string, number> };
type Media = { rows: { sku: string; name: string; ready: boolean; wc_id?: number;
  images: { requested_filename: string; resolved_filename: string; resolution: string }[] }[];
  summary: Record<string, number>; woocommerce_write: boolean; wordpress_write: boolean; wordpress_configured: boolean };
type Batch = { batch_id: string; processing: boolean;
  summary: { total: number; success: number; error: number; pending: number; running: number };
  rows: { position: number; sku: string; status: string; message: string; permalink?: string }[] };
type Confirmation = { title: string; text: string; label: string; action: () => Promise<void> };
type Props = {
  tool: Tool; namespace: string; canEdit: boolean; isAdmin: boolean; online: boolean;
  api: <T>(path: string, method?: string, body?: unknown, timeout?: number) => Promise<T>;
  ask: (confirmation: Confirmation) => void;
};
const money = (n: number | null) => n == null ? "—" : new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(n);

export default function InventoryTools({ tool, namespace, canEdit, isAdmin, online, api, ask }: Props) {
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [inventory, setInventory] = useState<Inventory>();
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<string[]>([]);
  const [sku, setSku] = useState("");
  const [history, setHistory] = useState<History[]>([]);
  const [review, setReview] = useState<Review>();
  const [media, setMedia] = useState<Media>();
  const [movement, setMovement] = useState({ movement_type: "Entrada", quantity: 0, reason: "", reference: "" });
  const [batchId, setBatchId] = useState("");
  const [batch, setBatch] = useState<Batch>();
  const [batchState, setBatchState] = useState("Pausado");
  const [running, setRunning] = useState(false);
  const pause = useRef(true);
  const mounted = useRef(true);
  const activeTool = useRef(tool);
  const batchRunning = useRef(false);
  const [options, setOptions] = useState({ mode: "10", custom: "", workers: 1,
    include_images: false, include_stock: false, skip_processed: true });
  const storageKey = "rincon-publication:" + namespace;
  const disabled = busy || !online;

  useEffect(() => {
    mounted.current = true;
    try { setBatchId(localStorage.getItem(storageKey) || ""); } catch {}
    return () => { mounted.current = false; pause.current = true; };
  }, [storageKey]);
  useEffect(() => {
    activeTool.current = tool;
    // Leaving this tool prevents the next write, even while the current HTTP wave finishes.
    if (tool !== "publication") pause.current = true;
  }, [tool]);
  useEffect(() => { if (!online) pause.current = true; }, [online]);

  const request = <T,>(operation: string, method = "GET", body?: unknown) =>
    api<T>("/api/tools/" + operation, method, body, 330_000);
  const attempt = async (action: () => Promise<void>) => {
    if (submitting.current || !online) return;
    submitting.current = true; setBusy(true); setError(""); setNotice("");
    try { await action(); } catch (e) { if (mounted.current) setError((e as Error).message); }
    finally { submitting.current = false; if (mounted.current) setBusy(false); }
  };
  const loadInventory = async () => {
    const data = await request<Inventory>("inventory?q=" + encodeURIComponent(query));
    setInventory(data); setCounts(Object.fromEntries(data.rows.filter(r => !r.variable_parent).map(r => [r.sku, r.Existencias])));
    setSelected([]);
  };
  const inspectHistory = async (value: string) => {
    setSku(value);
    const data = await request<{ rows: History[] }>("history?sku=" + encodeURIComponent(value));
    setHistory(data.rows);
  };
  const refreshBatch = async (id: string) => {
    const data = await request<Batch>("batch-status?batch_id=" + encodeURIComponent(id));
    if (mounted.current) setBatch(data);
    return data;
  };
  const runBatch = async (id: string) => {
    if (batchRunning.current || !mounted.current || activeTool.current !== "publication") return;
    batchRunning.current = true; pause.current = false; setRunning(true); setBatchState("Procesando");
    try {
      while (!pause.current && mounted.current && activeTool.current === "publication") {
        const state = await refreshBatch(id);
        if (!state.summary.pending && !state.summary.running) { setBatchState("Terminado"); break; }
        // A pause during the status read must also block the following write.
        if (pause.current || !mounted.current || activeTool.current !== "publication") break;
        const result = await request<{ done: boolean }>("batch-step", "POST", { confirm: true, batch_id: id });
        await refreshBatch(id);
        if (result.done) { if (mounted.current) setBatchState("Terminado"); break; }
      }
      if (pause.current && mounted.current) setBatchState("Pausado");
    } catch (e) {
      pause.current = true;
      if (mounted.current) { setBatchState("Pausado: revisa el resultado antes de reanudar"); throw e; }
    } finally { batchRunning.current = false; if (mounted.current) setRunning(false); }
  };
  const confirm = (title: string, text: string, label: string, action: () => Promise<void>) =>
    ask({ title, text, label, action: async () => {
      // Parent confirmation clears promptly; progress and pause remain in this native panel.
      void attempt(action);
    } });

  return <div className="p-native-tools" aria-label="Herramientas integradas">
    {error && <div className="p-alert danger" role="alert">{error}</div>}
    {notice && <div className="p-alert" role="status">{notice}</div>}
    {busy && <p role="status"><Loader2 className="spin" size={18} /> {running ? "Procesando el grupo actual…" : "Consultando servidor…"}</p>}
    {tool === "count" && <>
      <section className="p-card">
        <h2>Conteo y movimientos de Drive</h2>
        <p className="p-muted">Registra existencias físicas en tu inventario conectado. Las portadas no tienen stock propio.</p>
        <form className="p-toolbar" onSubmit={e => { e.preventDefault(); void attempt(loadInventory); }}>
          <label className="p-form-field">Buscar en Drive<input value={query} onChange={e => setQuery(e.target.value)} placeholder="SKU, producto, marca o categoría" /></label>
          <button className="button secondary" disabled={disabled}>Cargar inventario de Drive</button>
        </form>
        {inventory && <>
          <div className="p-tool-metrics">
            <p><strong>{inventory.summary.products}</strong> productos</p><p><strong>{inventory.summary.units}</strong> unidades</p>
            <p><strong>{inventory.pending}</strong> pendientes de conteo</p><p><strong>{money(inventory.summary.retail_value)}</strong> valor de venta</p>
          </div>
          <p className="p-muted">{inventory.rows.length} de {inventory.total} registros. Filtra para localizar otros productos.</p>
          <div className="p-table-wrap"><table><thead><tr><th>Seleccionar</th><th>SKU / historial</th><th>Producto</th><th>Stock</th><th>Precio</th><th>Conteo físico final</th><th>Estado</th></tr></thead>
            <tbody>{inventory.rows.map((row, i) => <tr key={row.sku + ":" + i}>
              <td><input type="checkbox" aria-label={"Seleccionar conteo " + row.sku} disabled={!canEdit || disabled || row.variable_parent}
                checked={selected.includes(row.sku)} onChange={e => setSelected(old => e.target.checked ? [...old, row.sku] : old.filter(s => s !== row.sku))} /></td>
              <td><button className="p-link" disabled={disabled} onClick={() => void attempt(() => inspectHistory(row.sku))}>{row.sku}</button></td>
              <td>{row.nombre_producto}<small>{row.Marca} · {row.categorias}</small></td><td>{row.variable_parent ? "—" : row.Existencias}</td><td>{row.variable_parent ? "—" : money(row.precio)}</td>
              <td>{row.variable_parent ? "—" : <input type="number" min={0} step={1} aria-label={"Conteo físico de " + row.sku} disabled={!canEdit || disabled}
                value={counts[row.sku] ?? row.Existencias} onChange={e => setCounts(old => ({ ...old, [row.sku]: Number(e.target.value) }))} />}</td>
              <td>{row.variable_parent ? "Portada sin stock propio" : row.counted ? "Ya contado" : "Pendiente"}</td>
            </tr>)}</tbody></table></div>
          <button className="button" disabled={!canEdit || disabled || !selected.length} onClick={() => {
            const rows = selected.map(sku => ({ sku, stock: counts[sku] }));
            confirm("Guardar conteos físicos", `${rows.length} SKU seleccionados. Se actualizará su stock en Drive y se registrará el movimiento. No se publica en la tienda.`, "Guardar conteos", async () => {
              const data = await request<{ message: string }>("counts", "POST", { confirm: true, counts: rows });
              await loadInventory(); setNotice(data.message);
            });
          }}>Guardar conteos seleccionados ({selected.length})</button>
        </>}
      </section>
      <section className="p-card"><h2>Registrar movimiento</h2>
        <p className="p-muted">Inventario inicial y Ajuste indican el stock final. Entrada, Salida, Merma y Devolución indican las unidades del movimiento.</p>
        <div className="p-tool-form">
          <label className="p-form-field">SKU<input value={sku} maxLength={80} onChange={e => setSku(e.target.value)} /></label>
          <label className="p-form-field">Movimiento<select value={movement.movement_type} onChange={e => setMovement(old => ({ ...old, movement_type: e.target.value }))}>
            {(inventory?.movement_types || ["Inventario inicial", "Entrada", "Salida", "Merma", "Devolución", "Ajuste"]).map(t => <option key={t}>{t}</option>)}</select></label>
          <label className="p-form-field">Cantidad<input type="number" min={0} step={1} value={movement.quantity} onChange={e => setMovement(old => ({ ...old, quantity: Number(e.target.value) }))} /></label>
          <label className="p-form-field">Referencia<input value={movement.reference} onChange={e => setMovement(old => ({ ...old, reference: e.target.value }))} /></label>
          <label className="p-form-field">Motivo<input value={movement.reason} onChange={e => setMovement(old => ({ ...old, reason: e.target.value }))} /></label>
        </div>
        <button className="button" disabled={!canEdit || disabled || !sku.trim()} onClick={() => {
          const payload = { confirm: true, sku: sku.trim(), ...movement };
          confirm("Guardar movimiento", `${payload.sku} · ${payload.movement_type} · ${payload.quantity}. Se actualizará Drive y su historial.`, "Guardar movimiento", async () => {
            const data = await request<{ message: string }>("movement", "POST", payload);
            await inspectHistory(payload.sku); if (inventory) await loadInventory(); setNotice(data.message);
          });
        }}>Guardar movimiento en Drive</button>
        <button className="button secondary" disabled={disabled || !sku.trim()} onClick={() => void attempt(() => inspectHistory(sku.trim()))}>Consultar historial</button>
        <div className="p-table-wrap"><table><thead><tr><th>Fecha</th><th>Tipo</th><th>Cantidad</th><th>Antes</th><th>Después</th><th>Motivo</th><th>Referencia</th></tr></thead><tbody>
          {history.map((row, i) => <tr key={i}><td>{row.timestamp}</td><td>{row.tipo}</td><td>{row.cantidad}</td><td>{row.stock_anterior}</td><td>{row.stock_nuevo}</td><td>{row.motivo}</td><td>{row.referencia}</td></tr>)}
        </tbody></table></div>
      </section>
      <section className="p-card"><h2>Comparar Sheets y WooCommerce</h2>
        <p className="p-muted">Esta revisión consulta nombres, existencias y precios. No modifica la tienda.</p>
        <button className="button secondary" disabled={disabled} onClick={() => void attempt(async () => setReview(await request<Review>("review")))}>Revisar sincronización y stock</button>
        {review && <><div className="p-tool-metrics">{Object.entries(review.summary).map(([name, n]) => <p key={name}>{name}: <strong>{n}</strong></p>)}</div>
          <div className="p-table-wrap"><table><thead><tr><th>SKU</th><th>Producto</th><th>Estado</th><th>Stock Drive / tienda</th><th>Precio Drive / tienda</th></tr></thead><tbody>
            {review.rows.map((row, i) => <tr key={i}><td>{row.sku}</td><td>{row.name}</td><td>{row.status}</td><td>{row.inventory_stock ?? "—"} / {row.woocommerce_stock ?? "—"}</td><td>{money(row.inventory_price)} / {money(row.woocommerce_price)}</td></tr>)}
          </tbody></table></div></>}
      </section>
    </>}
    {tool === "media" && <section className="p-card"><h2>Revisar Drive y WordPress</h2>
      <p className="p-muted">Comprueba las imágenes existentes y sus coincidencias con productos. La revisión comienza cuando pulses el botón.</p>
      <button className="button secondary" disabled={disabled} onClick={() => void attempt(async () => setMedia(await request<Media>("media-preview")))}>Revisar imágenes de Drive y WordPress</button>
      {media && <>
        <div className="p-tool-metrics">{Object.entries(media.summary).filter(([, n]) => typeof n === "number").map(([name, n]) => <p key={name}>{name}: <strong>{n}</strong></p>)}</div>
        <p className="p-muted">{media.wordpress_configured ? "WordPress conectado." : "Falta configurar WordPress."} {media.woocommerce_write && media.wordpress_write ? "Publicación de imágenes habilitada." : "La publicación de imágenes está deshabilitada en el servicio."}</p>
        <div className="p-table-wrap"><table><thead><tr><th>SKU</th><th>Producto</th><th>Imágenes de Drive</th><th>WooCommerce</th><th>Revisión</th></tr></thead><tbody>
          {media.rows.map((row, i) => <tr key={i}><td>{row.sku}</td><td>{row.name}</td><td>{row.images.map((image, j) => <p key={j}>{image.resolved_filename || image.requested_filename} · {image.resolution}</p>)}</td><td>{row.wc_id || "No encontrado"}</td><td>{row.ready ? "Listo" : "Revisar"}</td></tr>)}
        </tbody></table></div>
        <label className="p-form-field">SKU para publicar sus imágenes<input value={sku} maxLength={80} onChange={e => setSku(e.target.value)} /></label>
        <button className="button" disabled={!isAdmin || disabled || !sku.trim() || !media.wordpress_write || !media.woocommerce_write} onClick={() => {
          const selectedSku = sku.trim();
          confirm("Publicar imágenes de un producto", `Se sincronizarán las imágenes existentes de ${selectedSku} con WordPress y WooCommerce. Revisa las coincidencias antes de confirmar.`, "Publicar imágenes", async () => {
            const data = await request<{ message: string }>("media-sync", "POST", { confirm: true, sku: selectedSku }); setNotice(data.message);
          });
        }}>Publicar imágenes del SKU</button>
      </>}
    </section>}
    {tool === "publication" && <section className="p-card"><h2>Publicación masiva de Drive a WooCommerce</h2>
      <p className="p-muted">Publica los productos del inventario conectado con la lógica existente. Pausar o salir de esta herramienta detiene el siguiente grupo; el grupo iniciado termina y conserva su resultado.</p>
      <div className="p-tool-form">
        <label className="p-form-field">Productos del lote<select disabled={disabled} value={options.mode} onChange={e => setOptions(old => ({ ...old, mode: e.target.value }))}>
          <option value="10">Primeros 10</option><option value="50">Primeros 50</option><option value="all">Todos</option><option value="custom">Lista de SKU</option></select></label>
        <label className="p-form-field">SKU seleccionados<textarea disabled={disabled} value={options.custom} onChange={e => setOptions(old => ({ ...old, custom: e.target.value }))} placeholder="Un SKU por línea o separados por coma" /></label>
        <label className="p-form-field">Productos por grupo<select disabled={disabled} value={options.workers} onChange={e => setOptions(old => ({ ...old, workers: Number(e.target.value) }))}><option value={1}>1</option><option value={2}>2</option><option value={3}>3</option></select></label>
      </div>
      <div className="p-tool-options">
        <label><input type="checkbox" disabled={disabled} checked={options.skip_processed} onChange={e => setOptions(old => ({ ...old, skip_processed: e.target.checked }))} /> Omitir productos ya publicados correctamente</label>
        <label><input type="checkbox" disabled={disabled} checked={options.include_images} onChange={e => setOptions(old => ({ ...old, include_images: e.target.checked }))} /> Incluir imágenes existentes</label>
        <label><input type="checkbox" disabled={disabled} checked={options.include_stock} onChange={e => setOptions(old => ({ ...old, include_stock: e.target.checked }))} /> Publicar existencias físicas</label>
      </div>
      <button className="button" disabled={!isAdmin || disabled || running} onClick={() => {
        const selection = { ...options };
        confirm("Crear y publicar lote", `${selection.mode === "all" ? "Todos los productos pendientes" : selection.mode === "custom" ? "Los SKU indicados" : selection.mode + " productos"}. Imágenes: ${selection.include_images ? "sí" : "no"}. Stock: ${selection.include_stock ? "sí" : "no"}. Se actualizará la tienda; las portadas se procesan antes de sus variantes.`, "Crear y publicar", async () => {
          const data = await request<{ batch_id: string }>("batch-create", "POST", { confirm: true, ...selection });
          // Persist a created ID even when the user left during the request; never start a wave then.
          try { localStorage.setItem(storageKey, data.batch_id); } catch {}
          if (!mounted.current) return;
          setBatchId(data.batch_id);
          await runBatch(data.batch_id);
        });
      }}><Play size={17} /> Crear y publicar lote</button>
      <div className="p-toolbar">
        <label className="p-form-field">ID del lote<input value={batchId} maxLength={100} disabled={disabled || running} onChange={e => setBatchId(e.target.value)} /></label>
        <button className="button secondary" disabled={disabled || !batchId.trim()} onClick={() => void attempt(async () => { await refreshBatch(batchId.trim()); setBatchState("Pausado"); })}>Consultar lote</button>
        <button className="button secondary" disabled={!isAdmin || disabled || running || !batchId.trim()} onClick={() => {
          const id = batchId.trim();
          confirm("Reanudar publicación", "Revisa en la tienda los resultados inciertos antes de confirmar. Se conservarán los SKU terminados y se volverán a intentar los pendientes o fallidos.", "Reanudar lote", async () => {
            await request("batch-resume", "POST", { confirm: true, batch_id: id });
            await runBatch(id);
          });
        }}>Reanudar lote</button>
        <button className="button secondary p-danger" disabled={!running} onClick={() => { pause.current = true; setBatchState("Pausando al terminar el grupo actual…"); }}><Square size={17} /> Pausar publicación</button>
      </div>
      <p role="status">{batchState}</p>
      {batch && <>
        <div className="p-tool-metrics"><p>{batch.summary.total} productos</p><p>{batch.summary.success} terminados</p><p>{batch.summary.error} errores</p><p>{batch.summary.pending + batch.summary.running} pendientes</p></div>
        <progress aria-label="Progreso de publicación" max={Math.max(1, batch.summary.total)} value={batch.summary.success + batch.summary.error} />
        <div className="p-table-wrap"><table><thead><tr><th>SKU</th><th>Estado</th><th>Mensaje</th><th>Producto</th></tr></thead><tbody>
          {batch.rows.map((row, i) => <tr key={i}><td>{row.sku}</td><td>{row.status}</td><td>{row.message}</td><td>{row.permalink?.startsWith("https://") && <a href={row.permalink} target="_blank" rel="noreferrer">Ver en tienda</a>}</td></tr>)}
        </tbody></table></div>
      </>}
    </section>}
  </div>;
}
