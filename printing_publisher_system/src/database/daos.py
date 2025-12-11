# src/database/dao.py
"""
印刷出版商数据库管理系统的数据访问层 (DAO)
提供对所有数据库表的CRUD操作和业务特定查询
"""
import mysql.connector
from mysql.connector import Error, pooling
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
import contextlib
from src.config.settings import DB_CONFIG

# 配置日志
from src.config.settings import LOG_LEVEL
logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

class DatabaseManager:
    """
    数据库连接管理器，使用连接池提高性能
    采用单例模式确保全局只有一个连接池实例
    """
    _instance = None
    _connection_pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def _initialize_pool(cls):
        """初始化数据库连接池"""
        try:
            pool_kwargs = dict(DB_CONFIG)
            pool_kwargs.setdefault('autocommit', False)
            cls._connection_pool = pooling.MySQLConnectionPool(
                pool_name="printing_pool",
                pool_size=5,
                **pool_kwargs
            )
            logger.info("数据库连接池初始化成功")
        except Error as e:
            logger.error(f"数据库连接池初始化失败: {e}")
            raise
    
    def get_connection(self):
        """从连接池获取数据库连接，若未初始化则懒加载初始化（支持在应用启动时无数据库的场景）"""
        try:
            if self._connection_pool is None:
                self._initialize_pool()
            return self._connection_pool.get_connection()
        except Error as e:
            logger.error(f"获取数据库连接失败: {e}")
            raise
    
    @contextlib.contextmanager
    def get_cursor(self, dictionary=True):
        """
        上下文管理器，自动处理连接和游标的生命周期
        使用示例:
        with db_manager.get_cursor() as cursor:
            cursor.execute("SELECT * FROM 员工表")
            result = cursor.fetchall()
        """
        conn = self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor(dictionary=dictionary)
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

class BaseDAO:
    """
    DAO基类，提供通用的CRUD操作方法
    所有具体表的DAO类都应继承此类
    """
    
    def __init__(self, table_name: str, id_column: str = "id"):
        self.db = DatabaseManager()
        self.table_name = table_name
        self.id_column = id_column
    
    def create(self, data: Dict[str, Any]) -> Optional[int]:
        """创建新记录（自动管理连接）"""
        if not data:
            raise ValueError("创建记录时数据不能为空")
        
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, tuple(data.values()))
            return cursor.lastrowid

    def create_with_connection(self, data: Dict[str, Any], conn) -> Optional[int]:
        """在外部事务中创建记录（不提交，由调用方控制事务）"""
        if not data:
            raise ValueError("创建记录时数据不能为空")
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, tuple(data.values()))
            return cursor.lastrowid
    
    def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取记录"""
        query = f"SELECT * FROM {self.table_name} WHERE {self.id_column} = %s"
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (record_id,))
            return cursor.fetchone()
    
    def get_all(self, filters: Dict[str, Any] = None, 
                order_by: str = None, 
                limit: int = None) -> List[Dict[str, Any]]:
        """获取所有记录，支持过滤和排序"""
        where_clause = ""
        params = []
        
        if filters:
            where_conditions = []
            for key, value in filters.items():
                if value is not None:
                    where_conditions.append(f"{key} = %s")
                    params.append(value)
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
        
        order_clause = f"ORDER BY {order_by}" if order_by else ""
        limit_clause = f"LIMIT {limit}" if limit else ""
        
        query = f"SELECT * FROM {self.table_name} {where_clause} {order_clause} {limit_clause}"
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def count(self, filters: Dict[str, Any] = None) -> int:
        """统计满足过滤条件的记录总数"""
        where_clause = ""
        params = []
        if filters:
            where_conditions = []
            for key, value in filters.items():
                if value is not None:
                    where_conditions.append(f"{key} = %s")
                    params.append(value)
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
        query = f"SELECT COUNT(*) AS cnt FROM {self.table_name} {where_clause}"
        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return int(row["cnt"]) if row else 0

    def get_page(self, filters: Dict[str, Any] = None, order_by: str = None, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """分页查询，返回 {items,total,page,page_size}"""
        page = max(int(page or 1), 1)
        page_size = max(min(int(page_size or 10), 200), 1)
        total = self.count(filters)
        offset = (page - 1) * page_size
        where_clause = ""
        params = []
        if filters:
            where_conditions = []
            for key, value in filters.items():
                if value is not None:
                    where_conditions.append(f"{key} = %s")
                    params.append(value)
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
        order_clause = f"ORDER BY {order_by}" if order_by else ""
        query = f"SELECT * FROM {self.table_name} {where_clause} {order_clause} LIMIT %s OFFSET %s"
        with self.db.get_cursor() as cursor:
            cursor.execute(query, params + [page_size, offset])
            items = cursor.fetchall()
        return {"items": items, "total": total, "page": page, "page_size": page_size}
    
    def update(self, record_id: int, data: Dict[str, Any]) -> bool:
        """更新记录（自动管理连接）"""
        if not data:
            raise ValueError("更新数据不能为空")
        
        set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
        query = f"UPDATE {self.table_name} SET {set_clause} WHERE {self.id_column} = %s"
        params = tuple(data.values()) + (record_id,)
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount > 0

    def update_with_connection(self, record_id: int, data: Dict[str, Any], conn) -> bool:
        """在外部事务中更新记录（不提交，由调用方控制事务）"""
        if not data:
            raise ValueError("更新数据不能为空")
        set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
        query = f"UPDATE {self.table_name} SET {set_clause} WHERE {self.id_column} = %s"
        params = tuple(data.values()) + (record_id,)
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, params)
            return cursor.rowcount > 0
    
    def delete(self, record_id: int) -> bool:
        """删除记录（物理删除，慎用）"""
        query = f"DELETE FROM {self.table_name} WHERE {self.id_column} = %s"
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (record_id,))
            return cursor.rowcount > 0

# 具体表的DAO类实现
class 员工DAO(BaseDAO):
    """员工表数据访问对象"""
    
    def __init__(self):
        super().__init__("员工表", "员工id")
    
    def get_active_employees(self) -> List[Dict[str, Any]]:
        """获取所有在职员工"""
        return self.get_all(filters={"在职状态": "在职"}, order_by="入职日期 DESC")
    
    def get_employees_by_position(self, position: str) -> List[Dict[str, Any]]:
        """根据职位获取员工"""
        return self.get_all(filters={"职位": position, "在职状态": "在职"})

    def get_page_by_filters(self, name_kw: Optional[str] = None, status: Optional[str] = None,
                            position: Optional[str] = None, order_by: str = "入职日期 DESC",
                            page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """分页+筛选+姓名模糊查询"""
        page = max(int(page or 1), 1)
        page_size = max(min(int(page_size or 10), 200), 1)
        where_conditions = []
        params: List[Any] = []
        if name_kw:
            where_conditions.append("员工姓名 LIKE %s")
            params.append(f"%{name_kw}%")
        if status:
            where_conditions.append("在职状态 = %s")
            params.append(status)
        if position:
            where_conditions.append("职位 = %s")
            params.append(position)
        where_clause = ("WHERE " + " AND ".join(where_conditions)) if where_conditions else ""
        # count
        count_sql = f"SELECT COUNT(*) AS cnt FROM {self.table_name} {where_clause}"
        with self.db.get_cursor() as cursor:
            cursor.execute(count_sql, params)
            row = cursor.fetchone()
            total = int(row["cnt"]) if row else 0
        # items
        offset = (page - 1) * page_size
        order_clause = f"ORDER BY {order_by}" if order_by else ""
        items_sql = f"SELECT * FROM {self.table_name} {where_clause} {order_clause} LIMIT %s OFFSET %s"
        with self.db.get_cursor() as cursor:
            cursor.execute(items_sql, params + [page_size, offset])
            items = cursor.fetchall()
        return {"items": items, "total": total, "page": page, "page_size": page_size}
    
    def update_employment_status(self, employee_id: int, new_status: str) -> bool:
        """更新员工在职状态"""
        valid_statuses = ["在职", "离职"]
        if new_status not in valid_statuses:
            raise ValueError(f"状态必须是: {valid_statuses}")
        
        return self.update(employee_id, {"在职状态": new_status})

class 书籍核心信息DAO(BaseDAO):
    """书籍核心信息表数据访问对象"""
    
    def __init__(self):
        super().__init__("书籍核心信息表", "书籍id")
    
    def get_books_by_author(self, author: str) -> List[Dict[str, Any]]:
        """根据作者获取书籍"""
        return self.get_all(filters={"作者": author}, order_by="书籍名称")
    
    def search_books_by_name(self, book_name: str) -> List[Dict[str, Any]]:
        """根据书籍名称搜索（模糊匹配）"""
        query = "SELECT * FROM 书籍核心信息表 WHERE 书籍名称 LIKE %s"
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (f"%{book_name}%",))
            return cursor.fetchall()

class 书籍版本DAO(BaseDAO):
    """书籍版本表数据访问对象"""
    
    def __init__(self):
        super().__init__("书籍版本表", "书籍版本id")
    
    def get_versions_by_book_id(self, book_id: int) -> List[Dict[str, Any]]:
        """获取指定书籍的所有版本"""
        return self.get_all(filters={"书籍id": book_id}, order_by="版本创建日期 DESC")
    
    def get_version_by_isbn(self, isbn: str) -> Optional[Dict[str, Any]]:
        """根据ISBN获取版本信息"""
        query = "SELECT * FROM 书籍版本表 WHERE 国际标准书号 = %s"
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (isbn,))
            return cursor.fetchone()

class 印刷任务DAO(BaseDAO):
    """印刷任务表数据访问对象"""
    
    def __init__(self):
        super().__init__("印刷任务表", "印刷任务id")
    
    def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """根据状态获取任务"""
        valid_statuses = ["待开始", "进行中", "已完成", "已取消"]
        if status not in valid_statuses:
            raise ValueError(f"任务状态必须是: {valid_statuses}")
        
        return self.get_all(filters={"任务状态": status}, order_by="任务提交日期 DESC")
    
    def get_tasks_by_employee(self, employee_id: int) -> List[Dict[str, Any]]:
        """获取员工负责的所有任务"""
        return self.get_all(filters={"员工id": employee_id}, order_by="任务提交日期 DESC")
    
    def update_task_status(self, task_id: int, new_status: str, 
                          actual_completion_date: str = None) -> bool:
        """更新任务状态"""
        update_data = {"任务状态": new_status}
        if new_status == "已完成" and actual_completion_date:
            update_data["实际完成日期"] = actual_completion_date
        
        return self.update(task_id, update_data)
    
    def get_overdue_tasks(self) -> List[Dict[str, Any]]:
        """获取超期未完成的任务"""
        query = """
            SELECT * FROM 印刷任务表 
            WHERE 任务状态 IN ('待开始', '进行中') 
            AND 预计完成日期 < CURDATE() 
            ORDER BY 预计完成日期 ASC
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()

class 材料DAO(BaseDAO):
    """材料表数据访问对象"""
    
    def __init__(self):
        super().__init__("材料表", "材料id")
    
    def get_low_stock_materials(self) -> List[Dict[str, Any]]:
        """获取低于安全库存的材料"""
        query = "SELECT * FROM 材料表 WHERE 库存数量 <= 安全库存 AND 安全库存 > 0"
        with self.db.get_cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    
    def update_stock_quantity(self, material_id: int, new_quantity: Decimal) -> bool:
        """更新材料库存数量"""
        if new_quantity < 0:
            raise ValueError("库存数量不能为负数")
        
        return self.update(material_id, {"库存数量": float(new_quantity)})
    
    def get_materials_by_name(self, material_name: str) -> List[Dict[str, Any]]:
        """根据材料名称搜索"""
        query = "SELECT * FROM 材料表 WHERE 材料名称 LIKE %s"
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (f"%{material_name}%",))
            return cursor.fetchall()

class 供应商DAO(BaseDAO):
    """供应商表数据访问对象"""
    
    def __init__(self):
        super().__init__("供应商表", "供应商id")
    
    def get_active_suppliers(self) -> List[Dict[str, Any]]:
        """获取合作中的供应商"""
        return self.get_all(filters={"合作状态": "合作中"}, order_by="供应商名称")
    
    def get_suppliers_by_material(self, material_id: int) -> List[Dict[str, Any]]:
        """获取能提供指定材料的供应商"""
        query = """
            SELECT s.*, ms.供应商提供的材料单价, ms.是否为首选供应商
            FROM 供应商表 s
            JOIN 材料供应商关联表 ms ON s.供应商id = ms.供应商id
            WHERE ms.材料id = %s AND s.合作状态 = '合作中'
            ORDER BY ms.是否为首选供应商 DESC, ms.供应商提供的材料单价 ASC
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (material_id,))
            return cursor.fetchall()

class 材料供应商关联DAO(BaseDAO):
    """材料-供应商关联表数据访问对象"""
    
    def __init__(self):
        super().__init__("材料供应商关联表", "材料供应商关联id")
    
    def get_preferred_supplier_for_material(self, material_id: int) -> Optional[Dict[str, Any]]:
        """获取材料的首选供应商"""
        query = """
            SELECT ms.*, s.供应商名称, s.供应商联系人, s.联系电话
            FROM 材料供应商关联表 ms
            JOIN 供应商表 s ON ms.供应商id = s.供应商id
            WHERE ms.材料id = %s AND ms.是否为首选供应商 = '是' AND s.合作状态 = '合作中'
            LIMIT 1
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (material_id,))
            return cursor.fetchone()
    
    def get_material_suppliers(self, material_id: int) -> List[Dict[str, Any]]:
        """获取材料的所有供应商"""
        query = """
            SELECT ms.*, s.供应商名称, s.供应商联系人, s.联系电话
            FROM 材料供应商关联表 ms
            JOIN 供应商表 s ON ms.供应商id = s.供应商id
            WHERE ms.材料id = %s AND s.合作状态 = '合作中'
            ORDER BY ms.是否为首选供应商 DESC, ms.供应商提供的材料单价 ASC
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (material_id,))
            return cursor.fetchall()

class 采购清单DAO(BaseDAO):
    """采购清单表数据访问对象"""
    
    def __init__(self):
        super().__init__("采购清单表", "采购记录id")
    
    def get_purchases_by_task(self, task_id: int) -> List[Dict[str, Any]]:
        """获取任务的采购清单"""
        return self.get_all(filters={"印刷任务id": task_id}, order_by="采购日期 DESC")
    
    def get_purchases_by_status(self, status: str) -> List[Dict[str, Any]]:
        """根据状态获取采购记录"""
        return self.get_all(filters={"采购状态": status}, order_by="采购日期 DESC")
    
    def update_purchase_status(self, purchase_id: int, new_status: str, 
                              receipt_date: str = None) -> bool:
        """更新采购状态"""
        update_data = {"采购状态": new_status}
        if new_status == "已收货" and receipt_date:
            update_data["材料收货日期"] = receipt_date
        
        return self.update(purchase_id, update_data)

class 用户表DAO(BaseDAO):
    """用户表数据访问对象"""
    
    def __init__(self):
        super().__init__("用户表", "用户id")
    
    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """根据用户名获取用户"""
        query = "SELECT * FROM 用户表 WHERE 用户名 = %s"
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (username,))
            return cursor.fetchone()
    
    def get_users_by_position(self, position: str) -> List[Dict[str, Any]]:
        """根据职位获取用户"""
        return self.get_all(filters={"职位": position}, order_by="创建时间 DESC")

class 库存日志DAO(BaseDAO):
    """库存日志表数据访问对象"""
    
    def __init__(self):
        super().__init__("库存日志表", "库存日志id")
    
    def get_logs_by_material(self, material_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """获取材料的库存变动日志"""
        query = """
            SELECT sl.*, e.员工姓名 as 操作人姓名
            FROM 库存日志表 sl
            LEFT JOIN 员工表 e ON sl.操作人 = e.员工id
            WHERE sl.材料id = %s
            ORDER BY sl.变动时间 DESC
            LIMIT %s
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (material_id, limit))
            return cursor.fetchall()
    
    def get_recent_logs(self, days: int = 30) -> List[Dict[str, Any]]:
        """获取最近指定天数的库存日志"""
        query = """
            SELECT sl.*, m.材料名称, e.员工姓名 as 操作人姓名
            FROM 库存日志表 sl
            JOIN 材料表 m ON sl.材料id = m.材料id
            LEFT JOIN 员工表 e ON sl.操作人 = e.员工id
            WHERE sl.变动时间 >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
            ORDER BY sl.变动时间 DESC
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (days,))
            return cursor.fetchall()

# DAO工厂类，方便管理所有DAO实例
class DAOFactory:
    """
    DAO工厂类，采用单例模式管理所有DAO实例
    """
    _instance = None
    _daos = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_employee_dao(self) -> 员工DAO:
        """获取员工DAO实例"""
        if 'employee' not in self._daos:
            self._daos['employee'] = 员工DAO()
        return self._daos['employee']
    
    def get_book_dao(self) -> 书籍核心信息DAO:
        """获取书籍核心信息DAO实例"""
        if 'book' not in self._daos:
            self._daos['book'] = 书籍核心信息DAO()
        return self._daos['book']
    
    def get_printing_task_dao(self) -> 印刷任务DAO:
        """获取印刷任务DAO实例"""
        if 'printing_task' not in self._daos:
            self._daos['printing_task'] = 印刷任务DAO()
        return self._daos['printing_task']
    
    # 其他DAO的获取方法...
    def get_material_dao(self) -> 材料DAO:
        if 'material' not in self._daos:
            self._daos['material'] = 材料DAO()
        return self._daos['material']
    
    def get_supplier_dao(self) -> 供应商DAO:
        if 'supplier' not in self._daos:
            self._daos['supplier'] = 供应商DAO()
        return self._daos['supplier']

# 全局DAO工厂实例
dao_factory = DAOFactory()

# 测试代码
if __name__ == "__main__":
    # 测试数据库连接和基本操作
    try:
        # 测试员工DAO
        employee_dao = dao_factory.get_employee_dao()
        employees = employee_dao.get_all(limit=5)
        print(f"找到 {len(employees)} 条员工记录")
        
        # 测试材料DAO
        material_dao = dao_factory.get_material_dao()
        low_stock = material_dao.get_low_stock_materials()
        print(f"找到 {len(low_stock)} 种低库存材料")
        
        print("✅ DAO层测试通过！")
        
    except Exception as e:
        print(f"❌ DAO层测试失败: {e}")