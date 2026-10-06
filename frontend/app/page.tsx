"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowLeft,
  Check,
  CheckCircle2,
  ChevronRight,
  Camera,
  CircleAlert,
  Cloud,
  Download,
  ExternalLink,
  Home,
  Images,
  Layers,
  Loader2,
  LogOut,
  MoreHorizontal,
  Package,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  ShoppingBag,
  Sparkles,
  Upload,
  WifiOff,
  X,
} from "lucide-react";
import dynamic from "next/dynamic";
const CaptureStudio = dynamic(() => import("../components/CaptureStudio"), { ssr: false, loading: () => <p>Cargando captura…</p> });

type Section = "home" | "products" | "generate" | "inventory" | "more";
type Product = {
  id: string;
  sku: string;
  barcode: string;
  name: string;
  brand: string;
  category: string;
  subcategory: string;
  short_description: string;
  long_description: string;
  tags: string[];
  attributes: Record<string, string | string[]>;
  product_type: string;
  parent_id: string | null;
  price: number | null;
  cost: number | null;
  stock: number | null;
  woocommerce_stock: number | null;
  loyverse_stock: number | null;
  status: string;
  sync_status: string;
  version: number;
  image_id?: string;
  woocommerce_product_id?: number;
  woocommerce_variation_id?: number;
  loyverse_item_id?: string;
  last_woocommerce_sync?: string;
};
type Picture = {
  id: string;
  drive_file_id: string;
  role: string;
  status: string;
  metadata_json: Record<string, unknown>;
};
type Brief = {
  lifestyle?: string;
  comercial?: string;
  note?: string;
  sources?: { title: string; url: string }[];
  search_suggestions?: string;
};
type Asset = {
  id: string;
  image_id: string;
  product_id: string;
  job_id: string;
  sku: string;
  product_name: string;
  slot: string;
  estimated_correction_usd?: number | null;
  status: string;
  history: string[];
  metadata_json: {
    brief?: Brief;
    qa?: { resumen?: string };
    width?: number;
    height?: number;
  };
};
type Job = {
  id: string;
  kind: string;
  product_id: string;
  status: string;
  progress: number;
  message: string;
  estimated_cost?: number;
  created_at: string;
  payload: {
    in_flight?: unknown;
    proposal?: Record<string, unknown>;
    version?: number;
    product?: { name?: string; sku?: string };
  };
};
type Event = {
  id: string;
  product_id?: string;
  action: string;
  source: string;
  destination: string;
  status: string;
  message: string;
  created_at: string;
  job_id?: string;
};
type Detail = {
  product: Product;
  images: Picture[];
  assets: Asset[];
  jobs: Job[];
  movements: {
    id: string;
    source: string;
    source_event_id: string;
    quantity_before: number;
    quantity_after: number;
    delta: number;
    created_at: string;
  }[];
  sync_events: Event[];
  variants: Product[];
};
type Session = {
  authenticated: boolean;
  email?: string;
  gemini_configured?: boolean;
  folder?: string;
  image_model?: string;
};
type Status = {
  ready: boolean;
  configured: boolean;
  worker_ready: boolean;
  role: string;
  message: string;
};
type Dashboard = {
  stats: Record<string, number>;
  activity: { id: string; action: string; created_at: string }[];
  ecommerce: null | {
    sales_today: number;
    pending_orders: number;
    orders: {
      id: string;
      woocommerce_id: number;
      status: string;
      total: number;
      currency: string;
    }[];
  };
};
type Quote = {
  products: number;
  images: number;
  provider: string;
  model: string;
  estimated_usd: number | null;
  estimate_token: string;
  note: string;
};
type Preview = {
  preview_id: string;
  rows: number;
  errors: { row: number; sku: string; message: string }[];
  sample: { sku: string; name: string }[];
  note: string;
};
type Confirm = {
  title: string;
  text: string;
  label: string;
  uncertain?: boolean;
  action: () => Promise<void>;
};
const nav = [
  { id: "home", label: "Inicio", icon: Home },
  { id: "products", label: "Productos", icon: ShoppingBag },
  { id: "generate", label: "Generar", icon: Sparkles },
  { id: "inventory", label: "Inventario", icon: Layers },
  { id: "more", label: "Más", icon: MoreHorizontal },
] as const;
const stateLabel: Record<string, string> = {
  queued: "En cola",
  processing: "Procesando",
  completed: "Para revisar",
  failed: "Error",
  approved: "Aprobada",
  rejected: "Rechazada",
  published: "Publicada",
  pending: "Pendiente",
  synced: "Sincronizado",
  difference: "Diferencia",
  error: "Error",
  connected: "Conectado ✓",
  disconnected: "Sin conectar",
  token_expired: "Token vencido",
};
const kinds = [
  { id: "1_hd", label: "Producto limpio", note: "Fondo blanco y empaque fiel" },
  { id: "2_uso", label: "Lifestyle", note: "Personas consumiendo o usando" },
  {
    id: "3_comercial",
    label: "Comercial",
    note: "Composición artística del producto",
  },
];
const currency = (n: number | null | undefined) =>
  n == null
    ? "—"
    : new Intl.NumberFormat("es-MX", {
        style: "currency",
        currency: "MXN",
      }).format(n);
const date = (v?: string) =>
  v
    ? new Date(v).toLocaleString("es-MX", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
const pictureUrl = (id: string) =>
  "/api/platform/images/" + encodeURIComponent(id);
const active = (job: Job) => ["queued", "processing"].includes(job.status);
const blank = (): Product => ({
  id: "",
  sku: "",
  barcode: "",
  name: "",
  brand: "",
  category: "",
  subcategory: "",
  short_description: "",
  long_description: "",
  tags: [],
  attributes: {},
  product_type: "simple",
  parent_id: null,
  price: 0,
  cost: null,
  stock: 0,
  woocommerce_stock: null,
  loyverse_stock: null,
  status: "pending",
  sync_status: "pending",
  version: 1,
});
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
  const timer = setTimeout(() => controller.abort(), 90000);
  try {
    const response = await fetch(path, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      signal: controller.signal,
      headers:
        body && !(body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {},
      body: body
        ? body instanceof FormData
          ? body
          : JSON.stringify(body)
        : undefined,
    });
    const data = await response.json();
    if (!response.ok)
      throw new ApiError(
        typeof data.detail === "string"
          ? data.detail
          : data.error ||
              "No se pudo confirmar la operación. Revisa los datos y su estado.",
        response.status,
      );
    return data;
  } catch (e) {
    if ((e as Error).name === "AbortError")
      throw new Error(
        "La conexión tardó demasiado. Revisa el estado antes de reintentar.",
      );
    throw e;
  } finally {
    clearTimeout(timer);
  }
}
function Badge({ value }: { value: string }) {
  return (
    <span className={"p-badge " + value}>{stateLabel[value] || value}</span>
  );
}
function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="p-empty">
      <Package size={36} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}

export default function Platform() {
  const [section, setSection] = useState<Section>("home");
  const [moreTab, setMoreTab] = useState("connections");
  const [session, setSession] = useState<Session>({ authenticated: false });
  const [status, setStatus] = useState<Status>({
    ready: false,
    configured: false,
    worker_ready: false,
    role: "viewer",
    message: "Cargando…",
  });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [online, setOnline] = useState(true);
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [dashboard, setDashboard] = useState<Dashboard>();
  const [detail, setDetail] = useState<Detail | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Product>(blank);
  const [attributeText, setAttributeText] = useState("{}");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [connections, setConnections] = useState<
    { name: string; status: string; note?: string }[]
  >([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [selectionMode, setSelectionMode] = useState("selected");
  const [category, setCategory] = useState("");
  const [slots, setSlots] = useState(kinds.map((k) => k.id));
  const [quantity, setQuantity] = useState(1);
  const [automaticReview, setAutomaticReview] = useState(false);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [generationTab, setGenerationTab] = useState("batch");
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [comparison, setComparison] = useState<Detail | null>(null);
  const [feedback, setFeedback] = useState("");
  const [imageRole, setImageRole] = useState("gallery");
  const [stock, setStock] = useState(0);
  const [stockReason, setStockReason] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [uncertainChecked, setUncertainChecked] = useState(false);
  const scanRef = useRef<HTMLInputElement>(null);
  const referenceRef = useRef<HTMLInputElement>(null);
  const importRef = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const canEdit = session.authenticated && status.role !== "viewer";
  const isAdmin = status.role === "admin";
  const ready = session.authenticated && status.ready;
  const go = useCallback((target: Section) => {
    location.hash = target;
    setSection(target);
    setDetail(null);
    setEditing(false);
    setError("");
  }, []);
  const attempt = async (action: () => Promise<void>) => {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (e) {
      setError((e as Error).message);
      if (e instanceof ApiError && e.status === 401)
        setSession({ authenticated: false });
    } finally {
      setBusy(false);
    }
  };
  const reloadBase = useCallback(async () => {
    const [s, st] = await Promise.all([
      api<Session>("/api/session"),
      api<Status>("/api/platform/status"),
    ]);
    setSession(s);
    setStatus(st);
    return { s, st };
  }, []);
  const reloadOperations = useCallback(async () => {
    const [d, j, a] = await Promise.all([
      api<Dashboard>("/api/platform/dashboard"),
      api<{ items: Job[] }>("/api/platform/jobs"),
      api<{ items: Asset[] }>("/api/platform/assets"),
    ]);
    setDashboard(d);
    setJobs(j.items);
    setAssets(a.items);
  }, []);
  const loadProducts = useCallback(async () => {
    const data = await api<{ items: Product[]; total: number }>(
      `/api/platform/products?q=${encodeURIComponent(query)}&filter=${encodeURIComponent(filter)}&offset=${offset}&limit=50`,
    );
    setProducts(data.items);
    setTotal(data.total);
  }, [query, filter, offset]);
  useEffect(() => {
    const change = () => {
      const hash = location.hash.slice(1);
      if (nav.some((n) => n.id === hash)) setSection(hash as Section);
      else if (["studio", "catalog", "settings", "loyverse"].includes(hash)) {
        setSection(
          hash === "catalog"
            ? "products"
            : hash === "studio"
              ? "generate"
              : "more",
        );
        if (hash === "settings") setMoreTab("settings");
      }
    };
    const connection = () => setOnline(navigator.onLine);
    change();
    connection();
    window.addEventListener("hashchange", change);
    window.addEventListener("online", connection);
    window.addEventListener("offline", connection);
    reloadBase()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    if ("serviceWorker" in navigator)
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    return () => {
      window.removeEventListener("hashchange", change);
      window.removeEventListener("online", connection);
      window.removeEventListener("offline", connection);
    };
  }, [reloadBase]);
  useEffect(() => {
    if (!ready || !online) return;
    const timer = setTimeout(
      () => loadProducts().catch((e) => setError(e.message)),
      250,
    );
    return () => clearTimeout(timer);
  }, [ready, online, loadProducts]);
  useEffect(() => {
    if (!ready || !online) return;
    let stopped = false;
    const run = () =>
      reloadOperations().catch((e) => {
        if (!stopped) {
          setError(e.message);
          if (e.status === 401) setSession({ authenticated: false });
        }
      });
    run();
    const timer = setInterval(run, jobs.some(active) ? 4000 : 30000);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [ready, online, jobs.some(active), reloadOperations]);
  useEffect(() => {
    setQuote(null);
  }, [selected, selectionMode, category, slots, quantity, automaticReview]);
  useEffect(() => {
    if (section !== "more" || !ready) return;
    Promise.all([
      api<{ items: Event[] }>("/api/platform/events"),
      api<{ items: typeof connections }>("/api/platform/connections"),
    ])
      .then(([e, c]) => {
        setEvents(e.items);
        setConnections(c.items);
      })
      .catch((e) => setError(e.message));
  }, [section, moreTab, ready]);
  useEffect(() => {
    if (!confirm && !selectedAsset) return;
    const previous = document.activeElement as HTMLElement | null;
    modalRef.current?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const keys = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) {
        setConfirm(null);
        setSelectedAsset(null);
      }
      if (e.key === "Tab") {
        const controls = modalRef.current?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), a[href]",
        );
        if (controls?.length) {
          const first = controls[0],
            last = controls[controls.length - 1];
          if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
          } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };
    document.addEventListener("keydown", keys);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", keys);
      previous?.focus();
    };
  }, [confirm, selectedAsset, busy]);
  const openProduct = async (id: string) => {
    const data = await api<Detail>("/api/platform/products/" + id);
    setDetail(data);
    setForm(data.product);
    setStock(data.product.stock || 0);
    setAttributeText(JSON.stringify(data.product.attributes, null, 2));
    setEditing(false);
  };
  const ask = (value: Confirm) => {
    setUncertainChecked(false);
    setConfirm(value);
  };
  const operation = async (path: string) => {
    await api(path, "POST", {
      confirm: true,
      request_key: crypto.randomUUID(),
    });
    setNotice(
      "Trabajo en cola. Puedes cerrar el navegador y consultar su progreso después.",
    );
    await reloadOperations();
  };
  const saveProduct = async () => {
    let attrs;
    try {
      attrs = JSON.parse(attributeText);
      if (!attrs || typeof attrs !== "object" || Array.isArray(attrs))
        throw new Error();
    } catch {
      throw new Error("Los atributos deben ser un objeto JSON válido.");
    }
    const data = await api<{ product: Product }>(
      form.id ? "/api/platform/products/" + form.id : "/api/platform/products",
      form.id ? "PUT" : "POST",
      { ...form, attributes: attrs },
    );
    await openProduct(data.product.id);
    await loadProducts();
    setNotice("Producto guardado en el catálogo maestro.");
  };
  const uploadReference = async (file: File) => {
    if (!form.id)
      throw new Error("Guarda la ficha antes de agregar referencias.");
    const data = new FormData();
    data.append("image", file);
    const uploaded = await api<{ id: string }>("/api/uploads", "POST", data);
    await api(`/api/platform/products/${form.id}/reference`, "POST", {
      upload_id: uploaded.id,
    });
    await openProduct(form.id);
    await loadProducts();
    setNotice(
      "Referencia guardada. La IA la utilizará para conservar el producto.",
    );
  };
  const scan = async (file: File) => {
    const data = new FormData();
    data.append("image", file);
    const uploaded = await api<{ id: string }>("/api/uploads", "POST", data);
    const codes = await api<{ codes: string[] }>(
      "/api/platform/barcode",
      "POST",
      { upload_id: uploaded.id },
    );
    if (!codes.codes.length)
      throw new Error(
        "No se detectó un código. Acerca la cámara, mejora la luz o escríbelo.",
      );
    setQuery(codes.codes[0]);
    setOffset(0);
    setFilter("all");
    go("products");
  };
  const batch = () => ({
    product_ids: selectionMode === "selected" ? selected : [],
    category: selectionMode === "category" ? category : null,
    pending: selectionMode === "pending",
    slots,
    quantity,
    quality: "native",
    automatic_review: automaticReview,
  });
  const reviewAsset = async (asset: Asset) => {
    setSelectedAsset(asset);
    setFeedback("");
    setImageRole(
      asset.slot === "2_uso"
        ? "lifestyle"
        : asset.slot === "3_comercial"
          ? "commercial"
          : "main",
    );
    setComparison(
      await api<Detail>("/api/platform/products/" + asset.product_id),
    );
  };
  const approve = async (state: "approved" | "rejected") => {
    if (!selectedAsset) return;
    await api(`/api/platform/assets/${selectedAsset.id}/review`, "POST", {
      status: state,
      role: imageRole,
    });
    await reloadOperations();
    setSelectedAsset(null);
    setNotice(
      state === "approved"
        ? "Imagen aprobada. Publicar es una acción separada."
        : "Imagen rechazada; el archivo se conserva.",
    );
  };
  const retry = (job: Job) =>
    ask({
      title: "Reintentar trabajo",
      text: job.payload.in_flight
        ? "La operación se interrumpió con resultado incierto. Verifica los archivos de Drive y la tienda antes de autorizar otro intento; puede generar un cargo adicional."
        : "Se conservarán las imágenes ya terminadas. Las operaciones de IA restantes pueden generar consumo adicional.",
      label: "Autorizar intento",
      uncertain: !!job.payload.in_flight,
      action: async () => {
        await api(`/api/platform/jobs/${job.id}/retry`, "POST", {
          confirm: true,
          uncertainty_reviewed: true,
          request_key: crypto.randomUUID(),
        });
        await reloadOperations();
      },
    });
  const heading = {
    home: [
      "Tu tienda, al día",
      "Atiende lo importante y continúa con tu catálogo.",
    ],
    products: ["Productos", "El catálogo maestro de El Rincón de Asia."],
    generate: [
      "Dale vida a tus productos",
      "Genera, revisa y publica con el control en tus manos.",
    ],
    inventory: ["Inventario", "Existencias y diferencias entre tus canales."],
    more: [
      "Tu espacio de trabajo",
      "Conexiones, sincronización y herramientas.",
    ],
  }[section];

  return (
    <div className="platform">
      <a className="skip-link" href="#workspace">
        Ir al contenido
      </a>
      <header className="p-header">
        <a className="brand" href="#home">
          <img src="/logo.png" width={46} height={46} alt="El Rincón de Asia" />
          <span>
            El Rincón de Asia<small>Suite ecommerce IA</small>
          </span>
        </a>
        <div className="p-header-actions">
          <a
            href="https://rincon.creandotusite.com/"
            target="_blank"
            rel="noreferrer"
            className="p-store"
          >
            Ver tienda <ExternalLink size={14} />
          </a>
          <button
            aria-label="Cuenta y conexiones"
            onClick={() => {
              go("more");
              setMoreTab("settings");
            }}
            className="p-avatar"
          >
            {session.email?.slice(0, 1).toUpperCase() || (
              <Settings2 size={18} />
            )}
          </button>
        </div>
      </header>
      <nav className="p-navigation" aria-label="Navegación principal">
        {nav.map((n) => (
          <a
            key={n.id}
            href={"#" + n.id}
            className={section === n.id ? "active" : ""}
            aria-current={section === n.id ? "page" : undefined}
            onClick={() => {
              setDetail(null);
              setEditing(false);
            }}
          >
            <n.icon size={22} />
            <span>{n.label}</span>
          </a>
        ))}
        <div className="p-nav-note">
          <Cloud size={19} />
          <span>
            {session.folder || "Proyecto_IA"}
            <small>De Asia para tu casa.</small>
          </span>
        </div>
      </nav>
      <main className="p-main" id="workspace">
        {!online && (
          <div className="p-alert" role="status">
            <WifiOff size={19} />
            <span>
              Sin conexión. Tus trabajos aceptados continúan en el servidor.
              Conéctate para actualizar.
            </span>
            <button
              disabled={busy}
              onClick={() =>
                attempt(async () => {
                  await reloadBase();
                  if (ready) await reloadOperations();
                })
              }
            >
              Reintentar
            </button>
          </div>
        )}
        {error && (
          <div className="p-alert error" role="alert">
            <CircleAlert size={19} />
            <span>{error}</span>
            <button onClick={() => setError("")} aria-label="Cerrar error">
              <X size={18} />
            </button>
          </div>
        )}
        {notice && (
          <div className="p-alert success" role="status">
            <CheckCircle2 size={19} />
            <span>{notice}</span>
            <button onClick={() => setNotice("")} aria-label="Cerrar aviso">
              <X size={18} />
            </button>
          </div>
        )}
        <div className="p-title">
          <div>
            <span className="p-eyebrow">
              {section === "home"
                ? "BIENVENIDO A TU SUITE"
                : "EL RINCÓN DE ASIA"}
            </span>
            <h1>{heading[0]}</h1>
            <p>{heading[1]}</p>
          </div>
          {ready && (
            <button
              className="button secondary p-refresh"
              disabled={busy}
              onClick={() =>
                attempt(async () => {
                  await reloadBase();
                  await reloadOperations();
                  await loadProducts();
                })
              }
              aria-label="Actualizar panel"
            >
              <RefreshCw size={18} />
              <span>Actualizar</span>
            </button>
          )}
        </div>
        {loading && (
          <div className="inline-loading">
            <Loader2 className="spin" size={22} />
            Cargando tu espacio…
          </div>
        )}
        {!loading && !session.authenticated && (
          <div className="p-welcome">
            <img src="/logo.png" width={76} height={76} alt="" />
            <div>
              <h2>Tu catálogo merece brillar.</h2>
              <p>
                Conecta tu cuenta para trabajar con tus productos, imágenes y
                archivos de Drive.
              </p>
              <a className="button primary" href="/login">
                <Cloud size={19} />
                Conectar Google Drive
              </a>
            </div>
            <div className="p-welcome-art" aria-hidden="true">
              <Sparkles size={60} />
              <Package size={90} />
            </div>
          </div>
        )}
        {!loading && session.authenticated && !status.ready && (
          <div className="p-alert">
            <Cloud size={20} />
            <div>
              <strong>La migración del catálogo está preparada.</strong>
              <p>
                {status.message} La captura compatible está disponible en
                Generar.
              </p>
            </div>
          </div>
        )}
        {ready && !status.worker_ready && (
          <div className="p-alert">
            <CircleAlert size={20} />
            <span>
              El worker está desconectado. Puedes consultar y editar el
              catálogo; las nuevas operaciones en cola esperan su configuración.
            </span>
          </div>
        )}
        {session.authenticated && status.role === "viewer" && (
          <p className="p-readonly">Acceso de lectura · {session.email}</p>
        )}

        {section === "home" && (
          <>
            <div className="p-hero">
              <div>
                <span className="p-eyebrow">DE ASIA PARA TU CASA</span>
                <h2>
                  Todo lo que necesita
                  <br />
                  tu catálogo, en un lugar.
                </h2>
                <p>Fotos que atraen. Productos que conectan.</p>
                <button className="button white" onClick={() => go("generate")}>
                  <Sparkles size={19} />
                  Generar imágenes
                  <ChevronRight size={16} />
                </button>
              </div>
              <div className="p-hero-art" aria-hidden="true">
                <span className="hero-disc">
                  <ShoppingBag size={94} />
                </span>
                <span className="hero-spark">
                  <Sparkles size={31} />
                </span>
                <span className="hero-label">CATÁLOGO + IA</span>
              </div>
            </div>
            <div className="p-stats">
              {[
                {
                  label: "Ventas online · hoy",
                  value: ready
                    ? dashboard?.ecommerce
                      ? currency(dashboard.ecommerce.sales_today)
                      : "Sin lectura"
                    : "—",
                  icon: ShoppingBag,
                  target: "more",
                },
                {
                  label: "Pedidos pendientes",
                  value: dashboard?.ecommerce?.pending_orders ?? "—",
                  icon: Package,
                  target: "more",
                },
                {
                  label: "Stock bajo",
                  value: dashboard?.stats.low_stock ?? "—",
                  icon: Layers,
                  target: "inventory",
                  filter: "low",
                },
                {
                  label: "Sin stock",
                  value: dashboard?.stats.out_of_stock ?? "—",
                  icon: CircleAlert,
                  target: "inventory",
                  filter: "out",
                },
                {
                  label: "Errores de sincronización",
                  value: dashboard?.stats.sync_errors ?? "—",
                  icon: RefreshCw,
                  target: "products",
                  filter: "error",
                },
                {
                  label: "Generaciones pendientes",
                  value: dashboard?.stats.pending_jobs ?? "—",
                  icon: Sparkles,
                  target: "generate",
                },
              ].map((s) => (
                <button
                  key={s.label}
                  className="p-stat"
                  onClick={() => {
                    go(s.target as Section);
                    setFilter(s.filter || "all");
                    setMoreTab("sync");
                  }}
                >
                  <span className="p-stat-icon">
                    <s.icon size={20} />
                  </span>
                  <small>{s.label}</small>
                  <strong>{s.value}</strong>
                  <ChevronRight size={16} />
                </button>
              ))}
            </div>
            <div className="p-two-column">
              <section className="p-card">
                <div className="p-card-title">
                  <h2>Necesitan tu atención</h2>
                  <span className="p-dot" />
                </div>
                <button
                  className="p-action-row"
                  onClick={() => {
                    go("generate");
                    setGenerationTab("review");
                  }}
                >
                  <Images size={22} />
                  <span>
                    Revisar imágenes
                    <small>
                      {assets.filter((a) => a.status === "completed").length}{" "}
                      imágenes para aprobar
                    </small>
                  </span>
                  <ChevronRight size={18} />
                </button>
                <button
                  className="p-action-row"
                  onClick={() => {
                    go("products");
                    setFilter("pending");
                  }}
                >
                  <ShoppingBag size={22} />
                  <span>
                    Productos pendientes
                    <small>
                      {dashboard?.stats.pending_products ?? "—"} fichas por
                      publicar
                    </small>
                  </span>
                  <ChevronRight size={18} />
                </button>
                <button
                  className="p-action-row"
                  onClick={() => {
                    go("more");
                    setMoreTab("sync");
                  }}
                >
                  <RefreshCw size={22} />
                  <span>
                    Actualizar pedidos y stock
                    <small>Consultar WooCommerce</small>
                  </span>
                  <ChevronRight size={18} />
                </button>
              </section>
              <section className="p-card">
                <div className="p-card-title">
                  <h2>Actividad reciente</h2>
                  <Activity size={18} />
                </div>
                {dashboard?.activity.length ? (
                  dashboard.activity.map((a) => (
                    <div className="p-activity" key={a.id}>
                      <span className="p-activity-dot" />
                      <div>
                        <strong>{a.action.replaceAll(".", " · ")}</strong>
                        <small>{date(a.created_at)}</small>
                      </div>
                    </div>
                  ))
                ) : (
                  <Empty
                    title="Tu actividad aparecerá aquí"
                    text="Cada operación importante queda registrada."
                  />
                )}
              </section>
            </div>
            {dashboard?.ecommerce && (
              <section className="p-card">
                <h2>Pedidos recientes</h2>
                {dashboard.ecommerce.orders.map((o) => (
                  <div className="p-action-row" key={o.id}>
                    <Package size={20} />
                    <span>
                      Pedido #{o.woocommerce_id}
                      <small>{o.status}</small>
                    </span>
                    <strong>
                      {o.currency === "MXN"
                        ? currency(o.total)
                        : `${o.currency} ${o.total}`}
                    </strong>
                  </div>
                ))}
              </section>
            )}
          </>
        )}

        {(section === "products" || section === "inventory") && ready && (
          <>
            {!detail && !editing && (
              <>
                <div className="p-toolbar">
                  <label className="p-search">
                    <Search size={19} />
                    <input
                      value={query}
                      onChange={(e) => {
                        setQuery(e.target.value);
                        setOffset(0);
                      }}
                      placeholder="Buscar nombre / SKU / código"
                      aria-label="Buscar productos"
                    />
                  </label>
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => scanRef.current?.click()}
                  >
                    <Camera size={18} />
                    <span>Escanear</span>
                  </button>
                  {section === "products" && canEdit && (
                    <button
                      className="button primary"
                      onClick={() => {
                        setForm(blank());
                        setAttributeText("{}");
                        setEditing(true);
                      }}
                    >
                      <Plus size={18} />
                      Nuevo
                    </button>
                  )}
                </div>
                <div className="p-chips" aria-label="Filtros">
                  {(section === "inventory"
                    ? [
                        ["all", "Todo"],
                        ["low", "Stock bajo"],
                        ["out", "Sin stock"],
                        ["difference", "Diferencias"],
                        ["error", "Error"],
                      ]
                    : [
                        ["all", "Todos"],
                        ["published", "Publicados"],
                        ["pending", "Pendientes"],
                        ["error", "Errores"],
                        ["out", "Sin stock"],
                      ]
                  ).map(([id, label]) => (
                    <button
                      key={id}
                      aria-pressed={filter === id}
                      className={filter === id ? "active" : ""}
                      onClick={() => {
                        setFilter(id);
                        setOffset(0);
                      }}
                    >
                      {label}
                    </button>
                  ))}
                  <span>{total} productos</span>
                </div>
                {products.length ? (
                  <div
                    className={
                      section === "inventory"
                        ? "p-inventory-grid"
                        : "p-product-grid"
                    }
                  >
                    {products.map((p) => (
                      <button
                        className={
                          section === "inventory"
                            ? "p-inventory-card"
                            : "p-product-card"
                        }
                        key={p.id}
                        onClick={() => attempt(() => openProduct(p.id))}
                      >
                        {section === "products" && (
                          <div className="p-product-photo">
                            {p.image_id ? (
                              <img
                                src={pictureUrl(p.image_id)}
                                alt={p.name}
                                loading="lazy"
                              />
                            ) : (
                              <Package size={48} />
                            )}
                            <Badge value={p.status} />
                          </div>
                        )}
                        <div className="p-product-info">
                          <small>{p.brand || "Sin marca"}</small>
                          <h3>{p.name}</h3>
                          <code>{p.sku}</code>
                          {section === "products" ? (
                            <div className="p-price-row">
                              <strong>{currency(p.price)}</strong>
                              <span>
                                {p.stock == null
                                  ? "Familia"
                                  : `${p.stock} en stock`}
                              </span>
                            </div>
                          ) : (
                            <div className="p-stock-grid">
                              <span>
                                Maestro<strong>{p.stock ?? "—"}</strong>
                              </span>
                              <span>
                                WooCommerce
                                <strong>{p.woocommerce_stock ?? "—"}</strong>
                              </span>
                              <span>
                                Loyverse
                                <strong>{p.loyverse_stock ?? "—"}</strong>
                              </span>
                            </div>
                          )}
                          <div className="p-channel-row">
                            <span>
                              WooCommerce <Badge value={p.sync_status} />
                            </span>
                            <small>
                              Loyverse ·{" "}
                              {p.loyverse_item_id
                                ? "Vinculado"
                                : "Próximamente"}
                            </small>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <Empty
                    title="Tu catálogo empieza aquí"
                    text="Importa tus archivos o WooCommerce desde Más, o crea tu primer producto."
                  />
                )}
                {total > 50 && (
                  <div className="p-pagination">
                    <button
                      className="button secondary"
                      disabled={offset === 0}
                      onClick={() => setOffset(Math.max(0, offset - 50))}
                    >
                      Anterior
                    </button>
                    <span>
                      {offset + 1}–{Math.min(offset + 50, total)} de {total}
                    </span>
                    <button
                      className="button secondary"
                      disabled={offset + 50 >= total}
                      onClick={() => setOffset(offset + 50)}
                    >
                      Siguiente
                    </button>
                  </div>
                )}
              </>
            )}
            {(detail || editing) && (
              <>
                <button
                  className="p-back"
                  onClick={() => {
                    setDetail(null);
                    setEditing(false);
                  }}
                >
                  <ArrowLeft size={18} />
                  Volver al catálogo
                </button>
                {editing ? (
                  <section className="p-card">
                    <h2>{form.id ? "Editar producto" : "Nuevo producto"}</h2>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        attempt(saveProduct);
                      }}
                    >
                      <div className="p-form-grid">
                        {[
                          ["name", "Nombre"],
                          ["sku", "SKU"],
                          ["barcode", "Código de barras"],
                          ["brand", "Marca"],
                          ["category", "Categoría"],
                          ["subcategory", "Subcategoría"],
                        ].map(([key, label]) => (
                          <label key={key}>
                            {label}
                            <input
                              required={["name", "sku"].includes(key)}
                              value={String(form[key as keyof Product] ?? "")}
                              maxLength={key === "sku" ? 80 : 180}
                              onChange={(e) =>
                                setForm({ ...form, [key]: e.target.value })
                              }
                            />
                          </label>
                        ))}
                        <label>
                          Tipo
                          <select
                            value={form.product_type}
                            onChange={(e) =>
                              setForm({ ...form, product_type: e.target.value })
                            }
                          >
                            <option value="simple">Producto simple</option>
                            <option value="variable">
                              Familia / padre FULL
                            </option>
                            <option value="variation">Variación</option>
                          </select>
                        </label>
                        {form.product_type === "variation" && (
                          <label>
                            ID interno del padre
                            <input
                              value={form.parent_id || ""}
                              required
                              onChange={(e) =>
                                setForm({ ...form, parent_id: e.target.value })
                              }
                            />
                          </label>
                        )}
                        {form.product_type !== "variable" &&
                          [
                            ["price", "Precio MXN"],
                            ["cost", "Costo MXN"],
                            ["stock", "Stock maestro"],
                          ].map(([key, label]) => (
                            <label key={key}>
                              {label}
                              <input
                                type="number"
                                min={0}
                                max={1000000}
                                step="0.01"
                                value={
                                  form[key as "price" | "cost" | "stock"] ?? ""
                                }
                                onChange={(e) =>
                                  setForm({
                                    ...form,
                                    [key]:
                                      e.target.value === ""
                                        ? null
                                        : Number(e.target.value),
                                  })
                                }
                              />
                            </label>
                          ))}
                      </div>
                      <label className="p-form-field">
                        Descripción corta
                        <textarea
                          maxLength={600}
                          rows={3}
                          value={form.short_description}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              short_description: e.target.value,
                            })
                          }
                        />
                      </label>
                      <label className="p-form-field">
                        Descripción larga
                        <textarea
                          maxLength={5000}
                          rows={6}
                          value={form.long_description}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              long_description: e.target.value,
                            })
                          }
                        />
                      </label>
                      <label className="p-form-field">
                        Etiquetas, separadas por comas
                        <input
                          value={form.tags.join(", ")}
                          onChange={(e) =>
                            setForm({
                              ...form,
                              tags: e.target.value
                                .split(",")
                                .map((t) => t.trim())
                                .filter(Boolean),
                            })
                          }
                        />
                      </label>
                      <label className="p-form-field">
                        Atributos
                        <textarea
                          rows={3}
                          value={attributeText}
                          onChange={(e) => setAttributeText(e.target.value)}
                          placeholder={'{"Tamaño":"41 g"}'}
                        />
                      </label>
                      <div className="p-button-row">
                        <button
                          className="button primary"
                          disabled={busy || !online}
                          type="submit"
                        >
                          <Check size={18} />
                          Guardar
                        </button>
                        <button
                          className="button secondary"
                          type="button"
                          onClick={() => setEditing(false)}
                        >
                          Cancelar
                        </button>
                      </div>
                    </form>
                  </section>
                ) : (
                  detail && (
                    <>
                      <div className="p-product-detail">
                        <section className="p-card">
                          <div className="p-gallery">
                            {detail.images.length ? (
                              detail.images.map((i) => (
                                <div key={i.id}>
                                  <img
                                    src={pictureUrl(i.id)}
                                    alt={detail.product.name + " · " + i.role}
                                  />
                                  <div className="p-image-caption">
                                    <span>
                                      {i.role === "reference"
                                        ? "Referencia original"
                                        : i.role === "main"
                                          ? "Principal"
                                          : i.role}
                                    </span>
                                    <Badge value={i.status} />
                                  </div>
                                  {canEdit && i.role === "reference" && <button className="p-link" disabled={busy} onClick={() => ask({ title: "Aprobar foto original", text: "Usar esta fotografía también en la galería del producto. La referencia original se conserva. Publicar es una acción separada.", label: "Aprobar original", action: async () => { await api(`/api/platform/products/${form.id}/images/${i.id}/approve-original`, "POST", { confirm: true, request_key: crypto.randomUUID() }); await openProduct(form.id); } })}>Aprobar original para galería</button>}
                              {canEdit && i.role !== "reference" && (
                                    <button
                                      className="p-link"
                                      onClick={() =>
                                        attempt(async () => {
                                          await api(
                                            `/api/platform/products/${form.id}/reference-from-image/${i.id}`,
                                            "POST",
                                            {},
                                          );
                                          await openProduct(form.id);
                                        })
                                      }
                                    >
                                      Usar como referencia
                                    </button>
                                  )}
                                </div>
                              ))
                            ) : (
                              <Empty
                                title="Agrega una referencia"
                                text="La foto original es la base de las imágenes con IA."
                              />
                            )}
                          </div>
                          {canEdit && (
                            <button
                              className="button secondary"
                              disabled={busy}
                              onClick={() => referenceRef.current?.click()}
                            >
                              <Camera size={18} />
                              Agregar foto original
                            </button>
                          )}
                        </section>
                        <section className="p-card">
                          <small className="p-eyebrow">
                            {detail.product.brand || "PRODUCTO"}
                          </small>
                          <h2>{detail.product.name}</h2>
                          <code>{detail.product.sku}</code>
                          <div className="p-price-row">
                            <strong>{currency(detail.product.price)}</strong>
                            <Badge value={detail.product.status} />
                          </div>
                          <dl className="p-facts">
                            <div>
                              <dt>Stock maestro</dt>
                              <dd>{detail.product.stock ?? "Familia FULL"}</dd>
                            </div>
                            <div>
                              <dt>Código de barras</dt>
                              <dd>{detail.product.barcode || "—"}</dd>
                            </div>
                            <div>
                              <dt>Categoría</dt>
                              <dd>
                                {[
                                  detail.product.category,
                                  detail.product.subcategory,
                                ]
                                  .filter(Boolean)
                                  .join(" / ") || "—"}
                              </dd>
                            </div>
                            <div>
                              <dt>WooCommerce</dt>
                              <dd>
                                <Badge value={detail.product.sync_status} />
                              </dd>
                            </div>
                            <div>
                              <dt>Última lectura</dt>
                              <dd>
                                {date(detail.product.last_woocommerce_sync)}
                              </dd>
                            </div>
                            <div>
                              <dt>ID interno</dt>
                              <dd>
                                <code>{detail.product.id}</code>
                              </dd>
                            </div>
                          </dl>
                          <div className="p-button-row">
                            {canEdit && (
                              <>
                                <button
                                  className="button primary"
                                  onClick={() => setEditing(true)}
                                >
                                  Editar
                                </button>
                                <button
                                  className="button secondary"
                                  disabled={busy || !status.worker_ready}
                                  onClick={() =>
                                    ask({
                                      title: "Generar datos con IA",
                                      text: "Se analizarán las referencias para proponer descripciones, etiquetas y categoría. Revisa la propuesta antes de guardarla. Esta operación consume API de texto.",
                                      label: "Generar propuesta",
                                      action: () =>
                                        operation(
                                          `/api/platform/products/${form.id}/enrich`,
                                        ),
                                    })
                                  }
                                >
                                  <Sparkles size={18} />
                                  Generar IA
                                </button>
                                {form.product_type !== "variable" && (
                                  <button
                                    className="button secondary"
                                    onClick={() => {
                                      setSelected([form.id]);
                                      setSelectionMode("selected");
                                      go("generate");
                                    }}
                                  >
                                    Generar imágenes
                                  </button>
                                )}
                              </>
                            )}
                            {isAdmin && (
                              <button
                                className="button primary"
                                disabled={busy || !status.worker_ready}
                                onClick={() =>
                                  ask({
                                    title: form.woocommerce_product_id
                                      ? "Actualizar WooCommerce"
                                      : "Publicar en WooCommerce",
                                    text: "Se enviará la ficha y únicamente las imágenes aprobadas. WordPress recibirá los archivos y la tienda asociará sus IDs. El stock se sincroniza por separado.",
                                    label: form.woocommerce_product_id
                                      ? "Actualizar"
                                      : "Publicar",
                                    action: () =>
                                      operation(
                                        `/api/platform/products/${form.id}/publish`,
                                      ),
                                  })
                                }
                              >
                                {form.woocommerce_product_id
                                  ? "Actualizar WooCommerce"
                                  : "Publicar WooCommerce"}
                              </button>
                            )}
                            {form.woocommerce_product_id && (
                              <a
                                className="button secondary"
                                target="_blank"
                                rel="noreferrer"
                                href={`https://rincon.creandotusite.com/?p=${form.woocommerce_product_id}`}
                              >
                                Ver en tienda <ExternalLink size={16} />
                              </a>
                            )}
                          </div>
                        </section>
                      </div>
                      {detail.jobs
                        .filter(
                          (j) =>
                            j.kind === "enrichment" &&
                            j.status === "completed" &&
                            j.payload.proposal,
                        )
                        .slice(0, 1)
                        .map((j) => (
                          <section className="p-card p-proposal" key={j.id}>
                            <h2>Propuesta de IA lista</h2>
                            <p>
                              Revisa los textos sugeridos antes de guardar. SKU,
                              precio y existencias se conservan.
                            </p>
                            <button
                              className="button secondary"
                              disabled={!canEdit || busy}
                              onClick={() => {
                                const proposal = j.payload.proposal!;
                                const attrs = {
                                  ...form.attributes,
                                  ...(proposal.size
                                    ? { Tamaño: String(proposal.size) }
                                    : {}),
                                };
                                setForm({
                                  ...form,
                                  ...Object.fromEntries(
                                    Object.entries(proposal).filter(
                                      ([k, v]) => k !== "size" && !!v,
                                    ),
                                  ),
                                  attributes: attrs,
                                } as Product);
                                setAttributeText(
                                  JSON.stringify(attrs, null, 2),
                                );
                                setEditing(true);
                              }}
                            >
                              Revisar propuesta
                            </button>
                          </section>
                        ))}
                      <div className="p-two-column">
                        <section className="p-card">
                          <h2>Información del producto</h2>
                          <h3>Descripción corta</h3>
                          <p className="p-text">
                            {detail.product.short_description || "Pendiente"}
                          </p>
                          <h3>Descripción larga</h3>
                          <p className="p-text">
                            {detail.product.long_description || "Pendiente"}
                          </p>
                          <div className="p-chips">
                            {detail.product.tags.map((t) => (
                              <span className="p-tag" key={t}>
                                {t}
                              </span>
                            ))}
                          </div>
                          <dl className="p-facts">
                            {Object.entries(detail.product.attributes).map(
                              ([k, v]) => (
                                <div key={k}>
                                  <dt>{k}</dt>
                                  <dd>{Array.isArray(v) ? v.join(", ") : v}</dd>
                                </div>
                              ),
                            )}
                          </dl>
                          {detail.variants.length > 0 && (
                            <>
                              <h3>Variantes</h3>
                              {detail.variants.map((v) => (
                                <button
                                  className="p-action-row"
                                  key={v.id}
                                  onClick={() =>
                                    attempt(() => openProduct(v.id))
                                  }
                                >
                                  <Package size={18} />
                                  <span>
                                    {v.name}
                                    <small>
                                      {v.sku} · {v.stock ?? "—"} en stock
                                    </small>
                                  </span>
                                  <ChevronRight size={16} />
                                </button>
                              ))}
                            </>
                          )}
                        </section>
                        <section className="p-card">
                          <h2>Inventario y sincronización</h2>
                          <div className="p-stock-grid">
                            <span>
                              Maestro<strong>{form.stock ?? "—"}</strong>
                            </span>
                            <span>
                              WooCommerce
                              <strong>{form.woocommerce_stock ?? "—"}</strong>
                            </span>
                            <span>
                              Loyverse
                              <strong>{form.loyverse_stock ?? "—"}</strong>
                            </span>
                          </div>
                          {canEdit && form.product_type !== "variable" && (
                            <>
                              <label className="p-form-field">
                                Nuevo stock maestro
                                <input
                                  type="number"
                                  min={0}
                                  value={stock}
                                  onChange={(e) =>
                                    setStock(Number(e.target.value))
                                  }
                                />
                              </label>
                              <label className="p-form-field">
                                Motivo del movimiento
                                <input
                                  value={stockReason}
                                  onChange={(e) =>
                                    setStockReason(e.target.value)
                                  }
                                  placeholder="Ej. conteo físico"
                                />
                              </label>
                              <div className="p-button-row">
                                <button
                                  className="button secondary"
                                  disabled={
                                    busy || stockReason.trim().length < 3
                                  }
                                  onClick={() =>
                                    ask({
                                      title: "Registrar movimiento",
                                      text: `Stock maestro: ${form.stock} → ${stock}. Motivo: ${stockReason}. Se registrará origen, fecha y evento.`,
                                      label: "Registrar",
                                      action: async () => {
                                        await api(
                                          `/api/platform/products/${form.id}/stock`,
                                          "POST",
                                          {
                                            quantity: stock,
                                            reason: stockReason,
                                            version: form.version,
                                            event_id: crypto.randomUUID(),
                                          },
                                        );
                                        await openProduct(form.id);
                                        await loadProducts();
                                      },
                                    })
                                  }
                                >
                                  Registrar stock
                                </button>
                                <button
                                  className="button secondary"
                                  disabled={busy || !status.worker_ready}
                                  onClick={() =>
                                    ask({
                                      title: "Sincronizar stock",
                                      text: `Enviar ${form.stock} unidades del stock maestro a WooCommerce. Si la tienda cambió desde la última lectura, la operación se detendrá para revisar.`,
                                      label: "Enviar stock",
                                      action: () =>
                                        operation(
                                          `/api/platform/products/${form.id}/sync-stock`,
                                        ),
                                    })
                                  }
                                >
                                  <RefreshCw size={16} />
                                  Sincronizar
                                </button>
                              </div>
                            </>
                          )}
                          <h3>Historial de movimientos</h3>
                          {detail.movements.map((m) => (
                            <div className="p-log" key={m.id}>
                              <strong>
                                {m.quantity_before ?? "—"} → {m.quantity_after}{" "}
                                <small>
                                  ({m.delta > 0 ? "+" : ""}
                                  {m.delta})
                                </small>
                              </strong>
                              <span>
                                {m.source} · {date(m.created_at)}
                              </span>
                              <code>{m.source_event_id}</code>
                            </div>
                          ))}
                          {detail.sync_events.map((e) => (
                            <div className="p-log" key={e.id}>
                              <strong>
                                {e.action} <Badge value={e.status} />
                              </strong>
                              <span>
                                {e.source} → {e.destination} ·{" "}
                                {date(e.created_at)}
                              </span>
                              <p>{e.message}</p>
                            </div>
                          ))}
                        </section>
                      </div>
                    </>
                  )
                )}
              </>
            )}
          </>
        )}

        {section === "generate" && (
          <>
            {!ready ? (
              <CaptureStudio embedded />
            ) : (
              <>
                <div className="p-chips p-tabs">
                  <button
                    className={generationTab === "batch" ? "active" : ""}
                    onClick={() => setGenerationTab("batch")}
                  >
                    Generación masiva
                  </button>
                  <button
                    className={generationTab === "review" ? "active" : ""}
                    onClick={() => setGenerationTab("review")}
                  >
                    Revisar imágenes{" "}
                    <span>
                      {assets.filter((a) => a.status === "completed").length}
                    </span>
                  </button>
                  <button
                    className={generationTab === "jobs" ? "active" : ""}
                    onClick={() => setGenerationTab("jobs")}
                  >
                    Trabajos <span>{jobs.filter(active).length}</span>
                  </button>
                </div>
                {generationTab === "batch" && (
                  <div className="p-generation-grid">
                    <section className="p-card">
                      <div className="p-card-title">
                        <h2>1. Elige tus productos</h2>
                        <Package size={20} />
                      </div>
                      <label className="p-form-field">
                        Selección
                        <select
                          value={selectionMode}
                          disabled={!canEdit}
                          onChange={(e) => setSelectionMode(e.target.value)}
                        >
                          <option value="selected">
                            Uno o varios productos
                          </option>
                          <option value="category">Una categoría</option>
                          <option value="pending">Todos los pendientes</option>
                        </select>
                      </label>
                      {selectionMode === "category" ? (
                        <label className="p-form-field">
                          Categoría
                          <input
                            value={category}
                            onChange={(e) => setCategory(e.target.value)}
                            list="categories"
                          />
                          <datalist id="categories">
                            {Array.from(
                              new Set(products.map((p) => p.category)),
                            ).map((c) => (
                              <option key={c} value={c} />
                            ))}
                          </datalist>
                        </label>
                      ) : selectionMode === "pending" ? (
                        <p>
                          Se seleccionarán los productos pendientes que tengan
                          fotos de referencia. Los padres FULL se excluyen.
                        </p>
                      ) : (
                        <>
                          <label className="p-search">
                            <Search size={18} />
                            <input
                              value={query}
                              onChange={(e) => {
                                setQuery(e.target.value);
                                setOffset(0);
                              }}
                              placeholder="Buscar productos"
                            />
                          </label>
                          <div className="p-select-list">
                            {products
                              .filter((p) => p.product_type !== "variable")
                              .map((p) => (
                                <label className="p-select-product" key={p.id}>
                                  <input
                                    type="checkbox"
                                    disabled={!canEdit}
                                    checked={selected.includes(p.id)}
                                    onChange={(e) =>
                                      setSelected(
                                        e.target.checked
                                          ? [...selected, p.id]
                                          : selected.filter(
                                              (id) => id !== p.id,
                                            ),
                                      )
                                    }
                                  />
                                  {p.image_id ? (
                                    <img src={pictureUrl(p.image_id)} alt="" />
                                  ) : (
                                    <Package size={28} />
                                  )}
                                  <span>
                                    <strong>{p.name}</strong>
                                    <small>
                                      {p.sku} · {p.brand}
                                    </small>
                                  </span>
                                </label>
                              ))}
                          </div>
                          {total > 50 && (
                            <div className="p-pagination">
                              <button
                                className="p-link"
                                disabled={offset === 0}
                                onClick={() =>
                                  setOffset(Math.max(0, offset - 50))
                                }
                              >
                                Anterior
                              </button>
                              <span>
                                {offset + 1}–{Math.min(offset + 50, total)} de{" "}
                                {total}
                              </span>
                              <button
                                className="p-link"
                                disabled={offset + 50 >= total}
                                onClick={() => setOffset(offset + 50)}
                              >
                                Siguiente
                              </button>
                            </div>
                          )}
                          <p>{selected.length} productos seleccionados</p>
                        </>
                      )}
                    </section>
                    <section className="p-card">
                      <div className="p-card-title">
                        <h2>2. Prepara las imágenes</h2>
                        <Sparkles size={20} />
                      </div>
                      {kinds.map((k) => (
                        <label className="p-choice" key={k.id}>
                          <input
                            type="checkbox"
                            disabled={!canEdit}
                            checked={slots.includes(k.id)}
                            onChange={(e) =>
                              setSlots(
                                e.target.checked
                                  ? [...slots, k.id]
                                  : slots.filter((s) => s !== k.id),
                              )
                            }
                          />
                          <span>
                            <strong>{k.label}</strong>
                            <small>{k.note}</small>
                          </span>
                        </label>
                      ))}
                      <div className="p-form-grid">
                        <label>
                          Cantidad por tipo y producto
                          <select
                            disabled={!canEdit}
                            value={quantity}
                            onChange={(e) =>
                              setQuantity(Number(e.target.value))
                            }
                          >
                            {[1, 2, 3, 4].map((n) => (
                              <option value={n} key={n}>
                                {n}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Calidad
                          <select value="native" disabled>
                            <option value="native">
                              Nativa del generador · 1K
                            </option>
                          </select>
                        </label>
                      </div>
                      <label className="p-choice">
                        <input
                          type="checkbox"
                          disabled={!canEdit}
                          checked={automaticReview}
                          onChange={(e) => setAutomaticReview(e.target.checked)}
                        />
                        <span>
                          <strong>Revisión de IA opcional</strong>
                          <small>
                            Añade consumo de texto; tú decides la aprobación
                            final.
                          </small>
                        </span>
                      </label>
                      <button
                        className="button primary p-full"
                        disabled={busy || !canEdit || !slots.length || !online}
                        onClick={() =>
                          attempt(async () =>
                            setQuote(
                              await api<Quote>(
                                "/api/platform/generation/estimate",
                                "POST",
                                batch(),
                              ),
                            ),
                          )
                        }
                      >
                        <Sparkles size={18} />
                        Calcular lote
                      </button>
                      {quote && (
                        <div className="p-quote">
                          <h3>Antes de generar</h3>
                          <dl className="p-facts">
                            <div>
                              <dt>Productos</dt>
                              <dd>{quote.products}</dd>
                            </div>
                            <div>
                              <dt>Imágenes totales</dt>
                              <dd>{quote.images}</dd>
                            </div>
                            <div>
                              <dt>Proveedor</dt>
                              <dd>{quote.provider}</dd>
                            </div>
                            <div>
                              <dt>Modelo</dt>
                              <dd>{quote.model}</dd>
                            </div>
                            <div>
                              <dt>Costo estimado</dt>
                              <dd>
                                {quote.estimated_usd == null
                                  ? "Sin tarifa configurada"
                                  : `USD $${quote.estimated_usd.toFixed(3)}`}
                              </dd>
                            </div>
                          </dl>
                          <p>{quote.note}</p>
                          <button
                            className="button primary p-full"
                            disabled={busy || !status.worker_ready}
                            onClick={() =>
                              ask({
                                title: "Confirmar generación",
                                text: `${quote.products} productos · ${quote.images} imágenes · ${quote.provider}. Estimación ${quote.estimated_usd == null ? "no disponible" : `USD $${quote.estimated_usd.toFixed(3)}`} más consumo variable. Las imágenes quedarán para revisión.`,
                                label: "Generar lote",
                                action: async () => {
                                  await api(
                                    "/api/platform/generation/jobs",
                                    "POST",
                                    {
                                      ...batch(),
                                      confirm: true,
                                      request_key: crypto.randomUUID(),
                                      estimate_token: quote.estimate_token,
                                    },
                                  );
                                  setQuote(null);
                                  setSelected([]);
                                  setGenerationTab("jobs");
                                  await reloadOperations();
                                  setNotice(
                                    "Lote aceptado. Puedes cerrar el navegador; el worker continuará.",
                                  );
                                },
                              })
                            }
                          >
                            Confirmar y generar
                          </button>
                        </div>
                      )}
                    </section>
                  </div>
                )}
                {generationTab === "review" &&
                  (assets.length ? (
                    <div className="p-asset-grid">
                      {assets.map((a) => (
                        <button
                          className="p-asset-card"
                          key={a.id}
                          onClick={() => attempt(() => reviewAsset(a))}
                        >
                          <img
                            src={pictureUrl(a.image_id)}
                            alt={`${a.product_name} · ${kinds.find((k) => k.id === a.slot)?.label}`}
                            loading="lazy"
                          />
                          <div>
                            <Badge value={a.status} />
                            <h3>{a.product_name}</h3>
                            <p>
                              {a.sku} ·{" "}
                              {kinds.find((k) => k.id === a.slot)?.label}
                            </p>
                            <span className="p-link">
                              Revisar y comparar <ChevronRight size={16} />
                            </span>
                          </div>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <Empty
                      title="Cada imagen pasa por tus manos"
                      text="Genera un lote para revisar, aprobar o pedir correcciones. Ninguna imagen nueva se publica automáticamente."
                    />
                  ))}
                {generationTab === "jobs" && (
                  <section className="p-card">
                    <h2>Trabajos y progreso</h2>
                    {jobs.length ? (
                      jobs.map((j) => (
                        <div className="p-job" key={j.id}>
                          <div className="p-job-head">
                            <span>
                              {j.kind === "generation" ? (
                                <Sparkles size={20} />
                              ) : (
                                <RefreshCw size={20} />
                              )}
                              <strong>
                                {j.payload.product?.name ||
                                  {
                                    publication: "Publicación WooCommerce",
                                    import: "Importación de catálogo",
                                    ecommerce_pull: "Consulta WooCommerce",
                                    enrichment: "Datos con IA",
                                    stock_sync: "Sincronización de stock",
                                    webhook: "Evento recibido",
                                  }[j.kind] ||
                                  j.kind}
                              </strong>
                            </span>
                            <Badge value={j.status} />
                          </div>
                          <p>{j.message}</p>
                          <progress max={100} value={j.progress} />
                          <div className="p-job-foot">
                            <small>
                              {date(j.created_at)} · {j.progress}%
                              {j.estimated_cost
                                ? ` · estimado USD $${j.estimated_cost.toFixed(3)}`
                                : ""}
                            </small>
                            {j.status === "failed" && canEdit && (
                              <button
                                className="p-link"
                                disabled={busy}
                                onClick={() => retry(j)}
                              >
                                Revisar y reintentar
                              </button>
                            )}
                          </div>
                        </div>
                      ))
                    ) : (
                      <Empty
                        title="Sin trabajos pendientes"
                        text="Los lotes se guardan aquí con su estado y progreso."
                      />
                    )}
                  </section>
                )}
              </>
            )}
          </>
        )}

        {section === "more" && (
          <>
            <div className="p-chips p-tabs">
              {[
                ["connections", "Conexiones"],
                ["sync", "Sincronización"],
                ["exchange", "Importar / Exportar"],
                ["settings", "Ajustes"],
                ["help", "Ayuda"],
              ].map(([id, label]) => (
                <button
                  key={id}
                  className={moreTab === id ? "active" : ""}
                  onClick={() => setMoreTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            {moreTab === "connections" && (
              <>
                <div className="p-connection-grid">
                  {(ready
                    ? connections
                    : [
                        {
                          name: "Google Drive",
                          status: session.authenticated
                            ? "connected"
                            : "disconnected",
                        },
                        {
                          name: "IA · Gemini",
                          status: session.gemini_configured
                            ? "connected"
                            : "disconnected",
                        },
                        { name: "WooCommerce", status: "disconnected" },
                        { name: "WordPress", status: "disconnected" },
                        {
                          name: "Loyverse",
                          status: "disconnected",
                          note: "Integración futura",
                        },
                      ]
                  ).map((c) => (
                    <section className="p-card" key={c.name}>
                      <span className="p-stat-icon">
                        <Cloud size={23} />
                      </span>
                      <h2>{c.name}</h2>
                      <Badge value={c.status} />
                      {c.note && <p>{c.note}</p>}
                    </section>
                  ))}
                </div>
                <div className="p-card">
                  <h2>Tu cuenta</h2>
                  <p>
                    {session.email || "Conecta Google Drive para empezar"}
                    {session.authenticated ? ` · ${status.role}` : ""}
                  </p>
                  <button
                    className="button secondary"
                    onClick={() => setMoreTab("settings")}
                  >
                    <Settings2 size={18} />
                    Configurar conexiones
                  </button>
                  <p className="p-muted">
                    Las credenciales de la tienda se configuran en el servidor.
                    El estado de credenciales se confirma al ejecutar una
                    consulta.
                  </p>
                </div>
              </>
            )}
            {moreTab === "settings" && (
              <CaptureStudio embedded initialSection="settings" />
            )}
            {moreTab === "sync" && (
              <section className="p-card">
                <div className="p-card-title">
                  <h2>Sincronización</h2>
                  {isAdmin && ready && (
                    <button
                      className="button secondary"
                      disabled={busy || !status.worker_ready}
                      onClick={() =>
                        ask({
                          title: "Consultar WooCommerce",
                          text: "Leer pedidos recientes y stock por los IDs guardados. No se cambiarán los productos de la tienda.",
                          label: "Consultar",
                          action: () =>
                            operation("/api/platform/ecommerce/refresh"),
                        })
                      }
                    >
                      <RefreshCw size={18} />
                      Consultar tienda
                    </button>
                  )}
                </div>
                {events.length ? (
                  events.map((e) => (
                    <div className="p-log" key={e.id}>
                      <div>
                        <strong>{e.action}</strong>
                        <Badge value={e.status} />
                      </div>
                      <span>
                        {e.source} → {e.destination} · {date(e.created_at)}
                      </span>
                      <p>{e.message}</p>
                      {e.product_id && (
                        <button
                          className="p-link"
                          onClick={() => {
                            go("products");
                            attempt(() => openProduct(e.product_id!));
                          }}
                        >
                          Ver producto
                        </button>
                      )}
                      {e.status === "failed" && e.job_id && isAdmin && (
                        <button
                          className="p-link"
                          onClick={() => {
                            const j = jobs.find((j) => j.id === e.job_id);
                            if (j) retry(j);
                            else {
                              go("generate");
                              setGenerationTab("jobs");
                            }
                          }}
                        >
                          Revisar error
                        </button>
                      )}
                    </div>
                  ))
                ) : (
                  <Empty
                    title="Sin eventos de sincronización"
                    text="Las lecturas, publicaciones y errores de tus integraciones aparecerán aquí."
                  />
                )}
                <button
                  className="p-link"
                  onClick={() => {
                    go("generate");
                    setGenerationTab("jobs");
                  }}
                >
                  Ver todos los trabajos
                </button>
              </section>
            )}
            {moreTab === "exchange" && (
              <div className="p-two-column">
                <section className="p-card">
                  <h2>Importar al catálogo</h2>
                  <p>
                    Revisa una vista previa antes de confirmar. Los SKU
                    existentes se conservan y las fuentes se respaldan.
                  </p>
                  <div className="p-button-column">
                    <button
                      className="button secondary"
                      disabled={!isAdmin || !ready || busy}
                      onClick={() => importRef.current?.click()}
                    >
                      <Upload size={18} />
                      Excel / CSV
                    </button>
                    <button
                      className="button secondary"
                      disabled={!isAdmin || !ready || busy}
                      onClick={() =>
                        attempt(async () =>
                          setPreview(
                            await api<Preview>(
                              "/api/platform/import/sheets",
                              "POST",
                              {},
                            ),
                          ),
                        )
                      }
                    >
                      <Cloud size={18} />
                      Google Sheets existente
                    </button>
                    <button
                      className="button secondary"
                      disabled={
                        !isAdmin || !ready || !status.worker_ready || busy
                      }
                      onClick={() =>
                        ask({
                          title: "Importar WooCommerce",
                          text: "Crear las fichas y familias que todavía no estén en el catálogo maestro. Se respaldará el catálogo antes de importar. Los datos existentes y los productos de la tienda se conservan.",
                          label: "Importar",
                          action: () =>
                            operation("/api/platform/import/woocommerce"),
                        })
                      }
                    >
                      <ShoppingBag size={18} />
                      WooCommerce
                    </button>
                    <button className="button secondary" disabled>
                      Loyverse · Próximamente
                    </button>
                  </div>
                  {preview && (
                    <div className="p-quote">
                      <h3>{preview.rows} productos en la fuente</h3>
                      <p>{preview.note}</p>
                      {preview.sample.map((p) => (
                        <div className="p-preview-row" key={p.sku}>
                          <code>{p.sku}</code>
                          <span>{p.name}</span>
                        </div>
                      ))}
                      {preview.errors.length ? (
                        <div className="p-import-errors">
                          {preview.errors.map((e, i) => (
                            <p key={i}>
                              Fila {e.row} · {e.sku}: {e.message}
                            </p>
                          ))}
                        </div>
                      ) : (
                        <button
                          className="button primary"
                          disabled={
                            busy || !status.worker_ready || !preview.rows
                          }
                          onClick={() =>
                            ask({
                              title: "Confirmar importación",
                              text: `Importar ${preview.rows} filas después de crear copias de respaldo. La fuente se conserva y los SKU existentes se omiten.`,
                              label: "Respaldar e importar",
                              action: async () => {
                                await api(
                                  "/api/platform/import/commit",
                                  "POST",
                                  {
                                    confirm: true,
                                    preview_id: preview.preview_id,
                                    request_key: crypto.randomUUID(),
                                  },
                                );
                                setPreview(null);
                                await reloadOperations();
                                setNotice("Importación respaldada y en cola.");
                              },
                            })
                          }
                        >
                          Confirmar importación
                        </button>
                      )}
                    </div>
                  )}
                </section>
                <section className="p-card">
                  <h2>Exportar y respaldar</h2>
                  <p>
                    Descarga el catálogo operativo para compartirlo o usarlo
                    como respaldo. Sheets y Excel funcionan como intercambio.
                  </p>
                  <div className="p-button-column">
                    <a
                      className={
                        "button secondary " + (!ready ? "p-disabled" : "")
                      }
                      href="/api/platform/export?format=xlsx"
                    >
                      <Download size={18} />
                      Descargar Excel
                    </a>
                    <a
                      className={
                        "button secondary " + (!ready ? "p-disabled" : "")
                      }
                      href="/api/platform/export?format=csv"
                    >
                      <Download size={18} />
                      Descargar CSV
                    </a>
                    <a
                      className="button secondary"
                      href="https://docs.google.com/spreadsheets/d/1dUG_xuuIUwGLTMfXl56dGRyJSFc18VlD2EkD5aWjym8/edit"
                      target="_blank"
                      rel="noreferrer"
                    >
                      <Cloud size={18} />
                      Respaldo previo de la hoja <ExternalLink size={15} />
                    </a>
                  </div>
                  <p className="p-muted">
                    Los archivos originales de Drive conservan su ubicación. Las
                    nuevas imágenes y copias se crean dentro de
                    Rincon_de_Asia_App.
                  </p>
                </section>
              </div>
            )}
            {moreTab === "help" && (
              <section className="p-card">
                <h2>Un flujo claro, de principio a fin</h2>
                <ol className="p-guide">
                  <li>
                    <strong>Prepara el producto</strong>
                    <p>
                      Importa o crea la ficha en Productos. Añade una foto
                      original como referencia para la IA.
                    </p>
                  </li>
                  <li>
                    <strong>Genera las imágenes</strong>
                    <p>
                      Elige productos, tipo y cantidad. Revisa el proveedor, el
                      modelo y la estimación antes de confirmar el lote.
                    </p>
                  </li>
                  <li>
                    <strong>Revisa y aprueba</strong>
                    <p>
                      Compara cada imagen con el original. Puedes rechazarla o
                      regenerar con una corrección. Aprobar conserva tu elección
                      para publicar después.
                    </p>
                  </li>
                  <li>
                    <strong>Publica y sincroniza</strong>
                    <p>
                      Un administrador publica las imágenes aprobadas en
                      WordPress y WooCommerce. El inventario registra cada
                      movimiento por separado.
                    </p>
                  </li>
                </ol>
                <p>
                  Loyverse está preparado como integración futura; su activación
                  requiere validar credenciales, firma y autoridad de stock.
                </p>
                <p>
                  Si un trabajo queda incierto, comprueba sus archivos y la
                  tienda antes de autorizar otro intento.
                </p>
              </section>
            )}
            {session.authenticated && (
              <button
                className="button secondary p-logout"
                disabled={busy}
                onClick={() =>
                  attempt(async () => {
                    await fetch("/logout", {
                      method: "POST",
                      credentials: "same-origin",
                    });
                    setSession({ authenticated: false });
                    setDetail(null);
                    setProducts([]);
                    setAssets([]);
                    setJobs([]);
                    setDashboard(undefined);
                    setConnections([]);
                    setEvents([]);
                    go("home");
                  })
                }
              >
                <LogOut size={17} />
                Cerrar sesión
              </button>
            )}
          </>
        )}
        {(section === "products" || section === "inventory") &&
          !ready &&
          !loading && (
            session.authenticated ? <><div className="p-alert"><Cloud size={18}/><span>Catálogo histórico de Drive · disponible durante la activación de PostgreSQL.</span></div><CaptureStudio embedded initialSection="catalog"/></> : <Empty title="Conecta tu catálogo" text="En Más puedes conectar tu cuenta de Google Drive."/>
          )}
        <footer className="p-footer">
          <img src="/logo.png" width={23} height={23} alt="" />
          <span>El Rincón de Asia · De Asia para tu casa.</span>
          <small>{online ? "En línea" : "Sin conexión"}</small>
        </footer>
        {busy && (
          <div className="p-busy" role="status">
            <Loader2 className="spin" size={18} />
            Guardando tu operación…
          </div>
        )}
      </main>
      <input
        hidden
        ref={scanRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) attempt(() => scan(f));
          e.target.value = "";
        }}
      />
      <input
        hidden
        ref={referenceRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) attempt(() => uploadReference(f));
          e.target.value = "";
        }}
      />
      <input
        hidden
        ref={importRef}
        type="file"
        accept=".csv,.xlsx"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f)
            attempt(async () => {
              const data = new FormData();
              data.append("source", f);
              setPreview(
                await api<Preview>("/api/platform/import/file", "POST", data),
              );
            });
          e.target.value = "";
        }}
      />
      {selectedAsset && (
        <div className="p-modal-backdrop">
          <div
            className="p-dialog p-review-dialog"
            ref={modalRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="review-title"
            tabIndex={-1}
          >
            <div className="p-card-title">
              <div>
                <h2 id="review-title">Revisar imagen</h2>
                <p>
                  {selectedAsset.product_name} · {selectedAsset.sku}
                </p>
              </div>
              <button
                aria-label="Cerrar revisión"
                disabled={busy}
                onClick={() => setSelectedAsset(null)}
              >
                <X size={22} />
              </button>
            </div>
            <div className="p-comparison">
              <figure>
                <figcaption>Original de referencia</figcaption>
                {comparison?.images.find((i) => i.role === "reference") ? (
                  <img
                    src={pictureUrl(
                      comparison.images.find((i) => i.role === "reference")!.id,
                    )}
                    alt="Producto original"
                  />
                ) : (
                  <p>Sin referencia disponible</p>
                )}
              </figure>
              <figure>
                <figcaption>
                  {kinds.find((k) => k.id === selectedAsset.slot)?.label}{" "}
                  <Badge value={selectedAsset.status} />
                </figcaption>
                <img
                  src={pictureUrl(selectedAsset.image_id)}
                  alt="Resultado generado"
                />
              </figure>
            </div>
            <div className="p-button-row">
              <a
                className="button secondary"
                href={pictureUrl(selectedAsset.image_id) + "?download=true"}
              >
                <Download size={16} />
                Descargar
              </a>
              <button
                className="button secondary"
                onClick={() => {
                  setSelectedAsset(null);
                  go("products");
                  attempt(() => openProduct(selectedAsset.product_id));
                }}
              >
                Ver producto
              </button>
            </div>
            {selectedAsset.metadata_json.qa?.resumen && (
              <p className="p-muted">
                Revisión de IA: {selectedAsset.metadata_json.qa.resumen}
              </p>
            )}
            {selectedAsset.metadata_json.brief && (
              <details className="p-brief">
                <summary>Escenas y referencias de la investigación</summary>
                <p>{selectedAsset.metadata_json.brief.note}</p>
                <p>
                  {selectedAsset.slot === "2_uso"
                    ? selectedAsset.metadata_json.brief.lifestyle
                    : selectedAsset.metadata_json.brief.comercial}
                </p>
                {selectedAsset.metadata_json.brief.sources?.map((s) => (
                  <a key={s.url} href={s.url} rel="noreferrer" target="_blank">
                    {s.title || s.url}
                    <ExternalLink size={14} />
                  </a>
                ))}
                {selectedAsset.metadata_json.brief.search_suggestions && (
                  <iframe
                    title="Sugerencias de Google Search"
                    sandbox="allow-popups allow-popups-to-escape-sandbox"
                    srcDoc={
                      selectedAsset.metadata_json.brief.search_suggestions
                    }
                  />
                )}
              </details>
            )}
            {canEdit && selectedAsset.status !== "published" && (
              <>
                <label className="p-form-field">
                  Usar como
                  <select
                    value={imageRole}
                    onChange={(e) => setImageRole(e.target.value)}
                  >
                    <option value="main">Principal</option>
                    <option value="gallery">Galería</option>
                    <option value="lifestyle">Lifestyle</option>
                    <option value="commercial">Comercial</option>
                  </select>
                </label>
                <div className="p-button-row">
                  <button
                    className="button primary"
                    disabled={busy}
                    onClick={() => attempt(() => approve("approved"))}
                  >
                    <Check size={18} />
                    Aprobar
                  </button>
                  <button
                    className="button secondary"
                    disabled={busy}
                    onClick={() => attempt(() => approve("rejected"))}
                  >
                    Rechazar
                  </button>
                </div>
              </>
            )}
            {canEdit && (
              <div className="p-correction">
                <label className="p-form-field">
                  Corrección para regenerar
                  <textarea
                    rows={3}
                    maxLength={600}
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    placeholder="Describe qué debe cambiar y qué debe conservar…"
                  />
                </label>
                <p className="p-muted">
                  Se usarán la imagen anterior y las referencias originales.
                  Generar una corrección añade consumo de IA.
                </p>
                {selectedAsset.history.length > 0 && (
                  <p>
                    Correcciones anteriores: {selectedAsset.history.join(" · ")}
                  </p>
                )}
                <button
                  className="button secondary"
                  disabled={busy || !status.worker_ready || !feedback.trim()}
                  onClick={() => {
                    const asset = selectedAsset;
                    const correction = feedback;
                    setSelectedAsset(null);
                    ask({
                      title: "Regenerar con corrección",
                      text: `Se creará una nueva imagen conservando la anterior. Estimación de salida: ${asset.estimated_correction_usd == null ? "tarifa no configurada" : `USD $${asset.estimated_correction_usd.toFixed(3)}`}, más entradas y revisión si aplica. Confirma el consumo adicional.`,
                      label: "Regenerar",
                      action: async () => {
                        await api(
                          `/api/platform/assets/${asset.id}/correct`,
                          "POST",
                          {
                            feedback: correction,
                            confirm_cost: true,
                            request_key: crypto.randomUUID(),
                          },
                        );
                        await reloadOperations();
                        setGenerationTab("jobs");
                        setNotice(
                          "Corrección en cola. La imagen anterior se conserva.",
                        );
                      },
                    });
                  }}
                >
                  <RefreshCw size={18} />
                  Regenerar con corrección
                </button>
              </div>
            )}
          </div>
        </div>
      )}
      {confirm && (
        <div className="p-modal-backdrop">
          <div
            className="p-dialog"
            ref={modalRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            tabIndex={-1}
          >
            <span className="p-stat-icon">
              <CircleAlert size={24} />
            </span>
            <h2 id="confirm-title">{confirm.title}</h2>
            <p>{confirm.text}</p>
            {confirm.uncertain && (
              <label className="p-choice">
                <input
                  type="checkbox"
                  checked={uncertainChecked}
                  onChange={(e) => setUncertainChecked(e.target.checked)}
                />
                <span>
                  Revisé los archivos y la tienda; autorizar otro intento es
                  necesario.
                </span>
              </label>
            )}
            <div className="p-button-row">
              <button
                className="button primary"
                disabled={
                  busy || !online || (!!confirm.uncertain && !uncertainChecked)
                }
                onClick={() =>
                  attempt(async () => {
                    await confirm.action();
                    setConfirm(null);
                  })
                }
              >
                {busy ? (
                  <Loader2 className="spin" size={18} />
                ) : (
                  <Check size={18} />
                )}{" "}
                {confirm.label}
              </button>
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => setConfirm(null)}
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
