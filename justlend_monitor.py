# -*- coding: utf-8 -*-
"""JustLend jUSDT borrow-rate monitor + QQ mail notifier."""
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
API_URL = "https://openapi.just.network/lend/jtoken"
JTARGET = "TXJgMdjVX5dKiQaUi9QobwNxtSQaFqccvd"  # jUSDT
PAGE_URL = "https://app.justlend.org/marketDetailNew?jtokenAddress=TXJgMdjVX5dKiQaUi9QobwNxtSQaFqccvd&_from=/homeV1&lang=zh-TC"
THRESHOLD = 5.0  # %

CST = timezone(timedelta(hours=8))


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_borrow_apy():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for t in data.get("data", {}).get("tokenList", []):
        if t.get("address") == JTARGET:
            # borrowRate is annualized borrow APR (decimal). Convert to APY via compounding.
            apr = float(t.get("borrowRate", 0))
            apy = (1 + apr / 365.0) ** 365 - 1
            return apr, apy, t
    return None, None, None


def send_mail(subject, body_html):
    return mail_helper.send_mail(subject, body_html, 'JustLend监控')



def main():
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    try:
        apr, apy, info = get_borrow_apy()
    except Exception as e:
        print(json.dumps({"ok": False, "step": "fetch", "error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    if info is None:
        print(json.dumps({"ok": False, "step": "token", "error": "jUSDT not found"}, ensure_ascii=False))
        sys.exit(1)
    apy_pct = apy * 100
    apr_pct = apr * 100
    result = {"ok": True, "time": now, "borrow_apr_pct": round(apr_pct, 4), "borrow_apy_pct": round(apy_pct, 4), "threshold": THRESHOLD, "triggered": apy_pct > THRESHOLD}

    if apy_pct > THRESHOLD:
        subject = f"【JustLend监控】USDT借款利率 {apy_pct:.2f}% 已超阈值 {THRESHOLD}%"
        body = f"""
<html><body style="font-family:Arial,Microsoft YaHei,sans-serif">
<h3>JustLend USDT 借款利率提醒</h3>
<p>监控时间：{now}</p>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse">
<tr><td><b>借款年化 APY（复利）</b></td><td><b style="color:#d33">{apy_pct:.2f}%</b></td></tr>
<tr><td>借款 APR（单利）</td><td>{apr_pct:.4f}%</td></tr>
<tr><td>触发阈值</td><td>{THRESHOLD}%</td></tr>
<tr><td>是否触发</td><td><b style="color:#090">是，超过阈值</b></td></tr>
</table>
<p>市场链接：<a href="{PAGE_URL}">JustLend jUSDT 市场</a></p>
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
        result["note"] = "低于阈值，不发送"
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
