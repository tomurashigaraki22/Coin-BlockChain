from time import time
from flask import jsonify
import hashlib
import json
import sqlite3
import random
import string

conn = sqlite3.connect('./database.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, senderName TEXT, address TEXT, balance TEXT, password TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS blockchain (
                [id] INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                transactions TEXT,
                proof INTEGER,
                previous_hash TEXT)''')
conn.commit()

class Blockchain:
    def __init__(self):
        self.conn = sqlite3.connect('./database.db')
        self.c = self.conn.cursor()
        self.current_transactions = []
        self.accounts = {}
        self.chain = []
        self.c.execute('''CREATE TABLE IF NOT EXISTS blockchain (
                            [id] INTEGER PRIMARY KEY AUTOINCREMENT,
                            timestamp REAL,
                            transactions TEXT,
                            proof INTEGER,
                            previous_hash TEXT)''')
        self.conn.commit()

        # Load existing blockchain data from the database
        self.load_blockchain_from_db()

        # Create the genesis block if the blockchain is empty
        if not self.chain:
            self.new_block(proof=100)
    
    def signup(self, username, password):
        self.c.execute('SELECT * FROM accounts WHERE senderName = ?', (username,))
        row = self.c.fetchone()
        if row:
            print('User already exists with this username')
            return jsonify({'message': 'User already exists', 'status': 409})

        while True:
            characters = string.ascii_lowercase + string.digits
            random_string = ''.join(random.choice(characters) for _ in range(20))
            
            self.c.execute('SELECT * FROM accounts WHERE address = ?', (random_string,))
            existing_user = self.c.fetchone()
            
            if not existing_user:
                # The random string is unique, so we can use it
                break
        self.c.execute('INSERT INTO accounts (senderName, address, balance, password) VALUES (?, ?, ?, ?)', (username, random_string, 1000, password))
        self.conn.commit()

    def load_blockchain_from_db(self):
        self.chain = []
        self.c.execute('SELECT * FROM blockchain ORDER BY id')
        rows = self.c.fetchall()

        for row in rows:
            block = {
                "id": row[0],
                "timestamp": row[1],
                "transactions": json.loads(row[2]),
                "proof": row[3],
                "previous_hash": row[4],
            }
            self.chain.append(block)

    def save_block_to_db(self, block):
        self.c.execute('INSERT INTO blockchain (timestamp, transactions, proof, previous_hash) VALUES (?, ?, ?, ?)',  (block['timestamp'], json.dumps(block['transactions']), block['proof'], block['previous_hash']))
        self.conn.commit()

    def new_block(self, proof):
        # Fetch the previous hash from the last block in the chain
        previous_block = self.last_block if self.chain else {"previous_hash": "1"}

        block = {
            "timestamp": time(),
            "transactions": self.current_transactions,
            "proof": proof,
            "previous_hash": self.hash(previous_block),
        }

        self.current_transactions = []
        self.chain.append(block)
        self.save_block_to_db(block)
        return block


    def new_transaction(self, sender, recipient, amount):
        if sender not in self.accounts:
            self.accounts[sender] = 1000  # Initial balance for a new account

        if self.accounts[sender] >= amount:
            self.current_transactions.append({
                "sender": sender,
                "recipient": recipient,
                "amount": amount,
            })
            self.accounts[sender] -= amount
            if recipient not in self.accounts:
                self.accounts[recipient] = 0
            self.accounts[recipient] += amount
            return self.last_block["id"] + 1 if self.last_block else 1
        else:
            return -1  # Insufficient balance

    def proof_of_work(self, last_proof):
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    # Modify the valid_proof method to require more leading zeros
    @staticmethod
    def valid_proof(last_proof, proof, difficulty=5):
        guess = f"{last_proof}{proof}".encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:difficulty] == "0" * difficulty

    @staticmethod
    def hash(block):
        return hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]

# Example usage
if __name__ == '__main__':
    blockchain = Blockchain()
    sender = input('Input Sender Name: ')
    receiver = input('Input Receiver Name: ')
    amount = input('Input Amount: ')
    blockchain.new_transaction(sender, receiver, int(amount))

    while True:
        last_block = blockchain.last_block
        last_proof = last_block["proof"]
        proof = blockchain.proof_of_work(last_proof)

        # Check if the found proof is valid
        if blockchain.valid_proof(last_proof, proof):
            break  # Exit the loop when a valid proof is found

    # Create a new block with the valid proof
    blockchain.new_block(proof)

    print("New block mined!")
    print(json.dumps(blockchain.chain, indent=4))
    conn.close()
