# -*- coding: utf-8 -*-
"""Gate USD1 announcement monitor: watch Gate announcements via local proxy + Jina Reader,
notify by email when a new USD1-related announcement appears."""
import json
import os
import re
import ssl
import sys
import smtplib
import urllib.request
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from datetime import datetime, timezone, timedelta
import mail_helper

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "mail_config.json")
STATE_PATH = os.path.join(BASE_DIR, "gate_usd1_seen.json")
LOG_PATH = os.path.join(BASE_DIR, "gate_usd1_monitor.log")
PROXY = "http://127.0.0.1:7897"          # local proxy (Clash-like) required to reach gate.com
LIST_URL = "https://r.jina.ai/https://www.gate.com/zh/announcements/lastest"
ANNO_RE = re.compile(r"\[([^\]]+)\]\(https://www\.gate\.com/zh/announcements/article/(\d+)\)")
CST = timezone(timedelta(hours=8))


def log(msg):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"), msg))


def fetch_page(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {"User-Agent": "Mozilla/5.0"}
    # try direct first (works on overseas cloud servers / any net where r.jina.ai is reachable)
    try:
        req = urllib.request.Request(url, headers=headers)
        return urllib.request.urlopen(req, timeout=25, context=ctx).read().decode("utf-8", errors="ignore")
    except Exception:
        # fall back to local proxy (required in mainland China)
        proxy = urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
        opener = urllib.request.build_opener(proxy)
        req = urllib.request.Request(url, headers=headers)
        return opener.open(req, timeout=45).read().decode("utf-8", errors="ignore")


def send_mail(subject, body_html):
    return mail_helper.send_mail(subject, body_html, "Gate监控")


def load_seen():
    if os.path.exists(STATE_PATH):
        try:
            return json.load(open(STATE_PATH, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_seen(seen):
    json.dump(seen, open(STATE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def parse_announcements(html):
    """Extract (article_id, title_text) pairs from Jina-rendered markdown."""
    out = []
    for m in ANNO_RE.finditer(html):
        text, aid = m.group(1), m.group(2)
        title = text
        # iteratively strip trailing relative-time / date / view-count tokens
        for _ in range(4):
            new = re.sub(r"\s+\d+\s*天前\s*$", "", title)
            new = re.sub(r"\s+\d+\s*小时前\s*$", "", new)
            new = re.sub(r"\s+\d+\s*分钟前\s*$", "", new)
            new = re.sub(r"\s+\d{1,2}:\d{2}\s*$", "", new)
            new = re.sub(r"\s+\d{4}-\d{2}-\d{2}\s*$", "", new)
            new = re.sub(r"\s+[\d,]{2,}\s*$", "", new)  # trailing view count
            if new == title:
                break
            title = new
        out.append((aid, title.strip()))
    return out


def main():
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    try:
        html = fetch_page(LIST_URL)
        annos = parse_announcements(html)
    except Exception as e:
        log("FETCH FAIL: %s" % str(e))
        print(json.dumps({"ok": False, "step": "fetch", "error": str(e)}, ensure_ascii=False))
        # notify user that monitor source is down
        try:
            send_mail("【Gate监控】公告数据获取失败",
                      "<html><body><p>Gate USD1 公告监控在 %s 无法获取公告数据。</p>"
                      "<p>可能原因：本地代理 127.0.0.1:7897 未运行，或网络异常。请检查代理后重试。</p>"
                      "</body></html>" % now)
            print("fail-mail sent")
        except Exception as e2:
            print("fail-mail error:", str(e2))
        sys.exit(1)

    if not annos:
        log("EMPTY LIST")
        print(json.dumps({"ok": False, "step": "parse", "error": "no announcements parsed"}, ensure_ascii=False))
        sys.exit(1)

    seen = load_seen()
    usd1_new = []
    for aid, title in annos:
        if "usd1" in title.lower():
            if aid not in seen:
                usd1_new.append((aid, title))
    # record all seen ids
    for aid, _ in annos:
        seen[aid] = seen.get(aid, now)
    save_seen(seen)

    result = {"ok": True, "time": now, "total_annos": len(annos), "usd1_new": []}
    for aid, title in usd1_new:
        subject = "【Gate】新 USD1 公告：%s" % title[:40]
        body = ("<html><body style=\"font-family:Arial,Microsoft YaHei\">"
                "<h3>Gate 出现新的 USD1 相关公告</h3>"
                "<p>监控时间：%s</p>"
                "<p><b>标题：</b>%s</p>"
                "<p><b>链接：</b><a href=\"https://www.gate.com/zh/announcements/article/%s\">点击查看</a>"
                "（中国大陆网络需代理访问）</p>"
                "<p style=\"color:#888\">本邮件由 Gate USD1 公告定时监控自动发送。</p>"
                "</body></html>" % (now, title, aid))
        try:
            send_mail(subject, body)
            result["usd1_new"].append({"id": aid, "title": title, "mail_sent": True})
            log("NOTIFY id=%s title=%s" % (aid, title))
        except Exception as e:
            result["usd1_new"].append({"id": aid, "title": title, "mail_sent": False, "error": str(e)})
            log("MAIL FAIL id=%s err=%s" % (aid, e))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
