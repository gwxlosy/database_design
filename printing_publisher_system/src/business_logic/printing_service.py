from datetime import datetime, date
from typing import Dict, Any, Optional, List

from src.database.daos import (
    印刷任务DAO, 员工DAO, 书籍核心信息DAO, 材料DAO, 
    材料供应商关联DAO, 采购清单DAO, 库存日志DAO, DatabaseManager
)
from src.business_logic.base_service import BaseService
from src.database.models import PrintingTaskModel, PurchaseModel, model_to_db_dict

class PrintingTaskService(BaseService):
    """
    印刷任务业务逻辑服务，封装所有与印刷任务相关的业务规则和操作。
    """

    # ===== 任务需求与手动完结 =====
    def get_task_requirements(self, task_id: int) -> Dict[str, Any]:
        """返回指定任务的材料需求清单与库存对比。
        返回结构：{ items: [{material_id, material_name, unit?, required_qty, current_stock, shortage}], total_required }
        """
        try:
            task = self.task_dao.get_by_id(task_id)
            if not task:
                return self._create_error_response("任务不存在")
            qty = int(task.get('印刷数量') or 0)
            ctx = {'印刷数量': qty, '书籍id': task.get('书籍id')}
            required = self._calculate_material_requirements(ctx)
            items: List[Dict[str, Any]] = []
            total_required: float = 0.0
            for mid, rqty in (required or {}).items():
                mat = self.material_dao.get_by_id(int(mid)) or {}
                stock = float(mat.get('库存数量') or 0)
                shortage = max(0.0, float(rqty) - stock)
                items.append({
                    'material_id': int(mid),
                    'material_name': mat.get('材料名称') or f'材料#{mid}',
                    'unit': mat.get('计量单位'),
                    'required_qty': float(rqty),
                    'current_stock': stock,
                    'shortage': shortage,
                })
                total_required += float(rqty)
            return self._create_success_response(data={'items': items, 'total_required': total_required, 'task': task})
        except Exception as e:
            return self._create_error_response(f"获取任务需求失败: {str(e)}")

    def complete_task_manual(self, task_id: int, operator_id: int, completed_date: Optional[str] = None) -> Dict[str, Any]:
        """员工手动点击完成任务：
        - 校验任务存在且未取消
        - 计算材料需求，若库存充足则逐项出库，并将任务状态置为已完成，写入完成日期
        - 若库存不足，返回短缺清单
        """
        try:
            task = self.task_dao.get_by_id(task_id)
            if not task:
                return self._create_error_response("任务不存在")
            if task.get('任务状态') == '已取消':
                return self._create_error_response("任务已取消，无法完成")
            if task.get('任务状态') == '已完成':
                return self._create_error_response("任务已完成，无需重复操作")
            if not operator_id:
                return self._create_error_response("无法确定库存操作人")

            qty = int(task.get('印刷数量') or 0)
            ctx = {'印刷数量': qty, '书籍id': task.get('书籍id')}
            required = self._calculate_material_requirements(ctx)

            # 先校验库存是否充足
            shortages: List[Dict[str, Any]] = []
            for mid, rqty in required.items():
                mat = self.material_dao.get_by_id(int(mid)) or {}
                stock = float(mat.get('库存数量') or 0)
                if stock < float(rqty):
                    shortages.append({
                        'material_id': int(mid),
                        'material_name': mat.get('材料名称') or f'材料#{mid}',
                        'required_qty': float(rqty),
                        'current_stock': stock,
                        'shortage': float(rqty) - stock,
                    })
            if shortages:
                return {'success': False, 'message': '库存不足，无法完成任务', 'data': {'shortages': shortages}}

            # 库存充足：批量出库（单事务）
            from src.business_logic.inventory_service import InventoryService
            inv = InventoryService()
            ref = f"task:{task_id}"
            changes = []
            for mid, rqty in required.items():
                delta = -float(rqty)
                if delta == 0:
                    continue
                changes.append({
                    'material_id': int(mid),
                    'delta': delta,
                    'change_type': '出库',
                    'reference': ref,
                    'operator_id': int(operator_id),
                    'note': '任务手动完结扣减',
                })
            if changes:
                res = inv.batch_update_stock(changes)
                if not res.get('success'):
                    return self._create_error_response(res.get('message', '批量出库失败'))

            # 更新任务状态
            update_data = {'任务状态': '已完成'}
            if completed_date:
                update_data['实际完成日期'] = completed_date
            ok = self.task_dao.update(task_id, update_data)
            if not ok:
                return self._create_error_response("任务状态更新失败")
            return self._create_success_response(message='任务已完成，材料已扣减')
        except Exception as e:
            return self._create_error_response(f"手动完成任务失败: {str(e)}")

    def __init__(self):
        super().__init__()
        self.task_dao = 印刷任务DAO()
        self.employee_dao = 员工DAO()
        self.book_dao = 书籍核心信息DAO()
        self.material_dao = 材料DAO()
        self.material_supplier_dao = 材料供应商关联DAO()
        self.purchase_dao = 采购清单DAO()
        self.stock_log_dao = 库存日志DAO()

    def submit_printing_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        提交新的印刷任务（核心业务流程）
        这是一个事务性操作，包含业务规则验证、任务创建、采购需求生成等步骤。
        """
        self.logger.info("开始提交印刷任务流程")

        # 1. 业务规则验证
        validation_result = self._validate_task_data(task_data)
        if not validation_result['success']:
            return validation_result

        # 2. 验证关联数据是否存在
        associate_validation = self._validate_associated_data(task_data)
        if not associate_validation['success']:
            return associate_validation

        # 获取数据库连接以开启事务
        db_manager = DatabaseManager()
        conn = db_manager.get_connection()
        if conn is None:
            return self._create_error_response("无法获取数据库连接")

        try:
            # 开始事务
            conn.start_transaction()
            self.logger.debug("数据库事务开始")

            # 3. 创建印刷任务记录
            task_id = self.task_dao.create_with_connection(task_data, conn)
            if not task_id:
                raise Exception("创建印刷任务记录失败")

            # 4. 生成采购需求（基于印刷数量和材料计算）
            purchase_result = self._generate_purchase_requirements(task_id, task_data, conn)
            if not purchase_result['success']:
                raise Exception(f"生成采购需求失败: {purchase_result['message']}")

            # 5. 记录初始库存日志（如果需要）
            log_result = self._log_initial_task_creation(task_id, task_data, conn)
            if not log_result['success']:
                self.logger.warning(f"记录初始日志时出现问题: {log_result['message']}")

            # 提交事务
            conn.commit()
            self.logger.info(f"印刷任务提交成功，任务ID: {task_id}")

            return self._create_success_response(
                data={'task_id': task_id},
                message=f"印刷任务提交成功！任务ID: {task_id}"
            )

        except Exception as e:
            # 回滚事务
            conn.rollback()
            self.logger.error(f"提交印刷任务事务失败，已回滚: {e}")
            return self._create_error_response(f"系统错误: {str(e)}")
        finally:
            if conn and conn.is_connected():
                conn.close()

    def _validate_task_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证任务数据的业务规则"""
        # 必需字段验证
        required_fields = ['员工id', '书籍id', '预计完成日期', '印刷数量']
        missing_check = self._validate_required_fields(task_data, required_fields)
        if missing_check:
            return missing_check

        # 业务规则验证
        if task_data['印刷数量'] <= 0:
            return self._create_error_response("印刷数量必须大于0")

        due_date = self._normalize_date(task_data['预计完成日期'])
        if due_date is None:
            return self._create_error_response("预计完成日期格式必须为 YYYY-MM-DD")

        # 将规范化后的日期写回，便于后续流程重用
        task_data['预计完成日期'] = due_date

        if due_date < datetime.now().date():
            return self._create_error_response("预计完成日期不能是过去的时间")

        return self._create_success_response()

    def _validate_associated_data(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """验证关联数据的存在性和有效性"""
        try:
            # 验证员工存在且在职
            employee = self.employee_dao.get_by_id(task_data['员工id'])
            if not employee or employee['在职状态'] != '在职':
                return self._create_error_response("指定的员工不存在或已离职")

            # 验证书籍存在
            book = self.book_dao.get_by_id(task_data['书籍id'])
            if not book:
                return self._create_error_response("指定的书籍不存在")

            return self._create_success_response()

        except Exception as e:
            return self._create_error_response(f"验证关联数据时发生错误: {str(e)}")

    def _generate_purchase_requirements(self, task_id: int, task_data: Dict[str, Any], conn) -> Dict[str, Any]:
        """
        根据印刷任务生成采购需求
        这里包含复杂的业务逻辑：计算所需材料、选择最优供应商等。
        """
        try:
            # 1. 根据书籍和印刷数量计算材料需求
            # 示例：假设每本书需要0.5kg特定纸张
            materials_required = self._calculate_material_requirements(task_data)

            purchase_orders = []
            missing_materials: list[int] = []
            for material_id, required_qty in materials_required.items():
                # 2. 为每种材料选择最优供应商
                best_supplier = self._select_optimal_supplier(material_id, required_qty)
                if not best_supplier:
                    missing_materials.append(material_id)
                    continue

                # 3. 创建采购记录
                unit_price = float(best_supplier.get('供应商提供的材料单价') or 0)
                purchase_data = {
                    '印刷任务id': task_id,
                    '材料供应商关联id': best_supplier['材料供应商关联id'],
                    '采购数量': float(required_qty),
                    '总成本': round(float(required_qty) * unit_price, 2),
                    '采购状态': '待采购'
                }

                purchase_id = self.purchase_dao.create_with_connection(purchase_data, conn)
                if purchase_id:
                    purchase_orders.append(purchase_id)

            if missing_materials:
                # 组织更友好的错误信息，包含材料名称
                names = []
                for mid in missing_materials:
                    m = self.material_dao.get_by_id(mid)
                    names.append(f"{m.get('材料名称')}(ID:{mid})" if m else f"ID:{mid}")
                msg = "以下材料没有可用供应商：" + ", ".join(names) + "。请到‘材料/供应商’维护关联或设为合作中。"
                return self._create_error_response(msg)

            return self._create_success_response(data={'purchase_orders': purchase_orders})

        except Exception as e:
            self.logger.error(f"生成采购需求时发生错误: {e}")
            return self._create_error_response(f"生成采购需求失败: {str(e)}")

    def _calculate_material_requirements(self, task_data: Dict[str, Any]) -> Dict[int, float]:
        """
        计算完成印刷任务所需的材料清单和数量
        这是一个简化的示例，实际逻辑可能更复杂。
        """
        # 示例逻辑：假设我们知道印刷该书籍需要哪些材料
        # 实际应用中，这里可能会有复杂的计算公式
        materials_needed = {
            1: task_data['印刷数量'] * 0.5,  # 材料ID 1' 纸张，每本需要0.5kg
            2: task_data['印刷数量'] * 0.1   # 材料ID'2' 油墨，每本需要0.1kg
        }
        return materials_needed

    def _select_optimal_supplier(self, material_id: int, quantity: float) -> Optional[Dict[str, Any]]:
        """为指定材料选择最优供应商（基于价格、供应能力等）"""
        try:
            # 获取所有能提供该材料的供应商
            suppliers = self.material_supplier_dao.get_material_suppliers(material_id)

            if not suppliers:
                return None

            # 简单的选择策略：优先选择首选供应商，然后选择单价最低的
            preferred_suppliers = [s for s in suppliers if s['是否为首选供应商'] == '是']
            if preferred_suppliers:
                # 在首选供应商中选择单价最低的
                return min(preferred_suppliers, key=lambda x: x['供应商提供的材料单价'])
            else:
                # 没有首选供应商时选择单价最低的
                return min(suppliers, key=lambda x: x['供应商提供的材料单价'])

        except Exception as e:
            self.logger.error(f"选择供应商时发生错误: {e}")
            return None

    def get_task_with_full_details(self, task_id: int) -> Dict[str, Any]:
        """获取任务的完整详情（包括所有关联数据）"""
        try:
            task = self.task_dao.get_by_id(task_id)
            if not task:
                return self._create_error_response("任务不存在")

            # 获取关联的员工信息
            employee = self.employee_dao.get_by_id(task['员工id'])
            # 获取书籍信息
            book = self.book_dao.get_by_id(task['书籍id'])
            # 获取采购信息
            purchases = self.purchase_dao.get_purchases_by_task(task_id)

            result_data = {
                'task_info': task,
                'employee_info': employee,
                'book_info': book,
                'purchase_orders': purchases
            }

            return self._create_success_response(data=result_data)

        except Exception as e:
            return self._create_error_response(f"获取任务详情失败: {str(e)}")

    def list_tasks_page(self, page: int = 1, page_size: int = 10, status: Optional[str] = None) -> Dict[str, Any]:
        """分页查询印刷任务，支持按状态过滤"""
        try:
            filters = {"任务状态": status} if status else None
            page_data = self.task_dao.get_page(filters=filters, order_by="任务提交日期 DESC", page=page, page_size=page_size)
            return self._create_success_response(data=page_data)
        except Exception as e:
            return self._create_error_response(f"获取任务分页失败: {str(e)}")

    def update_task_status(self, task_id: int, new_status: str, 
                         actual_completion_date: str = None,
                         operator_id: Optional[int] = None) -> Dict[str, Any]:
        """更新任务状态（包含状态流转验证）。
        当状态变更为“已完成”时：按任务印刷数量计算材料实际消耗，执行材料出库并记录库存日志。
        - 出库参考号：task:{task_id}
        - 操作人：传入的 operator_id；若未传，回退为任务的员工id。
        """
        valid_statuses = ['待开始', '进行中', '已完成', '已取消']
        if new_status not in valid_statuses:
            return self._create_error_response(f"无效的状态值。必须是: {', '.join(valid_statuses)}")

        try:
            # 若标记完成，先进行材料出库校验/执行，成功后再更新状态，避免状态与库存不一致
            if new_status == '已完成':
                task = self.task_dao.get_by_id(task_id)
                if not task:
                    return self._create_error_response("任务不存在")
                # 计算材料消耗（基于当前简化规则）
                qty = int(task.get('印刷数量') or 0)
                task_ctx = {'印刷数量': qty, '书籍id': task.get('书籍id')}
                materials_required = self._calculate_material_requirements(task_ctx)
                # 操作人
                op_id = int(operator_id) if operator_id else int(task.get('员工id') or 0)
                if not op_id:
                    return self._create_error_response("无法确定库存操作人，请传入 operator_id 或确保任务有员工id")
                from src.business_logic.inventory_service import InventoryService
                inv = InventoryService()
                ref = f"task:{task_id}"
                changes = []
                for material_id, required_qty in materials_required.items():
                    delta = -float(required_qty)
                    if delta == 0:
                        continue
                    changes.append({
                        'material_id': int(material_id),
                        'delta': delta,
                        'change_type': '出库',
                        'reference': ref,
                        'operator_id': op_id,
                        'note': '任务完成实际消耗'
                    })
                if changes:
                    res = inv.batch_update_stock(changes)
                    if not res.get('success'):
                        return self._create_error_response(res.get('message', '批量出库失败'))

            # 出库成功或非完成状态，更新任务状态
            update_data = {'任务状态': new_status}
            if new_status == '已完成' and actual_completion_date:
                update_data['实际完成日期'] = actual_completion_date

            success = self.task_dao.update(task_id, update_data)
            if success:
                return self._create_success_response(message="任务状态更新成功")
            else:
                return self._create_error_response("任务状态更新失败")

        except Exception as e:
            return self._create_error_response(f"更新任务状态时发生错误: {str(e)}")

    def _normalize_date(self, value: Any) -> Optional[date]:
        """
        将传入的日期字段统一转换为 date 对象。
        支持 date / datetime / ISO 字符串，其他类型返回 None。
        """
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).date()
            except ValueError:
                return None
        return None

    def _log_initial_task_creation(self, task_id: int, task_data: Dict[str, Any], conn) -> Dict[str, Any]:
        """
        记录任务创建时的初始日志。
        当前实现为占位/简单成功返回，后续如需扩展可在此处
        使用 self.stock_log_dao 等进行真实记录。
        """
        # 为了保持事务流程完整，暂时直接返回成功
        return self._create_success_response()