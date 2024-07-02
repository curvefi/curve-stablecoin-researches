import requests
from scipy.optimize import minimize_scalar
from web3 import Web3

import json
import os
import time
from getpass import getpass
from eth_account import account
from copy import deepcopy

from simulator import Curve

web3 = Web3(
    provider=Web3.HTTPProvider(
        f"http://localhost:8545",
    ),
)

PRICE_DEVIATION = 500000000000000
PEG_KEEPERS = {
    "USDC": "0x5B49b9adD1ecfe53E19cc2cFc8a33127cD6bA4C6",
    "USDT": "0xFF78468340EE322ed63C432BF74D817742b392Bf",
    "pyUSD": "0x68e31e1eDD641B13cAEAb1Ac1BE661B19CC021ca",
    "TUSD": "0x0B502e48E950095d93E8b739aD146C72b4f6C820",
}
pools = {
    "USDT": "0x390f3595bCa2Df7d23783dFd126427CCeb997BF4",
    "USDC": "0x4DEcE678ceceb27446b35C672dC7d61F30bAD69E",
    "pyUSD": "0x625E92624Bc2D88619ACCc1788365A69767f6200",
    "TUSD": "0x34D655069F4cAc1547E4C8cA284FfFF5ad4A8db0",
}
MAX_FEE = 50 * 10 ** 9  # 50 gwei
PRIORITY = 2 * 10 ** 9  # 2 gwei

def account_load_pkey(fname):
    path = os.path.expanduser(os.path.join('~', '.brownie', 'accounts', fname + '.json'))
    with open(path, 'r') as f:
        pkey = account.decode_keyfile_json(json.load(f), getpass())
        return pkey
wallet_address = "0x71F718D3e4d1449D1502A6A7595eb84eBcCB1683"
# wallet_pk = account_load_pkey("curve")


def deploy_caller():
    import boa
    boa.set_network_env(f"http://localhost:8545")
    boa.env.add_account(account.Account.from_key(wallet_pk))
    boa.load("PegKeeperCaller.vy", "0x36a04caffc681fa179558b2aaba30395cddd855f", "0xbbbbbbbbbb9cc5e90e3b3af64bdaf62c37eeffcb", list(pools.values()))


builders = [
    "https://rpc.beaverbuild.org/",
    "https://rpc.titanbuilder.xyz/",
    "https://rsync-builder.xyz",
    # "https://relay.flashbots.net",
]


def get_amount(params):
    curve = Curve(params)

    def optimization_fun(x, log=False):
        sim = deepcopy(curve)
        i = 0 if x < 0 else 1
        if x != 0:
            amount = abs(int(x * 10 ** params[1][i]))
            dy = sim.exchange(i, 1-i, amount)
            if log:
                print(f"dy {dy}")
        if log:
            print(sim.get_p(), sim.p_o)
        return abs(sim.get_p() - sim.p_o) / 10 ** 18

    total = params[0][0] / 10 ** params[1][0] + params[0][1] / 10 ** params[1][1]
    solution = minimize_scalar(
        optimization_fun,
        bounds=(-10 * total, 10 * total),
        tol=0.000000000000000001,
        method='bounded',
    )
    # print(solution.fun, solution.x)

    x = solution.x
    i = 0 if x < 0 else 1
    return abs(int(x * 10 ** params[1][i])), i


def run():
    caller_abi = [{"stateMutability":"nonpayable","type":"constructor","inputs":[{"name":"_regulator","type":"address"},{"name":"_morpho","type":"address"},{"name":"_pools","type":"address[4]"}],"outputs":[]},{"stateMutability":"view","type":"function","name":"get_params","inputs":[{"name":"pk","type":"address"},{"name":"_ng","type":"bool"}],"outputs":[{"name":"","type":"tuple","components":[{"name":"balances","type":"uint256[2]"},{"name":"decimals","type":"uint256[2]"},{"name":"p_o","type":"uint256"},{"name":"cur_p","type":"uint256"},{"name":"A","type":"uint256"},{"name":"fee","type":"uint256"},{"name":"is_inverse","type":"bool"}]}]},{"stateMutability":"nonpayable","type":"function","name":"call","inputs":[{"name":"pk","type":"address"},{"name":"amount","type":"uint256"},{"name":"i","type":"int128"}],"outputs":[]},{"stateMutability":"nonpayable","type":"function","name":"call","inputs":[{"name":"pk","type":"address"},{"name":"amount","type":"uint256"},{"name":"i","type":"int128"},{"name":"_receiver","type":"address"}],"outputs":[]},{"stateMutability":"nonpayable","type":"function","name":"onMorphoFlashLoan","inputs":[{"name":"assets","type":"uint256"},{"name":"data","type":"bytes"}],"outputs":[]},{"stateMutability":"nonpayable","type":"function","name":"approve","inputs":[{"name":"_pool","type":"address"}],"outputs":[]}]
    web3_caller = web3.eth.contract("0xB1E914a640766539e744354f15862876E5250cc6", abi=caller_abi)

    while True:
        for name, pk in PEG_KEEPERS.items():
            block = web3.eth.get_block_number() + 1
            params = web3_caller.functions.get_params(pk, name == "pyUSD").call()
            if params[2] >= int(1.001 * 10 ** 18) and abs(params[3] - params[2]) >= PRICE_DEVIATION:
                amount, i = get_amount(params)
                try:
                    transaction = web3_caller.functions.call(pk, amount, i).buildTransaction({
                        "from": wallet_address, "nonce": web3.eth.get_transaction_count(wallet_address),
                        "maxFeePerGas": MAX_FEE, "maxPriorityFeePerGas": PRIORITY,
                    })
                    gas_estimate = web3.eth.estimate_gas(transaction)
                    transaction["gas"] = int(1.1 * gas_estimate)
                except Exception as e:
                    print(f"Could not build transaction", repr(e))
                    continue

                # Estimation went well, can execute
                signed_txs = [web3.eth.account.sign_transaction(transaction, private_key=wallet_pk)]
                print(f"Trying block {block}")
                for builder in builders:
                    r = requests.post(builder, json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "eth_sendBundle",
                        "params": [
                            {
                                "txs": [tx.rawTransaction.hex() for tx in signed_txs],
                                "blockNumber": str(hex(block)),
                            }
                        ]
                    })
                    print(builder, r.json())
                time.sleep(12 * 1.5)  # wait to propagate


if __name__ == "__main__":
    # deploy_caller()
    run()
