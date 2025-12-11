# test_database.py
import sys
import os

# 获取当前脚本的目录（tests目录），然后找到项目根目录（printing_publisher_system）
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)  # 将项目根目录添加到模块搜索路径的开头

import mysql.connector
from mysql.connector import Error
from src.config.settings import DB_CONFIG
def test_database_connection():
    """测试数据库连接"""
    try:
        # 尝试建立数据库连接
        connection = mysql.connector.connect(**DB_CONFIG)
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            print(f"成功连接到MySQL服务器，版本: {db_info}")
            
            # 获取数据库名称
            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE();")
            database_name = cursor.fetchone()
            print(f"当前数据库: {database_name[0]}")
            
            # 测试表创建情况
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM information_schema.tables 
                WHERE table_schema = 'printing_publisher_db'
            """)
            tables = cursor.fetchall()
            
            print("\n数据库中的表:")
            for i, table in enumerate(tables, 1):
                print(f"{i}. {table[0]}")
            
            return True
            
    except Error as e:
        error_code = e.errno
        error_msg = str(e)
        print(f"数据库连接错误: {e}")
        
        # 提供详细的错误诊断
        if error_code == 2003 or '10060' in error_msg:
            print("\n" + "=" * 60)
            print("❌ 连接超时错误 (10060)")
            print("=" * 60)
            print("\n可能的原因：")
            print("1. MySQL服务器未配置允许远程连接")
            print("   - 检查 my.ini 中 bind-address 是否为 0.0.0.0 或服务器IP")
            print("   - 确保MySQL服务已重启")
            print("\n2. Windows防火墙阻止了3306端口")
            print("   - 运行: netsh advfirewall firewall add rule name=\"MySQL\" dir=in action=allow protocol=TCP localport=3306")
            print("\n3. MySQL用户没有远程访问权限")
            print("   - 在服务器端执行: GRANT ALL PRIVILEGES ON printing_publisher_db.* TO 'root'@'%';")
            print("   - 然后执行: FLUSH PRIVILEGES;")
            print("\n4. 网络连接问题")
            print("   - 检查是否可以ping通服务器IP")
            print("   - 检查服务器IP地址是否正确")
            print("\n💡 提示：")
            print("   - 在服务器端运行: python tests/fix_remote_connection.py")
            print("   - 查看详细配置指南: 远程连接配置指南.md")
            print("=" * 60)
        elif error_code == 1045:
            print("\n❌ 认证失败：用户名或密码错误")
        elif error_code == 1049:
            print("\n❌ 数据库不存在：请检查数据库名称是否正确")
        elif 'Connection refused' in error_msg:
            print("\n❌ 连接被拒绝：MySQL服务可能未运行或端口不正确")
        
        return False
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            print("\n数据库连接已关闭")

if __name__ == "__main__":
    print("开始测试数据库连接...")
    success = test_database_connection()
    
    if success:
        print("\n✅ 第二阶段数据库创建与连接测试成功！")
    else:
        print("\n❌ 数据库连接测试失败，请检查配置。")