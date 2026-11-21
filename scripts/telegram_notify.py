#!/usr/bin/env python3
"""Build and optionally send a Telegram test-result notification."""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestStats:
    passed: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped


def read_stats(xml_dir: Path) -> TestStats:
    stats = TestStats()
    for xml_path in sorted(xml_dir.glob("**/*.xml")):
        try:
            root = ET.parse(xml_path).getroot()
        except (ET.ParseError, OSError) as error:
            raise ValueError(f"Cannot parse JUnit XML {xml_path}: {error}") from error

        passed = failed = skipped = 0
        for testcase in root.iter("testcase"):
            if testcase.find("failure") is not None or testcase.find("error") is not None:
                failed += 1
            elif testcase.find("skipped") is not None:
                skipped += 1
            else:
                passed += 1
        stats = TestStats(
            stats.passed + passed,
            stats.failed + failed,
            stats.skipped + skipped,
        )
    return stats


def build_status(compile_outcome: str, test_outcome: str, job_status: str, stats: TestStats) -> str:
    if job_status == "cancelled":
        return "CANCELLED"
    if compile_outcome != "success":
        return "BUILD_ERROR"
    if test_outcome == "success":
        return "SUCCESS"
    if stats.total == 0:
        return "TEST_ERROR"
    return "FAILED"


def build_message(project: str, ci: str, branch: str, commit: str, status: str,
                  stats: TestStats, run_url: str) -> str:
    return (
        f"{project}\n"
        f"CI: {ci}\n"
        f"Branch: {branch}\n"
        f"Commit: {commit}\n"
        f"Status: {status}\n"
        f"Tests: passed={stats.passed}, failed={stats.failed}, skipped={stats.skipped}\n"
        f"Run: {run_url}"
    )


def send_message(token: str, chat_id: str, message: str, api_url: str, timeout: float) -> None:
    endpoint = f"{api_url.rstrip('/')}/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
    request = urllib.request.Request(endpoint, data=payload, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Telegram HTTP status {response.status}")
            body = response.read().decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"Telegram request failed: {error}") from error

    try:
        response_json = __import__("json").loads(body)
    except ValueError as error:
        raise RuntimeError("Telegram returned invalid JSON") from error
    if response_json.get("ok") is not True:
        raise RuntimeError("Telegram API returned ok=false")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml-dir", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--ci", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--compile-outcome", required=True)
    parser.add_argument("--test-outcome", required=True)
    parser.add_argument("--job-status", required=True)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--api-url", default="https://api.telegram.org")
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stats = read_stats(args.xml_dir) if args.xml_dir.is_dir() else TestStats()
    status = build_status(args.compile_outcome, args.test_outcome, args.job_status, stats)
    message = build_message(args.project, args.ci, args.branch, args.commit, status, stats, args.run_url)

    if not args.send:
        print(message)
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram notification skipped: required secrets are not configured", file=sys.stderr)
        return 0
    send_message(token, chat_id, message, args.api_url, args.timeout)
    print("Telegram notification sent")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as error:
        print(f"Telegram notification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
