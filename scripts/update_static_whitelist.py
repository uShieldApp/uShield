#!/usr/bin/env python3
import os
import json
import urllib.request
import re
import argparse

ALLOWLIST_URL = "https://raw.githubusercontent.com/easylist/easylist/master/easylist/easylist_allowlist.txt"

def escape_regex(text):
    return re.sub(r'([.+?{}()|[\]\\^$])', r'\\\1', text)

def parse_abp_options(options_str):
    opts = {}
    parts = options_str.split(',')
    
    resource_types = []
    if_domains = []
    unless_domains = []
    
    type_map = {
        'script': 'script',
        'image': 'image',
        'stylesheet': 'style-sheet',
        'font': 'font',
        'xmlhttprequest': 'raw',
        'subdocument': 'document',
        'popup': 'popup',
        'media': 'media',
        'object': 'raw',
        'websocket': 'raw',
        'ping': 'raw',
        'other': 'raw',
    }
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        if part.startswith('domain='):
            domain_str = part[7:]
            domains = domain_str.split('|')
            for d in domains:
                d = d.strip()
                if d.startswith('~'):
                    unless_domains.append(d[1:])
                else:
                    if_domains.append(d)
        elif part.startswith('~domain='):
            unless_domains.append(part[8:])
        elif part.startswith('~'):
            pass
        elif part in type_map:
            resource_types.append(type_map[part])
            
    if resource_types:
        opts['resource-type'] = resource_types
    if if_domains:
        opts['if-domain'] = if_domains
    if unless_domains:
        opts['unless-domain'] = unless_domains
        
    return opts

def convert_rule_to_content_blocker(line):
    if not line.startswith('@@'):
        return None
        
    rule_text = line[2:]
    pattern = rule_text
    options = {}
    
    dollar_pos = rule_text.rfind('$')
    if dollar_pos > 0:
        potential_opts = rule_text[dollar_pos + 1:]
        known_keywords = ['script', 'image', 'stylesheet', 'font', 'xmlhttprequest',
                          'subdocument', 'popup', 'media', 'object', 'websocket', 'ping',
                          'third-party', 'first-party', 'domain=', '~domain=', '~script',
                          '~image', '~stylesheet', '~object', '~xmlhttprequest', 'other']
        if any(keyword in potential_opts for keyword in known_keywords):
            pattern = rule_text[:dollar_pos]
            options = parse_abp_options(potential_opts)
            
    url_filter = pattern
    raw_pattern = pattern
    
    if url_filter.startswith('||'):
        url_filter = url_filter[2:]
        url_filter = escape_regex(url_filter)
        url_filter = url_filter.replace('\\*', '.*')
        url_filter = '^[^:]+:(//)?([^/]+\\.)?' + url_filter
    elif url_filter.startswith('|'):
        url_filter = url_filter[1:]
        url_filter = escape_regex(url_filter)
        url_filter = url_filter.replace('\\*', '.*')
        url_filter = '^' + url_filter
    else:
        url_filter = escape_regex(url_filter)
        url_filter = url_filter.replace('\\*', '.*')
        
    if url_filter.endswith('\\|'):
        url_filter = url_filter[:-2] + '$'
        
    url_filter = url_filter.replace('\\^', '[/:?&=]')
    
    rule_domains = []
    if 'if-domain' in options:
        rule_domains = [d for d in options['if-domain']]
        
    rule = {
        "action": {
            "type": "ignore-previous-rules"
        },
        "trigger": {
            "url-filter": url_filter
        }
    }
    
    if 'resource-type' in options:
        rule['trigger']['resource-type'] = options['resource-type']
    if 'if-domain' in options:
        rule['trigger']['if-domain'] = options['if-domain']
    if 'unless-domain' in options:
        rule['trigger']['unless-domain'] = options['unless-domain']
        
    if raw_pattern:
        rule['urlFilter'] = raw_pattern
    if rule_domains:
        rule['domains'] = rule_domains
        
    return rule

def main():
    parser = argparse.ArgumentParser(description="Create static whitelist JSON for uShield CDN")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    print(f"Fetching allowlist from {ALLOWLIST_URL}...")
    try:
        req = urllib.request.Request(ALLOWLIST_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching url: {e}")
        return

    lines = content.splitlines()
    rules = []
    
    for line in lines:
        line = line.strip()
        if not line.startswith("@@"):
            continue
            
        rule = convert_rule_to_content_blocker(line)
        if rule:
            rules.append(rule)
            
    # Guarantee fallback domains
    fallback_domains = ["google.com", "google.com.vn", "paypal.com"]
    for fd in fallback_domains:
        has_simple_rule = False
        for r in rules:
            if r.get('urlFilter') == f"||{fd}^" and 'resource-type' not in r['trigger'] and 'if-domain' not in r['trigger']:
                has_simple_rule = True
                break
        if not has_simple_rule:
            fd_escaped = fd.replace('.', r'\.')
            rules.append({
                "action": {
                    "type": "ignore-previous-rules"
                },
                "trigger": {
                    "url-filter": f"^[^:]+:(//)?([^/]+\\.)?{fd_escaped}[/:?&=]"
                },
                "urlFilter": f"||{fd}^",
                "domains": [fd]
            })
            
    print(f"Parsed {len(rules)} whitelist rules.")
    
    output_path = os.path.join(args.output_dir, "static_whitelist.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)
    print(f"Saved static whitelist to {output_path}")

if __name__ == "__main__":
    main()
