import asyncio
import secrets
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
import truststore
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.responses import Response
from pwdlib import PasswordHash
from sqlalchemy import String, func, select, text
from sqlalchemy.orm import Session, joinedload

from .config import settings
from .models import RepairOrder
from .models import TelegramSubscriber
from .models import TelegramLink
from .models import BackupRecord
from .models import Branch, UserBranch
from .models import OpticalCase, EyeExam, Centration, LensConfiguration, LabJob
from .schemas import RepairOrderCreate, RepairOrderUpdate
from .schemas import UserCreate
from .schemas import BranchCreate, UserBranchAssign
from .schemas import OpticalCaseCreate, EyeExamCreate, CentrationCreate, LensConfigurationCreate, LabJobCreate, LabJobUpdate
from .database import Base, engine, get_db
from .models import AuditLog, CashMovement, CashShift, Customer, CustomerPayment, Expense, Order, Prescription, Product, Purchase, PurchaseItem, Sale, SaleItem, SaleReturn, StockMovement, Supplier, SupplierPayment, User
from .schemas import CashShiftClose, CashShiftOpen, CustomerCreate, CustomerPaymentCreate, ExpenseCreate, LoginInput, OrderCreate, PrescriptionCreate, ProductCreate, PurchaseCreate, SaleCreate, SaleReturnCreate, StockReceive, SupplierCreate, SupplierPaymentCreate

truststore.inject_into_ssl()

app = FastAPI(title=settings.app_name, version="0.2.0")
password_hash = PasswordHash.recommended()
bearer = HTTPBearer()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=500)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response


# In-memory brute-force guard for /auth/login (single-process uvicorn).
_login_attempts: dict[str, list[float]] = {}
LOGIN_MAX_ATTEMPTS = 8
LOGIN_WINDOW_SECONDS = 300


def check_login_rate(ip: str) -> None:
    now = time.monotonic()
    hits = [t for t in _login_attempts.get(ip, []) if now - t < LOGIN_WINDOW_SECONDS]
    _login_attempts[ip] = hits
    if len(hits) >= LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Juda ko'p urinish. Bir necha daqiqadan so'ng qayta urining.")


def record_login_failure(ip: str) -> None:
    self = _login_attempts.setdefault(ip, [])
    self.append(time.monotonic())


def ok(data: object) -> dict:
    return {"success": True, "data": data}


def user_data(user: User) -> dict:
    return {"id": user.id, "username": user.username, "role": user.role}


def audit(db: Session, user: User | None, action: str, entity_type: str, entity_id: int | None, summary: str) -> None:
    db.add(AuditLog(user_id=user.id if user else None, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary))


def create_token(user: User) -> str:
    expiry = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": expiry}, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def telegram_call(method: str, payload: dict) -> dict | None:
    if not settings.telegram_bot_token:
        return None
    try:
        response = httpx.post(f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}", json=payload, timeout=15)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return None


def send_telegram(db: Session, customer_id: int, message: str) -> None:
    chat_ids = db.scalars(select(TelegramSubscriber.chat_id).where(TelegramSubscriber.customer_id == customer_id)).all()
    for chat_id in chat_ids:
        send_tg(chat_id, message, MAIN_MENU)


# Mijoz uchun doimiy tugmalar (buyruq yozish shart emas).
MAIN_MENU = {"keyboard": [[{"text": "📦 Buyurtmalarim"}, {"text": "🔧 Ta'mirlash"}], [{"text": "👓 Retseptim"}, {"text": "💳 Qarzim"}], [{"text": "ℹ️ Yordam"}]], "resize_keyboard": True}


def som(value: int | None) -> str:
    return f"{value or 0:,}".replace(",", " ") + " so'm"
CONTACT_KB = {"keyboard": [[{"text": "📱 Telefon raqamni ulashish", "request_contact": True}]], "resize_keyboard": True, "one_time_keyboard": True}


def send_tg(chat_id: str, text: str, keyboard: dict | None = None) -> None:
    payload: dict = {"chat_id": chat_id, "text": text}
    if keyboard is not None:
        payload["reply_markup"] = keyboard
    telegram_call("sendMessage", payload)


def notify_order_created(db: Session, order: Order, name: str) -> None:
    balance = order.total - order.paid
    text = f"✅ Buyurtmangiz qabul qilindi!\n\n🔖 #{order.id} — {name}\nSumma: {som(order.total)} · To'langan: {som(order.paid)}"
    if balance > 0:
        text += f"\nQoldiq to'lov: {som(balance)}"
    text += "\n\nTayyor bo'lganda sizga shu yerda xabar beramiz."
    send_telegram(db, order.customer_id, text)


def phone_digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def find_customer_by_phone(db: Session, phone: str) -> Customer | None:
    tail = phone_digits(phone)[-9:]
    if len(tail) < 9:
        return None
    for customer in db.scalars(select(Customer)).all():
        if phone_digits(customer.phone).endswith(tail):
            return customer
    return None


def link_by_phone(db: Session, chat_id: str, display_name: str | None, phone: str) -> str:
    customer = find_customer_by_phone(db, phone)
    if not customer:
        return "Bu raqam optika bazasida topilmadi. Iltimos, do'konda ro'yxatdan o'tgan telefon raqamingizni ulang yoki optikaga murojaat qiling."
    subscriber = db.scalar(select(TelegramSubscriber).where(TelegramSubscriber.chat_id == chat_id))
    if not subscriber:
        db.add(TelegramSubscriber(chat_id=chat_id, customer=customer, display_name=display_name))
    else:
        subscriber.customer = customer
        subscriber.display_name = display_name
    db.commit()
    return f"Rahmat, {customer.name}! Muvaffaqiyatli ulandingiz. Pastdagi tugmalar bilan buyurtma va ta'mirlash holatini ko'rasiz."


def link_telegram_customer(db: Session, chat_id: str, display_name: str | None, phone: str) -> str:
    normalized = "".join(char for char in phone if char.isdigit() or char == "+")
    customer = db.scalar(select(Customer).where(Customer.phone == normalized))
    if not customer:
        return "Bu telefon raqami bazada topilmadi. Optikadagi raqamingizni tekshirib qayta yuboring."
    subscriber = db.scalar(select(TelegramSubscriber).where(TelegramSubscriber.chat_id == chat_id))
    if not subscriber:
        subscriber = TelegramSubscriber(chat_id=chat_id, customer=customer, display_name=display_name)
        db.add(subscriber)
    else:
        subscriber.customer = customer
        subscriber.display_name = display_name
    db.commit()
    return f"Assalomu alaykum, {customer.name}. Optika OS botiga muvaffaqiyatli bog'landingiz. /buyurtmalar buyrug'i orqali faol buyurtmalaringizni ko'ring."


def link_telegram_by_token(db: Session, chat_id: str, display_name: str | None, token: str) -> str:
    link = db.scalar(select(TelegramLink).options(joinedload(TelegramLink.customer)).where(TelegramLink.token == token))
    if not link or link.used_at or link.expires_at < datetime.utcnow():
        return "Bu bog'lanish havolasi yaroqsiz yoki muddati tugagan. Optikadan yangi havola so'rang."
    subscriber = db.scalar(select(TelegramSubscriber).where(TelegramSubscriber.chat_id == chat_id))
    if not subscriber:
        subscriber = TelegramSubscriber(chat_id=chat_id, customer=link.customer, display_name=display_name)
        db.add(subscriber)
    else:
        subscriber.customer = link.customer
        subscriber.display_name = display_name
    link.used_at = datetime.utcnow()
    db.commit()
    return f"Assalomu alaykum, {link.customer.name}. Optika OS botiga muvaffaqiyatli bog'landingiz. /buyurtmalar orqali buyurtmalaringizni ko'ring."


STATUS_UZ = {"CONFIRMED": "Yangi", "IN_PROGRESS": "Ishlanmoqda", "READY": "Tayyor", "RECEIVED": "Qabul qilindi", "DIAGNOSIS": "Tekshiruvda"}


def orders_reply(db: Session, customer_id: int) -> str:
    orders = db.scalars(select(Order).options(joinedload(Order.product)).where(Order.customer_id == customer_id, Order.status.not_in(["DELIVERED", "CANCELLED"])).order_by(Order.id.desc())).all()
    if not orders:
        return "Sizda hozircha faol buyurtma yo'q."
    lines = []
    for o in orders:
        name = o.item_name or (o.product.name if o.product else "Mahsulot")
        balance = o.total - o.paid
        line = f"🔖 #{o.id} — {name}\nHolati: {STATUS_UZ.get(o.status, o.status)}\nSumma: {som(o.total)} · To'langan: {som(o.paid)}"
        if balance > 0:
            line += f"\nQoldiq to'lov: {som(balance)}"
        lines.append(line)
    return "📦 Buyurtmalaringiz:\n\n" + "\n\n".join(lines)


def repairs_reply(db: Session, customer_id: int) -> str:
    repairs = db.scalars(select(RepairOrder).where(RepairOrder.customer_id == customer_id, RepairOrder.status.not_in(["DELIVERED", "CANCELLED"])).order_by(RepairOrder.id.desc())).all()
    if not repairs:
        return "Sizda hozircha faol ta'mirlash buyurtmasi yo'q."
    lines = []
    for r in repairs:
        line = f"🔧 #{r.id} — {r.device}\nHolati: {STATUS_UZ.get(r.status, r.status)}\nNarx: {som(r.estimated_cost)}"
        if r.estimated_cost - r.paid > 0:
            line += f" · Qoldiq: {som(r.estimated_cost - r.paid)}"
        lines.append(line)
    return "🔧 Ta'mirlash holati:\n\n" + "\n\n".join(lines)


def prescription_reply(db: Session, customer_id: int) -> str:
    p = db.scalar(select(Prescription).where(Prescription.customer_id == customer_id).order_by(Prescription.created_at.desc()))
    if not p:
        return "👓 Sizda hali retsept yo'q. Optikada ko'z tekshiruvidan o'ting."
    parts = ["👓 Oxirgi retseptingiz:\n"]
    parts.append(f"O'ng ko'z (OD): SPH {p.od_sph or '—'} · CYL {p.od_cyl or '—'} · AXIS {p.od_axis if p.od_axis is not None else '—'}")
    parts.append(f"Chap ko'z (OS): SPH {p.os_sph or '—'} · CYL {p.os_cyl or '—'} · AXIS {p.os_axis if p.os_axis is not None else '—'}")
    if p.pd is not None:
        parts.append(f"PD: {p.pd} mm")
    if p.note:
        parts.append(f"Izoh: {p.note}")
    parts.append("\nEslatma: bu ma'lumot shifokor tekshiruvini almashtirmaydi.")
    return "\n".join(parts)


def debt_reply(db: Session, customer_id: int) -> str:
    customer = db.get(Customer, customer_id)
    if not customer or customer.debt <= 0:
        return "💳 Sizda qarzdorlik yo'q. Rahmat!"
    return f"💳 Joriy qarzdorligingiz: {som(customer.debt)}\n\nTo'lovni optikada amalga oshirishingiz mumkin."


def handle_telegram_update(update: dict) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    if not chat_id:
        return
    contact = message.get("contact") or {}
    text_value = str(message.get("text") or "").strip()
    display_name = " ".join(value for value in [message.get("from", {}).get("first_name"), message.get("from", {}).get("last_name")] if value) or None
    with Session(engine) as db:
        subscriber = db.scalar(select(TelegramSubscriber).where(TelegramSubscriber.chat_id == chat_id))
        linked_id = subscriber.customer_id if subscriber else None

        # 1) Telefon raqam ulashildi — o'zi bog'lanadi (havola shart emas)
        if contact.get("phone_number"):
            send_tg(chat_id, link_by_phone(db, chat_id, display_name, contact["phone_number"]), MAIN_MENU)
            return

        # 2) Do'kondan kelgan shaxsiy havola (/start link_...)
        if text_value.startswith("/start"):
            payload = text_value.removeprefix("/start").strip()
            if payload.startswith("link_"):
                send_tg(chat_id, link_telegram_by_token(db, chat_id, display_name, payload.removeprefix("link_")), MAIN_MENU)
            elif linked_id:
                send_tg(chat_id, "Xush kelibsiz! Pastdagi tugmalar bilan buyurtma va ta'mirlash holatingizni ko'ring.", MAIN_MENU)
            else:
                send_tg(chat_id, "Assalomu alaykum! Optika buyurtmalaringizni shu botda kuzatasiz.\n\nBoshlash uchun pastdagi \"📱 Telefon raqamni ulashish\" tugmasini bosing — optikadagi raqamingiz orqali avtomatik ulanasiz.", CONTACT_KB)
            return

        # 3) Tugmalar / buyruqlar
        if not linked_id:
            send_tg(chat_id, "Avval telefon raqamingizni ulang. Pastdagi tugmani bosing.", CONTACT_KB)
            return
        if "Buyurtma" in text_value or text_value.startswith("/buyurtmalar"):
            send_tg(chat_id, orders_reply(db, linked_id), MAIN_MENU)
        elif "mirlash" in text_value or "Ta'mir" in text_value or text_value.startswith("/servis"):
            send_tg(chat_id, repairs_reply(db, linked_id), MAIN_MENU)
        elif "Retsept" in text_value or "Retseptim" in text_value:
            send_tg(chat_id, prescription_reply(db, linked_id), MAIN_MENU)
        elif "Qarz" in text_value:
            send_tg(chat_id, debt_reply(db, linked_id), MAIN_MENU)
        else:
            send_tg(chat_id, "Nima ko'rmoqchisiz? Pastdagi tugmalardan birini tanlang:\n\n📦 Buyurtmalarim — faol buyurtmalar\n🔧 Ta'mirlash — servis holati\n👓 Retseptim — ko'z o'lchovlaringiz\n💳 Qarzim — qarzdorlik", MAIN_MENU)


async def telegram_polling() -> None:
    offset = 0
    while True:
        payload = {"timeout": 25, "offset": offset}
        response = await asyncio.to_thread(telegram_call, "getUpdates", payload)
        if response and response.get("ok"):
            for update in response.get("result", []):
                offset = int(update["update_id"]) + 1
                await asyncio.to_thread(handle_telegram_update, update)
        await asyncio.sleep(1)


def dispatch_prescription_reminders() -> None:
    with Session(engine) as db:
        now = datetime.utcnow()
        due = db.scalars(select(Prescription).options(joinedload(Prescription.customer)).where(Prescription.reminder_at.is_not(None), Prescription.reminder_at <= now, Prescription.reminder_sent.is_(False))).all()
        for presc in due:
            message = f"Optika OS: hurmatli {presc.customer.name}, ko'z tekshiruvi/retsept yangilash vaqti keldi. Iltimos, optikaga tashrif buyuring."
            send_telegram(db, presc.customer_id, message)
            presc.reminder_sent = True
        if due:
            db.commit()


async def reminder_scheduler() -> None:
    while True:
        try:
            await asyncio.to_thread(dispatch_prescription_reminders)
        except Exception:
            pass
        await asyncio.sleep(300)


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Yaroqsiz yoki muddati tugagan token")
    user = db.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Foydalanuvchi faol emas")
    return user


def require_roles(*roles: str):
    def check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu amal uchun ruxsat yoq")
        return user
    return check


def customer_data(customer: Customer) -> dict:
    return {"id": customer.id, "name": customer.name, "phone": customer.phone, "debt": customer.debt}


def product_data(product: Product) -> dict:
    return {"id": product.id, "name": product.name, "brand": product.brand, "category": product.category, "sale_price": product.sale_price, "stock": product.stock, "minimum_stock": product.minimum_stock}


def prescription_data(prescription: Prescription) -> dict:
    return {"id": prescription.id, "customer_id": prescription.customer_id, "od_sph": prescription.od_sph, "od_cyl": prescription.od_cyl, "od_axis": prescription.od_axis, "os_sph": prescription.os_sph, "os_cyl": prescription.os_cyl, "os_axis": prescription.os_axis, "pd": prescription.pd, "note": prescription.note, "reminder_at": prescription.reminder_at, "created_at": prescription.created_at}


def supplier_data(supplier: Supplier) -> dict:
    return {"id": supplier.id, "name": supplier.name, "phone": supplier.phone, "balance": supplier.balance}


def cash_shift_data(shift: CashShift) -> dict:
    return {"id": shift.id, "opening_amount": shift.opening_amount, "expected_amount": shift.expected_amount, "actual_amount": shift.actual_amount, "difference": (shift.actual_amount - shift.expected_amount) if shift.actual_amount is not None and shift.expected_amount is not None else None, "status": shift.status, "opened_at": shift.opened_at, "closed_at": shift.closed_at}


def open_shift(db: Session) -> CashShift | None:
    return db.scalar(select(CashShift).where(CashShift.status == "OPEN").order_by(CashShift.opened_at.desc()))


def stock_movement(db: Session, product: Product, quantity: int, movement_type: str, reference_type: str, reference_id: int | None, note: str | None = None) -> None:
    db.add(StockMovement(product_id=product.id, quantity=quantity, movement_type=movement_type, reference_type=reference_type, reference_id=reference_id, note=note))


def order_data(order: Order) -> dict:
    return {"id": order.id, "customer": customer_data(order.customer), "product": product_data(order.product) if order.product else None, "item_name": order.item_name, "total": order.total, "paid": order.paid, "balance": order.total - order.paid, "status": order.status, "created_at": order.created_at}


def repair_data(repair: RepairOrder) -> dict:
    return {"id": repair.id, "customer": customer_data(repair.customer), "device": repair.device, "issue": repair.issue, "estimated_cost": repair.estimated_cost, "paid": repair.paid, "balance": repair.estimated_cost - repair.paid, "status": repair.status, "technician_note": repair.technician_note, "due_date": repair.due_date, "created_at": repair.created_at}


def optical_case_data(db: Session, item: OpticalCase) -> dict:
    exam = db.scalar(select(EyeExam).where(EyeExam.optical_case_id == item.id))
    centration = db.scalar(select(Centration).where(Centration.optical_case_id == item.id))
    lens = db.scalar(select(LensConfiguration).where(LensConfiguration.optical_case_id == item.id))
    lab = db.scalar(select(LabJob).where(LabJob.optical_case_id == item.id))
    return {"id": item.id, "customer": customer_data(item.customer), "frame": product_data(item.frame_product) if item.frame_product else None, "chief_complaint": item.chief_complaint, "status": item.status, "created_at": item.created_at, "exam": None if not exam else {"od_sph": exam.od_sph, "od_cyl": exam.od_cyl, "od_axis": exam.od_axis, "os_sph": exam.os_sph, "os_cyl": exam.os_cyl, "os_axis": exam.os_axis, "add_power": exam.add_power, "prism": exam.prism, "distance_va": exam.distance_va, "near_va": exam.near_va, "clinical_note": exam.clinical_note, "referral_required": exam.referral_required}, "centration": None if not centration else {"pd_right": centration.pd_right, "pd_left": centration.pd_left, "fitting_height_right": centration.fitting_height_right, "fitting_height_left": centration.fitting_height_left, "vertex_distance": centration.vertex_distance, "pantoscopic_tilt": centration.pantoscopic_tilt, "wrap_angle": centration.wrap_angle}, "lens": None if not lens else {"lens_design": lens.lens_design, "material_index": lens.material_index, "coating": lens.coating, "photochromic": lens.photochromic, "lab_note": lens.lab_note}, "lab": None if not lab else {"status": lab.status, "laboratory": lab.laboratory, "job_reference": lab.job_reference, "qc_note": lab.qc_note, "sent_at": lab.sent_at, "received_at": lab.received_at}}


def seed(db: Session) -> None:
    if not db.scalar(select(func.count(Branch.id))):
        db.add(Branch(name="Chilonzor filiali", code="CHIL-01", address="Toshkent, Chilonzor"))
        db.commit()
    if not db.scalar(select(func.count(User.id))):
        db.add_all([
            User(username="admin", password_hash=password_hash.hash("admin123"), role="OWNER"),
            User(username="sotuvchi", password_hash=password_hash.hash("seller123"), role="SELLER"),
        ])
        db.commit()
    if not db.scalar(select(User).where(User.username == "optometrist")):
        db.add(User(username="optometrist", password_hash=password_hash.hash("optometrist123"), role="OPTOMETRIST"))
        db.commit()
    if not db.scalar(select(func.count(Supplier.id))):
        db.add_all([Supplier(name="Optika Distribyutor", phone="+998901112233"), Supplier(name="Essilor Uzbekistan", phone="+998935556677")])
        db.commit()
    if db.scalar(select(func.count(Product.id))):
        return
    customers = [Customer(name="Aziz Akbarov", phone="+998901234567", debt=500000), Customer(name="Madina Karimova", phone="+998935552020")]
    products = [
        Product(name="RB 3447 Round", brand="Ray-Ban", category="FRAME", sale_price=850000, stock=6, minimum_stock=3),
        Product(name="Blue Cut 1.60", brand="Essilor", category="LENS", sale_price=300000, stock=18, minimum_stock=8),
        Product(name="Classic Black Case", brand="Optika", category="ACCESSORY", sale_price=50000, stock=4, minimum_stock=5),
    ]
    db.add_all(customers + products)
    db.commit()


@app.on_event("startup")
async def startup() -> None:
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        seed(db)
    if settings.telegram_bot_token:
        telegram_call("setMyCommands", {"commands": [
            {"command": "start", "description": "Boshlash / ulanish"},
            {"command": "buyurtmalar", "description": "Faol buyurtmalarim"},
            {"command": "servis", "description": "Ta'mirlash holati"},
        ]})
        telegram_call("setChatMenuButton", {"menu_button": {"type": "commands"}})
        asyncio.create_task(telegram_polling())
        asyncio.create_task(reminder_scheduler())


@app.get("/health")
def health() -> dict:
    return ok({"status": "healthy", "time": datetime.now(timezone.utc)})


@app.get("/health/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database ulanmagan")
    return ok({"status": "ready"})


@app.get("/api/v1/backups")
def list_backups(db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER"))) -> dict:
    rows = db.scalars(select(BackupRecord).order_by(BackupRecord.created_at.desc()).limit(50))
    return ok([{"id": row.id, "filename": row.filename, "size_bytes": row.size_bytes, "created_at": row.created_at} for row in rows])


@app.post("/api/v1/backups", status_code=status.HTTP_201_CREATED)
def create_backup(db: Session = Depends(get_db), user: User = Depends(require_roles("OWNER"))) -> dict:
    if not settings.database_url.startswith("sqlite:///"):
        raise HTTPException(501, "PostgreSQL backup uchun serverdagi pg_dump integratsiyasi kerak")
    source = Path(settings.database_url.removeprefix("sqlite:///"))
    if not source.exists():
        raise HTTPException(404, "Lokal ma'lumotlar bazasi topilmadi")
    backup_dir = Path("backups")
    backup_dir.mkdir(exist_ok=True)
    filename = f"optika-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.db"
    target = backup_dir / filename
    shutil.copy2(source, target)
    record = BackupRecord(filename=filename, size_bytes=target.stat().st_size, created_by_id=user.id)
    db.add(record); db.flush(); audit(db, user, "CREATE", "BACKUP", record.id, f"Backup yaratildi: {filename}"); db.commit(); db.refresh(record)
    return ok({"id": record.id, "filename": record.filename, "size_bytes": record.size_bytes, "created_at": record.created_at})


@app.post("/api/v1/auth/login")
def login(payload: LoginInput, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else "unknown"
    check_login_rate(ip)
    user = db.scalar(select(User).where(User.username == payload.username.strip().lower()))
    if not user or not password_hash.verify(payload.password, user.password_hash):
        record_login_failure(ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login yoki parol notogri")
    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Foydalanuvchi faol emas")
    return ok({"access_token": create_token(user), "token_type": "bearer", "user": user_data(user)})


@app.get("/api/v1/auth/me")
def me(user: User = Depends(current_user)) -> dict:
    return ok(user_data(user))


@app.get("/api/v1/bootstrap")
def bootstrap(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    customers = list(db.scalars(select(Customer).order_by(Customer.id.desc())))
    products = list(db.scalars(select(Product).order_by(Product.id.desc())))
    orders = list(db.scalars(select(Order).options(joinedload(Order.customer), joinedload(Order.product)).order_by(Order.id.desc())))
    suppliers = list(db.scalars(select(Supplier).order_by(Supplier.name)))
    return ok({"customers": [customer_data(c) for c in customers], "products": [product_data(p) for p in products], "orders": [order_data(o) for o in orders], "suppliers": [supplier_data(s) for s in suppliers], "cash_shift": cash_shift_data(open_shift(db)) if open_shift(db) else None})


@app.get("/api/v1/search")
def global_search(q: str, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    needle = q.strip()
    if len(needle) < 2:
        return ok([])
    customers = db.scalars(select(Customer).where(Customer.name.ilike(f"%{needle}%") | Customer.phone.ilike(f"%{needle}%")).limit(5))
    products = db.scalars(select(Product).where(Product.name.ilike(f"%{needle}%") | Product.brand.ilike(f"%{needle}%")).limit(5))
    orders = db.scalars(select(Order).options(joinedload(Order.customer)).where(Order.id.cast(String).ilike(f"%{needle}%")).limit(5))
    result = ([{"type": "customer", "id": row.id, "title": row.name, "subtitle": row.phone} for row in customers] + [{"type": "product", "id": row.id, "title": row.name, "subtitle": f"{row.brand} · {row.stock} dona"} for row in products] + [{"type": "order", "id": row.id, "title": f"Buyurtma #{row.id}", "subtitle": row.customer.name} for row in orders])
    return ok(result)


@app.get("/api/v1/notifications")
def notifications(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    ready = list(db.scalars(select(Order).options(joinedload(Order.customer)).where(Order.status == "READY").order_by(Order.id.desc()).limit(10)))
    low = list(db.scalars(select(Product).where(Product.stock <= Product.minimum_stock).order_by(Product.stock).limit(10)))
    now = datetime.utcnow()
    due = list(db.scalars(select(Prescription).options(joinedload(Prescription.customer)).where(Prescription.reminder_at.is_not(None), Prescription.reminder_at <= now, Prescription.reminder_at >= now - timedelta(days=60)).order_by(Prescription.reminder_at.desc()).limit(10)))
    result = ([{"type": "ORDER_READY", "severity": "success", "title": f"Buyurtma #{order.id} tayyor", "message": f"{order.customer.name}ga topshirish kerak", "entity_id": order.id} for order in ready] + [{"type": "PRESCRIPTION_REMINDER", "severity": "warning", "title": f"{presc.customer.name}ni tekshiruvga chaqiring", "message": f"Retsept eslatmasi vaqti keldi ({presc.reminder_at.strftime('%d.%m.%Y')})", "entity_id": presc.customer_id} for presc in due] + [{"type": "LOW_STOCK", "severity": "warning", "title": f"{product.name} kam qoldi", "message": f"Qoldiq: {product.stock}, minimum: {product.minimum_stock}", "entity_id": product.id} for product in low])
    return ok(result)


@app.get("/api/v1/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER"))) -> dict:
    rows = db.scalars(select(User).order_by(User.id))
    return ok([{**user_data(row), "active": row.active} for row in rows])


@app.post("/api/v1/users", status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER"))) -> dict:
    username = payload.username.strip().lower()
    if db.scalar(select(User).where(User.username == username)):
        raise HTTPException(409, "Bu login avval mavjud")
    user = User(username=username, password_hash=password_hash.hash(payload.password), role=payload.role)
    db.add(user); db.flush(); audit(db, _, "CREATE", "USER", user.id, f"Xodim yaratildi: {user.username}"); db.commit(); db.refresh(user)
    return ok({**user_data(user), "active": user.active})


@app.get("/api/v1/branches")
def list_branches(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    rows = db.scalars(select(Branch).order_by(Branch.name))
    return ok([{"id": row.id, "name": row.name, "code": row.code, "address": row.address, "active": row.active, "members": db.scalar(select(func.count(UserBranch.id)).where(UserBranch.branch_id == row.id)) or 0} for row in rows])


@app.post("/api/v1/branches", status_code=status.HTTP_201_CREATED)
def create_branch(payload: BranchCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("OWNER"))) -> dict:
    code = payload.code.strip().upper()
    if db.scalar(select(Branch).where((Branch.name == payload.name.strip()) | (Branch.code == code))):
        raise HTTPException(409, "Filial nomi yoki kodi avval mavjud")
    branch = Branch(name=payload.name.strip(), code=code, address=payload.address)
    db.add(branch); db.flush(); audit(db, user, "CREATE", "BRANCH", branch.id, f"Filial yaratildi: {branch.name}"); db.commit(); db.refresh(branch)
    return ok({"id": branch.id, "name": branch.name, "code": branch.code, "address": branch.address, "active": branch.active, "members": 0})


@app.post("/api/v1/branches/{branch_id}/members", status_code=status.HTTP_201_CREATED)
def add_branch_member(branch_id: int, payload: UserBranchAssign, db: Session = Depends(get_db), user: User = Depends(require_roles("OWNER"))) -> dict:
    branch = db.get(Branch, branch_id)
    member = db.get(User, payload.user_id)
    if not branch or not member:
        raise HTTPException(404, "Filial yoki foydalanuvchi topilmadi")
    if db.scalar(select(UserBranch).where(UserBranch.branch_id == branch.id, UserBranch.user_id == member.id)):
        raise HTTPException(409, "Xodim bu filialga allaqachon biriktirilgan")
    db.add(UserBranch(branch=branch, user=member)); audit(db, user, "ASSIGN", "BRANCH", branch.id, f"{member.username} filialga biriktirildi"); db.commit()
    return ok({"branch_id": branch.id, "user": user_data(member)})


@app.get("/api/v1/repairs")
def list_repairs(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    rows = db.scalars(select(RepairOrder).options(joinedload(RepairOrder.customer)).order_by(RepairOrder.id.desc()))
    return ok([repair_data(row) for row in rows])


@app.post("/api/v1/repairs", status_code=status.HTTP_201_CREATED)
def create_repair(payload: RepairOrderCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER", "SELLER"))) -> dict:
    customer = db.get(Customer, payload.customer_id)
    if not customer:
        raise HTTPException(404, "Mijoz topilmadi")
    if payload.paid > payload.estimated_cost:
        raise HTTPException(422, "Avans xizmat qiymatidan katta")
    repair = RepairOrder(customer=customer, device=payload.device.strip(), issue=payload.issue.strip(), estimated_cost=payload.estimated_cost, paid=payload.paid, due_date=payload.due_date)
    db.add(repair); db.flush()
    if repair.paid:
        if shift := open_shift(db):
            db.add(CashMovement(cash_shift_id=shift.id, movement_type="REPAIR_PAYMENT", amount=repair.paid, reference_type="REPAIR", reference_id=repair.id, note=f"Ta'mir #{repair.id}"))
    customer.debt += repair.estimated_cost - repair.paid
    audit(db, _, "CREATE", "REPAIR", repair.id, f"Ta'mir qabul qilindi: {repair.device}")
    db.commit(); db.refresh(repair)
    return ok(repair_data(repair))


@app.post("/api/v1/repairs/{repair_id}/status")
def update_repair_status(repair_id: int, payload: RepairOrderUpdate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER", "SELLER"))) -> dict:
    repair = db.scalar(select(RepairOrder).options(joinedload(RepairOrder.customer)).where(RepairOrder.id == repair_id))
    if not repair:
        raise HTTPException(404, "Ta'mirlash buyurtmasi topilmadi")
    if repair.status in {"DELIVERED", "CANCELLED"}:
        raise HTTPException(409, "Yopilgan buyurtma o'zgartirilmaydi")
    repair.status = payload.status
    if payload.technician_note is not None:
        repair.technician_note = payload.technician_note.strip() or None
    audit(db, _, "UPDATE", "REPAIR", repair.id, f"Ta'mir holati: {repair.status}")
    db.commit(); db.refresh(repair)
    if repair.status == "READY":
        send_telegram(db, repair.customer_id, f"Optika OS: servis buyurtmangiz #{repair.id} ({repair.device}) tayyor. Uni optikadan olib ketishingiz mumkin.")
    return ok(repair_data(repair))


@app.get("/api/v1/optical-cases")
def list_optical_cases(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    rows = db.scalars(select(OpticalCase).options(joinedload(OpticalCase.customer), joinedload(OpticalCase.frame_product)).order_by(OpticalCase.id.desc()))
    return ok([optical_case_data(db, item) for item in rows])


@app.post("/api/v1/optical-cases", status_code=status.HTTP_201_CREATED)
def create_optical_case(payload: OpticalCaseCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("OWNER", "MANAGER", "SELLER"))) -> dict:
    customer = db.get(Customer, payload.customer_id)
    if not customer:
        raise HTTPException(404, "Mijoz topilmadi")
    frame = db.get(Product, payload.frame_product_id) if payload.frame_product_id else None
    if payload.frame_product_id and not frame:
        raise HTTPException(404, "Ramka topilmadi")
    if frame and frame.category != "FRAME":
        raise HTTPException(422, "Optik karta uchun faqat rama tanlanadi")
    item = OpticalCase(customer=customer, frame_product=frame, chief_complaint=payload.chief_complaint, created_by_id=user.id, status="FRAME_SELECTED" if frame else "INTAKE")
    db.add(item); db.flush(); audit(db, user, "CREATE", "OPTICAL_CASE", item.id, "Professional optik karta yaratildi"); db.commit(); db.refresh(item)
    db.refresh(item, attribute_names=["customer", "frame_product"])
    return ok(optical_case_data(db, item))


@app.post("/api/v1/optical-cases/{case_id}/exam")
def save_eye_exam(case_id: int, payload: EyeExamCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("OWNER", "MANAGER", "OPTOMETRIST"))) -> dict:
    item = db.scalar(select(OpticalCase).options(joinedload(OpticalCase.customer), joinedload(OpticalCase.frame_product)).where(OpticalCase.id == case_id))
    if not item:
        raise HTTPException(404, "Optik karta topilmadi")
    exam = db.scalar(select(EyeExam).where(EyeExam.optical_case_id == case_id))
    if exam:
        for field, value in payload.model_dump().items():
            setattr(exam, field, value)
        exam.performed_by_id = user.id
    else:
        exam = EyeExam(optical_case_id=case_id, performed_by_id=user.id, **payload.model_dump())
        db.add(exam)
    item.status = "EXAM_COMPLETED" if not payload.referral_required else "REFERRAL_REQUIRED"
    audit(db, user, "SAVE", "EYE_EXAM", case_id, "Ko'z tekshiruvi yakunlandi")
    db.commit(); return ok(optical_case_data(db, item))


@app.post("/api/v1/optical-cases/{case_id}/centration")
def save_centration(case_id: int, payload: CentrationCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("OWNER", "MANAGER", "OPTOMETRIST", "SELLER"))) -> dict:
    item = db.scalar(select(OpticalCase).options(joinedload(OpticalCase.customer), joinedload(OpticalCase.frame_product)).where(OpticalCase.id == case_id))
    if not item:
        raise HTTPException(404, "Optik karta topilmadi")
    if not item.frame_product_id:
        raise HTTPException(422, "Centrationdan oldin rama tanlanishi kerak")
    if not db.scalar(select(EyeExam).where(EyeExam.optical_case_id == case_id)):
        raise HTTPException(422, "Centrationdan oldin ko'z tekshiruvi kiritilishi kerak")
    row = db.scalar(select(Centration).where(Centration.optical_case_id == case_id))
    if row:
        for field, value in payload.model_dump().items():
            setattr(row, field, value)
        row.measured_by_id = user.id
    else:
        db.add(Centration(optical_case_id=case_id, measured_by_id=user.id, **payload.model_dump()))
    item.status = "CENTRATION_COMPLETED"; audit(db, user, "SAVE", "CENTRATION", case_id, "Centration o'lchovlari saqlandi"); db.commit()
    return ok(optical_case_data(db, item))


@app.post("/api/v1/optical-cases/{case_id}/lens")
def save_lens_configuration(case_id: int, payload: LensConfigurationCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("OWNER", "MANAGER", "OPTOMETRIST", "SELLER"))) -> dict:
    item = db.scalar(select(OpticalCase).options(joinedload(OpticalCase.customer), joinedload(OpticalCase.frame_product)).where(OpticalCase.id == case_id))
    if not item:
        raise HTTPException(404, "Optik karta topilmadi")
    if not db.scalar(select(Centration).where(Centration.optical_case_id == case_id)):
        raise HTTPException(422, "Linza konfiguratsiyasidan oldin centration kerak")
    row = db.scalar(select(LensConfiguration).where(LensConfiguration.optical_case_id == case_id))
    if row:
        for field, value in payload.model_dump().items():
            setattr(row, field, value)
        row.selected_by_id = user.id
    else:
        db.add(LensConfiguration(optical_case_id=case_id, selected_by_id=user.id, **payload.model_dump()))
    item.status = "LENS_CONFIGURED"; audit(db, user, "SAVE", "LENS_CONFIGURATION", case_id, "Linza konfiguratsiyasi saqlandi"); db.commit()
    return ok(optical_case_data(db, item))


@app.post("/api/v1/optical-cases/{case_id}/lab")
def create_lab_job(case_id: int, payload: LabJobCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("OWNER", "MANAGER", "LAB_QC"))) -> dict:
    item = db.scalar(select(OpticalCase).options(joinedload(OpticalCase.customer), joinedload(OpticalCase.frame_product)).where(OpticalCase.id == case_id))
    if not item:
        raise HTTPException(404, "Optik karta topilmadi")
    if not db.scalar(select(LensConfiguration).where(LensConfiguration.optical_case_id == case_id)):
        raise HTTPException(422, "Laboratoriyaga yuborishdan oldin linza konfiguratsiyasi kerak")
    if db.scalar(select(LabJob).where(LabJob.optical_case_id == case_id)):
        raise HTTPException(409, "Laboratoriya ishi allaqachon yaratilgan")
    db.add(LabJob(optical_case_id=case_id, laboratory=payload.laboratory, job_reference=payload.job_reference)); item.status = "LAB_SENT"
    audit(db, user, "CREATE", "LAB_JOB", case_id, "Laboratoriyaga yuborildi"); db.commit()
    return ok(optical_case_data(db, item))


@app.post("/api/v1/optical-cases/{case_id}/lab/status")
def update_lab_job(case_id: int, payload: LabJobUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles("OWNER", "MANAGER", "LAB_QC"))) -> dict:
    item = db.scalar(select(OpticalCase).options(joinedload(OpticalCase.customer), joinedload(OpticalCase.frame_product)).where(OpticalCase.id == case_id))
    job = db.scalar(select(LabJob).where(LabJob.optical_case_id == case_id))
    if not item or not job:
        raise HTTPException(404, "Laboratoriya ishi topilmadi")
    job.status = payload.status; job.qc_note = payload.qc_note
    if payload.status in {"RECEIVED", "QC_PASSED", "QC_FAILED", "READY"}:
        job.received_at = datetime.utcnow()
    item.status = payload.status
    if payload.status == "READY":
        send_telegram(db, item.customer_id, f"Optika OS: ko'zoynak buyurtmangiz #{item.id} tayyor. Uni optikadan olib ketishingiz mumkin.")
    audit(db, user, "UPDATE", "LAB_JOB", case_id, f"Lab/QC holati: {payload.status}"); db.commit()
    return ok(optical_case_data(db, item))


@app.post("/api/v1/customers/{customer_id}/telegram-link")
def create_telegram_link(customer_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER", "SELLER"))) -> dict:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "Mijoz topilmadi")
    if not settings.telegram_bot_username:
        raise HTTPException(503, "Telegram bot username sozlanmagan")
    token = secrets.token_urlsafe(18).replace("-", "_")
    link = TelegramLink(token=token, customer=customer, expires_at=datetime.utcnow() + timedelta(days=7))
    db.add(link); db.commit()
    return ok({"customer": customer_data(customer), "url": f"https://t.me/{settings.telegram_bot_username}?start=link_{token}", "expires_at": link.expires_at})


@app.get("/api/v1/customers/{customer_id}/optical-advice")
def optical_advice(customer_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "Mijoz topilmadi")
    prescription = db.scalar(select(Prescription).where(Prescription.customer_id == customer_id).order_by(Prescription.created_at.desc()))
    if not prescription:
        return ok({"customer": customer_data(customer), "has_prescription": False, "recommendations": ["Avval retsept ma'lumotlarini kiriting."], "warning": "Tavsiyalar shifokor retseptini almashtirmaydi."})
    recommendations: list[str] = []
    warning = "Tavsiyalar shifokor retseptini almashtirmaydi. Yakuniy tanlovni mutaxassis tasdiqlaydi."
    values = [value for value in (prescription.od_sph, prescription.os_sph, prescription.od_cyl, prescription.os_cyl) if value]
    try:
        strength = max(abs(float(value)) for value in values) if values else 0
    except ValueError:
        strength = 0
    if strength >= 4:
        recommendations.append("Yuqori dioptriya: yupqaroq high-index linza va kichikroq ramka ko'rib chiqilsin.")
    elif strength >= 1.5:
        recommendations.append("O'rta dioptriya: 1.60 indeksli yupqalashtirilgan linza tavsiya etiladi.")
    else:
        recommendations.append("Standart indeksli linza ko'p holatda yetarli bo'ladi.")
    if prescription.od_cyl or prescription.os_cyl:
        recommendations.append("Astigmatizm bor: axis va PD qiymatlarini buyurtmadan oldin qayta tekshiring.")
    if prescription.pd is None:
        recommendations.append("PD qiymati kiritilmagan — markazlashtirish uchun o'lchov oling.")
    recommendations.append("Qoplama va fotoxrom tanlovi faqat mijozning ish/sharoiti, mutaxassis tavsiyasi va aniq mahsulot xususiyatiga qarab belgilanadi.")
    return ok({"customer": customer_data(customer), "has_prescription": True, "recommendations": recommendations, "warning": warning, "prescription": prescription_data(prescription)})


@app.get("/api/v1/customers")
def list_customers(q: str = "", db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    query = select(Customer).order_by(Customer.id.desc())
    if q:
        query = query.where(Customer.name.ilike(f"%{q}%") | Customer.phone.ilike(f"%{q}%"))
    return ok([customer_data(c) for c in db.scalars(query)])


@app.post("/api/v1/customers", status_code=status.HTTP_201_CREATED)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER", "SELLER"))) -> dict:
    normalized = "".join(char for char in payload.phone if char.isdigit() or char == "+")
    if db.scalar(select(Customer).where(Customer.phone == normalized)):
        raise HTTPException(409, "Bu telefon raqami avval mavjud")
    customer = Customer(name=payload.name.strip(), phone=normalized)
    db.add(customer); db.flush(); audit(db, _, "CREATE", "CUSTOMER", customer.id, f"Mijoz yaratildi: {customer.name}"); db.commit(); db.refresh(customer)
    return ok(customer_data(customer))


@app.post("/api/v1/customers/{customer_id}/payments", status_code=status.HTTP_201_CREATED)
def pay_customer_debt(customer_id: int, payload: CustomerPaymentCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER", "SELLER"))) -> dict:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "Mijoz topilmadi")
    if payload.amount > customer.debt:
        raise HTTPException(422, "Tolov mijoz qarzidan katta")
    payment = CustomerPayment(customer=customer, amount=payload.amount, comment=payload.comment)
    db.add(payment); db.flush()
    customer.debt -= payment.amount
    if shift := open_shift(db):
        db.add(CashMovement(cash_shift_id=shift.id, movement_type="CUSTOMER_DEBT_PAYMENT", amount=payment.amount, reference_type="CUSTOMER_PAYMENT", reference_id=payment.id, note=payload.comment))
    audit(db, _, "PAY", "CUSTOMER", customer.id, f"Mijozdan qarz tolov: {payment.amount} som")
    db.commit(); db.refresh(payment)
    return ok({"id": payment.id, "customer": customer_data(customer), "amount": payment.amount, "comment": payment.comment, "created_at": payment.created_at})


@app.get("/api/v1/customers/{customer_id}/prescriptions")
def list_prescriptions(customer_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    if not db.get(Customer, customer_id):
        raise HTTPException(404, "Mijoz topilmadi")
    prescriptions = db.scalars(select(Prescription).where(Prescription.customer_id == customer_id).order_by(Prescription.created_at.desc()))
    return ok([prescription_data(prescription) for prescription in prescriptions])


@app.post("/api/v1/customers/{customer_id}/prescriptions", status_code=status.HTTP_201_CREATED)
def create_prescription(customer_id: int, payload: PrescriptionCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER", "OPTOMETRIST"))) -> dict:
    if not db.get(Customer, customer_id):
        raise HTTPException(404, "Mijoz topilmadi")
    prescription = Prescription(customer_id=customer_id, **payload.model_dump())
    db.add(prescription); db.flush(); audit(db, _, "CREATE", "PRESCRIPTION", prescription.id, f"Mijoz #{customer_id} uchun retsept yaratildi"); db.commit(); db.refresh(prescription)
    return ok(prescription_data(prescription))


@app.get("/api/v1/products")
def list_products(q: str = "", low_stock: bool = False, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    query = select(Product).order_by(Product.name)
    if q:
        query = query.where(Product.name.ilike(f"%{q}%") | Product.brand.ilike(f"%{q}%"))
    if low_stock:
        query = query.where(Product.stock <= Product.minimum_stock)
    return ok([product_data(p) for p in db.scalars(query)])


@app.post("/api/v1/products", status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER"))) -> dict:
    product = Product(**payload.model_dump())
    db.add(product); db.flush(); audit(db, _, "CREATE", "PRODUCT", product.id, f"Mahsulot yaratildi: {product.name}"); db.commit(); db.refresh(product)
    return ok(product_data(product))


@app.post("/api/v1/inventory/{product_id}/receive")
def receive_stock(product_id: int, payload: StockReceive, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER"))) -> dict:
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404, "Mahsulot topilmadi")
    product.stock += payload.quantity
    stock_movement(db, product, payload.quantity, "MANUAL_RECEIVE", "INVENTORY", product.id, "Omborga kirim")
    audit(db, _, "RECEIVE_STOCK", "PRODUCT", product.id, f"{payload.quantity} dona kirim qilindi")
    db.commit(); db.refresh(product)
    return ok(product_data(product))


@app.get("/api/v1/orders")
def list_orders(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    rows = db.scalars(select(Order).options(joinedload(Order.customer), joinedload(Order.product)).order_by(Order.id.desc()))
    return ok([order_data(order) for order in rows])


@app.post("/api/v1/orders", status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER", "SELLER"))) -> dict:
    customer = db.get(Customer, payload.customer_id)
    if not customer:
        raise HTTPException(404, "Mijoz topilmadi")
    if payload.product_id is not None:
        product = db.get(Product, payload.product_id)
        if not product:
            raise HTTPException(404, "Mahsulot topilmadi")
        if product.stock < 1:
            raise HTTPException(409, "Omborda mahsulot qolmagan")
        if payload.paid > product.sale_price:
            raise HTTPException(422, "Avans umumiy summadan katta bo'lishi mumkin emas")
        product.stock -= 1
        customer.debt += product.sale_price - payload.paid
        order = Order(customer=customer, product=product, item_name=product.name, total=product.sale_price, paid=payload.paid, status="CONFIRMED")
        db.add(order); db.flush(); stock_movement(db, product, -1, "ORDER_RESERVE", "ORDER", order.id, "Buyurtma uchun rezerv"); audit(db, _, "CREATE", "ORDER", order.id, f"Buyurtma yaratildi: {product.name}"); db.commit(); db.refresh(order)
        db.refresh(order, attribute_names=["customer", "product"])
        notify_order_created(db, order, product.name)
        return ok(order_data(order))
    item_name = (payload.item_name or "").strip()
    if not item_name:
        raise HTTPException(422, "Mahsulot nomini kiriting yoki ro'yxatdan tanlang")
    total = payload.total or 0
    if payload.paid > total:
        raise HTTPException(422, "Avans umumiy summadan katta bo'lishi mumkin emas")
    customer.debt += total - payload.paid
    order = Order(customer=customer, product=None, item_name=item_name, total=total, paid=payload.paid, status="CONFIRMED")
    db.add(order); db.flush(); audit(db, _, "CREATE", "ORDER", order.id, f"Qo'lda buyurtma yaratildi: {item_name}"); db.commit(); db.refresh(order)
    db.refresh(order, attribute_names=["customer"])
    notify_order_created(db, order, item_name)
    return ok(order_data(order))


@app.post("/api/v1/orders/{order_id}/advance")
def advance_order(order_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER", "SELLER"))) -> dict:
    order = db.scalar(select(Order).options(joinedload(Order.customer), joinedload(Order.product)).where(Order.id == order_id))
    if not order:
        raise HTTPException(404, "Buyurtma topilmadi")
    transitions = {"CONFIRMED": "IN_PROGRESS", "IN_PROGRESS": "READY", "READY": "DELIVERED"}
    if order.status not in transitions:
        raise HTTPException(409, "Buyurtma allaqachon yopilgan")
    order.status = transitions[order.status]
    audit(db, _, "ADVANCE_STATUS", "ORDER", order.id, f"Buyurtma holati: {order.status}")
    db.commit(); db.refresh(order)
    if order.status == "READY":
        send_telegram(db, order.customer_id, f"Optika OS: buyurtmangiz #{order.id} ({order.item_name or (order.product.name if order.product else 'mahsulot')}) tayyor. Uni optikadan olib ketishingiz mumkin.")
    return ok(order_data(order))


@app.post("/api/v1/orders/{order_id}/cancel")
def cancel_order(order_id: int, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER"))) -> dict:
    order = db.scalar(select(Order).options(joinedload(Order.customer), joinedload(Order.product)).where(Order.id == order_id))
    if not order:
        raise HTTPException(404, "Buyurtma topilmadi")
    if order.status in {"DELIVERED", "CANCELLED"}:
        raise HTTPException(409, "Bu buyurtmani bekor qilib bolmaydi")
    order.status = "CANCELLED"
    order.customer.debt = max(0, order.customer.debt - (order.total - order.paid))
    if order.product:
        order.product.stock += 1
        stock_movement(db, order.product, 1, "ORDER_CANCEL", "ORDER", order.id, "Bekor qilingan buyurtma rezervi qaytarildi")
    audit(db, _, "CANCEL", "ORDER", order.id, "Buyurtma bekor qilindi")
    db.commit(); db.refresh(order)
    return ok(order_data(order))


@app.post("/api/v1/sales", status_code=status.HTTP_201_CREATED)
def create_sale(payload: SaleCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER", "SELLER"))) -> dict:
    customer = db.get(Customer, payload.customer_id) if payload.customer_id else None
    items: list[tuple[Product, int]] = []
    total = 0
    for line in payload.items:
        product = db.get(Product, line.product_id)
        if not product:
            raise HTTPException(404, f"Mahsulot #{line.product_id} topilmadi")
        if product.stock < line.quantity:
            raise HTTPException(409, f"{product.name}: qoldiq yetarli emas")
        items.append((product, line.quantity)); total += product.sale_price * line.quantity
    if payload.paid > total:
        raise HTTPException(422, "To'lov umumiy summadan katta")
    if payload.paid < total and not customer:
        raise HTTPException(422, "Qarzli savat uchun mijoz tanlang")
    sale = Sale(customer=customer, total=total, paid=payload.paid, payment_method=payload.payment_method)
    db.add(sale)
    db.flush()
    for product, quantity in items:
        product.stock -= quantity
        sale.items.append(SaleItem(product=product, quantity=quantity, unit_price=product.sale_price))
        stock_movement(db, product, -quantity, "SALE", "SALE", sale.id, "POS savdo")
    if customer:
        customer.debt += total - payload.paid
    if shift := open_shift(db):
        db.add(CashMovement(cash_shift_id=shift.id, movement_type="SALE_PAYMENT", amount=payload.paid, reference_type="SALE", reference_id=sale.id, note=f"Sotuv #{sale.id}"))
    db.flush(); audit(db, _, "CREATE", "SALE", sale.id, f"Sotuv: {total} som, tolov: {payload.paid} som"); db.commit(); db.refresh(sale)
    return ok({"id": sale.id, "total": sale.total, "paid": sale.paid, "balance": sale.total - sale.paid, "created_at": sale.created_at})


@app.get("/api/v1/sales")
def list_sales(limit: int = 100, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    rows = db.scalars(select(Sale).options(joinedload(Sale.customer), joinedload(Sale.items).joinedload(SaleItem.product)).order_by(Sale.id.desc()).limit(min(limit, 200))).unique()
    return ok([{"id": sale.id, "customer": customer_data(sale.customer) if sale.customer else None, "total": sale.total, "paid": sale.paid, "balance": sale.total - sale.paid, "payment_method": sale.payment_method, "created_at": sale.created_at, "items": [{"product": product_data(item.product), "quantity": item.quantity, "unit_price": item.unit_price} for item in sale.items]} for sale in rows])


@app.post("/api/v1/sales/{sale_id}/return", status_code=status.HTTP_201_CREATED)
def return_sale_item(sale_id: int, payload: SaleReturnCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER"))) -> dict:
    sale = db.scalar(select(Sale).options(joinedload(Sale.customer), joinedload(Sale.items)).where(Sale.id == sale_id))
    if not sale:
        raise HTTPException(404, "Sotuv topilmadi")
    sale_item = next((item for item in sale.items if item.product_id == payload.product_id), None)
    if not sale_item:
        raise HTTPException(404, "Bu mahsulot ushbu sotuvda mavjud emas")
    returned = db.scalar(select(func.coalesce(func.sum(SaleReturn.quantity), 0)).where(SaleReturn.sale_id == sale_id, SaleReturn.product_id == payload.product_id)) or 0
    if returned + payload.quantity > sale_item.quantity:
        raise HTTPException(409, "Qaytarilayotgan miqdor sotilgan miqdordan katta")
    product = db.get(Product, payload.product_id)
    amount = sale_item.unit_price * payload.quantity
    sale_return = SaleReturn(sale_id=sale.id, product_id=product.id, quantity=payload.quantity, amount=amount, disposition=payload.disposition, reason=payload.reason)
    db.add(sale_return); db.flush()
    if payload.disposition == "RESTOCK":
        product.stock += payload.quantity
        stock_movement(db, product, payload.quantity, "RETURN_IN", "SALE_RETURN", sale_return.id, payload.reason)
    else:
        stock_movement(db, product, 0, "DAMAGE", "SALE_RETURN", sale_return.id, payload.reason)
    if sale.customer:
        sale.customer.debt = max(0, sale.customer.debt - amount)
    if shift := open_shift(db):
        db.add(CashMovement(cash_shift_id=shift.id, movement_type="REFUND", amount=-amount, reference_type="SALE_RETURN", reference_id=sale_return.id, note=payload.reason))
    audit(db, _, "RETURN", "SALE", sale.id, f"{payload.quantity} dona qaytarildi: {amount} som")
    db.commit(); db.refresh(sale_return)
    return ok({"id": sale_return.id, "sale_id": sale_id, "product_id": product.id, "quantity": sale_return.quantity, "amount": sale_return.amount, "disposition": sale_return.disposition, "reason": sale_return.reason})


@app.get("/api/v1/suppliers")
def list_suppliers(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    return ok([supplier_data(supplier) for supplier in db.scalars(select(Supplier).order_by(Supplier.name))])


@app.post("/api/v1/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER"))) -> dict:
    if db.scalar(select(Supplier).where(Supplier.name == payload.name.strip())):
        raise HTTPException(409, "Bu supplier avval mavjud")
    supplier = Supplier(name=payload.name.strip(), phone=payload.phone)
    db.add(supplier); db.flush(); audit(db, _, "CREATE", "SUPPLIER", supplier.id, f"Supplier yaratildi: {supplier.name}"); db.commit(); db.refresh(supplier)
    return ok(supplier_data(supplier))


@app.post("/api/v1/suppliers/{supplier_id}/payments", status_code=status.HTTP_201_CREATED)
def pay_supplier(supplier_id: int, payload: SupplierPaymentCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER"))) -> dict:
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, "Supplier topilmadi")
    if payload.amount > supplier.balance:
        raise HTTPException(422, "Tolov supplier qarzidan katta")
    payment = SupplierPayment(supplier=supplier, amount=payload.amount, comment=payload.comment)
    db.add(payment); db.flush()
    supplier.balance -= payment.amount
    if shift := open_shift(db):
        db.add(CashMovement(cash_shift_id=shift.id, movement_type="SUPPLIER_PAYMENT", amount=-payment.amount, reference_type="SUPPLIER_PAYMENT", reference_id=payment.id, note=payload.comment))
    audit(db, _, "PAY", "SUPPLIER", supplier.id, f"Supplierga tolov: {payment.amount} som")
    db.commit(); db.refresh(payment)
    return ok({"id": payment.id, "supplier": supplier_data(supplier), "amount": payment.amount, "comment": payment.comment, "created_at": payment.created_at})


@app.post("/api/v1/purchases", status_code=status.HTTP_201_CREATED)
def create_purchase(payload: PurchaseCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER"))) -> dict:
    supplier = db.get(Supplier, payload.supplier_id)
    if not supplier:
        raise HTTPException(404, "Supplier topilmadi")
    rows: list[tuple[Product, int, int]] = []
    total = 0
    for line in payload.items:
        product = db.get(Product, line.product_id)
        if not product:
            raise HTTPException(404, f"Mahsulot #{line.product_id} topilmadi")
        rows.append((product, line.quantity, line.unit_cost)); total += line.quantity * line.unit_cost
    if payload.paid > total:
        raise HTTPException(422, "Tolov umumiy kirim summasidan katta")
    purchase = Purchase(supplier=supplier, total=total, paid=payload.paid, invoice_no=payload.invoice_no)
    db.add(purchase)
    db.flush()
    for product, quantity, cost in rows:
        product.stock += quantity
        purchase.items.append(PurchaseItem(product=product, quantity=quantity, unit_cost=cost))
        stock_movement(db, product, quantity, "PURCHASE", "PURCHASE", purchase.id, "Supplierdan kirim")
    supplier.balance += total - payload.paid
    if payload.paid and (shift := open_shift(db)):
        db.add(CashMovement(cash_shift_id=shift.id, movement_type="SUPPLIER_PAYMENT", amount=-payload.paid, reference_type="PURCHASE", reference_id=purchase.id, note=f"Kirim #{purchase.id}"))
    audit(db, _, "CREATE", "PURCHASE", purchase.id, f"Supplierdan kirim: {total} som")
    db.commit(); db.refresh(purchase)
    return ok({"id": purchase.id, "supplier": supplier_data(supplier), "total": purchase.total, "paid": purchase.paid, "balance": purchase.total - purchase.paid, "invoice_no": purchase.invoice_no, "created_at": purchase.created_at})


@app.get("/api/v1/purchases")
def list_purchases(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    rows = db.scalars(select(Purchase).options(joinedload(Purchase.supplier)).order_by(Purchase.id.desc()))
    return ok([{"id": row.id, "supplier": supplier_data(row.supplier), "total": row.total, "paid": row.paid, "balance": row.total - row.paid, "invoice_no": row.invoice_no, "created_at": row.created_at} for row in rows])


@app.get("/api/v1/expenses")
def list_expenses(limit: int = 100, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    rows = db.scalars(select(Expense).order_by(Expense.created_at.desc()).limit(min(limit, 200)))
    return ok([{"id": row.id, "category": row.category, "amount": row.amount, "description": row.description, "cash_shift_id": row.cash_shift_id, "created_at": row.created_at} for row in rows])


@app.post("/api/v1/expenses", status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER"))) -> dict:
    shift = open_shift(db)
    expense = Expense(category=payload.category.strip(), amount=payload.amount, description=payload.description, cash_shift_id=shift.id if shift else None)
    db.add(expense); db.flush()
    if shift:
        db.add(CashMovement(cash_shift_id=shift.id, movement_type="EXPENSE", amount=-expense.amount, reference_type="EXPENSE", reference_id=expense.id, note=expense.category))
    audit(db, _, "CREATE", "EXPENSE", expense.id, f"Xarajat: {expense.category}, {expense.amount} som")
    db.commit(); db.refresh(expense)
    return ok({"id": expense.id, "category": expense.category, "amount": expense.amount, "description": expense.description, "cash_shift_id": expense.cash_shift_id, "created_at": expense.created_at})


@app.get("/api/v1/inventory/{product_id}/movements")
def list_stock_movements(product_id: int, limit: int = 100, db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    if not db.get(Product, product_id):
        raise HTTPException(404, "Mahsulot topilmadi")
    rows = db.scalars(select(StockMovement).where(StockMovement.product_id == product_id).order_by(StockMovement.created_at.desc()).limit(min(limit, 200)))
    return ok([{"id": row.id, "quantity": row.quantity, "movement_type": row.movement_type, "reference_type": row.reference_type, "reference_id": row.reference_id, "note": row.note, "created_at": row.created_at} for row in rows])


@app.get("/api/v1/cash-shifts/current")
def current_shift(db: Session = Depends(get_db), _: User = Depends(current_user)) -> dict:
    shift = open_shift(db)
    return ok(cash_shift_data(shift) if shift else None)


@app.post("/api/v1/cash-shifts/open", status_code=status.HTTP_201_CREATED)
def open_cash_shift(payload: CashShiftOpen, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER", "SELLER"))) -> dict:
    if open_shift(db):
        raise HTTPException(409, "Ochiq smena mavjud")
    shift = CashShift(opening_amount=payload.opening_amount)
    db.add(shift); db.flush(); audit(db, _, "OPEN", "CASH_SHIFT", shift.id, f"Smena ochildi: {payload.opening_amount} som"); db.commit(); db.refresh(shift)
    return ok(cash_shift_data(shift))


@app.post("/api/v1/cash-shifts/{shift_id}/close")
def close_cash_shift(shift_id: int, payload: CashShiftClose, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER", "SELLER"))) -> dict:
    shift = db.get(CashShift, shift_id)
    if not shift or shift.status != "OPEN":
        raise HTTPException(404, "Ochiq smena topilmadi")
    movements = db.scalar(select(func.coalesce(func.sum(CashMovement.amount), 0)).where(CashMovement.cash_shift_id == shift.id)) or 0
    shift.expected_amount = shift.opening_amount + movements
    shift.actual_amount = payload.actual_amount
    shift.status = "CLOSED"
    shift.closed_at = datetime.utcnow()
    audit(db, _, "CLOSE", "CASH_SHIFT", shift.id, f"Smena yopildi. Farq: {shift.actual_amount - shift.expected_amount} som")
    db.commit(); db.refresh(shift)
    return ok(cash_shift_data(shift))


@app.get("/api/v1/reports/dashboard")
def dashboard(db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER"))) -> dict:
    revenue = db.scalar(select(func.coalesce(func.sum(Sale.paid), 0))) or 0
    order_paid = db.scalar(select(func.coalesce(func.sum(Order.paid), 0))) or 0
    debt = db.scalar(select(func.coalesce(func.sum(Customer.debt), 0))) or 0
    low_stock = db.scalar(select(func.count(Product.id)).where(Product.stock <= Product.minimum_stock)) or 0
    active_orders = db.scalar(select(func.count(Order.id)).where(Order.status != "DELIVERED")) or 0
    supplier_debt = db.scalar(select(func.coalesce(func.sum(Supplier.balance), 0))) or 0
    shift = open_shift(db)
    cash_expected = None
    if shift:
        movements = db.scalar(select(func.coalesce(func.sum(CashMovement.amount), 0)).where(CashMovement.cash_shift_id == shift.id)) or 0
        cash_expected = shift.opening_amount + movements
    return ok({"revenue": revenue + order_paid, "debt": debt, "supplier_debt": supplier_debt, "low_stock": low_stock, "active_orders": active_orders, "open_cash_shift": cash_shift_data(shift) if shift else None, "cash_expected": cash_expected})


@app.get("/api/v1/reports/finance")
def finance_report(db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER"))) -> dict:
    sales_total = db.scalar(select(func.coalesce(func.sum(Sale.total), 0))) or 0
    sales_paid = db.scalar(select(func.coalesce(func.sum(Sale.paid), 0))) or 0
    orders_total = db.scalar(select(func.coalesce(func.sum(Order.total), 0)).where(Order.status != "CANCELLED")) or 0
    orders_paid = db.scalar(select(func.coalesce(func.sum(Order.paid), 0)).where(Order.status != "CANCELLED")) or 0
    expenses = db.scalar(select(func.coalesce(func.sum(Expense.amount), 0))) or 0
    purchases = db.scalar(select(func.coalesce(func.sum(Purchase.total), 0))) or 0
    supplier_debt = db.scalar(select(func.coalesce(func.sum(Supplier.balance), 0))) or 0
    customer_debt = db.scalar(select(func.coalesce(func.sum(Customer.debt), 0))) or 0
    return ok({"sales_revenue": sales_total, "sales_paid": sales_paid, "order_value": orders_total, "order_paid": orders_paid, "expenses": expenses, "cash_in": sales_paid + orders_paid, "cash_out": expenses, "net_cash_flow": sales_paid + orders_paid - expenses, "purchase_value": purchases, "supplier_debt": supplier_debt, "customer_debt": customer_debt})


@app.get("/api/v1/audit")
def list_audit(limit: int = 50, db: Session = Depends(get_db), _: User = Depends(require_roles("OWNER", "MANAGER"))) -> dict:
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 200)))
    return ok([{"id": row.id, "action": row.action, "entity_type": row.entity_type, "entity_id": row.entity_id, "summary": row.summary, "created_at": row.created_at} for row in rows])
