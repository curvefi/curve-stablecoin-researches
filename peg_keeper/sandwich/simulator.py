from copy import deepcopy

PRECISION = 10 ** 18
FEE_DENOMINATOR = 10 ** 10
A_PRECISION = 100
ADMIN_FEE = 5000000000


class Curve:
    def __init__(self, params):
        self.balances = params[0]
        self.rate_multipliers = [10 ** (18 - params[1][i]) for i in range(2)]
        self.p_o = params[2]
        self.initial_p = params[3]
        self.A = params[4]
        self.fee = params[5]
        self.is_inverse = params[6]

    def exchange(self, i, j, _dx):
        rates = self.rate_multipliers
        old_balances = deepcopy(self.balances)
        xp = self._xp_mem(rates, old_balances)

        x = xp[i] + _dx * rates[i] // PRECISION

        amp = self.A
        D = self.get_D(xp, amp)
        y = self.get_y(i, j, x, xp, amp, D)

        dy = xp[j] - y - 1  # -1 just in case there were some rounding errors
        dy_fee = dy * self.fee // FEE_DENOMINATOR

        # Convert all to real units
        dy = (dy - dy_fee) * PRECISION // rates[j]

        # xp is not used anymore, so we reuse it for price calc
        xp[i] = x
        xp[j] = y

        dy_admin_fee = dy_fee * ADMIN_FEE // FEE_DENOMINATOR
        dy_admin_fee = dy_admin_fee * PRECISION // rates[j]

        # Change balances exactly in same way as we change actual ERC20 coin amounts
        self.balances[i] = old_balances[i] + _dx
        # When rounding errors happen, we undercharge admin fee in favor of LP
        self.balances[j] = old_balances[j] - dy - dy_admin_fee

        return dy

    def _xp_mem(self, _rates, _balances):
        return [_rates[i] * _balances[i] // PRECISION for i in range(2)]

    def get_D(self, _xp, _amp):
        S = sum(_xp)
        if S == 0:
            return 0

        D = S
        Ann = _amp * 2
        for i in range(255):
            D_P = D * D // _xp[0] * D // _xp[1] // 4
            Dprev = D
            D = (Ann * S // A_PRECISION + D_P * 2) * D // ((Ann - A_PRECISION) * D // A_PRECISION + 3 * D_P)
            # Equality with the precision of 1
            if D > Dprev:
                if D - Dprev <= 1:
                    return D
            else:
                if Dprev - D <= 1:
                    return D
        # convergence typically occurs in 4 rounds or less, this should be unreachable!
        # if it does happen the pool is borked and LPs can withdraw via `remove_liquidity`
        raise

    def get_y(self, i, j, x, xp, _amp, _D):
        amp = _amp
        D = _D
        if _D == 0:
            amp = self.A
            D = self.get_D(xp, amp)
        S_ = 0
        _x = 0
        y_prev = 0
        c = D
        Ann = amp * 2

        for _i in range(2):
            if _i == i:
                _x = x
            elif _i != j:
                _x = xp[_i]
            else:
                continue
            S_ += _x
            c = c * D // (_x * 2)

        c = c * D * A_PRECISION // (Ann * 2)
        b = S_ + D * A_PRECISION // Ann  # - D
        y = D

        for _i in range(255):
            y_prev = y
            y = (y * y + c) // (2 * y + b - D)
            # Equality with the precision of 1
            if y > y_prev:
                if y - y_prev <= 1:
                    return y
            else:
                if y_prev - y <= 1:
                    return y
        raise

    def _get_p(self, xp, amp, D):
        # dx_0 / dx_1 only, however can have any number of coins in pool
        ANN = amp * 2
        Dr = D // 4
        for i in range(2):
            Dr = Dr * D // xp[i]
        return 10 ** 18 * (ANN * xp[0] // A_PRECISION + Dr * xp[0] // xp[1]) // (ANN * xp[0] // A_PRECISION + Dr)

    def get_p(self):
        amp = self.A
        xp = self._xp_mem(self.rate_multipliers, self.balances)
        D = self.get_D(xp, amp)
        return self._get_p(xp, amp, D)
