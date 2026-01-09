# Блокчейн
Реализация технологии Proof-of-work, а также собственный тестовый алгоритм майнинга.
**Актуальность темы исследования** определяется тем, что в современным
миром блокчейн развивается семимильными шагами и число областей его
применения растут с каждым годом, тем самым изучение работы блокчейна
является неотъемлемо важным для живущего в современном мире человеке.

**Целью работы** является закрепление теоретических знаний о базовых
принципах работы блокчейн технологий и майнинга.

**Задачи работы** представляют собой следующее:

1.  Изучение теоретических сведений о блокчейне
2.  Изучение разновидностей блокчейна
3.  Реализация блокчейна без Proof-of-Work
4.  Реализация блокчейна с Proof-of-Work
5.  Написание собственного алгоритма майнинга

**Объектом исследования** является блокчейн.

**Предметом исследования** блокчейн с и без Proof-of-Work, алгоритмы
консенсуса и майнинга.

### Реализация блокчейна без Proof-of-Work

В рамках данной работы для реализации блокчейна используется язык
программирования Python3.12 с фреймворком Flask для создания HTTP
сервера. Для отправки запросов используется cURL.

Программа представляет собой HTTP сервер, который может обрабатывать
следующие запросы:

1.  /blocks возвращает цепочку блоков данного узла сети
2.  /mineBlock принимает информацию, добавляемую в блок, и осуществляет
    майнинг, возвращая добытый блок. Также оповещает другие узлы о
    добытом блоке через /updateChain, который в свою очередь обновляет
    цепь своего узла
3.  /peers возвращает список узлов, о котором известно данному участнику
    блокчейна
4.  /add_peer принимает URL нового узла и добавляет в свой список,
    обновляя списки уже добавленных участников через /updatePeers
5.  /resolve позволяет запустить алгоритм консенсуса, находя наибольшую
    цепь среди участников цепи

Структура блокчейна и действия с ним представлены в классе Blockchain:

```python
class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.peers = set()
        self.chain.append(self.get_genesis_block())

    @staticmethod
    def get_genesis_block():
        return Block(0, "0", 1714946885, "First block")

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
                    temp_chain.append(Block(block['index'], block['previous_hash'], block['timestamp'], block['data']))
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
        new_block = Block(len(self.chain), self.chain[-1].our_hash, time(), data)
        self.add_block(new_block)

    def latest_block(self):
        return self.chain[-1]
Класс блока выглядит следующим образом:

python
class Block(object):
    def __init__(self, index, previous_hash, timestamp, data):
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.data = data
        self.our_hash = self.calculate_hash()

    def __ne__(self, other):
        return (self.index != other.index or self.previous_hash != other.previous_hash
                or self.timestamp != other.timestamp or self.data != other.data or self.our_hash != other.our_hash)

    def calculate_hash(self):
        block_string = str(str(self.index) + self.previous_hash + str(self.timestamp) + self.data).encode()
        return hashlib.sha256(block_string).hexdigest()
Далее пройдемся по коду узлов сети, к которым будут идти обращения.

python
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
    new_block = Block(block_data['index'], block_data['previous_hash'], block_data['timestamp'], block_data['data'])
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
    for existing_peer in peers:
        if existing_peer not in blockchain.peers:
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
