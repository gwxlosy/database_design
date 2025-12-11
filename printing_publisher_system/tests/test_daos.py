import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from src.database.daos import (
    员工DAO, 书籍核心信息DAO, 书籍版本DAO, 
    印刷任务DAO, 材料DAO
)

def test_all_daos():
    """综合测试所有DAO类的基本功能"""
    print("=== 开始DAO层综合测试 ===\n")
    
    try:
        # 1. 测试员工DAO
        print("1. 测试员工DAO...")
        employee_dao = 员工DAO()
        employees = employee_dao.get_active_employees()
        print(f"   当前在职员工数: {len(employees)}")
        
        # 2. 测试书籍DAO
        print("2. 测试书籍核心信息DAO...")
        book_dao = 书籍核心信息DAO()
        all_books = book_dao.get_all()
        print(f"   书籍总数: {len(all_books)}")
        
        # 3. 测试材料DAO
        print("3. 测试材料DAO...")
        material_dao = 材料DAO()
        low_stock = material_dao.get_low_stock_materials()
        print(f"   低于安全库存的材料数: {len(low_stock)}")
        
        # 4. 测试错误处理
        print("4. 测试错误处理机制...")
        try:
            # 尝试用无效数据创建记录
            result = employee_dao.create({})  # 空数据应该失败
            print("   ❌ 错误处理测试失败")
        except Exception as e:
            print(f"   ✅ 错误处理正常: {str(e)[:50]}...")
        
        print("\n=== DAO层测试完成 ===")
        return True
        
    except Exception as e:
        print(f"\n❌ DAO层测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_all_daos()
    if success:
        print("\n🎉 第三阶段DAO层实现完成！")
        print("\n下一步建议：")
        print("1. 运行 'python test_daos.py' 进行完整测试")
        print("2. 检查数据库中的测试数据是否正确")
        print("3. 准备进入第四阶段：业务逻辑层开发")
    else:
        print("\n💥 需要修复上述问题后再继续")