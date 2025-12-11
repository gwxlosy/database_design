# 领域模型与字段映射（Pydantic 可选）
# - 兼容 Pydantic v1 与 v2（避免 v2 的 allow_population_by_field_name 警告）
# - 提供 dict <-> model 的通用转换

from __future__ import annotations

from typing import Any, Dict, Optional, Type, TypeVar, List
from datetime import datetime, date

_PYDANTIC = False
_PYDANTIC_V2 = False

try:
    import pydantic  # type: ignore
    from pydantic import BaseModel, Field  # type: ignore
    try:
        # v2 存在 ConfigDict
        from pydantic import ConfigDict  # type: ignore
        _PYDANTIC_V2 = True
    except Exception:
        _PYDANTIC_V2 = False
    _PYDANTIC = True
except Exception:
    BaseModel = object  # type: ignore
    Field = lambda *args, **kwargs: None  # type: ignore

# ========= 中文列名别名映射 =========
PRINTING_TASK_ALIASES: Dict[str, str] = {
    "task_id": "印刷任务id",
    "employee_id": "员工id",
    "book_id": "书籍id",
    "quantity": "印刷数量",
    "due_date": "预计完成日期",
    "status": "任务状态",
    "submitted_at": "任务提交日期",
    "completed_at": "实际完成日期",
}

EMPLOYEE_ALIASES: Dict[str, str] = {
    "employee_id": "员工id",
    "name": "员工姓名",
    "status": "在职状态",
    "position": "职位",
    "hired_at": "入职日期",
}

BOOK_ALIASES: Dict[str, str] = {
    "book_id": "书籍id",
    "name": "书籍名称",
    "author": "作者",
}

MATERIAL_ALIASES: Dict[str, str] = {
    "material_id": "材料id",
    "name": "材料名称",
    "stock_qty": "库存数量",
    "safety_stock": "安全库存",
    "unit_price": "标准单价",
}

SUPPLIER_LINK_ALIASES: Dict[str, str] = {
    "link_id": "材料供应商关联id",
    "material_id": "材料id",
    "supplier_id": "供应商id",
    "price": "供应商提供的材料单价",
    "preferred": "是否为首选供应商",
}

PURCHASE_ALIASES: Dict[str, str] = {
    "purchase_id": "采购记录id",
    "task_id": "印刷任务id",
    "link_id": "材料供应商关联id",
    "quantity": "采购数量",
    "total_cost": "总成本",
    "status": "采购状态",
    "receipt_date": "材料收货日期",
    "purchased_at": "采购日期",
}

STOCK_LOG_ALIASES: Dict[str, str] = {
    "log_id": "库存日志id",
    "material_id": "材料id",
    "delta": "库存变动数量",
    "change_type": "变动类型",
    "reference": "关联的业务记录标识",
    "operator_id": "操作人",
    "note": "备注",
    "changed_at": "变动时间",
}

USER_ALIASES: Dict[str, str] = {
    "user_id": "用户id",
    "username": "用户名",
    "password": "密码",
    "position": "职位",
    "created_at": "创建时间",
}

# ========= Pydantic 模型（可选） =========
if _PYDANTIC:

    def _cfg(extra: Optional[dict] = None):
        if _PYDANTIC_V2:
            # v2 使用 ConfigDict
            from pydantic import ConfigDict  # type: ignore
            base = dict(populate_by_name=True, arbitrary_types_allowed=True)
            if extra:
                base.update(extra)
            return ConfigDict(**base)  # type: ignore
        else:
            # v1 使用 Config 内类
            class _C:  # type: ignore
                allow_population_by_field_name = True
                arbitrary_types_allowed = True
            return _C

    class PrintingTaskModel(BaseModel):
        task_id: Optional[int] = Field(None, alias=PRINTING_TASK_ALIASES["task_id"])
        employee_id: int = Field(..., alias=PRINTING_TASK_ALIASES["employee_id"])
        book_id: int = Field(..., alias=PRINTING_TASK_ALIASES["book_id"])
        quantity: int = Field(..., alias=PRINTING_TASK_ALIASES["quantity"])
        due_date: date = Field(..., alias=PRINTING_TASK_ALIASES["due_date"])
        status: Optional[str] = Field("待开始", alias=PRINTING_TASK_ALIASES["status"])  # 默认状态
        submitted_at: Optional[datetime] = Field(None, alias=PRINTING_TASK_ALIASES["submitted_at"])
        completed_at: Optional[date] = Field(None, alias=PRINTING_TASK_ALIASES["completed_at"])

        if _PYDANTIC_V2:
            model_config = _cfg()
        else:
            Config = _cfg()  # type: ignore

    class EmployeeModel(BaseModel):
        employee_id: Optional[int] = Field(None, alias=EMPLOYEE_ALIASES["employee_id"])  # 允许 None 以便创建
        name: Optional[str] = Field(None, alias=EMPLOYEE_ALIASES["name"])
        status: Optional[str] = Field(None, alias=EMPLOYEE_ALIASES["status"])
        position: Optional[str] = Field(None, alias=EMPLOYEE_ALIASES["position"])
        hired_at: Optional[date] = Field(None, alias=EMPLOYEE_ALIASES["hired_at"])

        if _PYDANTIC_V2:
            model_config = _cfg()
        else:
            Config = _cfg()  # type: ignore

    class BookModel(BaseModel):
        book_id: int = Field(..., alias=BOOK_ALIASES["book_id"])
        name: Optional[str] = Field(None, alias=BOOK_ALIASES["name"])
        author: Optional[str] = Field(None, alias=BOOK_ALIASES["author"])

        if _PYDANTIC_V2:
            model_config = _cfg()
        else:
            Config = _cfg()  # type: ignore

    class MaterialModel(BaseModel):
        material_id: int = Field(..., alias=MATERIAL_ALIASES["material_id"])
        name: Optional[str] = Field(None, alias=MATERIAL_ALIASES["name"])
        stock_qty: float = Field(..., alias=MATERIAL_ALIASES["stock_qty"])
        safety_stock: float = Field(..., alias=MATERIAL_ALIASES["safety_stock"])
        unit_price: float = Field(..., alias=MATERIAL_ALIASES["unit_price"])

        if _PYDANTIC_V2:
            model_config = _cfg()
        else:
            Config = _cfg()  # type: ignore

    class SupplierLinkModel(BaseModel):
        link_id: int = Field(..., alias=SUPPLIER_LINK_ALIASES["link_id"])
        material_id: int = Field(..., alias=SUPPLIER_LINK_ALIASES["material_id"])
        supplier_id: int = Field(..., alias=SUPPLIER_LINK_ALIASES["supplier_id"])
        price: float = Field(..., alias=SUPPLIER_LINK_ALIASES["price"])
        preferred: Optional[str] = Field(None, alias=SUPPLIER_LINK_ALIASES["preferred"])  # '是'/'否'

        if _PYDANTIC_V2:
            model_config = _cfg()
        else:
            Config = _cfg()  # type: ignore

    class PurchaseModel(BaseModel):
        purchase_id: Optional[int] = Field(None, alias=PURCHASE_ALIASES["purchase_id"])
        task_id: int = Field(..., alias=PURCHASE_ALIASES["task_id"])
        link_id: int = Field(..., alias=PURCHASE_ALIASES["link_id"])
        quantity: float = Field(..., alias=PURCHASE_ALIASES["quantity"])
        total_cost: float = Field(..., alias=PURCHASE_ALIASES["total_cost"])
        status: Optional[str] = Field(None, alias=PURCHASE_ALIASES["status"])  # '待采购'/'已采购'/'已收货'
        receipt_date: Optional[date] = Field(None, alias=PURCHASE_ALIASES["receipt_date"])
        purchased_at: Optional[datetime] = Field(None, alias=PURCHASE_ALIASES["purchased_at"])

        if _PYDANTIC_V2:
            model_config = _cfg()
        else:
            Config = _cfg()  # type: ignore

    class StockLogModel(BaseModel):
        log_id: Optional[int] = Field(None, alias=STOCK_LOG_ALIASES["log_id"])
        material_id: int = Field(..., alias=STOCK_LOG_ALIASES["material_id"])
        delta: float = Field(..., alias=STOCK_LOG_ALIASES["delta"])
        change_type: str = Field(..., alias=STOCK_LOG_ALIASES["change_type"])  # 入库/出库/调整
        reference: Optional[str] = Field(None, alias=STOCK_LOG_ALIASES["reference"])  # 业务关联ID
        operator_id: Optional[int] = Field(None, alias=STOCK_LOG_ALIASES["operator_id"])  # 员工id
        note: Optional[str] = Field(None, alias=STOCK_LOG_ALIASES["note"])
        changed_at: Optional[datetime] = Field(None, alias=STOCK_LOG_ALIASES["changed_at"])

        if _PYDANTIC_V2:
            model_config = _cfg()
        else:
            Config = _cfg()  # type: ignore

    class UserModel(BaseModel):
        user_id: Optional[int] = Field(None, alias=USER_ALIASES["user_id"])
        username: str = Field(..., alias=USER_ALIASES["username"])
        password: str = Field(..., alias=USER_ALIASES["password"])
        position: str = Field(..., alias=USER_ALIASES["position"])
        created_at: Optional[datetime] = Field(None, alias=USER_ALIASES["created_at"])

        if _PYDANTIC_V2:
            model_config = _cfg()
        else:
            Config = _cfg()  # type: ignore

else:
    PrintingTaskModel = None  # type: ignore
    EmployeeModel = None  # type: ignore
    BookModel = None  # type: ignore
    MaterialModel = None  # type: ignore
    SupplierLinkModel = None  # type: ignore
    PurchaseModel = None  # type: ignore
    StockLogModel = None  # type: ignore
    UserModel = None  # type: ignore

# ========= 通用转换工具 =========
T = TypeVar("T")

_ALIAS_MAPS = {
    "PrintingTaskModel": PRINTING_TASK_ALIASES,
    "EmployeeModel": EMPLOYEE_ALIASES,
    "BookModel": BOOK_ALIASES,
    "MaterialModel": MATERIAL_ALIASES,
    "SupplierLinkModel": SUPPLIER_LINK_ALIASES,
    "PurchaseModel": PURCHASE_ALIASES,
    "StockLogModel": STOCK_LOG_ALIASES,
    "UserModel": USER_ALIASES,
}


def _get_alias_map_for(model_cls: Any) -> Dict[str, str]:
    name = getattr(model_cls, "__name__", "")
    return _ALIAS_MAPS.get(name, {})


def dict_to_model(model_cls: Type[T], row: Dict[str, Any]) -> T | Dict[str, Any]:
    """将数据库返回的中文键 dict 转为模型实例（若 pydantic 可用），否则原样返回 dict。"""
    if row is None:
        return row  # type: ignore
    if _PYDANTIC and isinstance(model_cls, type) and issubclass(model_cls, BaseModel):  # type: ignore
        # pydantic 支持：通过 alias 直接构造
        return model_cls(**row)  # type: ignore
    return row  # type: ignore


def model_to_db_dict(model: Any) -> Dict[str, Any]:
    """将模型实例转换为数据库中文键 dict。pydantic v2 使用 model_dump；v1 使用 dict。
    回退：若传入 dict 原样返回；若是自定义对象，利用别名映射按属性导出。
    """
    if _PYDANTIC and isinstance(model, BaseModel):  # type: ignore
        if _PYDANTIC_V2:
            return model.model_dump(by_alias=True, exclude_none=True)  # type: ignore
        else:
            return {k: v for k, v in model.dict(by_alias=True).items() if v is not None}  # type: ignore
    if isinstance(model, dict):
        return model
    alias_map = _get_alias_map_for(model.__class__)
    out: Dict[str, Any] = {}
    for en, zh in alias_map.items():
        if hasattr(model, en):
            val = getattr(model, en)
            if val is not None:
                out[zh] = val
    return out


def list_dicts_to_models(model_cls: Type[T], rows: List[Dict[str, Any]]) -> List[T | Dict[str, Any]]:
    return [dict_to_model(model_cls, r) for r in (rows or [])]
