"""Offline diagnostic entry point. It only writes an explicitly requested report."""
import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .inventory import offline_snapshot
from .models import version_text
from .scanner import scan


def main():
    parser = argparse.ArgumentParser(description="Read-only SKSE compatibility inventory")
    parser.add_argument("--mo2", required=True, type=Path, help="MO2 instance directory")
    parser.add_argument("--game", type=Path, help="Optional override; otherwise read MO2 configuration")
    parser.add_argument("--profile", help="Optional override; otherwise read selected profile")
    parser.add_argument("--output", type=Path, help="Private JSON report destination; contains local paths")
    args = parser.parse_args()
    try:
        snapshot = offline_snapshot(args.mo2, args.game, args.profile)
        report = scan(snapshot)
        if args.output:
            output = args.output.resolve()
            protected = [args.mo2.resolve(), Path(snapshot.game_path).resolve()]
            # Also protect configured providers outside the default instance directory.
            protected.extend(Path(p.path).parents[2].resolve() for p in snapshot.providers)
            if any(output == root or root in output.parents for root in protected):
                parser.error("Report output must be outside the scanned installation/mod directories")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
        current = version_text(report.runtime)
        statuses = Counter(row.assessments[current].status for row in report.rows if current in row.assessments)
        print(f"Skyrim {current}; {len(report.rows)} DLL providers; {dict(statuses)}")
        print(f"Address Library files: {len(snapshot.databases)}; root component candidates: {len(snapshot.root_candidates)}")
        for warning in snapshot.warnings:
            print("Note:", warning)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Scan failed: {exc}\n")


if __name__ == "__main__":
    main()
