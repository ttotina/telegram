import os
import asyncio
from aiohttp import web
import aiohttp_jinja2
import jinja2

from config import API_ID, API_HASH
import account_manager
from database import (
    get_all_keywords_and_responses, add_keyword_with_responses, delete_keyword,
    get_all_settings, update_settings
)

# --- Path Definitions ---
BASE_DIR = os.path.dirname(__file__)
MEDIA_DIR = os.path.join(BASE_DIR, 'media')
os.makedirs(MEDIA_DIR, exist_ok=True)

# --- Route Handlers ---

@aiohttp_jinja2.template('index.html')
async def index(request):
    accounts = account_manager.get_all_accounts_status()
    image_files = [f for f in os.listdir(MEDIA_DIR) if os.path.isfile(os.path.join(MEDIA_DIR, f))]
    return {
        'accounts': accounts,
        'images': image_files,
        'request': request # Pass the request object
    }

@aiohttp_jinja2.template('keywords.html')
async def keywords_get(request):
    keywords_data = await asyncio.to_thread(get_all_keywords_and_responses)
    return {
        'keywords_data': keywords_data,
        'request': request # Pass the request object
    }

# --- Settings Handlers ---
@aiohttp_jinja2.template('settings.html')
async def settings_get(request):
    settings = await asyncio.to_thread(get_all_settings)
    return {'settings': settings}

async def settings_post(request):
    data = await request.post()
    flow_enabled = 'true' if 'flow_enabled' in data else 'false'
    
    new_settings = {
        'flow_enabled': flow_enabled,
        'media_interval_min': data.get('media_interval_min', '2'),
        'media_interval_max': data.get('media_interval_max', '4'),
        'step0_msgs_1': data.get('step0_msgs_1', ''),
        'step0_msgs_2': data.get('step0_msgs_2', ''),
        'step1_msgs': data.get('step1_msgs', ''),
        'step2_msg': data.get('step2_msg', ''),
        'fallback_msgs': data.get('fallback_msgs', ''),
        'cpa_links': data.get('cpa_links', ''),
    }
    await asyncio.to_thread(update_settings, new_settings)
    return web.HTTPFound('/settings')

# --- Account Handlers ---
@aiohttp_jinja2.template('verify.html')
async def verify_get(request):
    phone = request.query.get('phone')
    if phone:
        phone = phone.strip()
        if not phone.startswith('+'):
            phone = '+' + phone
    error = request.query.get('error')
    
    stage_from_url = request.query.get('stage')

    status_list = account_manager.get_all_accounts_status()
    current_account_status = next((acc for acc in status_list if acc['phone'] == phone and acc.get('is_pending')), None)

    stage = "error" # Default to error if not found
    if stage_from_url:
        stage = stage_from_url
    elif current_account_status:
        stage = current_account_status.get('stage', 'code')
    else:
        stage = "error"
        error = error or "Login session expired or not initiated. Please try adding the account again from the dashboard."
    
    phone_code_hash_to_pass = account_manager.PENDING_CLIENTS.get(phone, {}).get('phone_code_hash')

    return {
        "phone": phone,
        "stage": stage,
        "error": error,
        "phone_code_hash": phone_code_hash_to_pass
    }

async def add_account_post(request):
    data = await request.post()
    phone = data.get('phone')
    if not phone: return web.HTTPFound('/')

    result = await account_manager.add_account(phone, API_ID, API_HASH)
    
    if result['status'] == 'code_required':
        return web.HTTPFound(f"/verify?phone={phone}")
    elif result['status'] == 'already_authorized':
        return web.HTTPFound('/') # Redirect to home if already authorized
    else:
        # Redirect to verify page with error message
        return web.HTTPFound(f"/verify?phone={phone}&error={result.get('message', 'Failed to add account.')}")

async def verify_code_post(request):
    data = await request.post()
    phone = data.get('phone')
    code = data.get('code')
    phone_code_hash = data.get('phone_code_hash') # Get phone_code_hash from form
    
    result = await account_manager.verify_code(phone, code, phone_code_hash)
    if result['status'] == 'success':
        return web.HTTPFound('/')
    elif result['status'] == 'password_required':
        return web.HTTPFound(f"/verify?phone={phone}&stage=password")
    else:
        return web.HTTPFound(f"/verify?phone={phone}&phone_code_hash={phone_code_hash}&error={result.get('message', 'Invalid code.')}")

async def verify_password_post(request):
    data = await request.post()
    phone = data.get('phone')
    password = data.get('password')
    
    result = await account_manager.verify_password(phone, password)
    if result['status'] == 'success':
        return web.HTTPFound('/')
    elif result['status'] == 'error':
        return web.HTTPFound(f"/verify?phone={phone}&stage=password&error={result.get('message', 'Incorrect password.')}")
    return web.HTTPFound('/')

async def remove_account_post(request):
    data = await request.post()
    phone = data.get('phone')
    if phone: await account_manager.remove_account(phone)
    return web.HTTPFound('/')

# --- Keyword and Media handlers ---
async def add_keyword(request):
    data = await request.post()
    keyword = data.get('keyword')
    responses = data.get('responses')
    if keyword and responses:
        response_list = [r.strip() for r in responses.splitlines() if r.strip()]
        if response_list: await asyncio.to_thread(add_keyword_with_responses, keyword, response_list)
    return web.HTTPFound('/keywords')

async def delete_keyword_handler(request):
    data = await request.post()
    keyword_id = data.get('keyword_id')
    if keyword_id: await asyncio.to_thread(delete_keyword, int(keyword_id))
    return web.HTTPFound('/keywords')

async def upload_media(request):
    data = await request.post()
    photo = data.get('photo')
    if photo and photo.file:
        filename = os.path.basename(photo.filename)
        filepath = os.path.join(MEDIA_DIR, filename)
        with open(filepath, 'wb') as f: f.write(photo.file.read())
    return web.HTTPFound('/')

async def delete_media(request):
    data = await request.post()
    filename = data.get('filename')
    if filename:
        filepath = os.path.join(MEDIA_DIR, os.path.basename(filename))
        if os.path.exists(filepath): os.remove(filepath)
    return web.HTTPFound('/')

# --- Application Setup ---
def setup_routes(app):
    app.router.add_get('/', index)
    # Keywords
    app.router.add_get('/keywords', keywords_get)
    app.router.add_post('/add_keyword', add_keyword)
    app.router.add_post('/delete_keyword', delete_keyword_handler)
    # Settings
    app.router.add_get('/settings', settings_get)
    app.router.add_post('/settings', settings_post)
    # Account routes
    app.router.add_post('/add_account', add_account_post)
    app.router.add_get('/verify', verify_get)
    app.router.add_post('/verify_code', verify_code_post)
    app.router.add_post('/verify_password', verify_password_post)
    app.router.add_post('/remove_account', remove_account_post)
    # Media routes
    app.router.add_post('/upload', upload_media)
    app.router.add_post('/delete_media', delete_media)
    # Static files
    app.router.add_static('/media', MEDIA_DIR)
    app.router.add_static('/static', os.path.join(BASE_DIR, 'static'))

def create_app():
    app = web.Application()
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(os.path.join(BASE_DIR, 'templates')))
    setup_routes(app)
    return app
