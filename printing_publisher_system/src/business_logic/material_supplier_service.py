from typing import Any, Dict, Optional, List
from decimal import Decimal

from src.business_logic.base_service import BaseService
from src.database.daos import 材料DAO, 供应商DAO, 材料供应商关联DAO


class MaterialSupplierService(BaseService):
    """
    材料、供应商及关联管理：
    - 材料基础信息维护
    - 供应商信息维护
    - 材料-供应商关联（价格、首选）
    """

    def __init__(self) -> None:
        super().__init__()
        self.material_dao = 材料DAO()
        self.supplier_dao = 供应商DAO()
        self.link_dao = 材料供应商关联DAO()

    # ========== 材料 ==========
    def list_materials(self, name_kw: Optional[str] = None) -> Dict[str, Any]:
        try:
            if name_kw:
                query = "SELECT * FROM 材料表 WHERE 材料名称 LIKE %s ORDER BY 材料名称"
                with self.material_dao.db.get_cursor() as cursor:  # type: ignore
                    cursor.execute(query, (f"%{name_kw}%",))
                    items = cursor.fetchall()
            else:
                items = self.material_dao.get_all(order_by="材料名称")
            return self._create_success_response(data={"items": items})
        except Exception as e:
            return self._create_error_response(f"获取材料列表失败: {str(e)}")

    def create_material(self, name: str, unit: str, spec: Optional[str], unit_price: Optional[float]) -> Dict[str, Any]:
        try:
            name = (name or "").strip()
            unit = (unit or "").strip()
            spec = (spec or "").strip()
            if not name:
                return self._create_error_response("材料名称不能为空")
            payload: Dict[str, Any] = {
                "材料名称": name,
                "计量单位": unit or None,  # 表字段为“计量单位”
                "规格": spec or None,
            }
            if unit_price is not None:
                payload["标准单价"] = float(unit_price)
            new_id = self.material_dao.create(payload)
            if not new_id:
                return self._create_error_response("创建材料失败")
            return self._create_success_response(data={"material_id": new_id}, message="材料创建成功")
        except Exception as e:
            return self._create_error_response(f"创建材料失败: {str(e)}")

    # ========== 供应商 ==========
    def list_suppliers(self, name_kw: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        try:
            filters: Dict[str, Any] = {}
            if status:
                filters["合作状态"] = status
            items = self.supplier_dao.get_all(filters=filters, order_by="供应商名称")
            if name_kw:
                # 进一步在内存中过滤名称
                items = [s for s in items if name_kw in str(s.get("供应商名称", ""))]
            return self._create_success_response(data={"items": items})
        except Exception as e:
            return self._create_error_response(f"获取供应商列表失败: {str(e)}")

    def create_supplier(self, name: str, contact: Optional[str], phone: Optional[str], status: str = "合作中") -> Dict[str, Any]:
        try:
            name = (name or "").strip()
            contact = (contact or "").strip()
            phone = (phone or "").strip()
            status = (status or "合作中").strip()
            if not name:
                return self._create_error_response("供应商名称不能为空")
            payload = {
                "供应商名称": name,
                "供应商联系人": contact or None,
                "联系电话": phone or None,
                "合作状态": status or "合作中",
            }
            new_id = self.supplier_dao.create(payload)
            if not new_id:
                return self._create_error_response("创建供应商失败")
            return self._create_success_response(data={"supplier_id": new_id}, message="供应商创建成功")
        except Exception as e:
            return self._create_error_response(f"创建供应商失败: {str(e)}")

    # ========== 材料-供应商关联 ==========
    def list_material_suppliers(self, material_id: int) -> Dict[str, Any]:
        try:
            items = self.link_dao.get_material_suppliers(material_id)
            return self._create_success_response(data={"items": items})
        except Exception as e:
            return self._create_error_response(f"获取材料供应商列表失败: {str(e)}")

    def create_material_supplier_link(
        self,
        material_id: int,
        supplier_id: int,
        price: float,
        preferred: bool = False,
    ) -> Dict[str, Any]:
        try:
            if price is None:
                return self._create_error_response("供应商提供的材料单价不能为空")
            price_val = float(price)
            payload = {
                "材料id": material_id,
                "供应商id": supplier_id,
                "供应商提供的材料单价": price_val,
                "是否为首选供应商": "是" if preferred else "否",
            }
            new_id = self.link_dao.create(payload)
            if not new_id:
                return self._create_error_response("创建材料-供应商关联失败")
            return self._create_success_response(data={"link_id": new_id}, message="关联创建成功")
        except Exception as e:
            return self._create_error_response(f"创建材料-供应商关联失败: {str(e)}")

