## About
PegKeeperV2 has `price_deviation` check that stops PegKeepers to update if price went too far away from oracle price.
But from incident of massive liquidations happened in June this becomes a problem for crvUSD to peg.
There is a possibility to mitigate this check by sandwiching PegKeeper call and earning extra money.
This dir/ is devoted to an example of such bot.
