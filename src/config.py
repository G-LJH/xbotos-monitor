"""全局配置管理：从 config.json + 环境变量加载"""
import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "check_interval": 60,
    "consecutive_fail_threshold": 3,
    "alert_cooldown_seconds": 600,
    "request_timeout": 10,
    "api_base_url": "https://www.xbotos.com/center-api/robot/common/info/isAvailable",
    "aliyun_sms": {
        "access_key_id": "",
        "access_key_secret": "",
        "sign_name": "机器人监控",
        "template_code": "SMS_XXXXXXX",
        "phone_numbers": []
    }
}

_config_cache = None


def load_config(config_path: str = None) -> dict:
    """加载配置：config.json 优先，缺失字段用默认值补全"""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

    config = dict(DEFAULT_CONFIG)

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        # 合并：用户配置覆盖默认
        _deep_merge(config, user_config)

    # 环境变量优先（方便 Docker 部署）
    env_sms = config.get("aliyun_sms", {})
    env_sms["access_key_id"] = os.getenv("ALIYUN_ACCESS_KEY_ID", env_sms.get("access_key_id", ""))
    env_sms["access_key_secret"] = os.getenv("ALIYUN_ACCESS_KEY_SECRET", env_sms.get("access_key_secret", ""))
    env_sms["sign_name"] = os.getenv("ALIYUN_SMS_SIGN_NAME", env_sms.get("sign_name", "机器人监控"))
    env_sms["template_code"] = os.getenv("ALIYUN_SMS_TEMPLATE_CODE", env_sms.get("template_code", "SMS_XXXXXXX"))
    phones = os.getenv("ALIYUN_SMS_PHONE_NUMBERS", "")
    if phones:
        env_sms["phone_numbers"] = [p.strip() for p in phones.split(",") if p.strip()]
    config["aliyun_sms"] = env_sms

    _config_cache = config
    return config


def save_config(config: dict, config_path: str = None):
    """保存配置到 config.json（排除敏感信息）"""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

    to_save = dict(config)
    # 不保存空密钥到文件
    sms = to_save.get("aliyun_sms", {})
    if not sms.get("access_key_id") and not sms.get("access_key_secret"):
        sms["access_key_id"] = ""
        sms["access_key_secret"] = ""

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)

    global _config_cache
    _config_cache = to_save


def _deep_merge(base: dict, override: dict):
    """深度合并字典"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
