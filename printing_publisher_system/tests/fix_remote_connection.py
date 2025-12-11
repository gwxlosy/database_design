# fix_remote_connection.py
"""
MySQL远程连接配置修复脚本
在数据库服务器端运行此脚本来配置MySQL允许远程连接
"""
import sys
import os

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

import mysql.connector
from mysql.connector import Error
from src.config.settings import DB_CONFIG

def check_mysql_bind_address():
    """检查MySQL的bind-address配置"""
    print("=" * 60)
    print("步骤1: 检查MySQL bind-address配置")
    print("=" * 60)
    print("\n请在MySQL服务器上执行以下操作：")
    print("\n1. 找到MySQL配置文件 my.ini (Windows) 或 my.cnf (Linux)")
    print("   Windows默认位置: C:\\ProgramData\\MySQL\\MySQL Server X.X\\my.ini")
    print("   或: C:\\Program Files\\MySQL\\MySQL Server X.X\\my.ini")
    print("\n2. 找到 [mysqld] 部分，确保有以下配置：")
    print("   [mysqld]")
    print("   bind-address = 0.0.0.0    # 允许所有IP连接")
    print("   或")
    print("   bind-address = 10.82.157.204  # 只允许特定IP")
    print("\n3. 如果配置被注释掉或不存在，请添加上述配置")
    print("4. 保存文件后，重启MySQL服务")
    print("\n重启MySQL服务的方法：")
    print("   - 打开服务管理器 (services.msc)")
    print("   - 找到 MySQL 服务")
    print("   - 右键 -> 重新启动")
    print("\n" + "=" * 60)

def check_firewall():
    """检查防火墙配置"""
    print("\n步骤2: 检查Windows防火墙")
    print("=" * 60)
    print("\n请确保Windows防火墙允许3306端口：")
    print("\n方法1 - 使用命令行（以管理员身份运行）：")
    print("   netsh advfirewall firewall add rule name=\"MySQL\" dir=in action=allow protocol=TCP localport=3306")
    print("\n方法2 - 使用图形界面：")
    print("   1. 打开 'Windows Defender 防火墙'")
    print("   2. 点击 '高级设置'")
    print("   3. 点击 '入站规则' -> '新建规则'")
    print("   4. 选择 '端口' -> 'TCP' -> '特定本地端口' -> 输入 3306")
    print("   5. 选择 '允许连接'")
    print("   6. 应用到所有配置文件")
    print("\n" + "=" * 60)

def grant_remote_access():
    """授予MySQL用户远程访问权限"""
    print("\n步骤3: 配置MySQL用户远程访问权限")
    print("=" * 60)
    
    try:
        # 使用本地连接
        local_config = DB_CONFIG.copy()
        local_config['host'] = 'localhost'
        
        connection = mysql.connector.connect(**local_config)
        cursor = connection.cursor()
        
        print("\n正在检查当前用户权限...")
        
        # 检查root用户的host权限
        cursor.execute("""
            SELECT user, host FROM mysql.user 
            WHERE user = 'root'
        """)
        
        users = cursor.fetchall()
        print("\n当前root用户的访问权限：")
        for user, host in users:
            print(f"  用户: {user}, 允许的主机: {host}")
        
        # 检查是否有'%'（允许所有主机）的权限
        has_remote_access = any(host == '%' for _, host in users)
        
        if not has_remote_access:
            print("\n⚠️  未找到允许远程访问的权限，正在创建...")
            
            # 授予远程访问权限
            # 方法1: 允许所有IP访问（不推荐，但简单）
            print("\n正在授予root用户从任何IP访问的权限...")
            try:
                cursor.execute("""
                    CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '18302057923ljl'
                """)
                cursor.execute("""
                    GRANT ALL PRIVILEGES ON printing_publisher_db.* TO 'root'@'%'
                """)
                cursor.execute("FLUSH PRIVILEGES")
                connection.commit()
                print("✅ 已授予root用户远程访问权限（所有IP）")
            except Error as e:
                print(f"⚠️  创建用户时出错: {e}")
                print("   尝试更新现有用户权限...")
                try:
                    cursor.execute("""
                        GRANT ALL PRIVILEGES ON printing_publisher_db.* TO 'root'@'%' 
                        IDENTIFIED BY '18302057923ljl'
                    """)
                    cursor.execute("FLUSH PRIVILEGES")
                    connection.commit()
                    print("✅ 已更新root用户远程访问权限")
                except Error as e2:
                    print(f"❌ 更新权限失败: {e2}")
            
            # 方法2: 只允许特定IP访问（更安全，推荐）
            print("\n💡 更安全的做法：只允许特定IP访问")
            print("   如果需要，可以手动执行以下SQL命令：")
            print("   CREATE USER 'root'@'客户端IP地址' IDENTIFIED BY '18302057923ljl';")
            print("   GRANT ALL PRIVILEGES ON printing_publisher_db.* TO 'root'@'客户端IP地址';")
            print("   FLUSH PRIVILEGES;")
        else:
            print("\n✅ root用户已具有远程访问权限")
        
        cursor.close()
        connection.close()
        
    except Error as e:
        print(f"\n❌ 连接MySQL失败: {e}")
        print("   请确保MySQL服务正在运行，并且可以使用localhost连接")
        return False
    
    print("\n" + "=" * 60)
    return True

def test_connection():
    """测试连接"""
    print("\n步骤4: 测试连接配置")
    print("=" * 60)
    
    # 测试本地连接
    print("\n1. 测试本地连接...")
    try:
        local_config = DB_CONFIG.copy()
        local_config['host'] = 'localhost'
        connection = mysql.connector.connect(**local_config)
        if connection.is_connected():
            print("   ✅ 本地连接成功")
            connection.close()
        else:
            print("   ❌ 本地连接失败")
            return False
    except Error as e:
        print(f"   ❌ 本地连接失败: {e}")
        return False
    
    # 测试远程连接（使用服务器IP）
    print("\n2. 测试远程连接（使用服务器IP 10.82.157.204）...")
    try:
        remote_config = DB_CONFIG.copy()
        remote_config['host'] = '10.82.157.204'
        remote_config['connect_timeout'] = 5
        connection = mysql.connector.connect(**remote_config)
        if connection.is_connected():
            print("   ✅ 远程连接成功")
            connection.close()
        else:
            print("   ❌ 远程连接失败")
            return False
    except Error as e:
        print(f"   ⚠️  远程连接失败: {e}")
        print("   这是正常的，因为可能需要在客户端测试")
        print("   请确保已完成前面的配置步骤")
    
    print("\n" + "=" * 60)
    return True

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("MySQL远程连接配置助手")
    print("=" * 60)
    print("\n此脚本将帮助您配置MySQL以允许远程连接")
    print("请在数据库服务器端运行此脚本")
    print("\n⚠️  注意：配置远程访问会带来安全风险，请确保：")
    print("   1. 使用强密码")
    print("   2. 只允许必要的IP访问")
    print("   3. 定期更新MySQL版本")
    print("\n" + "=" * 60)
    
    input("\n按Enter键继续...")
    
    # 执行配置步骤
    check_mysql_bind_address()
    input("\n完成步骤1后，按Enter继续...")
    
    check_firewall()
    input("\n完成步骤2后，按Enter继续...")
    
    if grant_remote_access():
        input("\n完成步骤3后，按Enter继续...")
        test_connection()
    
    print("\n" + "=" * 60)
    print("配置完成！")
    print("=" * 60)
    print("\n请确保：")
    print("1. ✅ MySQL bind-address已配置为0.0.0.0或服务器IP")
    print("2. ✅ MySQL服务已重启")
    print("3. ✅ Windows防火墙已允许3306端口")
    print("4. ✅ MySQL用户已授予远程访问权限")
    print("\n现在可以在远程客户端测试连接了！")
    print("=" * 60)

if __name__ == "__main__":
    main()



