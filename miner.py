import requests
import hashlib
import json
from time import time
from ecdsa import SigningKey, SECP256k1
import os

# Путь к файлу с ключами
KEYS_FILE = "wallet_keys.json"

# Генерация или загрузка ключей
def load_or_generate_keys():
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, "r") as f:
            keys = json.load(f)
            private_key = SigningKey.from_string(bytes.fromhex(keys["private_key"]), curve=SECP256k1)
            public_key = private_key.verifying_key
    else:
        private_key = SigningKey.generate(curve=SECP256k1)
        public_key = private_key.verifying_key
        keys = {
            "private_key": private_key.to_string().hex(),
            "public_key": public_key.to_string().hex()
        }
        with open(KEYS_FILE, "w") as f:
            json.dump(keys, f)
    return private_key, public_key

# Функция хэширования
def calculate_hash(index, timestamp, transactions, previous_hash, nonce):
    block_string = f"{index}{timestamp}{json.dumps(transactions)}{previous_hash}{nonce}"
    return hashlib.sha256(block_string.encode()).hexdigest()

# Получение последнего блока
def get_last_block():
    response = requests.get("http://localhost:5000/chain")
    if response.status_code == 200:
        chain = response.json()
        return chain[-1] if chain else None
    return None

# Получение транзакций из пула
def get_transactions():
    response = requests.get("http://localhost:5000/transactions")
    return response.json() if response.status_code == 200 else []

# Получение текущей сложности
def get_difficulty():
    difficulty_response = requests.get("http://localhost:5000/difficulty")
    return difficulty_response.json()["difficulty"]

# Майнинг нового блока
def mine_block(miner_address):
    last_block = get_last_block()
    index = last_block["index"] + 1 if last_block else 0
    previous_hash = last_block["hash"] if last_block else "0"
    timestamp = str(time())
    nonce = 0

    # Получение транзакций из пула
    transactions = get_transactions()

    # Получение текущей сложности
    difficulty = get_difficulty()

    while True:
        # Рассчитываем хэш с сериализованными транзакциями
        hash = calculate_hash(index, timestamp, json.dumps(transactions), previous_hash, nonce)
        if hash.startswith("0" * difficulty):
            break
        nonce += 1
    # Отправка блока на сервер
    block_data = {
        "index": index,
        "timestamp": timestamp,
        "transactions": transactions,
        "previous_hash": previous_hash,
        "nonce": nonce,
        "hash": hash,
        "miner_address": miner_address
    }
    response = requests.post("http://localhost:5000/mine", json=block_data)
    return response.json()

if __name__ == '__main__':
    # Загрузка ключей минера
    private_key, public_key = load_or_generate_keys()
    miner_address = public_key.to_string().hex()

    print(f"Miner address: {miner_address}")

    while True:
        result = mine_block(miner_address)
        print("Mining result:", result)