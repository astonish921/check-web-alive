import os
import sys
import time
import json
from pathlib import Path
try:
    from typing import Optional, Tuple
except ImportError:
    # Python 3.6 兼容性
    Optional = None
    Tuple = None

import requests

# 导入基础通用能力
from src.base import BaseApp




## ========begin 业务代码 =============

def read_state(state_file):
	"""读取上次状态（是否可达、时间戳）。"""
	if not state_file.exists():
		return None, None
	try:
		data = json.loads(state_file.read_text(encoding="utf-8"))
		return data.get("last_ok"), data.get("last_change_ts")
	except Exception:
		return None, None


def write_state(state_file, last_ok):
	"""写入状态到文件。"""
	state = {"last_ok": last_ok, "last_change_ts": int(time.time())}
	state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def check_url(url, timeout_seconds):
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

## ========end 业务代码 =============


def main() -> None:
	# 创建基础应用实例
	app = BaseApp("check-web-alive")
	
	# 获取单例锁
	if not app.acquire_single_instance_lock():
		print("检测到已有监控程序在运行，退出当前实例")
		sys.exit(1)
	
	try:
		# 设置日志系统（在配置加载之前，用于记录配置错误）
		logger = app.setup_logging()
		
		# 加载配置
		try:
			## ========按具体业务代码需求定义配置项=============
			# 定义网站监控程序必需的配置项
			required_keys = [
				"TARGET_URL",
				"CHECK_INTERVAL_SECONDS", 
				"SMTP_HOST",
				"SMTP_PORT",
				"SMTP_USERNAME",
				"SMTP_PASSWORD",
				"MAIL_FROM",
				"MAIL_TO",
				"REQUEST_TIMEOUT_SECONDS",
				"LOG_RETENTION_DAYS"
			]
			
			## ========按具体业务代码需求定义类型转换规则=============
			# 定义类型转换规则
			type_conversions = {
				"CHECK_INTERVAL_SECONDS": "int",
				"SMTP_PORT": "int", 
				"REQUEST_TIMEOUT_SECONDS": "int",
				"LOG_RETENTION_DAYS": "int",
				"SMTP_USE_TLS": "bool"
			}
			
			cfg = app.load_config(required_keys=required_keys, type_conversions=type_conversions)
			
			# 特殊处理：如果MAIL_FROM为空，使用SMTP_USERNAME
			if not cfg.get("MAIL_FROM") and cfg.get("SMTP_USERNAME"):
				cfg["MAIL_FROM"] = cfg["SMTP_USERNAME"]
				
		except (FileNotFoundError, ValueError) as config_error:
			logger.error("配置加载失败: {}".format(config_error))
			print("配置加载失败: {}".format(config_error))
			sys.exit(1)
		
		## ========begin 业务代码 =============
		# 创建 rundata 目录（如果不存在）
		rundata_dir = app.root / "rundata"
		rundata_dir.mkdir(exist_ok=True)
		
		# 读取上次状态
		state_file = rundata_dir / "state.json"
		last_ok, _ = read_state(state_file)

		url = cfg["TARGET_URL"]
		interval = cfg["CHECK_INTERVAL_SECONDS"]
		request_timeout = cfg["REQUEST_TIMEOUT_SECONDS"]
		
		logger.info("监控启动: {}，检查间隔: {}s，日志保留: {}天".format(url, interval, cfg['LOG_RETENTION_DAYS']))
		logger.info("进程ID: {}".format(os.getpid()))

		while True:
			ok, status_code, error_msg = check_url(url, request_timeout)
			status_text = "{}".format(status_code) if status_code is not None else "EXCEPTION"
			
			# 记录检查结果到日志
			logger.info("检查结果 - URL: {}, 状态: {}, 可达: {}".format(url, status_text, ok))
			if error_msg:
				logger.warning("请求异常: {}".format(error_msg))

			# 仅在状态由 OK -> NG 时发送一封报警，避免每分钟刷屏
			if ok is False and (last_ok is True or last_ok is None):
				try:
					subject = "axure网站挂了"
					# 邮件正文包含简单上下文
					content = (
						"axure网站挂了\n\n"
						"URL: {}\n"
						"状态: {}\n"
						"错误: {}\n"
						"时间: {}\n"
					).format(url, status_text, error_msg or '', time.strftime('%Y-%m-%d %H:%M:%S'))
					app.send_mail(cfg, subject, content)
					logger.info("已发送告警邮件")
				except Exception as mail_exc:
					logger.error("发送邮件失败: {}".format(mail_exc))

			# 记录最新状态
			if last_ok is None or last_ok != ok:
				write_state(state_file, ok)
				last_ok = ok
				logger.info("状态变更: {} -> {}".format(last_ok, ok))

			time.sleep(interval)
		## ========end 业务代码 =============
	
	except KeyboardInterrupt:
		logger.info("收到中断信号，正在退出...")
	except Exception as e:
		logger.error("程序异常: {}".format(e))
		raise
	finally:
		# 清理锁文件
		app.release_single_instance_lock()
		logger.info("程序已退出，锁文件已清理")


if __name__ == "__main__":
	main()


