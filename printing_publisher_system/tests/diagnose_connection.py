# diagnose_connection.py
"""
网络连接诊断脚本
在客户端运行此脚本来诊断MySQL远程连接问题
"""
import sys
import os
import socket
import subprocess
import platform

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

import mysql.connector
from mysql.connector import Error
from src.config.settings import DB_CONFIG

# 服务器配置
SERVER_IP = '10.82.157.204'
SERVER_PORT = 3306

def test_ping():
    """测试是否能ping通服务器"""
    print("=" * 60)
    print("步骤1: 测试网络连通性 (Ping)")
    print("=" * 60)
    
    try:
        # 根据操作系统选择ping命令
        if platform.system().lower() == 'windows':
            result = subprocess.run(
                ['ping', '-n', '4', SERVER_IP],
                capture_output=True,
                text=True,
                timeout=10
            )
        else:
            result = subprocess.run(
                ['ping', '-c', '4', SERVER_IP],
                capture_output=True,
                text=True,
                timeout=10
            )
        
        if result.returncode == 0:
            print(f"✅ 可以ping通服务器 {SERVER_IP}")
            print("\nPing结果:")
            print(result.stdout)
            return True
        else:
            print(f"❌ 无法ping通服务器 {SERVER_IP}")
            print("\nPing结果:")
            print(result.stdout)
            print("\n可能的原因:")
            print("1. 服务器IP地址不正确")
            print("2. 服务器未开机或网络不通")
            print("3. 防火墙阻止了ICMP包")
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ Ping超时，无法连接到服务器 {SERVER_IP}")
        return False
    except Exception as e:
        print(f"⚠️  Ping测试失败: {e}")
        print("   请手动测试: ping " + SERVER_IP)
        return None

def test_port_connectivity():
    """测试3306端口是否可达"""
    print("\n" + "=" * 60)
    print("步骤2: 测试端口连通性 (TCP 3306)")
    print("=" * 60)
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5秒超时
        
        print(f"正在尝试连接到 {SERVER_IP}:{SERVER_PORT}...")
        result = sock.connect_ex((SERVER_IP, SERVER_PORT))
        sock.close()
        
        if result == 0:
            print(f"✅ 端口 {SERVER_PORT} 可达，服务器正在监听")
            return True
        else:
            print(f"❌ 端口 {SERVER_PORT} 不可达 (错误代码: {result})")
            print("\n可能的原因:")
            print("1. MySQL服务未运行")
            print("2. MySQL未绑定到正确的IP地址 (bind-address配置)")
            print("3. 服务器防火墙阻止了3306端口")
            print("4. 路由器/网络防火墙阻止了连接")
            return False
    except socket.timeout:
        print(f"❌ 连接超时，无法连接到 {SERVER_IP}:{SERVER_PORT}")
        print("\n这通常表示:")
        print("1. 服务器防火墙阻止了连接")
        print("2. MySQL未配置允许远程连接")
        print("3. 网络路由问题")
        return False
    except Exception as e:
        print(f"❌ 端口测试失败: {e}")
        return False

def check_client_config():
    """检查客户端配置"""
    print("\n" + "=" * 60)
    print("步骤3: 检查客户端配置")
    print("=" * 60)
    
    print(f"\n当前配置 (src/config/settings.py):")
    print(f"  Host: {DB_CONFIG.get('host', '未设置')}")
    print(f"  Port: {DB_CONFIG.get('port', '3306 (默认)')}")
    print(f"  User: {DB_CONFIG.get('user', '未设置')}")
    print(f"  Database: {DB_CONFIG.get('database', '未设置')}")
    
    if DB_CONFIG.get('host') == 'localhost':
        print("\n⚠️  警告: Host设置为'localhost'，这只会连接本地数据库")
        print(f"   如果要从远程连接，应该设置为: {SERVER_IP}")
        print(f"   请修改 src/config/settings.py 中的 host 为 '{SERVER_IP}'")
        return False
    elif DB_CONFIG.get('host') == SERVER_IP:
        print(f"\n✅ Host配置正确: {SERVER_IP}")
        return True
    else:
        print(f"\n⚠️  Host配置为: {DB_CONFIG.get('host')}")
        print(f"   如果服务器IP是 {SERVER_IP}，请确认配置正确")
        return None

def test_mysql_connection():
    """测试MySQL连接"""
    print("\n" + "=" * 60)
    print("步骤4: 测试MySQL连接")
    print("=" * 60)
    
    # 使用服务器IP测试连接
    test_config = DB_CONFIG.copy()
    test_config['host'] = SERVER_IP
    test_config['port'] = SERVER_PORT
    test_config['connect_timeout'] = 5
    
    print(f"\n尝试连接到 MySQL 服务器...")
    print(f"  Host: {test_config['host']}")
    print(f"  Port: {test_config['port']}")
    print(f"  User: {test_config['user']}")
    print(f"  Database: {test_config['database']}")
    
    try:
        connection = mysql.connector.connect(**test_config)
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            print(f"\n✅ MySQL连接成功！")
            print(f"   服务器版本: {db_info}")
            
            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE();")
            db_name = cursor.fetchone()
            print(f"   当前数据库: {db_name[0]}")
            
            cursor.close()
            connection.close()
            return True
    except Error as e:
        error_code = e.errno
        error_msg = str(e)
        
        print(f"\n❌ MySQL连接失败")
        print(f"   错误: {e}")
        
        if error_code == 2003 or '10060' in error_msg:
            print("\n   这是连接超时错误，可能的原因:")
            print("   1. 服务器端MySQL未配置允许远程连接")
            print("   2. 服务器防火墙阻止了3306端口")
            print("   3. MySQL用户没有远程访问权限")
        elif error_code == 1045:
            print("\n   认证失败，可能的原因:")
            print("   1. 用户名或密码错误")
            print("   2. 用户没有从该IP访问的权限")
        elif error_code == 1049:
            print("\n   数据库不存在")
        
        return False
    except Exception as e:
        print(f"\n❌ 连接测试失败: {e}")
        return False

def provide_solutions():
    """提供解决方案"""
    print("\n" + "=" * 60)
    print("解决方案建议")
    print("=" * 60)
    
    print("\n请在服务器端执行以下操作：")
    print("\n1. 修改MySQL配置文件 my.ini:")
    print("   找到 [mysqld] 部分，添加或修改:")
    print("   bind-address = 0.0.0.0")
    print("   然后重启MySQL服务")
    
    print("\n2. 配置Windows防火墙:")
    print("   以管理员身份运行:")
    print(f'   netsh advfirewall firewall add rule name="MySQL" dir=in action=allow protocol=TCP localport={SERVER_PORT}')
    
    print("\n3. 授予MySQL用户远程访问权限:")
    print("   连接到MySQL后执行:")
    print("   GRANT ALL PRIVILEGES ON printing_publisher_db.* TO 'root'@'%' IDENTIFIED BY '你的密码';")
    print("   FLUSH PRIVILEGES;")
    
    print("\n4. 在服务器端运行自动配置脚本:")
    print("   python tests/fix_remote_connection.py")
    
    print("\n5. 检查客户端配置:")
    print("   确保 src/config/settings.py 中 host 设置为服务器IP")
    print(f"   当前应该为: 'host': '{SERVER_IP}'")
    
    print("\n" + "=" * 60)

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("MySQL远程连接诊断工具")
    print("=" * 60)
    print(f"\n服务器信息:")
    print(f"  IP地址: {SERVER_IP}")
    print(f"  端口: {SERVER_PORT}")
    print("\n" + "=" * 60)
    
    results = {}
    
    # 执行诊断测试
    results['ping'] = test_ping()
    results['port'] = test_port_connectivity()
    results['config'] = check_client_config()
    results['mysql'] = test_mysql_connection()
    
    # 总结
    print("\n" + "=" * 60)
    print("诊断结果总结")
    print("=" * 60)
    
    print(f"\n网络连通性 (Ping): {'✅ 通过' if results['ping'] else '❌ 失败' if results['ping'] is False else '⚠️  未测试'}")
    print(f"端口连通性 (3306): {'✅ 通过' if results['port'] else '❌ 失败'}")
    print(f"客户端配置: {'✅ 正确' if results['config'] else '❌ 需要修改' if results['config'] is False else '⚠️  请确认'}")
    print(f"MySQL连接: {'✅ 成功' if results['mysql'] else '❌ 失败'}")
    
    if not all([results['ping'], results['port'], results['mysql']]):
        provide_solutions()
    else:
        print("\n✅ 所有测试通过！连接应该可以正常工作。")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()


