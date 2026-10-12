#!/usr/bin/env python3
"""CLI utility to execute the official PRAL/FBR Pre-Production Certification drill.

Usage:
    python scripts/run_fbr_certification_drill.py --mode SANDBOX --output certification_report.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.services.fbr_certification_service import FBRCertificationService


def main():
    parser = argparse.ArgumentParser(description="PRAL / FBR Pre-Production Certification Runner")
    parser.add_argument("--mode", default="SANDBOX", choices=["SANDBOX", "PRODUCTION", "DEMO"], help="Adapter mode to certify")
    parser.add_argument("--ntn", default="1234567-8", help="Taxpayer NTN")
    parser.add_argument("--pos-id", default="10001", help="Branch POS Identifier")
    parser.add_argument("--tenant-id", default="system-cert-tenant", help="Tenant Identifier")
    parser.add_argument("--cert", default=None, help="Path to client X.509 certificate (optional)")
    parser.add_argument("--output", default=None, help="Output JSON report file path")
    parser.add_argument("--markdown", default=None, help="Output Markdown report file path")

    args = parser.parse_args()

    print(f"\n======================================================================")
    print(f"  FBR / PRAL PRE-PRODUCTION CERTIFICATION DRILL")
    print(f"  Mode: {args.mode} | NTN: {args.ntn} | POS ID: {args.pos_id}")
    print(f"======================================================================\n")

    report = FBRCertificationService.run_full_certification_suite(
        tenant_id=args.tenant_id,
        taxpayer_ntn=args.ntn,
        pos_id=args.pos_id,
        forced_adapter_mode=args.mode,
        client_cert_path=args.cert,
    )

    print(f"[*] Dossier Reference : {report['dossier_id']}")
    print(f"[*] Certification Status : {report['certification_status']}")
    print(f"[*] Compliance Score  : {report['compliance_score']}% ({report['passed_cycles']}/{report['total_cycles']} Cycles Passed)")
    print(f"[*] Total Duration     : {report['total_duration_ms']} ms")
    print(f"[*] Cryptographic Seal : {report['cryptographic_seal']}\n")

    for cycle in report["cycles"]:
        symbol = "PASS" if cycle["passed"] else "FAIL"
        print(f"  [{symbol}] Cycle {cycle['cycle_number']}: {cycle['cycle_name']} ({cycle['duration_ms']}ms)")
        if cycle.get("errors"):
            for err in cycle["errors"]:
                print(f"         Error: {err}")

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\n[+] JSON report saved to: {out_p.resolve()}")

    if args.markdown:
        md_p = Path(args.markdown)
        md_p.parent.mkdir(parents=True, exist_ok=True)
        md_content = f"""# PRAL Pre-Production Certification Dossier

**Dossier ID:** `{report['dossier_id']}`  
**Certification Status:** **{report['certification_status']}**  
**Compliance Score:** {report['compliance_score']}%  
**Execution Timestamp:** {report['executed_at']}  
**Cryptographic Integrity Seal:** `{report['cryptographic_seal']}`  

## Transmission Cycles Breakdown

| Cycle # | Name | Status | Latency | Description |
| :--- | :--- | :--- | :--- | :--- |
"""
        for c in report["cycles"]:
            status_badge = "PASS" if c["passed"] else "FAIL"
            md_content += f"| {c['cycle_number']} | `{c['cycle_name']}` | **{status_badge}** | {c['duration_ms']}ms | {c['description']} |\n"

        md_p.write_text(md_content, encoding="utf-8")
        print(f"[+] Markdown dossier saved to: {md_p.resolve()}")

    print("\n======================================================================\n")
    if not report["certified"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
