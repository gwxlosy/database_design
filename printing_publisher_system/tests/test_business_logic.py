# test_database.py
import sys
import os
from datetime import datetime, timedelta
# 获取当前脚本的目录（tests目录），然后找到项目根目录（printing_publisher_system）
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)  # 将项目根目录添加到模块搜索路径的开头

import mysql.connector
import unittest
from unittest.mock import Mock, patch
from src.business_logic.printing_service import PrintingTaskService
from src.business_logic.service_factory import service_factory

class TestPrintingTaskService(unittest.TestCase):
    """印刷任务服务测试类"""

    def setUp(self):
        """测试前置设置"""
        self.printing_service = service_factory.get_printing_task_service()
        self.future_due_date = (datetime.now() + timedelta(days=30)).date().isoformat()
        
        # 模拟DAO层，避免真实数据库依赖
        self.printing_service.task_dao = Mock()
        self.printing_service.employee_dao = Mock()
        self.printing_service.book_dao = Mock()
        self.printing_service.material_supplier_dao = Mock()
        self.printing_service.purchase_dao = Mock()
        self.printing_service.stock_log_dao = Mock()

    def test_submit_task_with_valid_data(self):
        """测试提交有效任务数据"""
        # 准备测试数据
        test_task_data = {
            '员工id': 1,
            '书籍id': 1,
            '预计完成日期': self.future_due_date,
            '印刷数量': 1000
        }

        # 设置模拟行为
        self.printing_service.employee_dao.get_by_id.return_value = {
            '员工id': 1, '在职状态': '在职'
        }
        self.printing_service.book_dao.get_by_id.return_value = {
            '书籍id': 1, '书籍名称': '测试书籍'
        }
        # submit_printing_task 使用的是带事务的 create_with_connection
        self.printing_service.task_dao.create_with_connection.return_value = 123
        # 为材料与供应商、采购、库存日志提供模拟返回值
        self.printing_service.material_supplier_dao.get_material_suppliers.return_value = [
            {
                '材料供应商关联id': 1,
                '供应商提供的材料单价': 10.0,
                '是否为首选供应商': '是'
            }
        ]
        self.printing_service.purchase_dao.create_with_connection.return_value = 1001
        self.printing_service.stock_log_dao.create_with_connection.return_value = 5001

        # 执行测试
        result = self.printing_service.submit_printing_task(test_task_data)

        # 验证结果
        self.assertTrue(result['success'])
        self.assertEqual(result['data']['task_id'], 123)

    def test_submit_task_with_invalid_quantity(self):
        """测试提交无效印刷数量"""
        test_task_data = {
            '员工id': 1,
            '书籍id': 1,
            '预计完成日期': self.future_due_date,
            '印刷数量': -5  # 无效数量
        }

        result = self.printing_service.submit_printing_task(test_task_data)

        self.assertFalse(result['success'])
        self.assertIn('印刷数量必须大于0', result['message'])

    def test_submit_task_with_inactive_employee(self):
        """测试提交已离职员工的任务"""
        test_task_data = {
            '员工id': 2,
            '书籍id': 1,
            '预计完成日期': self.future_due_date,
            '印刷数量': 1000
        }

        # 模拟已离职员工
        self.printing_service.employee_dao.get_by_id.return_value = {
            '员工id': 2, '在职状态': '离职'
        }

        result = self.printing_service.submit_printing_task(test_task_data)

        self.assertFalse(result['success'])
        self.assertIn('不存在或已离职', result['message'])

if __name__ == '__main__':
    # 运行测试
    unittest.main()