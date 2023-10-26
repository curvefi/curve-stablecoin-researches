# Depeg
It is possible that coin used in Peg Keeper depegs, e.g. USDC in March 2023.
If the price comes back with time there are no worries
but in case it is stuck permanently there are risks for Stablecoin.
Peg Keeper will provide Stablecoin to the pool and posses LP tokens.
Those LP tokens can be redeemed only when the price of Stablecoin goes beneath the depegged coin.

## Theoretical scenario
__Note.__
This is theoretical only.
There are many assumptions and parameters needed to be taken into consideration
like ratio of excessive debt to TVL (e.g. 100k vs 1B) or MM behaviour.

0. USDT permanently depegs
1. USDTPegKeeper has excessive debt, crvUSD is overvalued
2. Selling pressure, other PegKeepers empty
3. Discounted crvUSD  
4. 
- LLAMMA soft-liquidates current tick
- Higher rate, loans are returned, TVL shrinks
5. crvUSD price reaches USDT
6. Going below USDT makes USDTPegKeeper to return debt and become safu,
BUT! those selling below will "buy out" USDT to save crvUSD

Main assumptions:
1. Oracles will not be manipulated with depegs and possible TVL shrinks (AggregateStablePrice2 manages these)
2. All excessive liquidity will be eventually dumped

## Salvation
In case part of the debt becomes insolvent, one(like DAO) can take the penalty of market's wrath and buy it out.
```
Set a new Regulator which allows to withdraw
Set fee=0 for the pool

Move the price in pool (here some fees might be taken for sandwich amount)
Call PegKeeper.update()
Move the price back
```
In result, sacrifice will pay the ransom of debt atoning sins of crvUSD.
> For it is by vote you have been saved, through faith — and this is not from yourselves,
> it is the gift of DAO — not by weak hands, so that no one can rug.
