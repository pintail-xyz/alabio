from datetime import datetime
import time
import math
import json

from web3 import Web3

from utils import interp_search, progress_string

# genesis timestamp is not on blockchain, this is taken from etherscan.io
GENESIS_TS = 1438269973
NODE_URL = "http://localhost:8545"
DELTA = 1800 # 1800 seconds = 30 minutes
DEFAULT_FILENAME = 'data/blocktimes.json'

class Blocktimes:
    # object that can calculate, update, save, load and query a sequence of
    # Ethereum block numbers corresponding to equally spaced time deltas
    def __init__(
            self, start_ts=None, delta=DELTA, node_url=NODE_URL, filename=None
    ):
        if filename:
            # restore Blocktimes object from saved JSON file
            with open(filename) as f:
                tmp = json.load(f)
            self.start_ts = tmp['start_ts']
            self.delta = tmp['delta']
            if 'block_nums' in tmp:
                self.block_nums = tmp['block_nums']
            else:
                self.block_nums = []
                total = 0
                for d in tmp['block_diffs']:
                    total += d
                    self.block_nums += [total]

            self.ts_offsets = tmp['ts_offsets']
        else:
            # generate new Blocktimes object based on supplied parameters
            if not start_ts:
                start_ts = delta * (GENESIS_TS // delta + 1)
            self.start_ts = start_ts
            self.delta = delta
            self.block_nums = []
            self.ts_offsets = []

            self.generate_sequence(node_url)

        self.datetimes = []
        for i, offset in enumerate(self.ts_offsets):
            ts = self.start_ts + i * self.delta + offset
            self.datetimes.append(datetime.fromtimestamp(ts))

    def generate_sequence(self, node_url=NODE_URL):
        web3 = Web3(Web3.HTTPProvider(node_url))
        def get_timestamp(block):
            return web3.eth.getBlock(block).timestamp

        start_ts = self.start_ts
        delta = self.delta
        latest_block = web3.eth.getBlock('latest')
        latest_blocknum = latest_block.number
        latest_ts = latest_block.timestamp

        last = start_ts + delta * ((latest_ts - start_ts) // delta)
        sequence_length = 1 + (last - start_ts) // delta

        n = len(self.block_nums)
        if n > 0:
            blocknum_lims = [self.block_nums[-1], 0]
            ts_lims = [start_ts + n * delta + self.ts_offsets[-1], 0]
        else:
            blocknum_lims = [0, 0]
            ts_lims = [GENESIS_TS, 0]

        start_time = time.time()
        start_ind = len(self.block_nums)
        eval_count = 0

        for i in range(start_ind, sequence_length):
            blocknum_lims[1] = latest_blocknum
            ts_lims[1] = latest_ts
            target = start_ts + i * delta

            b, o, c = interp_search(target, blocknum_lims, ts_lims, get_timestamp)

            self.block_nums.append(b)
            self.ts_offsets.append(o)
            eval_count += c

            blocknum_lims[0] = self.block_nums[i]
            ts_lims[0] = target + self.ts_offsets[i]

            prog = progress_string(i, sequence_length, start_time)
            print(prog, end='\r')

        if start_ind < sequence_length:
            print(' ' * len(prog), end='\r')

    def save(self, filename=DEFAULT_FILENAME):
        data = self.as_dict()
        prev = 0
        diffs = []

        for b in data['block_nums']:
            diffs += [b - prev]
            prev = b

        data.pop('block_nums')
        data['block_diffs'] = diffs

        with open(filename, 'w') as f:
            json.dump(data, f, separators=(',', ':'))

    def as_dict(self):
        return {'start_ts':self.start_ts, 'delta':self.delta, 'block_nums':self.block_nums,
                'ts_offsets':self.ts_offsets}

    def print_latest(self):
        N = len(self.block_nums)
        last_period = self.start_ts + self.delta * (N - 1) + self.ts_offsets[N - 1]
        dt = datetime.utcfromtimestamp(last_period)
        print(f"latest dt: {dt}, blocknum: {self.block_nums[-1]}")

    def update(self):
        # extend sequence of block numbers up to the present
        self.generate_sequence()
        self.print_latest()

    def lookup(self, target):
        if not (isinstance(target, list) or isinstance(target, tuple)):
            i = round((target - self.start_ts) / self.delta)
            return self.block_nums[i], self.start_ts + i * self.delta + self.ts_offsets[i]

        block_nums = []
        timestamps = []
        for t in target:
            i = round((t - self.start_ts) / self.delta)
            block_nums.append(self.block_nums[i])
            timestamps.append(self.start_ts + i * self.delta + self.ts_offsets[i])

        return block_nums, timestamps

if __name__ == "__main__":
    b = Blocktimes()
    b.save()
