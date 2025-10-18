"""
基础通用能力模块包
"""
from .base import BaseApp, acquire_single_instance_lock, release_single_instance_lock, load_config, setup_logging, send_mail

__all__ = [
    'BaseApp',
    'acquire_single_instance_lock', 
    'release_single_instance_lock',
    'load_config',
    'setup_logging', 
    'send_mail'
]
