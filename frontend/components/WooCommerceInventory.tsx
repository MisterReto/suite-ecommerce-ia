"use client";

import { useMemo, useRef, useState } from "react";

type Remote = { id: number; parent_id: number | null; stock: number | null; stock_inherited: boolean;
  status: string; visibility: string };
type Row = { sku: string; name: string; kind: string; parent_sku: string; stock: number | null;
  publication: string; stock_comparison: string; difference: number | null; woocommerce: Remote | null;
  matches: Remote[]; brand: string; category: string };
type Comparison = { rows: Row[]; summary: Record<string, number>; checked_at: string;
  app_products: number; woocommerce_products: number; woocommerce_variations: number; store: string };
type Props = { online: boolean; openPublisher: () => void;
  api: <T>(path: string, method?: string, body?: unknown, timeout?: number) => Promise<T> };
const labels: Record<string, string> = { missing_woocommerce: "Falta subir a WooCommerce", missing_app: "Solo en WooCommerce",
  published: "Publicado", draft: "Borrador en WooCommerce", hidden: "Publicado, oculto en catálogo", conflict: "Revisar SKU o familia",
  other: "Otro estado de WooCommerce", no_sku: "Sin SKU en WooCommerce" };
const kinds: Record<string, string> = { simple: "Simple", family: "Familia", variant: "Variante" };
const amount = (value: number | null) => value == null ? "Sin dato" : new Intl.NumberFormat("es-MX").format(value);

export default function WooCommerceInventory({ online, api, openPublisher }: Props) {
  const [result, setResult] = useState<Comparison>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const submitting = useRef(false);
  const rows = useMemo(() => (result?.rows || []).filter(row =>
    (!filter || (filter === "stock_different" ? row.stock_comparison === "different" : row.publication === filter)) &&
    (!query || [row.sku, row.name, row.parent_sku, row.brand, row.category].join(" ").toLocaleLowerCase().includes(query.toLocaleLowerCase()))),
  [result, query, filter]);
  const load = async () => {
    if (submitting.current || !online) return;
    submitting.current = true; setBusy(true); setError("");
    try {
      const data = await api<Comparison>("/api/woocommerce/inventory-comparison?refresh=true", "GET", undefined, 330_000);
      setResult(data); setOffset(0);
    } catch (e) { setError((e as Error).message); }
    finally { submitting.current = false; setBusy(false); }
  };
  const exportCsv = () => {
    const cell = (value: unknown) => {
      const text = value == null ? "" : String(value);
      return '"' + (/^[=+\-@\t\r]/.test(text) ? "'" + text : text).replaceAll('"', '""') + '"';
    };
    const body = [["SKU", "Producto", "Tipo", "Familia", "Estado WooCommerce", "Stock app", "Stock WooCommerce", "Diferencia Woo-app", "Comparación stock"],
      ...rows.map(row => [row.sku, row.name, kinds[row.kind], row.parent_sku, labels[row.publication],
        row.kind === "family" ? "" : row.stock, row.kind === "family" ? "" : row.woocommerce?.stock, row.difference,
        row.stock_comparison === "different" ? "Diferente" : row.stock_comparison === "same" ? "Coincide" : "No comparable"])];
    const url = URL.createObjectURL(new Blob(["\ufeff" + body.map(row => row.map(cell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "comparacion-inventario.csv"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <section className="p-card" aria-label="Comparador de inventario WooCommerce">
    <h2>Comparar inventario con WooCommerce</h2>
    <p className="p-muted">Compara por SKU los productos registrados en la app con todos los productos y variantes de tu tienda.</p>
    <div className="p-toolbar">
      <button type="button" className="button" disabled={busy || !online} onClick={() => void load()}>{busy ? "Leyendo productos y variantes…" : result ? "Actualizar comparación" : "Comparar inventarios"}</button>
      <button type="button" className="button secondary" onClick={openPublisher}>Ir a publicar productos</button>
    </div>
    {error && <div className="p-alert danger" role="alert">{error}{result && " Se conserva la comparación anterior; no se pudo actualizar."}</div>}
    {busy && <p role="status">Consultando todas las páginas de WooCommerce. Puede tardar unos minutos.</p>}
    {result && <>
      <p className="p-muted">{result.store} · Consultado: {new Date(result.checked_at).toLocaleString("es-MX")} · {result.app_products} registros en la app · {result.woocommerce_products} productos y {result.woocommerce_variations} variantes en WooCommerce.</p>
      {!result.app_products && <div className="p-alert">El catálogo de la app está vacío. Carga el inventario de Drive y usa «Sincronizar catálogo de la app» para registrar sus productos y compararlos.</div>}
      <div className="p-tool-metrics">
        {[["missing_woocommerce", "faltan por subir"], ["draft", "borradores"], ["published", "publicados"], ["stock_different", "con stock diferente"]].map(([key, label]) =>
          <button type="button" className="button secondary" key={key} aria-pressed={filter === key} onClick={() => { setFilter(filter === key ? "" : key); setOffset(0); }}>
            <strong>{result.summary[key] || 0}</strong> {label}</button>)}
      </div>
      <div className="p-toolbar">
        <label className="p-form-field">Buscar por SKU o producto<input value={query} onChange={e => { setQuery(e.target.value); setOffset(0); }} /></label>
        <label className="p-form-field">Mostrar<select value={filter} onChange={e => { setFilter(e.target.value); setOffset(0); }}>
          <option value="">Todos</option>{Object.entries(labels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          <option value="stock_different">Diferencias de stock</option></select></label>
        <button type="button" className="button secondary" disabled={!rows.length || busy} onClick={exportCsv}>Descargar comparación CSV</button>
      </div>
      <p className="p-muted">{rows.length} resultados. Diferencia = stock WooCommerce − stock app. Los totales incluyen familias y variantes; las familias no tienen stock propio.</p>
      <div className="wc-results" aria-live="polite">{rows.slice(offset, offset + 50).map((row, index) => <article className="wc-inventory-row" key={row.sku + ":" + index}>
        <div><strong>{row.name || "Producto sin nombre"}</strong><br /><code>{row.sku || "Sin SKU"}</code> · {kinds[row.kind]}
          {row.parent_sku && <small>Familia: {row.parent_sku}</small>}</div>
        <div><strong>{labels[row.publication]}</strong>{row.woocommerce && ["other", "missing_app"].includes(row.publication) &&
          <small>Estado en tienda: {row.woocommerce.status === "publish" ? "Publicado" : row.woocommerce.status === "draft" ? "Borrador" : row.woocommerce.status}{row.woocommerce.visibility === "hidden" && " · Oculto"}</small>}
          {row.matches.length > 0 && <small>Coincidencias: {row.matches.map(item => "ID " + item.id).join(", ")}</small>}</div>
        {row.kind !== "family" && <p>Stock app: <strong>{amount(row.stock)}</strong> · WooCommerce: <strong>{amount(row.woocommerce?.stock ?? null)}</strong>
          {row.difference != null && <> · Diferencia: <strong>{row.difference > 0 ? "+" : ""}{amount(row.difference)}</strong></>}
          {row.woocommerce?.stock_inherited && <small>Stock compartido con la familia; requiere revisión conjunta.</small>}
          {row.stock_comparison === "unknown" && <small>Sin cantidad comparable. WooCommerce puede tener desactivada la gestión de stock.</small>}</p>}
      </article>)}</div>
      {!rows.length && <p>No hay productos con estos filtros.</p>}
      <div className="p-toolbar">
        <button type="button" className="button secondary" disabled={!offset} onClick={() => setOffset(Math.max(0, offset - 50))}>Anterior</button>
        <span>{rows.length ? offset + 1 : 0}–{Math.min(offset + 50, rows.length)} de {rows.length}</span>
        <button type="button" className="button secondary" disabled={offset + 50 >= rows.length} onClick={() => setOffset(offset + 50)}>Siguiente</button>
      </div>
    </>}
  </section>;
}
