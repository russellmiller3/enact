"""Quick diagnostic — show top-level receipts that don't match any run."""
import json
import pathlib
import re

RUN_ID_RE = re.compile(
    r"ENACT_CHAOS_RUN_ID[= ]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
PATH_RE = re.compile(
    r"chaos[/\\]runs[/\\]([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


def main() -> None:
    unattributed = []
    for r in pathlib.Path("receipts").glob("*.json"):
        try:
            data = json.loads(r.read_text())
        except Exception:
            continue
        payload = data.get("payload") or {}
        cmd = payload.get("command", "") or ""
        fp = payload.get("file_path", "") or ""

        matched = bool(
            RUN_ID_RE.search(cmd)
            or PATH_RE.search(cmd)
            or PATH_RE.search(fp)
        )
        if not matched:
            for v in payload.values():
                if isinstance(v, str) and (
                    RUN_ID_RE.search(v) or PATH_RE.search(v)
                ):
                    matched = True
                    break
        if matched:
            continue

        decision = data.get("decision", "?")
        tool = payload.get("tool_name", "?")
        failed = [
            (p.get("policy"), (p.get("reason", "") or "")[:80])
            for p in data.get("policy_results", []) or []
            if not p.get("passed", True)
        ]
        unattributed.append(
            (r.name[:14], decision, tool, (cmd or fp)[:80], failed)
        )

    print(f"-- {len(unattributed)} unattributed top-level receipts --")
    for name, decision, tool, snippet, failed in unattributed:
        print(f"{name} | {decision} | {tool} | {snippet}")
        for pol, reason in failed:
            print(f"    BLOCKED: {pol} -> {reason}")


if __name__ == "__main__":
    main()
