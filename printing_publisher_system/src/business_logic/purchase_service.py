from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from src.business_logic.base_service import BaseService
from src.database.daos import 采购清单DAO, 材料供应商关联DAO, 材料DAO, 供应商DAO, 印刷任务DAO
from src.business_logic.inventory_service import InventoryService


class PurchaseService(BaseService):
    """
    采购管理服务：创建采购、分页查询、状态更新、收货入库联动。
    表结构参考：采购清单表、材料供应商关联表、材料表、供应商表。
    """

    def __init__(self) -> None:
        super().__init__()
        self.purchase_dao = 采购清单DAO()
        self.link_dao = 材料供应商关联DAO()
        self.material_dao = 材料DAO()
        self.supplier_dao = 供应商DAO()
        self.inventory_service = InventoryService()
        self.task_dao = 印刷任务DAO()

    # ========= 查询 =========
    def list_purchases_page(
        self,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
        task_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """分页查询采购记录，支持按状态与任务过滤，并补充材料/供应商名称。"""
        try:
            filters: Dict[str, Any] = {}
            if status:
                filters["采购状态"] = status
            if task_id:
                filters["印刷任务id"] = int(task_id)
            page_data = self.purchase_dao.get_page(filters=filters or None, order_by="采购日期 DESC", page=page, page_size=page_size)
            items = page_data.get("items", [])

            # 补充关联信息（材料/供应商/单价）
            for it in items:
                link_id = it.get("材料供应商关联id")
                link = self.link_dao.get_by_id(link_id) if link_id else None
                if link:
                    it["关联_单价"] = link.get("供应商提供的材料单价")
                    material = self.material_dao.get_by_id(link.get("材料id"))
                    supplier = self.supplier_dao.get_by_id(link.get("供应商id"))
                    it["关联_材料名称"] = material.get("材料名称") if material else None
                    it["关联_供应商名称"] = supplier.get("供应商名称") if supplier else None
            page_data["items"] = items
            return self._create_success_response(data=page_data)
        except Exception as e:
            return self._create_error_response(f"获取采购记录失败: {str(e)}")

    def list_all_links(self) -> Dict[str, Any]:
        """列出所有材料-供应商关联，附带材料/供应商名称与单价。"""
        try:
            # 直接获取全部关联
            links = self.link_dao.get_all(order_by="材料id ASC")
            enriched = []
            for lk in links:
                material = self.material_dao.get_by_id(lk.get("材料id")) if lk.get("材料id") else None
                supplier = self.supplier_dao.get_by_id(lk.get("供应商id")) if lk.get("供应商id") else None
                enriched.append({
                    **lk,
                    "材料名称": material.get("材料名称") if material else None,
                    "供应商名称": supplier.get("供应商名称") if supplier else None,
                })
            return self._create_success_response(data={"items": enriched})
        except Exception as e:
            return self._create_error_response(f"获取材料-供应商关联失败: {str(e)}")

    # ========= 创建 =========
    def create_purchase(self, task_id: int, link_id: int, quantity: float) -> Dict[str, Any]:
        try:
            if not task_id or not link_id:
                return self._create_error_response("任务与材料-供应商关联必须选择")
            try:
                qty = float(quantity)
            except Exception:
                return self._create_error_response("采购数量格式错误")
            if qty <= 0:
                return self._create_error_response("采购数量必须大于0")

            # 校验印刷任务存在且可用
            task = self.task_dao.get_by_id(int(task_id))
            if not task:
                return self._create_error_response("印刷任务不存在或已删除，请先创建印刷任务")
            if task.get("任务状态") == "已取消":
                return self._create_error_response("该印刷任务已取消，不能创建采购")

            # 校验材料-供应商关联存在
            link = self.link_dao.get_by_id(int(link_id))
            if not link:
                return self._create_error_response("材料-供应商关联不存在")
            unit_price = float(link.get("供应商提供的材料单价") or 0)
            total_cost = round(qty * unit_price, 2)

            payload = {
                "印刷任务id": int(task_id),
                "材料供应商关联id": int(link_id),
                "采购数量": qty,
                "总成本": total_cost,
                "采购状态": "待采购",
            }
            new_id = self.purchase_dao.create(payload)
            if not new_id:
                return self._create_error_response("创建采购记录失败")
            return self._create_success_response(data={"purchase_id": new_id}, message="采购记录已创建")
        except Exception as e:
            return self._create_error_response(f"创建采购记录失败: {str(e)}")

    # ========= 状态流转 =========
    def update_status(self, purchase_id: int, new_status: str, receipt_date: Optional[str] = None) -> Dict[str, Any]:
        """
        严格的状态流转：
        - 待采购 -> 已下单/已取消
        - 已下单 -> 已取消（收货请使用 receive_purchase）
        - 已收货/已取消 -> 不允许再修改
        """
        try:
            record = self.purchase_dao.get_by_id(purchase_id)
            if not record:
                return self._create_error_response("采购记录不存在")
            current = record.get("采购状态")
            if current in {"已收货", "已取消"}:
                return self._create_error_response("该采购记录已完成或已取消，状态不可再修改")

            valid = {"待采购", "已下单", "已收货", "已取消"}
            if new_status not in valid:
                return self._create_error_response("无效的采购状态")

            allowed = {
                "待采购": {"已下单", "已取消"},
                "已下单": {"已取消"},  # 收货请走 receive_purchase
            }
            if current not in allowed or new_status not in allowed[current]:
                if new_status == "已收货":
                    return self._create_error_response("请使用收货入库来完成收货操作")
                return self._create_error_response(f"非法的状态流转：{current} -> {new_status}")

            ok = self.purchase_dao.update(purchase_id, {"采购状态": new_status})
            if not ok:
                return self._create_error_response("更新采购状态失败")
            return self._create_success_response(message="采购状态已更新")
        except Exception as e:
            return self._create_error_response(f"更新采购状态失败: {str(e)}")

    def receive_purchase(self, purchase_id: int, operator_employee_id: int, receipt_date: Optional[str] = None) -> Dict[str, Any]:
        """
        收货：
        1) 将采购状态置为“已收货”，写入收货日期（默认今日）
        2) 按采购数量做入库，并记录库存日志
        """
        try:
            row = self.purchase_dao.get_by_id(purchase_id)
            if not row:
                return self._create_error_response("采购记录不存在")
            status = row.get("采购状态")
            if status == "已收货":
                return self._create_error_response("该采购已收货，不能重复收货")
            if status == "已取消":
                return self._create_error_response("已取消的采购无法收货")
            if status != "待采购":
                return self._create_error_response("仅'待采购'的采购可以收货入库")

            link_id = row.get("材料供应商关联id")
            link = self.link_dao.get_by_id(link_id) if link_id else None
            if not link:
                return self._create_error_response("找不到关联的材料-供应商信息")
            material_id = int(link.get("材料id"))
            qty = float(row.get("采购数量") or 0)
            if qty <= 0:
                return self._create_error_response("采购数量无效，无法入库")

            # 1) 入库并记录日志（先做入库，避免出现标记收货但库存未变动）
            rdate = receipt_date or date.today().isoformat()
            ref = f"purchase:{purchase_id}"
            inv = self.inventory_service.update_stock_level(
                material_id=material_id,
                change_quantity=qty,
                change_type="入库",
                reference_id=ref,
                operator_id=int(operator_employee_id),
                note="采购收货入库",
            )
            if not inv.get("success"):
                return self._create_error_response("入库失败: " + inv.get("message", "未知错误"))

            # 2) 更新采购状态 + 收货日期
            ok = self.purchase_dao.update(purchase_id, {"采购状态": "已收货", "材料收货日期": rdate})
            if not ok:
                return self._create_error_response("更新采购状态失败")

            return self._create_success_response(message="收货并入库成功", data={"new_quantity": inv.get("data", {}).get("new_quantity")})
        except Exception as e:
            return self._create_error_response(f"收货失败: {str(e)}")

