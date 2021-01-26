import json

from web3 import Web3
#from ethtoken.abi import EIP20_ABI

from blocktimes import Blocktimes, NODE_URL

NODE_URL = 'http://localhost:8545'
UNISWAP_V1_FAC_ADDRESS = '0xc0a47dFe034B400B47bDaD5FecDa2621de6c4d95'
UNISWAP_V2_FAC_ADDRESS = '0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f'

with open('erc20_abi.json') as f:
    EIP20_ABI = json.load(f)
with open('uniswap_v1_factory_abi.json') as f:
    UNISWAP_V1_FAC_ABI = json.load(f)
with open('uniswap_v1_exchange_abi.json') as f:
    UNISWAP_V1_EXC_ABI = json.load(f)
with open('uniswap_v2_factory_abi.json') as f:
    UNISWAP_V2_FAC_ABI = json.load(f)
with open('uniswap_v2_exchange_abi.json') as f:
    UNISWAP_V2_EXC_ABI = json.load(f)

class AssetRegister:
    exchanges_v1 = {}
    exchanges_v2 = {}
    def __init__(self, node_url=NODE_URL):
        self.web3 = Web3(Web3.HTTPProvider(node_url))

    def add_asset(self, address):
        self.exchanges_v1[address] = UniswapV1Exchange(self.web3, address)

    def get_price(self, address=None, symbol=None):
        if not address and not symbol:
            return None
        if not address:
            for ex in self.exchanges_v1:
                if self.exchanges_v1[ex].symbol.upper() == symbol.upper():
                    address = self.exchanges_v1[ex].token_contract.address

        return self.exchanges_v1[address].get_price()

class UniswapV1Exchange:
    def __init__(self, web3, token_address):
        self.web3 = web3
        factory = web3.eth.contract(address=UNISWAP_V1_FAC_ADDRESS, abi=UNISWAP_V1_FAC_ABI)
        exchange_address = factory.functions.getExchange(token_address).call()
        self.contract = web3.eth.contract(address=exchange_address, abi=UNISWAP_V1_EXC_ABI)
        self.token_contract = web3.eth.contract(address=token_address, abi=EIP20_ABI)
        self.token_decimals = self.token_contract.functions.decimals().call()
        self.symbol = str(self.token_contract.functions.symbol().call(),'utf-8').rstrip('\x00')
        print(f"symbol: '{self.symbol}'")

    def get_price(self, block='latest', inverse=False):
        ether_balance = self.web3.eth.getBalance(self.contract.address, block)
        erc20_balance = self.token_contract.functions.balanceOf(self.contract.address).call(
                                                                     block_identifier=block)
        if ether_balance == 0 or erc20_balance == 0:
            return None
        elif inverse:
            return erc20_balance * 10 ** (18 - self.token_decimals) / ether_balance
        else:
            return ether_balance / (erc20_balance * 10 ** (18 - self.token_decimals))

    def get_share_value(self, block='latest'):
        pass
