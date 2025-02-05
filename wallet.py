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

# Создание транзакции
def create_transaction(sender, recipient, amount, fee, private_key):
    transaction = {
        "sender": sender,
        "recipient": recipient,
        "amount": amount,
        "fee": fee,
        "public_key": private_key.verifying_key.to_string().hex()
    }
    message = f"{sender}{recipient}{amount}{fee}".encode()
    transaction["signature"] = private_key.sign(message).hex()
    return transaction

# Отправка транзакции на сервер
def send_transaction(transaction):
    response = requests.post("http://localhost:5000/transaction", json=transaction)
    return response.json()

# Получение баланса
def get_balance(address):
    response = requests.get("http://localhost:5000/chain")
    if response.status_code != 200:
        return 0
    chain = response.json()
    balance = 0
    for block in chain:
        for tx in block["transactions"]:
            if tx["sender"] == address:
                balance -= tx["amount"] + tx["fee"]
            if tx["recipient"] == address:
                balance += tx["amount"]
    return balance

# Отображение транзакций
def get_transactions(address):
    response = requests.get("http://localhost:5000/chain")
    if response.status_code != 200:
        return []
    chain = response.json()
    transactions = []
    for block in chain:
        for tx in block["transactions"]:
            if tx["sender"] == address or tx["recipient"] == address:
                transactions.append(tx)
    return transactions

if __name__ == '__main__':
    private_key, public_key = load_or_generate_keys()
    wallet_address = public_key.to_string().hex()
    print(f"Wallet address: {wallet_address}")

    while True:
        print("\n=== Wallet Menu ===")
        print("1. View Balance")
        print("2. View Transactions")
        print("3. Send Transaction")
        print("4. Exit")
        choice = input("Enter your choice: ")

        if choice == "1":
            balance = get_balance(wallet_address)
            print(f"Your balance: {balance}")

        elif choice == "2":
            transactions = get_transactions(wallet_address)
            print("Your transactions:")
            for tx in transactions:
                print(tx)

        elif choice == "3":
            recipient = input("Recipient address: ")
            amount = int(input("Amount: "))
            fee = int(input("Fee: "))
            transaction = create_transaction(wallet_address, recipient, amount, fee, private_key)
            result = send_transaction(transaction)
            print("Transaction result:", result)

        elif choice == "4":
            break