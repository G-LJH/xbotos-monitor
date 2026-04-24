"""数据管理：机器人配置 + 检测历史 + 告警记录，全部存为 JSON 文件"""
import json
import os
import threading
from datetime import datetime

_lock = threading.Lock()


def _data_dir():
    d = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    os.makedirs(d, exist_ok=True)
    return d


def _path(name):
    return os.path.join(_data_dir(), f"{name}.json")


# ---- 机器人配置 ----

def load_robots() -> list:
    p = _path("robots")
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_robots(robots: list):
    with _lock:
        with open(_path("robots"), "w", encoding="utf-8") as f:
            json.dump(robots, f, ensure_ascii=False, indent=2)


def get_robot(robot_id: str) -> dict | None:
    for r in load_robots():
        if r["id"] == robot_id:
            return r
    return None


def add_robot(robot: dict):
    robots = load_robots()
    # 检查重复
    for r in robots:
        if r["id"] == robot["id"]:
            raise ValueError(f"机器人 ID {robot['id']} 已存在")
    # 初始化运行时字段
    robot.setdefault("status", "未检测")
    robot.setdefault("color", "secondary")
    robot.setdefault("last_update", "-")
    robot.setdefault("consecutive_fail_count", 0)
    robot.setdefault("last_alert_time", 0)
    robot.setdefault("enabled", True)
    robots.append(robot)
    save_robots(robots)


def update_robot(robot_id: str, updates: dict):
    robots = load_robots()
    for r in robots:
        if r["id"] == robot_id:
            r.update(updates)
            save_robots(robots)
            return
    raise ValueError(f"机器人 ID {robot_id} 不存在")


def delete_robot(robot_id: str):
    robots = load_robots()
    robots = [r for r in robots if r["id"] != robot_id]
    save_robots(robots)


# ---- 检测历史 ----

def load_history(robot_id: str = None, limit: int = 200) -> list:
    p = _path("history")
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8") as f:
        records = json.load(f)

    if robot_id:
        records = [r for r in records if r.get("robot_id") == robot_id]

    return records[-limit:]


def add_history(robot_id: str, robot_name: str, success: bool, detail: str, response_time_ms: float):
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "robot_id": robot_id,
        "robot_name": robot_name,
        "success": success,
        "detail": detail,
        "response_time_ms": round(response_time_ms, 1)
    }
    p = _path("history")
    with _lock:
        records = []
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                try:
                    records = json.load(f)
                except json.JSONDecodeError:
                    records = []
        records.append(record)
        # 保留最近 5000 条
        if len(records) > 5000:
            records = records[-5000:]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)


# ---- 告警记录 ----

def load_alerts(limit: int = 200) -> list:
    p = _path("alerts")
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8") as f:
        records = json.load(f)
    return records[-limit:]


def add_alert(robot_id: str, robot_name: str, alert_type: str, message: str, sms_sent: bool = False):
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "robot_id": robot_id,
        "robot_name": robot_name,
        "type": alert_type,
        "message": message,
        "sms_sent": sms_sent
    }
    p = _path("alerts")
    with _lock:
        records = []
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                try:
                    records = json.load(f)
                except json.JSONDecodeError:
                    records = []
        records.append(record)
        if len(records) > 2000:
            records = records[-2000:]
        with open(p, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False)
