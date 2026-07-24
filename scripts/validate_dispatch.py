#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Validate the Markdown contract between the agent and deterministic scripts."""

from __future__ import annotations

import argparse
from collections import Counter
import http.client
import ipaddress
import json
import re
import socket
import ssl
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

try:
    from .content_history import extract_content_entries, history_findings, load_history
    from .dispatch_config import FieldSpec, load_dispatch_config, parse_config_fields, parse_count_spec
    from .dispatch_markdown import parse_markdown
    from .dispatch_paths import ProjectPaths, resolve_from_root
except ImportError:  # Direct script execution: python scripts/validate_dispatch.py
    from content_history import extract_content_entries, history_findings, load_history
    from dispatch_config import FieldSpec, load_dispatch_config, parse_config_fields, parse_count_spec
    from dispatch_markdown import parse_markdown
    from dispatch_paths import ProjectPaths, resolve_from_root

WORK_DIR = Path(__file__).resolve().parent.parent


def normalize_heading(title: str) -> str:
    title = title.strip()
    title = re.sub(r"^[一二三四五六七八九十]+、\s*", "", title)
    title = title.strip(" ✦")
    return title.strip()


def extract_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s<>)\]]+", text)
    return [url.rstrip(".,，。;；") for url in urls]


def classify_http_status(url: str, status: int) -> dict:
    if 200 <= status < 400:
        return {"url": url, "level": "ok", "verdict": "reachable", "http_status": status, "message": "reachable"}
    if status in {401, 403}:
        return {
            "url": url,
            "level": "warning",
            "verdict": "bot_blocked",
            "http_status": status,
            "message": f"public server blocked automated verification with HTTP {status}",
        }
    if status == 429 or status >= 500:
        return {
            "url": url,
            "level": "warning",
            "verdict": "transient",
            "http_status": status,
            "message": f"remote server returned transient HTTP {status}",
        }
    return {
        "url": url,
        "level": "error",
        "verdict": "dead",
        "http_status": status,
        "message": f"remote server returned HTTP {status}",
    }


def resolve_public_target(url: str, resolver=socket.getaddrinfo) -> tuple[str, str, object | None, list[str]]:
    try:
        parsed = urlsplit(url)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        return "error", f"invalid URL: {exc}", None, []
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "error", "invalid HTTP URL", None, []
    if parsed.username or parsed.password:
        return "error", "URL credentials are not allowed", None, []

    hostname = (parsed.hostname or "").rstrip(".").lower()
    if not hostname or hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        return "error", "local hostnames are not allowed", None, []

    try:
        literal_ip = ipaddress.ip_address(hostname)
        addresses = [(None, None, None, None, (str(literal_ip), port))]
    except ValueError:
        try:
            addresses = resolver(hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            temporary_codes = {getattr(socket, "EAI_AGAIN", -3)}
            level = "warning" if exc.errno in temporary_codes else "error"
            kind = "temporary DNS failure" if level == "warning" else "DNS name does not resolve"
            return level, f"{kind}: {exc}", parsed, []
        except OSError as exc:
            return "warning", f"temporary DNS failure: {exc}", parsed, []

    resolved_ips = set()
    for item in addresses:
        address = item[4][0].split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return "error", f"resolver returned an invalid IP: {address}", parsed, []
        resolved_ips.add(str(ip))
        if not ip.is_global:
            return "error", f"private, local, or reserved address is not allowed: {ip}", parsed, []

    if not resolved_ips:
        return "error", "DNS returned no addresses", parsed, []
    return "ok", "public URL", parsed, sorted(resolved_ips)


def validate_public_url(url: str, resolver=socket.getaddrinfo) -> tuple[str, str]:
    level, reason, _, _ = resolve_public_target(url, resolver=resolver)
    return level, reason


def build_fixed_connection(parsed, ip: str, timeout: float):
    hostname = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if parsed.scheme == "https":
        connection = http.client.HTTPSConnection(
            hostname,
            port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
    else:
        connection = http.client.HTTPConnection(hostname, port, timeout=timeout)

    connection._create_connection = lambda address, timeout=timeout, source_address=None: socket.create_connection(
        (ip, port), timeout, source_address
    )
    return connection


def request_once(url: str, method: str, timeout: float, resolver, connection_builder):
    level, reason, parsed, public_ips = resolve_public_target(url, resolver=resolver)
    if level != "ok":
        return None, None, {
            "url": url,
            "level": level,
            "verdict": "unsafe" if "not allowed" in reason or "local" in reason else ("dead" if level == "error" else "transient"),
            "http_status": None,
            "message": reason,
        }

    connection = connection_builder(parsed, public_ips[0], timeout)
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    headers = {"User-Agent": "academic-dispatch-validator/1.0", "Connection": "close"}
    if method == "GET":
        headers["Range"] = "bytes=0-0"

    try:
        connection.request(method, target, headers=headers)
        response = connection.getresponse()
        status = int(response.status)
        location = response.getheader("Location")
        response.read(1)
        return status, location, None
    except ssl.SSLCertVerificationError as exc:
        return None, None, {
            "url": url,
            "level": "error",
            "verdict": "dead",
            "http_status": None,
            "message": f"TLS certificate validation failed: {exc}",
        }
    except (ssl.SSLError, socket.timeout, TimeoutError, OSError, http.client.HTTPException) as exc:
        return None, None, {
            "url": url,
            "level": "warning",
            "verdict": "transient",
            "http_status": None,
            "message": f"temporary network failure: {exc}",
        }
    finally:
        connection.close()


def check_url(
    url: str,
    timeout: float = 8.0,
    resolver=socket.getaddrinfo,
    connection_builder=build_fixed_connection,
) -> dict:
    current_url = url
    redirect_statuses = {301, 302, 303, 307, 308}
    for _ in range(6):
        redirected = False
        for method in ("HEAD", "GET"):
            status, location, failure = request_once(
                current_url,
                method,
                timeout,
                resolver,
                connection_builder,
            )
            if failure:
                failure["url"] = url
                failure["final_url"] = current_url
                failure["method"] = method
                return failure
            if status == 405 and method == "HEAD":
                continue
            if status in redirect_statuses and location:
                current_url = urljoin(current_url, location)
                redirected = True
                break
            result = classify_http_status(url, status)
            result["final_url"] = current_url
            result["method"] = method
            return result
        if redirected:
            continue
        return {
            "url": url, "level": "error", "verdict": "dead", "http_status": 405,
            "method": "HEAD+GET", "message": "URL rejected HEAD and GET",
        }

    return {
        "url": url, "level": "error", "verdict": "dead", "http_status": None,
        "method": "HEAD+GET", "message": "too many redirects",
    }


def check_urls(urls: list[str], timeout: float = 8.0, checker=None) -> list[dict]:
    check = checker or (lambda url: check_url(url, timeout=timeout))
    return [check(url) for url in dict.fromkeys(urls)]


def split_markdown_sections(md_text: str) -> tuple[dict[str, str], str]:
    sections: dict[str, list[str]] = {}
    diversion_lines: list[str] = []
    current_name: str | None = None
    current_is_diversion = False

    for line in md_text.splitlines():
        m = re.match(r"^##\s+(.+)", line.strip())
        if m:
            heading = normalize_heading(m.group(1))
            current_is_diversion = "打岔" in heading or "diversion" in heading.lower()
            current_name = "__diversion__" if current_is_diversion else heading
            if current_is_diversion:
                diversion_lines = [line]
            else:
                sections.setdefault(current_name, [line])
            continue

        if current_name is None:
            continue
        if current_is_diversion:
            diversion_lines.append(line)
        else:
            sections.setdefault(current_name, []).append(line)

    return {name: "\n".join(lines) for name, lines in sections.items()}, "\n".join(diversion_lines)


def item_blocks(section_text: str) -> list[str]:
    blocks: list[list[str]] = []
    current: list[str] | None = None

    for line in section_text.splitlines():
        if re.match(r"^\s*[-*]\s+\*\*", line):
            if current:
                blocks.append(current)
            current = [line]
            continue
        if current is not None:
            if line.startswith(" ") or line.startswith("\t") or not line.strip():
                current.append(line)
            elif re.match(r"^#{1,3}\s+", line):
                blocks.append(current)
                current = None
            else:
                current.append(line)

    if current:
        blocks.append(current)
    return ["\n".join(block) for block in blocks]


def subsection_text(section_text: str, heading_pattern: str) -> str:
    lines = []
    active = False
    for line in section_text.splitlines():
        if re.match(r"^###\s+", line.strip()):
            if active:
                break
            active = bool(re.search(heading_pattern, line, re.IGNORECASE))
        if active:
            lines.append(line)
    return "\n".join(lines)


def validate_dispatch(
    date_str: str,
    md_path: Path,
    config_path: Path,
    strict: bool = False,
    check_links: bool = False,
    link_timeout: float = 8.0,
    link_checker=None,
    history_path: Path | None = None,
) -> dict:
    report = {
        "date": date_str,
        "markdown": str(md_path),
        "config": str(config_path),
        "strict": strict,
        "sections": {},
        "arts": 0,
        "humors": 0,
        "url_count": 0,
        "links_checked": check_links,
        "links": [],
        "errors": [],
        "warnings": [],
        "verifiedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sourceDomains": {},
        "history": {"duplicates": [], "warnings": []},
    }

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        report["errors"].append("date must use YYYY-MM-DD")
    else:
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            report["errors"].append("date is not a valid calendar date")

    if not md_path.exists():
        report["errors"].append(f"Markdown file does not exist: {md_path}")
        return report

    try:
        md_text = md_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        report["errors"].append("Markdown file is not valid UTF-8")
        return report

    if not md_text.strip():
        report["errors"].append("Markdown file is empty")
        return report

    if not re.search(rf"^#\s+.*{re.escape(date_str)}", md_text, re.MULTILINE):
        report["errors"].append("top-level title must contain the dispatch date")

    parsed = parse_markdown(md_text)
    if parsed.get("date") != date_str:
        report["errors"].append("TTS parser did not recover the expected date")

    if not parsed.get("sections"):
        report["errors"].append("TTS parser found no academic sections")

    sections, diversion = split_markdown_sections(md_text)
    try:
        config = load_dispatch_config(config_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        config = None
        report["errors"].append(f"configuration is invalid: {exc}")
    fields = config.fields if config else []
    if strict and not fields:
        report["errors"].append("strict mode requires configured academic fields")

    for field in fields:
        section_text = sections.get(field.name)
        if section_text is None:
            report["errors"].append(f"missing configured section: {field.name}")
            continue

        blocks = item_blocks(section_text)
        no_highlights = "今日暂无亮点" in section_text
        count = len(blocks)
        report["sections"][field.name] = {
            "items": count,
            "expected": field.count_spec,
        }

        if count == 0 and not no_highlights:
            report["errors"].append(f"section has no items and no no-highlights marker: {field.name}")
        if field.min_items is not None and count and count < field.min_items:
            report["warnings"].append(f"{field.name} has {count} items, below configured {field.count_spec}")
        if field.max_items is not None and count > field.max_items:
            report["warnings"].append(f"{field.name} has {count} items, above configured {field.count_spec}")

        for idx, block in enumerate(blocks, 1):
            if "摘要" not in block:
                report["errors"].append(f"{field.name} item {idx} is missing 摘要")
            if "为什么值得看" not in block:
                report["errors"].append(f"{field.name} item {idx} is missing 为什么值得看")
            if not extract_urls(block):
                report["errors"].append(f"{field.name} item {idx} is missing a URL")

    if not diversion:
        report["errors"].append("missing 今日打岔 section")
    else:
        if not re.search(r"^###\s+.*(艺术|摄影|art)", diversion, re.MULTILINE | re.IGNORECASE):
            report["errors"].append("diversion section is missing 艺术一刻")
        if not re.search(r"^###\s+.*(笑|幽默|趣味|冷知识|humor)", diversion, re.MULTILINE | re.IGNORECASE):
            report["errors"].append("diversion section is missing 会心一笑")

        if strict:
            art_section = subsection_text(diversion, r"艺术|摄影|art")
            art_blocks = item_blocks(art_section)
            art_sources = []
            art_hosts = []
            for idx, block in enumerate(art_blocks, 1):
                first_line = block.splitlines()[0] if block.splitlines() else ""
                source_match = re.search(r"^\s*[-*]\s+\*\*.+?\*\*\s+[—-]\s+(.+?)\s*$", first_line)
                if not source_match:
                    report["errors"].append(f"art item {idx} is missing a source")
                else:
                    art_sources.append(source_match.group(1).strip().casefold())
                if "简介" not in block:
                    report["errors"].append(f"art item {idx} is missing 简介")
                block_urls = extract_urls(block)
                if not block_urls:
                    report["errors"].append(f"art item {idx} is missing a URL")
                else:
                    host = (urlsplit(block_urls[0]).hostname or "").lower()
                    art_hosts.append(host.removeprefix("www."))
            art_policy = config.art if config else {}
            target_items = int(art_policy.get("targetItems", 5))
            minimum_sources = int(art_policy.get("minimumDistinctSources", 3))
            maximum_per_source = int(art_policy.get("maximumItemsPerSource", 2))
            if len(art_blocks) < target_items:
                report["warnings"].append(
                    f"art section has {len(art_blocks)} items, below default target {target_items}"
                )
            required_distinct = min(minimum_sources, len(art_blocks))
            if len(art_blocks) >= 2 and (
                len(set(art_sources)) < required_distinct
                or len(set(art_hosts)) < required_distinct
            ):
                report["errors"].append(
                    f"art section must use at least {required_distinct} distinct sources "
                    f"and domains when it contains {len(art_blocks)} items"
                )
            if any(count > maximum_per_source for count in Counter(art_sources).values()) or any(
                count > maximum_per_source for count in Counter(art_hosts).values()
            ):
                report["errors"].append(
                    f"art section must use no more than {maximum_per_source} items per source and domain"
                )

    report["arts"] = len(parsed.get("arts", []))
    report["humors"] = len(parsed.get("humors", []))
    if strict and report["arts"] == 0:
        report["errors"].append("TTS parser found no art items")
    if strict and report["humors"] == 0:
        report["errors"].append("TTS parser found no humor items")

    urls = extract_urls(md_text)
    report["url_count"] = len(urls)
    entries = extract_content_entries(md_text, date_str)
    report["sourceDomains"] = dict(Counter(entry["domain"] for entry in entries if entry.get("domain")))
    if history_path:
        raw_history = load_history(history_path)
        history_config = (config.raw.get("history", {}) if config else {})
        findings = history_findings(
            entries,
            raw_history,
            date_str,
            duplicate_days=int(history_config.get("duplicateWindowDays", 30)),
            diversity_days=int(history_config.get("diversityWindowDays", 7)),
        )
        report["history"] = {
            "duplicates": [
                {"title": entry.get("title"), "url": entry.get("url")} for entry in findings["duplicates"]
            ],
            "warnings": findings["warnings"],
        }
        for duplicate in report["history"]["duplicates"]:
            report["errors"].append(f"duplicate content in history: {duplicate['title'] or duplicate['url']}")
        report["warnings"].extend(findings["warnings"])
    if strict and not urls:
        report["errors"].append("strict mode requires at least one URL")

    if check_links:
        report["links"] = check_urls(urls, timeout=link_timeout, checker=link_checker)
        for result in report["links"]:
            message = f"link {result['url']}: {result['message']}"
            if result["level"] == "error":
                report["errors"].append(message)
            elif result["level"] == "warning":
                report["warnings"].append(message)

    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="验证每日学术速递 Markdown 契约。")
    parser.add_argument("date", help="日期，格式 YYYY-MM-DD。")
    parser.add_argument("--root", type=Path, default=WORK_DIR, help="项目根目录。")
    parser.add_argument("--strict", action="store_true", help="启用 CI 严格检查。")
    parser.add_argument("--check-links", action="store_true", help="检查 URL 可达性并写入验证报告。")
    parser.add_argument("--link-timeout", type=float, default=8.0, help="每个 URL 的超时秒数。")
    parser.add_argument("--markdown", type=Path, help="Markdown 文件；相对路径基于项目根目录。")
    parser.add_argument("--config", type=Path, help="配置文件；相对路径基于项目根目录。")
    parser.add_argument("--report", type=Path, help="JSON 报告；相对路径基于项目根目录。")
    parser.add_argument("--history", type=Path, help="历史 JSONL；默认 data/content-history.jsonl。")
    args = parser.parse_args(argv)

    project = ProjectPaths.from_root(args.root)
    default_markdown = project.data / f"{args.date}_学术速递.md"
    default_report = project.data / f"{args.date}_validation.json"
    md_path = resolve_from_root(args.markdown, project.root, default_markdown)
    config_path = resolve_from_root(args.config, project.root, project.config)
    report_path = resolve_from_root(args.report, project.root, default_report)
    history_path = resolve_from_root(args.history, project.root, project.data / "content-history.jsonl")
    report = validate_dispatch(
        args.date,
        md_path,
        config_path,
        args.strict,
        check_links=args.check_links,
        link_timeout=args.link_timeout,
        history_path=history_path,
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[INFO] 验证报告: {report_path}")
    print(f"[INFO] 学术板块: {len(report['sections'])}, 艺术: {report['arts']}, 趣味: {report['humors']}, URL: {report['url_count']}")
    for warning in report["warnings"]:
        print(f"[WARN] {warning}")
    for error in report["errors"]:
        print(f"[ERROR] {error}")

    if report["errors"]:
        return 1
    print("[OK] Markdown 契约验证通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
