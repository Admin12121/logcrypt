import os
import hashlib
import base64
import secrets
import mysql.connector
from hashlib import pbkdf2_hmac
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from decouple import config

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user=config("DB_USER", default="grooot"),
        password=config("DB_PASS", default="grooot"),
        database=config("DB_NAME", default="grooot")
    )

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_salt(length: int = 16) -> bytes:
    return secrets.token_bytes(length)

def derive_aes_key(password: str, salt: bytes, iterations: int = 100_000) -> bytes:
    return pbkdf2_hmac('sha256', password.encode(), salt, iterations, dklen=32)

def create_user(username: str, password: str):
    try:
        conn = get_db_connection()
        password_hash = hash_password(password)
        kdf_salt = generate_salt()

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, kdf_salt) VALUES (%s, %s, %s)",
            (username, password_hash, kdf_salt)
        )
        conn.commit()
        cursor.close()
        conn.close()

        print("\n✅ User created successfully.")
    except Exception as e:
        print(f"\n❌ Error creating user: {e}")

def generate_data_key() -> bytes:
    return secrets.token_bytes(32)

def encrypt_data_key(data_key: bytes, user_key: bytes) -> str:
    iv = secrets.token_bytes(16)
    cipher = AES.new(user_key, AES.MODE_CBC, iv)
    enc_key = cipher.encrypt(pad(data_key, AES.block_size))
    return base64.b64encode(iv + enc_key).decode()

def decrypt_data_key(enc_key_b64: str, user_key: bytes) -> bytes:
    raw = base64.b64decode(enc_key_b64)
    iv, enc_key = raw[:16], raw[16:]
    cipher = AES.new(user_key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(enc_key), AES.block_size)

def encrypt_data(data: str, data_key: bytes) -> str:
    iv = secrets.token_bytes(16)
    cipher = AES.new(data_key, AES.MODE_CBC, iv)
    ciphertext = cipher.encrypt(pad(data.encode(), AES.block_size))
    return base64.b64encode(iv + ciphertext).decode()

def decrypt_data(enc_data_b64: str, data_key: bytes) -> str:
    raw = base64.b64decode(enc_data_b64)
    iv, ciphertext = raw[:16], raw[16:]
    cipher = AES.new(data_key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ciphertext), AES.block_size).decode() 