#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
push_email.py — 将当日速递（Markdown 正文 + MP3 附件）通过 SMTP 邮件发送。

用法：
    python scripts/push_email.py [YYYY-MM-DD]
    不传日期则使用当天日期。

默认通道：邮件（SMTP），MP3 作为 MIME 附件发送，可在手机邮箱 App 中直接收听。

可选通道（Bark / Server酱 / 飞书 Webhook）代码保留在文件末尾，
如需启用：取消对应函数注释，并在 .env 中填入配置项即可。

依赖：Python 标准库（smtplib, email），无需额外 pip 安装。
"""

import sys
sys.dont_write_bytecode = True

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import urllib.request
import urllib.error

WORK_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = WORK_DIR / "data"


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_env():
    env_path = WORK_DIR / ".env"
    env = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


# ============ Markdown → HTML 轻量转换 ============

def _md_to_html(text: str) -> str:
    lines = text.split("\n")
    html_parts = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        if stripped.startswith("# "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            title = stripped[2:].strip()
            html_parts.append(f"<h2 style='color:#1a73e8;'>{_inline_md(title)}</h2>")
        elif stripped.startswith("## "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            title = stripped[3:].strip()
            title = re.sub(r"^[一二三四五六七八九十]+、\s*", "", title)
            html_parts.append(f"<h3 style='color:#202124;border-bottom:1px solid #e0e0e0;padding-bottom:4px;margin-top:20px;'>{_inline_md(title)}</h3>")
        elif stripped.startswith("### "):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            title = stripped[4:].strip()
            html_parts.append(f"<h4 style='color:#5f6368;margin-top:16px;'>{_inline_md(title)}</h4>")
        elif stripped.startswith(">"):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            quote = stripped.lstrip(">").strip()
            html_parts.append(f"<blockquote style='border-left:3px solid #1a73e8;padding:8px 16px;background:#f8f9fa;color:#5f6368;margin:12px 0;'>{_inline_md(quote)}</blockquote>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_parts.append("<ul style='padding-left:20px;'>")
                in_list = True
            item = stripped[2:].strip()
            html_parts.append(f"<li style='margin-bottom:6px;'>{_inline_md(item)}</li>")
        elif stripped == "---":
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append("<hr style='border:none;border-top:1px solid #e0e0e0;margin:16px 0;'>")
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<p style='margin:8px 0;'>{_inline_md(stripped)}</p>")

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


def _inline_md(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" style="color:#1a73e8;text-decoration:none;">\1</a>', text)
    text = re.sub(r"`([^`]+)`", r"<code style='background:#f1f3f4;padding:2px 4px;border-radius:3px;font-family:Consolas,monospace;'>\1</code>", text)
    return text


# ============ 邮件发送 ============

def push_email(env: dict, title: str, body_summary: str, md_path: Path, mp3_path: Path) -> bool:
    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    import html as html_mod

    host = env.get("SMTP_HOST")
    port = int(env.get("SMTP_PORT", "465"))
    user = env.get("SMTP_USER")
    password = env.get("SMTP_PASS")
    to_addr = env.get("MAIL_TO")

    if not all([host, user, password, to_addr]):
        print("[邮件] 未配置 SMTP，跳过（如需邮件推送请在 .env 中填写 SMTP_* 和 MAIL_TO）")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = user
        msg["To"] = to_addr
        msg["Subject"] = title

        body_html = f"""
        <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:700px;margin:0 auto;padding:20px;">
          <div style="background:linear-gradient(135deg,#1a73e8,#4285f4);color:white;padding:20px;border-radius:8px 8px 0 0;">
            <h1 style="margin:0;font-size:22px;">📰 {html_mod.escape(title.replace('📰 ', ''))}</h1>
            <p style="margin:8px 0 0 0;opacity:0.9;">{html_mod.escape(body_summary)}</p>
          </div>
          <div style="padding:20px;background:white;border:1px solid #e0e0e0;border-top:none;border-radius:0 0 8px 8px;">
            {_md_to_html(md_path.read_text(encoding='utf-8')) if md_path.exists() else '<p>（Markdown 文件未找到）</p>'}
          </div>
          <div style="text-align:center;padding:12px;color:#5f6368;font-size:12px;">
            由「会打岔的学术速递」自动发送 · MP3 语音播报请查收附件
          </div>
        </div>
        """
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        if mp3_path.exists():
            with open(mp3_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=mp3_path.name)
            part["Content-Disposition"] = f'attachment; filename="{mp3_path.name}"'
            msg.attach(part)
            print(f"[邮件] 已附加 MP3: {mp3_path.name} ({mp3_path.stat().st_size / 1024:.0f} KB)")

        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())
        server.quit()
        print(f"[邮件] 成功发送至 {to_addr}")
        return True
    except Exception as e:
        print(f"[邮件] 异常: {e}")
        return False


# ============ 可选推送通道（默认注释掉，取消注释即可启用） ============
#
# 若需启用 Bark（iOS 推送），取消下面函数的注释，并在 main() 中调用：
#
# def push_bark(bark_url: str, title: str, body: str, md_path: Path, mp3_path: Path) -> bool:
#     if not bark_url:
#         return False
#     try:
#         url = bark_url.rstrip("/")
#         content = body
#         if md_path.exists():
#             content = body + "\n\n" + md_path.read_text(encoding="utf-8")[:3500]
#         payload = {"title": title, "body": content[:4000], "sound": "minuet", "group": "学术速递"}
#         body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
#         req = urllib.request.Request(f"{url}/", data=body_bytes,
#                                      headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
#         with urllib.request.urlopen(req, timeout=15) as resp:
#             resp_json = json.loads(resp.read().decode("utf-8"))
#         ok = resp_json.get("code") == 200 or resp_json.get("message") == "success"
#         print(f"[Bark] {'成功' if ok else '失败: ' + str(resp_json)}")
#         return ok
#     except Exception as e:
#         print(f"[Bark] 异常: {e}")
#         return False
#
# 若需启用 Server酱（微信服务号推送，不支持MP3附件）：
#
# def push_serverchan(send_key: str, title: str, body: str, md_path: Path, mp3_path: Path) -> bool:
#     if not send_key:
#         return False
#     try:
#         from urllib.parse import urlencode
#         desp = body + "\n\n---\n\n" + (md_path.read_text(encoding="utf-8") if md_path.exists() else "")
#         data = urlencode({"title": title, "desp": desp[:30000]}).encode("utf-8")
#         req = urllib.request.Request(f"https://sctapi.ftqq.com/{send_key}.send", data=data, method="POST")
#         with urllib.request.urlopen(req, timeout=15) as resp:
#             resp_json = json.loads(resp.read().decode("utf-8"))
#         ok = resp_json.get("code") == 0
#         print(f"[Server酱] {'成功' if ok else '失败: ' + str(resp_json)}")
#         return ok
#     except Exception as e:
#         print(f"[Server酱] 异常: {e}")
#         return False
#
# 若需启用飞书自定义机器人 Webhook：
#
# def push_feishu_webhook(webhook: str, title: str, body: str, md_path: Path, mp3_path: Path) -> bool:
#     if not webhook:
#         return False
#     try:
#         content_md = body + "\n\n---\n\n" + (md_path.read_text(encoding="utf-8") if md_path.exists() else "")
#         msg = {"msg_type": "interactive", "card": {"config": {"wide_screen_mode": True},
#                 "header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"},
#                 "elements": [{"tag": "markdown", "content": content_md[:30000]}]}}
#         body_bytes = json.dumps(msg, ensure_ascii=False).encode("utf-8")
#         req = urllib.request.Request(webhook, data=body_bytes,
#                                      headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
#         with urllib.request.urlopen(req, timeout=15) as resp:
#             resp_json = json.loads(resp.read().decode("utf-8"))
#         ok = resp_json.get("code") == 0
#         print(f"[飞书Webhook] {'成功' if ok else '失败: ' + str(resp_json)}")
#         return ok
#     except Exception as e:
#         print(f"[飞书Webhook] 异常: {e}")
#         return False


# ============ 主流程 ============

def build_summary(md_path: Path) -> tuple:
    title = "会打岔的学术速递"
    summary = ""
    if not md_path.exists():
        return title, summary
    text = md_path.read_text(encoding="utf-8")
    m = re.search(r"#\s*(.+)", text)
    if m:
        title = m.group(1).strip()
    m2 = re.search(r">\s*(.+)", text)
    if m2:
        summary = m2.group(1).strip()[:200]
    return title, summary


def main():
    ensure_data_dir()
    env = load_env()

    if len(sys.argv) > 1:
        date_str = sys.argv[1]
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    md_path = DATA_DIR / f"{date_str}_学术速递.md"
    mp3_path = DATA_DIR / f"{date_str}_学术播报.mp3"

    title, summary = build_summary(md_path)
    push_title = f"📰 {title}"
    push_body = summary if summary else f"{date_str} 的学术速递已生成。"

    if mp3_path.exists():
        push_body += f"\n\n🎙️ 语音播报已生成（{mp3_path.stat().st_size / 1024:.0f} KB），通勤路上可听。"

    print(f"[INFO] 推送日期: {date_str}")
    print(f"[INFO] Markdown: {md_path} ({'存在' if md_path.exists() else '缺失'})")
    print(f"[INFO] MP3: {mp3_path} ({'存在' if mp3_path.exists() else '缺失'})")
    print()

    success = push_email(env, push_title, push_body, md_path, mp3_path)

    # 如需启用其他通道，取消下面对应行的注释：
    # if not success:
    #     success = push_bark(env.get("BARK_URL", ""), push_title, push_body, md_path, mp3_path)
    # if not success:
    #     success = push_serverchan(env.get("SERVERCHAN_KEY", ""), push_title, push_body, md_path, mp3_path)
    # if not success:
    #     success = push_feishu_webhook(env.get("FEISHU_WEBHOOK", ""), push_title, push_body, md_path, mp3_path)

    if not success:
        print()
        print("[INFO] 邮件推送未配置或失败。")
        print("[INFO] 如需邮件推送，请在 .env 文件中填写 SMTP_HOST / SMTP_USER / SMTP_PASS / MAIL_TO。")
        print(f"[INFO] 文件位置：{WORK_DIR / '.env'}")
        return 0

    print()
    print("[OK] 推送完成（邮件 + MP3附件）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
