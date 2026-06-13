#!/usr/bin/env python3
"""
generate_delta.py — Compare new EasyList rules against the baseline (current app bundle)
and produce a delta_rules.json file containing only NEW or CHANGED rules.

This script is designed to run in GitHub Actions as part of the OTA auto-update pipeline.

Usage:
    python3 generate_delta.py \
        --baseline-dir ./baseline \
        --output-dir ./output \
        --max-delta-rules 28000

The script will:
1. Download the latest filter lists from easylist.to
2. Convert them to DNR JSON format
3. Compare against baseline JSON files
4. Output delta_rules.json + version.json
"""

import json
import os
import sys
import math
import hashlib
import argparse
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# Reuse the DNR conversion logic from convert_easylist_dnr.py
# ============================================================

RESOURCE_MAP = {
    'script': 'script',
    'image': 'image',
    'stylesheet': 'stylesheet',
    'object': 'object',
    'xmlhttprequest': 'xmlhttprequest',
    'subdocument': 'sub_frame',
    'ping': 'ping',
    'websocket': 'websocket',
    'webrtc': 'webrtc',
    'document': 'main_frame',
    'other': 'other',
    'media': 'media',
    'font': 'font',
    'third-party': None,
    '~third-party': None
}


def parse_options(options_str):
    opts = options_str.split(',')
    resourceTypes = []
    excludedResourceTypes = []
    requestDomains = []
    excludedRequestDomains = []
    is_third_party = None

    for opt in opts:
        if opt == 'third-party':
            is_third_party = True
        elif opt == '~third-party':
            is_third_party = False
        elif opt.startswith('domain='):
            domains = opt[7:].split('|')
            for d in domains:
                if d.startswith('~'):
                    excludedRequestDomains.append(d[1:])
                else:
                    requestDomains.append(d)
        elif opt.startswith('~'):
            res = RESOURCE_MAP.get(opt[1:])
            if res:
                excludedResourceTypes.append(res)
        else:
            res = RESOURCE_MAP.get(opt)
            if res:
                resourceTypes.append(res)

    condition = {}
    if resourceTypes:
        condition['resourceTypes'] = resourceTypes
    if excludedResourceTypes:
        condition['excludedResourceTypes'] = excludedResourceTypes
    if requestDomains:
        condition['requestDomains'] = requestDomains
    if excludedRequestDomains:
        condition['excludedRequestDomains'] = excludedRequestDomains

    if is_third_party is True:
        condition['domainType'] = 'thirdParty'
    elif is_third_party is False:
        condition['domainType'] = 'firstParty'

    return condition


def parse_easylist_to_dnr(input_file, start_id=1):
    """Parse an EasyList-format file and return a list of DNR rules."""
    rules = []
    current_id = start_id

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('!') or line.startswith('['):
                continue

            # Skip cosmetic rules (handled separately by content script)
            if '##' in line or '#?#' in line or '#@#' in line:
                continue

            action_type = "block"
            if line.startswith('@@'):
                action_type = "allow"
                line = line[2:]

            condition = {}
            url_filter = line

            if '$' in line:
                parts = line.split('$', 1)
                url_filter = parts[0]
                condition = parse_options(parts[1])

            if url_filter:
                condition['urlFilter'] = url_filter

            rule = {
                "id": current_id,
                "priority": 1,
                "action": {"type": action_type},
                "condition": condition
            }

            rules.append(rule)
            current_id += 1

    return rules


# ============================================================
# Delta generation logic
# ============================================================

def rule_fingerprint(rule):
    """Create a unique fingerprint for a rule (ignoring its ID)."""
    # Create a copy without the ID to compare content only
    r = {
        "action": rule.get("action", {}),
        "condition": rule.get("condition", {})
    }
    # Add priority if non-default
    if rule.get("priority", 1) != 1:
        r["priority"] = rule["priority"]
    return hashlib.md5(json.dumps(r, sort_keys=True).encode()).hexdigest()


def load_baseline_fingerprints(baseline_dir, prefixes):
    """Load all rules from baseline JSON files and return set of fingerprints."""
    fingerprints = set()
    
    for prefix in prefixes:
        # Find all chunks: prefix_1.json, prefix_2.json, ...
        i = 1
        while True:
            filepath = os.path.join(baseline_dir, f"{prefix}_{i}.json")
            if not os.path.exists(filepath):
                break
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    rules = json.load(f)
                for rule in rules:
                    fingerprints.add(rule_fingerprint(rule))
            except Exception as e:
                print(f"Warning: Could not load {filepath}: {e}")
            i += 1
    
    return fingerprints


def download_filter_list(url, output_path):
    """Download a filter list file from URL."""
    import urllib.request
    print(f"Downloading {url}...")
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; uShield/1.0; +https://github.com/huykhoi0504/uShield)'
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        with open(output_path, 'wb') as f:
            f.write(data)
        # Count lines
        with open(output_path, 'r', encoding='utf-8') as f:
            lines = sum(1 for _ in f)
        print(f"  -> {lines} lines saved to {output_path}")
        return True
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return False


# Filter list sources (CC BY-SA licensed from EasyList)
FILTER_SOURCES = {
    "ads": {
        "url": "https://easylist.to/easylist/easylist.txt",
        "baseline_prefix": "ads_net",
        "start_id": 5000001,  # Dynamic rules use IDs starting at 5M
    },
    "privacy": {
        "url": "https://easylist.to/easylist/easyprivacy.txt",
        "baseline_prefix": "privacy_net",
        "start_id": 5100001,
    },
    "cookie": {
        "url": "https://secure.fanboy.co.nz/fanboy-cookiemonster.txt",
        "baseline_prefix": "cookie_net",
        "start_id": 5200001,
    },
    "annoyance": {
        "url": "https://secure.fanboy.co.nz/fanboy-annoyance.txt",
        "baseline_prefix": "annoyance_net",
        "start_id": 5300001,
    },
    "social": {
        "url": "https://easylist.to/easylist/fanboy-social.txt",
        "baseline_prefix": "social_net",
        "start_id": 5400001,
    },
}


def main():
    parser = argparse.ArgumentParser(description="Generate delta rules for OTA update")
    parser.add_argument("--baseline-dir", required=True,
                        help="Directory containing baseline JSON files from the current App Store build")
    parser.add_argument("--output-dir", required=True,
                        help="Directory to output delta_rules.json and version.json")
    parser.add_argument("--max-delta-rules", type=int, default=28000,
                        help="Maximum number of delta rules (Safari limit is 30K, keep buffer)")
    parser.add_argument("--temp-dir", default="/tmp/ushield_filters",
                        help="Temporary directory for downloaded filter lists")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.temp_dir, exist_ok=True)

    # Step 1: Load baseline fingerprints
    print("=" * 60)
    print("Step 1: Loading baseline fingerprints...")
    print("=" * 60)
    
    baseline_prefixes = [src["baseline_prefix"] for src in FILTER_SOURCES.values()]
    baseline_fps = load_baseline_fingerprints(args.baseline_dir, baseline_prefixes)
    print(f"Loaded {len(baseline_fps)} baseline rule fingerprints")

    # Step 2: Download latest filter lists
    print("\n" + "=" * 60)
    print("Step 2: Downloading latest filter lists...")
    print("=" * 60)
    
    for name, src in FILTER_SOURCES.items():
        output_path = os.path.join(args.temp_dir, f"{name}.txt")
        if not download_filter_list(src["url"], output_path):
            print(f"FATAL: Could not download {name} filter list. Aborting.")
            sys.exit(1)

    # Step 3: Parse and compute delta
    print("\n" + "=" * 60)
    print("Step 3: Computing delta rules...")
    print("=" * 60)
    
    all_delta_rules = []
    delta_id = 5000001  # Start ID for dynamic delta rules
    stats = {}

    for name, src in FILTER_SOURCES.items():
        input_path = os.path.join(args.temp_dir, f"{name}.txt")
        new_rules = parse_easylist_to_dnr(input_path, start_id=1)  # temp ID, will reassign
        
        new_count = 0
        for rule in new_rules:
            fp = rule_fingerprint(rule)
            if fp not in baseline_fps:
                # This is a NEW rule not in the baseline
                rule["id"] = delta_id
                all_delta_rules.append(rule)
                delta_id += 1
                new_count += 1
        
        stats[name] = {
            "total_latest": len(new_rules),
            "delta_new": new_count
        }
        print(f"  {name}: {len(new_rules)} total -> {new_count} new rules")

    print(f"\nTotal delta rules: {len(all_delta_rules)}")

    # Step 4: Trim if over limit
    if len(all_delta_rules) > args.max_delta_rules:
        print(f"\n⚠️  Delta exceeds limit ({args.max_delta_rules}). Trimming...")
        # Prioritize: block rules first, then by source order
        # Keep allow rules (exceptions) with high priority
        allow_rules = [r for r in all_delta_rules if r["action"]["type"] == "allow"]
        block_rules = [r for r in all_delta_rules if r["action"]["type"] == "block"]
        
        budget = args.max_delta_rules
        kept_allow = allow_rules[:min(len(allow_rules), budget // 5)]  # 20% budget for allows
        budget -= len(kept_allow)
        kept_block = block_rules[:budget]
        
        all_delta_rules = kept_allow + kept_block
        # Reassign IDs
        for i, rule in enumerate(all_delta_rules):
            rule["id"] = 5000001 + i
        
        print(f"  Trimmed to {len(all_delta_rules)} rules ({len(kept_allow)} allow + {len(kept_block)} block)")

    # Step 5: Write output files
    print("\n" + "=" * 60)
    print("Step 5: Writing output files...")
    print("=" * 60)

    # delta_rules.json
    delta_path = os.path.join(args.output_dir, "delta_rules.json")
    with open(delta_path, 'w', encoding='utf-8') as f:
        json.dump(all_delta_rules, f, separators=(',', ':'))
    
    delta_size = os.path.getsize(delta_path) / 1024
    print(f"  delta_rules.json: {len(all_delta_rules)} rules, {delta_size:.1f} KB")

    # version.json - metadata for the iOS app to check
    now = datetime.now(timezone.utc)
    version_hash = hashlib.sha256(
        json.dumps(all_delta_rules, sort_keys=True).encode()
    ).hexdigest()[:12]
    
    version_info = {
        "version": now.strftime("%Y%m%d%H"),
        "hash": version_hash,
        "rules_count": len(all_delta_rules),
        "updated_at": now.isoformat(),
        "expires_hours": 24,
        "stats": stats,
        "delta_url": "https://uShieldApp.github.io/uShield/delta_rules.json"
    }
    
    version_path = os.path.join(args.output_dir, "version.json")
    with open(version_path, 'w', encoding='utf-8') as f:
        json.dump(version_info, f, indent=2)
    
    print(f"  version.json: version={version_info['version']}, hash={version_hash}")
    
    print("\n✅ Delta generation complete!")
    print(f"   Output directory: {args.output_dir}")


if __name__ == '__main__':
    main()
