from flask import Flask, request, jsonify, render_template
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import hashlib
import json
from time import time
from ecdsa import VerifyingKey, SECP256k1

app = Flask(__name__)

# База данных
DATABASE_URL = "sqlite:///blockchain.db"
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# Модель блока
class Block(Base):
    __tablename__ = 'blocks'
    id = Column(Integer, primary_key=True)
    index = Column(Integer)
    timestamp = Column(String)
    transactions = Column(Text)  # Транзакции в формате JSON
    previous_hash = Column(String)
    hash = Column(String)
    nonce = Column(Integer)

# Модель транзакции (пул транзакций)
class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    sender = Column(String)
    recipient = Column(String)
    amount = Column(Integer)
    fee = Column(Integer)  # Комиссия
    public_key = Column(String)
    signature = Column(String)

Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# Глобальные переменные
DIFFICULTY = 4  # Количество нулей в начале хэша
BLOCK_TIME = 10  # Целевое время создания блока в секундах
MINER_REWARD = 50  # Награда майнеру

# Функция хэширования
def calculate_hash(index, timestamp, transactions, previous_hash, nonce):
    block_string = f"{index}{timestamp}{json.dumps(transactions)}{previous_hash}{nonce}"
    return hashlib.sha256(block_string.encode()).hexdigest()

# Получение последнего блока
def get_last_block():
    return session.query(Block).order_by(Block.index.desc()).first()

# Добавление нового блока
def add_block(index, timestamp, transactions, previous_hash, nonce, hash):
    new_block = Block(
        index=index,
        timestamp=timestamp,
        transactions=json.dumps(transactions),
        previous_hash=previous_hash,
        nonce=nonce,
        hash=hash
    )
    session.add(new_block)
    session.commit()

# Обновление сложности
def update_difficulty():
    last_block = get_last_block()
    if not last_block:
        return DIFFICULTY
    blocks = session.query(Block).order_by(Block.index.desc()).limit(10).all()
    if len(blocks) < 10:
        return DIFFICULTY
    first_block_time = float(blocks[-1].timestamp)
    last_block_time = float(blocks[0].timestamp)
    actual_time = last_block_time - first_block_time
    target_time = BLOCK_TIME * 10
    if actual_time < target_time:
        return DIFFICULTY + 1
    elif actual_time > target_time:
        return max(1, DIFFICULTY - 1)
    return DIFFICULTY

# Роут для главной страницы
@app.route('/', methods=['GET'])
def index():
    # Получение пула транзакций
    transactions = session.query(Transaction).all()
    transaction_list = [
        {
            "id": t.id,
            "sender": t.sender,
            "recipient": t.recipient,
            "amount": t.amount,
            "public_key": t.public_key,
            "signature": t.signature
        } for t in transactions
    ]

    # Получение последних 10 блоков
    blocks = session.query(Block).order_by(Block.index.desc()).limit(10).all()
    block_list = [
        {
            "index": b.index,
            "timestamp": b.timestamp,
            "transactions": json.loads(b.transactions),
            "previous_hash": b.previous_hash,
            "hash": b.hash,
            "nonce": b.nonce
        } for b in blocks
    ]

    # Статистика
    chain_length = session.query(Block).count()
    difficulty = update_difficulty()

    # Топ майнеров (по количеству блоков)
    miner_stats = {}
    all_blocks = session.query(Block).all()
    for block in all_blocks:
        transactions = json.loads(block.transactions)
        for tx in transactions:
            miner = tx.get("recipient")
            if miner:
                miner_stats[miner] = miner_stats.get(miner, 0) + 1
    top_miners = sorted(miner_stats.items(), key=lambda x: x[1], reverse=True)[:5]

    return render_template('index.html',
                           transactions=transaction_list,
                           blocks=block_list,
                           chain_length=chain_length,
                           difficulty=difficulty,
                           top_miners=top_miners)

# Роут для обозревателя блоков
@app.route('/block/<int:index>', methods=['GET'])
def block_explorer(index):
    block = session.query(Block).filter_by(index=index).first()
    if not block:
        return jsonify({"message": "Block not found"}), 404
    block_data = {
        "index": block.index,
        "timestamp": block.timestamp,
        "transactions": json.loads(block.transactions),
        "previous_hash": block.previous_hash,
        "hash": block.hash,
        "nonce": block.nonce
    }
    return render_template('block.html', block=block_data)

# Роут для получения текущего состояния блокчейна
@app.route('/chain', methods=['GET'])
def get_chain():
    blocks = session.query(Block).order_by(Block.index).all()
    chain = [{"index": b.index, "timestamp": b.timestamp, "transactions": json.loads(b.transactions), "previous_hash": b.previous_hash, "hash": b.hash, "nonce": b.nonce} for b in blocks]
    return jsonify(chain), 200

# Роут для добавления транзакции в пул
@app.route('/transaction', methods=['POST'])
def add_transaction():
    data = request.json
    required_fields = ["sender", "recipient", "amount", "fee", "public_key", "signature"]
    if not all(field in data for field in required_fields):
        return jsonify({"message": "Missing fields"}), 400

    # Проверка подписи
    public_key = data["public_key"]
    signature = data["signature"]
    message = f"{data['sender']}{data['recipient']}{data['amount']}{data['fee']}".encode()
    vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=SECP256k1)
    if not vk.verify(bytes.fromhex(signature), message):
        return jsonify({"message": "Invalid transaction signature"}), 400

    # Добавление транзакции в пул
    new_transaction = Transaction(
        sender=data["sender"],
        recipient=data["recipient"],
        amount=data["amount"],
        fee=data["fee"],
        public_key=public_key,
        signature=signature
    )
    session.add(new_transaction)
    session.commit()
    return jsonify({"message": "Transaction added to pool"}), 201

# Роут для получения списка транзакций из пула
@app.route('/transactions', methods=['GET'])
def get_transactions():
    transactions = session.query(Transaction).all()
    transactions_list = [
        {
            "id": t.id,
            "sender": t.sender,
            "recipient": t.recipient,
            "amount": t.amount,
            "fee": t.fee,
            "public_key": t.public_key,
            "signature": t.signature
        } for t in transactions
    ]
    return jsonify(transactions_list), 200

# Роут для получения текущей сложности
@app.route('/difficulty', methods=['GET'])
def get_difficulty():
    difficulty = update_difficulty()
    return jsonify({"difficulty": difficulty}), 200

@app.route('/mine', methods=['POST'])
def mine():
    global DIFFICULTY
    data = request.json
    required_fields = ["index", "timestamp", "transactions", "previous_hash", "nonce", "hash", "miner_address"]
    if not all(field in data for field in required_fields):
        return jsonify({"message": "Missing fields"}), 400

    # Проверка хэша
    calculated_hash = calculate_hash(data["index"], data["timestamp"], json.dumps(data["transactions"]), data["previous_hash"], data["nonce"])
    print(data["index"], data["timestamp"], json.dumps(data["transactions"]), data["previous_hash"], data["nonce"])
    print(f"Calculated hash: {calculated_hash}")
    print(f"Received hash: {data['hash']}")
    print(data["miner_address"])
    if calculated_hash != data["hash"]:
        return jsonify({"message": "Invalid hash"}), 400

    # Проверка сложности
    difficulty = update_difficulty()
    if not calculated_hash.startswith("0" * difficulty):
        return jsonify({"message": "Hash does not meet difficulty requirements"}), 400

    # Проверка подписи транзакций
    for transaction in data["transactions"]:
        public_key = transaction.get("public_key")
        signature = transaction.get("signature")
        message = f"{transaction['sender']}{transaction['recipient']}{transaction['amount']}{transaction['fee']}".encode()
        vk = VerifyingKey.from_string(bytes.fromhex(public_key), curve=SECP256k1)
        if not vk.verify(bytes.fromhex(signature), message):
            return jsonify({"message": "Invalid transaction signature"}), 400

    # Добавление награды майнеру
    miner_reward_transaction = {
        "sender": "BLOCKCHAIN",
        "recipient": data["miner_address"],
        "amount": MINER_REWARD + sum(tx["fee"] for tx in data["transactions"]),
        "fee": 0,
        "public_key": "",
        "signature": ""
    }
    data["transactions"].append(miner_reward_transaction)

    # Добавление блока
    add_block(data["index"], data["timestamp"], data["transactions"], data["previous_hash"], data["nonce"], data["hash"])

    # Очистка пула транзакций
    session.query(Transaction).delete()
    session.commit()

    return jsonify({"message": "Block added successfully", "difficulty": difficulty}), 201

if __name__ == '__main__':
    app.run(debug=True)