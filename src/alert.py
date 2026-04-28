"""阿里云短信告警 - 完全参照 test.py"""
import json
import random
import time
import logging
import os
from logging.handlers import RotatingFileHandler
import src.data as data
from src.config import load_config

# 创建日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 配置日志
logger = logging.getLogger("alert")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "alert.log"),
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


def send_sms(phone_number: str, robot_name: str, fail_count: int) -> bool:
    """发送阿里云短信，返回是否成功（完全参照 test.py）"""
    config = load_config()
    sms_cfg = config.get("aliyun_sms", {})

    ak = sms_cfg.get("access_key_id", "")
    sk = sms_cfg.get("access_key_secret", "")
    if not ak or not sk:
        logger.warning("[告警] 未配置阿里云 AccessKey，跳过短信发送")
        return False

    sign_name = sms_cfg.get("sign_name", "银川慧疗互联网医院")
    template_code = sms_cfg.get("template_code", "")
    region_id = sms_cfg.get("region_id", "cn-qingdao")
    
    if not template_code:
        logger.warning("[告警] 未配置短信模板CODE，跳过短信发送")
        return False

    try:
        logger.info("导入模块...")
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkdysmsapi.request.v20170525 import SendSmsRequest
        logger.info("模块导入成功")

        logger.info(f"初始化客户端，区域: {region_id}...")
        client = AcsClient(ak, sk, region_id)
        logger.info("客户端初始化成功")

        # 生成随机6位验证码
        code = str(random.randint(100000, 999999))
        logger.info(f"生成验证码: {code}")

        logger.info("配置短信请求参数...")
        request = SendSmsRequest.SendSmsRequest()
        request.set_PhoneNumbers(phone_number)
        request.set_SignName(sign_name)
        request.set_TemplateCode(template_code)
        request.set_TemplateParam(json.dumps({"code": code}))
        logger.info("参数配置完成")

        logger.info("发送短信请求...")
        response = client.do_action_with_exception(request)
        logger.info("请求发送成功!")
        logger.info("响应结果: %s", response.decode("utf-8"))
        logger.info("发送验证码: %s", code)
        return True
            
    except Exception as e:
        logger.error("发送失败! 异常类型: %s, 异常信息: %s", type(e).__name__, e)
        import traceback
        traceback.print_exc()
        return False


def check_and_alert(robot: dict):
    """检查是否需要发送告警（连续失败达到阈值时才推送）"""
    config = load_config()
    threshold = config.get("consecutive_fail_threshold", 3)
    cooldown = config.get("alert_cooldown_seconds", 600)

    fail_count = robot.get("consecutive_fail_count", 0)
    if fail_count < threshold:
        return

    current_time = time.time()
    last_alert = robot.get("last_alert_time", 0)
    if current_time - last_alert < cooldown:
        return

    phones = config.get("aliyun_sms", {}).get("phone_numbers", [])
    sms_cfg = config.get("aliyun_sms", {})
    
    logger.debug("AccessKey ID 已配置: %s", bool(sms_cfg.get('access_key_id')))
    logger.debug("AccessKey Secret 已配置: %s", bool(sms_cfg.get('access_key_secret')))
    logger.debug("区域: %s", sms_cfg.get('region_id', 'cn-qingdao'))
    logger.debug("签名: %s", sms_cfg.get('sign_name', '银川慧疗互联网医院'))
    logger.debug("模板CODE: %s", sms_cfg.get('template_code'))
    logger.debug("接收号码列表: %s", phones)
    
    if not phones:
        logger.warning("[告警] 未配置短信号码，跳过 [%s]", robot.get('name', ''))
        data.add_alert(
            robot["id"], robot["name"],
            "告警(未发送)",
            f"连续失败 {fail_count} 次，未配置短信号码",
            sms_sent=False
        )
        return

    logger.warning("[告警] 触发告警: %s 已连续失败 %s 次", robot['name'], fail_count)

    any_sent = False
    for phone in phones:
        phone = phone.strip()
        if phone:
            logger.info("[短信] 准备发送到: %s", phone)
            ok = send_sms(phone, robot["name"], fail_count)
            if ok:
                any_sent = True

    data.add_alert(
        robot["id"], robot["name"],
        "告警",
        f"连续失败 {fail_count} 次",
        sms_sent=any_sent
    )
    robot["last_alert_time"] = current_time
