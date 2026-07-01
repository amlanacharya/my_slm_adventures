#!/usr/bin/env python3
"""
SLM harness: ornith reads local .md issues + prd.md → writes code to kurma_slm/ → Claude/Codex judge → feedback loop.

Usage
-----
    # dry-run (show what would be written):
    python harness.py --issue 058 --dry-run

    # run for real:
    python harness.py --issue 058

    # run all issues in issues/ folder:
    python harness.py

    # choose your judge:
    python harness.py --issue 058 --judge codex
    python harness.py --issue 058 --judge both

Requires
--------
    - Ollama running at http://localhost:11434 with ornith:9b-q4
    - claude CLI on PATH (for --judge claude or both)
    - ruff + pytest installed (for --judge codex or both)
    - httpx  (.venv already has it)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT        = Path(__file__).resolve().parent
ISSUES_DIR  = ROOT / "issues"
PRD_PATH    = ROOT / "prd.md"
OUTPUT_DIR  = ROOT / "kurma_slm"   # SLM writes all generated files here

MAX_PRD_CHARS    = 4_000
MAX_FILE_CHARS   = 2_000
MAX_CONTEXT_CHARS = 8_000


# ---------------------------------------------------------------------------
# Local issue loader
# ---------------------------------------------------------------------------


def list_issues() -> list[Path]:
    return sorted(ISSUES_DIR.glob("*.md"))


def load_issue(identifier: str) -> dict[str, Any]:
    """Load by number prefix (e.g. '058') or full filename."""
    candidates = [p for p in list_issues() if p.stem.startswith(identifier)]
    if not candidates:
        raise FileNotFoundError(f"No issue file matching '{identifier}' in {ISSUES_DIR}")
    path = candidates[0]
    text = path.read_text(encoding="utf-8")

    # parse frontmatter
    fm: dict[str, str] = {}
    body = text
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"')
        body = fm_match.group(2).strip()

    return {
        "number": fm.get("number", path.stem.split("_")[0]),
        "title":  fm.get("title", path.stem),
        "body":   body,
        "path":   path,
    }


def extract_acceptance_criteria(body: str) -> str:
    m = re.search(r"##\s*Acceptance criteria\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else body.strip()


# ---------------------------------------------------------------------------
# PRD — only sections matching this issue's user stories
# ---------------------------------------------------------------------------


def _story_numbers(issue_body: str) -> list[int]:
    m = re.search(r"[Uu]ser\s+stories?\s+covered:\s*([\d,\s]+)", issue_body)
    if not m:
        return []
    return [int(n.strip()) for n in m.group(1).split(",") if n.strip().isdigit()]


def load_prd(issue: dict[str, Any]) -> str:
    if not PRD_PATH.exists():
        return ""
    text = re.sub(r"\\([#*_\[\]`>|~])", r"\1", PRD_PATH.read_text(encoding="utf-8"))
    nums = _story_numbers(issue.get("body") or "")
    if not nums:
        return text[:MAX_PRD_CHARS]

    nums_re = re.compile(r"\b(" + "|".join(str(n) for n in nums) + r")\b")
    header_re = re.compile(r"^#{1,4}\s")
    sections: list[list[str]] = []
    current: list[str] = []
    in_target = False

    for line in text.split("\n"):
        if header_re.match(line):
            if in_target and current:
                sections.append(current)
            in_target = bool(nums_re.search(line))
            current = [line] if in_target else []
        elif in_target:
            current.append(line)
    if in_target and current:
        sections.append(current)

    extracted = "\n\n".join("\n".join(s) for s in sections)
    return (extracted or text)[:MAX_PRD_CHARS]


# ---------------------------------------------------------------------------
# Source context — read already-written SLM files for rework rounds
# ---------------------------------------------------------------------------


def load_prior_output(files: list[str]) -> str:
    """On rework rounds, feed back SLM's own previous files as context."""
    parts: list[str] = []
    total = 0
    for rel in files:
        path = OUTPUT_DIR / rel
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS] + "\n... (truncated)"
        snippet = f"### {rel}\n```python\n{content}\n```"
        if total + len(snippet) > MAX_CONTEXT_CHARS:
            break
        parts.append(snippet)
        total += len(snippet)
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Ollama (ornith)
# ---------------------------------------------------------------------------


def call_ornith(messages: list[dict[str, str]], base_url: str, model: str) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    parts: list[str] = []
    with httpx.stream(
        "POST", url,
        json={"model": model, "messages": messages, "temperature": 0.0, "stream": True},
        timeout=180.0,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            payload = line[6:]
            if payload.strip() == "[DONE]":
                break
            try:
                token = json.loads(payload)["choices"][0]["delta"].get("content") or ""
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
            if token:
                print(token, end="", flush=True)
                parts.append(token)
    print()
    return "".join(parts)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SLM_SYSTEM = """\
You are an expert Python developer.
Given an issue, implement ONLY what is asked — nothing more.

Rules:
- Touch the MINIMUM number of files required.
- Write tests alongside implementation code.
- Output ONLY fenced code blocks, each preceded by a path comment:
    # file: src/blueprint.py
    # file: tests/test_blueprint.py
  Paths are relative to the project root. No prose, no explanations — only code blocks.
"""

_JUDGE_SYSTEM = """\
You are a strict code reviewer. Decide whether the code fully satisfies ALL acceptance criteria.

Respond with a JSON object ONLY (no markdown fences, no prose):
{
  "passed": true | false,
  "score": 0-10,
  "reasoning": "one or two sentences",
  "missing": ["unmet criteria — empty if passed"]
}
"""


def build_messages(
    issue: dict[str, Any],
    prd_context: str,
    source_context: str,
    previous: dict[str, Any] | None,
) -> list[dict[str, str]]:
    prd_block = f"## Relevant PRD sections\n\n{prd_context}\n\n---\n\n" if prd_context else ""

    if previous is None:
        user = (
            f"## Issue {issue['number']}: {issue['title']}\n\n"
            f"{issue['body']}\n\n---\n\n"
            f"{prd_block}"
        )
    else:
        files = "\n".join(f"  - {p}" for p in previous["files"])
        codex_block = (
            "### Automated check failures (ruff / pytest)\n"
            + "\n".join(f"  - {e}" for e in previous["codex_errors"])
            + "\n\n"
        ) if previous["codex_errors"] else ""
        missing_block = (
            "### Acceptance criteria still unmet\n"
            + "\n".join(f"  - {m}" for m in previous["missing"])
            + "\n\n"
        ) if previous["missing"] else ""
        user = (
            f"## Issue {issue['number']}: {issue['title']} — REWORK (round {previous['round']})\n\n"
            f"You previously wrote:\n{files}\n\n"
            f"**Fix ONLY the items below. Do not touch what already passed.**\n\n"
            f"{codex_block}"
            f"{missing_block}"
            f"### Acceptance criteria\n{extract_acceptance_criteria(issue['body'])}\n\n"
            f"---\n\n"
            f"## Your previous files (current state)\n\n{source_context}"
        )

    return [
        {"role": "system", "content": _SLM_SYSTEM},
        {"role": "user",   "content": user},
    ]


# ---------------------------------------------------------------------------
# Parse file blocks
# ---------------------------------------------------------------------------


def parse_blocks(output: str) -> list[tuple[str, str]]:
    return [
        (m.group(1).strip(), m.group(2))
        for m in re.finditer(r"#\s*file:\s*(\S+)\s*\n```[a-z]*\n(.*?)```", output, re.DOTALL)
    ]


# ---------------------------------------------------------------------------
# Write files to kurma_slm/
# ---------------------------------------------------------------------------


def write_files(blocks: list[tuple[str, str]], dry_run: bool) -> list[str]:
    written: list[str] = []
    for rel, code in blocks:
        target = OUTPUT_DIR / rel
        if dry_run:
            print(f"      [dry-run] {rel}  ({len(code)} chars)")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(code, encoding="utf-8")
            print(f"      wrote  kurma_slm/{rel}")
        written.append(rel)
    return written


# ---------------------------------------------------------------------------
# Codex judge (ruff + pytest)
# ---------------------------------------------------------------------------


def codex_judge(rel_paths: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"passed": True, "errors": []}
    written = [OUTPUT_DIR / p for p in rel_paths]

    try:
        r = subprocess.run(
            ["ruff", "check", "--output-format", "json", "--", *map(str, written)],
            capture_output=True, text=True, timeout=30, cwd=str(OUTPUT_DIR),
        )
        issues = json.loads(r.stdout) if r.stdout.strip() else []
        if issues:
            result["passed"] = False
            result["errors"].extend(
                f"ruff {i.get('filename','?')}:{i.get('location',{}).get('row','?')}"
                f" [{i.get('code','?')}] {i.get('message','?')}"
                for i in issues[:8]
            )
    except FileNotFoundError:
        pass
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        result["errors"].append(f"ruff: {e}")

    test_files = [OUTPUT_DIR / p for p in rel_paths if Path(p).name.startswith("test_")]
    if test_files:
        try:
            r = subprocess.run(
                ["pytest", "--tb=short", "-q", "--", *map(str, test_files)],
                capture_output=True, text=True, timeout=90, cwd=str(OUTPUT_DIR),
            )
            if r.returncode != 0:
                result["passed"] = False
                lines = (r.stdout + r.stderr).strip().split("\n")
                result["errors"].extend(f"pytest: {l}" for l in lines[-20:] if l.strip())
        except FileNotFoundError:
            pass
        except subprocess.TimeoutExpired:
            result["passed"] = False
            result["errors"].append("pytest timed out")

    return result


# ---------------------------------------------------------------------------
# Claude judge (semantic)
# ---------------------------------------------------------------------------


def claude_judge(issue: dict[str, Any], output: str, round_n: int) -> dict[str, Any]:
    criteria = extract_acceptance_criteria(issue.get("body") or "")
    round_note = f" (round {round_n})" if round_n > 1 else ""
    prompt = (
        f"{_JUDGE_SYSTEM}\n\n"
        f"## Issue {issue['number']}: {issue['title']}{round_note}\n\n"
        f"### Acceptance criteria\n{criteria}\n\n"
        f"### Generated code\n```\n{output[:8000]}\n```"
    )
    r = subprocess.run(["claude", "-p", prompt], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"claude -p failed: {r.stderr[:200]}")
    raw = re.sub(r"^```[a-z]*\n?", "", r.stdout.strip())
    raw = re.sub(r"\n?```$", "", raw.strip())
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise RuntimeError(f"no JSON in claude output: {raw[:200]}")
    return json.loads(m.group(0))


# ---------------------------------------------------------------------------
# Per-issue loop
# ---------------------------------------------------------------------------


def run_issue(
    issue: dict[str, Any],
    *,
    base_url: str,
    model: str,
    judge: str,
    max_rounds: int,
    dry_run: bool,
    verbose: bool,
) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"Issue {issue['number']}: {issue['title']}")

    prd_context = load_prd(issue)
    previous: dict[str, Any] | None = None
    result: dict[str, Any] = {}

    for round_n in range(1, max_rounds + 1):
        print(f"\n  Round {round_n}/{max_rounds}")

        source_ctx = load_prior_output(previous["files"]) if previous else ""
        messages = build_messages(issue, prd_context, source_ctx, previous)

        print(f"    [ornith] generating...", flush=True)
        try:
            output = call_ornith(messages, base_url, model)
            print(f"    --- {len(output)} chars ---")
        except Exception as exc:  # noqa: BLE001
            print(f"    FAILED: {exc}")
            return {"issue": issue["number"], "passed": False, "error": str(exc)}

        blocks = parse_blocks(output)
        if not blocks:
            print("    WARNING: no `# file:` blocks found")
            if verbose:
                print(output[:600])
            return {"issue": issue["number"], "passed": False, "error": "no file blocks"}

        rel_paths = write_files(blocks, dry_run)

        judge_errors: list[str] = []
        missing: list[str] = []
        score, reasoning = 0, ""
        passed = True

        if judge == "none":
            print(f"    [judge] skipped")

        if judge in ("codex", "both") and not dry_run:
            print(f"    [codex] ruff + pytest...", end=" ", flush=True)
            cx = codex_judge(rel_paths)
            print("OK" if cx["passed"] else f"FAIL ({len(cx['errors'])})")
            if not cx["passed"]:
                passed = False
                judge_errors.extend(cx["errors"])
            if cx["errors"] and verbose:
                for e in cx["errors"]:
                    print(f"      {e}")

        if judge in ("claude", "both"):
            print(f"    [claude] judging...", end=" ", flush=True)
            try:
                verdict = claude_judge(issue, output, round_n)
                c_passed  = bool(verdict.get("passed"))
                score     = verdict.get("score", 0)
                reasoning = verdict.get("reasoning", "")
                missing   = verdict.get("missing", [])
                print(f"{'PASS' if c_passed else 'FAIL'}  score={score}/10")
                if not c_passed or verbose:
                    print(f"      {reasoning}")
                    for m in missing:
                        print(f"      - {m}")
                if not c_passed:
                    passed = False
            except Exception as exc:  # noqa: BLE001
                print(f"ERROR: {exc}")
                passed = False
                reasoning = str(exc)

        result = {
            "issue": issue["number"],
            "title": issue["title"],
            "passed": passed,
            "score": score,
            "reasoning": reasoning,
            "missing": missing,
            "judge_errors": judge_errors,
            "rounds": round_n,
            "files": rel_paths,
        }

        if passed:
            print(f"\n  DONE — passed in {round_n} round(s)")
            print(f"  Files in kurma_slm/:")
            for p in rel_paths:
                print(f"    {p}")
            break

        if round_n < max_rounds:
            previous = {
                "round": round_n + 1,
                "files": rel_paths,
                "codex_errors": judge_errors,
                "missing": missing,
            }
            reasons = []
            if judge_errors:
                reasons.append(f"codex: {len(judge_errors)} issue(s)")
            if missing:
                reasons.append(f"missing: {len(missing)}")
            print(f"  Reworking ({', '.join(reasons) or 'failed'})...")
        else:
            print(f"  Max rounds reached — check kurma_slm/ manually")

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SLM harness: ornith → judge → kurma_slm/")
    p.add_argument("--issue", help="Issue number prefix (e.g. 058) or run all if omitted")
    p.add_argument("--model",    default="ornith:9b-q4",           help="Ollama model tag")
    p.add_argument("--base-url", default="http://localhost:11434/v1", help="Ollama base URL")
    p.add_argument("--judge",    choices=["claude", "codex", "both", "none"], default="claude",
                   help="Reviewer: claude | codex | both | none  (default: claude)")
    p.add_argument("--max-rounds", type=int, default=3,            help="Max rework rounds")
    p.add_argument("--dry-run",  action="store_true",              help="Show what would be written, skip disk writes")
    p.add_argument("--verbose",  "-v", action="store_true",        help="Show full judge output")
    args = p.parse_args(argv)

    if args.issue:
        issues = [load_issue(args.issue)]
    else:
        paths = list_issues()
        if not paths:
            print(f"No .md files found in {ISSUES_DIR}", file=sys.stderr)
            return 1
        issues = [load_issue(p.stem.split("_")[0]) for p in paths]

    print(f"ornith   : {args.model}  @  {args.base_url}")
    print(f"judge    : {args.judge}")
    print(f"output   : kurma_slm/")
    print(f"rounds   : {args.max_rounds}")
    if args.dry_run:
        print("DRY RUN")

    results: list[dict[str, Any]] = []
    for issue in issues:
        try:
            results.append(run_issue(
                issue,
                base_url=args.base_url,
                model=args.model,
                judge=args.judge,
                max_rounds=args.max_rounds,
                dry_run=args.dry_run,
                verbose=args.verbose,
            ))
        except Exception as exc:  # noqa: BLE001
            print(f"\nERROR issue {issue['number']}: {exc}")
            results.append({"issue": issue["number"], "passed": False, "error": str(exc)})

    passed_count = sum(1 for r in results if r.get("passed"))
    print(f"\n{'='*60}")
    print(f"DONE  {passed_count}/{len(results)} passed")
    for r in results:
        status = "PASS" if r.get("passed") else "FAIL"
        print(f"  {r['issue']} [{status}]  rounds={r.get('rounds','?')}  {r.get('title','')[:50]}")
    print("=" * 60)
    return 0 if passed_count == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
