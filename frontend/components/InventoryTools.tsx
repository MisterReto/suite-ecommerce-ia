"use client";
// Herramientas nativas: reutilizan las APIs establecidas, con confirmación antes de escribir.
// Conteos y movimientos locales con confirmación explícita.
import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

type Tool = "count";
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
  const [movement, setMovement] = useState({ movement_type: "Entrada", quantity: 0, reason: "", reference: "" });
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const disabled = busy || !online;

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
  const confirm = (title: string, text: string, label: string, action: () => Promise<void>) =>
    ask({ title, text, label, action: async () => {
      // Parent confirmation clears promptly; progress and pause remain in this native panel.
      void attempt(action);
    } });

  return <div className="p-native-tools" aria-label="Herramientas integradas">
    {error && <div className="p-alert danger" role="alert">{error}</div>}
    {notice && <div className="p-alert" role="status">{notice}</div>}
    {busy && <p role="status"><Loader2 className="spin" size={18} /> Consultando servidor…</p>}
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
            confirm("Guardar conteos físicos", `${rows.length} SKU seleccionados. Se actualizará su stock en Drive y se registrará el movimiento. Se conserva el historial de movimientos.`, "Guardar conteos", async () => {
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

    </>}


  </div>;
}
