# -*- coding: utf-8 -*-
"""USDD PSM (BSC) monitor: USDD->USDT direction USDT Available, notify if < 10,000,000 USDT."""
import json
import os
import smtplib
import ssl
import sys
import urllib.request
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from datetime import datetime, timezone, timedelta
import mail_helper

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "mail_config.json")
BSC_RPC = "https://bsc-dataseed.bnbchain.org"
BSC_USDT = "0x55d398326f99059fF775485246999027B3197955"
PSM_GEMJOIN = "0xe229fda620b8a9b98ef184830ee3063f0f86b790"  # MCD_JOIN_PSM_USDT_A (BSC)
THRESHOLD = 10_000_000  # 10 million USDT
PAGE_URL = "https://app.usdd.io/bsc/psm"
CST = timezone(timedelta(hours=8))


def eth_call(to, data, rpc=BSC_RPC):
    body = {"jsonrpc": "2.0", "id": 1, "method": "eth_call",
            "params": [{"to": to, "data": data}, "latest"]}
    req = urllib.request.Request(rpc, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                                 method="POST")
    r = urllib.request.urlopen(req, timeout=20)
    return json.loads(r.read().decode())


def get_usdt_available():
    data = "0x70a08231000000000000000000000000" + PSM_GEMJOIN[2:].lower()
    try:
        d = eth_call(BSC_USDT, data)
    except Exception:
        # fallback RPC
        d = eth_call(BSC_USDT, data, rpc="https://bsc.publicnode.com")
    if "result" not in d:
        raise RuntimeError("chain call failed: " + json.dumps(d)[:200])
    return int(d["result"], 16) / 1e18


def send_mail(subject, body_html):
    cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))
    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header("USDD-BSC监控", "utf-8")), cfg["smtp_user"]))
    msg["To"] = cfg["to_addr"]
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"], timeout=30, context=ctx) as s:
        s.login(cfg["smtp_user"], cfg["smtp_password"])
        s.sendmail(cfg["smtp_user"], [cfg["to_addr"]], msg.as_string())


def main():
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    try:
        avail = get_usdt_available()
    except Exception as e:
        print(json.dumps({"ok": False, "step": "fetch", "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    triggered = avail < THRESHOLD
    result = {"ok": True, "time": now, "usdt_available": round(avail, 4),
              "threshold": THRESHOLD, "triggered": triggered}
    if triggered:
        subject = f"【USDD-BSC PSM】USDT兑换可用量 {avail:,.0f} 已低于 {THRESHOLD/1e6:,.0f} 万"
        body = f"""
<html><body style="font-family:Arial,Microsoft YaHei,sans-serif">
<h3>USDD PSM (BSC) 兑换可用量提醒</h3>
<p>监控时间：{now}</p>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse">
<tr><td><b>USDT Available（USDD兑换USDT方向）</b></td><td><b style="color:#d33">{avail:,.4f} USDT</b></td></tr>
<tr><td>触发阈值</td><td>{THRESHOLD/1e6:,.0f} 万 USDT（10,000,000）</td></tr>
<tr><td>是否触发</td><td><b style="color:#090">是，可用量已低于阈值</b></td></tr>
</table>
<p>页面链接：<a href="{PAGE_URL}">app.usdd.io/bsc/psm</a></p>
<p style="color:#888">本邮件由定时监控任务自动发送。</p>
</body></html>"""
        try:
            send_mail(subject, body)
            result["mail_sent"] = True
        except Exception as e:
            result["mail_sent"] = False
            result["mail_error"] = str(e)
    else:
        result["mail_sent"] = False
        result["note"] = "高于阈值，不发送"
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
