"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { GenerationSounds } from "@/lib/generation-sounds";
import DriveClassification from "@/components/DriveClassification";
import { recoverSession } from "@/lib/session-recovery";
import {
  Camera,
  Check,
  CheckCircle2,
  Download,
  ExternalLink,
  HelpCircle,
  ImagePlus,
  Images,
  Info,
  Layers,
  Loader2,
  LogOut,
  Package,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  ShoppingBag,
  Sparkles,
  Upload,
  Users,
  WandSparkles,
  X,
} from "lucide-react";

type Product = {
  sku: string;
  name: string;
  brand: string;
  size: string;
  kind: string;
  price: number;
  category: string;
  subcategory: string;
  tags: string;
  short_description: string;
  description: string;
  barcode: string;
  parent_sku: string;
  parent_name: string;
  parent_mode: string;
  attribute: string;
  attribute_value: string;
  product_type?: string;
  variant?: string;
  attributes?: Record<string, string>;
  uncertain_fields?: string[];
};
type Match = {sku: string; nombre_producto: string; Marca?: string; precio?: number | string;
  atributo_nombre?: string; atributo_valor?: string | string[]; sku_padre?: string;
  product_id?: string; image_url?: string; _source?: string; attributes?: Record<string, string | string[]>;
  matching_attributes?: string[]; different_attributes?: string[]};
type IdentityReview = {status: string; case: string; message: string; recommendation: string;
  suggested?: string; duplicate?: Match; parents: Match[]; candidates: Match[]; sources?: string[]};
type Picture = {
  id: string;
  approved: boolean;
  message: string;
  history: string[];
  qa?: { resumen?: string; aprobada?: boolean };
};
type Brief = {
  lifestyle: string;
  comercial: string;
  note: string;
  style_count: number;
  sources: { title: string; url: string }[];
  search_suggestions: string;
};
type Draft = {
  revision: string;
  front_id: string;
  back_id?: string;
  context: string;
  product: Product;
  images: Record<string, Picture>;
  brief?: Brief;
  cover_id?: string;
  cover_message?: string;
  saved?: string;
  variant_report?: string;
  variant_recommendation?: string;
  identity_review?: IdentityReview;
  sync_status?: string;
  sync_error?: string;
  master_product_id?: string;
};
type Job = {
  id: string;
  status: string;
  label: string;
  progress: number;
  message: string;
};
type Session = {
  authenticated: boolean;
  email?: string;
  gemini_configured?: boolean;
  folder?: string;
  folder_id?: string;
  image_model?: string;
  image_provider?: string;
  estimated_image_usd?: number | null;
  text_model?: string;
  errors?: string[];
  usage?: Record<string, number>;
  draft?: Draft;
  job?: Job;
  loyverse?: {
    configured: boolean;
    stores: { id: string; name: string }[];
    job?: LoyJob;
  };
};
type CatalogRow = Record<string, string | number>;
type LoyRow = {
  sku: string;
  name: string;
  drive: number;
  loyverse: number;
  price: number;
  status: string;
  detail: string;
  eligible: boolean;
};
type LoyJob = {
  id: string;
  state: string;
  done: number;
  total: number;
  phase: string;
  current?: string;
  error?: string;
  uncertain?: string;
  created?: string[];
  completed?: string[];
};

const initial: Product = {
  sku: "",
  name: "",
  brand: "",
  size: "",
  kind: "Simple",
  price: 0,
  category: "",
  subcategory: "",
  tags: "",
  short_description: "",
  description: "",
  barcode: "",
  parent_sku: "",
  parent_name: "",
  parent_mode: "Crear nuevo padre",
  attribute: "Tamaño",
  attribute_value: "",
  product_type: "",
  variant: "",
  attributes: {},
  uncertain_fields: [],
};

function sameProduct(a: Product, b: Product) {
  const normalize = (value: unknown): unknown => value && typeof value === "object" && !Array.isArray(value)
    ? Object.fromEntries(Object.entries(value).sort(([x], [y]) => x.localeCompare(y)).map(([key, item]) => [key, normalize(item)]))
    : value;
  return JSON.stringify(normalize({...initial, ...a})) === JSON.stringify(normalize({...initial, ...b}));
}
const slots = [
  {
    id: "1_hd",
    name: "Catálogo",
    description: "Fondo blanco · producto fiel",
    icon: ShoppingBag,
    tone: "catalog",
  },
  {
    id: "2_uso",
    name: "Lifestyle",
    description: "Personas consumiendo o usando",
    icon: Users,
    tone: "lifestyle",
  },
  {
    id: "3_comercial",
    name: "Comercial",
    description: "Arte y producto protagonista",
    icon: WandSparkles,
    tone: "commercial",
  },
];
const fileUrl = (id: string) => "/api/files/" + encodeURIComponent(id);
const activeJob = (job?: Job | null) =>
  !!job && ["queued", "running", "cancelling"].includes(job.status);

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(),
    path.includes("/loyverse/") || path.includes("/catalog") ? 120000 : 45000,
  );
  try {
    const response = await fetch(path, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      signal: controller.signal,
      ...(body instanceof FormData
        ? { body }
        : body !== undefined
          ? {
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(body),
            }
          : {}),
    });
    const result = await response.json().catch(() => {
      throw new ApiError(
        "El servicio todavía no responde. Espera unos segundos y vuelve a intentarlo.",
        response.ok ? 503 : response.status,
      );
    });
    if (!response.ok)
      throw new ApiError(
        typeof result.detail === "string"
          ? result.detail
          : result.error || "Revisa los datos y vuelve a intentar.",
        response.status,
      );
    return result as T;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError")
      throw new Error(
        "La conexión tardó demasiado. Consulta el progreso antes de volver a enviar.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function Field({
  label,
  hint,
  children,
  wide = false,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <label className={"field" + (wide ? " wide" : "")}>
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

function PhotoUpload({
  name,
  id,
  optional,
  disabled,
  onUpload,
  onRemove,
}: {
  name: string;
  id?: string;
  optional?: boolean;
  disabled: boolean;
  onUpload: (file: File) => void;
  onRemove: () => void;
}) {
  return (
    <div className={"photo-upload" + (id ? " has-photo" : "")}>
      {id ? (
        <img src={fileUrl(id)} alt={name + " del producto"} />
      ) : (
        <div className="photo-placeholder">
          <Camera size={30} strokeWidth={1.5} />
          <strong>{name}</strong>
          <span>
            {optional
              ? "Opcional · ayuda a leer la etiqueta"
              : "El frente completo del producto"}
          </span>
        </div>
      )}
      <label className="upload-control">
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp,image/avif,image/heic,image/heif"
          disabled={disabled}
          aria-label={"Subir foto " + name.toLowerCase()}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            e.target.value = "";
          }}
        />
        <Upload size={15} />
        {id ? "Cambiar foto" : "Galería / archivos"}
      </label>
      <label className="camera-control" title="Tomar foto">
        <input
          type="file"
          capture="environment"
          accept="image/*"
          disabled={disabled}
          aria-label={"Tomar foto " + name.toLowerCase()}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onUpload(f);
            e.target.value = "";
          }}
        />
        <Camera size={17} />
        <span>Tomar foto</span>
      </label>
      {id && <span className="photo-name">{name}</span>}
      {id && <button className="photo-remove" disabled={disabled} onClick={onRemove} aria-label={"Eliminar foto " + name.toLowerCase()}><X size={17} /></button>}
    </div>
  );
}

export default function CaptureStudio({
  embedded = false,
  initialSection = "studio",
  onOpenProduct,
  onSaved,
  onSessionChange,
}: {
  embedded?: boolean;
  initialSection?: string;
  onOpenProduct?: (id: string) => void;
  onSaved?: () => void;
  onSessionChange?: (value: Session) => void;
}) {
  const [session, setSession] = useState<Session>({ authenticated: false });
  const sessionCallback = useRef(onSessionChange);
  sessionCallback.current = onSessionChange;
  const [loading, setLoading] = useState(true);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [section, setSection] = useState(initialSection);
  useEffect(() => { if (embedded) setSection(initialSection); }, [embedded, initialSection]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [product, setProduct] = useState<Product>(initial);
  const [front, setFront] = useState<string>();
  const [back, setBack] = useState<string>();
  const [context, setContext] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const sounds = useRef<GenerationSounds | null>(null);
  if (!sounds.current) sounds.current = new GenerationSounds();
  const [soundEnabled, setSoundEnabled] = useState(true);
  useEffect(() => {
    let enabled = true;
    try { enabled = localStorage.getItem("rincon-generation-sounds") !== "off"; } catch {}
    setSoundEnabled(enabled);
    sounds.current!.setEnabled(enabled);
    return () => sounds.current!.dispose();
  }, []);
  useEffect(() => { sounds.current!.observe(job); }, [job]);
  const [posting, setPosting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [selectedSlots, setSelectedSlots] = useState(slots.map((s) => s.id));
  const [review, setReview] = useState(false);
  const [correctionSlot, setCorrectionSlot] = useState<string | null>(null);
  const [correction, setCorrection] = useState("");
  const [correctionErrors, setCorrectionErrors] = useState<string[]>([]);
  const [key, setKey] = useState("");
  const [folder, setFolder] = useState("");
  const [showBrief, setShowBrief] = useState(false);
  const [rows, setRows] = useState<CatalogRow[]>([]);
  const [sheetUrl, setSheetUrl] = useState("");
  const [query, setQuery] = useState("");
  const [catalogLoaded, setCatalogLoaded] = useState(false);
  const [parents, setParents] = useState<[string, string][]>([]);
  const [token, setToken] = useState("");
  const [stores, setStores] = useState<{ id: string; name: string }[]>([]);
  const [store, setStore] = useState("");
  const [loyRows, setLoyRows] = useState<LoyRow[]>([]);
  const [preview, setPreview] = useState("");
  const [loySelected, setLoySelected] = useState<string[]>([]);
  const [loyConfirmed, setLoyConfirmed] = useState(false);
  const [loyJob, setLoyJob] = useState<LoyJob | null>(null);
  const loyWorking = !!loyJob && ["queued", "running"].includes(loyJob.state);
  const busy = posting || activeJob(job) || loyWorking;
  const signedIn = session.authenticated;
  const imageCount = Object.keys(draft?.images || {}).length;
  const allApproved =
    imageCount === 0 ||
    Object.values(draft?.images || {}).every((i) => i.approved);

  const applyDraft = useCallback((value: Draft | null | undefined) => {
    if (!value) {
      setDraft(null); setProduct(initial); setFront(undefined); setBack(undefined); setContext("");
      return;
    }
    setDraft(value);
    setProduct(value.product);
    setFront(value.front_id);
    setBack(value.back_id || undefined);
    setContext(value.context);
  }, []);

  const refresh = useCallback(async () => {
    const data = await recoverSession<Session>();
    setSession(data);
    setSessionChecked(true);
    sessionCallback.current?.(data);
    applyDraft(data.draft);
    if (data.job) setJob(data.job);
    if (data.loyverse?.job) setLoyJob(data.loyverse.job);
    if (data.loyverse?.stores?.length) {
      setStores(data.loyverse.stores);
      setStore((prev) => prev || data.loyverse!.stores[0].id);
    }
    return data;
  }, [applyDraft]);

  useEffect(() => {
    const change = () =>
      setSection(
        ["studio", "catalog", "loyverse", "settings", "help"].includes(
          location.hash.slice(1),
        )
          ? location.hash.slice(1)
          : "studio",
      );
    if (!embedded) {
      change();
      window.addEventListener("hashchange", change);
    }
    refresh()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    return () => window.removeEventListener("hashchange", change);
  }, [refresh, embedded]);

  useEffect(() => {
    if (!activeJob(job)) return;
    let stopped = false;
    const timer = setInterval(async () => {
      try {
        const data = await api<{ job: Job; draft: Draft }>(
          "/api/jobs/" + job!.id,
        );
        if (stopped) return;
        setJob(data.job);
        applyDraft(data.draft);
        if (data.job.status === "failed") setError(data.job.message);
        if (data.job.status === "cancelled") setMessage(data.job.message);
        if (data.job.status === "completed") {
          setMessage(data.draft?.saved || "Listo. Revisa el resultado.");
          if (data.draft?.saved) onSaved?.();
          await refresh();
        }
      } catch (e) {
        if (!stopped && e instanceof ApiError && e.status === 401) {
          setJob(null);
          setSession({ authenticated: false });
        }
        if (!stopped) setError((e as Error).message);
      }
    }, 1800);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [job?.id, job?.status, applyDraft, refresh, onSaved]);

  useEffect(() => {
    if (!loyWorking || !loyJob) return;
    let stopped = false;
    const timer = setInterval(async () => {
      try {
        const data = await api<{ job: LoyJob }>(
          "/loyverse-upload-status?job_id=" + encodeURIComponent(loyJob.id),
        );
        if (!stopped && data.job) {
          setLoyJob(data.job);
          if (data.job.error) setError(data.job.error);
        }
      } catch (e) {
        if (!stopped && e instanceof ApiError && e.status === 401) {
          setLoyJob(null);
          setSession({ authenticated: false });
        }
        if (!stopped) setError((e as Error).message);
      }
    }, 2200);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [loyJob?.id, loyJob?.state, loyWorking]);

  const submitting = useRef(false);
  const generationKeys = useRef(new Map<string, string>());
  useEffect(() => {
    if (job && !activeJob(job)) generationKeys.current.clear();
  }, [job?.id, job?.status]);

  const attempt = async (action: () => Promise<void>) => {
    if (busy || submitting.current) return;
    submitting.current = true;
    setPosting(true);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      submitting.current = false;
      setPosting(false);
    }
  };
  const edit = <K extends keyof Product>(field: K, value: Product[K]) =>
    setProduct((p) => ({ ...p, [field]: value }));
  const ensureCapture = async () => {
    if (!front) throw new Error("Sube la foto frontal del producto.");
    if (draft && draft.front_id === front && (draft.back_id || undefined) === back) {
      if (draft.context !== context) {
        const result = await api<{ draft: Draft }>("/api/capture-notes", "PUT", { context });
        setDraft(result.draft);
      }
      return;
    }
    const result = await api<{ draft: Draft }>("/api/capture", "POST", {
      front_id: front,
      back_id: back || null,
      context,
    });
    setDraft(result.draft);
  };
  const persist = async () => {
    await ensureCapture();
    const result = await api<{ draft: Draft }>("/api/draft", "PUT", product);
    setDraft(result.draft);
    setProduct((latest) => sameProduct(latest, product) ? result.draft.product : latest);
    return result.draft;
  };
  const run = async (path: string, body: unknown = {}) => {
    if (path === "/api/generate" || path.endsWith("/correct")) {
      const fingerprint = JSON.stringify([path, draft?.revision, body]);
      let key = generationKeys.current.get(fingerprint);
      if (!key) {
        key = crypto.randomUUID();
        generationKeys.current.set(fingerprint, key);
      }
      body = { ...(body as Record<string, unknown>), request_key: key, confirm_cost: true };
    }
    const result = await api<{ job?: Job; draft?: Draft }>(path, "POST", body);
    if (result.job) {
      sounds.current!.observe(result.job, path === "/api/generate" || path.endsWith("/correct"));
      setJob(result.job);
    }
    if (!activeJob(result.job)) {
      if (result.draft) applyDraft(result.draft);
      await refresh();
      if (result.job?.status === "failed") setError(result.job.message);
    }
  };
  const upload = (which: "front" | "back", file: File) =>
    attempt(async () => {
      if (file.size > 12_000_000)
        throw new Error("La foto supera 12 MB. Usa una versión más ligera.");
      const form = new FormData();
      form.append("image", file);
      const result = await api<{ id: string }>("/api/uploads", "POST", form);
      if (which === "front") {
        setFront(result.id);
        setProduct(initial);
      } else setBack(result.id);
      const nextFront = which === "front" ? result.id : front;
      if (nextFront) {
        const saved = await api<{draft: Draft}>("/api/capture", "POST", {front_id: nextFront, back_id: which === "back" ? result.id : back || null, context});
        setDraft(saved.draft);
      } else setDraft(null);
      setMessage("Foto lista. Analiza el producto o captura sus datos.");
    });
  const loadCatalog = () =>
    attempt(async () => {
      const data = await api<{ rows: CatalogRow[]; sheet_url: string }>(
        "/api/catalog",
      );
      setRows(data.rows);
      setSheetUrl(data.sheet_url);
      setCatalogLoaded(true);
    });
  const removePhoto = (which: "front" | "back") => attempt(async () => {
    if (which === "front") {
      await api("/api/draft", "DELETE"); setFront(undefined); setBack(undefined); setDraft(null); setProduct(initial);
    } else {
      setBack(undefined);
      if (front) {
        const r = await api<{draft: Draft}>("/api/capture", "POST", {front_id: front, back_id: null, context});
        setDraft(r.draft);
        await api("/api/draft", "PUT", product);
      }
    }
  });
  const loadParents = () =>
    attempt(async () => {
      await persist();
      const result = await api<{
        choices: [string, string][];
        parent_sku: string;
        parent_name: string;
        attribute: string;
      }>("/api/parents");
      setParents(result.choices);
      setProduct((p) => ({
        ...p,
        parent_sku: result.parent_sku,
        parent_name: result.parent_name,
        attribute: result.attribute,
      }));
    });
  const chooseFamily = (mode: string) => attempt(async () => {
    await ensureCapture();
    const selected = draft?.identity_review?.suggested || "";
    const next = {...product, kind: "Variable", parent_mode: mode, parent_sku: mode === "Usar padre existente" ? selected : ""};
    const saved = await api<{draft: Draft}>("/api/draft", "PUT", next);
    setDraft(saved.draft);
    const r = await api<{choices: [string, string][]; parent_sku: string; parent_name: string; attribute: string}>("/api/parents");
    setParents(r.choices);
    setProduct({...next, parent_sku: r.parent_sku, parent_name: r.parent_name, attribute: r.attribute});
    setMessage("Familia propuesta. Revisa el atributo y prepara su portada antes de guardar.");
  });
  const go = (name: string) => {
    if (embedded) setSection(name);
    else location.hash = name;
    setError("");
    setMessage("");
  };
  useEffect(() => {
    if (!signedIn || busy || !draft || draft.saved || !front || draft.front_id !== front || (draft.back_id || undefined) !== back) return;
    if (sameProduct(product, draft.product) && context === draft.context) return;
    const timer = setTimeout(() => {
      attempt(async () => { await persist(); });
    }, 800);
    return () => clearTimeout(timer);
  }, [product, context, draft, signedIn, busy, front, back]);

  return (
    <div className={embedded ? "app capture-embedded" : "app"} onClickCapture={() => sounds.current!.unlock()}>
      <header className="brand-header">
        <a className="brand" href="#studio">
          <img src="/logo.png" width="48" height="48" alt="El Rincón de Asia" />
          <span>
            El Rincón de Asia<small>Suite e-commerce</small>
          </span>
        </a>
        <a
          className="store-link"
          href="https://rincon.creandotusite.com/"
          target="_blank"
          rel="noreferrer"
        >
          Ver tienda
          <ExternalLink size={14} />
        </a>
        <button className="account" onClick={() => go("settings")}>
          <span className="avatar">
            {signedIn ? (
              session.email?.slice(0, 1).toUpperCase()
            ) : (
              <Settings2 size={17} />
            )}
          </span>
          <span>
            {signedIn ? "Mi cuenta" : "Conectar cuenta"}
            <small>
              {signedIn ? "Drive conectado" : "Google Drive y Gemini"}
            </small>
          </span>
        </button>
      </header>
      <div className="shell">
        <aside className="sidebar">
          <div className="sidebar-title">TU ESPACIO DE TRABAJO</div>
          <nav aria-label="Navegación principal">
            {[
              { id: "studio", name: "Estudio de productos", icon: Images },
              { id: "catalog", name: "Inventario", icon: Package },
              { id: "loyverse", name: "Loyverse", icon: ShoppingBag },
              { id: "settings", name: "Ajustes", icon: Settings2 },
            ].map((item) => (
              <a
                key={item.id}
                href={"#" + item.id}
                aria-current={section === item.id ? "page" : undefined}
                className={section === item.id ? "nav-link active" : "nav-link"}
              >
                <item.icon size={19} />
                {item.name}
                {section === item.id && <span className="nav-mark" />}
              </a>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="folder-note">
              <Layers size={19} />
              <span>
                Tu catálogo en Drive
                <small>{session.folder || "Proyecto_IA"}</small>
              </span>
            </div>
            <a
              href="#help"
              className={"nav-link " + (section === "help" ? "active" : "")}
            >
              <HelpCircle size={19} />
              Guía de uso
            </a>
            <small className="sidebar-footer">De Asia para tu casa.</small>
          </div>
        </aside>
        <main id="main">
          {loading && (
            <div className="inline-loading">
              <Loader2 className="spin" size={18} />
              Iniciando servidor y recuperando tu sesión…
            </div>
          )}
          {!loading && !sessionChecked && (
            <div className="connection-banner" role="status">
              <span>El servidor aún no está disponible.</span>
              <button className="button primary" onClick={() => {
                setLoading(true); setError("");
                void refresh().catch(e => setError(e.message)).finally(() => setLoading(false));
              }}>Reintentar conexión</button>
            </div>
          )}
          {!loading && sessionChecked && !signedIn && (
            <div className="connection-banner">
              <Info size={19} />
              <div>
                <strong>Conecta tu cuenta para empezar.</strong>
                <span>
                  Tu inventario y tus imágenes se guardan en tu Google Drive.
                </span>
              </div>
              <a href="/login" className="button white">
                Conectar Google Drive
              </a>
            </div>
          )}
          {signedIn && !session.gemini_configured && section !== "settings" && (
            <div className="notice">
              <Info size={18} />
              <span>
                Guarda tu clave de Gemini en Ajustes para analizar y generar
                imágenes.
              </span>
              <button className="text-button" onClick={() => go("settings")}>
                Abrir ajustes
              </button>
            </div>
          )}
          {error && (
            <div className="feedback error" role="alert">
              <Info size={18} />
              <span>{error}</span>
              <button aria-label="Cerrar error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {message && (
            <div className="feedback success" role="status">
              <CheckCircle2 size={18} />
              <span>{message}</span>
              <button
                aria-label="Cerrar mensaje"
                onClick={() => setMessage("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {activeJob(job) && (
            <div className="job-banner" role="status" aria-live="polite">
              <Loader2 size={20} className="spin" />
              <div>
                <strong>{job?.label}</strong>
                <span>{job?.message}</span>
                <progress value={job?.progress} max={100} />
              </div>
              <span>{job?.progress}%</span>
            </div>
          )}

          {section === "studio" && (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">CATÁLOGO & CREATIVIDAD</p>
                  <h1>
                    Estudio de productos<span className="title-dot">.</span>
                  </h1>
                  <p>Del producto real a una ficha lista para tu tienda.</p>
                </div>
                <button
                  className="button secondary"
                  disabled={busy || !front}
                  onClick={() => attempt(async () => {
                    await api("/api/draft", "DELETE");
                    setFront(undefined);
                    setBack(undefined);
                    setDraft(null);
                    setProduct(initial);
                    setContext("");
                    setJob(null);
                    setMessage(
                      "Nueva captura. Sube las fotos de tu siguiente producto.",
                    );
                  })}
                >
                  <Plus size={16} />
                  Nuevo producto
                </button>
              </div>
              <ol className="workflow" aria-label="Progreso del producto">
                {["Captura", "Información", "Imágenes", "Guardar"].map(
                  (label, index) => {
                    const complete = [
                      !!front,
                      !!product.name,
                      imageCount > 0,
                      !!draft?.saved,
                    ][index];
                    return (
                      <li key={label} className={complete ? "complete" : ""}>
                        <span>
                          {complete ? <Check size={14} /> : index + 1}
                        </span>
                        {label}
                      </li>
                    );
                  },
                )}
              </ol>
              <div className="capture-grid">
                <section className="card capture-card">
                  <div className="section-heading">
                    <div className="section-icon">
                      <Camera size={20} />
                    </div>
                    <div>
                      <h2>El producto real</h2>
                      <p>Una buena referencia hace la diferencia.</p>
                    </div>
                    <span className="section-number">01</span>
                  </div>
                  <div className="photos">
                    <PhotoUpload
                      name="Frente"
                      id={front}
                      disabled={!signedIn || busy}
                      onUpload={(f) => upload("front", f)}
                      onRemove={() => removePhoto("front")}
                    />
                    <PhotoUpload
                      name="Reverso"
                      optional
                      id={back}
                      disabled={!signedIn || busy}
                      onUpload={(f) => upload("back", f)}
                      onRemove={() => removePhoto("back")}
                    />
                  </div>
                  <Field
                    label="¿Algo más que debamos saber?"
                    hint="Sabor, presentación o detalles que no se leen en la foto."
                  >
                    <textarea
                      value={context}
                      onChange={(e) => setContext(e.target.value)}
                      placeholder="Ej. Salsa agridulce de 326 g"
                      maxLength={1000}
                      rows={3}
                      disabled={busy}
                    />
                  </Field>
                  <button
                    className="button primary full"
                    disabled={
                      busy ||
                      !front ||
                      !session.gemini_configured ||
                    !!draft?.saved || draft?.identity_review?.status === "duplicate"
                    }
                    onClick={() =>
                      attempt(async () => {
                        await ensureCapture();
                        await run("/api/analyze");
                      })
                    }
                  >
                    <Sparkles size={18} />
                    {activeJob(job) && job?.label.includes("Analizando")
                      ? "Analizando…"
                      : "Analizar producto"}
                  </button>
                  <p className="micro-copy">
                    También puedes completar la ficha manualmente.
                  </p>
                </section>
                <section className="card information-card">
                  <div className="section-heading">
                    <div className="section-icon purple">
                      <Package size={20} />
                    </div>
                    <div>
                      <h2>La ficha del producto</h2>
                      <p>Revisa los datos antes de generar.</p>
                    </div>
                    <span className="section-number">02</span>
                  </div>
                  <fieldset
                    disabled={busy || !!draft?.saved}
                    className="form-grid"
                  >
                    <Field label="Nombre del producto" wide>
                      <input
                        value={product.name}
                        onChange={(e) => edit("name", e.target.value)}
                        placeholder="Nombre tal como aparece en el producto"
                        maxLength={180}
                      />
                    </Field>
                    <Field label="Marca">
                      <input
                        value={product.brand}
                        onChange={(e) => edit("brand", e.target.value)}
                        placeholder="Marca original"
                        maxLength={120}
                      />
                    </Field>
                    <Field label="Presentación">
                      <input
                        value={product.size}
                        onChange={(e) => edit("size", e.target.value)}
                        placeholder="Ej. 326G, 410ML, 1PZ"
                        maxLength={80}
                      />
                    </Field>
                    <Field label="SKU" hint="Código de barras legible; sin código se crean 10 caracteres.">
                      <input
                        aria-label="SKU"
                        autoCapitalize="characters"
                        autoCorrect="off"
                        spellCheck={false}
                        value={product.sku}
                        readOnly
                        placeholder="Se asigna automáticamente"
                        maxLength={80}
                      />
                    </Field>
                    <Field label="Código de barras">
                      <input
                        autoComplete="off"
                        autoCorrect="off"
                        spellCheck={false}
                        value={product.barcode}
                        onChange={(e) => edit("barcode", e.target.value)}
                        placeholder="Se lee de las fotos"
                        inputMode="numeric"
                        maxLength={32}
                      />
                    </Field>
                    <DriveClassification
                      value={{ category: product.category, subcategory: product.subcategory, tags: product.tags.split(",").map(tag => tag.trim()).filter(Boolean) }}
                      onChange={value => setProduct(previous => ({ ...previous, ...value, tags: value.tags.join(", ") }))}
                      enabled={signedIn}
                      folderKey={(session.email || "") + ":" + (session.folder_id || session.folder || "")}
                      disabled={busy}
                    />
                    <Field label="Tipo reconocido">
                      <input value={product.product_type || ""} maxLength={120} onChange={e => edit("product_type", e.target.value)} placeholder="Por confirmar" />
                    </Field>
                    <Field label="Sabor, color o variante">
                      <input value={product.variant || ""} maxLength={120} onChange={e => edit("variant", e.target.value)} placeholder="Por confirmar" />
                    </Field>
                    {Object.entries(product.attributes || {}).map(([name, value]) => <Field key={name} label={name}><input value={value} maxLength={160} onChange={e => edit("attributes", {...product.attributes, [name]: e.target.value})} /></Field>)}
                    <Field label="Precio de venta · MXN">
                      <div className="input-affix">
                        <span>$</span>
                        <input
                          type="number"
                          inputMode="decimal"
                          min={0}
                          step="0.01"
                          value={product.price || ""}
                          onChange={(e) =>
                            edit("price", Number(e.target.value) || 0)
                          }
                          placeholder="0.00"
                        />
                      </div>
                    </Field>
                    <Field label="Tipo de producto">
                      <select
                        value={product.kind}
                        onChange={(e) => edit("kind", e.target.value)}
                      >
                        <option>Simple</option>
                        <option value="Variable">
                          Variación de un producto
                        </option>
                      </select>
                    </Field>
                    <Field label="Descripción corta" wide>
                      <textarea
                        value={product.short_description}
                        onChange={(e) =>
                          edit("short_description", e.target.value)
                        }
                        placeholder="Una frase con producto, marca y presentación."
                        rows={2}
                        maxLength={300}
                      />
                    </Field>
                    <Field label="Descripción completa" wide>
                      <textarea
                        value={product.description}
                        onChange={(e) => edit("description", e.target.value)}
                        placeholder="Características y usos confirmados del producto."
                        rows={3}
                        maxLength={3000}
                      />
                    </Field>
                  </fieldset>
                  <div className="form-actions">
                    <button
                      className="button small secondary"
                      disabled={busy || !signedIn || !product.name}
                      onClick={() =>
                        attempt(async () => {
                          await persist();
                          const r = await api<{ message: string; draft: Draft }>(
                            "/api/check-product",
                            "POST",
                            {},
                          );
                          setMessage(r.message);
                          setDraft(r.draft);
                        })
                      }
                    >
                      <CheckCircle2 size={15} />
                      Verificar coincidencias
                    </button>
                    <button
                      className="text-button"
                      disabled={
                        busy || !product.name || !session.gemini_configured
                      }
                      onClick={() =>
                        attempt(async () => {
                          await persist();
                          await run("/api/research-price");
                        })
                      }
                    >
                      Investigar precio
                    </button>
                    <button
                      className="text-button"
                      disabled={busy || !front}
                      onClick={() =>
                        attempt(async () => {
                          await persist();
                          await run("/api/find-variants");
                        })
                      }
                    >
                      Buscar variantes
                    </button>
                  </div>
                  {!!product.uncertain_fields?.length && <p className="notice compact" role="status">Datos por confirmar: {product.uncertain_fields.join(", ")}. Revisa las etiquetas antes de guardar.</p>}
                  {draft?.identity_review && <section className="identity-review" aria-label="Coincidencias y clasificación">
                    <h3>Coincidencias y clasificación</h3>
                    <p>{draft.identity_review.message}</p>
                    <p>{draft.identity_review.recommendation}</p>
                    {[...(draft.identity_review.duplicate ? [draft.identity_review.duplicate] : []), ...draft.identity_review.candidates, ...draft.identity_review.parents.filter(p => p.sku === draft.identity_review?.suggested)].map((match, i) => <div className="identity-match" key={match.sku + match._source + i}>
                      {match.image_url && <img src={match.image_url} alt={match.nombre_producto} width={64} height={64} />}
                      <div><strong>{match.nombre_producto}</strong><p>SKU: {match.sku} · {match.Marca || "Marca por confirmar"} · {match._source}</p>
                      <p>{match.precio != null ? `Precio: $${match.precio} · ` : ""}{match.atributo_nombre}: {Array.isArray(match.atributo_valor) ? match.atributo_valor.join(", ") : match.atributo_valor}</p>
                      {match.attributes && <p>{Object.entries(match.attributes).map(([k,v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`).join(" · ")}</p>}
                      {!!match.matching_attributes?.length && <p>Coinciden: {match.matching_attributes.join(", ")}</p>}
                      {!!match.different_attributes?.length && <p>Difieren: {match.different_attributes.join("; ")}</p>}
                      {match.product_id && onOpenProduct && <button className="text-button" onClick={() => onOpenProduct(match.product_id!)}>Abrir o actualizar ficha</button>}
                      {!match.product_id && <button className="text-button" onClick={() => { setQuery(match.sku); go("catalog"); loadCatalog(); }}>Ver en catálogo de Drive</button>}
                      </div>
                    </div>)}
                    {draft.identity_review.sources?.map(note => <p className="micro-copy left" key={note}>{note}</p>)}
                    {draft.identity_review.status !== "duplicate" && <div className="form-actions">
                      <button className="button secondary small" disabled={busy || !draft.identity_review.suggested} onClick={() => chooseFamily("Usar padre existente")}>Utilizar padre existente</button>
                      <button className="button secondary small" disabled={busy} onClick={() => chooseFamily("Crear nuevo padre")}>Crear nuevo padre</button>
                      <button className="button secondary small" disabled={busy} onClick={() => setProduct(p => ({...p, kind: "Simple", parent_sku: "", parent_name: ""}))}>Guardar como simple</button>
                      <button className="text-button" disabled={busy} onClick={() => attempt(async () => { await persist(); await run("/api/find-variants"); })}>Investigar nuevamente</button>
                    </div>}
                    <p className="micro-copy left">Compara marca, familia, presentación y atributos. Puedes corregir la ficha y la clasificación manualmente; la decisión final es tuya.</p>
                  </section>}
                  {draft?.variant_recommendation && (
                    <div className="notice compact">
                      <Info size={16} />
                      <span>{draft.variant_recommendation}</span>
                    </div>
                  )}
                  {draft?.variant_report && (
                    <details className="variant-report">
                      <summary>Ver presentaciones encontradas</summary>
                      <p>{draft.variant_report}</p>
                    </details>
                  )}
                  {product.kind === "Variable" && (
                    <div className="parent-panel">
                      <h3>Familia del producto</h3>
                      <div className="form-grid">
                        <Field label="Vinculación">
                          <select
                            value={product.parent_mode}
                            disabled={busy}
                            onChange={(e) =>
                              edit("parent_mode", e.target.value)
                            }
                          >
                            <option>Crear nuevo padre</option>
                            <option>Usar padre existente</option>
                          </select>
                        </Field>
                        <button
                          className="button secondary small"
                          disabled={busy || !signedIn || !product.name}
                          onClick={loadParents}
                        >
                          <RefreshCw size={14} />
                          Cargar familias
                        </button>
                        {product.parent_mode === "Usar padre existente" && (
                          <Field label="Familia existente" wide>
                            <select
                              disabled={busy}
                              value={product.parent_sku}
                              onChange={(e) => {
                                const name =
                                  parents
                                    .find((p) => p[1] === e.target.value)?.[0]
                                    .split(" · ")[0] || "";
                                setProduct((p) => ({
                                  ...p,
                                  parent_sku: e.target.value,
                                  parent_name: name,
                                }));
                              }}
                            >
                              <option value="">Selecciona una familia</option>
                              {parents.map(([name, sku]) => (
                                <option value={sku} key={sku}>
                                  {name}
                                </option>
                              ))}
                            </select>
                          </Field>
                        )}
                        <Field label="SKU padre">
                          <input
                            autoCapitalize="characters"
                            autoCorrect="off"
                            spellCheck={false}
                            disabled={
                              busy ||
                              product.parent_mode === "Usar padre existente"
                            }
                            value={product.parent_sku}
                            onChange={(e) => edit("parent_sku", e.target.value)}
                            placeholder="Ej. 400638xxxxxxx"
                          />
                        </Field>
                        <Field label="Nombre de la familia">
                          <input
                            disabled={
                              busy ||
                              product.parent_mode === "Usar padre existente"
                            }
                            value={product.parent_name}
                            onChange={(e) =>
                              edit("parent_name", e.target.value)
                            }
                          />
                        </Field>
                        <Field label="Atributo">
                          <input
                            disabled={busy}
                            value={product.attribute}
                            onChange={(e) => edit("attribute", e.target.value)}
                          />
                        </Field>
                        <Field label="Valor de esta variación">
                          <input
                            disabled={busy}
                            value={product.attribute_value}
                            onChange={(e) =>
                              edit("attribute_value", e.target.value)
                            }
                            placeholder={product.size}
                          />
                        </Field>
                      </div>
                      <button
                        className="button secondary small"
                        disabled={busy || !signedIn || !product.parent_sku}
                        onClick={() =>
                          attempt(async () => {
                            await persist();
                            await run("/api/family-cover");
                          })
                        }
                      >
                        Preparar portada de la familia
                      </button>
                      {draft?.cover_id && (
                        <div className="family-cover">
                          <img
                            src={fileUrl(draft.cover_id)}
                            alt="Portada de la familia"
                          />
                          <small>{draft.cover_message}</small>
                        </div>
                      )}
                    </div>
                  )}
                </section>
              </div>

              <section className="image-studio">
                <div className="studio-heading">
                  <div>
                    <div className="eyebrow">
                      <Sparkles size={14} />
                      EL ESTUDIO CREATIVO
                    </div>
                    <h2>Tres maneras de contar tu producto.</h2>
                    <p>El empaque se conserva. La escena cambia.</p>
                  </div>
                  <span className="format-tag">1:1 · Cuadrado</span>
                </div>
                <div className="generation-controls">
                  <p className="p-muted" role="status">
                    1 producto · {selectedSlots.length} imagen(es) · {session.image_provider || "Gemini"} · {session.image_model || "Modelo configurado"}
                    {session.estimated_image_usd != null
                      ? ` · Estimación: USD ${(selectedSlots.length * session.estimated_image_usd).toFixed(3)}`
                      : " · Estimación de costo no disponible"}.
                    La investigación y revisión pueden añadir consumo. Generar confirma este consumo.
                  </p>
                  <label className="approve-check">
                    <input
                      type="checkbox"
                      checked={soundEnabled}
                      onChange={(e) => {
                        const enabled = e.target.checked;
                        setSoundEnabled(enabled);
                        sounds.current!.setEnabled(enabled);
                        if (enabled) sounds.current!.unlock();
                        try { localStorage.setItem("rincon-generation-sounds", enabled ? "on" : "off"); } catch {}
                      }}
                    />
                    Sonidos al iniciar, terminar o fallar la generación
                  </label>
                  <div className="slot-selector">
                    {slots.map((s) => (
                      <label key={s.id}>
                        <input
                          type="checkbox"
                          checked={selectedSlots.includes(s.id)}
                          disabled={busy}
                          onChange={(e) =>
                            setSelectedSlots((current) =>
                              e.target.checked
                                ? [...current, s.id]
                                : current.filter((id) => id !== s.id),
                            )
                          }
                        />
                        {s.name}
                      </label>
                    ))}
                  </div>
                  <button
                    className="button purple"
                    disabled={
                      busy ||
                      !front ||
                      !product.name ||
                      !product.sku ||
                      !session.gemini_configured ||
                      selectedSlots.length === 0 ||
                      !!draft?.saved
                    }
                    onClick={() =>
                      attempt(async () => {
                        await persist();
                        await run("/api/generate", {
                          slots: selectedSlots,
                          automatic_review: review,
                        });
                      })
                    }
                  >
                    <Sparkles size={17} />
                    Generar{" "}
                    {selectedSlots.length === 3
                      ? "las tres imágenes"
                      : selectedSlots.length === 1
                        ? "imagen"
                        : "imágenes"}
                  </button>
                </div>
                <div className="image-grid">
                  {slots.map((s) => {
                    const picture = draft?.images[s.id];
                    return (
                      <article key={s.id} className={"image-card " + s.tone}>
                        <div className="image-card-heading">
                          <span className="image-type-icon">
                            <s.icon size={18} />
                          </span>
                          <div>
                            <h3>{s.name}</h3>
                            <p>{s.description}</p>
                          </div>
                          {picture?.approved && (
                            <CheckCircle2 size={18} className="approved-icon" />
                          )}
                        </div>
                        <div className="image-canvas">
                          {picture ? (
                            <img
                              src={fileUrl(picture.id)}
                              alt={
                                "Imagen " +
                                s.name.toLowerCase() +
                                " de " +
                                product.name
                              }
                            />
                          ) : (
                            <div className="image-empty">
                              <s.icon size={38} strokeWidth={1.2} />
                              <span>
                                {s.id === "1_hd"
                                  ? "Una foto limpia y fiel"
                                  : s.id === "2_uso"
                                    ? "Tu producto en la vida real"
                                    : "Una imagen que atrae miradas"}
                              </span>
                              <small>Aquí aparecerá tu imagen</small>
                            </div>
                          )}
                        </div>
                        <div className="image-tools">
                          {picture ? (
                            <>
                              <label className="approve-check">
                                <input
                                  type="checkbox"
                                  checked={picture.approved}
                                  disabled={busy || !!draft?.saved}
                                  onChange={(e) =>
                                    attempt(async () => {
                                      const r = await api<{ draft: Draft }>(
                                        "/api/images/" + s.id + "/approve",
                                        "POST",
                                        { approved: e.target.checked },
                                      );
                                      setDraft(r.draft);
                                    })
                                  }
                                />
                                {picture.approved
                                  ? "Aprobada"
                                  : "Aprobar imagen"}
                              </label>
                              <a
                                href={fileUrl(picture.id) + "?download=true"}
                                title="Descargar imagen"
                                aria-label={"Descargar " + s.name}
                                className="icon-button"
                              >
                                <Download size={17} />
                              </a>
                              <button
                                className="icon-button"
                                aria-label={"Corregir " + s.name}
                                title="Corregir imagen"
                                disabled={busy || !!draft?.saved}
                                onClick={() => {
                                  setCorrectionSlot(s.id);
                                  setCorrection("");
                                  setCorrectionErrors([]);
                                }}
                              >
                                <RefreshCw size={17} />
                              </button>
                            </>
                          ) : (
                            <span>Lista para generar con tus fotos</span>
                          )}
                        </div>
                        {picture?.qa && !picture.qa.aprobada && (
                          <p className="qa-note">{picture.message}</p>
                        )}
                      </article>
                    );
                  })}
                </div>
                <div className="studio-footnote">
                  <label>
                    <input
                      type="checkbox"
                      checked={review}
                      disabled={busy}
                      onChange={(e) => setReview(e.target.checked)}
                    />
                    Añadir revisión automática de fidelidad
                    <small>Una llamada de texto adicional por imagen.</small>
                  </label>
                  {draft?.brief && (
                    <button
                      className="text-button"
                      onClick={() => setShowBrief(!showBrief)}
                    >
                      <Search size={15} />
                      {showBrief ? "Ocultar" : "Ver"} dirección creativa y
                      fuentes
                    </button>
                  )}
                </div>
                {showBrief && draft?.brief && (
                  <div className="brief-panel">
                    <p>{draft.brief.note}</p>
                    {draft.brief.style_count > 0 && (
                      <span className="pill">
                        {draft.brief.style_count} referencias comerciales de tu
                        Drive
                      </span>
                    )}
                    <div className="brief-prompts">
                      <div>
                        <h3>Lifestyle</h3>
                        <p>{draft.brief.lifestyle}</p>
                      </div>
                      <div>
                        <h3>Comercial</h3>
                        <p>{draft.brief.comercial}</p>
                      </div>
                    </div>
                    {draft.brief.sources.length > 0 && (
                      <div className="sources">
                        <strong>Fuentes de investigación</strong>
                        {draft.brief.sources.map((s) => (
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noreferrer"
                            key={s.url}
                          >
                            {s.title}
                            <ExternalLink size={13} />
                          </a>
                        ))}
                      </div>
                    )}
                    {draft.brief.search_suggestions && (
                      <iframe
                        title="Sugerencias de búsqueda de Google"
                        srcDoc={draft.brief.search_suggestions}
                        sandbox="allow-popups allow-popups-to-escape-sandbox"
                        className="search-suggestions"
                      />
                    )}
                  </div>
                )}
              </section>
              <div className="save-bar">
                <div>
                  <span className="save-icon">
                    <CheckCircle2 size={22} />
                  </span>
                  <div>
                    <strong>
                      {draft?.saved
                        ? "Producto guardado"
                        : "Todo listo para tu inventario"}
                    </strong>
                    <p>
                      {draft?.saved
                        ? "La ficha y las imágenes aprobadas están en Drive."
                        : !allApproved
                          ? "Aprueba tus imágenes antes de guardar."
                          : "Revisa los datos y guarda la ficha con las imágenes aprobadas."}
                    </p>
                  </div>
                </div>
                <button
                  className="button primary"
                  disabled={
                    busy ||
                    !signedIn ||
                    !front ||
                    !product.name ||
                    !product.sku ||
                    !allApproved ||
                    !!draft?.saved || draft?.identity_review?.status === "duplicate"
                  }
                  onClick={() =>
                    attempt(async () => {
                      await persist();
                      await run("/api/save", { confirm: true });
                    })
                  }
                >
                  <Check size={17} />
                  {draft?.saved
                    ? "Guardado en Drive"
                    : "Guardar producto en Drive"}
                </button>
                {draft?.sync_status === "pending_repair" && <div className="notice compact"><p>{draft.sync_error}</p><button className="button secondary small" disabled={busy} onClick={() => attempt(async () => { await run("/api/capture-sync"); })}>Reparar catálogo maestro</button></div>}
              </div>
            </>
          )}

          {section === "catalog" && (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">TU CATÁLOGO</p>
                  <h1>
                    Inventario<span className="title-dot">.</span>
                  </h1>
                  <p>Los productos de tu hoja Lista completa.</p>
                </div>
                <button
                  className="button primary"
                  disabled={!signedIn || busy}
                  onClick={loadCatalog}
                >
                  <RefreshCw size={17} />
                  {catalogLoaded ? "Actualizar" : "Cargar inventario"}
                </button>
              </div>
              <section className="card">
                <div className="catalog-toolbar">
                  <div className="search-field">
                    <Search size={18} />
                    <input
                      placeholder="Buscar nombre, SKU o marca"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </div>
                  {sheetUrl && (
                    <a
                      className="button secondary small"
                      target="_blank"
                      rel="noreferrer"
                      href={sheetUrl}
                    >
                      Abrir hoja
                      <ExternalLink size={14} />
                    </a>
                  )}
                  <a className="button secondary small" href="/inventory-hub">
                    Conteos y movimientos
                  </a>
                  <a
                    className="button secondary small"
                    href="/woocommerce-batch-sync"
                  >
                    Subida a WooCommerce
                  </a>
                </div>
                {!catalogLoaded ? (
                  <div className="empty-state">
                    <Package size={42} strokeWidth={1.2} />
                    <h2>Tu inventario, en un solo lugar</h2>
                    <p>
                      Carga tu hoja para buscar productos y revisar existencias.
                    </p>
                  </div>
                ) : (
                  <>
                    <p className="table-caption">
                      {rows.length} productos en tu hoja
                    </p>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Producto</th>
                            <th>SKU</th>
                            <th>Marca</th>
                            <th>Tipo</th>
                            <th>Existencias</th>
                            <th>Precio</th>
                            <th>Categoría</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows
                            .filter((row) =>
                              [row.nombre_producto, row.sku, row.Marca].some(
                                (v) =>
                                  String(v || "")
                                    .toLowerCase()
                                    .includes(query.toLowerCase()),
                              ),
                            )
                            .map((row, i) => (
                              <tr key={String(row.sku) + i}>
                                <td>
                                  <strong>{row.nombre_producto}</strong>
                                </td>
                                <td className="sku-value">{row.sku}</td>
                                <td>{row.Marca}</td>
                                <td>
                                  <span className="pill">
                                    {row.tipo === "variable"
                                      ? "Familia"
                                      : row.tipo === "variation"
                                        ? "Variación"
                                        : "Simple"}
                                  </span>
                                </td>
                                <td>
                                  {row.tipo === "variable"
                                    ? "—"
                                    : row.Existencias}
                                </td>
                                <td>
                                  {row.tipo === "variable"
                                    ? "—"
                                    : "$" + Number(row.precio || 0).toFixed(2)}
                                </td>
                                <td>{row.categorias}</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </section>
              <div className="notice">
                <Info size={18} />
                <span>
                  Los productos padre reúnen las variaciones. Su precio y
                  existencias pertenecen a cada presentación.
                </span>
              </div>
            </>
          )}

          {section === "loyverse" && (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">PUNTO DE VENTA</p>
                  <h1>
                    Loyverse<span className="title-dot">.</span>
                  </h1>
                  <p>
                    Compara tu catálogo y revisa los productos antes de
                    enviarlos.
                  </p>
                </div>
              </div>
              <div className="connection-grid">
                <section className="card">
                  <div className="section-heading">
                    <ShoppingBag size={23} />
                    <div>
                      <h2>Conexión con Loyverse</h2>
                      <p>Elige la sucursal que vas a actualizar.</p>
                    </div>
                  </div>
                  <Field label="Token de acceso">
                    <input
                      type="password"
                      autoComplete="off"
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      placeholder="Tu token de Loyverse"
                      disabled={busy}
                    />
                  </Field>
                  <div className="form-actions">
                    <button
                      className="button primary"
                      disabled={!signedIn || busy || !token}
                      onClick={() =>
                        attempt(async () => {
                          const r = await api<{
                            stores: { id: string; name: string }[];
                          }>("/loyverse/connect", "POST", { token });
                          setToken("");
                          setStores(r.stores);
                          setStore(r.stores[0]?.id || "");
                          setPreview("");
                          setLoyRows([]);
                          setMessage(
                            "Loyverse conectado. Elige una sucursal y compara.",
                          );
                        })
                      }
                    >
                      Conectar Loyverse
                    </button>
                    {stores.length > 0 && (
                      <button
                        className="text-button"
                        disabled={busy}
                        onClick={() =>
                          attempt(async () => {
                            await api("/loyverse/disconnect", "POST", {});
                            setStores([]);
                            setLoyRows([]);
                            setPreview("");
                            setStore("");
                          })
                        }
                      >
                        Desconectar
                      </button>
                    )}
                  </div>
                  <Field label="Sucursal">
                    <select
                      value={store}
                      disabled={busy || stores.length === 0}
                      onChange={(e) => {
                        setStore(e.target.value);
                        setPreview("");
                        setLoyRows([]);
                        setLoySelected([]);
                        setLoyConfirmed(false);
                      }}
                    >
                      <option value="">Selecciona una sucursal</option>
                      {stores.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <button
                    className="button purple full"
                    disabled={busy || !store}
                    onClick={() =>
                      attempt(async () => {
                        setPreview("");
                        setLoyConfirmed(false);
                        setLoySelected([]);
                        const r = await api<{ id: string; rows: LoyRow[] }>(
                          "/loyverse/preview",
                          "POST",
                          { store },
                        );
                        setPreview(r.id);
                        setLoyRows(r.rows);
                        setMessage(
                          "Comparación lista. Revisa las acciones y selecciona hasta 20 productos o familias.",
                        );
                      })
                    }
                  >
                    <RefreshCw size={17} />
                    Comparar catálogo
                  </button>
                </section>
                <section className="card connection-note">
                  <Layers size={32} strokeWidth={1.4} />
                  <h2>Revisa antes de enviar</h2>
                  <p>
                    Los productos existentes actualizan existencias. Los
                    productos nuevos y sus familias se crean según la revisión.
                  </p>
                  <p>
                    El precio y las variaciones se muestran antes de confirmar.
                    Cada revisión vence en cinco minutos.
                  </p>
                  <button
                    className="button secondary"
                    disabled={posting}
                    onClick={() =>
                      attempt(async () => {
                        const r = await api<{ job: LoyJob }>(
                          "/loyverse-upload-status",
                        );
                        if (r.job) setLoyJob(r.job);
                        else
                          setMessage(
                            "No hay una subida en curso en esta sesión.",
                          );
                      })
                    }
                  >
                    Consultar última subida
                  </button>
                </section>
              </div>
              {loyJob && (
                <div className="job-banner">
                  <RefreshCw size={20} className={loyWorking ? "spin" : ""} />
                  <div>
                    <strong>
                      {loyJob.done}/{loyJob.total} confirmados
                    </strong>
                    <span>
                      {loyJob.phase}
                      {loyJob.current ? " · " + loyJob.current : ""}
                    </span>
                    <progress value={loyJob.done} max={loyJob.total || 1} />
                    {loyJob.error && <span>{loyJob.error}</span>}
                    {loyJob.uncertain && (
                      <span>
                        Revisa en Loyverse el resultado de {loyJob.uncertain}{" "}
                        antes de repetir.
                      </span>
                    )}
                  </div>
                </div>
              )}
              {loyRows.length > 0 && (
                <section className="card">
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Enviar</th>
                          <th>Producto / SKU</th>
                          <th>Drive</th>
                          <th>Loyverse</th>
                          <th>Precio</th>
                          <th>Acción</th>
                          <th>Detalle</th>
                        </tr>
                      </thead>
                      <tbody>
                        {loyRows.map((r) => (
                          <tr key={r.sku}>
                            <td>
                              <input
                                type="checkbox"
                                aria-label={"Seleccionar " + r.sku}
                                disabled={busy || !r.eligible}
                                checked={loySelected.includes(r.sku)}
                                onChange={(e) => {
                                  setLoySelected((s) =>
                                    e.target.checked
                                      ? [...s, r.sku]
                                      : s.filter((v) => v !== r.sku),
                                  );
                                  setLoyConfirmed(false);
                                }}
                              />
                            </td>
                            <td>
                              <strong>{r.name}</strong>
                              <small className="block">{r.sku}</small>
                            </td>
                            <td>{r.drive}</td>
                            <td>{r.loyverse ?? "—"}</td>
                            <td>{r.price}</td>
                            <td>{r.status}</td>
                            <td>{r.detail}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="send-controls">
                    <label>
                      <input
                        type="checkbox"
                        checked={loyConfirmed}
                        disabled={busy}
                        onChange={(e) => setLoyConfirmed(e.target.checked)}
                      />
                      Revisé los productos y autorizo estas acciones en
                      Loyverse.
                    </label>
                    <button
                      className="button primary"
                      disabled={
                        busy ||
                        !loyConfirmed ||
                        !preview ||
                        loySelected.length < 1 ||
                        loySelected.length > 20
                      }
                      onClick={() =>
                        attempt(async () => {
                          const r = await api<LoyJob>(
                            "/loyverse/apply",
                            "POST",
                            { id: preview, skus: loySelected },
                          );
                          setLoyJob(r);
                          setPreview("");
                          setLoyConfirmed(false);
                        })
                      }
                    >
                      Enviar {loySelected.length} seleccionados
                    </button>
                  </div>
                </section>
              )}
            </>
          )}

          {section === "settings" && (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">TU CUENTA</p>
                  <h1>
                    Ajustes<span className="title-dot">.</span>
                  </h1>
                  <p>Conecta las herramientas que usa tu catálogo.</p>
                </div>
              </div>
              <div className="settings-grid">
                <section className="card">
                  <div className="section-heading">
                    <Layers size={24} />
                    <div>
                      <h2>Google Drive</h2>
                      <p>
                        {signedIn
                          ? session.email
                          : "Conecta la cuenta del inventario."}
                      </p>
                    </div>
                    {signedIn && <span className="pill green">Conectado</span>}
                  </div>
                  {signedIn ? (
                    <>
                      <Field
                        label="Carpeta del proyecto"
                        hint={"Actual: " + (session.folder || "Proyecto_IA")}
                      >
                        <input
                          value={folder}
                          onChange={(e) => setFolder(e.target.value)}
                          placeholder="https://drive.google.com/drive/folders/…"
                          disabled={busy}
                        />
                      </Field>
                      <p className="micro-copy left">
                        Déjalo vacío para usar Proyecto_IA. La carpeta debe
                        contener inventario_completo.
                      </p>
                      <button
                        className="button secondary"
                        disabled={busy}
                        onClick={() =>
                          attempt(async () => {
                            await api("/api/settings", "POST", { folder });
                            setFolder("");
                            await refresh();
                            setMessage("Carpeta validada y guardada.");
                          })
                        }
                      >
                        Guardar carpeta
                      </button>
                      <form
                        action="/logout"
                        method="post"
                        className="logout-form"
                      >
                        <button className="text-button" disabled={busy}>
                          <LogOut size={15} />
                          Cerrar sesión
                        </button>
                      </form>
                    </>
                  ) : (
                    <a href="/login" className="button primary">
                      Conectar Google Drive
                    </a>
                  )}
                </section>
                <section className="card">
                  <div className="section-heading">
                    <Sparkles size={24} />
                    <div>
                      <h2>Gemini</h2>
                      <p>Tu proyecto de Google genera las imágenes.</p>
                    </div>
                    {session.gemini_configured && (
                      <span className="pill green">Configurado</span>
                    )}
                  </div>
                  <Field label="Clave de API">
                    <input
                      type="password"
                      value={key}
                      onChange={(e) => setKey(e.target.value)}
                      placeholder={
                        session.gemini_configured
                          ? "Clave configurada · ingresa una nueva para cambiarla"
                          : "AIza…"
                      }
                      autoComplete="off"
                      disabled={busy}
                    />
                  </Field>
                  <p className="micro-copy left">
                    Tu clave se guarda cifrada en el servidor, asociada a tu cuenta y tienda. Permanece configurada al volver a iniciar sesión.
                  </p>
                  <button
                    className="button purple"
                    disabled={busy || !signedIn || !key}
                    onClick={() =>
                      attempt(async () => {
                        await api("/api/settings", "POST", { api_key: key });
                        setKey("");
                        await refresh();
                        setMessage(
                          "Clave guardada. Ya puedes generar imágenes.",
                        );
                      })
                    }
                  >
                    Guardar clave
                  </button>
                  <div className="form-actions">
                    <button className="button secondary small" disabled={busy || !session.gemini_configured} onClick={() => attempt(async () => {
                      const r = await api<{message: string; image_model_available: boolean; text_model_available: boolean}>("/api/settings/gemini/test", "POST", {});
                      setMessage(r.message + (r.image_model_available && r.text_model_available ? " Los dos modelos actuales están disponibles." : " Revisa la disponibilidad de los modelos actuales en tu proyecto."));
                    })}>Comprobar clave y modelos</button>
                    <button className="button secondary small" disabled={busy || !session.gemini_configured} onClick={() => attempt(async () => {
                      await api("/api/settings/gemini", "DELETE"); setKey(""); await refresh(); setMessage("Clave personal eliminada.");
                    })}>Eliminar clave</button>
                  </div>
                  <p className="micro-copy left">Configuración activa: {session.gemini_configured ? "clave personal de Ajustes" : "sin clave personal"}.</p>
                </section>
              </div>
              <section className="card consumption">
                <div className="section-heading">
                  <div>
                    <h2>Consumo registrado</h2>
                    <p>Registro disponible de llamadas y tokens. La facturación final se consulta en el proveedor.</p>
                  </div>
                </div>
                <div className="usage-grid">
                  {[
                    {
                      label: "Llamadas a Gemini",
                      value: session.usage?.count || 0,
                    },
                    {
                      label: "Consultas reutilizadas",
                      value: session.usage?.cache_hits || 0,
                    },
                    {
                      label: "Tokens de entrada",
                      value: session.usage?.input_tokens || 0,
                    },
                    {
                      label: "Tokens de salida",
                      value: session.usage?.output_tokens || 0,
                    },
                  ].map((m) => (
                    <div key={m.label}>
                      <strong>{m.value.toLocaleString("es-MX")}</strong>
                      <span>{m.label}</span>
                    </div>
                  ))}
                </div>
                <details>
                  <summary>Modelos del estudio</summary>
                  <p>
                    Textos e investigación: {session.text_model}. Imágenes:{" "}
                    {session.image_model}.
                  </p>
                </details>
              </section>
            </>
          )}

          {section === "help" && (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">GUÍA DE USO</p>
                  <h1>
                    Un producto, paso a paso<span className="title-dot">.</span>
                  </h1>
                </div>
              </div>
              <div className="help-grid">
                {[
                  {
                    name: "Conecta tu cuenta",
                    text: "En Ajustes, conecta Google Drive y guarda la clave de Gemini. El inventario está en Proyecto_IA o en la carpeta que selecciones.",
                  },
                  {
                    name: "Fotografía el producto",
                    text: "Sube el frente completo y, de ser posible, el reverso. Usa buena luz para que el empaque, marca y presentación sean legibles.",
                  },
                  {
                    name: "Revisa la información",
                    text: "Analiza las fotos o captura los datos manualmente. Verifica SKU y código de barras. El precio se investiga solo cuando lo solicitas.",
                  },
                  {
                    name: "Genera y corrige",
                    text: "Elige Catálogo, Lifestyle o Comercial. Lifestyle muestra personas consumiendo o usando el producto; Comercial toma inspiración artística de tus imágenes de Drive. Pulsa el icono de regenerar e indica las correcciones.",
                  },
                  {
                    name: "Aprueba y guarda",
                    text: "Aprueba cada imagen que quieras guardar. Guardar producto sube las imágenes a Drive y registra la ficha en Lista completa. Los productos padre no tienen precio ni existencias propios.",
                  },
                  {
                    name: "Publica o sincroniza",
                    text: "Desde Inventario puedes abrir conteos y subida a WooCommerce. En Loyverse, compara una sucursal, selecciona los productos, revisa las acciones y confirma el envío.",
                  },
                ].map((s, i) => (
                  <section className="card" key={s.name}>
                    <span className="help-number">0{i + 1}</span>
                    <h2>{s.name}</h2>
                    <p>{s.text}</p>
                  </section>
                ))}
              </div>
              <div className="notice">
                <Info size={18} />
                <span>
                  Al volver a entrar, se recuperan el borrador guardado y la
                  configuración de Gemini de tu cuenta. Si Google solicita
                  acceso, vuelve a conectar Drive. Ante una subida interrumpida,
                  consulta su progreso antes de repetir.
                </span>
              </div>
            </>
          )}
          <footer className="app-footer">
            <img src="/logo.png" width="20" height="20" alt="" />
            <span>El Rincón de Asia · Suite e-commerce</span>
            <a
              href="https://rincon.creandotusite.com/"
              target="_blank"
              rel="noreferrer"
            >
              Nuestra tienda
              <ExternalLink size={12} />
            </a>
          </footer>
        </main>
      </div>
      {correctionSlot && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget && !busy) setCorrectionSlot(null);
          }}
        >
          <section
            className="correction-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="correction-title"
          >
            <div className="dialog-heading">
              <span className="section-icon purple">
                <RefreshCw size={20} />
              </span>
              <div>
                <p className="eyebrow">AFINA EL RESULTADO</p>
                <h2 id="correction-title">
                  Corregir {slots.find((s) => s.id === correctionSlot)?.name}
                </h2>
              </div>
              <button
                className="icon-button"
                disabled={busy}
                aria-label="Cerrar corrección"
                onClick={() => setCorrectionSlot(null)}
              >
                <X size={21} />
              </button>
            </div>
            {draft?.images[correctionSlot] && (
              <img
                className="correction-preview"
                src={fileUrl(draft.images[correctionSlot].id)}
                alt="Imagen que se corregirá"
              />
            )}
            <Field label="¿Qué quieres cambiar?">
              <textarea
                autoFocus
                value={correction}
                onChange={(e) => setCorrection(e.target.value)}
                placeholder="Ej. Que la persona sostenga los palillos correctamente y que el empaque conserve su color."
                rows={3}
                maxLength={600}
                disabled={busy}
              />
            </Field>
            <details>
              <summary>Marcar errores comunes</summary>
              <div className="error-options">
                {(session.errors || []).map((label) => (
                  <label key={label}>
                    <input
                      type="checkbox"
                      checked={correctionErrors.includes(label)}
                      disabled={busy}
                      onChange={(e) =>
                        setCorrectionErrors((v) =>
                          e.target.checked
                            ? [...v, label]
                            : v.filter((x) => x !== label),
                        )
                      }
                    />
                    {label}
                  </label>
                ))}
              </div>
            </details>
            {(draft?.images[correctionSlot]?.history?.length || 0) > 0 && (
              <small className="history-note">
                Se conservarán {draft?.images[correctionSlot]?.history?.length}{" "}
                correcciones anteriores.
              </small>
            )}
            <button
              className="button purple full"
              disabled={
                busy || (!correction.trim() && !correctionErrors.length)
              }
              onClick={() =>
                attempt(async () => {
                  await persist();
                  await run("/api/images/" + correctionSlot + "/correct", {
                    feedback: correction,
                    errors: correctionErrors,
                    automatic_review: review,
                  });
                  setCorrectionSlot(null);
                })
              }
            >
              <RefreshCw size={17} />
              Aplicar correcciones
            </button>
            <p className="micro-copy">
              Se usan la imagen anterior y las fotos originales del producto.
            </p>
          </section>
        </div>
      )}
    </div>
  );
}
