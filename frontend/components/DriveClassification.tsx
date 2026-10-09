"use client";

import { useEffect, useState } from "react";

type Choices = {
  source: "drive" | "defaults";
  categories: string[];
  subcategories: Record<string, string[]>;
  tags: string[];
};
type Value = { category: string; subcategory: string; tags: string[] };

export default function DriveClassification({ value, onChange, enabled, folderKey, disabled = false }: {
  value: Value;
  onChange: (value: Value) => void;
  enabled: boolean;
  folderKey: string;
  disabled?: boolean;
}) {
  const [choices, setChoices] = useState<Choices>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [tagQuery, setTagQuery] = useState("");
  useEffect(() => {
    setChoices(undefined);
    setError("");
    setTagQuery("");
    if (!enabled) { setLoading(false); return; }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 45_000);
    let stopped = false;
    setLoading(true);
    void (async () => {
      try {
        const response = await fetch("/api/catalog-taxonomy", {
          credentials: "same-origin", cache: "no-store", signal: controller.signal,
        });
        if (!response.ok || !response.headers.get("content-type")?.includes("application/json")) throw new Error();
        const data: Choices = await response.json();
        if (!Array.isArray(data.categories) || !Array.isArray(data.tags) || !data.subcategories) throw new Error();
        if (!stopped) setChoices(data);
      } catch {
        if (!stopped) setError("No pudimos cargar las opciones de Drive.");
      } finally {
        clearTimeout(timer);
        if (!stopped) setLoading(false);
      }
    })();
    return () => { stopped = true; clearTimeout(timer); controller.abort(); };
  }, [enabled, folderKey, refresh]);

  const subcategories = [...new Set([
    ...(value.category ? choices?.subcategories[value.category] || [] : Object.values(choices?.subcategories || {}).flat()),
    ...(choices?.subcategories[""] || []),
    value.subcategory,
  ])].filter(Boolean);
  const locked = disabled || loading || !enabled;
  const matchingTags = (choices?.tags || []).filter(tag => tag.toLocaleLowerCase().includes(tagQuery.trim().toLocaleLowerCase()));
  const visibleTags = [...new Set([...value.tags, ...matchingTags.slice(0, 60)])];
  return <>
    <label className="field">
      <span>Categoría</span>
      <select aria-label="Categoría" value={value.category} disabled={locked}
        onChange={event => {
          const category = event.target.value;
          const valid = [...(choices?.subcategories[category] || []), ...(choices?.subcategories[""] || [])];
          onChange({ ...value, category, subcategory: valid.includes(value.subcategory) ? value.subcategory : "" });
        }}>
        <option value="">Por confirmar</option>
        {[...new Set([...(choices?.categories || []), value.category])].filter(Boolean).map(item => <option key={item}>{item}</option>)}
      </select>
    </label>
    <label className="field">
      <span>Subcategoría</span>
      <select aria-label="Subcategoría" value={value.subcategory} disabled={locked}
        onChange={event => onChange({ ...value, subcategory: event.target.value })}>
        <option value="">Por confirmar</option>
        {subcategories.map(item => <option key={item}>{item}</option>)}
      </select>
    </label>
    <fieldset className="classification-tags wide" disabled={locked}>
      <legend>Etiquetas</legend>
      {!!choices?.tags.length && <input type="search" aria-label="Buscar etiqueta" value={tagQuery}
        onChange={event => setTagQuery(event.target.value)} placeholder="Buscar entre las etiquetas de Drive" />}
      <div className="classification-options" role="group" aria-label="Etiquetas">
        {visibleTags.map(tag => {
          const selected = value.tags.includes(tag);
          const full = value.tags.length >= 20 || [...value.tags, tag].join(", ").length > 500;
          return <label className={"classification-option" + (selected ? " selected" : "")} key={tag}>
            <input type="checkbox" checked={selected} disabled={!selected && full}
              onChange={event => onChange({ ...value, tags: event.target.checked ? [...value.tags, tag] : value.tags.filter(item => item !== tag) })} />
            <span>{tag}</span>
          </label>;
        })}
      </div>
      {matchingTags.length > 60 && <small>Busca para encontrar más etiquetas ({choices?.tags.length} disponibles).</small>}
      {!!tagQuery && !matchingTags.length && <small>No hay etiquetas con esa búsqueda.</small>}
      {choices && !choices.tags.length && !value.tags.length && <small>Tu inventario todavía no contiene etiquetas.</small>}
    </fieldset>
    <div className="classification-status wide" aria-live="polite">
      <span>{loading ? "Cargando categorías y etiquetas de Drive…" : error || (choices?.source === "drive"
        ? "Opciones de Lista completa en tu Drive." : choices ? "Inventario sin clasificación: opciones iniciales." : "")}</span>
      {enabled && !loading && <button type="button" className="text-button" disabled={disabled}
        onClick={() => setRefresh(previous => previous + 1)}>{error ? "Reintentar carga" : "Actualizar opciones"}</button>}
    </div>
  </>;
}
