from flask import Flask, jsonify, request
from time import time
import sqlite3
import hashlib
import json
import string
import jwt
import random
import threading

app = Flask(__name__)
app.secret_key = 'blockchaintesting'

conn = sqlite3.connect('./database.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY, senderName TEXT, address TEXT, balance TEXT, password TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS blockchain (
                [id] INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                transactions TEXT,
                proof INTEGER,
                previous_hash TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS blockchain_transactions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          transactions TEXT,
          timestamp REAl,
          uniqueId
)
''')
conn.commit()

mining_in_progress = False
app.config['mining_thread'] = None

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

    def new_transaction(self, sender, recipient, amount, username):
        # Connect to the database
        conn = sqlite3.connect('./database.db')
        c = conn.cursor()

        c.execute('SELECT * FROM accounts WHERE address = ?', (recipient,))
        rec_found = c.fetchone()
        if rec_found:

            # Check if the sender exists in the accounts table
            c.execute('SELECT balance FROM accounts WHERE senderName = ?', (sender,))
            sender_balance = c.fetchone()

            # Check if the sender exists and has sufficient balance
            if sender_balance and int(sender_balance[0]) >= amount:
                # Create the transaction
                transaction_data = {
                    "sender": sender,
                    "recipient": recipient,
                    "amount": amount,
                }
                self.current_transactions.append(transaction_data)

                # Convert the current_transactions list to a JSON string
                transactions_json = json.dumps(self.current_transactions)
                character = string.ascii_lowercase
                characters = string.ascii_lowercase + string.digits
                unique_id = str(int(time())) + ''.join(random.choice(characters) for _ in range(20))
                # Insert the JSON string into the blockchain_transactions table
                c.execute('INSERT INTO blockchain_transactions (transactions, timestamp, uniqueId, username) VALUES (?, ?, ?, ?)', (transactions_json, time(), unique_id, username))

                # Deduct the amount from the sender's balance
                c.execute('UPDATE accounts SET balance = balance - ? WHERE senderName = ?', (amount, sender))

                # Add the amount to the recipient's balance
                c.execute('UPDATE accounts SET balance = balance + ? WHERE senderName = ?', (amount, recipient))

                # Commit the changes to the database
                conn.commit()

                return self.last_block["id"] + 1 if self.last_block else 1
            else:
                return jsonify({'status': 404, 'message': 'Insufficient Balance'})
        else:
            return jsonify({ 'status': 404, 'message': 'Recipient Not Found'})

        
    def proof_of_work(self, last_proof):
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof, difficulty=8):
        guess = f"{last_proof}{proof}".encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:difficulty] == "0" * difficulty

    @staticmethod
    def hash(block):
        return hashlib.sha256(json.dumps(block, sort_keys=True).encode()).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]
    
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    conn = sqlite3.connect('./database.db')
    c = conn.cursor()

    c.execute('SELECT * FROM accounts WHERE senderName = ?', (username,))
    row = c.fetchone()
    if row:
        print(row)
        print(row[4])
        if password == row[4]:
            payload = {
                'username': row[1],
                'password': row[4],
                'address': row[2]
            }
            jwt_token = jwt.encode(payload, app.secret_key, algorithm='HS256')

            return jsonify({'message':'Login Successful', 'status': 200, 'token': jwt_token})
        else:
            return jsonify({'message': 'Login Unsuccessful', 'status': 404})
    else:
        return jsonify({'message': 'User does not exist', 'status': 404})

@app.route('/signup', methods=['POST'])
def signup():
    username = request.form.get('username')
    password = request.form.get('password')
    conn = sqlite3.connect('./database.db')
    c = conn.cursor()

    # Check if the user already exists
    c.execute('SELECT * FROM accounts WHERE senderName = ?', (username,))
    row = c.fetchone()
    if row:
        return jsonify({'message': 'User already exists', 'status': 409})

    # Generate a unique address for the user
    while True:
        characters = string.ascii_lowercase + string.digits
        random_string = ''.join(random.choice(characters) for _ in range(20))
        
        c.execute('SELECT * FROM accounts WHERE address = ?', (random_string,))
        existing_user = c.fetchone()
        
        if not existing_user:
            # The random string is unique, so we can use it
            break

    # Store the password as plain text
    c.execute('INSERT INTO accounts (senderName, address, balance, password) VALUES (?, ?, ?, ?)', (username, random_string, 1000, password))
    conn.commit()
    payload = {
            'username': username,
            'password': password,
            'address': random_string
        }
    jwt_token = jwt.encode(payload, app.secret_key, algorithm='HS256')

    return jsonify({'message': 'User registered successfully', 'status': 200, 'address': random_string, 'token': jwt_token})

@app.route('/new_transaction', methods=['POST'])
def new_transaction():
    # Get data from the request
    sender = request.form.get('sender')
    recipient = request.form.get('recipient')
    amount = int(request.form.get('amount'))

    # Check if the sender has sufficient balance
    conn = sqlite3.connect('./database.db')
    c = conn.cursor()
    c.execute('SELECT * FROM accounts WHERE senderName = ?', (sender,))
    sender_deets = c.fetchone()
    sender_balance = sender_deets[3]
    sender_addr = sender_deets[2]
    print(sender_balance)

    if not sender_balance or int(sender_balance) < amount:
        return jsonify({'message': 'Insufficient balance', 'status': 400})

    # Create an instance of the Blockchain class
    blockchain = Blockchain()

    # Call the new_transaction method on the blockchain instance
    blockchain.new_transaction(sender, recipient, amount, sender)

    return jsonify({'message': 'Transaction added to the blockchain', 'status': 200, 'sender_addr': sender_addr})


@app.route('/mine', methods=['GET', 'POST'])
def mine():
    global mining_in_progress
    username = request.form.get('username')
    conn = sqlite3.connect('./database.db')
    c = conn.cursor()
    c.execute('SELECT balance FROM accounts WHERE senderName = ?', (username,))
    cs = c.fetchone()
    balance = cs[0]
    print(balance)
    if not mining_in_progress:
        # Start the mining process in a separate thread
        mining_in_progress = True
        per_block = 100
        
        def mine_block():
            blockchain = Blockchain()  # Create a new blockchain instance inside the thread
            conn = sqlite3.connect('./database.db')  # Create a new database connection
            c = conn.cursor()  # Create a new cursor

            while mining_in_progress:
                last_block = blockchain.last_block
                last_proof = last_block["proof"]
                proof = blockchain.proof_of_work(last_proof)

                # Check if the found proof is valid
                if blockchain.valid_proof(last_proof, proof):
                    # Create a new block with the valid proof
                    blockchain.new_block(proof)
                    print("New block mined!")
                    c.execute('SELECT balance FROM accounts WHERE senderName = ?', (username,))
                    cs = c.fetchone()
                    
                    # Increment the balance by 100 and update it in the database
                    ball = int(cs[0])
                    balance2 = ball + per_block
                    c.execute('UPDATE accounts SET balance = ? WHERE senderName = ?', (balance2, username))
                    conn.commit()
                    print(f"Balance updated: {balance2}")

            conn.close()  # Close the database connection when mining is finished

        mining_thread = threading.Thread(target=mine_block)
        app.config['mining_thread'] = mining_thread  # Store the thread in the app's configuration
        mining_thread.start()
        return jsonify({'message': 'Mining started', 'status': 200, 'balance': balance})
    else:
        return jsonify({'message': 'Mining is already in progress', 'status': 400})

    
@app.route('/getData', methods=['POST'])
def getData():
    username = request.form.get('username')
    password = request.form.get('password')
    conn = sqlite3.connect('./database.db')
    c = conn.cursor()

    c.execute('SELECT * FROM accounts WHERE senderName = ?', (username,))
    row = c.fetchone()
    if row:
        return jsonify({'balance': row[3], 'status': 200, 'address': row[2]})
    else:
        return jsonify({'status': 404, 'balance': None, 'address': None})
    
@app.route('/getTransactions', methods=['POST'])
def getTransactions():
    username = request.form.get('username')
    password = request.form.get('password')
    conn = sqlite3.connect('./database.db')
    c = conn.cursor()

    c.execute('SELECT transactions FROM blockchain_transactions WHERE username = ?', ('portable',))
    row = c.fetchone()
    
    if row:
        transactions_data = json.loads(row[0])  # Parse the JSON data
        return jsonify(transactions_data)  # Return the parsed data as JSON
    else:
        return jsonify([])  # Return an empty array if no data is found

@app.route('/cancel_mine', methods=['POST'])
def cancel_mine():
    global mining_in_progress
    mining_thread = app.config.get('mining_thread')  # Get the mining thread object
    
    if mining_thread:
        mining_in_progress = False  # Set the flag to stop mining
        mining_thread.join()  # Wait for the mining thread to complete
        app.config['mining_thread'] = None  # Reset the thread object in the app's configuration
        return jsonify({'message': 'Mining canceled', 'status': 200})
    else:
        return jsonify({'message': 'No mining in progress', 'status': 400})
# ...

if __name__ == '__main__':
    app.config['mining_thread'] = None  # Initialize a variable to hold the mining thread
    app.run(host='0.0.0.0', port=6005, use_reloader=True)