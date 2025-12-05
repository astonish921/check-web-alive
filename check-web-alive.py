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
	"""读取状态信息。
	
	返回: (last_ok, first_ng_ts, first_ok_ts, last_update_ts, last_alert_ts)
	- last_ok: 最新一次检查的状态（True/False/None）
	- first_ng_ts: 最早发现异常的时间戳（None表示当前正常）
	- first_ok_ts: 最早转为正常的时间戳（None表示当前异常）
	- last_update_ts: 最新一次登记的时间戳
	- last_alert_ts: 上次发送告警/统计邮件的时间戳（None表示未发送过）
	"""
	if not state_file.exists():
		return None, None, None, None, None
	try:
		data = json.loads(state_file.read_text(encoding="utf-8"))
		return (
			data.get("last_ok"),
			data.get("first_ng_ts"),
			data.get("first_ok_ts"),
			data.get("last_update_ts"),
			data.get("last_alert_ts")
		)
	except Exception:
		return None, None, None, None, None


def write_state(state_file, last_ok, first_ng_ts=None, first_ok_ts=None, last_alert_ts=None):
	"""写入状态到文件。
	
	Args:
		last_ok: 最新一次检查的状态
		first_ng_ts: 最早发现异常的时间戳（如果为None，则从现有状态读取或设置）
		first_ok_ts: 最早转为正常的时间戳（如果为None，则从现有状态读取或设置）
		last_alert_ts: 上次发送告警/统计邮件的时间戳（如果为None，则从现有状态读取）
	"""
	current_time = int(time.time())
	
	# 读取现有状态（如果存在）
	existing_last_ok, existing_first_ng_ts, existing_first_ok_ts, _, existing_last_alert_ts = read_state(state_file)
	
	# 如果未指定，则从现有状态继承
	if first_ng_ts is None:
		first_ng_ts = existing_first_ng_ts
	if first_ok_ts is None:
		first_ok_ts = existing_first_ok_ts
	if last_alert_ts is None:
		last_alert_ts = existing_last_alert_ts
	
	# 如果状态从正常变为异常，记录最早异常时间，清除告警时间
	if last_ok is False and (existing_last_ok is True or existing_last_ok is None):
		if first_ng_ts is None:
			first_ng_ts = current_time
		first_ok_ts = None  # 清除正常时间
		last_alert_ts = None  # 清除上次告警时间（首次告警会重新设置）
	
	# 如果状态从异常变为正常，记录最早正常时间，清除告警时间
	if last_ok is True and existing_last_ok is False:
		if first_ok_ts is None:
			first_ok_ts = current_time
		first_ng_ts = None  # 清除异常时间
		last_alert_ts = None  # 清除上次告警时间
	
	state = {
		"last_ok": last_ok,
		"first_ng_ts": first_ng_ts,
		"first_ok_ts": first_ok_ts,
		"last_update_ts": current_time,
		"last_alert_ts": last_alert_ts
	}
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
				"LOG_RETENTION_DAYS",
				"SMTP_USE_TLS",  # 是否启用TLS，避免后续发送邮件时报 KeyError
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
		last_ok, first_ng_ts, first_ok_ts, last_update_ts, last_alert_ts = read_state(state_file)

		url = cfg["TARGET_URL"]
		interval = cfg["CHECK_INTERVAL_SECONDS"]
		request_timeout = cfg["REQUEST_TIMEOUT_SECONDS"]
		# 异常持续超过20分钟（1200秒）后再次发送邮件
		ALERT_INTERVAL_SECONDS = 20 * 60
		
		logger.info("监控启动: {}，检查间隔: {}s，日志保留: {}天".format(url, interval, cfg['LOG_RETENTION_DAYS']))
		logger.info("进程ID: {}".format(os.getpid()))

		while True:
			ok, status_code, error_msg = check_url(url, request_timeout)
			status_text = "{}".format(status_code) if status_code is not None else "EXCEPTION"
			current_time = int(time.time())
			
			# 记录检查结果到日志
			logger.info("检查结果 - URL: {}, 状态: {}, 可达: {}".format(url, status_text, ok))
			if error_msg:
				logger.warning("请求异常: {}".format(error_msg))

			# 1. 如果状态从异常恢复为正常，发送恢复通知
			if ok is True and last_ok is False:
				try:
					# 计算异常持续时间
					duration_minutes = 0
					if first_ng_ts:
						duration_seconds = current_time - first_ng_ts
						duration_minutes = duration_seconds // 60
					
					subject = "axure网站已恢复正常"
					content = (
						"axure网站已恢复正常\n\n"
						"URL: {}\n"
						"状态: {}\n"
						"异常持续时间: {} 分钟\n"
						"恢复时间: {}\n"
					).format(
						url, 
						status_text, 
						duration_minutes,
						time.strftime('%Y-%m-%d %H:%M:%S')
					)
					app.send_mail(cfg, subject, content)
					logger.info("已发送恢复通知邮件")
					last_alert_ts = current_time  # 记录发送恢复通知的时间
				except Exception as mail_exc:
					logger.error("发送邮件失败: {}".format(mail_exc))
			
			# 2. 如果状态从正常变为异常，发送首次告警
			elif ok is False and (last_ok is True or last_ok is None):
				try:
					subject = "axure网站挂了"
					content = (
						"axure网站挂了\n\n"
						"URL: {}\n"
						"状态: {}\n"
						"错误: {}\n"
						"时间: {}\n"
					).format(url, status_text, error_msg or '', time.strftime('%Y-%m-%d %H:%M:%S'))
					app.send_mail(cfg, subject, content)
					logger.info("已发送告警邮件")
					last_alert_ts = current_time  # 记录发送首次告警的时间
				except Exception as mail_exc:
					logger.error("发送邮件失败: {}".format(mail_exc))
			
			# 3. 如果持续异常，且距离上次发送告警时间超过20分钟，再次发送统计邮件
			elif ok is False and last_ok is False:
				# 计算距离最早异常时间
				if first_ng_ts:
					elapsed_seconds = current_time - first_ng_ts
					# 如果异常持续时间超过20分钟，且距离上次发送告警超过20分钟
					if elapsed_seconds >= ALERT_INTERVAL_SECONDS:
						# 检查距离上次发送告警的时间
						time_since_last_alert = current_time - last_alert_ts if last_alert_ts else elapsed_seconds
						if time_since_last_alert >= ALERT_INTERVAL_SECONDS:
							try:
								duration_minutes = elapsed_seconds // 60
								subject = "axure网站持续异常"
								content = (
									"axure网站持续异常\n\n"
									"URL: {}\n"
									"状态: {}\n"
									"错误: {}\n"
									"异常持续时间: {} 分钟\n"
									"统计时间: {}\n"
								).format(
									url, 
									status_text, 
									error_msg or '',
									duration_minutes,
									time.strftime('%Y-%m-%d %H:%M:%S')
								)
								app.send_mail(cfg, subject, content)
								logger.info("已发送持续异常统计邮件（异常持续 {} 分钟）".format(duration_minutes))
								last_alert_ts = current_time  # 记录发送统计邮件的时间
							except Exception as mail_exc:
								logger.error("发送邮件失败: {}".format(mail_exc))

			# 记录最新状态（无论是否变化都更新 last_update_ts）
			state_changed = (last_ok is None or last_ok != ok)
			if state_changed:
				write_state(state_file, ok, first_ng_ts, first_ok_ts, last_alert_ts)
				logger.info("状态变更: {} -> {}".format(last_ok, ok))
				# 重新读取状态以获取更新后的时间戳
				last_ok, first_ng_ts, first_ok_ts, last_update_ts, last_alert_ts = read_state(state_file)
			else:
				# 即使状态未变化，也更新 last_update_ts 和 last_alert_ts
				write_state(state_file, ok, first_ng_ts, first_ok_ts, last_alert_ts)
				last_update_ts = current_time

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


