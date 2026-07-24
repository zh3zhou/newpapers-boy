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

from __future__ import annotations

import sys
sys.dont_write_bytecode = True

import argparse
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import urllib.request
import urllib.error

try:
    from .dispatch_paths import ProjectPaths, resolve_dispatch_date, resolve_from_root
    from .env_utils import load_env
except ImportError:  # Direct script execution: python scripts/push_email.py
    from dispatch_paths import ProjectPaths, resolve_dispatch_date, resolve_from_root
    from env_utils import load_env

WORK_DIR = Path(__file__).resolve().parent.parent


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
    escaped = html.escape(text, quote=True)

    def safe_link(match):
        label = match.group(1)
        raw_url = html.unescape(match.group(2))
        parsed = urlsplit(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return match.group(0)
        href = html.escape(raw_url, quote=True)
        return f'<a href="{href}" style="color:#1a73e8;text-decoration:none;">{label}</a>'

    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", safe_link, escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(
        r"`([^`]+)`",
        r"<code style='background:#f1f3f4;padding:2px 4px;border-radius:3px;font-family:Consolas,monospace;'>\1</code>",
        escaped,
    )
    return escaped


# ============ 邮件发送 ============

def push_email(
    env: dict,
    title: str,
    body_summary: str,
    md_path: Path,
    mp3_path: Path,
    *,
    result: dict | None = None,
) -> bool:
    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import make_msgid
    import html as html_mod

    host = env.get("SMTP_HOST")
    port_raw = env.get("SMTP_PORT") or "465"
    user = env.get("SMTP_USER")
    password = env.get("SMTP_PASS")
    to_addr = env.get("MAIL_TO")

    if not all([host, user, password, to_addr]):
        print("[邮件] 未配置 SMTP，跳过（如需邮件推送请在 .env 中填写 SMTP_* 和 MAIL_TO）")
        return False
    try:
        port = int(port_raw)
    except ValueError:
        print(f"[邮件] SMTP_PORT 无效: {port_raw}")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = user
        msg["To"] = to_addr
        msg["Subject"] = title
        message_id = make_msgid(domain="academic-dispatch.local")
        msg["Message-ID"] = message_id

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
        print("[邮件] 发送成功（收件人已隐藏）")
        if result is not None:
            result.update({"status": "sent", "messageId": message_id})
        return True
    except Exception as e:
        print(f"[邮件] 异常: {e}")
        if result is not None:
            result.update({"status": "failed", "errorType": type(e).__name__})
        return False


def push_failure_email(env: dict, date_str: str, error_code: str, detail: str, *, result: dict | None = None) -> bool:
    import html
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import make_msgid

    host = env.get("SMTP_HOST")
    user = env.get("SMTP_USER")
    password = env.get("SMTP_PASS")
    to_addr = env.get("MAIL_TO")
    try:
        port = int(env.get("SMTP_PORT") or "465")
    except ValueError:
        return False
    if not all([host, user, password, to_addr]):
        return False
    safe_code = re.sub(r"[^A-Za-z0-9_.-]", "_", error_code)[:80]
    safe_detail = re.sub(r"[A-Za-z]:\\[^\s]+|/[^\s]+", "[local evidence]", detail)[:300]
    message_id = make_msgid(domain="academic-dispatch.local")
    msg = MIMEMultipart("alternative")
    msg["From"] = user
    msg["To"] = to_addr
    msg["Subject"] = f"⚠️ 学术速递未发送 — {date_str}"
    msg["Message-ID"] = message_id
    text = f"{date_str} 的学术速递未通过交付门。\n错误代码：{safe_code}\n摘要：{safe_detail}\n未发送旧内容或附件。"
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(
        MIMEText(
            f"<h2>学术速递未发送</h2><p>{html.escape(date_str)} 的工件未通过交付门。</p>"
            f"<p>错误代码：<code>{html.escape(safe_code)}</code></p>"
            f"<p>{html.escape(safe_detail)}</p><p>未发送旧内容或附件。</p>",
            "html",
            "utf-8",
        )
    )
    try:
        server = smtplib.SMTP_SSL(host, port, timeout=30) if port == 465 else smtplib.SMTP(host, port, timeout=30)
        if port != 465:
            server.starttls()
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())
        server.quit()
        if result is not None:
            result.update({"status": "failure_notified", "messageId": message_id})
        return True
    except Exception as exc:
        if result is not None:
            result.update({"status": "notification_failed", "errorType": type(exc).__name__})
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="发送学术速递邮件。")
    parser.add_argument("date", nargs="?", help="日期，格式 YYYY-MM-DD。")
    parser.add_argument("--root", type=Path, default=WORK_DIR, help="项目根目录。")
    parser.add_argument("--markdown", type=Path, help="输入 Markdown；相对路径基于项目根目录。")
    parser.add_argument("--mp3", type=Path, help="MP3 附件；相对路径基于项目根目录。")
    parser.add_argument("--strict", action="store_true", help="失败时返回非零退出码，供 CI 使用。")
    args = parser.parse_args(argv)

    project = ProjectPaths.from_root(args.root)
    project.data.mkdir(parents=True, exist_ok=True)
    env = load_env(project.root)
    strict = args.strict or env.get("DISPATCH_MODE") == "ci"

    try:
        date_str = resolve_dispatch_date(args.date)
    except ValueError as exc:
        parser.error(str(exc))
    artifacts = project.artifacts(date_str)
    md_path = resolve_from_root(args.markdown, project.root, artifacts.markdown)
    mp3_path = resolve_from_root(args.mp3, project.root, artifacts.audio)

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
        if strict:
            print("[ERROR] 邮件推送未配置或失败，strict 模式返回失败。")
            print("[ERROR] CI 需要配置 SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / MAIL_TO。")
            return 1
        print("[INFO] 邮件推送未配置或失败。")
        print("[INFO] 如需邮件推送，请在 .env 文件或 CI secrets 中填写 SMTP_HOST / SMTP_USER / SMTP_PASS / MAIL_TO。")
        print(f"[INFO] 本地配置文件位置：{project.env_file}")
        return 0

    print()
    print("[OK] 推送完成（邮件 + MP3附件）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
