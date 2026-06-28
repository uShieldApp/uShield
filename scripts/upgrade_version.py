#!/usr/bin/env python3
"""
upgrade_version.py — Fetch the latest core and regional filter lists, compile them 
to Apple DNR format baseline JSON files under rules/v<version>/baseline/, 
and run generate_delta.py to produce the version.json and delta_rules.json.

Designed to be executed in GitHub Actions or locally.
"""

import os
import sys
import json
import math
import time
import argparse
import subprocess
import urllib.request
from datetime import datetime, timezone

# 5 Core filter lists and baseline prefixes
CORE_SOURCES = {
    "ads": {
        "url": "https://easylist.to/easylist/easylist.txt",
        "prefix": "ads_net",
        "start_id": 1
    },
    "privacy": {
        "url": "https://easylist.to/easylist/easyprivacy.txt",
        "prefix": "privacy_net",
        "start_id": 1
    },
    "cookie": {
        "url": "https://secure.fanboy.co.nz/fanboy-cookiemonster.txt",
        "prefix": "cookie_net",
        "start_id": 1
    },
    "annoyance": {
        "url": "https://secure.fanboy.co.nz/fanboy-annoyance.txt",
        "prefix": "annoyance_net",
        "start_id": 1
    },
    "social": {
        "url": "https://easylist.to/easylist/fanboy-social.txt",
        "prefix": "social_net",
        "start_id": 1
    }
}

# 22 Regional filter lists
REGIONAL_SOURCES = {
    "vietnamese": "https://abpvn.com/filter/abpvn-FCfc5D.txt",
    "indonesian": "https://easylist-downloads.adblockplus.org/abpindo.txt",
    "china": "https://easylist-downloads.adblockplus.org/easylistchina.txt",
    "korean": "https://cdn.jsdelivr.net/npm/@list-kr/filterslists@latest/dist/filterslist-uBlockOrigin-classic.txt",
    "indian": "https://easylist-downloads.adblockplus.org/indianlist.txt",
    "germany": "https://easylist-downloads.adblockplus.org/easylistgermany.txt",
    "french": "https://easylist-downloads.adblockplus.org/liste_fr.txt",
    "italy": "https://easylist-downloads.adblockplus.org/easylistitaly.txt",
    "spanish": "https://easylist-downloads.adblockplus.org/easylistspanish.txt",
    "dutch": "https://easylist-downloads.adblockplus.org/easylistdutch.txt",
    "portuguese": "https://easylist-downloads.adblockplus.org/easylistportuguese.txt",
    "russian": "https://easylist-downloads.adblockplus.org/ruadlist.txt",
    "polish": "https://easylist-downloads.adblockplus.org/easylistpolish.txt",
    "czech_slovak": "https://raw.githubusercontent.com/tomasko126/easylistczechandslovak/master/filters.txt",
    "latvian": "https://raw.githubusercontent.com/Latvian-List/adblock-latvian/master/lists/latvian-list.txt",
    "lithuanian": "https://raw.githubusercontent.com/EasyList-Lithuania/easylist_lithuania/master/easylistlithuania.txt",
    "bulgarian": "https://raw.githubusercontent.com/KokichaKolevTM/BG-Adblock-list/master/BG-Adblock-list.txt",
    "romanesc": "https://raw.githubusercontent.com/tcptomato/ROad-Block/master/road-block-filters-light.txt",
    "nordic": "https://raw.githubusercontent.com/dandelionsprout/adfilt/master/NorwegianList.txt",
    "arabic": "https://raw.githubusercontent.com/easylist/listear/master/Liste_AR.txt",
    "hebrew": "https://easylist-downloads.adblockplus.org/israellist.txt",
    "japanese": "COMBINED_JAPANESE"
}

# Fixed index mapping to ensure stable regional rule ID ranges matching v1.0.0
REGIONAL_MAPPING = {
    "indonesian": 0,
    "arabic": 1,
    "latvian": 2,
    "bulgarian": 3,
    "china": 4,
    "vietnamese": 5,
    "lithuanian": 6,
    "russian": 7,
    "french": 8,
    "italy": 9,
    "romanesc": 10,
    "indian": 11,
    "czech_slovak": 12,
    "germany": 13,
    "spanish": 14,
    "nordic": 15,
    "portuguese": 16,
    "hebrew": 17,
    "dutch": 18,
    "korean": 19,
    "polish": 20,
    "japanese": 21
}

# DNR Resource Types Mapping
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
    '~third-party': None,
    'first-party': None,
    '~first-party': None
}

def download_file(url, dest_path, retries=3, delay=3):
    """Download a file with retries and a custom User-Agent."""
    print(f"Downloading {url}...")
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (compatible; uShield/1.0; +https://github.com/huykhoi0504/uShield)'}
            )
            with urllib.request.urlopen(req, timeout=45) as response, open(dest_path, 'wb') as out_file:
                out_file.write(response.read())
            
            # Simple line count verification
            with open(dest_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = sum(1 for _ in f)
            print(f"  -> SUCCESS ({lines} lines saved)")
            return True
        except Exception as e:
            print(f"  -> Error downloading (attempt {i+1}/{retries}): {e}")
            if i < retries - 1:
                time.sleep(delay)
    return False

def parse_options(options_str):
    """Parse option parameters in EasyList rule format (after $ symbol)."""
    opts = options_str.split(',')
    resourceTypes = []
    excludedResourceTypes = []
    initiatorDomains = []
    excludedInitiatorDomains = []
    is_third_party = None

    for opt in opts:
        opt = opt.strip()
        if not opt:
            continue
        if opt == 'third-party' or opt == '~first-party':
            is_third_party = True
        elif opt == '~third-party' or opt == 'first-party':
            is_third_party = False
        elif opt.startswith('domain='):
            domains = opt[7:].split('|')
            for d in domains:
                d = d.strip()
                if d.startswith('~'):
                    excludedInitiatorDomains.append(d[1:])
                else:
                    initiatorDomains.append(d)
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
    if initiatorDomains:
        condition['initiatorDomains'] = initiatorDomains
    if excludedInitiatorDomains:
        condition['excludedInitiatorDomains'] = excludedInitiatorDomains

    if is_third_party is True:
        condition['domainType'] = 'thirdParty'
    elif is_third_party is False:
        condition['domainType'] = 'firstParty'

    return condition

def parse_to_dnr(input_file, start_id=1):
    """Convert an EasyList text filter file into a list of DNR rules."""
    rules = []
    current_id = start_id

    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('!') or line.startswith('['):
                continue

            # Skip cosmetic rules (handled by browser element hiding injection)
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

def write_chunks(rules, output_prefix, max_rules_per_file):
    """Chunk the rules list and write to multiple JSON files."""
    total_rules = len(rules)
    chunks = math.ceil(total_rules / max_rules_per_file)
    
    os.makedirs(os.path.dirname(output_prefix), exist_ok=True)
    
    for i in range(chunks):
        chunk_rules = rules[i * max_rules_per_file : (i + 1) * max_rules_per_file]
        file_name = f"{output_prefix}_{i+1}.json"
        
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(chunk_rules, f, separators=(',', ':'))
            
        print(f"  -> Saved {len(chunk_rules)} rules to {os.path.basename(file_name)}")
    
    return chunks

def main():
    parser = argparse.ArgumentParser(description="Create a new baseline rule version for uShield CDN")
    parser.add_argument("--version", required=True, help="Target version string (e.g. 1.0.1 or v1.0.1)")
    parser.add_argument("--max-rules-per-file", type=int, default=30000, 
                        help="Maximum rules per chunked JSON baseline file")
    parser.add_argument("--rules-dir", default="rules", help="Base rules directory")
    args = parser.parse_args()

    # Normalize version string
    version = args.version.strip()
    if not version.startswith('v'):
        version = f"v{version}"
    
    print("=" * 70)
    print(f"Starting uShield version upgrade to {version}")
    print("=" * 70)

    # Establish directories
    version_dir = os.path.abspath(os.path.join(args.rules_dir, version))
    baseline_dir = os.path.join(version_dir, "baseline")
    regional_dir = os.path.join(baseline_dir, "regional")
    
    temp_dir = os.path.abspath("tmp_upgrade")
    
    os.makedirs(baseline_dir, exist_ok=True)
    os.makedirs(regional_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    # Step 1: Download Core lists and process them
    print("\n--- Step 1: Processing Core Filter Lists ---")
    for name, config in CORE_SOURCES.items():
        temp_txt = os.path.join(temp_dir, f"{name}.txt")
        if not download_file(config["url"], temp_txt):
            print(f"CRITICAL ERROR: Failed to download core list {name}. Aborting.")
            sys.exit(1)
        
        print(f"Parsing {name} into DNR rules...")
        rules = parse_to_dnr(temp_txt, start_id=config["start_id"])
        print(f"Found {len(rules)} network rules.")
        
        output_prefix = os.path.join(baseline_dir, config["prefix"])
        write_chunks(rules, output_prefix, args.max_rules_per_file)

    # Step 2: Download and process Regional lists
    print("\n--- Step 2: Processing Regional Filter Lists ---")
    for lang_key, url in REGIONAL_SOURCES.items():
        if lang_key not in REGIONAL_MAPPING:
            print(f"WARNING: No mapping index found for language: {lang_key}. Skipping.")
            continue
            
        index = REGIONAL_MAPPING[lang_key]
        start_id = 10000000 + (index * 50000)
        
        temp_txt = os.path.join(temp_dir, f"regional_{lang_key}.txt")
        if lang_key == "japanese":
            # Dynamically combine Mochi and Fanboy Japanese lists
            mochi_url = "https://raw.githubusercontent.com/eEIi0A5L/adblock_filter/master/mochi_filter.txt"
            fanboy_url = "https://secure.fanboy.co.nz/fanboy-japanese.txt"
            temp_mochi = os.path.join(temp_dir, "mochi_raw.txt")
            temp_fanboy = os.path.join(temp_dir, "fanboy_raw.txt")
            
            print("Downloading and merging combined Japanese filter list (Mochi + Fanboy)...")
            if not download_file(mochi_url, temp_mochi) or not download_file(fanboy_url, temp_fanboy):
                print("WARNING: Failed to download Japanese lists. Skipping.")
                continue
                
            # Merge files
            try:
                with open(temp_txt, 'w', encoding='utf-8') as out_f:
                    out_f.write("! Combined Japanese Filter (Mochi + Fanboy)\n")
                    out_f.write("! Mochi: CC0 1.0 Universal\n")
                    out_f.write("! Fanboy Japanese: CC BY 3.0\n\n")
                    
                    for src in [temp_mochi, temp_fanboy]:
                        with open(src, 'r', encoding='utf-8', errors='ignore') as in_f:
                            out_f.write(in_f.read())
                            out_f.write("\n")
                print("  -> Combined Japanese filter list successfully written.")
            except Exception as e:
                print(f"WARNING: Error combining Japanese lists: {e}")
                continue
        else:
            if not download_file(url, temp_txt):
                print(f"WARNING: Failed to download regional list {lang_key}. Skipping.")
                continue
            
        print(f"Parsing regional list '{lang_key}' with start ID {start_id}...")
        rules = parse_to_dnr(temp_txt, start_id=start_id)
        print(f"Found {len(rules)} network rules.")
        
        if not rules:
            print(f"  -> Skipping output (0 rules extracted)")
            continue
            
        output_prefix = os.path.join(regional_dir, f"regional_{lang_key}")
        write_chunks(rules, output_prefix, args.max_rules_per_file)

    # Step 3: Run generate_delta.py to compute initial delta
    print("\n--- Step 3: Generating Initial Delta & Version Metadata ---")
    delta_url = f"https://uShieldApp.github.io/uShield/rules/{version}/delta_rules.json"
    
    cmd = [
        sys.executable,
        "scripts/generate_delta.py",
        "--baseline-dir", baseline_dir,
        "--output-dir", version_dir,
        "--delta-url", delta_url,
        "--max-delta-rules", "29500"
    ]
    
    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("CRITICAL ERROR generating delta rules:")
        print(result.stderr)
        sys.exit(result.returncode)
    else:
        print(result.stdout)

    # Step 4: Generate static_whitelist.json
    print("\n--- Step 4: Generating Static Whitelist JSON ---")
    cmd_static = [
        sys.executable,
        "scripts/update_static_whitelist.py",
        "--output-dir", version_dir
    ]
    print(f"Executing: {' '.join(cmd_static)}")
    result_static = subprocess.run(cmd_static, capture_output=True, text=True)
    if result_static.returncode != 0:
        print("CRITICAL ERROR generating static whitelist:")
        print(result_static.stderr)
        sys.exit(result_static.returncode)
    else:
        print(result_static.stdout)

    # Clean up temporary directory
    print("\nCleaning up temporary files...")
    for file in os.listdir(temp_dir):
        os.remove(os.path.join(temp_dir, file))
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass

    print(f"\n✅ Version upgrade to {version} completed successfully!")
    print(f"   Baseline path: {baseline_dir}")
    print(f"   Delta output:  {version_dir}/delta_rules.json")
    print(f"   Version spec:  {version_dir}/version.json")

if __name__ == "__main__":
    main()
