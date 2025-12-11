"""
使用Python执行创建用户表的SQL脚本
这样可以更好地处理中文字符编码问题
"""
import sys
import os
import mysql.connector
from mysql.connector import Error

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config.settings import DB_CONFIG


def create_user_table():
    """执行创建用户表的SQL"""
    connection = None
    try:
        # 连接数据库
        print("正在连接数据库...")
        connection = mysql.connector.connect(**DB_CONFIG)
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            print(f"✅ 成功连接到MySQL服务器，版本: {db_info}")
            
            cursor = connection.cursor()
            
            # 设置字符集
            cursor.execute("SET NAMES utf8mb4")
            
            # 创建用户表
            print("\n正在创建用户表...")
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS 用户表 (
                用户id INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID，主键',
                用户名 VARCHAR(50) NOT NULL UNIQUE COMMENT '登录用户名，唯一',
                密码 VARCHAR(255) NOT NULL COMMENT '密码（SHA256哈希值）',
                职位 VARCHAR(20) NOT NULL COMMENT '用户职位（编辑、排版、印刷工、采购、仓储、销售、人事、管理员等）',
                创建时间 DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '账户创建时间',
                INDEX idx_username (用户名),
                INDEX idx_position (职位)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';
            """
            cursor.execute(create_table_sql)
            print("✅ 用户表创建成功")
            
            # 插入默认管理员账户
            print("\n正在插入默认管理员账户...")
            insert_admin_sql = """
            INSERT INTO 用户表 (用户名, 密码, 职位) 
            VALUES ('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', '管理员')
            ON DUPLICATE KEY UPDATE 用户名=用户名;
            """
            cursor.execute(insert_admin_sql)
            connection.commit()
            print("✅ 默认管理员账户创建成功")
            print("   用户名: admin")
            print("   密码: admin123")
            print("   职位: 管理员")
            
            # 验证表结构
            print("\n验证表结构...")
            cursor.execute("DESCRIBE 用户表")
            columns = cursor.fetchall()
            print("用户表字段：")
            for col in columns:
                print(f"  - {col[0]} ({col[1]})")
            
            print("\n✅ 用户表创建完成！")
            
    except Error as e:
        print(f"\n❌ 数据库错误: {e}")
        if connection:
            connection.rollback()
        return False
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()
            print("\n数据库连接已关闭")
    
    return True


if __name__ == '__main__':
    print("=" * 60)
    print("创建用户表脚本")
    print("=" * 60)
    
    success = create_user_table()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ 所有操作完成！")
        print("=" * 60)
        print("\n现在可以使用以下账户登录：")
        print("  用户名: admin")
        print("  密码: admin123")
    else:
        print("\n" + "=" * 60)
        print("❌ 操作失败，请检查错误信息")
        print("=" * 60)
        sys.exit(1)

