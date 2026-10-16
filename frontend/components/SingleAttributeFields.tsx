"use client";

type Attributes = Record<string, string | string[]>;

export function singleAttribute(attributes: Attributes): Attributes {
  const entries = Object.entries(attributes || {}).filter(([key]) => key !== "Tipo reconocido");
  const chosen = ["Sabor", "Color", "Variante", "Tamaño"].map(name =>
    entries.find(([key]) => key.toLocaleLowerCase() === name.toLocaleLowerCase())).find(Boolean) || entries[0];
  return chosen ? { [chosen[0]]: chosen[1] } : {};
}

export default function SingleAttributeFields({ attributes, family, onChange }: {
  attributes: Attributes; family: boolean; onChange: (value: Attributes) => void;
}) {
  const [name, value] = Object.entries(singleAttribute(attributes))[0] || ["", ""];
  return <div className="p-form-field">
    <p>Usa un solo atributo por producto: el que distingue sus variaciones.</p>
    {Object.keys(attributes).length > 1 && <label>
      Esta ficha tiene varios atributos antiguos. Elige el único que conservarás al guardar.
      <select value={name} onChange={e => onChange({ [e.target.value]: attributes[e.target.value] })}>
        {Object.keys(attributes).filter(key => key !== "Tipo reconocido").map(key => <option key={key}>{key}</option>)}
      </select>
    </label>}
    <div className="p-form-grid">
      <label>Atributo de variación<input value={name} maxLength={80} placeholder="Ej. Sabor"
        onChange={e => onChange({ [e.target.value]: value })} /></label>
      <label>{family ? "Opciones · una por línea" : "Valor del atributo"}
        {family ? <textarea rows={3} value={Array.isArray(value) ? value.join("\n") : value}
          onChange={e => onChange({ [name]: e.target.value.split("\n") })} /> :
          <input value={Array.isArray(value) ? value.join(", ") : value} maxLength={160} placeholder="Ej. Camarón, limón y habanero"
            onChange={e => onChange({ [name]: e.target.value })} />}
      </label>
    </div>
  </div>;
}
