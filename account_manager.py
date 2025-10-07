import os
import asyncio
from telethon import TelegramClient, errors

from userbot import register_handlers, inactivity_loop

# This dictionary will hold all active client instances and their tasks
# Format: { 'phone_number': { 'client': client_instance, 'task': background_task } }
ACCOUNTS = {}

# This dictionary will temporarily hold client instances during the login process
# { 'phone_number': { 'client': client_instance, 'phone_code_hash': hash } }
PENDING_CLIENTS = {}

SESSION_DIR = os.path.join(os.path.dirname(__file__), "sessions")
os.makedirs(SESSION_DIR, exist_ok=True)

def get_session_path(phone):
    return os.path.join(SESSION_DIR, f"{phone}.session")

async def start_bot_for_client(client_instance):
    """Registers handlers and starts background tasks for a single client."""
    register_handlers(client_instance)
    task = asyncio.create_task(inactivity_loop(client_instance))
    return task

async def add_account(phone, api_id, api_hash):
    session_path = get_session_path(phone)
    client = TelegramClient(session_path, api_id, api_hash)
    
    try:
        await client.connect()

        if not await client.is_user_authorized():
            PENDING_CLIENTS[phone] = {"client": client}
            sent_code = await client.send_code_request(phone)
            PENDING_CLIENTS[phone]["phone_code_hash"] = sent_code.phone_code_hash
            return {"status": "code_required", "phone_code_hash": sent_code.phone_code_hash}
        else:
            # Account is already authorized, start services immediately
            task = await start_bot_for_client(client)
            ACCOUNTS[phone] = {"client": client, "task": task}
            print(f"Account {phone} already authorized and started.")
            return {"status": "already_authorized"}
    except Exception as e:
        print(f"Error adding account {phone}: {e}")
        # Ensure client is disconnected if an error occurs during initial connect/send_code_request
        if client.is_connected():
            await client.disconnect()
        # Clean up session file if it was created and login failed
        if os.path.exists(session_path): os.remove(session_path)
        return {"status": "error", "message": str(e)}

async def verify_code(phone, code, phone_code_hash):
    """Verifies the login code."""
    if phone not in PENDING_CLIENTS:
        return {"status": "error", "message": "Login session expired or not initiated."}

    client = PENDING_CLIENTS[phone]["client"]
    # Ensure the client is connected before attempting sign_in
    if not client.is_connected():
        try:
            await client.connect()
        except Exception as e:
            print(f"Error reconnecting client for {phone}: {e}")
            return {"status": "error", "message": f"Failed to reconnect client: {e}"}

    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        # On success, move client from PENDING to ACCOUNTS
        task = await start_bot_for_client(client)
        ACCOUNTS[phone] = {"client": client, "task": task}
        PENDING_CLIENTS.pop(phone, None) # Clean up pending client
        print(f"Account {phone} added successfully.")
        return {"status": "success"}
    except errors.rpcerrorlist.SessionPasswordNeededError:
        return {"status": "password_required"}
    except Exception as e:
        print(f"Error verifying code for {phone}: {e}")
        # Disconnect client on error to allow a clean retry
        if client.is_connected():
            await client.disconnect()
        PENDING_CLIENTS.pop(phone, None) # Clean up pending client on definitive error
        return {"status": "error", "message": str(e)}

async def verify_password(phone, password):
    """Verifies the 2FA password."""
    # Client should be in PENDING_CLIENTS if password was required after code
    if phone not in PENDING_CLIENTS:
        return {"status": "error", "message": "Login session expired or not initiated for password."}

    client = PENDING_CLIENTS[phone]["client"]
    # Ensure the client is connected before attempting sign_in
    if not client.is_connected():
        try:
            await client.connect()
        except Exception as e:
            print(f"Error reconnecting client for {phone}: {e}")
            return {"status": "error", "message": f"Failed to reconnect client: {e}"}

    try:
        await client.sign_in(password=password)
        # On success, move client from PENDING to ACCOUNTS
        task = await start_bot_for_client(client)
        ACCOUNTS[phone] = {"client": client, "task": task}
        PENDING_CLIENTS.pop(phone, None) # Clean up pending client
        print(f"Account {phone} added successfully after 2FA.")
        return {"status": "success"}
    except Exception as e:
        print(f"Error verifying password for {phone}: {e}")
        # Disconnect client on error to allow a clean retry
        if client.is_connected():
            await client.disconnect()
        PENDING_CLIENTS.pop(phone, None) # Clean up pending client on definitive error
        return {"status": "error", "message": str(e)}

async def remove_account(phone):
    """Stops and logs out a single account without affecting others."""
    # Check in ACCOUNTS (active clients)
    if phone in ACCOUNTS:
        account = ACCOUNTS.pop(phone)
        client = account['client']
        task = account['task']
        
        if task: task.cancel()
        if client.is_connected(): await client.log_out()
        
        session_path = get_session_path(phone)
        if os.path.exists(session_path): os.remove(session_path)
            
        print(f"Account {phone} has been removed.")
        return True
    
    # Also check in PENDING_CLIENTS (if login was not completed)
    if phone in PENDING_CLIENTS:
        client = PENDING_CLIENTS.pop(phone)['client']
        if client.is_connected(): await client.disconnect()
        session_path = get_session_path(phone)
        if os.path.exists(session_path): os.remove(session_path)
        print(f"Pending login for {phone} has been cleared.")
        return True

    return False

async def start_existing_sessions(api_id, api_hash):
    """Scans for session files and starts a client for each one."""
    session_files = [f for f in os.listdir(SESSION_DIR) if f.endswith('.session')]
    for session_file in session_files:
        phone = os.path.splitext(session_file)[0]
        print(f"Found existing session for {phone}. Starting...")
        session_path = get_session_path(phone)
        client = TelegramClient(session_path, api_id, api_hash)
        
        try:
            await client.connect()
            if await client.is_user_authorized():
                task = await start_bot_for_client(client)
                ACCOUNTS[phone] = {"client": client, "task": task}
                print(f"Successfully started client for {phone}.")
            else:
                print(f"Session for {phone} is invalid. Deleting.")
                # Ensure client is disconnected before deleting session file
                if client.is_connected(): await client.disconnect()
                os.remove(session_path)
        except Exception as e:
            print(f"Could not start session for {phone}: {e}. Deleting session file.")
            # Ensure client is disconnected if an error occurs
            if client.is_connected():
                await client.disconnect()
            if os.path.exists(session_path):
                os.remove(session_path)

def get_all_accounts_status():
    """Returns a list of all managed accounts and their connection status."""
    status_list = []
    for phone, account_data in ACCOUNTS.items():
        status_list.append({
            "phone": phone,
            "is_connected": account_data['client'].is_connected(),
            "is_pending": False
        })
    # Also include pending clients (those waiting for code/password) in the status list
    for phone, pending_data in PENDING_CLIENTS.items():
        status_list.append({
            "phone": phone,
            "is_connected": False, 
            "is_pending": True,
            "stage": "code" # Assume code is pending if in PENDING_CLIENTS
        })
    return status_list