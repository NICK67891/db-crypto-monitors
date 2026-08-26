# -*- coding: utf-8 -*-
"""USDD PSM monitor: USDD->USDT direction USDT Available, notify if < 20,000,000 USDT."""
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
TRON_API = "https://api.trongrid.io/wallet/triggerconstantcontract"
USDT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
PSM_GEMJOIN = "TSUYvQ5tdd3DijCD1uGunGLpftHuSZ12sQ"  # MCD_JOIN_PSM_USDT_A
THRESHOLD = 20_000_000  # 20 million USDT
PAGE_URL = "https://app.usdd.io/tron/psm"
CST = timezone(timedelta(hours=8))
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58_to_hex20(s):
    n = 0
    for c in s:
        n = n * 58 + B58.index(c)
    h = format(n, 'x')
    nz = len(s) - len(s.lstrip('1'))
    h = '00' * nz + h
    return h.zfill(50)[2:42]


def get_usdt_available():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    param = base58_to_hex20(PSM_GEMJOIN).rjust(64, '0')
    body = {
        "owner_address": PSM_GEMJOIN,
        "contract_address": USDT,
        "function_selector": "balanceOf(address)",
        "parameter": param,
        "visible": True,
    }
    req = urllib.request.Request(TRON_API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    r = urllib.request.urlopen(req, timeout=30, context=ctx)
    d = json.loads(r.read().decode())
    cr = d.get("constant_result")
    if not cr:
        raise RuntimeError("chain call failed: " + json.dumps(d)[:200])
    return int(cr[0], 16) / 1e6


def send_mail(subject, body_html):
    cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))
    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header("USDD监控", "utf-8")), cfg["smtp_user"]))
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
        subject = f"【USDD PSM】USDT兑换可用量 {avail:,.0f} 已低于 {THRESHOLD/1e6:,.0f} 万"
        body = f"""
<html><body style="font-family:Arial,Microsoft YaHei,sans-serif">
<h3>USDD PSM 兑换可用量提醒</h3>
<p>监控时间：{now}</p>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse">
<tr><td><b>USDT Available（USDD兑换USDT方向）</b></td><td><b style="color:#d33">{avail:,.4f} USDT</b></td></tr>
<tr><td>触发阈值</td><td>{THRESHOLD/1e6:,.0f} 万 USDT（20,000,000）</td></tr>
<tr><td>是否触发</td><td><b style="color:#090">是，可用量已低于阈值</b></td></tr>
</table>
<p>页面链接：<a href="{PAGE_URL}">app.usdd.io/tron/psm</a></p>
<p style="color:#888">本邮件由定时监控任务自动发送。</p>
</body></html>"""
        try:
            to = send_mail(subject, body)
            result["mail_sent"] = True
            result["to"] = to
        except Exception as e:
            result["mail_sent"] = False
            result["mail_error"] = str(e)
    else:
        result["mail_sent"] = False
        result["note"] = "高于阈值，不发送"
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
