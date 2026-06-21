#!/usr/bin/env python3
import json
import argparse
import sys

def parse_notes(notes_str, fallback_msg):
    if not notes_str or not notes_str.strip():
        return [fallback_msg]
    # Tách các patch note bằng dấu gạch đứng '|'
    notes = [note.strip() for note in notes_str.split('|') if note.strip()]
    return notes if notes else [fallback_msg]

def main():
    parser = argparse.ArgumentParser(description="Tự động sinh file app_update.json cho uShield CDN hỗ trợ 8 ngôn ngữ")
    parser.add_argument("--version", required=True, help="Phiên bản mới nhất (ví dụ: 1.2.0)")
    parser.add_argument("--rules-count", type=int, default=1500, help="Số lượng rule chặn quảng cáo được cập nhật")
    parser.add_argument("--force-update", action="store_true", help="Cờ bắt buộc cập nhật ứng dụng")
    
    # 9 ngôn ngữ được hỗ trợ
    parser.add_argument("--patch-notes-en", default="", help="Patch notes bằng tiếng Anh (ngăn cách bởi |)")
    parser.add_argument("--patch-notes-vi", default="", help="Patch notes bằng tiếng Việt (ngăn cách bởi |)")
    parser.add_argument("--patch-notes-de", default="", help="Patch notes bằng tiếng Đức (ngăn cách bởi |)")
    parser.add_argument("--patch-notes-fr", default="", help="Patch notes bằng tiếng Pháp (ngăn cách bởi |)")
    parser.add_argument("--patch-notes-es", default="", help="Patch notes bằng tiếng Tây Ban Nha (ngăn cách bởi |)")
    parser.add_argument("--patch-notes-ru", default="", help="Patch notes bằng tiếng Nga (ngăn cách bởi |)")
    parser.add_argument("--patch-notes-id", default="", help="Patch notes bằng tiếng Indonesia (ngăn cách bởi |)")
    parser.add_argument("--patch-notes-zh-hans", default="", help="Patch notes bằng tiếng Trung giản thể (ngăn cách bởi |)")
    parser.add_argument("--patch-notes-ja", default="", help="Patch notes bằng tiếng Nhật (ngăn cách bởi |)")
    
    args = parser.parse_args()
    
    # Chuẩn hóa số phiên bản (loại bỏ tiền tố 'v' nếu có)
    version = args.version.strip()
    if version.lower().startswith('v'):
        version = version[1:]
        
    # Tạo nội dung patch notes cho từng ngôn ngữ (với fallback phù hợp)
    notes_en = parse_notes(args.patch_notes_en, f"Updated {args.rules_count:,} ad-blocking rules for improved speed and safety.")
    notes_vi = parse_notes(args.patch_notes_vi, f"Cập nhật {args.rules_count:,} bộ lọc quảng cáo mới giúp lướt web nhanh và an toàn hơn.")
    notes_de = parse_notes(args.patch_notes_de, f"Aktualisierte {args.rules_count:,} Werbeblocker-Regeln für schnellere und sicherere Navigation.")
    notes_fr = parse_notes(args.patch_notes_fr, f"Mise à jour de {args.rules_count:,} règles de blocage des publicités pour une navigation plus rapide et plus sûre.")
    notes_es = parse_notes(args.patch_notes_es, f"Se actualizaron {args.rules_count:,} reglas de bloqueo de anuncios para una navegación más rápida y segura.")
    notes_ru = parse_notes(args.patch_notes_ru, f"Обновлено {args.rules_count:,} правил блокировки рекламы для более быстрого и безопасного просмотра.")
    notes_id = parse_notes(args.patch_notes_id, f"Memperbarui {args.rules_count:,} aturan pemblokiran iklan untuk penjelajahan yang lebih cepat dan aman.")
    notes_zh_hans = parse_notes(args.patch_notes_zh_hans, f"更新了 {args.rules_count:,} 条广告拦截规则，以实现更快、更安全的浏览。")
    notes_ja = parse_notes(args.patch_notes_ja, f"より高速で安全なブラウジングのために、{args.rules_count:,}個の広告ブロック規則を更新しました。")
    
    # Tạo cấu trúc dữ liệu JSON cập nhật
    data = {
        "latest_version": version,
        "min_required_version": "1.0.0",
        "store_url": "https://apps.apple.com/app/ushield-browser-adblocker/id6778865496",
        "rules_updated_count": args.rules_count,
        "patch_notes": {
            "en": notes_en,
            "vi": notes_vi,
            "de": notes_de,
            "fr": notes_fr,
            "es": notes_es,
            "ru": notes_ru,
            "id": notes_id,
            "zh-Hans": notes_zh_hans,
            "ja": notes_ja
        },
        "is_force_update": args.force_update
    }
    
    # Ghi file app_update.json ở thư mục hiện tại (thường là root repo uShield_CDN)
    output_file = "app_update.json"
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"✅ Đã tạo thành công {output_file} hỗ trợ 9 ngôn ngữ cho phiên bản {version}")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Lỗi khi ghi file {output_file}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
