"""阿里云短信告警"""
import json
import time
import src.data as data
from src.config import load_config


def send_sms(phone_number: str, robot_name: str, fail_count: int) -> bool:
    """发送阿里云短信，返回是否成功"""
    config = load_config()
    sms_cfg = config.get("aliyun_sms", {})

    ak = sms_cfg.get("access_key_id", "")
    sk = sms_cfg.get("access_key_secret", "")
    if not ak or not sk:
        print("[告警] 未配置阿里云 AccessKey，跳过短信发送")
        return False

    try:
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.request import CommonRequest

        client = AcsClient(ak, sk, "cn-hangzhou")

        request = CommonRequest()
        request.set_accept_format('json')
        request.set_domain('dysmsapi.aliyuncs.com')
        request.set_method('POST')
        request.set_protocol_type('https')
        request.set_version('2017-05-25')
        request.set_action_name('SendSms')

        request.add_query_param('PhoneNumbers', phone_number)
        request.add_query_param('SignName', sms_cfg.get("sign_name", "机器人监控"))
        request.add_query_param('TemplateCode', sms_cfg.get("template_code", "SMS_XXXXXXX"))
        request.add_query_param('TemplateParam', json.dumps({
            "robot_name": robot_name,
            "fail_count": fail_count
        }))

        response = client.do_action_with_exception(request)
        result = json.loads(response)
        ok = result.get("Code") == "OK"
        print(f"[短信] 发送结果 [{robot_name}]: {result}")
        return ok
    except ImportError:
        print("[告警] 未安装 aliyun-python-sdk-core，请先 pip install aliyun-python-sdk-core")
        return False
    except Exception as e:
        print(f"[短信] 发送失败 [{robot_name}]: {e}")
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
    if not phones:
        print(f"[告警] 未配置短信号码，跳过 [{robot.get('name', '')}]")
        data.add_alert(
            robot["id"], robot["name"],
            "告警(未发送)",
            f"连续失败 {fail_count} 次，未配置短信号码",
            sms_sent=False
        )
        return

    print(f"[告警] 触发告警: {robot['name']} 已连续失败 {fail_count} 次")

    any_sent = False
    for phone in phones:
        phone = phone.strip()
        if phone:
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
