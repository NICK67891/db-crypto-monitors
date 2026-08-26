# -*- coding: utf-8 -*-
"""Shared SMTP mail helper for cloud (GitHub Actions) deployment.
Config priority: environment variables (GitHub Secrets) -> local mail_config.json."""
import json
import os
import smtplib
import ssl
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

DEFAULT_HOST = "smtp.qq.com"
DEFAULT_PORT = 465


def load_mail_config():
    cfg = {
        "smtp_host": os.environ.get("SMTP_HOST", DEFAULT_HOST),
        "smtp_port": int(os.environ.get("SMTP_PORT", str(DEFAULT_PORT))),
        "smtp_user": os.environ.get("SMTP_USER"),
        "smtp_password": os.environ.get("SMTP_PASSWORD"),
        "to_addr": os.environ.get("SMTP_TO"),
    }
    # if env provides full config, use it (cloud / GitHub Actions)
    if cfg["smtp_user"] and cfg["smtp_password"] and cfg["to_addr"]:
        return cfg
    # fallback: local mail_config.json
    cfg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mail_config.json")
    with open(cfg_file, "r", encoding="utf-8") as f:
        local = json.load(f)
    for k in ("smtp_user", "smtp_password", "to_addr"):
        if not cfg[k]:
            cfg[k] = local.get(k)
    cfg["smtp_host"] = local.get("smtp_host", cfg["smtp_host"])
    cfg["smtp_port"] = int(local.get("smtp_port", cfg["smtp_port"]))
    return cfg


def send_mail(subject, body_html, from_name="监控"):
    cfg = load_mail_config()
    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header(from_name, "utf-8")), cfg["smtp_user"]))
    msg["To"] = cfg["to_addr"]
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"], timeout=30, context=ctx) as s:
        s.login(cfg["smtp_user"], cfg["smtp_password"])
        s.sendmail(cfg["smtp_user"], [cfg["to_addr"]], msg.as_string())
    return cfg["to_addr"]
