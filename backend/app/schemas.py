from datetime import datetime

from pydantic import BaseModel, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    phone: str = Field(min_length=7, max_length=30)
    branch_id: int | None = None


class LoginInput(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)


class PrescriptionCreate(BaseModel):
    od_sph: str | None = Field(default=None, max_length=12)
    od_cyl: str | None = Field(default=None, max_length=12)
    od_axis: int | None = Field(default=None, ge=0, le=180)
    os_sph: str | None = Field(default=None, max_length=12)
    os_cyl: str | None = Field(default=None, max_length=12)
    os_axis: int | None = Field(default=None, ge=0, le=180)
    pd: float | None = Field(default=None, ge=40, le=85)
    note: str | None = Field(default=None, max_length=500)
    reminder_at: datetime | None = Field(default=None)


class SupplierCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)


class PurchaseLine(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_cost: int = Field(gt=0)


class PurchaseCreate(BaseModel):
    supplier_id: int
    paid: int = Field(default=0, ge=0)
    invoice_no: str | None = Field(default=None, max_length=80)
    items: list[PurchaseLine] = Field(min_length=1)


class CashShiftOpen(BaseModel):
    opening_amount: int = Field(ge=0)
    branch_id: int | None = None


class CashShiftClose(BaseModel):
    actual_amount: int = Field(ge=0)


class SaleReturnCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    disposition: str = Field(default="RESTOCK", pattern="^(RESTOCK|DAMAGE)$")
    reason: str = Field(min_length=2, max_length=300)


class ExpenseCreate(BaseModel):
    category: str = Field(min_length=2, max_length=80)
    amount: int = Field(gt=0)
    description: str | None = Field(default=None, max_length=300)
    branch_id: int | None = None



class SupplierPaymentCreate(BaseModel):
    amount: int = Field(gt=0)
    comment: str | None = Field(default=None, max_length=300)


class CustomerPaymentCreate(BaseModel):
    amount: int = Field(gt=0)
    comment: str | None = Field(default=None, max_length=300)


class ProductCreate(BaseModel):
    name: str
    brand: str = "Optika"
    category: str
    sale_price: int = Field(gt=0)
    stock: int = Field(ge=0)
    minimum_stock: int = Field(default=0, ge=0)
    branch_id: int | None = None


class StockReceive(BaseModel):
    quantity: int = Field(gt=0)


class OrderCancel(BaseModel):
    refund_advance: bool = False


class OrderCreate(BaseModel):
    customer_id: int
    product_id: int | None = None
    item_name: str | None = Field(default=None, max_length=200)
    total: int | None = Field(default=None, ge=0)
    paid: int = Field(default=0, ge=0)


class SaleLine(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class SaleCreate(BaseModel):
    customer_id: int | None = None
    paid: int = Field(ge=0)
    payment_method: str = "CASH"
    items: list[SaleLine] = Field(min_length=1)


class RepairOrderCreate(BaseModel):
    customer_id: int
    device: str = Field(min_length=2, max_length=180)
    issue: str = Field(min_length=2, max_length=500)
    estimated_cost: int = Field(ge=0)
    paid: int = Field(default=0, ge=0)
    due_date: datetime | None = None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern="^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="SELLER", pattern="^(OWNER|MANAGER|SELLER|OPTOMETRIST|LAB_QC)$")


class OpticalCaseCreate(BaseModel):
    customer_id: int
    frame_product_id: int | None = None
    chief_complaint: str | None = Field(default=None, max_length=500)


class EyeExamCreate(BaseModel):
    od_sph: str | None = Field(default=None, max_length=12)
    od_cyl: str | None = Field(default=None, max_length=12)
    od_axis: int | None = Field(default=None, ge=0, le=180)
    os_sph: str | None = Field(default=None, max_length=12)
    os_cyl: str | None = Field(default=None, max_length=12)
    os_axis: int | None = Field(default=None, ge=0, le=180)
    add_power: str | None = Field(default=None, max_length=12)
    prism: str | None = Field(default=None, max_length=30)
    distance_va: str | None = Field(default=None, max_length=30)
    near_va: str | None = Field(default=None, max_length=30)
    clinical_note: str | None = Field(default=None, max_length=1000)
    referral_required: bool = False


class CentrationCreate(BaseModel):
    pd_right: float = Field(ge=20, le=45)
    pd_left: float = Field(ge=20, le=45)
    fitting_height_right: float = Field(ge=10, le=45)
    fitting_height_left: float = Field(ge=10, le=45)
    vertex_distance: float | None = Field(default=None, ge=5, le=25)
    pantoscopic_tilt: float | None = Field(default=None, ge=-5, le=25)
    wrap_angle: float | None = Field(default=None, ge=0, le=30)


class LensConfigurationCreate(BaseModel):
    lens_design: str = Field(pattern="^(SINGLE_VISION|READING|BIFOCAL|PROGRESSIVE)$")
    material_index: str = Field(pattern="^(1.50|1.56|1.60|1.67|1.74|POLYCARBONATE)$")
    coating: str | None = Field(default=None, max_length=200)
    photochromic: bool = False
    lab_note: str | None = Field(default=None, max_length=500)


class LabJobCreate(BaseModel):
    laboratory: str | None = Field(default=None, max_length=150)
    job_reference: str | None = Field(default=None, max_length=100)


class LabJobUpdate(BaseModel):
    status: str = Field(pattern="^(RECEIVED|QC_PASSED|QC_FAILED|READY|DELIVERED)$")
    qc_note: str | None = Field(default=None, max_length=500)


class BranchCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    code: str = Field(min_length=2, max_length=30, pattern="^[A-Za-z0-9_-]+$")
    address: str | None = Field(default=None, max_length=300)


class UserBranchAssign(BaseModel):
    user_id: int


class RepairOrderUpdate(BaseModel):
    status: str = Field(pattern="^(RECEIVED|DIAGNOSIS|IN_PROGRESS|READY|DELIVERED|CANCELLED)$")
    technician_note: str | None = Field(default=None, max_length=500)
