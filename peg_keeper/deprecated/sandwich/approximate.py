import numpy as np
import matplotlib.pyplot as plt
from simulation import Curve
from copy import deepcopy
from scipy.optimize import minimize
from tqdm import tqdm

# Pool params
n = 2
CRVUSD_I = 1  # For 0 use (1 - share)
A = 500  # ALTER
fee = int(0.01 * 10 ** 8)  # ALTER: %
usd_amount = 2 * 10 ** 6  # ALTER: each token balance in equilibrium

CALLER_SHARE = 20  # %

# auxiliary
INITIAL_AMOUNT = usd_amount * 10 ** 18
BOUNDARY = int(.8 * INITIAL_AMOUNT)
SANDWICH_BOUNDARY = 3 * BOUNDARY
STEPS = 500

OPERATION = ["Provide", "Exchange"][0]  # ALTER

X_COORDINATE = ["Share", "Price"][1]  # ALTER
Y_COORDINATE = ["Amount", "Profit"][1]  # ALTER

# Plot
GAS_COST = 100  # ALTER: expected gas price for the manipulation in USD
SHARE_LIMIT = 10  # %

USE_SPECIFIC = True  # ALTER: calc a new line or use from the dict below
lines = {
    500: {
        int(0.01 * 10 ** 8): {
            "Provide": (
                (-399721741143539208, 257754518881445707),
                (395673649873780890, -224952787475105624)
            ),
            "Exchange": (
                (-219151167679233091, 143702027493939994),
                (242164993984940260, -129297051132283184)
            )
        }
    }
}


# -------------------------- Operations functionality ------------------------ #


def get_price(_curve):
    dx = 10 ** 18
    return dx / _curve.dy(CRVUSD_I, 1 - CRVUSD_I, dx)


def get_share(_curve):
    return _curve.x[CRVUSD_I] / _curve.x[1 - CRVUSD_I]


def update(_curve):
    """ Peg Keeper update """
    diff = _curve.x[CRVUSD_I] - _curve.x[1 - CRVUSD_I]
    amount = abs(diff) // 5
    if amount < 10 ** 18:
        return 0, 0, 0
    amounts = [0, 0]
    amounts[CRVUSD_I] = amount
    if diff > 0:
        lp_amount = _curve.remove_liquidity_imbalance(amounts, True)
    else:
        lp_amount = _curve.add_liquidity(amounts, True)

    vp = _curve.get_virtual_price()
    if diff > 0:
        # amount we had - amount needed
        profit = amount * 10 ** 18 // vp - lp_amount
        amount = -amount
    else:
        # amount received - amount needed in future
        profit = lp_amount - amount * 10 ** 18 // vp

    # debt change, full profit, caller profit
    return amount, profit, profit * CALLER_SHARE // 100


def sandwich(amount, _curve):
    if abs(amount) < INITIAL_AMOUNT // 10 ** 8:
        return 0
    i = 1 - CRVUSD_I if amount < 0 else CRVUSD_I
    amounts = [0] * n
    amounts[i] = abs(amount)
    if OPERATION == "Provide":
        tokens = _curve.add_liquidity(amounts, update_values=True)
    elif OPERATION == "Exchange":
        tokens = _curve.exchange(i, 1 - i, amounts[i])
    else:
        raise ValueError(f"Unknown OPERATION: {OPERATION}")

    *_, caller_profit = update(_curve)

    if OPERATION == "Provide":
        return tokens - _curve.remove_liquidity_imbalance(amounts) + caller_profit
    elif OPERATION == "Exchange":
        return _curve.exchange(1 - i, i, tokens) - amounts[i] + caller_profit


# ------------------------ Best solution functionality ----------------------- #


def find_best_sandwich(_curve):
    best_amount, best_profit = 0, 0
    for amount in range(-SANDWICH_BOUNDARY, SANDWICH_BOUNDARY, SANDWICH_BOUNDARY // 1_000):
        profit = sandwich(amount, deepcopy(_curve))
        if profit > best_profit:
            best_amount, best_profit = amount, profit
    return best_amount, best_profit


def find_best_sandwich_scipy(_curve, initial_guess=10 ** 5):
    def neg_sandwich(x):
        return -sandwich(int(x[0] * 10 ** 18), deepcopy(_curve))

    max_flash_result = minimize(
        neg_sandwich,
        x0=initial_guess / 10 ** 18,
        bounds=((-SANDWICH_BOUNDARY / 10 ** 18, SANDWICH_BOUNDARY / 10 ** 18),),
    )
    amount = int(max_flash_result.x[0] * 10 ** 18)
    profit = -max_flash_result.fun
    return amount, profit


# --------------------- Line approximation functionality --------------------- #


def straight_share(share):
    return (share < 1) ^ (CRVUSD_I == 0)


def get_lines(shares, amounts, D):
    """
    y = ax + b
    1) y1 - y0 = a(x1 - x0)
    2) y = 0 <=> b = -ax
    """
    mid = len(shares) // 2
    while abs(shares[mid] - 1) > 0.05:
        mid -= 1
    while abs(shares[mid] - 1) > 0.05:
        mid += 1
    print(mid, amounts[mid], shares[mid])
    first0, last0 = mid, mid
    while abs(amounts[first0]) < 10 ** 18:
        first0 -= 1
    while abs(amounts[last0]) < 10 ** 18:
        last0 += 1

    def get_ab(i, j):
        if straight_share(shares[i]):
            angle = (amounts[i] - amounts[j]) / (shares[i] - shares[j])
            b = -angle * shares[j]
        else:
            share_i, share_j = 1 / shares[i], 1 / shares[j]
            angle = (amounts[i] - amounts[j]) / (share_i - share_j)
            b = -angle * share_i
        return int(angle) * 10 ** 18 // D, int(b) * 10 ** 18 // D

    return get_ab(first0 - STEPS // 10, first0), get_ab(last0, last0 + STEPS // 5)  # ALTER: steps


def print_line(a, b, side):
    if side == 'left':
        print(
            f"amount = D * ({a} * crvUSD_balance / coin_balance + {b}) // 10 ** 18"
            f" if share < 1"
        )
    else:
        print(
            f"amount = D * ({a} * coin_balance / crvUSD_balance + {b}) // 10 ** 18"
            f" if share > 1"
        )


def get_amount(line_left, line_right, share, D):
    if straight_share(share):
        amount = int(line_left[0] * share) + line_left[1]
        amount_mid = line_left[0] + line_left[1]
    else:
        amount = int(line_right[0] / share) + line_right[1]
        amount_mid = line_right[0] + line_right[1]
    amount = amount * D // 10 ** 18
    if abs(amount) > SANDWICH_BOUNDARY:
        return 0
    return amount if amount * amount_mid < 0 else 0


# ------------------------------ Main functions ------------------------------ #


def preset_curve(dx):
    curve = Curve(A, 0, n, tokens=0, fee=fee, admin_fee=5 * 10 ** 9)
    curve.add_liquidity([INITIAL_AMOUNT] * n, True)
    i = 0 if dx < 0 else 1
    curve.exchange(i, 1 - i, abs(dx))
    return curve


def approximate_sandwich(plot=True):
    xs = []
    ys = []
    shares = []
    amounts = []
    D = 0
    for dx in tqdm(np.arange(-BOUNDARY, BOUNDARY, 2 * BOUNDARY // STEPS), desc="Real values"):
        curve = preset_curve(dx)
        D = curve.D()

        initial_price = get_price(curve)
        initial_share = curve.x[CRVUSD_I] / sum(curve.x)
        shares.append(get_share(curve))

        amount, profit = find_best_sandwich(curve)
        amount, profit = find_best_sandwich_scipy(curve, amount)
        amounts.append(amount)

        xs.append(
            initial_share * 100 if X_COORDINATE == "Share" else initial_price
        )
        ys.append(
            (amount if Y_COORDINATE == "Amount" else profit) / 10 ** 18
        )

    line_left, line_right = lines[A][fee][OPERATION] if USE_SPECIFIC else get_lines(shares, amounts, D)
    print_line(*line_left, "left")
    print_line(*line_right, "right")
    if plot:
        ys_approx = []
        for dx in tqdm(np.arange(-BOUNDARY, BOUNDARY, 2 * BOUNDARY // STEPS), desc="Approximate values"):
            curve = preset_curve(dx)

            amount = get_amount(line_left, line_right, get_share(curve), curve.D())
            profit = sandwich(amount, deepcopy(curve))

            ys_approx.append(
                (amount if Y_COORDINATE == "Amount" else profit) / 10 ** 18
            )

        plt.plot(xs, ys, alpha=.7, label=f"Best")
        plt.plot(xs, ys_approx, alpha=.7, label=f"Approximate")

        if X_COORDINATE == "Share":
            plt.xlim((SHARE_LIMIT, 100 - SHARE_LIMIT))
        if Y_COORDINATE == "Profit":
            plt.axhline(y=GAS_COST, linestyle="dashed", label=f"Gas cost")

        plt.title(f"Peg Keeper sandwich with A={A}, fee={fee / 10 ** 8:.2f}%")
        plt.xlabel(X_COORDINATE + " of crvUSD")
        plt.ylabel(Y_COORDINATE)
        plt.legend()
        # plt.savefig(f"images/{Y_COORDINATE.lower()}.jpg")
        plt.show()

    return line_left, line_right


if __name__ == "__main__":
    approximate_sandwich()
