import time
import json
import fjson
import yaml
from hexbytes import HexBytes

from web3 import Web3
from blocktimes import Blocktimes, progress_string

NODE_URL = 'http://localhost:8545'
UNISWAP_V1_FAC_ADR = '0xc0a47dFe034B400B47bDaD5FecDa2621de6c4d95'
UNISWAP_V1_DEPLOY_BLOCK = 6627917
UNISWAP_V2_FAC_ADR = '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f'
UNISWAP_V2_DEPLOY_BLOCK = 10000835
WETH_ADR = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
DATA_DIR = 'data/'
ABI_DIR = 'abi/'
BLOCKTIMES_FILENAME = DATA_DIR + 'blocktimes.json'
TOKENS_FILENAME = 'tokens.yaml'
TOKENS_EXPORT_FILENAME = DATA_DIR + 'tokens.json'
FLOAT_FORMAT = '.5e'

with open(ABI_DIR + 'uniswap_v1_factory.json') as f:
    UNISWAP_V1_FAC_ABI = json.load(f)
with open(ABI_DIR + 'uniswap_v1_exchange.json') as f:
    UNISWAP_V1_EXC_ABI = json.load(f)
with open(ABI_DIR + 'uniswap_v2_factory.json') as f:
    UNISWAP_V2_FAC_ABI = json.load(f)
with open(ABI_DIR + 'uniswap_v2_exchange.json') as f:
    UNISWAP_V2_EXC_ABI = json.load(f)

def get_deploy_block(web3, address, lower_bound=0, upper_bound='latest'):
    nocode = HexBytes('0x')
    if upper_bound == 'latest':
        upper_bound = web3.eth.blockNumber

    while upper_bound - lower_bound > 1:
        mid = (lower_bound + upper_bound) // 2
        code = web3.eth.getCode(address, block_identifier=mid)
        if code == nocode:
            lower_bound = mid
        else:
            upper_bound = mid

    return upper_bound

class AssetRegister:
    exchanges_v1 = {}
    exchanges_v2 = {}
    price_histories = {}
    token_lookup = {}

    def __init__(self, node_url=NODE_URL, tokens_filename=TOKENS_FILENAME,
                 blocktimes_filename=BLOCKTIMES_FILENAME):

        self.web3 = Web3(Web3.HTTPProvider(node_url))
        with open(tokens_filename) as f:
            self.token_lookup = yaml.full_load(f)
        self.blocktimes = Blocktimes(filename=blocktimes_filename)

    def add_all_assets(self):
        for sym in self.token_lookup:
            self.add_asset(sym)

    def add_asset(self, identifier):
        token_info = self.get_token_info(identifier)
        symbol, address = token_info['symbol'], token_info['address']

        print(f"adding {symbol} ({address})")

        v1_exchange = UniswapV1Exchange(self.web3, address)
        self.exchanges_v1[address] = v1_exchange
        self.exchanges_v2[address] = UniswapV2Exchange(self.web3, address)
        try:
            with open(DATA_DIR + address.lower() + '.json') as f:
                self.price_histories[address] = json.load(f)
        except FileNotFoundError:
            print('no price history found for ' + symbol)

    def get_token_info(self, identifier):
        if self.web3.isAddress(identifier):
            adr = identifier
            sym = next(k for k, v in self.token_lookup.items() if v['address'] == adr)
        elif identifier in self.token_lookup:
            sym = identifier
            adr = self.token_lookup[identifier]['address']
        else:
            raise ValueError("token identifier {str(identifier)} not recognised")

        return {'symbol': sym, 'address': adr, 'name': self.token_lookup[sym]['name']}

    def export_token_info(self, filename=TOKENS_EXPORT_FILENAME):
        print(f"writing token info to {filename}")
        with open(filename, 'w') as f:
            json.dump(self.token_lookup, f, separators=(',', ':'))

    def get_deploy_block(self, identifier):
        token_info = self.get_token_info(identifier)
        address = token_info['address']

        v1_deploy_block = self.exchanges_v1[address].deploy_block
        v2_deploy_block = self.exchanges_v2[address].deploy_block

        return min(v1_deploy_block, v2_deploy_block)

    def get_price_in_eth(self, identifier, block='latest'):
        return self.get_price(identifier_A=identifier, block=block)

    def get_price(self, identifier_A, identifier_B=WETH_ADR, block='latest'):
        exchange_A1 = self.get_exchange(identifier_A, uniswap_version=1)
        exchange_A2 = self.get_exchange(identifier_A, uniswap_version=2)
        pool_A1, eth_A1 = exchange_A1.get_pools(block)
        pool_A2, eth_A2 = exchange_A2.get_pools(block)

        if identifier_B == WETH_ADR:
            pool_B1, pool_B2 = eth_A1, eth_A2
        else:
            exchange_B1 = self.get_exchange(identifier_B, uniswap_version=1)
            pool_B1, eth_B1 = exchange_B1.get_pools(block)
            pool_A1, pool_B1 = reweight_pools(pool_A1, eth_A1, pool_B1, eth_B1)

            exchange_B2 = self.get_exchange(identifier_B, uniswap_version=2)
            pool_B2, eth_B2 = exchange_B2.get_pools(block)
            pool_A2, pool_B2 = reweight_pools(pool_A2, eth_A2, pool_B2, eth_B2)

        if pool_A1 + pool_A2 == 0:
            return None
        else:
            return (pool_B1 + pool_B2) / (pool_A1 + pool_A2)

    def get_exchange(self, identifier, uniswap_version=2):
        token_info = self.get_token_info(identifier)
        address = token_info['address']

        if uniswap_version == 1:
            if address  not in self.exchanges_v1:
                self.add_asset(address)
            return self.exchanges_v1[address]
        elif uniswap_version == 2:
            if address not in self.exchanges_v2:
                self.add_asset(address)
            return self.exchanges_v2[address]
        else:
            return None

    def calculate_price_history_in_eth(self, identifier, clear_existing=False):
        token_info = self.get_token_info(identifier)
        symbol, address = token_info['symbol'], token_info['address']
        b = self.blocktimes

        # check if we already have a saved price history
        if address in self.price_histories:
            if clear_existing:
                self.price_histories.pop(address)
            else:
                start_ind = self.price_histories[address]['start_index']
                prices = self.price_histories[address]['prices']
                continue_from = start_ind + len(prices)

        # if starting fresh, identify first available block after exchange was deployed
        if address not in self.price_histories:
            deploy_num = self.get_deploy_block(identifier)
            start_ind = next(i for i, n in enumerate(b.block_nums) if n > deploy_num)
            for i in range(start_ind, len(b.block_nums)):
                start_ind = i
                price = self.get_price_in_eth(identifier, block=b.block_nums[i])
                if price:
                    break
            continue_from = start_ind
            prices = []

        start_time = time.time() # for reporting progress
        last_update = 0          #  "      "        "
        for i in range(continue_from, len(b.block_nums)):
            price = self.get_price_in_eth(identifier, block=b.block_nums[i])
            if not price:
                price = 0
            prices.append(price)

            t = time.time()
            if t - last_update > 0.2:
                prog = progress_string(i+1-start_ind, len(b.block_nums)-start_ind, start_time)
                print(prog, end='\r')
                last_update = t

        elapsed = time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))

        self.price_histories[address] = {'symbol':symbol,'address':address,
                                         'start_index':start_ind, 'prices':prices}

    def get_price_time_series(self, identifiers=None):
        if not identifiers:
            identifiers = self.price_histories.keys()

        start_ind = min(v['start_index'] for _, v in self.price_histories.items()
                        if v['symbol'] in identifiers or v['address'] in identifiers)

        result  = {'time':self.blocktimes.datetimes[start_ind:]}

        for identifier in identifiers:
            token_info = self.get_token_info(identifier)
            symbol, address = token_info['symbol'], token_info['address']

            diff = self.price_histories[address]['start_index'] - start_ind
            if diff:
                result[symbol] = [None] * diff + self.price_histories[address]['prices']
            else:
                result[symbol] = self.price_histories[address]['prices']

        return result

    def save_price_history(self, identifier):
        token_info = self.get_token_info(identifier)
        symbol, address = token_info['symbol'], token_info['address']

        with open(DATA_DIR + address.lower() + '.json', 'w') as f:
            fjson.dump(self.price_histories[address], f,
                       float_format=FLOAT_FORMAT)#, separators=(',',':'))


def reweight_pools(pool_A, eth_A, pool_B, eth_B):
    if pool_A == 0 or eth_A == 0 or pool_B == 0 or eth_B == 0:
        return 0, 0
    A_price = eth_A / pool_A
    B_price = eth_B / pool_B
    if eth_A > eth_B:
        return eth_B / A_price, pool_B
    else:
        return pool_A, eth_A / B_price

def get_abi(token_address):
    # check whether we have a specific abi for this address, else use ERC-20
    try:
        with open(ABI_DIR + token_address.lower() + '.json') as f:
            abi = json.load(f)
    except FileNotFoundError:
        with open(ABI_DIR + 'erc20.json') as f:
            abi = json.load(f)
    return abi

class UniswapV1Exchange:
    def __init__(self, web3, token_address):
        self.web3 = web3
        factory = web3.eth.contract(address=UNISWAP_V1_FAC_ADR,
                                    abi=UNISWAP_V1_FAC_ABI)
        exchange_address = factory.functions \
                                  .getExchange(token_address).call()
        self.contract = web3.eth.contract(address=exchange_address,
                                          abi=UNISWAP_V1_EXC_ABI)
        abi = get_abi(token_address)
        self.token_contract = web3.eth.contract(address=token_address, abi=abi)
        self.token_decimals = self.token_contract.functions.decimals().call()
        self.deploy_block = get_deploy_block(self.web3, exchange_address,
                                             lower_bound=UNISWAP_V1_DEPLOY_BLOCK)

    def get_ether_balance(self, block='latest'):
        raw = self.web3.eth.getBalance(self.contract.address,block)
        return raw * 10 ** -18

    def get_erc20_balance(self, block='latest'):
        raw = self.token_contract.functions.balanceOf(self.contract.address) \
                                           .call(block_identifier=block)
        return raw * 10 ** -self.token_decimals

    def get_pools(self, block='latest'):
        if isinstance(block, int) and block < self.deploy_block:
            return 0, 0
        else:
            return self.get_erc20_balance(block), self.get_ether_balance(block)

class UniswapV2Exchange:
    def __init__(self, web3, token_A_address, token_B_address=WETH_ADR):
        self.web3 = web3
        factory = web3.eth.contract(address=UNISWAP_V2_FAC_ADR,
                                    abi=UNISWAP_V2_FAC_ABI)
        self.address = factory.functions.getPair(token_A_address,
                                                 token_B_address).call()
        self.contract = web3.eth.contract(address=self.address,
                                          abi=UNISWAP_V2_EXC_ABI)

        token_A_abi = get_abi(token_A_address)
        self.token_A_contract = web3.eth.contract(address=token_A_address,
                                                  abi=token_A_abi)
        self.token_A_decimals = self.token_A_contract \
                                    .functions.decimals().call()

        token_B_abi = get_abi(token_B_address)
        self.token_B_contract = web3.eth.contract(address=token_B_address,
                                                  abi=token_B_abi)
        self.token_B_decimals = self.token_B_contract \
                                    .functions.decimals().call()
        self.deploy_block = get_deploy_block(self.web3, self.address,
                                             lower_bound=UNISWAP_V2_DEPLOY_BLOCK)

    def get_token_A_balance(self, block='latest'):
        raw = self.token_A_contract.functions.balanceOf(self.address)  \
                                            .call(block_identifier=block)
        return raw * 10 ** -self.token_A_decimals


    def get_token_B_balance(self, block='latest'):
        raw = self.token_B_contract.functions.balanceOf(self.address)  \
                                            .call(block_identifier=block)
        return raw * 10 ** -self.token_B_decimals

    def get_pools(self, block='latest'):
        if isinstance(block, int) and block < self.deploy_block:
            return 0, 0
        else:
            return self.get_token_A_balance(block), self.get_token_B_balance(block)
