from flask import Flask, jsonify, request
from time import time
import requests
import hashlib
from urllib.parse import urlparse
import argparse


class Block(object):
    def __init__(self, index, previous_hash, timestamp, data, difficulty, nonce):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.data = data
        self.difficulty = difficulty
        self.nonce = nonce
        self.our_hash = self.calculate_hash()

    def __ne__(self, other):
        return (self.index != other.index or self.previous_hash != other.previous_hash
                or self.timestamp != other.timestamp or self.data != other.data or self.our_hash != other.our_hash)

    def calculate_hash(self):
        block_string = str(int(self.previous_hash, 16) * self.nonce).encode()
        return hashlib.sha256(block_string).hexdigest()


class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.peers = set()
        self.chain.append(self.get_genesis_block())
        self.difficulty = 7

    @staticmethod
    def get_genesis_block():
        return Block(0, "0", 1714946885, "First block", 0, 3)

    def add_block(self, block):
        if self.is_valid_block(block, self.latest_block()):
            self.chain.append(block)
            return True
        return False

    @staticmethod
    def is_valid_block(block, prev_block):
        if (block.index != prev_block.index + 1 or
                prev_block.our_hash != block.previous_hash or block.calculate_hash() != block.our_hash):
            return False
        return True

    def is_valid_chain(self, chain):
        if chain[0] != self.get_genesis_block():
            return False
        for i in range(1, len(chain)):
            if not self.is_valid_block(chain[i], chain[i - 1]):
                return False
        return True

    def resolve_conflicts(self):
        new_chain = None
        max_length = len(self.chain)

        for peer in self.peers:
            response = requests.get(f'http://{peer}/blocks')
            temp_chain = []
            if response.status_code == 200:
                chain = response.json()
                for block in chain:
                    temp_chain.append(Block(block['index'], block['previous_hash'], block['timestamp'], block['data'],
                                            block['difficulty'], block['nonce']))
                    temp_chain[-1].our_hash = block['our_hash']
                if len(chain) > max_length and self.is_valid_chain(temp_chain):
                    new_chain = temp_chain
                    max_length = len(chain)
        if new_chain:
            self.chain = new_chain
            return True

        return False

    def add_peer(self, address):
        url = urlparse(address)
        self.peers.add(url.netloc)

    def mine_block(self, data):
        new_block = Block(len(self.chain), self.chain[-1].our_hash, time(), data, self.difficulty, 0)
        nonce = 1
        while True:
            prime = True
            for i in range(2, nonce // 2 + 1):
                if nonce % i == 0:
                    prime = False
                    nonce += 1
                    break
            if not prime:
                continue
            num = int(new_block.our_hash[:self.difficulty], 16)
            new_block.nonce = nonce
            new_block.our_hash = new_block.calculate_hash()
            for i in range(2, num // 2 + 1):
                if num % i == 0:
                    prime = False
                    nonce += 1
                    break
            if prime and new_block.our_hash[0] != '0':
                self.add_block(new_block)
                break

    def latest_block(self):
        return self.chain[-1]


app = Flask(__name__)
blockchain = Blockchain()


@app.route('/blocks', methods=['GET'])
def get_blocks():
    chain_data = []
    for block in blockchain.chain:
        chain_data.append(vars(block))
    return jsonify(chain_data), 200


@app.route('/mineBlock', methods=['POST'])
def mine_block():
    data = request.get_json().get('data')
    blockchain.mine_block(data)
    for peer in blockchain.peers:
        requests.post('http://' + peer + '/updateChain', json={'block': vars(blockchain.latest_block())})
    return jsonify({'message': 'Block mined', 'block': vars(blockchain.latest_block())}), 201


@app.route('/updateChain', methods=['POST'])
def update_block():
    data = request.get_json()
    block_data = data.get('block')
    new_block = Block(block_data['index'], block_data['previous_hash'], block_data['timestamp'], block_data['data'],
                      block_data['difficulty'], block_data['nonce'])
    if new_block.index <= blockchain.latest_block().index:
        return jsonify({'message': 'Chain is not behind'}), 201
    if new_block.previous_hash == blockchain.latest_block().our_hash:
        if blockchain.add_block(new_block):
            return jsonify({'message': 'Block added', 'block': vars(new_block)}), 201
    if blockchain.resolve_conflicts():
        return jsonify({'message': 'Chain updated'})
    return jsonify({'message': 'Chain is not behind'}), 201


@app.route('/peers', methods=['GET'])
def get_peers():
    return jsonify(list(blockchain.peers)), 200


@app.route('/addPeer', methods=['POST'])
def add_peer():
    values = request.get_json()
    peers = values.get('peers')

    for peer in peers:
        blockchain.add_peer(peer)
    for existing_peer in blockchain.peers:
        if existing_peer not in peers:
            requests.post('http://' + existing_peer + '/updatePeers', json={'peers': list(peers)})
    return jsonify({'message': 'Peers added', 'peers': list(blockchain.peers)}), 201


@app.route('/updatePeers', methods=['POST'])
def update_peers():
    values = request.get_json()
    peers = values.get('peers')
    for peer in peers:
        blockchain.add_peer(peer)
    return jsonify({'message': 'Peers updated', 'peers': list(blockchain.peers)}), 201


@app.route('/resolve', methods=['GET'])
def consensus():
    if blockchain.resolve_conflicts():
        return jsonify({'message': 'Chain updated'})
    else:
        return jsonify({'message': 'Chain is not behind'}), 201


parser = argparse.ArgumentParser(prog='Blockchain')
parser.add_argument('-p', '--port', type=int, help='HTTP port', required=True)
parser.add_argument('-e', '--peers', nargs='*', type=str, help='List of existing peers')


if __name__ == '__main__':
    args = parser.parse_args()
    port = args.port
    default_peers = args.peers
    if default_peers:
        for def_pear in default_peers:
            blockchain.add_peer(def_pear)

    app.run(host='0.0.0.0', port=port)
