#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Project layout and artifact naming shared by every command-line adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def resolve_dispatch_date(value: str | None = None, *, now: datetime | None = None) -> str:
    date_str = value or (now or datetime.now()).strftime("%Y-%m-%d")
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must be a valid calendar date in YYYY-MM-DD format") from exc
    if parsed.strftime("%Y-%m-%d") != date_str:
        raise ValueError("date must use YYYY-MM-DD format")
    return date_str


def resolve_from_root(path: Path | None, root: Path, default: Path) -> Path:
    if path is None:
        return default
    return path if path.is_absolute() else root / path


@dataclass(frozen=True)
class DispatchArtifacts:
    markdown: Path
    audio: Path
    transcript: Path
    validation: Path
    agent_log: Path
    ready: Path
    sent: Path


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @classmethod
    def from_root(cls, root: Path | str) -> "ProjectPaths":
        return cls(Path(root).expanduser().resolve())

    @property
    def config(self) -> Path:
        return self.root / "dispatch.config.json"

    @property
    def legacy_config(self) -> Path:
        return self.root / "config.md"

    @property
    def env_file(self) -> Path:
        return self.root / ".env"

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def archive(self) -> Path:
        return self.root / "archive"

    @property
    def scripts(self) -> Path:
        return self.root / "scripts"

    def artifacts(self, date_str: str) -> DispatchArtifacts:
        date_str = resolve_dispatch_date(date_str)
        return DispatchArtifacts(
            markdown=self.data / f"{date_str}_学术速递.md",
            audio=self.data / f"{date_str}_学术播报.mp3",
            transcript=self.data / f"{date_str}_播报稿.txt",
            validation=self.data / f"{date_str}_validation.json",
            agent_log=self.data / f"{date_str}_agent.log",
            ready=self.data / f"{date_str}_ready.json",
            sent=self.data / f"{date_str}_sent.json",
        )
