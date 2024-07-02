# pragma version 0.3.10
# pragma evm-version cancun

interface ERC20:
    def approve(_to: address, _value: uint256): nonpayable
    def transfer(_to: address, _value: uint256) -> bool: nonpayable
    def transferFrom(_from: address, _to: address, _value: uint256) -> bool: nonpayable
    def balanceOf(_owner: address) -> uint256: view
    def decimals() -> uint256: view

interface StableSwap:
    def get_p(i: uint256=0) -> uint256: view
    def price_oracle(i: uint256=0) -> uint256: view
    def get_balances() -> uint256[2]: view
    def exchange(i: int128, j: int128, _dx: uint256, _min_dy: uint256, _receiver: address = msg.sender) -> uint256: nonpayable
    def A_precise() -> uint256: view
    def fee() -> uint256: view
    def coins(i: uint256) -> ERC20: view

interface Regulator:
    def price_deviation() -> uint256: view

interface PegKeeper:
    def pool() -> StableSwap: view
    def IS_INVERSE() -> bool: view
    def update(_receiver: address = msg.sender) -> uint256: nonpayable

interface Morpho:
    def flashLoan(token: address, assets: uint256, data: Bytes[256]):nonpayable

struct Params:
    balances: uint256[2]
    decimals: uint256[2]
    p_o: uint256
    cur_p: uint256
    A: uint256
    fee: uint256
    is_inverse: bool

struct SandwichParams:
    amount: uint256
    i: int128
    pk: PegKeeper
    pool: StableSwap
    coin: ERC20
    receiver: address

REGULATOR: immutable(Regulator)
MORPHO: immutable(Morpho)

sandwich_params: transient(SandwichParams)

@external
def __init__(_regulator: Regulator, _morpho: Morpho, _pools: StableSwap[4]):
    REGULATOR = _regulator
    MORPHO = _morpho

    for pool in _pools:
        for i in range(2):
            pool.coins(i).approve(pool.address, max_value(uint256))


@view
@external
def get_params(pk: PegKeeper, _ng: bool) -> Params:
    pool: StableSwap = pk.pool()
    cur_p: uint256 = 0
    p_o: uint256 = 0
    if _ng:
        cur_p = pool.get_p(0)
        p_o = pool.price_oracle(0)
    else:
        cur_p = pool.get_p()
        p_o = pool.price_oracle()
    return Params({
        balances: pool.get_balances(),
        decimals: [pool.coins(0).decimals(), pool.coins(1).decimals()],
        p_o: p_o,
        cur_p: cur_p,
        A: pool.A_precise(),
        fee: pool.fee(),
        is_inverse: pk.IS_INVERSE()
    })


@external
def call(pk: PegKeeper, amount: uint256, i: int128, _receiver: address=msg.sender):
    if amount > 0:
        pool: StableSwap = pk.pool()
        coin: ERC20 = pool.coins(convert(i, uint256))
        self.sandwich_params = SandwichParams({
            amount: amount,
            i: i,
            pk: pk,
            pool: pool,
            coin: coin,
            receiver: _receiver,
        })
        MORPHO.flashLoan(coin.address, amount, b"")
        coin.transfer(_receiver, coin.balanceOf(self))
        return

    pk.update(_receiver)


@external
def onMorphoFlashLoan(assets: uint256, data: Bytes[256]):
    sp: SandwichParams = self.sandwich_params
    dy: uint256 = sp.pool.exchange(sp.i, 1-sp.i, sp.amount, 0)

    sp.pk.update(sp.receiver)

    sp.pool.exchange(1-sp.i, sp.i, dy, 0)

    sp.coin.approve(msg.sender, assets)


@external
def approve(_pool: StableSwap):
    _pool.coins(0).approve(_pool.address, max_value(uint256))
    _pool.coins(1).approve(_pool.address, max_value(uint256))
