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
from typing import Optional, Tuple, Dict, Any

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
        
        # 兼容 PyInstaller 打包后的路径问题
        if root_path is None:
            if getattr(sys, 'frozen', False):
                # PyInstaller 打包后的情况
                self.root = Path(sys.executable).parent
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
        mutex_name = f"Global\\{name}"
        handle = CreateMutexW(None, False, mutex_name)
        if not handle:
            return False
        # 检查是否已存在
        last_error = ctypes.get_last_error()
        _WIN_MUTEX_HANDLE = handle
        return last_error != _WIN_ERROR_ALREADY_EXISTS

    def acquire_single_instance_lock(self, lock_file: Optional[Path] = None) -> bool:
        """尝试获取单实例锁。Windows用命名互斥量；Unix用fcntl文件锁。"""
        global _LOCK_HANDLE
        
        if lock_file is None:
            lock_file = self.root / f"{self.app_name}.lock"
            
        try:
            if os.name == 'nt':
                # Windows: 使用命名互斥量
                return self._acquire_windows_mutex(f'{self.app_name}-mutex')
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

    def release_single_instance_lock(self, lock_file: Optional[Path] = None) -> None:
        """释放单实例锁。"""
        global _LOCK_HANDLE, _WIN_MUTEX_HANDLE
        
        if lock_file is None:
            lock_file = self.root / f"{self.app_name}.lock"
            
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

    def load_config(self, config_file: Optional[Path] = None, required_keys: Optional[list] = None, 
                   type_conversions: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """加载配置，优先读取 .env 文件，其次读取系统环境变量。
        
        Args:
            config_file: 配置文件路径，默认为 .env
            required_keys: 必需的配置项列表，如果为None则不检查
            type_conversions: 类型转换字典，格式为 {"key": "int|bool|str"}
        """
        
        if config_file is None:
            config_file = self.root / ".env"
            
        if not config_file.exists() and not getattr(sys, 'frozen', False):
            script_dir = Path(__file__).resolve().parent.parent
            config_file = script_dir / ".env"
        
        # 检查配置文件是否存在
        if not config_file.exists():
            error_msg = f"配置文件不存在: {config_file}"
            print(f"错误: {error_msg}")
            raise FileNotFoundError(error_msg)
            
        # 加载 .env 文件
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
                            missing_keys.append(f"{key}(无效的{target_type}值)")
                    else:
                        config[key] = env_value
            
            # 如果有缺失的配置项，抛出异常
            if missing_keys:
                error_msg = f"配置文件 {config_file} 中缺少必需的配置项: {', '.join(missing_keys)}"
                print(f"错误: {error_msg}")
                raise ValueError(error_msg)
        else:
            # 如果没有指定必需配置项，则加载所有环境变量
            for key, value in os.environ.items():
                if value.strip():
                    config[key] = value
                
        return config

    def setup_logging(self, log_dir: Optional[Path] = None, retention_days: int = 30) -> logging.Logger:
        """设置日志记录，按天分割日志文件，自动清理过期日志。"""
        if log_dir is None:
            log_dir = self.root / "logs"
            
        # 确保日志目录存在
        log_dir.mkdir(exist_ok=True)
        
        # 清理过期日志文件
        self.cleanup_old_logs(log_dir, retention_days)
        
        # 创建按天分割的日志文件名
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"{self.app_name}-{today}.log"
        
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
        logger.info(f"日志系统已启动，日志文件: {log_file}")
        return logger

    def cleanup_old_logs(self, log_dir: Path, retention_days: int) -> None:
        """清理超过保留天数的日志文件。"""
        if not log_dir.exists():
            return
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0
        
        for log_file in log_dir.glob(f"{self.app_name}-*.log"):
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
            print(f"[日志清理] 已删除 {deleted_count} 个过期日志文件")

    def send_mail(self, config: Dict[str, Any], subject: str, content: str) -> None:
        """发送邮件通知。"""
        smtp_host = config["SMTP_HOST"]
        smtp_port = config["SMTP_PORT"]
        username = config["SMTP_USERNAME"]
        password = config["SMTP_PASSWORD"]
        use_tls = config["SMTP_USE_TLS"]
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



# 为了向后兼容，提供独立的函数接口
def acquire_single_instance_lock(lock_file: Path, app_name: str = "check-web-alive") -> bool:
    """向后兼容的单例锁获取函数"""
    app = BaseApp(app_name)
    return app.acquire_single_instance_lock(lock_file)


def release_single_instance_lock(lock_file: Path, app_name: str = "check-web-alive") -> None:
    """向后兼容的单例锁释放函数"""
    app = BaseApp(app_name)
    app.release_single_instance_lock(lock_file)


def load_config() -> dict:
    """向后兼容的配置加载函数"""
    app = BaseApp("check-web-alive")
    return app.load_config()


def setup_logging(log_dir: Path, retention_days: int, app_name: str = "check-web-alive") -> logging.Logger:
    """向后兼容的日志设置函数"""
    app = BaseApp(app_name)
    return app.setup_logging(log_dir, retention_days)


def cleanup_old_logs(log_dir: Path, retention_days: int, app_name: str = "check-web-alive") -> None:
    """向后兼容的日志清理函数"""
    app = BaseApp(app_name)
    app.cleanup_old_logs(log_dir, retention_days)


def send_mail(cfg: dict, subject: str, content: str) -> None:
    """向后兼容的邮件发送函数"""
    app = BaseApp("check-web-alive")
    app.send_mail(cfg, subject, content)


