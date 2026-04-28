"""监控引擎：后台线程持续检测机器人状态"""
import time
import threading
import requests
import logging
import os
from logging.handlers import RotatingFileHandler
import src.data as data
from src.config import load_config
from src.alert import check_and_alert

# 创建日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 配置日志
logger = logging.getLogger("monitor")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "monitor.log"),
    maxBytes=5*1024*1024,  # 5MB
    backupCount=3,
    encoding="utf-8"
)
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(handler)

# 同时输出到控制台
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logger.addHandler(console_handler)

_running = False
_thread = None
_status_lock = threading.Lock()


def check_single_robot(robot: dict) -> dict:
    """检测单个机器人，返回检测结果字典"""
    config = load_config()
    url = config.get("api_base_url", "https://www.xbotos.com/center-api/robot/common/info/isAvailable")
    timeout = config.get("request_timeout", 10)

    payload = {
        "apiKey": robot["api_key"],
        "robotId": robot["id"]
    }

    start = time.time()
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        elapsed_ms = (time.time() - start) * 1000
        res_json = resp.json()

        if res_json.get("success") and res_json.get("data") is True:
            return {
                "success": True,
                "detail": "在线 (Available)",
                "elapsed_ms": elapsed_ms
            }
        else:
            data_str = res_json.get("data", "")
            return {
                "success": False,
                "detail": f"不可用 (响应: {data_str})",
                "elapsed_ms": elapsed_ms
            }
    except requests.exceptions.Timeout:
        elapsed_ms = (time.time() - start) * 1000
        return {"success": False, "detail": "请求超时", "elapsed_ms": elapsed_ms}
    except requests.exceptions.ConnectionError as e:
        elapsed_ms = (time.time() - start) * 1000
        return {"success": False, "detail": "连接失败", "elapsed_ms": elapsed_ms}
    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        return {"success": False, "detail": f"异常: {str(e)[:100]}", "elapsed_ms": elapsed_ms}


def monitor_loop():
    """监控主循环"""
    global _running
    config = load_config()
    interval = config.get("check_interval", 60)

    logger.info(f"监控引擎启动，检测间隔 {interval} 秒")

    while _running:
        robots = data.load_robots()
        if not robots:
            time.sleep(5)
            continue

        for robot in robots:
            if not _running:
                break
            if not robot.get("enabled", True):
                # 已禁用的机器人，标记状态
                robot["status"] = "已禁用"
                robot["color"] = "secondary"
                continue

            logger.info(f"检测机器人: {robot['name']}...")
            result = check_single_robot(robot)

            if result["success"]:
                robot["status"] = result["detail"]
                robot["color"] = "success"
                robot["consecutive_fail_count"] = 0
                logger.info(f"{robot['name']}: 在线")
            else:
                robot["consecutive_fail_count"] = robot.get("consecutive_fail_count", 0) + 1
                robot["status"] = result["detail"]
                if robot["consecutive_fail_count"] >= config.get("consecutive_fail_threshold", 3):
                    robot["color"] = "danger"
                    logger.warning(f"{robot['name']}: 异常 - {result['detail']} (连续失败 {robot['consecutive_fail_count']} 次)")
                else:
                    robot["color"] = "warning"
                    logger.warning(f"{robot['name']}: 警告 - {result['detail']} (连续失败 {robot['consecutive_fail_count']} 次)")
                check_and_alert(robot)

            robot["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # 更新到数据层
            try:
                data.update_robot(robot["id"], {
                    "status": robot["status"],
                    "color": robot["color"],
                    "last_update": robot["last_update"],
                    "consecutive_fail_count": robot["consecutive_fail_count"],
                    "last_alert_time": robot.get("last_alert_time", 0),
                })
            except ValueError:
                pass

            # 记录历史
            data.add_history(
                robot["id"], robot["name"],
                result["success"], result["detail"], result["elapsed_ms"]
            )

            # 间隔一下再检测下一个，避免过快
            time.sleep(1)

        # 一轮检测完，休息
        time.sleep(interval)

    logger.info("监控引擎已停止")


def start_monitor():
    """启动监控引擎（仅启动一次）"""
    global _running, _thread
    with _status_lock:
        if _running:
            return False
        _running = True
        _thread = threading.Thread(target=monitor_loop, daemon=True, name="monitor")
        _thread.start()
        return True


def stop_monitor():
    """停止监控引擎"""
    global _running
    with _status_lock:
        _running = False
    if _thread:
        _thread.join(timeout=5)


def is_running() -> bool:
    return _running
