"""机器人监控系统 — Streamlit 主入口"""
import streamlit as st
import time
import src.data as data
from src.config import load_config, save_config
from src.monitor import start_monitor, stop_monitor, is_running, check_single_robot

st.set_page_config(
    page_title="🤖 机器人监控",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ---- 侧边栏 ----
with st.sidebar:
    st.title("⚙️ 控制面板")

    # 监控开关
    running = is_running()
    if running:
        st.success("🟢 监控运行中")
        if st.button("⏸ 停止监控", type="primary", use_container_width=True):
            stop_monitor()
            st.success("监控已停止")
            st.rerun()
    else:
        st.warning("🔴 监控已停止")
        if st.button("▶ 启动监控", type="primary", use_container_width=True):
            start_monitor()
            st.success("监控已启动")
            st.rerun()

    st.divider()

    # 全局配置
    st.subheader("📝 全局设置")
    config = load_config()

    new_interval = st.number_input(
        "检测间隔（秒）",
        min_value=10, max_value=3600,
        value=config.get("check_interval", 60),
        help="每轮检测之间的等待时间"
    )
    new_threshold = st.number_input(
        "告警阈值（次）",
        min_value=1, max_value=10,
        value=config.get("consecutive_fail_threshold", 3),
        help="连续失败多少次后发送短信"
    )
    new_cooldown = st.number_input(
        "告警冷却（秒）",
        min_value=60, max_value=3600,
        value=config.get("alert_cooldown_seconds", 600),
        help="同一机器人两次告警之间的最小间隔"
    )
    new_timeout = st.number_input(
        "请求超时（秒）",
        min_value=1, max_value=30,
        value=config.get("request_timeout", 10)
    )

    config_changed = (
        new_interval != config.get("check_interval") or
        new_threshold != config.get("consecutive_fail_threshold") or
        new_cooldown != config.get("alert_cooldown_seconds") or
        new_timeout != config.get("request_timeout")
    )

    if config_changed:
        if st.button("💾 保存配置", use_container_width=True):
            config["check_interval"] = new_interval
            config["consecutive_fail_threshold"] = new_threshold
            config["alert_cooldown_seconds"] = new_cooldown
            config["request_timeout"] = new_timeout
            save_config(config)
            st.success("✅ 配置已保存！刷新后生效")
            st.rerun()

    st.divider()

    # 短信配置
    st.subheader("📱 阿里云短信")
    sms = config.get("aliyun_sms", {})

    ak = st.text_input("AccessKey ID", value=sms.get("access_key_id", ""), type="password")
    sk = st.text_input("AccessKey Secret", value=sms.get("access_key_secret", ""), type="password")
    sign = st.text_input("短信签名", value=sms.get("sign_name", "机器人监控"))
    tpl = st.text_input("模板CODE", value=sms.get("template_code", "SMS_XXXXXXX"))
    phones_str = st.text_input(
        "接收号码（逗号分隔）",
        value=",".join(sms.get("phone_numbers", []))
    )

    if st.button("💾 保存短信配置", use_container_width=True):
        sms["access_key_id"] = ak
        sms["access_key_secret"] = sk
        sms["sign_name"] = sign
        sms["template_code"] = tpl
        sms["phone_numbers"] = [p.strip() for p in phones_str.split(",") if p.strip()]
        config["aliyun_sms"] = sms
        save_config(config)
        st.success("✅ 短信配置已保存！")
        st.rerun()

    if st.button("📨 发送测试短信", use_container_width=True):
        phones = [p.strip() for p in phones_str.split(",") if p.strip()]
        if not phones:
            st.error("❌ 请先填写接收号码")
        elif not ak or not sk:
            st.error("❌ 请先填写 AccessKey ID 和 Secret")
        else:
            st.info(f"🔍 当前配置:")
            st.code(f"AccessKey ID: {ak}\n签名: {sign}\n模板: {tpl}\n号码: {phones}")
            
            from src.alert import send_sms
            with st.spinner("正在发送测试短信..."):
                any_sent = False
                for phone in phones:
                    ok = send_sms(phone, "测试机器人", 99)
                    if ok:
                        any_sent = True
                if any_sent:
                    st.success("✅ 测试短信发送成功！请查收")
                else:
                    st.error("❌ 短信发送失败")
                    st.warning("💡 常见原因：\n1. AccessKey Secret 错误（注意大小写和特殊字符）\n2. RAM 用户无短信权限（需要 AliyunDysmsFullAccess）\n3. AccessKey 已被禁用/删除\n4. 阿里云账号未开通短信服务")
                    st.info("📋 请查看终端窗口获得详细错误信息")


# ---- Tab 导航 ----
tab_names = ["📊 总览", "🔧 管理机器人", "📋 检测历史", "🚨 告警记录"]
tabs = st.tabs(tab_names)

# ========== 总览 ==========
with tabs[0]:
    st.title("🤖 机器人可用性监控")
    robots = data.load_robots()

    if not robots:
        st.info("暂无机器人，请先在「管理机器人」页面添加。")
    else:
        # 统计卡片
        total = len(robots)
        online = sum(1 for r in robots if r.get("color") == "success")
        warning = sum(1 for r in robots if r.get("color") == "warning")
        error_count = sum(1 for r in robots if r.get("color") == "danger")
        disabled = sum(1 for r in robots if r.get("status") == "已禁用")

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("📦 总数", total)
        col2.metric("✅ 在线", online)
        col3.metric("⚠️ 警告", warning)
        col4.metric("❌ 异常", error_count)
        col5.metric("⏸ 已禁用", disabled)

        st.divider()

        # 状态卡片
        import pandas as pd
        rows = []
        for r in robots:
            color = r.get("color", "secondary")
            color_emoji = {"success": "🟢", "warning": "🟡", "danger": "🔴", "secondary": "⚪"}.get(color, "⚪")
            enabled = r.get("enabled", True)
            rows.append({
                "机器人": f"{'✅' if enabled else '⏸'} {r['name']}",
                "状态": f"{color_emoji} {r.get('status', '未检测')}",
                "连续失败": r.get("consecutive_fail_count", 0),
                "最后检测": r.get("last_update", "-"),
                "机器人ID": r["id"],
            })

        df = pd.DataFrame(rows)
        st.dataframe(
            df[["机器人", "状态", "连续失败", "最后检测"]],
            use_container_width=True,
            hide_index=True,
        )

        # 快捷操作
        st.divider()
        st.subheader("🔘 快捷操作")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            robot_options = {f"{r['name']}": r["id"] for r in robots}
            selected_name = st.selectbox("选择机器人", list(robot_options.keys()))
            selected_id = robot_options[selected_name]
        with col_b:
            if st.button("🔍 立即检测", use_container_width=True):
                robot = data.get_robot(selected_id)
                if robot:
                    with st.spinner(f"正在检测 {robot['name']}..."):
                        result = check_single_robot(robot)
                        if result["success"]:
                            data.update_robot(selected_id, {
                                "status": result["detail"],
                                "color": "success",
                                "last_update": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "consecutive_fail_count": 0,
                            })
                        else:
                            robot = data.get_robot(selected_id)
                            new_fail = (robot.get("consecutive_fail_count", 0) or 0) + 1
                            color = "danger" if new_fail >= 3 else "warning"
                            data.update_robot(selected_id, {
                                "status": result["detail"],
                                "color": color,
                                "last_update": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "consecutive_fail_count": new_fail,
                            })
                        data.add_history(selected_id, selected_name, result["success"], result["detail"], result["elapsed_ms"])
                        st.success(f"✅ {result['detail']} ({result['elapsed_ms']:.0f}ms)")
                        st.rerun()
        with col_c:
            if st.button("🔄 刷新页面", use_container_width=True):
                st.rerun()

# ========== 管理机器人 ==========
with tabs[1]:
    st.title("🔧 管理机器人")

    # ---- 添加机器人 ----
    st.subheader("➕ 添加新机器人")

    with st.form("add_robot_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            new_id = st.text_input("机器人 ID *", placeholder="如: a5f820a718d74be392fc0bf4e417c1c9")
            new_name = st.text_input("机器人名称 *", placeholder="如: 小慧-健康管理师")
        with c2:
            new_api_key = st.text_input("API Key *", placeholder="如: xbotos-438a9222caaf49b2b5da...")
            new_enabled = st.checkbox("启用监控", value=True)

        add_submitted = st.form_submit_button("✅ 添加机器人", type="primary", use_container_width=True)

        if add_submitted:
            if not new_id.strip() or not new_name.strip() or not new_api_key.strip():
                st.error("❌ 请填写所有必填字段（带 * 号）")
            else:
                try:
                    data.add_robot({
                        "id": new_id.strip(),
                        "name": new_name.strip(),
                        "api_key": new_api_key.strip(),
                        "enabled": new_enabled,
                    })
                    st.success(f"✅ 已添加机器人: {new_name}")
                    st.rerun()
                except ValueError as e:
                    st.error(f"❌ {e}")

    st.divider()

    # ---- 机器人列表 ----
    st.subheader("📋 已添加的机器人")
    robots = data.load_robots()

    if not robots:
        st.info("暂无机器人，请使用上方表单添加。")
    else:
        # 用表格展示，每行有操作按钮
        for idx, r in enumerate(robots):
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([3, 2, 1, 2])

                # 基本信息
                with c1:
                    status_icon = {"success": "🟢", "warning": "🟡", "danger": "🔴", "secondary": "⚪"}.get(r.get("color", "secondary"), "⚪")
                    enabled_icon = "✅" if r.get("enabled", True) else "⏸"
                    st.markdown(f"**{enabled_icon} {status_icon} {r['name']}**")
                    st.caption(f"ID: `{r['id']}`")

                # 运行状态
                with c2:
                    st.markdown(f"状态: **{r.get('status', '未检测')}**")
                    st.caption(f"连续失败: {r.get('consecutive_fail_count', 0)} | 最后检测: {r.get('last_update', '-')}")

                # API Key 显示
                with c3:
                    st.caption(f"API Key: `{r['api_key'][:10]}...`")

                # 操作按钮
                with c4:
                    # 编辑切换
                    edit_key = f"edit_toggle_{r['id']}"
                    if edit_key not in st.session_state:
                        st.session_state[edit_key] = False

                    if st.button("✏️ 编辑", key=f"edit_btn_{r['id']}", use_container_width=True):
                        st.session_state[edit_key] = True

                    if st.button("🗑 删除", key=f"del_btn_{r['id']}", type="primary", use_container_width=True):
                        data.delete_robot(r["id"])
                        st.success(f"✅ 已删除: {r['name']}")
                        st.rerun()

                    # 快捷启停
                    if r.get("enabled", True):
                        if st.button("⏸ 停用", key=f"dis_btn_{r['id']}"):
                            data.update_robot(r["id"], {"enabled": False})
                            st.rerun()
                    else:
                        if st.button("▶ 启用", key=f"en_btn_{r['id']}"):
                            data.update_robot(r["id"], {"enabled": True})
                            st.rerun()

                # 编辑面板
                if st.session_state.get(edit_key, False):
                    st.markdown("---")
                    with st.form(key=f"edit_form_{r['id']}"):
                        ec1, ec2, ec3 = st.columns(3)
                        with ec1:
                            edit_name = st.text_input("名称", value=r["name"], key=f"ename_{r['id']}")
                        with ec2:
                            edit_api_key = st.text_input("API Key", value=r["api_key"], key=f"ekey_{r['id']}")
                        with ec3:
                            edit_enabled = st.checkbox("启用", value=r.get("enabled", True), key=f"een_{r['id']}")

                        ec4, ec5 = st.columns(2)
                        with ec4:
                            if st.form_submit_button("💾 保存", use_container_width=True):
                                data.update_robot(r["id"], {
                                    "name": edit_name,
                                    "api_key": edit_api_key,
                                    "enabled": edit_enabled,
                                })
                                st.success(f"✅ 已保存: {edit_name}")
                                st.session_state[edit_key] = False
                                st.rerun()
                        with ec5:
                            if st.form_submit_button("❌ 取消", use_container_width=True):
                                st.session_state[edit_key] = False
                                st.rerun()
                    st.markdown("---")

# ========== 检测历史 ==========
with tabs[2]:
    st.title("📋 检测历史")

    import pandas as pd
    robots = data.load_robots()
    robot_options = {"全部": None}
    robot_options.update({r["name"]: r["id"] for r in robots})

    filter_name = st.selectbox("筛选机器人", list(robot_options.keys()))
    limit = st.slider("显示条数", 10, 500, 100)

    selected_id = robot_options[filter_name]
    if selected_id:
        records = data.load_history(robot_id=selected_id, limit=limit)
    else:
        records = data.load_history(limit=limit)

    if not records:
        st.info("暂无检测记录")
    else:
        df = pd.DataFrame(records)
        df["time"] = pd.to_datetime(df["time"])
        df = df.sort_values("time", ascending=False)
        df["结果"] = df["success"].apply(lambda x: "✅ 成功" if x else "❌ 失败")
        df["耗时"] = df["response_time_ms"].apply(lambda x: f"{x:.0f}ms")
        df = df[["time", "robot_name", "结果", "detail", "耗时"]]
        df.columns = ["时间", "机器人", "结果", "详情", "耗时"]
        st.dataframe(df, use_container_width=True, hide_index=True, height=600)

# ========== 告警记录 ==========
with tabs[3]:
    st.title("🚨 告警记录")

    import pandas as pd
    alerts = data.load_alerts(limit=200)
    if not alerts:
        st.info("暂无告警记录")
    else:
        df = pd.DataFrame(alerts)
        df = df.sort_values("time", ascending=False)
        df["短信"] = df["sms_sent"].apply(lambda x: "✅ 已发送" if x else "❌ 未发送")
        df = df[["time", "robot_name", "type", "message", "短信"]]
        df.columns = ["时间", "机器人", "类型", "详情", "短信"]
        st.dataframe(df, use_container_width=True, hide_index=True, height=600)
