"use client";

import {
  Archive, Bell, BookOpen, Boxes, ChevronRight, CircleDollarSign, ClipboardList, CreditCard,
  HelpCircle, LayoutDashboard, Menu, Minus, PackagePlus, Plus, Search, ShoppingBag, Sparkles, Users, Wrench, X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import QRCode from "qrcode";

type Product = { id: number; name: string; brand: string; type: string; price: number; stock: number; min: number };
type Customer = { id: number; name: string; phone: string; debt: number; visits: number };
type Order = { id: number; customer: string; item: string; total: number; paid: number; status: "Yangi" | "Ishda" | "Tayyor" | "Topshirildi" | "Bekor qilindi"; date: string; createdAt?: string };
type CartLine = Product & { qty: number };
type SessionUser = { id?: number; username: string; role: string; branch?: { id: number; name: string } | null };
type Supplier = { id: number; name: string; phone: string | null; balance: number };
type CashShift = { id: number; opening_amount: number; expected_amount: number | null; actual_amount: number | null; difference: number | null; status: string; opened_at: string };
type SaleRecord = { id: number; customer: Customer | null; total: number; paid: number; created_at?: string; items: { product: Product; quantity: number; unit_price: number }[] };
type FinanceReport = { sales_revenue:number; sales_paid:number; order_value:number; order_paid:number; expenses:number; cash_in:number; cash_out:number; net_cash_flow:number; purchase_value:number; supplier_debt:number; customer_debt:number };
type SearchResult = { type: string; id: number; title: string; subtitle: string };
type Repair = { id:number; customer:Customer; device:string; issue:string; estimated_cost:number; paid:number; balance:number; status:string; technician_note:string | null; due_date:string | null };
type TeamUser = { id:number; username:string; role:string; active:boolean };
type SystemNotification = { type:string; severity:string; title:string; message:string; entity_id:number };
type OpticalAdvice = { customer:Customer; has_prescription:boolean; recommendations:string[]; warning:string };
type BranchInfo = { id:number; name:string; code:string; address:string | null; active:boolean; members:number };
type OpticalCase = { id:number; customer:Customer; frame:Product | null; chief_complaint:string | null; status:string; exam:{od_sph:string|null;od_cyl:string|null;od_axis:number|null;os_sph:string|null;os_cyl:string|null;os_axis:number|null;add_power:string|null;prism:string|null;distance_va:string|null;near_va:string|null;clinical_note:string|null;referral_required:boolean}|null; centration:{pd_right:number;pd_left:number;fitting_height_right:number;fitting_height_left:number;vertex_distance:number|null;pantoscopic_tilt:number|null;wrap_angle:number|null}|null; lens:{lens_design:string;material_index:string;coating:string|null;photochromic:boolean;lab_note:string|null}|null; lab:{status:string;laboratory:string|null;job_reference:string|null;qc_note:string|null}|null };
type BeforeInstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }> };
type Notice = { text: string; tone: "success" | "error" | "info" };
type ApiResult<T> = { ok: true; data: T } | { ok: false; error: string; status: number };

const sections = [
  ["Bosh sahifa", LayoutDashboard], ["Sotuv", ShoppingBag], ["Sotuvlar", CreditCard], ["Buyurtmalar", ClipboardList], ["Optik buyurtma", ClipboardList], ["Servis", Wrench], ["Mijozlar", Users], ["Aqlli yordamchi", Sparkles], ["Ombor", Boxes], ["Kassa", CircleDollarSign], ["Supplierlar", Archive], ["Filiallar", Archive], ["Xodimlar", Users], ["Hisobotlar", LayoutDashboard], ["Qo'llanma", BookOpen],
] as const;

// Rol bo'yicha ko'rinadigan bo'limlar. OWNER va MANAGER hammasini ko'radi.
const ROLE_SECTIONS: Record<string, string[]> = {
  SELLER: ["Bosh sahifa", "Sotuv", "Sotuvlar", "Buyurtmalar", "Optik buyurtma", "Servis", "Mijozlar", "Aqlli yordamchi", "Ombor", "Kassa", "Supplierlar", "Qo'llanma"],
  OPTOMETRIST: ["Bosh sahifa", "Optik buyurtma", "Mijozlar", "Aqlli yordamchi", "Buyurtmalar", "Qo'llanma"],
  LAB_QC: ["Bosh sahifa", "Optik buyurtma", "Buyurtmalar", "Qo'llanma"],
};

// Har bir bo'lim uchun oddiy tildagi izoh: nima uchun va qanday ishlatiladi.
const HELP: Record<string, { what: string; steps: string[] }> = {
  "Bosh sahifa": { what: "Do'koningizning bugungi umumiy holati: tushum, faol buyurtmalar, mijozlar va qarzdorlik bir ekranda.", steps: ["Yuqoridagi kartalardan bugungi asosiy raqamlarni ko'ring", "'E'tibor kerak' bo'limi kam qolgan mahsulot va tayyor buyurtmalarni ogohlantiradi", "Tezkor +Mijoz yoki +Buyurtma tugmalari bilan darrov ish boshlang"] },
  "Sotuv": { what: "Kassada tez sotuv qilish uchun. Mahsulotni savatchaga qo'shib, to'lovni yakunlaysiz.", steps: ["Chapdan mahsulotni bosing — savatchaga qo'shiladi", "Miqdorni + va - bilan o'zgartiring", "'To'lovni yakunlash' tugmasini bosing — sotuv saqlanadi va ombordan ayiriladi"] },
  "Sotuvlar": { what: "Yakunlangan barcha sotuvlar tarixi. Kerak bo'lsa mahsulotni qaytarasiz.", steps: ["Sotuvni toping", "Mahsulot yonidagi 'Qaytarish' tugmasini bosing", "Sabab va holatni tanlab tasdiqlang"] },
  "Buyurtmalar": { what: "Mijoz buyurtmalarini boshqarish: Yangi, Ishda, Tayyor, Topshirildi.", steps: ["'+ Yangi buyurtma' bilan buyurtma yarating (ro'yxatdan yoki qo'lda)", "'Keyingi' tugmasi bilan holatni bosqichma-bosqich o'tkazing", "Tayyor bo'lganda mijozga Telegram orqali avtomatik xabar ketadi"] },
  "Optik buyurtma": { what: "Professional optika jarayoni: ramka tanlashdan tayyor ko'zoynakkacha bosqichma-bosqich.", steps: ["'+ Yangi optik karta' — mijoz va ramkani tanlang", "Ko'z tekshiruvi, Centration o'lchovi, Linza tanlovi, Laboratoriyaga yuborish", "Har bosqichda tugma o'zi keyingi kerakli qadamni ko'rsatadi"] },
  "Servis": { what: "Ko'zoynak yoki ramka ta'mirlash buyurtmalarini qabul qilish va kuzatish.", steps: ["'+ Servis qabul qilish' — mijoz, buyum va nosozlikni yozing", "Narx va avansni kiriting", "'Keyingi' bilan holatni Tayyorgacha o'tkazing"] },
  "Mijozlar": { what: "Mijozlar bazasi. Retsept, qarzdorlik va Telegram havolasini shu yerdan boshqarasiz.", steps: ["'+ Yangi mijoz' bilan mijoz qo'shing", "Mijozni bosib retsept (ko'rish o'lchovlari) kiriting", "Qarzi bo'lsa 'Qarz to'lovi' bilan to'lovni qabul qiling"] },
  "Aqlli yordamchi": { what: "Mijozning retseptiga qarab qoidaga asoslangan optik tavsiyalar beradi (shifokorni almashtirmaydi).", steps: ["Mijozni tanlang", "'Tavsiya olish' tugmasini bosing", "Chiqqan tavsiyalarni mijozga tushuntiring"] },
  "Ombor": { what: "Mahsulot qoldiqlari. Sotuv va buyurtma qoldiqni avtomatik kamaytiradi.", steps: ["'+ Mahsulot' bilan yangi tovar qo'shing", "'Kirim qilish' bilan qoldiqni oshiring", "Qizil 'kam qoldi' belgisi minimumdan past mahsulotni ko'rsatadi"] },
  "Kassa": { what: "Kunlik kassa smenasi: ochish, yopish va xarajatlar.", steps: ["'Smenani ochish' — boshlang'ich summani kiriting", "Kun davomida '+ Xarajat' bilan chiqimlarni yozing", "Kun oxirida 'Smenani yopish' bilan hisobni yakunlang"] },
  "Supplierlar": { what: "Yetkazib beruvchilar, ulardan kirim va ularga qarzdorlik.", steps: ["'+ Yangi supplier' qo'shing", "'+ Kirim' bilan supplierdan mahsulot qabul qiling", "Qarz bo'lsa 'To'lash' bilan to'lovni yozing"] },
  "Filiallar": { what: "Bir nechta do'kon filialini va ulardagi xodimlarni boshqarish.", steps: ["'+ Filial qo'shish' — nom, kod va manzilni kiriting", "Filiallarni ro'yxatda ko'ring"] },
  "Xodimlar": { what: "Tizim foydalanuvchilari va ularning rollari (Owner, Manager, Sotuvchi va boshqalar).", steps: ["'+ Xodim qo'shish' — login, parol va rol tanlang", "Har rol faqat o'ziga kerakli bo'limlarni ko'radi"] },
  "Hisobotlar": { what: "Moliyaviy holat: sotuv, xarajat, sof foyda va qarzdorlik ko'rsatkichlari.", steps: ["Yuqoridagi kartalardan asosiy raqamlarni ko'ring", "'Operatsion jamlanma'da batafsil kirim va chiqimni ko'ring"] },
};

// Ilk kirishda ko'rsatiladigan bosqichma-bosqich yo'l-yo'riq.
const TOUR: { section: string | null; title: string; text: string }[] = [
  { section: "Bosh sahifa", title: "Optika OS'ga xush kelibsiz!", text: "Bu — do'koningizni boshqaradigan tizim. Sizga har bir asosiy qismni qisqacha ko'rsatamiz. Bu 6 qadam, 1 daqiqa vaqt oladi." },
  { section: "Sotuv", title: "1. Sotuv (Kassa)", text: "Mijoz kelganda shu yerda tez sotuv qilasiz: mahsulotni bosib savatchaga qo'shasiz va to'lovni yakunlaysiz. Ombor qoldig'i o'zi kamayadi." },
  { section: "Buyurtmalar", title: "2. Buyurtmalar", text: "Ko'zoynak buyurtmalarini shu yerda kuzatasiz: Yangi → Ishda → Tayyor → Topshirildi. Tayyor bo'lganda mijozga Telegram orqali xabar boradi." },
  { section: "Mijozlar", title: "3. Mijozlar", text: "Mijoz qo'shasiz, retsept (ko'z o'lchovlari) kiritasiz va qarzdorlikni boshqarasiz. Mijozni bosib kartasini ochasiz." },
  { section: "Ombor", title: "4. Ombor", text: "Mahsulot qoldiqlari shu yerda. Kam qolgan tovar qizil bilan belgilanadi va sizni ogohlantiradi." },
  { section: null, title: "5. Yordam har doim yoningizda", text: "Har bir bo'lim tepasidagi '?' tugmasini bossangiz, o'sha bo'lim nima uchun va qanday ishlashini o'zbek tilida tushuntiradi. To'liq qo'llanma esa chapdagi 'Qo'llanma' bo'limida." },
];
const format = (value: number) => `${new Intl.NumberFormat("uz-UZ").format(value)} som`;
const parseApiDate = (iso?: string | null) => { if (!iso) return null; return new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`); };
const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

function useSavedState<T>(key: string, initial: T) {
  const [state, setState] = useState<T>(initial);
  const [ready, setReady] = useState(false);
  useEffect(() => { const raw = localStorage.getItem(key); if (raw) setState(JSON.parse(raw)); setReady(true); }, [key]);
  useEffect(() => { if (ready) localStorage.setItem(key, JSON.stringify(state)); }, [key, ready, state]);
  return [state, setState] as const;
}

export default function OptikaOS() {
  const [section, setSection] = useState("Bosh sahifa");
  const [products, setProducts] = useSavedState<Product[]>("optika-products", []);
  const [customers, setCustomers] = useSavedState<Customer[]>("optika-customers", []);
  const [orders, setOrders] = useSavedState<Order[]>("optika-orders", []);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [sales, setSales] = useState<SaleRecord[]>([]);
  const [repairs, setRepairs] = useState<Repair[]>([]);
  const [team, setTeam] = useState<TeamUser[]>([]);
  const [branches, setBranches] = useState<BranchInfo[]>([]);
  const [opticalCases, setOpticalCases] = useState<OpticalCase[]>([]);
  const [systemNotifications, setSystemNotifications] = useState<SystemNotification[]>([]);
  const [opticalAdvice, setOpticalAdvice] = useState<OpticalAdvice | null>(null);
  const [telegramLink, setTelegramLink] = useState<{ customer: string; url: string; qr: string } | null>(null);
  const [finance, setFinance] = useState<FinanceReport | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [cart, setCart] = useState<CartLine[]>([]);
  const [query, setQuery] = useState("");
  const [manualOrder, setManualOrder] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [tourStep, setTourStep] = useState(-1);
  const [modal, setModal] = useState<"customer" | "order" | "stock" | "product" | "prescription" | "supplier" | "cash-open" | "cash-close" | "return" | "expense" | "customer-payment" | "supplier-payment" | "purchase" | "repair" | "user" | "branch" | "optical-case" | "eye-exam" | "centration" | "lens-config" | "lab-job" | "lab-qc" | null>(null);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [selectedSupplier, setSelectedSupplier] = useState<Supplier | null>(null);
  const [cashShift, setCashShift] = useState<CashShift | null>(null);
  const [selectedReturn, setSelectedReturn] = useState<{ saleId: number; product: Product } | null>(null);
  const [selectedOpticalCase, setSelectedOpticalCase] = useState<OpticalCase | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);
  const [backendOnline, setBackendOnline] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<SessionUser | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const [isOnline, setIsOnline] = useState(true);
  const [installPrompt, setInstallPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isStandalone, setIsStandalone] = useState(false);
  const [installHint, setInstallHint] = useState("");

  useEffect(() => {
    setToken(localStorage.getItem("optika-token"));
    const savedUser = localStorage.getItem("optika-user");
    if (savedUser) setUser(JSON.parse(savedUser));
    setSessionReady(true);
  }, []);

  const say = (text: string, tone: Notice["tone"] = "success") => setNotice({ text, tone });
  useEffect(() => {
    if (!notice) return;
    const id = window.setTimeout(() => setNotice(null), notice.tone === "error" ? 6000 : 4000);
    return () => window.clearTimeout(id);
  }, [notice]);
  const canSee = (label: string) => !user || !ROLE_SECTIONS[user.role] || ROLE_SECTIONS[user.role].includes(label);
  const goSection = (label: string) => { if (canSee(label)) { setSection(label); setMenu(false); } else say("Bu bo'lim sizning rolingiz uchun ochiq emas", "info"); };

  function clearSession() {
    ["optika-token", "optika-user", "optika-products", "optika-customers", "optika-orders"].forEach(key => localStorage.removeItem(key));
    setToken(null); setUser(null); setCart([]); setNotice(null); setSection("Bosh sahifa"); setQuery(""); setSearchResults([]);
    setProducts([]); setCustomers([]); setOrders([]); setSales([]); setRepairs([]); setSuppliers([]); setTeam([]); setBranches([]); setOpticalCases([]); setSystemNotifications([]); setCashShift(null); setFinance(null);
  }

  const api = useCallback(async function apiCall<T = unknown>(path: string, init?: { method?: string; body?: unknown; skip401?: boolean }): Promise<ApiResult<T>> {
    try {
      const response = await fetch(`${apiUrl}${path}`, { method: init?.method || "GET", headers: { ...(init?.body !== undefined ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: init?.body !== undefined ? JSON.stringify(init.body) : undefined });
      if (response.status === 401 && !init?.skip401) { clearSession(); setNotice({ text: "Sessiya muddati tugadi. Iltimos, qaytadan kiring.", tone: "error" }); return { ok: false, error: "Sessiya tugadi", status: 401 }; }
      let payload: { data?: T; detail?: unknown } | null = null;
      try { payload = await response.json(); } catch { /* nginx 502 kabi JSON bo'lmagan javob */ }
      if (!response.ok) { const rawDetail = payload?.detail; const detail = typeof rawDetail === "string" ? rawDetail : rawDetail ? "Kiritilgan ma'lumotlar formati noto'g'ri" : undefined; return { ok: false, error: detail || `Server xatosi (${response.status})`, status: response.status }; }
      return { ok: true, data: (payload?.data ?? payload) as T };
    } catch { return { ok: false, error: "Internet yoki server bilan aloqa yo'q. Qayta urinib ko'ring.", status: 0 }; }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!token) return;
    void (async () => { const res = await api<SessionUser>("/auth/me"); if (res.ok && res.data?.username && localStorage.getItem("optika-token")) { setUser(res.data); localStorage.setItem("optika-user", JSON.stringify(res.data)); } })();
  }, [token, api]);

  useEffect(() => {
    if ("serviceWorker" in navigator) void navigator.serviceWorker.register("/sw.js");
  }, []);

  useEffect(() => {
    if (user && !localStorage.getItem("optika-tour-v1")) setTourStep(0);
  }, [user]);

  useEffect(() => {
    if (tourStep >= 0 && tourStep < TOUR.length) { const s = TOUR[tourStep].section; if (s && (!user || !ROLE_SECTIONS[user.role] || ROLE_SECTIONS[user.role].includes(s))) setSection(s); }
  }, [tourStep]);

  const finishTour = () => { localStorage.setItem("optika-tour-v1", "1"); setTourStep(-1); setSection("Bosh sahifa"); };

  useEffect(() => {
    const sync = () => setIsOnline(navigator.onLine);
    sync(); window.addEventListener("online", sync); window.addEventListener("offline", sync);
    return () => { window.removeEventListener("online", sync); window.removeEventListener("offline", sync); };
  }, []);

  useEffect(() => {
    const onInstallPrompt = (event: Event) => { event.preventDefault(); setInstallPrompt(event as BeforeInstallPromptEvent); };
    const standalone = window.matchMedia("(display-mode: standalone)").matches || Boolean((navigator as Navigator & { standalone?: boolean }).standalone);
    setIsStandalone(standalone);
    window.addEventListener("beforeinstallprompt", onInstallPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onInstallPrompt);
  }, []);

  const loadFromApi = useCallback(async () => {
    if (!token) return;
    const bootstrap = await api<{ customers: {id:number;name:string;phone:string;debt:number}[]; products: {id:number;name:string;brand:string;category:string;sale_price:number;stock:number;minimum_stock:number}[]; orders: {id:number;customer:{name:string};product:{name:string}|null;item_name:string|null;total:number;paid:number;status:string;created_at:string}[]; suppliers: Supplier[]; cash_shift: CashShift | null }>("/bootstrap");
    if (!bootstrap.ok) { if (bootstrap.status === 0) setBackendOnline(false); return; }
    if (!localStorage.getItem("optika-token")) return;
    const data = bootstrap.data;
    setCustomers(data.customers.map(customer => ({ ...customer, visits: 0 })));
    setProducts(data.products.map(product => ({ id: product.id, name: product.name, brand: product.brand, type: product.category, price: product.sale_price, stock: product.stock, min: product.minimum_stock })));
    setSuppliers(data.suppliers || []);
    setCashShift(data.cash_shift || null);
    const mapStatus: Record<string, Order["status"]> = { CONFIRMED: "Yangi", IN_PROGRESS: "Ishda", READY: "Tayyor", DELIVERED: "Topshirildi", CANCELLED: "Bekor qilindi" };
    setOrders(data.orders.map(order => ({ id: order.id, customer: order.customer.name, item: order.item_name || order.product?.name || "Mahsulot", total: order.total, paid: order.paid, status: mapStatus[order.status] || "Yangi", date: (parseApiDate(order.created_at) as Date).toLocaleDateString("uz-UZ"), createdAt: order.created_at })));
    setBackendOnline(true);
    const [salesRes, financeRes, repairsRes, usersRes, branchesRes, casesRes, notifsRes] = await Promise.all([
      api<{id:number;customer:{id:number;name:string;phone:string;debt:number}|null;total:number;paid:number;created_at:string;items:{product:{id:number;name:string;brand:string;category:string;sale_price:number;stock:number;minimum_stock:number};quantity:number;unit_price:number}[]}[]>("/sales"),
      api<FinanceReport>("/reports/finance"),
      api<(Omit<Repair, "customer"> & { customer: {id:number;name:string;phone:string;debt:number} })[]>("/repairs"),
      api<TeamUser[]>("/users"),
      api<BranchInfo[]>("/branches"),
      api<OpticalCase[]>("/optical-cases"),
      api<SystemNotification[]>("/notifications"),
    ]);
    if (salesRes.ok) setSales(salesRes.data.map(sale => ({ id: sale.id, customer: sale.customer ? { ...sale.customer, visits: 0 } : null, total: sale.total, paid: sale.paid, created_at: sale.created_at, items: sale.items.map(item => ({ product: { id: item.product.id, name: item.product.name, brand: item.product.brand, type: item.product.category, price: item.product.sale_price, stock: item.product.stock, min: item.product.minimum_stock }, quantity: item.quantity, unit_price: item.unit_price })) })));
    if (financeRes.ok) setFinance(financeRes.data);
    if (repairsRes.ok) setRepairs(repairsRes.data.map(repair => ({ ...repair, customer: { ...repair.customer, visits: 0 } })));
    if (usersRes.ok) setTeam(usersRes.data);
    if (branchesRes.ok) setBranches(branchesRes.data);
    if (casesRes.ok) setOpticalCases(casesRes.data);
    if (notifsRes.ok) setSystemNotifications(notifsRes.data);
  }, [api, setCustomers, setOrders, setProducts, token]);
  useEffect(() => { if (token) void loadFromApi(); else setBackendOnline(false); }, [loadFromApi, token]);
  useEffect(() => {
    if (!token) return;
    const id = setInterval(() => { if (!document.hidden) void loadFromApi(); }, 30000);
    const onFocus = () => { void loadFromApi(); };
    window.addEventListener("focus", onFocus);
    return () => { clearInterval(id); window.removeEventListener("focus", onFocus); };
  }, [loadFromApi, token]);
  useEffect(() => {
    if (!token || query.trim().length < 2) { setSearchResults([]); return; }
    const timer = window.setTimeout(async () => {
      const res = await api<SearchResult[]>(`/search?q=${encodeURIComponent(query)}`);
      if (res.ok) setSearchResults(res.data);
    }, 220);
    return () => window.clearTimeout(timer);
  }, [api, query, token]);
  useEffect(() => {
    const onDown = (event: PointerEvent) => { const wrap = document.querySelector(".search-wrap"); if (wrap && !wrap.contains(event.target as Node)) setSearchResults([]); };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, []);

  const isToday = (iso?: string) => { const d = parseApiDate(iso); if (!d) return false; const n = new Date(); return d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate(); };
  const todayRevenue = useMemo(() => sales.filter(sale => isToday(sale.created_at)).reduce((sum, sale) => sum + sale.paid, 0) + orders.filter(order => isToday(order.createdAt)).reduce((sum, order) => sum + order.paid, 0), [sales, orders]);
  const debt = useMemo(() => customers.reduce((sum, customer) => sum + customer.debt, 0), [customers]);
  const lowStock = products.filter(product => product.stock <= product.min);
  const cartTotal = cart.reduce((sum, line) => sum + line.price * line.qty, 0);
  const addToCart = (product: Product) => setCart(current => {
    const existing = current.find(line => line.id === product.id);
    if (existing) return current.map(line => line.id === product.id ? { ...line, qty: Math.min(line.qty + 1, product.stock) } : line);
    return product.stock ? [...current, { ...product, qty: 1 }] : current;
  });
  const updateQty = (id: number, change: number) => setCart(current => current.flatMap(line => {
    const qty = line.qty + change;
    return qty > 0 ? [{ ...line, qty: Math.min(qty, line.stock) }] : [];
  }));
  const statusTone = (status: Order["status"]) => ({ "Yangi": "neutral", "Ishda": "working", "Tayyor": "ready", "Topshirildi": "done", "Bekor qilindi": "cancelled" })[status];
  const nextStatus = (status: Order["status"]): Order["status"] => {
    if (status === "Yangi") return "Ishda";
    if (status === "Ishda") return "Tayyor";
    return "Topshirildi";
  };
  async function checkout() {
    if (!cart.length) return say("Avval savatchaga mahsulot qo'shing", "info");
    if (busy) return; setBusy(true);
    const res = await api("/sales", { method: "POST", body: { paid: cartTotal, payment_method: "CASH", items: cart.map(line => ({ product_id: line.id, quantity: line.qty })) } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setCart([]); await loadFromApi(); say(`${format(cartTotal)} sotuv bazaga saqlandi`);
  }
  async function addCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    const name = String(data.get("name") || "").trim(); const phone = String(data.get("phone") || "").trim();
    if (!name || !phone) return say("Ism va telefonni kiriting", "info");
    const branchId = String(data.get("branch_id") || "");
    if (busy) return; setBusy(true);
    const res = await api("/customers", { method: "POST", body: { name, phone, ...(branchId ? { branch_id: Number(branchId) } : {}) } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say(`${name} mijoz sifatida bazaga qo'shildi`);
  }
  async function addOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    const selected = customers.find(item => item.id === Number(data.get("customer")));
    if (!selected) return say("Mijozni tanlang", "info");
    const paid = Number(data.get("paid") || 0);
    let body: Record<string, unknown>;
    if (manualOrder) {
      const itemName = String(data.get("item_name") || "").trim();
      if (!itemName) return say("Mahsulot nomini kiriting", "info");
      body = { customer_id: selected.id, item_name: itemName, total: Number(data.get("total") || 0), paid };
    } else {
      const product = products.find(item => item.id === Number(data.get("product")));
      if (!product) return say("Ro'yxatdan mahsulot tanlang yoki qo'lda kiriting", "info");
      body = { customer_id: selected.id, product_id: product.id, paid };
    }
    if (busy) return; setBusy(true);
    const res = await api("/orders", { method: "POST", body });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); setManualOrder(false); await loadFromApi(); say(manualOrder ? "Qo'lda buyurtma bazaga yaratildi" : "Buyurtma bazaga yaratildi va mahsulot rezerv qilindi");
  }
  async function addRepair(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (busy) return; setBusy(true);
    const res = await api("/repairs", { method: "POST", body: { customer_id: Number(data.get("customer")), device: data.get("device"), issue: data.get("issue"), estimated_cost: Number(data.get("estimated_cost")), paid: Number(data.get("paid") || 0), due_date: data.get("due_date") ? new Date(String(data.get("due_date"))).toISOString() : null } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say("Servis buyurtmasi qabul qilindi");
  }
  async function advanceRepair(repair: Repair) {
    const steps = ["RECEIVED", "DIAGNOSIS", "IN_PROGRESS", "READY", "DELIVERED"];
    const next = steps[Math.min(steps.indexOf(repair.status) + 1, steps.length - 1)];
    if (next === repair.status) return say("Bu buyurtma allaqachon oxirgi bosqichda", "info");
    if (busy) return; setBusy(true);
    const res = await api(`/repairs/${repair.id}/status`, { method: "POST", body: { status: next } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    await loadFromApi(); say("Servis buyurtmasi holati yangilandi");
  }
  async function createTelegramLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const customerId = Number(new FormData(event.currentTarget).get("customer"));
    if (busy) return; setBusy(true);
    const res = await api<{ customer: { name: string }; url: string }>(`/customers/${customerId}/telegram-link`, { method: "POST", body: {} });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    const qr = await QRCode.toDataURL(res.data.url, { width: 280, margin: 2, color: { dark: "#087653", light: "#ffffff" } });
    setTelegramLink({ customer: res.data.customer.name, url: res.data.url, qr });
    try { await navigator.clipboard.writeText(res.data.url); say("Telegram havolasi nusxalandi — mijozga yuboring"); } catch { say("Havola yaratildi, uni nusxalang"); }
  }
  async function getOpticalAdvice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const customerId = Number(data.get("customer"));
    const res = await api<OpticalAdvice>(`/customers/${customerId}/optical-advice`);
    if (!res.ok) return say(res.error, "error");
    setOpticalAdvice({ ...res.data, customer: { ...res.data.customer, visits: 0 } });
  }
  async function installPwa() {
    if (!installPrompt) {
      setInstallHint("iPhone: Safari menyusidan Share → Add to Home Screen. Android: brauzer menyusidan Install app.");
      return;
    }
    await installPrompt.prompt();
    const choice = await installPrompt.userChoice;
    setInstallPrompt(null);
    if (choice.outcome === "accepted") setInstallHint("Optika OS bosh ekranga o'rnatildi.");
  }
  async function createOpticalCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const frame = String(data.get("frame") || "");
    if (busy) return; setBusy(true);
    const res = await api("/optical-cases", { method: "POST", body: { customer_id: Number(data.get("customer")), frame_product_id: frame ? Number(frame) : null, chief_complaint: data.get("chief_complaint") || null } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say("Ramka tanlandi. Endi ko'z tekshiruvi bosqichiga o'ting.");
  }
  async function saveOpticalStep(event: FormEvent<HTMLFormElement>, endpoint: string, success: string) {
    event.preventDefault();
    if (!selectedOpticalCase) return say("Avval optik kartani tanlang", "info");
    const data = new FormData(event.currentTarget);
    const payload: Record<string, string | number | boolean | File> = Object.fromEntries([...data.entries()].filter(([, value]) => value !== ""));
    ["od_axis", "os_axis", "pd_right", "pd_left", "fitting_height_right", "fitting_height_left", "vertex_distance", "pantoscopic_tilt", "wrap_angle"].forEach(key => { if (payload[key] !== undefined) payload[key] = Number(payload[key]); });
    if (payload.referral_required !== undefined) payload.referral_required = payload.referral_required === "on";
    if (payload.photochromic !== undefined) payload.photochromic = payload.photochromic === "on";
    if (busy) return; setBusy(true);
    const res = await api(`/optical-cases/${selectedOpticalCase.id}/${endpoint}`, { method: "POST", body: payload });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say(success);
  }
  async function advanceLab(caseItem: OpticalCase) {
    const next = caseItem.lab?.status === "SENT" ? "RECEIVED" : caseItem.lab?.status === "RECEIVED" ? "QC_PASSED" : caseItem.lab?.status === "QC_FAILED" ? "QC_PASSED" : caseItem.lab?.status === "QC_PASSED" ? "READY" : caseItem.lab?.status === "READY" ? "DELIVERED" : null;
    if (!next) return say("Bu holat uchun keyingi bosqich yo'q", "info");
    if (busy) return; setBusy(true);
    const res = await api(`/optical-cases/${caseItem.id}/lab/status`, { method: "POST", body: { status: next } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    await loadFromApi(); say("Laboratoriya/QC holati yangilandi");
  }
  async function addBranch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (busy) return; setBusy(true);
    const res = await api("/branches", { method: "POST", body: { name: data.get("name"), code: data.get("code"), address: data.get("address") || null } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say("Yangi filial yaratildi");
  }
  async function addTeamUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const branchId = String(data.get("branch_id") || "");
    if (["SELLER", "OPTOMETRIST", "LAB_QC"].includes(String(data.get("role"))) && !branchId) return say("Bu rol uchun filial tanlang — aks holda xodim hech narsa ko'ra olmaydi", "info");
    if (busy) return; setBusy(true);
    const res = await api<TeamUser>("/users", { method: "POST", body: { username: data.get("username"), password: data.get("password"), role: data.get("role") } });
    if (!res.ok) { setBusy(false); return say(res.error, "error"); }
    if (branchId) {
      const assign = await api(`/branches/${branchId}/members`, { method: "POST", body: { user_id: res.data.id } });
      if (!assign.ok) { setBusy(false); return say(`Xodim yaratildi, lekin filialga biriktirilmadi: ${assign.error}`, "error"); }
    }
    setBusy(false); setModal(null); await loadFromApi(); say(branchId ? "Yangi xodim yaratildi va filialga biriktirildi" : "Yangi xodim yaratildi");
  }
  async function addStock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); const productId = Number(data.get("product")); const amount = Number(data.get("amount"));
    if (!amount) return say("Kirim miqdorini kiriting", "info");
    if (busy) return; setBusy(true);
    const res = await api(`/inventory/${productId}/receive`, { method: "POST", body: { quantity: amount } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say("Kirim bazaga saqlandi va ombor yangilandi");
  }
  async function advanceOrder(id: number) {
    if (busy) return; setBusy(true);
    const res = await api(`/orders/${id}/advance`, { method: "POST", body: {} });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    await loadFromApi(); say("Buyurtma holati yangilandi");
  }
  async function cancelOrder(id: number) {
    if (!window.confirm("Buyurtmani bekor qilishni tasdiqlaysizmi? Mahsulot omborga qaytadi.")) return;
    if (busy) return; setBusy(true);
    const res = await api(`/orders/${id}/cancel`, { method: "POST", body: {} });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    await loadFromApi(); say("Buyurtma bekor qilindi va rezerv omborga qaytdi");
  }
  async function addPrescription(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCustomer) return say("Avval mijozni tanlang", "info");
    const data = new FormData(event.currentTarget);
    const payload = Object.fromEntries([...data.entries()].filter(([, value]) => value !== ""));
    if (busy) return; setBusy(true);
    const res = await api(`/customers/${selectedCustomer.id}/prescriptions`, { method: "POST", body: payload });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); say(`${selectedCustomer.name} uchun retsept saqlandi`);
  }
  async function addSupplier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (busy) return; setBusy(true);
    const res = await api("/suppliers", { method: "POST", body: { name: data.get("name"), phone: data.get("phone") || null } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say("Supplier bazaga qo'shildi");
  }
  async function receiveCustomerPayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedCustomer) return say("Avval mijozni tanlang", "info");
    const data = new FormData(event.currentTarget);
    if (busy) return; setBusy(true);
    const res = await api(`/customers/${selectedCustomer.id}/payments`, { method: "POST", body: { amount: Number(data.get("amount")), comment: data.get("comment") || null } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say(`${selectedCustomer.name}dan qarz to'lovi qabul qilindi`);
  }
  async function paySupplier(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSupplier) return say("Avval supplierni tanlang", "info");
    const data = new FormData(event.currentTarget);
    if (busy) return; setBusy(true);
    const res = await api(`/suppliers/${selectedSupplier.id}/payments`, { method: "POST", body: { amount: Number(data.get("amount")), comment: data.get("comment") || null } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say(`${selectedSupplier.name}ga to'lov saqlandi`);
  }
  async function addPurchase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const quantity = Number(data.get("quantity")); const unitCost = Number(data.get("unit_cost")); const paid = Number(data.get("paid") || 0);
    if (busy) return; setBusy(true);
    const res = await api("/purchases", { method: "POST", body: { supplier_id: Number(data.get("supplier")), paid, invoice_no: data.get("invoice_no") || null, items: [{ product_id: Number(data.get("product")), quantity, unit_cost: unitCost }] } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say("Supplierdan kirim, qoldiq va qarzdorlik yangilandi");
  }
  async function changeCashShift(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const amount = Number(data.get("amount") || 0);
    const isOpening = modal === "cash-open";
    if (!isOpening && !cashShift?.id) { setModal(null); return say("Ochiq smena topilmadi — ro'yxat yangilandi", "info"); }
    const branchId = String(data.get("branch_id") || "");
    const body = isOpening ? { opening_amount: amount, ...(branchId ? { branch_id: Number(branchId) } : {}) } : { actual_amount: amount };
    if (busy) return; setBusy(true);
    const res = await api(isOpening ? "/cash-shifts/open" : `/cash-shifts/${cashShift?.id}/close`, { method: "POST", body });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say(isOpening ? "Kassa smenasi ochildi" : "Kassa smenasi yopildi");
  }
  async function returnSale(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedReturn) return say("Avval qaytariladigan mahsulotni tanlang", "info");
    const data = new FormData(event.currentTarget);
    if (busy) return; setBusy(true);
    const res = await api(`/sales/${selectedReturn.saleId}/return`, { method: "POST", body: { product_id: selectedReturn.product.id, quantity: Number(data.get("quantity")), disposition: data.get("disposition"), reason: data.get("reason") } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say("Qaytarish bazaga saqlandi, ombor va kassa yangilandi");
  }
  async function addExpense(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (busy) return; setBusy(true);
    const branchId = String(data.get("branch_id") || "");
    const res = await api("/expenses", { method: "POST", body: { category: data.get("category"), amount: Number(data.get("amount")), description: data.get("description") || null, ...(branchId ? { branch_id: Number(branchId) } : {}) } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say("Xarajat kassa va audit logga saqlandi");
  }
  async function addProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const branchId = String(data.get("branch_id") || "");
    if (busy) return; setBusy(true);
    const res = await api("/products", { method: "POST", body: { name: data.get("name"), brand: data.get("brand") || "Optika", category: data.get("category"), sale_price: Number(data.get("sale_price")), stock: Number(data.get("stock")), minimum_stock: Number(data.get("minimum_stock")), ...(branchId ? { branch_id: Number(branchId) } : {}) } });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    setModal(null); await loadFromApi(); say("Yangi mahsulot omborga qo'shildi");
  }

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (busy) return; setBusy(true);
    const res = await api<{ access_token: string; user: SessionUser }>("/auth/login", { method: "POST", body: { username: data.get("username"), password: data.get("password") }, skip401: true });
    setBusy(false);
    if (!res.ok) return say(res.error, "error");
    ["optika-products", "optika-customers", "optika-orders"].forEach(key => localStorage.removeItem(key));
    setProducts([]); setCustomers([]); setOrders([]);
    localStorage.setItem("optika-token", res.data.access_token);
    localStorage.setItem("optika-user", JSON.stringify(res.data.user));
    setNotice(null); setUser(res.data.user); setToken(res.data.access_token);
  }

  function signOut() {
    clearSession();
  }

  if (!sessionReady) return <main className="login-screen" />;
  if (!token || !user) return <LoginScreen onSubmit={signIn} notice={notice} clearNotice={() => setNotice(null)}/>;

  const modalTitles: Record<string, string> = {
    customer: "Yangi mijoz", order: "Yangi buyurtma", stock: "Omborga kirim", product: "Yangi mahsulot",
    supplier: "Yangi supplier", "cash-open": "Kassa smenasini ochish", "cash-close": "Kassa smenasini yopish",
    expense: "Xarajat kiritish", purchase: "Supplierdan kirim", user: "Yangi xodim", branch: "Yangi filial",
    "optical-case": "Yangi optik karta", "eye-exam": "Ko'z tekshiruvi", centration: "Centration o'lchovi",
    "lens-config": "Linza konfiguratsiyasi", "lab-job": "Laboratoriyaga yuborish",
    prescription: `${selectedCustomer?.name || "Mijoz"} retsepti`,
    return: `${selectedReturn?.product.name || "Mahsulot"} qaytarish`,
    "customer-payment": `${selectedCustomer?.name || "Mijoz"} qarzi`,
    "supplier-payment": `${selectedSupplier?.name || "Supplier"} to'lovi`,
  };
  const modalTitle = modal ? (modalTitles[modal] || "Optika OS") : "";

  return <main className="app-shell">
    <aside className={`side ${menu ? "show" : ""}`}>
      <div className="logo"><span>O</span><div>OPTIKA<small>BUSINESS OS</small></div></div>
      <nav>{sections.filter(([label]) => canSee(label)).map(([label, Icon]) => <button key={label} className={section === label ? "selected" : ""} onClick={() => { setSection(label); setMenu(false); }}><Icon size={19}/><span>{label}</span></button>)}</nav>
      <div className="side-bottom"><small>OPTIKA OS</small><b>{user.username.charAt(0).toUpperCase() + user.username.slice(1)}</b><span>{user.branch ? user.branch.name : user.role === "SELLER" ? "Filial biriktirilmagan" : "Barcha filiallar"}</span><span>{cashShift ? "Bugun ochiq smena" : "Smena yopiq"}</span></div>
    </aside>
    <section className="main">
      <header className="topbar"><button className="menu" onClick={() => setMenu(!menu)}><Menu/></button><div className="search-wrap"><div className="global-search"><Search size={18}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Mijoz, buyurtma yoki mahsulot qidiring"/>{query && <span>{searchResults.length} topildi</span>}{query && <button type="button" className="search-clear" onClick={() => { setQuery(""); setSearchResults([]); }}><X size={14}/></button>}</div>{searchResults.length > 0 && <div className="search-popover">{searchResults.map(result => <button key={`${result.type}-${result.id}`} onClick={() => { const target = result.type === "customer" ? "Mijozlar" : result.type === "product" ? "Ombor" : result.type === "order" ? "Buyurtmalar" : result.type === "supplier" ? "Supplierlar" : result.type === "repair" ? "Servis" : "Bosh sahifa"; goSection(target); setQuery(""); setSearchResults([]); say(`${result.title} — ${target} bo'limida`, "info"); }}><b>{result.title}</b><span>{result.type} · {result.subtitle}</span></button>)}</div>}</div><span className={`api-status ${backendOnline ? "online" : ""}`}>{backendOnline ? "API ulangan" : "Ulanmoqda"}</span>{HELP[section] && <button className="help-btn" onClick={() => setHelpOpen(true)} title="Bu bo'lim bo'yicha yordam"><HelpCircle size={19}/></button>}<button className="bell" onClick={() => { if (systemNotifications.length) { const first = systemNotifications[0]; goSection(first.type === "LOW_STOCK" ? "Ombor" : first.type === "PRESCRIPTION_REMINDER" ? "Mijozlar" : "Buyurtmalar"); say(`${first.title}: ${first.message}`, "info"); } else say("Yangi bildirishnoma yo'q", "info"); }}><Bell size={19}/>{systemNotifications.length > 0 && <i/>}</button><button className="account" onClick={signOut} title="Chiqish"><span className="avatar">{user.username.slice(0,2).toUpperCase()}</span><small>{user.role}{user.branch ? ` · ${user.branch.name}` : ""}</small></button></header>
      <div className="page">
        {user.role === "SELLER" && user.branch === null && <div className="branch-warning">Filialga biriktirilmagansiz — administratorga murojaat qiling. Amallar saqlanmaydi.</div>}
        {notice && <button className={`notice ${notice.tone}`} onClick={() => setNotice(null)}><b>{notice.tone === "error" ? "!" : notice.tone === "info" ? "i" : "✓"}</b>{notice.text}<X size={15}/></button>}
        {section === "Bosh sahifa" && <Dashboard revenue={todayRevenue} debt={debt} customers={customers.length} orders={orders} lowStock={lowStock} go={goSection} setModal={setModal} statusTone={statusTone} userName={user.username}/>}
        {!isStandalone && <section className="pwa-install"><div><b>Optika OS ilovasi</b><span>Telefoningiz bosh ekraniga qo'shing.</span>{installHint && <small>{installHint}</small>}</div><button onClick={installPwa}>{installPrompt ? "Ilovani o'rnatish" : "Bosh ekranga qo'shish"}</button></section>}
        {!isOnline && <div className="offline-banner">Offline rejim: avval yuklangan ma'lumotlar ko'rinadi. Internet qaytgach yangi amallarni davom ettiring.</div>}
        {systemNotifications.length > 0 && <section className="system-alerts">{systemNotifications.slice(0, 3).map(item => <button key={`${item.type}-${item.entity_id}`} className={item.severity === "warning" ? "warning" : "success"} onClick={() => goSection(item.type === "LOW_STOCK" ? "Ombor" : "Buyurtmalar")}><Bell size={15}/><span><b>{item.title}</b>{item.message}</span><ChevronRight size={15}/></button>)}</section>}
        {section === "Sotuv" && <POS products={products} cart={cart} total={cartTotal} query={query} add={addToCart} qty={updateQty} checkout={checkout} busy={busy} setModal={setModal}/>} 
        {section === "Sotuvlar" && <SalesHistory sales={sales} openReturn={(saleId, product) => { setSelectedReturn({ saleId, product }); setModal("return"); }}/>} 
        {section === "Buyurtmalar" && <Orders orders={orders} statusTone={statusTone} nextStatus={nextStatus} onAdvance={advanceOrder} onCancel={cancelOrder} open={() => setModal("order")}/>} 
        {section === "Servis" && <><div className="heading compact"><div><p>SERVIS / TA'MIRLASH</p><h1>Ta'mirlash buyurtmalari</h1><span>Qabul qilishdan topshirishgacha bo'lgan servis jarayoni.</span></div><button className="primary" onClick={() => setModal("repair")}>+ Servis qabul qilish</button></div><section className="card table-card"><div className="table-head"><span>BUYURTMA</span><span>MIJOZ / QURILMA</span><span>SUMMA</span><span>HOLAT</span><span></span></div>{repairs.length ? repairs.map(repair => <div className="table-row" key={repair.id}><b>#{repair.id}<small>{repair.issue}</small></b><div><b>{repair.customer.name}</b><span>{repair.device}</span></div><div><b>{format(repair.estimated_cost)}</b><span>Qoldiq: {format(repair.balance)}</span></div><span className={`badge ${repair.status === "READY" ? "ready" : repair.status === "DELIVERED" ? "done" : repair.status === "IN_PROGRESS" ? "working" : "neutral"}`}>{({RECEIVED:"Qabul qilindi",DIAGNOSIS:"Tekshiruv",IN_PROGRESS:"Ta'mirda",READY:"Tayyor",DELIVERED:"Topshirildi",CANCELLED:"Bekor"} as Record<string,string>)[repair.status]}</span><button className="advance" disabled={["DELIVERED","CANCELLED"].includes(repair.status)} onClick={() => advanceRepair(repair)}>{repair.status === "DELIVERED" ? "Yopilgan" : "Keyingi"}<ChevronRight size={14}/></button></div>) : <div className="empty"><Wrench/><b>Servis buyurtmalari yo'q</b><span>Birinchi ta'mirlash buyurtmasini qabul qiling</span></div>}</section></>} 
        {section === "Optik buyurtma" && <><div className="heading compact"><div><p>PROFESSIONAL OPTIKA WORKFLOW</p><h1>Ramkadan tayyor ko'zoynakkacha</h1><span>Ramka → tekshiruv → centration → linza → laboratoriya/QC → topshirish.</span></div><button className="primary" onClick={() => setModal("optical-case")}>+ Yangi optik karta</button></div><section className="card table-card"><div className="table-head"><span>KARTA</span><span>MIJOZ / RAMKA</span><span>TEKSHIRUV</span><span>JARAYON</span><span></span></div>{opticalCases.length ? opticalCases.map(item => <div className="table-row" key={item.id}><b>#{item.id}<small>{item.chief_complaint || "Ehtiyoj kiritilmagan"}</small></b><div><b>{item.customer.name}</b><span>{item.frame?.name || "Ramka tanlanmagan"}</span></div><div><b>{item.exam ? `${item.exam.od_sph || "—"} / ${item.exam.os_sph || "—"}` : "Kutilmoqda"}</b><span>{item.centration ? "Centration tayyor" : "O'lchov kutilmoqda"}</span></div><span className={`badge ${item.status === "READY" ? "ready" : item.status === "DELIVERED" ? "done" : item.status === "QC_PASSED" ? "working" : "neutral"}`}>{({INTAKE:"Qabul",FRAME_SELECTED:"Ramka",EXAM_COMPLETED:"Retsept",REFERRAL_REQUIRED:"Yo'naltirish",CENTRATION_COMPLETED:"Centration",LENS_CONFIGURED:"Linza",LAB_SENT:"Labda",RECEIVED:"Qabul qilindi",QC_PASSED:"QC o'tdi",QC_FAILED:"QC xato",READY:"Tayyor",DELIVERED:"Topshirildi"} as Record<string,string>)[item.status] || item.status}</span><div className="order-actions">{!item.exam ? <button className="advance" onClick={() => { setSelectedOpticalCase(item); setModal("eye-exam"); }}>Ko'z tekshiruvi</button> : !item.centration ? <button className="advance" onClick={() => { setSelectedOpticalCase(item); setModal("centration"); }}>Centration</button> : !item.lens ? <button className="advance" onClick={() => { setSelectedOpticalCase(item); setModal("lens-config"); }}>Linza</button> : !item.lab ? <button className="advance" onClick={() => { setSelectedOpticalCase(item); setModal("lab-job"); }}>Labga yuborish</button> : <button className="advance" disabled={item.status === "DELIVERED"} onClick={() => advanceLab(item)}>{item.status === "DELIVERED" ? "Yopilgan" : "Keyingi"}<ChevronRight size={14}/></button>}</div></div>) : <div className="empty"><ClipboardList/><b>Optik kartalar yo'q</b><span>Avval mijoz va ramkani tanlang</span></div>}</section></>} 
        {section === "Mijozlar" && <><div className="heading compact"><div><p>CRM / MIJOZLAR</p><h1>Mijozlar bazasi</h1><span>Retsept va qarzdorlikni bir joydan boshqaring.</span></div><button className="primary" onClick={() => setModal("customer")}>+ Yangi mijoz</button></div><section className="customer-grid">{customers.filter(customer => `${customer.name} ${customer.phone}`.toLowerCase().includes(query.toLowerCase())).map(customer => <article className="customer" key={customer.id}><button className="customer-main" onClick={() => { setSelectedCustomer(customer); setModal("prescription"); }}><div className="customer-avatar">{customer.name.split(" ").map(value => value[0]).join("").slice(0,2)}</div><div className="customer-info"><b>{customer.name}</b><span>{customer.phone}</span><small>{customer.debt ? `Qarz: ${format(customer.debt)}` : "Qarz yo'q"}</small></div><ChevronRight size={18}/></button>{customer.debt > 0 && <button className="debt-action" onClick={() => { setSelectedCustomer(customer); setModal("customer-payment"); }}>Qarz to'lovi</button>}</article>)}</section></>} 
        {section === "Ombor" && <Inventory products={products} query={query} open={() => setModal("stock")} addProduct={() => setModal("product")}/>} 
        {section === "Mijozlar" && telegramLink && <><button className="telegram-send" onClick={() => window.open(`https://t.me/share/url?url=${encodeURIComponent(telegramLink.url)}&text=${encodeURIComponent(`${telegramLink.customer} uchun Optika OS bot havolasi`)}`, "_blank", "noopener,noreferrer")}>Telegramda yuborish</button><section className="telegram-qr"><div><p>MIJOZ UCHUN QR-KOD</p><h2>{telegramLink.customer} telefonida skaner qilsin</h2><span>Telegram ochiladi va bot avtomatik ulanadi.</span></div><img src={telegramLink.qr} alt={`${telegramLink.customer} uchun Telegram QR-kodi`}/></section></>}
        {section === "Mijozlar" && <section className="card telegram-link-card"><div><p>TELEGRAM BOT</p><h2>Mijozga bog'lanish havolasini yuboring</h2><span>Mijoz havolani bir marta bosadi — botga avtomatik ulanadi.</span></div><form className="form telegram-link-form" onSubmit={createTelegramLink}><select name="customer" required defaultValue=""><option value="" disabled>Mijozni tanlang</option>{customers.map(customer => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select><button className="primary">Havola yaratish</button></form>{telegramLink && <div className="telegram-link-result"><b>{telegramLink.customer} uchun havola</b><input readOnly value={telegramLink.url} onFocus={event => event.currentTarget.select()}/><small>Havola 7 kun amal qiladi va bir marta bog'lash uchun ishlatiladi.</small></div>}</section>} 
        {section === "Aqlli yordamchi" && <><div className="heading compact"><div><p>AQLLI OPTIKA YORDAMCHISI</p><h1>Retsept asosida tavsiya</h1><span>Qoidaga asoslangan, tushuntiriladigan optik yordamchi.</span></div></div><section className="card ai-card"><form className="form" onSubmit={getOpticalAdvice}><label>Mijoz<select name="customer" required defaultValue=""><option value="" disabled>Mijozni tanlang</option>{customers.map(customer => <option key={customer.id} value={customer.id}>{customer.name} — {customer.phone}</option>)}</select></label><button className="primary"> <Sparkles size={16}/> Tavsiya olish</button></form>{opticalAdvice && <div className="advice-result"><h2>{opticalAdvice.customer.name} uchun tavsiya</h2>{opticalAdvice.recommendations.map(item => <p key={item}><Sparkles size={15}/>{item}</p>)}<small>{opticalAdvice.warning}</small></div>}</section></>} 
        {section === "Kassa" && <Cash revenue={todayRevenue} debt={debt} orders={orders} shift={cashShift} branchName={user.branch?.name} open={() => setModal("cash-open")} close={() => setModal("cash-close")} expense={() => setModal("expense")}/>} 
        {section === "Supplierlar" && <><div className="heading compact"><div><p>SUPPLIERLAR</p><h1>Yetkazib beruvchilar</h1><span>Kirim, to'lov va qarzdorlikni boshqaring.</span></div><div className="heading-actions"><button onClick={() => setModal("purchase")}>+ Kirim</button><button className="primary" onClick={() => setModal("supplier")}>+ Yangi supplier</button></div></div><section className="customer-grid">{suppliers.map(supplier => <article className="customer" key={supplier.id}><div className="customer-avatar">{supplier.name.slice(0,2).toUpperCase()}</div><div className="customer-info"><b>{supplier.name}</b><span>{supplier.phone || "Telefon kiritilmagan"}</span><small>{supplier.balance ? `Qarz: ${format(supplier.balance)}` : "Qarz yo'q"}</small></div>{supplier.balance > 0 && <button className="debt-action" onClick={() => { setSelectedSupplier(supplier); setModal("supplier-payment"); }}>To'lash</button>}</article>)}</section></>} 
        {section === "Xodimlar" && <><div className="heading compact"><div><p>XO'JALIK / XODIMLAR</p><h1>Foydalanuvchilar va rollar</h1><span>Owner, manager va sotuvchi huquqlarini boshqaring.</span></div>{user.role === "OWNER" && <button className="primary" onClick={() => setModal("user")}>+ Xodim qo'shish</button>}</div><section className="customer-grid">{team.map(member => <article className="customer" key={member.id}><div className="customer-avatar">{member.username.slice(0,2).toUpperCase()}</div><div className="customer-info"><b>{member.username}</b><span>{member.role}</span><small>{member.active ? "Faol foydalanuvchi" : "Nofaol foydalanuvchi"}</small></div><span className={`badge ${member.active ? "ready" : "neutral"}`}>{member.active ? "Faol" : "Nofaol"}</span></article>)}</section>{!team.length && <div className="empty"><Users/><b>Bu bo'lim faqat Owner uchun</b></div>}</>} 
        {section === "Hisobotlar" && <Reports report={finance}/>} 
        {section === "Filiallar" && <><div className="heading compact"><div><p>KO'P FILIALLI BOSHQARUV</p><h1>Filiallar</h1><span>Filiallar va ulardagi xodimlar reyestri.</span></div>{user.role === "OWNER" && <button className="primary" onClick={() => setModal("branch")}>+ Filial qo'shish</button>}</div><section className="customer-grid">{branches.map(branch => <article className="customer" key={branch.id}><div className="customer-avatar">{branch.code.slice(0,2)}</div><div className="customer-info"><b>{branch.name}</b><span>{branch.address || "Manzil kiritilmagan"}</span><small>{branch.code} · {branch.members} xodim</small></div><span className={`badge ${branch.active ? "ready" : "neutral"}`}>{branch.active ? "Faol" : "Nofaol"}</span></article>)}</section></>}
        {section === "Qo'llanma" && <><div className="heading compact"><div><p>YORDAM / QO'LLANMA</p><h1>Ilovadan qanday foydalanamiz</h1><span>Har bir bo'lim nima uchun va qanday ishlatilishi — oddiy qadamlar bilan.</span></div><button className="primary" onClick={() => setTourStep(0)}><Sparkles size={16}/> Yo'l-yo'riqni qayta ko'rish</button></div><section className="guide-grid">{Object.entries(HELP).map(([name, info]) => <article className="guide-card" key={name}><h3>{name}</h3><p>{info.what}</p><ol>{info.steps.map((s, i) => <li key={i}>{s}</li>)}</ol></article>)}</section></>}
      </div>
    </section>
    {modal && <Modal title={modalTitle} close={() => setModal(null)}>
      {modal === "customer" && <form className="form" onSubmit={addCustomer}>{!user.branch && <label>Filial<select name="branch_id" required defaultValue=""><option value="" disabled>Filialni tanlang</option>{branches.filter(branch => branch.active).map(branch => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label>}<label>Ism va familiya<input name="name" required placeholder="Masalan, Dilshod Karimov"/></label><label>Telefon<input name="phone" required inputMode="tel" placeholder="90 123 45 67"/></label><button className="primary">Mijozni saqlash</button></form>}
      {modal === "order" && <form className="form" onSubmit={addOrder}><label>Mijoz<select name="customer" required><option value="">Mijozni tanlang</option>{customers.map(c => <option key={c.id} value={c.id}>{c.name} — {c.phone}</option>)}</select></label><div className="order-mode-switch"><button type="button" className={manualOrder ? "" : "active"} onClick={() => setManualOrder(false)}>Ro'yxatdan</button><button type="button" className={manualOrder ? "active" : ""} onClick={() => setManualOrder(true)}>Qo'lda kiritish</button></div>{manualOrder ? <><label>Mahsulot nomi<input name="item_name" required placeholder="Masalan, Import ramka + linza"/></label><label>Umumiy narx (som)<input name="total" type="number" min="0" required placeholder="0"/></label></> : <label>Mahsulot<select name="product" required={!manualOrder}><option value="">Ramka yoki linzani tanlang</option>{products.filter(p => p.stock).map(p => <option key={p.id} value={p.id}>{p.name} — {format(p.price)}</option>)}</select></label>}<label>Avans<input name="paid" type="number" min="0" defaultValue="0"/></label><button className="primary">Buyurtma yaratish</button></form>}
      {modal === "stock" && <form className="form" onSubmit={addStock}><label>Mahsulot<select name="product">{products.map(p => <option key={p.id} value={p.id}>{p.name} (qoldiq: {p.stock})</option>)}</select></label><label>Miqdor<input name="amount" type="number" min="1" required defaultValue="1"/></label><button className="primary">Kirimni saqlash</button></form>}
      {modal === "product" && <form className="form" onSubmit={addProduct}>{!user.branch && <label>Filial<select name="branch_id" required defaultValue=""><option value="" disabled>Filialni tanlang</option>{branches.filter(branch => branch.active).map(branch => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label>}<label>Mahsulot nomi<input name="name" required placeholder="Masalan, Ray-Ban RB 3025"/></label><label>Brend<input name="brand" placeholder="Ray-Ban"/></label><label>Turi<select name="category"><option value="FRAME">Rama</option><option value="LENS">Linza</option><option value="CONTACT_LENS">Kontakt linza</option><option value="ACCESSORY">Aksessuar</option></select></label><label>Sotuv narxi<input name="sale_price" required type="number" min="1"/></label><label>Boshlangich qoldiq<input name="stock" required type="number" min="0" defaultValue="0"/></label><label>Minimum qoldiq<input name="minimum_stock" required type="number" min="0" defaultValue="0"/></label><button className="primary">Mahsulotni saqlash</button></form>}
      {modal === "prescription" && <form className="form prescription-form" onSubmit={addPrescription}><div className="eye-label">O'ng ko'z (OD)</div><div className="eye-grid"><label>SPH<input name="od_sph" placeholder="-2.75"/></label><label>CYL<input name="od_cyl" placeholder="-0.50"/></label><label>AXIS<input name="od_axis" type="number" min="0" max="180" placeholder="90"/></label></div><div className="eye-label">Chap ko'z (OS)</div><div className="eye-grid"><label>SPH<input name="os_sph" placeholder="-1.00"/></label><label>CYL<input name="os_cyl" placeholder="-0.25"/></label><label>AXIS<input name="os_axis" type="number" min="0" max="180" placeholder="90"/></label></div><label>PD (mm)<input name="pd" type="number" min="40" max="85" step="0.5" placeholder="62"/></label><label>Eslatma sanasi (keyingi tekshiruv)<input name="reminder_at" type="date"/></label><label>Izoh<input name="note" placeholder="Qo'shimcha qayd"/></label><button className="primary">Retseptni saqlash</button></form>}
      {modal === "supplier" && <form className="form" onSubmit={addSupplier}><label>Supplier nomi<input name="name" required placeholder="Masalan, Optika Distribyutor"/></label><label>Telefon<input name="phone" inputMode="tel" placeholder="90 123 45 67"/></label><button className="primary">Supplierni saqlash</button></form>}
      {modal === "customer-payment" && <form className="form" onSubmit={receiveCustomerPayment}><p className="form-note">Joriy qarz: <b>{format(selectedCustomer?.debt || 0)}</b></p><label>Qabul qilinadigan summa<input name="amount" required type="number" min="1" max={selectedCustomer?.debt || 0}/></label><label>Izoh<input name="comment" placeholder="Masalan, naqd pulda"/></label><button className="primary">To'lovni qabul qilish</button></form>}
      {modal === "supplier-payment" && <form className="form" onSubmit={paySupplier}><p className="form-note">Joriy qarz: <b>{format(selectedSupplier?.balance || 0)}</b></p><label>To'lanadigan summa<input name="amount" required type="number" min="1" max={selectedSupplier?.balance || 0}/></label><label>Izoh<input name="comment" placeholder="Masalan, bank o'tkazmasi"/></label><button className="primary">Supplierga to'lash</button></form>}
      {modal === "purchase" && <form className="form" onSubmit={addPurchase}><label>Supplier<select name="supplier" required><option value="">Supplierni tanlang</option>{suppliers.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label><label>Mahsulot<select name="product" required>{products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></label><div className="form-split"><label>Miqdor<input name="quantity" type="number" min="1" required defaultValue="1"/></label><label>1 dona tannarx<input name="unit_cost" type="number" min="1" required/></label></div><label>Hozir to'langan summa<input name="paid" type="number" min="0" defaultValue="0"/></label><label>Hisob-faktura raqami<input name="invoice_no" placeholder="INV-001"/></label><button className="primary">Kirimni saqlash</button></form>}
      {(modal === "cash-open" || modal === "cash-close") && <form className="form" onSubmit={changeCashShift}>{modal === "cash-open" && !user.branch && <label>Filial<select name="branch_id" required defaultValue=""><option value="" disabled>Filialni tanlang</option>{branches.filter(branch => branch.active).map(branch => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label>}<label>{modal === "cash-open" ? "Boshlangich summa" : "Kassadagi haqiqiy summa"}<input name="amount" required type="number" min="0" defaultValue={modal === "cash-close" ? cashShift?.opening_amount || 0 : 0}/></label><button className="primary">{modal === "cash-open" ? "Smenani ochish" : "Smenani yopish"}</button></form>}
      {modal === "return" && <form className="form" onSubmit={returnSale}><label>Miqdor<input name="quantity" required type="number" min="1" max="1" defaultValue="1"/></label><label>Holati<select name="disposition"><option value="RESTOCK">Yaroqli — omborga qaytarish</option><option value="DAMAGE">Shikastlangan — damage</option></select></label><label>Sabab<input name="reason" required placeholder="Masalan, mijoz fikrini ozgartirdi"/></label><button className="primary">Qaytarishni tasdiqlash</button></form>}
      {modal === "expense" && <form className="form" onSubmit={addExpense}>{!user.branch && <label>Filial<select name="branch_id" required defaultValue=""><option value="" disabled>Filialni tanlang</option>{branches.filter(branch => branch.active).map(branch => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label>}<label>Kategoriya<select name="category"><option>Ish haqi</option><option>Transport</option><option>Kommunal</option><option>Marketing</option><option>Tamir</option><option>Boshqa</option></select></label><label>Summa<input name="amount" required type="number" min="1"/></label><label>Izoh<input name="description" placeholder="Xarajat tavsifi"/></label><button className="primary">Xarajatni saqlash</button></form>}
      {modal === "repair" && <form className="form" onSubmit={addRepair}><label>Mijoz<select name="customer" required><option value="">Mijozni tanlang</option>{customers.map(customer => <option key={customer.id} value={customer.id}>{customer.name} — {customer.phone}</option>)}</select></label><label>Buyum / qurilma<input name="device" required placeholder="Masalan, ko'zoynak ramkasi"/></label><label>Nosozlik tavsifi<input name="issue" required placeholder="Masalan, siniq dasta, vint yo'q"/></label><div className="form-split"><label>Xizmat narxi<input name="estimated_cost" type="number" min="0" required/></label><label>Avans<input name="paid" type="number" min="0" defaultValue="0"/></label></div><label>Tayyor bo'lish sanasi<input name="due_date" type="date"/></label><button className="primary">Servisga qabul qilish</button></form>}
      {modal === "user" && <form className="form" onSubmit={addTeamUser}><label>Login<input name="username" required placeholder="masalan, malika"/></label><label>Vaqtinchalik parol<input name="password" required type="password" minLength={6}/></label><label>Roli<select name="role"><option value="SELLER">Sotuvchi</option><option value="OPTOMETRIST">Optometrist</option><option value="LAB_QC">Laboratoriya / QC</option><option value="MANAGER">Manager</option><option value="OWNER">Owner</option></select></label><label>Filial<select name="branch_id" defaultValue=""><option value="">Filialsiz (butun tarmoq)</option>{branches.filter(branch => branch.active).map(branch => <option key={branch.id} value={branch.id}>{branch.name}</option>)}</select></label><button className="primary">Xodimni yaratish</button></form>}
      {modal === "branch" && <form className="form" onSubmit={addBranch}><label>Filial nomi<input name="name" required placeholder="Masalan, Yunusobod filiali"/></label><label>Filial kodi<input name="code" required placeholder="YUN-01"/></label><label>Manzil<input name="address" placeholder="Toshkent, Yunusobod"/></label><button className="primary">Filialni yaratish</button></form>}
      {modal === "optical-case" && <form className="form" onSubmit={createOpticalCase}><p className="form-note">1-bosqich: mijoz ehtiyoji va tanlangan rama qayd qilinadi. Yakuniy linza keyingi klinik o'lchovlardan keyin tanlanadi.</p><label>Mijoz<select name="customer" required><option value="">Mijozni tanlang</option>{customers.map(customer => <option key={customer.id} value={customer.id}>{customer.name} — {customer.phone}</option>)}</select></label><label>Tanlangan rama<select name="frame"><option value="">Keyin tanlanadi</option>{products.filter(product => product.type === "FRAME").map(product => <option key={product.id} value={product.id}>{product.name} — {format(product.price)}</option>)}</select></label><label>Mijoz ehtiyoji<input name="chief_complaint" placeholder="Masalan, uzoqni xira ko'radi / o'qish uchun"/></label><button className="primary">Optik kartani boshlash</button></form>}
      {modal === "eye-exam" && <form className="form prescription-form" onSubmit={event => saveOpticalStep(event, "exam", "Ko'z tekshiruvi va retsept saqlandi") }><p className="form-note">2-bosqich: faqat malakali optometrist ko'z tekshiruvi natijasini tasdiqlaydi.</p><div className="eye-label">O'ng ko'z (OD)</div><div className="eye-grid"><label>SPH<input name="od_sph" placeholder="-2.75"/></label><label>CYL<input name="od_cyl" placeholder="-0.50"/></label><label>AXIS<input name="od_axis" type="number" min="0" max="180"/></label></div><div className="eye-label">Chap ko'z (OS)</div><div className="eye-grid"><label>SPH<input name="os_sph" placeholder="-1.00"/></label><label>CYL<input name="os_cyl" placeholder="-0.25"/></label><label>AXIS<input name="os_axis" type="number" min="0" max="180"/></label></div><div className="form-split"><label>ADD<input name="add_power" placeholder="+1.50"/></label><label>Prism<input name="prism" placeholder="Masalan, 1Δ BI"/></label></div><div className="form-split"><label>Uzoq VA<input name="distance_va" placeholder="6/6"/></label><label>Yaqin VA<input name="near_va" placeholder="N6"/></label></div><label>Klinik qayd<input name="clinical_note" placeholder="Tekshiruv qaydi"/></label><label className="check-label"><input name="referral_required" type="checkbox"/> Shifokorga yo'naltirish kerak</label><button className="primary">Retseptni tasdiqlash</button></form>}
      {modal === "centration" && <form className="form" onSubmit={event => saveOpticalStep(event, "centration", "Centration o'lchovlari saqlandi") }><p className="form-note">3-bosqich: rama mijoz yuzida to'g'ri sozlangandan keyin o'lchov olinadi.</p><div className="form-split"><label>O'ng PD (mm)<input name="pd_right" required type="number" step="0.1" min="20" max="45"/></label><label>Chap PD (mm)<input name="pd_left" required type="number" step="0.1" min="20" max="45"/></label></div><div className="form-split"><label>O'ng fitting height<input name="fitting_height_right" required type="number" step="0.1" min="10" max="45"/></label><label>Chap fitting height<input name="fitting_height_left" required type="number" step="0.1" min="10" max="45"/></label></div><div className="form-split"><label>Vertex distance<input name="vertex_distance" type="number" step="0.1" placeholder="12"/></label><label>Pantoscopic tilt<input name="pantoscopic_tilt" type="number" step="0.1" placeholder="8"/></label></div><label>Wrap angle<input name="wrap_angle" type="number" step="0.1" placeholder="5"/></label><button className="primary">Centrationni saqlash</button></form>}
      {modal === "lens-config" && <form className="form" onSubmit={event => saveOpticalStep(event, "lens", "Linza konfiguratsiyasi saqlandi") }><p className="form-note">4-bosqich: retsept, rama va o'lchovga qarab tanlanadi.</p><label>Linza dizayni<select name="lens_design"><option value="SINGLE_VISION">Bir fokusli</option><option value="READING">O'qish uchun</option><option value="BIFOCAL">Bifokal</option><option value="PROGRESSIVE">Progressiv</option></select></label><label>Material indeksi<select name="material_index"><option value="1.50">1.50</option><option value="1.56">1.56</option><option value="1.60">1.60</option><option value="1.67">1.67</option><option value="1.74">1.74</option><option value="POLYCARBONATE">Polikarbonat</option></select></label><label>Qoplama<input name="coating" placeholder="Masalan, antirefleks"/></label><label className="check-label"><input name="photochromic" type="checkbox"/> Fotoxrom</label><label>Laboratoriya uchun izoh<input name="lab_note" placeholder="Kesim, qirra, rama qaydi"/></label><button className="primary">Linza tanlovini saqlash</button></form>}
      {modal === "lab-job" && <form className="form" onSubmit={event => saveOpticalStep(event, "lab", "Laboratoriyaga yuborildi") }><p className="form-note">5-bosqich: laboratoriya topshirig'i yaratiladi.</p><label>Laboratoriya nomi<input name="laboratory" placeholder="Masalan, Essilor Lab"/></label><label>Lab raqami<input name="job_reference" placeholder="LAB-2026-001"/></label><button className="primary">Laboratoriyaga yuborish</button></form>}
    </Modal>}
    {helpOpen && HELP[section] && <Modal title={`${section} — yordam`} close={() => setHelpOpen(false)}><div className="help-body"><p className="help-what">{HELP[section].what}</p><b className="help-label">Qanday ishlatiladi:</b><ol className="help-steps">{HELP[section].steps.map((s, i) => <li key={i}>{s}</li>)}</ol></div></Modal>}
    {tourStep >= 0 && tourStep < TOUR.length && <div className="tour-bg"><div className="tour-card"><div className="tour-progress">{TOUR.map((_, i) => <span key={i} className={i === tourStep ? "on" : ""}/>)}</div><small>QADAM {tourStep + 1} / {TOUR.length}</small><h2>{TOUR[tourStep].title}</h2><p>{TOUR[tourStep].text}</p><div className="tour-actions"><button className="tour-skip" onClick={finishTour}>O'tkazib yuborish</button>{tourStep > 0 && <button className="tour-back" onClick={() => setTourStep(tourStep - 1)}>Orqaga</button>}<button className="tour-next primary" onClick={() => { if (tourStep + 1 >= TOUR.length) finishTour(); else setTourStep(tourStep + 1); }}>{tourStep + 1 >= TOUR.length ? "Tayyor!" : "Keyingi"}</button></div></div></div>}
  </main>;
}

function Dashboard({revenue,debt,customers,orders,lowStock,go,setModal,statusTone,userName}:{revenue:number;debt:number;customers:number;orders:Order[];lowStock:Product[];go:(value:string)=>void;setModal:(value:"customer"|"order"|"stock")=>void;statusTone:(value:Order["status"])=>string;userName:string}) { const now = new Date(); const uzMonths = ["Yanvar","Fevral","Mart","Aprel","May","Iyun","Iyul","Avgust","Sentabr","Oktabr","Noyabr","Dekabr"]; const uzDays = ["Yakshanba","Dushanba","Seshanba","Chorshanba","Payshanba","Juma","Shanba"]; const dateLabel = `${now.getDate()}-${uzMonths[now.getMonth()]}, ${uzDays[now.getDay()]}`.toUpperCase(); const hour = now.getHours(); const greeting = hour < 6 ? "Xayrli tun" : hour < 12 ? "Xayrli tong" : hour < 18 ? "Xayrli kun" : "Xayrli kech"; const displayName = userName.charAt(0).toUpperCase() + userName.slice(1); return <><div className="heading"><div><p>{dateLabel}</p><h1>{greeting}, {displayName}</h1><span>Optikangizdagi bugungi holat shu yerda.</span></div><div className="heading-actions"><button onClick={() => setModal("customer")}>+ Mijoz</button><button className="primary" onClick={() => setModal("order")}>+ Buyurtma</button></div></div><div className="metric-grid"><Metric icon={<CircleDollarSign/>} label="Bugungi tushum" value={format(revenue)} note="Yopilgan va qabul qilingan"/><Metric icon={<ShoppingBag/>} label="Faol buyurtma" value={`${orders.filter(o => o.status !== "Topshirildi" && o.status !== "Bekor qilindi").length} ta`} note="Jarayondagi buyurtmalar"/><Metric icon={<Users/>} label="Mijozlar" value={`${customers} ta`} note="Bazadagi mijozlar"/><Metric icon={<Archive/>} label="Mijoz qarzi" value={format(debt)} note="Qabul qilinishi kerak"/></div><div className="two-col"><section className="card"><div className="card-head"><div><h2>So'nggi buyurtmalar</h2><p>Holatni bir bosishda kuzating</p></div><button onClick={() => go("Buyurtmalar")}>Barchasi <ChevronRight size={15}/></button></div><div className="order-list">{orders.slice(0,4).map(o => <div className="order-row" key={o.id}><div className="order-id"><b>#{o.id}</b><span>{o.customer}</span></div><div className="hide-small"><b>{format(o.total)}</b><span>{o.item}</span></div><span className={`badge ${statusTone(o.status)}`}>{o.status}</span></div>)}</div></section><section className="card"><div className="card-head"><div><h2>E'tibor kerak</h2><p>Tezkor tekshiruv</p></div></div><button className="attention" onClick={() => go("Ombor")}><span className="warn">{lowStock.length}</span><div><b>Kam qolgan mahsulot</b><small>Minimum qoldiqdan past</small></div><ChevronRight size={17}/></button><button className="attention" onClick={() => go("Buyurtmalar")}><span className="good">{orders.filter(o => o.status === "Tayyor").length}</span><div><b>Tayyor buyurtmalar</b><small>Mijozga topshirish kerak</small></div><ChevronRight size={17}/></button><button className="attention" onClick={() => go("Kassa")}><span className="cash">{orders.filter(o => o.paid < o.total && o.status !== "Bekor qilindi").length}</span><div><b>Qoldiq to'lovlar</b><small>Kassa va qarzdorlikda ko'ring</small></div><ChevronRight size={17}/></button></section></div></> }
function Metric({icon,label,value,note}:{icon:React.ReactNode;label:string;value:string;note:string}) { return <article className="metric"><i>{icon}</i><span>{label}</span><strong>{value}</strong><small>{note}</small></article> }
function POS({products,cart,total,query,add,qty,checkout,busy,setModal}:{products:Product[];cart:CartLine[];total:number;query:string;add:(p:Product)=>void;qty:(id:number,c:number)=>void;checkout:()=>void;busy:boolean;setModal:(x:"customer")=>void}) { const visible = products.filter(p => `${p.name} ${p.brand} ${p.type}`.toLowerCase().includes(query.toLowerCase())); return <><div className="heading compact"><div><p>POS / SOTUV</p><h1>Yangi sotuv</h1><span>Mahsulotni savatchaga qo'shing va to'lovni yakunlang.</span></div><button onClick={() => setModal("customer")}>+ Yangi mijoz</button></div><div className="pos"><section className="catalog"><div className="catalog-title"><h2>Mahsulotlar</h2><span>{visible.length} ta natija</span></div><div className="product-grid">{visible.map(p => <button className="product" key={p.id} disabled={!p.stock} onClick={() => add(p)}><div className="product-image">{p.type === "Rama" ? "◯" : "◈"}</div><small>{p.brand} · {p.type}</small><b>{p.name}</b><strong>{format(p.price)}</strong><span className={p.stock <= p.min ? "stock low" : "stock"}>{p.stock} dona qoldi</span></button>)}</div></section><aside className="cart"><div className="cart-head"><div><h2>Savatcha</h2><span>{cart.length ? `${cart.length} xil mahsulot` : "Hali bo'sh"}</span></div><ShoppingBag size={19}/></div>{cart.length ? <><div className="cart-lines">{cart.map(line => <div className="cart-line" key={line.id}><div><b>{line.name}</b><span>{format(line.price)}</span></div><div className="qty"><button onClick={() => qty(line.id, -1)}><Minus size={14}/></button><b>{line.qty}</b><button onClick={() => qty(line.id, 1)}><Plus size={14}/></button></div><strong>{format(line.price * line.qty)}</strong></div>)}</div><div className="total"><span>Jami</span><strong>{format(total)}</strong></div><button className="checkout" onClick={checkout} disabled={busy}><CreditCard size={18}/> To'lovni yakunlash</button></> : <div className="empty"><ShoppingBag/><b>Savatcha bo'sh</b><span>Chap tomondan mahsulot tanlang</span></div>}</aside></div></> }
function SalesHistory({sales,openReturn}:{sales:SaleRecord[];openReturn:(saleId:number,product:Product)=>void}) { return <><div className="heading compact"><div><p>SOTUVLAR TARIXI</p><h1>Yakunlangan sotuvlar</h1><span>Mahsulot bo'yicha qaytarish shu yerdan amalga oshiriladi.</span></div></div><section className="card sale-history">{sales.length ? sales.map(sale => <article className="sale-history-row" key={sale.id}><div><b>Chek #{sale.id}</b><span>{sale.customer?.name || "Mehmon mijoz"} · {format(sale.total)}</span></div><div className="sale-items">{sale.items.map(item => <button key={item.product.id} onClick={() => openReturn(sale.id,item.product)}><span>{item.product.name} × {item.quantity}</span><b>Qaytarish</b></button>)}</div></article>) : <div className="empty"><CreditCard/><b>Sotuvlar topilmadi</b></div>}</section></> }
function Orders({orders,statusTone,nextStatus,onAdvance,onCancel,open}:{orders:Order[];statusTone:(value:Order["status"])=>string;nextStatus:(value:Order["status"])=>Order["status"];onAdvance:(id:number)=>void;onCancel:(id:number)=>void;open:()=>void}) { return <><div className="heading compact"><div><p>BUYURTMALAR</p><h1>Buyurtmalar boshqaruvi</h1><span>Statusni bir tugma bilan keyingi bosqichga o'tkazing.</span></div><button className="primary" onClick={open}>+ Yangi buyurtma</button></div><section className="card table-card"><div className="table-head"><span>BUYURTMA</span><span>MIJOZ / MAHSULOT</span><span>SUMMA</span><span>HOLAT</span><span></span></div>{orders.map(order => <div className="table-row" key={order.id}><b>#{order.id}<small>{order.date}</small></b><div><b>{order.customer}</b><span>{order.item}</span></div><div><b>{format(order.total)}</b><span>To'langan: {format(order.paid)}</span></div><span className={`badge ${statusTone(order.status)}`}>{order.status}</span><div className="order-actions"><button className="advance" disabled={order.status === "Topshirildi" || order.status === "Bekor qilindi"} onClick={() => onAdvance(order.id)}>{order.status === "Topshirildi" ? "Yopilgan" : "Keyingi"}<ChevronRight size={14}/></button>{!['Topshirildi','Bekor qilindi'].includes(order.status) && <button className="cancel-order" onClick={() => onCancel(order.id)}>Bekor qilish</button>}</div></div>)}</section></> }
function Customers({customers,query,open,openPrescription}:{customers:Customer[];query:string;open:()=>void;openPrescription:(customer:Customer)=>void}) { const rows = customers.filter(c => `${c.name} ${c.phone}`.toLowerCase().includes(query.toLowerCase())); return <><div className="heading compact"><div><p>CRM / MIJOZLAR</p><h1>Mijozlar bazasi</h1><span>Mijozni tanlab, yangi retsept qo'shing.</span></div><button className="primary" onClick={open}>+ Yangi mijoz</button></div><section className="customer-grid">{rows.map(c => <button className="customer" key={c.id} onClick={() => openPrescription(c)}><div className="customer-avatar">{c.name.split(" ").map(v => v[0]).join("").slice(0,2)}</div><div className="customer-info"><b>{c.name}</b><span>{c.phone}</span><small>{c.visits} ta xarid · {c.debt ? `Qarz: ${format(c.debt)}` : "Qarz yo'q"}</small></div><ChevronRight size={18}/></button>)}</section></> }
function Inventory({products,query,open,addProduct}:{products:Product[];query:string;open:()=>void;addProduct:()=>void}) { const rows = products.filter(p => `${p.name} ${p.brand} ${p.type}`.toLowerCase().includes(query.toLowerCase())); return <><div className="heading compact"><div><p>OMBOR</p><h1>Mahsulot qoldiqlari</h1><span>Qoldiq sotuv va buyurtmadan avtomatik kamayadi.</span></div><div className="heading-actions"><button onClick={addProduct}>+ Mahsulot</button><button className="primary" onClick={open}><PackagePlus size={17}/> Kirim qilish</button></div></div><section className="card table-card"><div className="table-head inventory-head"><span>MAHSULOT</span><span>TURI</span><span>NARX</span><span>QOLDIQ</span></div>{rows.map(p => <div className="table-row inventory-row" key={p.id}><div><b>{p.name}</b><span>{p.brand}</span></div><span>{p.type}</span><b>{format(p.price)}</b><span className={p.stock <= p.min ? "stock low" : "stock"}>{p.stock} dona <small>min: {p.min}</small></span></div>)}</section></> }
function Cash({revenue,debt,orders,shift,branchName,open,close,expense}:{revenue:number;debt:number;orders:Order[];shift:CashShift | null;branchName?:string;open:()=>void;close:()=>void;expense:()=>void}) { return <><div className="heading compact"><div><p>KASSA</p><h1>Bugungi kassa</h1><span>{shift ? `Smena #${shift.id} ochiq` : "Smena hozir yopiq"}{branchName ? ` · ${branchName}` : ""}</span></div><div className="heading-actions"><button onClick={expense}>+ Xarajat</button>{shift ? <button className="primary" onClick={close}>Smenani yopish</button> : <button className="primary" onClick={open}>Smenani ochish</button>}</div></div><div className="cash-grid"><Metric icon={<CircleDollarSign/>} label="Qabul qilingan" value={format(revenue)} note="Sotuv va buyurtma avansi"/><Metric icon={<CreditCard/>} label="Kutilayotgan qarz" value={format(debt)} note="Mijozlardan olinadi"/><Metric icon={<ClipboardList/>} label="To'lovli buyurtma" value={`${orders.filter(o => o.paid > 0).length} ta`} note="Bugun va oldingi kunlar"/></div><section className="card money-card"><h2>{shift ? `Ochiq smena · boshlangich: ${format(shift.opening_amount)}` : "Smena ochilmagan"}</h2>{orders.map(o => <div key={o.id}><span>#{o.id} · {o.customer}</span><b>{format(o.paid)} / {format(o.total)}</b></div>)}</section></> }
function Suppliers({suppliers,open}:{suppliers:Supplier[];open:()=>void}) { return <><div className="heading compact"><div><p>SUPPLIERLAR</p><h1>Yetkazib beruvchilar</h1><span>Kirim, to'lov va qarzdorlikni boshqaring.</span></div><button className="primary" onClick={open}>+ Yangi supplier</button></div><section className="customer-grid">{suppliers.map(supplier => <article className="customer" key={supplier.id}><div className="customer-avatar">{supplier.name.slice(0,2).toUpperCase()}</div><div className="customer-info"><b>{supplier.name}</b><span>{supplier.phone || "Telefon kiritilmagan"}</span><small>{supplier.balance ? `Qarz: ${format(supplier.balance)}` : "Qarz yoq"}</small></div><ChevronRight size={18}/></article>)}</section></> }
function Reports({report}:{report:FinanceReport | null}) { return <><div className="heading compact"><div><p>HISOBOTLAR</p><h1>Moliyaviy holat</h1><span>Sotuv, xarajat va qarzdorlikning real ko'rsatkichlari.</span></div></div>{report ? <><div className="metric-grid"><Metric icon={<CircleDollarSign/>} label="Sotuv qiymati" value={format(report.sales_revenue)} note={`Qabul qilingan: ${format(report.sales_paid)}`}/><Metric icon={<CreditCard/>} label="Xarajatlar" value={format(report.expenses)} note="Kassadan chiqim"/><Metric icon={<Archive/>} label="Sof cash flow" value={format(report.net_cash_flow)} note="Kirim minus chiqim"/><Metric icon={<Users/>} label="Mijoz qarzi" value={format(report.customer_debt)} note={`Supplier qarzi: ${format(report.supplier_debt)}`}/></div><section className="card money-card"><h2>Operatsion jamlanma</h2><div><span>Buyurtmalar qiymati</span><b>{format(report.order_value)}</b></div><div><span>Supplierdan kirim qiymati</span><b>{format(report.purchase_value)}</b></div><div><span>Kassa kirimi</span><b>{format(report.cash_in)}</b></div><div><span>Kassa chiqimi</span><b>{format(report.cash_out)}</b></div></section></> : <div className="empty"><LayoutDashboard/><b>Hisobot yuklanmoqda yoki ruxsat yoq</b></div>}</> }
function Modal({title,close,children}:{title:string;close:()=>void;children:React.ReactNode}) { return <div className="modal-bg" onMouseDown={close}><section className="modal" onMouseDown={e => e.stopPropagation()}><div><small>OPTIKA OS</small><h2>{title}</h2></div><button className="close" onClick={close}><X/></button>{children}</section></div> }
function LoginScreen({onSubmit,notice,clearNotice}:{onSubmit:(event:FormEvent<HTMLFormElement>)=>void;notice:Notice | null;clearNotice:()=>void}) { return <main className="login-screen"><section className="login-card"><div className="login-logo"><span>O</span><div>OPTIKA<small>BUSINESS OS</small></div></div><div><p>XUSH KELIBSIZ</p><h1>Tizimga kiring</h1><span>Optika ish jarayonini bir joydan boshqaring.</span></div>{notice && <button className="login-error" onClick={clearNotice}>{notice.text}<X size={15}/></button>}<form className="form" onSubmit={onSubmit}><label>Login<input name="username" required autoFocus placeholder="Loginingizni kiriting"/></label><label>Parol<input name="password" required type="password" placeholder="••••••••"/></label><button className="primary">Kirish</button></form></section></main> }
