from typing import Dict, Any, Optional, List

from src.business_logic.base_service import BaseService
from src.database.daos import 材料DAO, 库存日志DAO, 采购清单DAO, DatabaseManager

class InventoryService(BaseService):
    """库存管理业务逻辑服务"""

    def batch_update_stock(self, changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量库存变更（单事务）：
        changes: [{material_id:int, delta:float, change_type:str, reference:str, operator_id:int, note:str}]
        - 确保所有变更均合法（不会出现负库存）后统一提交；否则整体回滚。
        返回: {success, message, data:{results:[{material_id,new_quantity,log_id}]}}
        """
        if not changes:
            return self._create_success_response(data={'results': []})
        try:
            db_manager = DatabaseManager()
            conn = db_manager.get_connection()
            if conn is None:
                return self._create_error_response("无法获取数据库连接")
            try:
                conn.start_transaction()
                results: List[Dict[str, Any]] = []
                # 逐项检查并更新
                for ch in changes:
                    material_id = int(ch.get('material_id'))
                    delta = float(ch.get('delta') or 0)
                    change_type = ch.get('change_type') or ('入库' if delta >= 0 else '出库')
                    reference = ch.get('reference') or ''
                    operator_id = int(ch.get('operator_id') or 0)
                    note = ch.get('note') or ''
                    # 查询当前库存（使用同一连接）
                    with conn.cursor(dictionary=True) as cursor:
                        cursor.execute("SELECT 库存数量 FROM 材料表 WHERE 材料id = %s", (material_id,))
                        row = cursor.fetchone()
                    if not row:
                        raise Exception(f"材料不存在: {material_id}")
                    current_qty = float(row.get('库存数量') or 0)
                    new_qty = current_qty + delta
                    if new_qty < 0:
                        raise Exception(f"材料ID {material_id} 库存不足（需要 {abs(delta)}，当前 {current_qty}）")
                    # 更新库存
                    ok = self.material_dao.update_with_connection(material_id, {'库存数量': new_qty}, conn)
                    if not ok:
                        raise Exception(f"更新材料 {material_id} 库存失败")
                    # 写日志
                    log_id = self.stock_log_dao.create_with_connection({
                        '材料id': material_id,
                        '库存变动数量': delta,
                        '变动类型': change_type,
                        '关联的业务记录标识': reference,
                        '操作人': operator_id,
                        '备注': note,
                    }, conn)
                    if not log_id:
                        raise Exception(f"记录材料 {material_id} 日志失败")
                    results.append({'material_id': material_id, 'new_quantity': new_qty, 'log_id': log_id})
                conn.commit()
                return self._create_success_response(data={'results': results}, message='库存已批量更新')
            except Exception as e:
                conn.rollback()
                return self._create_error_response(f"批量更新库存失败: {str(e)}")
            finally:
                if conn and conn.is_connected():
                    conn.close()
        except Exception as e:
            return self._create_error_response(f"批量更新库存失败: {str(e)}")

    def __init__(self):
        super().__init__()
        self.material_dao = 材料DAO()
        self.stock_log_dao = 库存日志DAO()
        self.purchase_dao = 采购清单DAO()

    # ===== 材料查询 =====
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

    def get_material_detail(self, material_id: int, log_limit: int = 100) -> Dict[str, Any]:
        try:
            row = self.material_dao.get_by_id(material_id)
            if not row:
                return self._create_error_response("材料不存在")
            logs = self.stock_log_dao.get_logs_by_material(material_id, limit=log_limit)
            return self._create_success_response(data={"material": row, "logs": logs})
        except Exception as e:
            return self._create_error_response(f"获取材料详情失败: {str(e)}")

    # ===== 参数设置 =====
    def set_safety_stock(self, material_id: int, safety_stock: float) -> Dict[str, Any]:
        try:
            val = float(safety_stock)
            if val < 0:
                return self._create_error_response("安全库存不能为负数")
            ok = self.material_dao.update(material_id, {"安全库存": val})
            if not ok:
                return self._create_error_response("更新安全库存失败")
            return self._create_success_response(message="已更新安全库存")
        except Exception as e:
            return self._create_error_response(f"更新安全库存失败: {str(e)}")

    def set_unit_price(self, material_id: int, unit_price: float) -> Dict[str, Any]:
        try:
            val = float(unit_price)
            if val < 0:
                return self._create_error_response("单价不能为负数")
            ok = self.material_dao.update(material_id, {"标准单价": val})
            if not ok:
                return self._create_error_response("更新单价失败")
            return self._create_success_response(message="已更新标准单价")
        except Exception as e:
            return self._create_error_response(f"更新标准单价失败: {str(e)}")

    def list_material_logs(self, material_id: int, limit: int = 100) -> Dict[str, Any]:
        try:
            logs = self.stock_log_dao.get_logs_by_material(material_id, limit=limit)
            return self._create_success_response(data={"items": logs})
        except Exception as e:
            return self._create_error_response(f"获取库存日志失败: {str(e)}")

    def query_stock_logs(self, material_id: Optional[int] = None, reference_kw: Optional[str] = None,
                         days: int = 30, limit: int = 500) -> Dict[str, Any]:
        """库存变动历史查询（支持材料、关联关键字、时间范围）"""
        try:
            days = int(days or 30)
            if days <= 0:
                days = 30
            limit = max(1, min(int(limit or 500), 1000))
            mid = int(material_id) if material_id else None
            logs = self.stock_log_dao.search_logs(material_id=mid, reference_kw=reference_kw, days=days, limit=limit)
            return self._create_success_response(data={"items": logs})
        except Exception as e:
            return self._create_error_response(f"查询库存日志失败: {str(e)}")

    def update_stock_level(self, material_id: int, change_quantity: float, 
                         change_type: str, reference_id: str, operator_id: int,
                         note: str = "") -> Dict[str, Any]:
        """
        更新库存水平并记录日志
        这是一个关键的业务操作，确保库存变动的可追溯性。
        """
        try:
            # 获取当前材料信息
            material = self.material_dao.get_by_id(material_id)
            if not material:
                return self._create_error_response("材料不存在")

            # 计算新的库存数量（兼容 Decimal/float）
            current_qty = float(material.get('库存数量') or 0)
            delta = float(change_quantity)
            new_quantity = current_qty + delta
            if new_quantity < 0:
                return self._create_error_response("库存数量不能为负")

            # 在事务中更新库存和记录日志
            db_manager = DatabaseManager()
            conn = db_manager.get_connection()
            if conn is None:
                return self._create_error_response("无法获取数据库连接")

            try:
                conn.start_transaction()

                # 更新材料库存
                update_success = self.material_dao.update_with_connection(
                    material_id, {'库存数量': new_quantity}, conn
                )
                if not update_success:
                    raise Exception("更新库存数量失败")

                # 记录库存变动日志
                log_data = {
                    '材料id': material_id,
                    '库存变动数量': change_quantity,
                    '变动类型': change_type,
                    '关联的业务记录标识': reference_id,
                    '操作人': operator_id,
                    '备注': note
                }
                log_id = self.stock_log_dao.create_with_connection(log_data, conn)

                if not log_id:
                    raise Exception("记录库存日志失败")

                conn.commit()
                self.logger.info(f"库存更新成功: 材料ID {material_id}, 变动 {change_quantity}")

                return self._create_success_response(data={
                    'new_quantity': new_quantity,
                    'log_id': log_id
                })

            except Exception as e:
                conn.rollback()
                raise e
            finally:
                if conn and conn.is_connected():
                    conn.close()

        except Exception as e:
            return self._create_error_response(f"更新库存水平失败: {str(e)}")

    def check_low_stock_alerts(self) -> Dict[str, Any]:
        """检查低库存预警[5](@ref)"""
        try:
            low_stock_materials = self.material_dao.get_low_stock_materials()
            
            alerts = []
            for material in low_stock_materials:
                if material['库存数量'] <= material['安全库存']:
                    alerts.append({
                        'material_id': material['材料id'],
                        'material_name': material['材料名称'],
                        'current_stock': material['库存数量'],
                        'safety_stock': material['安全库存'],
                        'alert_level': 'CRITICAL' if material['库存数量'] == 0 else 'WARNING'
                    })

            return self._create_success_response(data={'alerts': alerts})

        except Exception as e:
            return self._create_error_response(f"检查低库存预警失败: {str(e)}")

    def get_inventory_report(self) -> Dict[str, Any]:
        """生成库存报告（包含统计信息）"""
        try:
            all_materials = self.material_dao.get_all()
            # 统一浮点计算，避免 Decimal 混算
            def f(v):
                try:
                    return float(v)
                except Exception:
                    return 0.0
            total_value = sum(f(m.get('库存数量')) * f(m.get('标准单价')) for m in all_materials)
            low_stock_count = len([m for m in all_materials 
                                 if f(m.get('库存数量')) <= f(m.get('安全库存'))])
            out_of_stock_count = len([m for m in all_materials 
                                   if f(m.get('库存数量')) == 0.0])

            report = {
                'total_materials': len(all_materials),
                'total_inventory_value': round(total_value, 2),
                'low_stock_items': low_stock_count,
                'out_of_stock_items': out_of_stock_count,
                'materials': all_materials
            }

            return self._create_success_response(data=report)

        except Exception as e:
            return self._create_error_response(f"生成库存报告失败: {str(e)}")