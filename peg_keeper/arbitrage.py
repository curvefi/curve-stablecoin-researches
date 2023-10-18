import boa
import os
from simulation import Curve
from copy import deepcopy


# Pool params
n = 2
CRVUSD_I = 1  # For 0 use (1 - share)
A = 500  # ALTER
fees = [
    int(0.01 * 10 ** 8),  # Arber
    int(0.02 * 10 ** 8),  # Arbed
]  # ALTER: %
usd_amount = 2 * 10 ** 6  # ALTER: each token balance in equilibrium

# auxiliary
INITIAL_AMOUNT = usd_amount * 10 ** 18
STEPS = 400

EPSILON = 10 ** 17

PROFIT_BREAKPOINTS = [0, 3, 6, 12, 24, 48]


def get_price(_curve):
    dx = 10 ** 18
    return dx / _curve.dy(CRVUSD_I, 1 - CRVUSD_I, dx, False)


def preset_curve(dx, fee):
    curve = Curve(A, 0, n, tokens=0, fee=fee, admin_fee=5 * 10 ** 9)
    curve.add_liquidity([INITIAL_AMOUNT] * n, True)
    if dx != 0:
        i = 0 if dx < 0 else 1
        curve.exchange(i, 1 - i, abs(dx))
    return curve


def arbitrage_profit(c0: Curve, c1: Curve):
    def find_best(left_bound, right_bound):
        profit, best_dx = 0, 0
        step = (right_bound - left_bound) // 100
        for dx in range(left_bound, right_bound, step):
            dy = c0.dy(CRVUSD_I, 1 - CRVUSD_I, dx)
            new_dx = c1.dy(1 - CRVUSD_I, CRVUSD_I, dy)
            cur_profit = new_dx - dx
            if profit < cur_profit:
                profit, best_dx = cur_profit, new_dx
        return profit, best_dx, step
    p0, p1 = get_price(c0), get_price(c1)
    if p0 > p1:
        c0, c1 = c1, c0
    # Arbitrage, assuming other0 = other1:
    # crvusd --c0-> dy other0
    # crvusd <-c1-- dy other1
    profit, best_dx, step = find_best(10 ** 18, usd_amount * 10 ** 18)
    for i in range(5):
        profit, best_dx, step = find_best(max(best_dx - step, 0), best_dx + step)
    if profit < EPSILON or best_dx < EPSILON:
        return 0, (get_price(c0), get_price(c1))
    # Calculate new prices
    dy = c0.exchange(CRVUSD_I, 1 - CRVUSD_I, best_dx)
    new_dx = c1.exchange(1 - CRVUSD_I, CRVUSD_I, dy)
    return profit / 10 ** 18, (get_price(c0), get_price(c1))


def find_arbitrage_limit(p: float):
    print(f"fees: {fees[0] / 10 ** 8:.2f}% arber, {fees[1] / 10 ** 8:.2f}% arbed")

    curve0 = preset_curve(0, fees[0])
    left_bound, right_bound = 10 ** 18, usd_amount * 10 ** 18 // 2
    for dx in range(left_bound, right_bound, (right_bound - left_bound) // STEPS):
        curve = preset_curve(-dx, fees[0])
        if abs(get_price(curve0) - p) > abs(get_price(curve) - p):
            curve0 = curve
            left_bound = dx
    print(f"Arber curve initial price: {get_price(curve0):.5f}")

    profit_breakpoints = PROFIT_BREAKPOINTS
    for dx in range(left_bound, right_bound, (right_bound - left_bound) // STEPS):
        curve1 = preset_curve(-dx, fees[1])

        initial_price = get_price(curve1)
        profit, prices = arbitrage_profit(deepcopy(curve0), deepcopy(curve1))

        if profit > profit_breakpoints[0]:
            print(f"{profit:.2f} USD profit, "
                  f"arbed: {initial_price:.6f} -> {prices[0]:.6f}, "
                  f"arber resulting: {prices[1]:.6f}")
            if len(profit_breakpoints) == 1:
                break
            profit_breakpoints = profit_breakpoints[1:]


def arbitrage_gas() -> int:
    boa.env.fork(f"https://eth-mainnet.alchemyapi.io/v2/{os.environ['WEB3_ETHEREUM_MAINNET_ALCHEMY_API_KEY']}")
    arbitrage = boa.loads("""
# @version 0.3.10
interface ERC20:
    def approve(_to: address, _value: uint256): nonpayable
    def decimals() -> uint256: view
    def owner() -> address: view
interface Curve:
    def exchange(i: int128, j: int128, dx: uint256, min_dy: uint256): payable
    def coins(_i: uint256) -> address: view
pools: public(immutable(Curve[2]))
@external
def __init__():
    pools = [Curve(0x390f3595bCa2Df7d23783dFd126427CCeb997BF4), Curve(0x4DEcE678ceceb27446b35C672dC7d61F30bAD69E)]
    # Difference between uint256 and int128 does not allow to use for i in range(2):
    ERC20(pools[0].coins(0)).approve(pools[0].address, max_value(uint256))
    ERC20(pools[1].coins(1)).approve(pools[1].address, max_value(uint256))
@external
def arbitrage(amount0: uint256, amount1: uint256):
    pools[0].exchange(0, 1, amount0, 1)  # 0xdAC17F958D2ee523a2206206994597C13D831ec7
    pools[1].exchange(1, 0, amount1, 1)  # 0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E
@external
@view
def usdt_transfer_metadata() -> (address, address, Bytes[68], uint256, uint256):
    coin: ERC20 = ERC20(pools[0].coins(0))
    amount0: uint256 = 10 * 10 ** coin.decimals()
    amount1: uint256 = 10 ** ERC20(pools[1].coins(1)).decimals()
    return coin.address, coin.owner(),\
           _abi_encode(self, amount0, method_id=method_id("transfer(address,uint256)")),\
           amount0, amount1
    """)
    coin, coin_sender, coin_transfer_call, *amounts = arbitrage.usdt_transfer_metadata()
    boa.env.execute_code(coin, sender=coin_sender, data=coin_transfer_call)
    arbitrage.arbitrage(*amounts)
    return arbitrage._computation.get_gas_used()


if __name__ == "__main__":
    find_arbitrage_limit(1 - fees[0] / 10 ** 10)
    print(f"Gas needed for arbitrage: {arbitrage_gas()}")
