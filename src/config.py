"""全局配置管理：从 config.json + 环境变量加载"""
import copy
import json
import os

DEFAULT_CONFIG = {
    "check_interval": 60,
    "consecutive_fail_threshold": 3,
    "alert_cooldown_seconds": 600,
    "request_timeout": 10,
    "api_base_url": "https://www.xbotos.com/center-api/robot/common/info/isAvailable",
    "alert_channels": ["sms"],
    "aliyun_sms": {
        "access_key_id": "",
        "access_key_secret": "",
        "sign_name": "银川慧疗互联网医院",
        "template_code": "SMS_505135345",
        "region_id": "cn-qingdao",
        "phone_numbers": ["18045034451"]
    },
    "email": {
        "smtp_host": "",
        "smtp_port": 465,
        "use_ssl": True,
        "username": "",
        "password": "",
        "from_addr": "",
        "to_addrs": []
    }
}

_config_cache = None


def load_config(config_path: str = None) -> dict:
    """加载配置：config.json 优先，缺失字段用默认值补全"""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    if config_path is None:
        config_path = _default_config_path()

    config = copy.deepcopy(DEFAULT_CONFIG)

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        # 合并：用户配置覆盖默认
        _deep_merge(config, user_config)

    # 环境变量优先（方便 Docker 部署）
    env_sms = config.get("aliyun_sms", {})
    env_sms["access_key_id"] = os.getenv("ALIYUN_ACCESS_KEY_ID", env_sms.get("access_key_id", ""))
    env_sms["access_key_secret"] = os.getenv("ALIYUN_ACCESS_KEY_SECRET", env_sms.get("access_key_secret", ""))
    env_sms["sign_name"] = os.getenv("ALIYUN_SMS_SIGN_NAME", env_sms.get("sign_name", "银川慧疗互联网医院"))
    env_sms["template_code"] = os.getenv("ALIYUN_SMS_TEMPLATE_CODE", env_sms.get("template_code", "SMS_XXXXXXX"))
    phones = os.getenv("ALIYUN_SMS_PHONE_NUMBERS", "")
    if phones:
        env_sms["phone_numbers"] = [p.strip() for p in phones.split(",") if p.strip()]
    config["aliyun_sms"] = env_sms

    channels = os.getenv("ALERT_CHANNELS", "")
    if channels:
        config["alert_channels"] = [c.strip() for c in channels.split(",") if c.strip()]

    env_email = config.get("email", {})
    env_email["smtp_host"] = os.getenv("EMAIL_SMTP_HOST", env_email.get("smtp_host", ""))
    env_email["smtp_port"] = _parse_int(os.getenv("EMAIL_SMTP_PORT"), env_email.get("smtp_port", 465))
    env_email["use_ssl"] = _parse_bool(os.getenv("EMAIL_USE_SSL"), env_email.get("use_ssl", True))
    env_email["username"] = os.getenv("EMAIL_USERNAME", env_email.get("username", ""))
    env_email["password"] = os.getenv("EMAIL_PASSWORD", env_email.get("password", ""))
    env_email["from_addr"] = os.getenv("EMAIL_FROM", env_email.get("from_addr", ""))
    email_to = os.getenv("EMAIL_TO", "")
    if email_to:
        env_email["to_addrs"] = [p.strip() for p in email_to.split(",") if p.strip()]
    config["email"] = env_email

    _config_cache = config
    return config


def save_config(config: dict, config_path: str = None):
    """保存配置到 config.json（排除敏感信息）"""
    if config_path is None:
        config_path = _default_config_path()

    to_save = copy.deepcopy(config)
    # 不保存空密钥到文件
    sms = to_save.get("aliyun_sms", {})
    if not sms.get("access_key_id") and not sms.get("access_key_secret"):
        sms["access_key_id"] = ""
        sms["access_key_secret"] = ""

    email = to_save.get("email", {})
    if not email.get("username") and not email.get("password"):
        email["username"] = ""
        email["password"] = ""

    os.makedirs(os.path.dirname(config_path), exist_ok=True)
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


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return int(default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _default_config_path() -> str:
    return os.getenv(
        "CONFIG_PATH",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json"),
    )
