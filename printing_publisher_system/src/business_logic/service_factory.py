from src.business_logic.printing_service import PrintingTaskService
from src.business_logic.inventory_service import InventoryService
from src.business_logic.employee_service import EmployeeService
from src.business_logic.book_service import BookService
from src.business_logic.material_supplier_service import MaterialSupplierService
from src.business_logic.purchase_service import PurchaseService

class ServiceFactory:
    """
    服务工厂类，统一创建和管理业务逻辑服务实例。
    使用单例模式确保服务实例的唯一性。
    """
    _instance = None
    _services = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True

    def get_printing_task_service(self) -> PrintingTaskService:
        """获取印刷任务服务实例"""
        if 'printing_task' not in self._services:
            self._services['printing_task'] = PrintingTaskService()
        return self._services['printing_task']

    def get_inventory_service(self) -> InventoryService:
        """获取库存管理服务实例"""
        if 'inventory' not in self._services:
            self._services['inventory'] = InventoryService()
        return self._services['inventory']

    def get_employee_service(self) -> EmployeeService:
        """获取员工管理服务实例"""
        if 'employee' not in self._services:
            self._services['employee'] = EmployeeService()
        return self._services['employee']

    def get_book_service(self) -> BookService:
        """获取书籍与版本服务实例"""
        if 'book' not in self._services:
            self._services['book'] = BookService()
        return self._services['book']

    def get_material_supplier_service(self) -> MaterialSupplierService:
        """获取材料与供应商服务实例"""
        if 'material_supplier' not in self._services:
            self._services['material_supplier'] = MaterialSupplierService()
        return self._services['material_supplier']

    def get_purchase_service(self) -> PurchaseService:
        """获取采购管理服务实例"""
        if 'purchase' not in self._services:
            self._services['purchase'] = PurchaseService()
        return self._services['purchase']

    def clear_cache(self):
        """清空服务缓存（主要用于测试）"""
        self._services.clear()

# 创建全局工厂实例
service_factory = ServiceFactory()