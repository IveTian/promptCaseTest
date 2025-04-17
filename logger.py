#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time

class LogColor:
    """控制台颜色常量"""
    RESET = "\033[0m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"

def get_spinner_char():
    """获取动态加载符号"""
    spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    spinner_idx = int(time.time() * 15) % len(spinner_chars)
    return spinner_chars[spinner_idx]

def log_debug(message):
    """调试级别日志，使用蓝色显示"""
    spinner = get_spinner_char()
    print(f"{LogColor.BLUE}{spinner} DEBUG{LogColor.RESET}: {message}")
    
def log_info(message):
    """信息级别日志，使用绿色✓图标"""
    print(f"{LogColor.GREEN}✓{LogColor.RESET} {message}")
    
def log_warning(message):
    """警告级别日志，使用黄色警告图标"""
    print(f"{LogColor.YELLOW}⚠{LogColor.RESET} {message}")
    
def log_error(message):
    """错误级别日志，使用红色错误图标"""
    print(f"{LogColor.RED}✗{LogColor.RESET} {message}")

def log_system(message):
    """系统信息日志，使用青色图标"""
    spinner = get_spinner_char()
    print(f"{LogColor.BOLD}{LogColor.CYAN}{spinner}{LogColor.RESET} {message}")

def log_ai_output(message: str):
    """打印AI输出日志"""
    print(f"{LogColor.BOLD}{LogColor.MAGENTA}◉{LogColor.RESET} {message}") 