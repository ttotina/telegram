import time
import random
import asyncio
from telethon import events
from deep_translator import GoogleTranslator
from langdetect import detect

from config import PHOTOS, VIDEOS
from database import get_random_response, get_all_settings

# --- Configurable runtime params ---
SEMAPHORE_LIMIT = 10
MAX_PHOTOS_PER_USER = 2
INACTIVITY_INTERVAL = 3600
INACTIVITY_MAX = 2

# --- State Management ---
user_states_by_account = {}

# --- Utility functions ---
SUPPORTED_LANGS = [
    'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh-cn', 
    'ar', 'hi', 'bn', 'id', 'tr', 'vi', 'th', 'nl', 'pl', 'sv'
]

def detect_lang(text: str) -> str:
    try:
        if len(text.strip()) < 4:
            return "en"
        return detect(text) or "en"
    except Exception:
        return "en"

def translate(text: str, dest: str) -> str:
    if not dest or dest not in SUPPORTED_LANGS: return text
    try:
        if len(text.strip()) < 4:
            return text
        return GoogleTranslator(source='auto', target=dest).translate(text)
    except Exception as e:
        print(f"ERROR: Translation failed. Details: {e}")
        return text

async def typing_sleep(client, chat_id, min_s=2, max_s=5):
    try:
        async with client.action(chat_id, "typing"): await asyncio.sleep(random.uniform(min_s, max_s))
    except Exception: await asyncio.sleep(random.uniform(min_s, max_s))

# --- Step implementations ---
async def do_step0(client, phone, chat_id, lang, my_name, user_name, settings):
    account_state = user_states_by_account.setdefault(phone, {"sem": asyncio.Semaphore(SEMAPHORE_LIMIT), "chats": {}})
    user_states = account_state["chats"]
    
    msg1_list = settings.get('step0_msgs_1', '').splitlines()
    msg2_list = settings.get('step0_msgs_2', '').splitlines()

    if msg1_list:
        msg1 = random.choice(msg1_list).format(my_name=my_name)
        await typing_sleep(client, chat_id, 2, 5)
        await client.send_message(chat_id, translate(msg1, lang))
    
    if msg2_list:
        msg2 = random.choice(msg2_list).format(user_name=user_name)
        await typing_sleep(client, chat_id, 2, 5)
        await client.send_message(chat_id, translate(msg2, lang))

    st = user_states.setdefault(chat_id, {})
    st.update({
        "step": 0, "last_active": time.time(), "photo_sent": 0,
        "msg_after_step2": 0, "inactivity_sent": 0, "lang": lang
    })

async def do_step1(client, phone, chat_id, lang, settings):
    account_state = user_states_by_account.setdefault(phone, {"sem": asyncio.Semaphore(SEMAPHORE_LIMIT), "chats": {}})
    user_states = account_state["chats"]
    st = user_states.setdefault(chat_id, {})
    media_list = PHOTOS + VIDEOS
    if media_list and st.get("photo_sent", 0) < MAX_PHOTOS_PER_USER:
        media = random.choice(media_list)
        try:
            await typing_sleep(client, chat_id, 3, 6)
            await client.send_file(chat_id, media)
            st["photo_sent"] = st.get("photo_sent", 0) + 1
        except Exception: pass

    tease_list = settings.get('step1_msgs', '').splitlines()
    if tease_list:
        tease = random.choice(tease_list)
        await typing_sleep(client, chat_id, 2, 4)
        await client.send_message(chat_id, translate(tease, lang))

    st["step"] = 1
    st["last_active"] = time.time()

async def do_step2(client, phone, chat_id, lang, settings):
    account_state = user_states_by_account.setdefault(phone, {"sem": asyncio.Semaphore(SEMAPHORE_LIMIT), "chats": {}})
    user_states = account_state["chats"]
    st = user_states.setdefault(chat_id, {})
    
    msg_list = settings.get('step2_msg', '').splitlines()
    if msg_list:
        msg = random.choice(msg_list)
        await typing_sleep(client, chat_id, 4, 7)
        await client.send_message(chat_id, translate(msg, lang))

    await asyncio.sleep(1)
    cpa_links = settings.get('cpa_links', '').splitlines()
    if cpa_links:
        cpa_link = random.choice(cpa_links)
        await client.send_message(chat_id, cpa_link)
    st["step"] = 2
    st["last_active"] = time.time()
    st["msg_after_step2"] = 0

# --- Schedule helpers ---
async def schedule_step1_if_no_reply(client, phone, chat_id, delay, settings):
    await asyncio.sleep(delay)
    account_state = user_states_by_account.get(phone)
    if not account_state: return
    st = account_state["chats"].get(chat_id)
    if st and st.get("step") == 0: await do_step1(client, phone, chat_id, st.get("lang", "en"), settings)

async def schedule_step2_if_no_reply(client, phone, chat_id, delay, settings):
    await asyncio.sleep(delay)
    account_state = user_states_by_account.get(phone)
    if not account_state: return
    st = account_state["chats"].get(chat_id)
    if st and st.get("step") == 1: await do_step2(client, phone, chat_id, st.get("lang", "en"), settings)

# --- Database-based reply ---
async def handle_user_reply(client, phone, chat_id, user_text, lang, settings):
    account_state = user_states_by_account.setdefault(phone, {"sem": asyncio.Semaphore(SEMAPHORE_LIMIT), "chats": {}})
    user_states = account_state["chats"]
    st = user_states.setdefault(chat_id, {})
    async with account_state["sem"]:
        translated_text = await asyncio.to_thread(translate, user_text, 'en')
        reply = await asyncio.to_thread(get_random_response, translated_text)
        if not reply:
            fallback_msgs = settings.get('fallback_msgs', '').splitlines()
            if fallback_msgs:
                reply = random.choice(fallback_msgs)
            else:
                reply = random.choice(["mmh 😏", "so hot...", "u make me wet 💦", "bad boy 😉"])

        out = translate(reply, lang)
        await typing_sleep(client, chat_id, 1, 3)
        try: await client.send_message(chat_id, out)
        except Exception: pass

        if random.random() < 0.30:
            await asyncio.sleep(0.6)
            cpa_links = settings.get('cpa_links', '').splitlines()
            if cpa_links:
                cpa_link = random.choice(cpa_links)
                try: await client.send_message(chat_id, cpa_link)
                except Exception: pass

        st["msg_after_step2"] = st.get("msg_after_step2", 0) + 1
        st["last_active"] = time.time()
        if st.get("photo_sent", 0) < MAX_PHOTOS_PER_USER:
            min_interval = int(settings.get('media_interval_min', 2))
            max_interval = int(settings.get('media_interval_max', 4))
            interval = random.randint(min_interval, max_interval)
            if interval > 0 and st["msg_after_step2"] % interval == 0:
                media_list = PHOTOS + VIDEOS
                if media_list:
                    media = random.choice(media_list)
                    try:
                        await typing_sleep(client, chat_id, 2, 4)
                        await client.send_file(chat_id, media)
                        await asyncio.sleep(0.8)
                        cpa_links = settings.get('cpa_links', '').splitlines()
                        if cpa_links:
                            cpa_link = random.choice(cpa_links)
                            await client.send_message(chat_id, cpa_link)
                        st["photo_sent"] = st.get("photo_sent", 0) + 1
                    except Exception: pass

# --- Inactivity checker ---
async def inactivity_loop(client):
    phone = client.session.filename.split('/')[-1].split('.')[0]
    account_state = user_states_by_account.setdefault(phone, {"sem": asyncio.Semaphore(SEMAPHORE_LIMIT), "chats": {}})
    user_states = account_state["chats"]
    while True:
        now = time.time()
        for chat_id, st in list(user_states.items()):
            if st.get("step", -1) >= 2:
                last = st.get("last_active", now)
                sent = st.get("inactivity_sent", 0)
                if sent < INACTIVITY_MAX and (now - last) > INACTIVITY_INTERVAL:
                    try:
                        msg = translate("Hey babe, still there? 😏", st.get("lang", "en"))
                        await client.send_message(chat_id, msg)
                        st["inactivity_sent"] = sent + 1
                        st["last_active"] = time.time()
                    except Exception: pass
        await asyncio.sleep(60)

# --- Main Event Handler ---
async def handler(event):
    client = event.client
    phone = client.session.filename.split('/')[-1].split('.')[0]
    account_state = user_states_by_account.setdefault(phone, {"sem": asyncio.Semaphore(SEMAPHORE_LIMIT), "chats": {}})
    user_states = account_state["chats"]
    settings = await asyncio.to_thread(get_all_settings)

    if event.is_group or event.is_channel: return
        
    chat_id = event.chat_id
    sender = await event.get_sender()
    try:
        await client.send_read_acknowledge(chat_id, message=event.message)
    except Exception:
        pass
    user_name = (sender.first_name or "there")
    text = (event.raw_text or "")
    lang = detect_lang(text) if text else "en"
    
    st = user_states.setdefault(chat_id, {
        "step": -1, "photo_sent": 0, "msg_after_step2": 0,
        "last_active": time.time(), "inactivity_sent": 0, "lang": lang
    })
    st["last_active"] = time.time()
    st["lang"] = lang

    me = await client.get_me()
    my_name = me.first_name or "Me"

    if settings.get('flow_enabled', 'true') == 'false' and st["step"] == -1:
        st["step"] = 2

    if st["step"] == -1:
        await do_step0(client, phone, chat_id, lang, my_name, user_name, settings)
        asyncio.create_task(schedule_step1_if_no_reply(client, phone, chat_id, 90, settings))
        return
    if st["step"] == 0:
        await do_step1(client, phone, chat_id, lang, settings)
        asyncio.create_task(schedule_step2_if_no_reply(client, phone, chat_id, 120, settings))
        return
    if st["step"] == 1:
        await do_step2(client, phone, chat_id, lang, settings)
        return
    if st["step"] >= 2:
        asyncio.create_task(handle_user_reply(client, phone, chat_id, text, lang, settings))
        return

def register_handlers(client_instance):
    client_instance.add_event_handler(handler, events.NewMessage(incoming=True))
