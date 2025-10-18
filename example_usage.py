"""
其他程序使用通用模块的示例
展示如何为不同的程序定义不同的配置项
"""
import time
from src.base import BaseApp

def main():
    # 创建其他应用实例
    app = BaseApp("other-app")
    
    # 获取单例锁
    if not app.acquire_single_instance_lock():
        print("检测到已有程序在运行，退出当前实例")
        return
    
    try:
        # 设置日志系统
        logger = app.setup_logging()
        
        # 加载配置（为其他程序定义不同的配置项）
        try:
            # 定义其他程序特有的配置项
            required_keys = [
                "API_URL",
                "API_KEY", 
                "DATABASE_HOST",
                "DATABASE_PORT",
                "WORKER_COUNT"
            ]
            
            # 定义类型转换规则
            type_conversions = {
                "DATABASE_PORT": "int",
                "WORKER_COUNT": "int",
                "ENABLE_DEBUG": "bool"
            }
            
            config = app.load_config(required_keys=required_keys, type_conversions=type_conversions)
            logger.info("配置加载成功")
            
        except (FileNotFoundError, ValueError) as config_error:
            logger.error(f"配置加载失败: {config_error}")
            print(f"配置加载失败: {config_error}")
            return
        
        logger.info("其他程序启动")
        
        # 模拟一些工作
        for i in range(3):
            logger.info(f"执行任务 {i+1}")
            time.sleep(1)
        
        # 其他程序不需要状态管理功能
        logger.info("其他程序执行中...")
        
        logger.info("其他程序完成")
        
    finally:
        # 释放锁
        app.release_single_instance_lock()

if __name__ == "__main__":
    main()
