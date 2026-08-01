#!/usr/bin/env python3
"""Inspect and test the independently versioned RAG product repositories."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "providers.json"


def load_repositories() -> list[dict[str, Any]]:
    with REGISTRY_PATH.open(encoding="utf-8") as registry_file:
        registry = json.load(registry_file)
    repositories = registry.get("repositories")
    if not isinstance(repositories, list):
        raise ValueError("providers.json must contain a repositories list")
    return repositories


def select_repositories(
    repositories: list[dict[str, Any]], names: list[str]
) -> list[dict[str, Any]]:
    if not names:
        return repositories
    by_id = {repository["id"]: repository for repository in repositories}
    unknown = sorted(set(names) - set(by_id))
    if unknown:
        raise ValueError(f"unknown product(s): {', '.join(unknown)}")
    return [by_id[name] for name in names]


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def command_list(repositories: list[dict[str, Any]]) -> int:
    width = max(len(repository["id"]) for repository in repositories)
    for repository in repositories:
        print(
            f"{repository['id']:<{width}}  "
            f"{repository['path']:<15}  {repository['role']}"
        )
    return 0


def command_check(repositories: list[dict[str, Any]]) -> int:
    failed = False
    for repository in repositories:
        product_id = repository["id"]
        product_path = ROOT / repository["path"]
        if not product_path.is_dir():
            print(f"{product_id}: MISSING ({product_path})")
            failed = True
            continue

        result = run(["git", "remote", "get-url", "origin"], product_path)
        actual_remote = result.stdout.strip()
        expected_remote = repository["remote"]
        if result.returncode != 0:
            print(f"{product_id}: not a Git repository with an origin remote")
            failed = True
        elif actual_remote != expected_remote:
            print(
                f"{product_id}: origin mismatch "
                f"(expected {expected_remote}, found {actual_remote})"
            )
            failed = True
        else:
            print(f"{product_id}: ok")
    return 1 if failed else 0


def command_status(repositories: list[dict[str, Any]]) -> int:
    failed = False
    for repository in repositories:
        product_id = repository["id"]
        product_path = ROOT / repository["path"]
        print(f"[{product_id}]")
        if not product_path.is_dir():
            print(f"missing: {product_path}")
            failed = True
            continue
        result = run(["git", "status", "--short", "--branch"], product_path)
        print(result.stdout.rstrip() or "clean")
        failed = failed or result.returncode != 0
    return 1 if failed else 0


def command_test(repositories: list[dict[str, Any]]) -> int:
    failed = False
    for repository in repositories:
        product_id = repository["id"]
        test_command = repository.get("test_command")
        print(f"[{product_id}]")
        if not test_command:
            print("skipped: no test command declared")
            continue
        product_path = ROOT / repository["path"]
        if not product_path.is_dir():
            print(f"missing: {product_path}")
            failed = True
            continue
        result = run(test_command, product_path)
        print(result.stdout.rstrip())
        if result.returncode != 0:
            print(f"failed with exit code {result.returncode}")
            failed = True
    return 1 if failed else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Coordinate independently versioned RAG product repositories."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="list registered products")
    for name, help_text in (
        ("check", "validate local paths and origin remotes"),
        ("status", "show Git status for each product"),
        ("test", "run each product's declared test command"),
    ):
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.add_argument("products", nargs="*", help="optional product IDs")
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        repositories = load_repositories()
        if args.command == "list":
            return command_list(repositories)
        repositories = select_repositories(repositories, args.products)
        commands = {
            "check": command_check,
            "status": command_status,
            "test": command_test,
        }
        return commands[args.command](repositories)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
