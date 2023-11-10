SELECT
  SQRT(AVG( POWER(usdt_diff, 2) )) AS usdt_ed,
  SQRT(AVG( POWER(usdc_diff, 2) )) AS usdc_ed,
  SQRT(AVG( POWER(usdp_diff, 2) )) AS usdp_ed,
  SQRT(AVG( POWER(tusd_diff, 2) )) AS tusd_ed
FROM (
  SELECT
    ABS(usdt - LAG(usdt, 1, 0) OVER (ORDER BY action_delayed)) AS usdt_diff,
    ABS(usdc - LAG(usdc, 1, 0) OVER (ORDER BY action_delayed)) AS usdc_diff,
    ABS(usdp - LAG(usdp, 1, 0) OVER (ORDER BY action_delayed)) AS usdp_diff,
    ABS(tusd - LAG(tusd, 1, 0) OVER (ORDER BY action_delayed)) AS tusd_diff
  FROM (
    SELECT
      action_delayed,
      MAX(usdt) as usdt,
      MAX(usdc) as usdc,
      MAX(usdp) as usdp,
      MAX(tusd) as tusd
    FROM (
      SELECT
        DATE_TRUNC('minute', minute) AS action_delayed,
        CASE "contract_address"
          WHEN 0xdAC17F958D2ee523a2206206994597C13D831ec7
          THEN price
        END AS "usdt",
        CASE "contract_address"
          WHEN 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48
          THEN price
        END AS "usdc",
        CASE
          WHEN "contract_address" = 0x8E870D67F660D95d5be530380D0eC0bd388289E1
          THEN price
        END AS "usdp",
        CASE
          WHEN "contract_address" = 0x0000000000085d4780b73119b644ae5ecd22b376
          THEN price
        END AS "tusd"
      FROM prices."usd"
      WHERE
        "contract_address" IN (0xdAC17F958D2ee523a2206206994597C13D831ec7, 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48, 0x8E870D67F660D95d5be530380D0eC0bd388289E1, 0x0000000000085d4780b73119b644ae5ecd22b376)
        AND minute > CURRENT_TIMESTAMP - INTERVAL '180' day
        AND minute(minute) % 10 = 0
      GROUP BY
        1,
        2,
        3,
        4,
        5
    ) AS a
    GROUP BY action_delayed
  ) AS b
  OFFSET 1
) AS c
