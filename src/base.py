"""
基础通用能力模块
提供单例执行、日志登记、配置加载、邮件发送等通用功能
"""
import os
import sys
import json
import time
import ssl
import smtplib
import logging
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
try:
    from typing import Optional, Tuple, Dict, Any
except ImportError:
    # Python 3.6 兼容性
    Optional = None
    Tuple = None
    Dict = None
    Any = None

# 平台相关导入
if os.name == 'nt':
    import ctypes
    from ctypes import wintypes
else:
    import fcntl

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # 允许在未安装dotenv时继续运行（使用系统环境变量）


# 全局锁句柄（Windows: mutex 句柄；Unix: 文件句柄）
_LOCK_HANDLE = None
_WIN_MUTEX_HANDLE = None
_WIN_ERROR_ALREADY_EXISTS = 183


class BaseApp:
    """基础应用类，提供通用能力"""
    
    def __init__(self, app_name: str, root_path: Optional[Path] = None):
        """
        初始化基础应用
        
        Args:
            app_name: 应用名称，用于日志文件名和锁文件名
            root_path: 应用根路径，如果为None则自动检测
        """
        self.app_name = app_name
        self.logger = None  # logger 实例，在 setup_logging 时设置
        
        # 兼容 PyInstaller 打包后的路径问题
        if root_path is None:
            if getattr(sys, 'frozen', False):
                # PyInstaller 打包后的情况
                # exe 文件在 dist 目录下，但配置文件和日志文件应该在项目根目录
                exe_path = Path(sys.executable).parent
                # 如果 exe 在 dist 目录下，则项目根目录是 dist 的父目录
                if exe_path.name == 'dist':
                    self.root = exe_path.parent
                else:
                    self.root = exe_path
            else:
                # 开发环境的情况
                self.root = Path(__file__).resolve().parent.parent
        else:
            self.root = root_path
    
    def _acquire_windows_mutex(self, name: str) -> bool:
        """创建并持有Windows命名互斥量，已存在则返回False。"""
        global _WIN_MUTEX_HANDLE
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        CreateMutexW = kernel32.CreateMutexW
        CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        CreateMutexW.restype = wintypes.HANDLE

        # 创建全局命名互斥量，避免不同会话重复实例
        mutex_name = "Global\\{}".format(name)
        handle = CreateMutexW(None, False, mutex_name)
        if not handle:
            return False
        # 检查是否已存在
        last_error = ctypes.get_last_error()
        _WIN_MUTEX_HANDLE = handle
        return last_error != _WIN_ERROR_ALREADY_EXISTS

    def acquire_single_instance_lock(self, lock_file=None):
        """尝试获取单实例锁。Windows用命名互斥量；Unix用fcntl文件锁。"""
        global _LOCK_HANDLE
        
        if lock_file is None:
            # 创建 rundata 目录（如果不存在）
            rundata_dir = self.root / "rundata"
            rundata_dir.mkdir(exist_ok=True)
            lock_file = rundata_dir / "{}.lock".format(self.app_name)
            
        try:
            if os.name == 'nt':
                # Windows: 使用命名互斥量
                return self._acquire_windows_mutex('{}-mutex'.format(self.app_name))
            else:
                # Unix: 使用文件锁
                lock_file.parent.mkdir(parents=True, exist_ok=True)
                _LOCK_HANDLE = open(lock_file, 'a+')
                _LOCK_HANDLE.seek(0)
                _LOCK_HANDLE.truncate(0)
                _LOCK_HANDLE.write(str(os.getpid()))
                _LOCK_HANDLE.flush()
                fcntl.flock(_LOCK_HANDLE.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
        except Exception:
            try:
                if _LOCK_HANDLE:
                    _LOCK_HANDLE.close()
            except Exception:
                pass
            _LOCK_HANDLE = None
            return False

    def release_single_instance_lock(self, lock_file=None):
        """释放单实例锁。"""
        global _LOCK_HANDLE, _WIN_MUTEX_HANDLE
        
        if lock_file is None:
            # 创建 rundata 目录（如果不存在）
            rundata_dir = self.root / "rundata"
            rundata_dir.mkdir(exist_ok=True)
            lock_file = rundata_dir / "{}.lock".format(self.app_name)
            
        try:
            if os.name == 'nt':
                if _WIN_MUTEX_HANDLE:
                    ctypes.windll.kernel32.CloseHandle(_WIN_MUTEX_HANDLE)
                    _WIN_MUTEX_HANDLE = None
            else:
                if _LOCK_HANDLE:
                    try:
                        fcntl.flock(_LOCK_HANDLE.fileno(), fcntl.LOCK_UN)
                    except Exception:
                        pass
                    _LOCK_HANDLE.close()
                    _LOCK_HANDLE = None
                if lock_file.exists():
                    lock_file.unlink()
        except Exception:
            pass

    def load_config(self, config_file=None, required_keys=None, type_conversions=None):
        """加载配置，优先读取 .my-env 文件，其次读取 .env 文件，最后读取系统环境变量。
        
        Args:
            config_file: 配置文件路径，如果为None则自动选择 .my-env 或 .env
            required_keys: 必需的配置项列表，如果为None则不检查
            type_conversions: 类型转换字典，格式为 {"key": "int|bool|str"}
        """
        
        # 如果未指定配置文件，则优先查找 .my-env，其次查找 .env
        if config_file is None:
            # 优先检查 .my-env
            my_env_file = self.root / ".my-env"
            env_file = self.root / ".env"
            
            # 如果 .my-env 存在，使用它；否则使用 .env
            if my_env_file.exists():
                config_file = my_env_file
            elif env_file.exists():
                config_file = env_file
            else:
                # 如果都不存在，尝试在脚本目录查找（开发环境）
                if not getattr(sys, 'frozen', False):
                    script_dir = Path(__file__).resolve().parent.parent
                    my_env_file = script_dir / ".my-env"
                    env_file = script_dir / ".env"
                    
                    if my_env_file.exists():
                        config_file = my_env_file
                    elif env_file.exists():
                        config_file = env_file
                    else:
                        error_msg = "配置文件不存在: 未找到 .my-env 或 .env 文件"
                        print("错误: {}".format(error_msg))
                        raise FileNotFoundError(error_msg)
                else:
                    error_msg = "配置文件不存在: 未找到 .my-env 或 .env 文件"
                    print("错误: {}".format(error_msg))
                    raise FileNotFoundError(error_msg)
        else:
            # 如果指定了配置文件，但不存在，尝试在脚本目录查找（开发环境）
            if not config_file.exists() and not getattr(sys, 'frozen', False):
                script_dir = Path(__file__).resolve().parent.parent
                config_file = script_dir / config_file.name
        
        # 检查配置文件是否存在
        if not config_file.exists():
            error_msg = "配置文件不存在: {}".format(config_file)
            print("错误: {}".format(error_msg))
            raise FileNotFoundError(error_msg)
            
        # 加载配置文件
        if load_dotenv and config_file.exists():
            load_dotenv(config_file)
        
        config = {}
        missing_keys = []
        
        # 如果指定了必需配置项，则进行检查
        if required_keys:
            for key in required_keys:
                env_value = os.getenv(key)
                if env_value is None or env_value.strip() == "":
                    missing_keys.append(key)
                else:
                    # 根据类型转换字典进行转换
                    if type_conversions and key in type_conversions:
                        target_type = type_conversions[key]
                        try:
                            if target_type == "int":
                                config[key] = int(env_value)
                            elif target_type == "bool":
                                config[key] = env_value.lower() in {"1", "true", "yes", "y"}
                            else:
                                config[key] = env_value
                        except ValueError:
                            missing_keys.append("{}(无效的{}值)".format(key, target_type))
                    else:
                        config[key] = env_value
            
            # 如果有缺失的配置项，抛出异常
            if missing_keys:
                error_msg = "配置文件 {} 中缺少必需的配置项: {}".format(config_file, ', '.join(missing_keys))
                print("错误: {}".format(error_msg))
                raise ValueError(error_msg)
        else:
            # 如果没有指定必需配置项，则加载所有环境变量
            for key, value in os.environ.items():
                if value.strip():
                    config[key] = value
                
        return config

    def setup_logging(self, log_dir=None, retention_days=30):
        """设置日志记录，按天分割日志文件，自动清理过期日志。"""
        if log_dir is None:
            log_dir = self.root / "logs"
            
        # 确保日志目录存在
        log_dir.mkdir(exist_ok=True)
        
        # 清理过期日志文件
        self.cleanup_old_logs(log_dir, retention_days)
        
        # 创建按天分割的日志文件名
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / "{}-{}.log".format(self.app_name, today)
        
        # 配置日志格式
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()  # 同时输出到控制台
            ]
        )
        
        logger = logging.getLogger(self.app_name)
        logger.info("日志系统已启动，日志文件: {}".format(log_file))
        self.logger = logger  # 保存 logger 实例
        return logger

    def cleanup_old_logs(self, log_dir, retention_days):
        """清理超过保留天数的日志文件。"""
        if not log_dir.exists():
            return
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0
        
        for log_file in log_dir.glob("{}-*.log".format(self.app_name)):
            try:
                # 从文件名提取日期
                date_str = log_file.stem.split('-')[-1]  # 获取日期部分
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                if file_date < cutoff_date:
                    log_file.unlink()
                    deleted_count += 1
            except (ValueError, IndexError):
                # 文件名格式不正确，跳过
                continue
        
        if deleted_count > 0:
            print("[日志清理] 已删除 {} 个过期日志文件".format(deleted_count))

    def send_mail(self, config, subject, content):
        """发送邮件通知。
        
        返回:
            bool: 如果成功发送邮件返回 True，如果因为未配置而跳过发送返回 False
        异常:
            如果发送过程中出现错误，抛出异常
        """
        smtp_host = config["SMTP_HOST"]
        
        # 检查是否为示例配置
        if smtp_host == "smtp.example.com":
            error_msg = "SMTP邮件服务器未配置，请到\".env\"文件进行配置。"
            self.logger.warning("警告: {}".format(error_msg))
           
            return False  # 返回 False 表示未发送邮件
        
        smtp_port = config["SMTP_PORT"]
        username = config["SMTP_USERNAME"]
        password = config["SMTP_PASSWORD"]
        # 兼容旧配置：如果未显式配置 SMTP_USE_TLS，则根据端口推断一个默认值
        if "SMTP_USE_TLS" in config:
            use_tls = config["SMTP_USE_TLS"]
        else:
            # 常见端口 465/587 默认使用 TLS，其它端口默认不启用
            use_tls = smtp_port in (465, 587)

        mail_from = config["MAIL_FROM"]
        mail_to = config["MAIL_TO"]

        if not (smtp_host and smtp_port and username and password and mail_from and mail_to):
            raise RuntimeError("SMTP配置不完整，请在 .env 中设置 SMTP_* 与邮件地址")

        msg = EmailMessage()
        msg["From"] = mail_from
        msg["To"] = mail_to
        msg["Subject"] = subject
        msg.set_content(content)

        if use_tls and smtp_port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
                server.login(username, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                if use_tls:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                server.login(username, password)
                server.send_message(msg)
        
        return True  # 成功发送邮件，返回 True



# 为了向后兼容，提供独立的函数接口
def acquire_single_instance_lock(lock_file, app_name="check-web-alive"):
    """向后兼容的单例锁获取函数"""
    app = BaseApp(app_name)
    return app.acquire_single_instance_lock(lock_file)


def release_single_instance_lock(lock_file, app_name="check-web-alive"):
    """向后兼容的单例锁释放函数"""
    app = BaseApp(app_name)
    app.release_single_instance_lock(lock_file)


def load_config():
    """向后兼容的配置加载函数"""
    app = BaseApp("check-web-alive")
    return app.load_config()


def setup_logging(log_dir, retention_days, app_name="check-web-alive"):
    """向后兼容的日志设置函数"""
    app = BaseApp(app_name)
    return app.setup_logging(log_dir, retention_days)


def cleanup_old_logs(log_dir, retention_days, app_name="check-web-alive"):
    """向后兼容的日志清理函数"""
    app = BaseApp(app_name)
    app.cleanup_old_logs(log_dir, retention_days)


def send_mail(cfg, subject, content):
    """向后兼容的邮件发送函数"""
    app = BaseApp("check-web-alive")
    return app.send_mail(cfg, subject, content)


