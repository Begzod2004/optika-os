from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Customer(Base):
    __tablename__ = "customers"
    # Telefon unikalligi filial darajasida: har filial o'z mijozlar daftarini yuritadi.
    __table_args__ = (UniqueConstraint("branch_id", "phone", name="uq_customers_branch_phone"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str] = mapped_column(String(30), index=True)
    debt: Mapped[int] = mapped_column(Integer, default=0)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CustomerPayment(Base):
    __tablename__ = "customer_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    customer: Mapped[Customer] = relationship()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="SELLER")
    active: Mapped[bool] = mapped_column(default=True)
    full_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(80), nullable=True)
    photo: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    brand: Mapped[str] = mapped_column(String(100), default="Optika")
    category: Mapped[str] = mapped_column(String(60))
    sale_price: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    minimum_stock: Mapped[int] = mapped_column(Integer, default=0)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    movement_type: Mapped[str] = mapped_column(String(40))
    reference_type: Mapped[str] = mapped_column(String(40))
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(250), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    product: Mapped[Product] = relationship()


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    od_sph: Mapped[str | None] = mapped_column(String(12), nullable=True)
    od_cyl: Mapped[str | None] = mapped_column(String(12), nullable=True)
    od_axis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    os_sph: Mapped[str | None] = mapped_column(String(12), nullable=True)
    os_cyl: Mapped[str | None] = mapped_column(String(12), nullable=True)
    os_axis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pd: Mapped[float | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    customer: Mapped[Customer] = relationship()


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SupplierPayment(Base):
    __tablename__ = "supplier_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    supplier: Mapped[Supplier] = relationship()


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"))
    total: Mapped[int] = mapped_column(Integer)
    paid: Mapped[int] = mapped_column(Integer, default=0)
    invoice_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    supplier: Mapped[Supplier] = relationship()
    items: Mapped[list["PurchaseItem"]] = relationship(cascade="all, delete-orphan")


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_cost: Mapped[int] = mapped_column(Integer)
    purchase: Mapped[Purchase] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class CashShift(Base):
    __tablename__ = "cash_shifts"

    id: Mapped[int] = mapped_column(primary_key=True)
    opening_amount: Mapped[int] = mapped_column(Integer)
    expected_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CashMovement(Base):
    __tablename__ = "cash_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    cash_shift_id: Mapped[int | None] = mapped_column(ForeignKey("cash_shifts.id"), nullable=True)
    movement_type: Mapped[str] = mapped_column(String(40))
    amount: Mapped[int] = mapped_column(Integer)
    reference_type: Mapped[str] = mapped_column(String(40))
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(250), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(80))
    amount: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    cash_shift_id: Mapped[int | None] = mapped_column(ForeignKey("cash_shifts.id"), nullable=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    item_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    total: Mapped[int] = mapped_column(Integer)
    paid: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="CONFIRMED")
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    customer: Mapped[Customer] = relationship()
    product: Mapped[Product | None] = relationship()


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    total: Mapped[int] = mapped_column(Integer)
    paid: Mapped[int] = mapped_column(Integer)
    payment_method: Mapped[str] = mapped_column(String(30), default="CASH")
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    customer: Mapped[Customer | None] = relationship()
    items: Mapped[list["SaleItem"]] = relationship(cascade="all, delete-orphan")


class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[int] = mapped_column(Integer)
    sale: Mapped[Sale] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()


class SaleReturn(Base):
    __tablename__ = "sale_returns"

    id: Mapped[int] = mapped_column(primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer)
    disposition: Mapped[str] = mapped_column(String(20), default="RESTOCK")
    reason: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sale: Mapped[Sale] = relationship()
    product: Mapped[Product] = relationship()


class RepairOrder(Base):
    __tablename__ = "repair_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    device: Mapped[str] = mapped_column(String(180))
    issue: Mapped[str] = mapped_column(String(500))
    estimated_cost: Mapped[int] = mapped_column(Integer)
    paid: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="RECEIVED", index=True)
    technician_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    customer: Mapped[Customer] = relationship()


class TelegramSubscriber(Base):
    __tablename__ = "telegram_subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    customer: Mapped[Customer | None] = relationship()


class TelegramLink(Base):
    __tablename__ = "telegram_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    customer: Mapped[Customer] = relationship()


class BackupRecord(Base):
    __tablename__ = "backup_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserBranch(Base):
    __tablename__ = "user_branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    user: Mapped[User] = relationship()
    branch: Mapped[Branch] = relationship()


class OpticalCase(Base):
    __tablename__ = "optical_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    frame_product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    chief_complaint: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="FRAME_SELECTED", index=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    customer: Mapped[Customer] = relationship(foreign_keys=[customer_id])
    frame_product: Mapped[Product | None] = relationship(foreign_keys=[frame_product_id])
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])


class EyeExam(Base):
    __tablename__ = "eye_exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    optical_case_id: Mapped[int] = mapped_column(ForeignKey("optical_cases.id"), unique=True, index=True)
    performed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    od_sph: Mapped[str | None] = mapped_column(String(12), nullable=True)
    od_cyl: Mapped[str | None] = mapped_column(String(12), nullable=True)
    od_axis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    os_sph: Mapped[str | None] = mapped_column(String(12), nullable=True)
    os_cyl: Mapped[str | None] = mapped_column(String(12), nullable=True)
    os_axis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    add_power: Mapped[str | None] = mapped_column(String(12), nullable=True)
    prism: Mapped[str | None] = mapped_column(String(30), nullable=True)
    distance_va: Mapped[str | None] = mapped_column(String(30), nullable=True)
    near_va: Mapped[str | None] = mapped_column(String(30), nullable=True)
    clinical_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    referral_required: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20), default="FINAL")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    optical_case: Mapped[OpticalCase] = relationship()
    performed_by: Mapped[User | None] = relationship()


class Centration(Base):
    __tablename__ = "centrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    optical_case_id: Mapped[int] = mapped_column(ForeignKey("optical_cases.id"), unique=True, index=True)
    pd_right: Mapped[float] = mapped_column()
    pd_left: Mapped[float] = mapped_column()
    fitting_height_right: Mapped[float] = mapped_column()
    fitting_height_left: Mapped[float] = mapped_column()
    vertex_distance: Mapped[float | None] = mapped_column(nullable=True)
    pantoscopic_tilt: Mapped[float | None] = mapped_column(nullable=True)
    wrap_angle: Mapped[float | None] = mapped_column(nullable=True)
    measured_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    optical_case: Mapped[OpticalCase] = relationship()


class LensConfiguration(Base):
    __tablename__ = "lens_configurations"

    id: Mapped[int] = mapped_column(primary_key=True)
    optical_case_id: Mapped[int] = mapped_column(ForeignKey("optical_cases.id"), unique=True, index=True)
    lens_design: Mapped[str] = mapped_column(String(30))
    material_index: Mapped[str] = mapped_column(String(20))
    coating: Mapped[str | None] = mapped_column(String(200), nullable=True)
    photochromic: Mapped[bool] = mapped_column(default=False)
    lab_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    selected_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    optical_case: Mapped[OpticalCase] = relationship()


class LabJob(Base):
    __tablename__ = "lab_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    optical_case_id: Mapped[int] = mapped_column(ForeignKey("optical_cases.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="SENT")
    laboratory: Mapped[str | None] = mapped_column(String(150), nullable=True)
    job_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    qc_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    optical_case: Mapped[OpticalCase] = relationship()
