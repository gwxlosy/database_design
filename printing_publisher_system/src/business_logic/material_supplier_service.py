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
    def list_materials(self, name_kw: Optional[str] = None, sort: Optional[str] = None) -> Dict[str, Any]:
        try:
            order_map = {
                "id_asc": "材料id ASC",
                "id_desc": "材料id DESC",
                "name_asc": "材料名称 ASC",
                "name_desc": "材料名称 DESC",
            }
            order_by = order_map.get((sort or "").strip(), "材料id ASC")

            if name_kw:
                query = f"SELECT * FROM 材料表 WHERE 材料名称 LIKE %s ORDER BY {order_by}"
                with self.material_dao.db.get_cursor() as cursor:  # type: ignore
                    cursor.execute(query, (f"%{name_kw}%",))
                    items = cursor.fetchall()
            else:
                items = self.material_dao.get_all(order_by=order_by)
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

    def update_material(self, material_id: int, name: str, unit: str, spec: Optional[str], unit_price: Optional[float]) -> Dict[str, Any]:
        try:
            if not material_id:
                return self._create_error_response("材料ID不能为空")
            name = (name or "").strip()
            unit = (unit or "").strip()
            spec = (spec or "").strip()
            if not name:
                return self._create_error_response("材料名称不能为空")
            payload: Dict[str, Any] = {
                "材料名称": name,
                "计量单位": unit or None,
                "规格": spec or None,
            }
            if unit_price is not None:
                payload["标准单价"] = float(unit_price)
            ok = self.material_dao.update(int(material_id), payload)
            if not ok:
                return self._create_error_response("更新材料失败")
            return self._create_success_response(message="材料已更新")
        except Exception as e:
            return self._create_error_response(f"更新材料失败: {str(e)}")

    # ========== 供应商 ==========
    def _normalize_status(self, status: Optional[str]) -> Optional[str]:
        """将前端状态值映射到数据库存储值（枚举：合作中/已终止）。"""
        if not status:
            return None
        s = (status or "").strip()
        if s in {"暂停", "暂停合作", "已终止"}:
            return "已终止"
        if s == "合作中":
            return "合作中"
        return s

    def list_suppliers(self, name_kw: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        try:
            filters: Dict[str, Any] = {}
            norm_status = self._normalize_status(status)
            if norm_status:
                filters["合作状态"] = norm_status
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
            status = self._normalize_status(status) or "合作中"
            if not name:
                return self._create_error_response("供应商名称不能为空")
            if phone:
                if not phone.isdigit() or len(phone) != 11:
                    return self._create_error_response("联系电话必须为11位数字")
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

    def update_supplier(self, supplier_id: int, name: str, contact: Optional[str], phone: Optional[str], status: str) -> Dict[str, Any]:
        try:
            if not supplier_id:
                return self._create_error_response("供应商ID不能为空")
            name = (name or "").strip()
            contact = (contact or "").strip()
            phone = (phone or "").strip()
            status = self._normalize_status(status) or "合作中"
            if not name:
                return self._create_error_response("供应商名称不能为空")
            if phone:
                if not phone.isdigit() or len(phone) != 11:
                    return self._create_error_response("联系电话必须为11位数字")
            payload = {
                "供应商名称": name,
                "供应商联系人": contact or None,
                "联系电话": phone or None,
                "合作状态": status or "合作中",
            }
            ok = self.supplier_dao.update(int(supplier_id), payload)
            if not ok:
                return self._create_error_response("更新供应商失败")
            return self._create_success_response(message="供应商已更新")
        except Exception as e:
            return self._create_error_response(f"更新供应商失败: {str(e)}")

    def update_supplier_status(self, supplier_id: int, status: str) -> Dict[str, Any]:
        """
        更新供应商合作状态，仅允许合作中/暂停。
        """
        try:
            if not supplier_id:
                return self._create_error_response("供应商ID不能为空")
            status = (status or "").strip()
            if status not in {"合作中", "已终止", "暂停", "暂停合作"}:
                return self._create_error_response("合作状态只能是“合作中”或“已终止”")
            db_status = self._normalize_status(status) or "合作中"
            ok = self.supplier_dao.update(int(supplier_id), {"合作状态": db_status})
            if not ok:
                return self._create_error_response("更新合作状态失败")
            return self._create_success_response(message="合作状态已更新")
        except Exception as e:
            return self._create_error_response(f"更新合作状态失败: {str(e)}")

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

