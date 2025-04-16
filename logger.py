#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class LogColor:
    # 字体颜色
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    # 效果
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    # 恢复默认设置
    RESET = '\033[0m'

def log_info(message: str):
    """打印信息日志"""
    print(f"{LogColor.BOLD}{LogColor.GREEN}[INFO]{LogColor.RESET} {message}")

def log_warning(message: str):
    """打印警告日志"""
    print(f"{LogColor.BOLD}{LogColor.YELLOW}[WARN]{LogColor.RESET} {message}")

def log_error(message: str):
    """打印错误日志"""
    print(f"{LogColor.BOLD}{LogColor.RED}[ERR]{LogColor.RESET} {message}")

def log_debug(message: str):
    """打印调试日志"""
    print(f"{LogColor.BOLD}{LogColor.BLUE}[DEBUG]{LogColor.RESET} {message}")

def log_ai_output(message: str):
    """打印AI输出日志"""
    print(f"{LogColor.BOLD}{LogColor.MAGENTA}[AI]{LogColor.RESET} {message}")

def log_system(message: str):
    """打印系统日志"""
    print(f"{LogColor.BOLD}{LogColor.CYAN}[SYS]{LogColor.RESET} {message}") 