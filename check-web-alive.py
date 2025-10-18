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
from typing import Optional, Tuple

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

import requests


# 全局锁句柄（Windows: mutex 句柄；Unix: 文件句柄）
_LOCK_HANDLE = None
_WIN_MUTEX_HANDLE = None
_WIN_ERROR_ALREADY_EXISTS = 183


# 兼容 PyInstaller 打包后的路径问题
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后的情况
    ROOT = Path(sys.executable).parent
else:
    # 开发环境的情况
    ROOT = Path(__file__).resolve().parent




def _acquire_windows_mutex(name: str) -> bool:
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


def acquire_single_instance_lock(lock_file: Path) -> bool:
	"""尝试获取单实例锁。Windows用命名互斥量；Unix用fcntl文件锁。"""
	global _LOCK_HANDLE
	try:
		if os.name == 'nt':
			##print("33333")
			# Windows: 使用命名互斥量
			return _acquire_windows_mutex('check-web-alive-mutex')
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


def release_single_instance_lock(lock_file: Path) -> None:
	"""释放单实例锁。"""
	global _LOCK_HANDLE, _WIN_MUTEX_HANDLE
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


def load_config() -> dict:
	"""加载配置，优先读取 .env 文件，其次读取系统环境变量。"""
	
	dotenv_path = ROOT / ".env"
	if not dotenv_path.exists() and not getattr(sys, 'frozen', False):
		script_dir = Path(__file__).resolve().parent
		dotenv_path = script_dir / ".env"
	if load_dotenv and dotenv_path.exists():
		load_dotenv(dotenv_path)
	config = {
		"TARGET_URL": os.getenv("TARGET_URL", "https://www.axured.cn"),
		"CHECK_INTERVAL_SECONDS": int(os.getenv("CHECK_INTERVAL_SECONDS", "60")),
		"SMTP_HOST": os.getenv("SMTP_HOST", ""),
		"SMTP_PORT": int(os.getenv("SMTP_PORT", "465")),
		"SMTP_USERNAME": os.getenv("SMTP_USERNAME", ""),
		"SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", ""),
		"SMTP_USE_TLS": os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "y"},
		"MAIL_FROM": os.getenv("MAIL_FROM", os.getenv("SMTP_USERNAME", "")),
		"MAIL_TO": os.getenv("MAIL_TO", "astonish921@126.com"),
		"REQUEST_TIMEOUT_SECONDS": int(os.getenv("REQUEST_TIMEOUT_SECONDS", "10")),
		"LOG_RETENTION_DAYS": int(os.getenv("LOG_RETENTION_DAYS", "30")),
	}
	return config


def read_state(state_file: Path) -> Tuple[Optional[bool], Optional[int]]:
	"""读取上次状态（是否可达、时间戳）。"""
	if not state_file.exists():
		return None, None
	try:
		data = json.loads(state_file.read_text(encoding="utf-8"))
		return data.get("last_ok"), data.get("last_change_ts")
	except Exception:
		return None, None


def write_state(state_file: Path, last_ok: bool) -> None:
	state = {"last_ok": last_ok, "last_change_ts": int(time.time())}
	state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def check_url(url: str, timeout_seconds: int) -> Tuple[bool, Optional[int], Optional[str]]:
	"""检查目标URL是否可达。

	返回: (是否可达, HTTP状态码或None, 错误消息或None)
	"""
	try:
		resp = requests.get(url, timeout=timeout_seconds)
		# 认为 <400 为可达；>=400 为不可达
		ok = resp.status_code < 400
		return ok, resp.status_code, None
	except Exception as exc:
		return False, None, str(exc)


def setup_logging(log_dir: Path, retention_days: int) -> logging.Logger:
	"""设置日志记录，按天分割日志文件，自动清理过期日志。"""
	# 确保日志目录存在
	log_dir.mkdir(exist_ok=True)
	
	# 清理过期日志文件
	cleanup_old_logs(log_dir, retention_days)
	
	# 创建按天分割的日志文件名
	today = datetime.now().strftime("%Y-%m-%d")
	log_file = log_dir / f"check-web-alive-{today}.log"
	
	# 配置日志格式
	logging.basicConfig(
		level=logging.INFO,
		format='%(asctime)s - %(levelname)s - %(message)s',
		handlers=[
			logging.FileHandler(log_file, encoding='utf-8'),
			logging.StreamHandler()  # 同时输出到控制台
		]
	)
	
	logger = logging.getLogger(__name__)
	logger.info(f"日志系统已启动，日志文件: {log_file}")
	return logger


def cleanup_old_logs(log_dir: Path, retention_days: int) -> None:
	"""清理超过保留天数的日志文件。"""
	if not log_dir.exists():
		return
	
	cutoff_date = datetime.now() - timedelta(days=retention_days)
	deleted_count = 0
	
	for log_file in log_dir.glob("check-web-alive-*.log"):
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


def send_mail(cfg: dict, subject: str, content: str) -> None:
	"""发送邮件通知。"""
	smtp_host = cfg["SMTP_HOST"]
	smtp_port = cfg["SMTP_PORT"]
	username = cfg["SMTP_USERNAME"]
	password = cfg["SMTP_PASSWORD"]
	use_tls = cfg["SMTP_USE_TLS"]
	mail_from = cfg["MAIL_FROM"]
	mail_to = cfg["MAIL_TO"]

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


def main() -> None:
	cfg = load_config()
	
	state_file = ROOT / "state.json"
	lock_file = ROOT / "check-web-alive.lock"
	
	# 基于文件锁的单实例
	if not acquire_single_instance_lock(lock_file):
		print("检测到已有监控程序在运行，退出当前实例")
		sys.exit(1)
	
	try:
		last_ok, _ = read_state(state_file)

		url = cfg["TARGET_URL"]
		interval = cfg["CHECK_INTERVAL_SECONDS"]
		request_timeout = cfg["REQUEST_TIMEOUT_SECONDS"]
		retention_days = cfg["LOG_RETENTION_DAYS"]

		# 设置日志系统
		log_dir = ROOT / "logs"
		logger = setup_logging(log_dir, retention_days)
		
		logger.info(f"监控启动: {url}，检查间隔: {interval}s，日志保留: {retention_days}天")
		logger.info(f"进程ID: {os.getpid()}")

		while True:
			ok, status_code, error_msg = check_url(url, request_timeout)
			status_text = f"{status_code}" if status_code is not None else "EXCEPTION"
			
			# 记录检查结果到日志
			logger.info(f"检查结果 - URL: {url}, 状态: {status_text}, 可达: {ok}")
			if error_msg:
				logger.warning(f"请求异常: {error_msg}")

			# 仅在状态由 OK -> NG 时发送一封报警，避免每分钟刷屏
			if ok is False and (last_ok is True or last_ok is None):
				try:
					subject = "axure网站挂了"
					# 邮件正文包含简单上下文
					content = (
						"axure网站挂了\n\n"
						f"URL: {url}\n"
						f"状态: {status_text}\n"
						f"错误: {error_msg or ''}\n"
						f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
					)
					send_mail(cfg, subject, content)
					logger.info("已发送告警邮件")
				except Exception as mail_exc:
					logger.error(f"发送邮件失败: {mail_exc}")

			# 记录最新状态
			if last_ok is None or last_ok != ok:
				write_state(state_file, ok)
				last_ok = ok
				logger.info(f"状态变更: {last_ok} -> {ok}")

			time.sleep(interval)
	
	except KeyboardInterrupt:
		logger.info("收到中断信号，正在退出...")
	except Exception as e:
		logger.error(f"程序异常: {e}")
		raise
	finally:
		# 清理锁文件
		release_single_instance_lock(lock_file)
		logger.info("程序已退出，锁文件已清理")


if __name__ == "__main__":
	main()


