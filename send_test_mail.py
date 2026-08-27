# -*- coding: utf-8 -*-
"""Send a test mail to verify the cloud -> QQ mail pipeline works.

Used by workflow_dispatch with send_test_mail=true (manual trigger in GitHub Actions).
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mail_helper

CST = timezone(timedelta(hours=8))


def main():
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    subject = "【测试邮件】云端监控链路验证 OK"
    body = f"""
<html><body style="font-family:Arial,Microsoft YaHei,sans-serif">
<h3>云端监控链路测试邮件</h3>
<p>发送时间：{now}</p>
<p>这封邮件说明：<b>云端（GitHub Actions）→ QQ 邮箱</b> 的发信链路完全正常。</p>
<p>4 个监控任务（JustLend 借款利率 / USDD TRON / USDD BSC / Gate USD1 公告）已全部部署在云端，每 30 分钟自动运行一次，达标时你会收到对应提醒邮件。</p>
<p style="color:#888">本邮件由定时监控任务的测试功能自动发送，无需回复。</p>
</body></html>"""
    to = mail_helper.send_mail(subject, body, "云端监控测试")
    print(json.dumps({"ok": True, "test_mail_sent": True, "to": to, "time": now}, ensure_ascii=False))


if __name__ == "__main__":
    main()
