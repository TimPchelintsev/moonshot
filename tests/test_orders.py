# Copyright 2018 QuantRocket LLC - All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# To run: python3 -m unittest discover -s tests/ -p test_*.py -t . -v

import unittest
from unittest.mock import patch
import pandas as pd
from moonshot import Moonshot
from moonshot.exceptions import MoonshotParameterError

class OrdersTestCase(unittest.TestCase):
    """
    Test cases related to creating orders.
    """

    def test_child_orders(self):
        """
        Tests that the orders DataFrame is correct when using orders_to_child_orders.
        """

        class BuyBelow10ShortAbove10Overnight(Moonshot):
            """
            A basic test strategy that buys below 10 and shorts above 10.
            """
            CODE = "long-short-10"

            def prices_to_signals(self, prices):
                long_signals = prices.loc["Open"] <= 10
                short_signals = prices.loc["Open"] > 10
                signals = long_signals.astype(int).where(long_signals, -short_signals.astype(int))
                return signals

            def signals_to_target_weights(self, signals, prices):
                weights = self.allocate_fixed_weights(signals, 0.25)
                return weights

            def order_stubs_to_orders(self, orders, prices):
                orders["Exchange"] = "SMART"
                orders["OrderType"] = 'MKT'
                orders["Tif"] = "Day"

                child_orders = self.orders_to_child_orders(orders)
                child_orders.loc[:, "OrderType"] = "MOC"

                orders = pd.concat([orders,child_orders])
                return orders

        def mock_get_historical_prices(*args, **kwargs):

            dt_idx = pd.date_range(end=pd.Timestamp.today(), periods=3, normalize=True)
            fields = ["Open"]
            idx = pd.MultiIndex.from_product([fields, dt_idx], names=["Field", "Date"])

            prices = pd.DataFrame(
                {
                    12345: [
                        # Open
                        9,
                        11,
                        10.50
                    ],
                    23456: [
                        # Open
                        9.89,
                        11,
                        8.50,
                    ],
                 },
                index=idx
            )

            master_fields = ["Timezone", "SecType", "Currency", "PriceMagnifier", "Multiplier"]
            idx = pd.MultiIndex.from_product((master_fields, [dt_idx[0]]), names=["Field", "Date"])
            securities = pd.DataFrame(
                {
                    12345: [
                        "America/New_York",
                        "STK",
                        "USD",
                        None,
                        None
                    ],
                    23456: [
                        "America/New_York",
                        "STK",
                        "USD",
                        None,
                        None,
                    ]
                },
                index=idx
            )
            return pd.concat((prices, securities))

        def mock_download_account_balances(f, **kwargs):
            balances = pd.DataFrame(dict(Account=["U123"],
                                         NetLiquidation=[85000],
                                         Currency=["USD"]))
            balances.to_csv(f, index=False)
            f.seek(0)

        def mock_download_exchange_rates(f, **kwargs):
            rates = pd.DataFrame(dict(BaseCurrency=["USD"],
                                      QuoteCurrency=["USD"],
                                         Rate=[1.0]))
            rates.to_csv(f, index=False)
            f.seek(0)

        def mock_list_positions(**kwargs):
            return []

        with patch("moonshot.strategies.base.get_historical_prices", new=mock_get_historical_prices):
            with patch("moonshot.strategies.base.download_account_balances", new=mock_download_account_balances):
                with patch("moonshot.strategies.base.download_exchange_rates", new=mock_download_exchange_rates):
                    with patch("moonshot.strategies.base.list_positions", new=mock_list_positions):

                        orders = BuyBelow10ShortAbove10Overnight().trade({"U123": 0.5})

        self.assertSetEqual(
            set(orders.columns),
            {'ConId',
             'Account',
             'Action',
             'OrderRef',
             'TotalQuantity',
             'Exchange',
             'OrderId',
             'ParentId',
             'OrderType',
             'Tif'}
        )
        # replace nan with 'nan' to allow equality comparisons
        orders = orders.where(orders.notnull(), 'nan')

        self.assertListEqual(
            orders.to_dict(orient="records"),
            [
                {
                    'Account': 'U123',
                    'Action': 'SELL',
                    'ConId': 12345,
                    'Exchange': 'SMART',
                    'OrderId': 0.0,
                    'OrderRef': 'long-short-10',
                    'OrderType': 'MKT',
                    'ParentId': 'nan',
                    'Tif': 'Day',
                    'TotalQuantity': 1012
                },
                {
                    'Account': 'U123',
                    'Action': 'BUY',
                    'ConId': 23456,
                    'Exchange': 'SMART',
                    'OrderId': 1.0,
                    'OrderRef': 'long-short-10',
                    'OrderType': 'MKT',
                    'ParentId': 'nan',
                    'Tif': 'Day',
                    'TotalQuantity': 1250
                },
                {
                    'Account': 'U123',
                    'Action': 'BUY',
                    'ConId': 12345,
                    'Exchange': 'SMART',
                    'OrderId': 'nan',
                    'OrderRef': 'long-short-10',
                    'OrderType': 'MOC',
                    'ParentId': 0.0,
                    'Tif': 'Day',
                    'TotalQuantity': 1012
                },
                {
                    'Account': 'U123',
                    'Action': 'SELL',
                    'ConId': 23456,
                    'Exchange': 'SMART',
                    'OrderId': 'nan',
                    'OrderRef': 'long-short-10',
                    'OrderType': 'MOC',
                    'ParentId': 1.0,
                    'Tif': 'Day',
                    'TotalQuantity': 1250
                }
            ]
        )

    def test_reindex_like_orders(self):
        """
        Tests that the orders DataFrame is correct when using reindex_like_orders.
        """

        class BuyBelow10ShortAbove10Overnight(Moonshot):
            """
            A basic test strategy that buys below 10 and shorts above 10.
            """
            CODE = "long-short-10"

            def prices_to_signals(self, prices):
                long_signals = prices.loc["Close"] <= 10
                short_signals = prices.loc["Close"] > 10
                signals = long_signals.astype(int).where(long_signals, -short_signals.astype(int))
                return signals

            def signals_to_target_weights(self, signals, prices):
                weights = self.allocate_fixed_weights(signals, 0.25)
                return weights

            def order_stubs_to_orders(self, orders, prices):
                closes = prices.loc["Close"]
                prior_closes = closes.shift()
                prior_closes = self.reindex_like_orders(prior_closes, orders)

                orders["Exchange"] = "SMART"
                orders["OrderType"] = 'LMT'
                orders["LmtPrice"] = prior_closes
                orders["Tif"] = "Day"
                return orders

        def mock_get_historical_prices(*args, **kwargs):

            dt_idx = pd.date_range(end=pd.Timestamp.today(), periods=3, normalize=True)
            fields = ["Close"]
            idx = pd.MultiIndex.from_product([fields, dt_idx], names=["Field", "Date"])

            prices = pd.DataFrame(
                {
                    12345: [
                        # Close
                        9,
                        11,
                        10.50
                    ],
                    23456: [
                        # Close
                        9.89,
                        11.25,
                        8.50,
                    ],
                 },
                index=idx
            )

            master_fields = ["Timezone", "SecType", "Currency", "PriceMagnifier", "Multiplier"]
            idx = pd.MultiIndex.from_product((master_fields, [dt_idx[0]]), names=["Field", "Date"])
            securities = pd.DataFrame(
                {
                    12345: [
                        "America/New_York",
                        "STK",
                        "USD",
                        None,
                        None
                    ],
                    23456: [
                        "America/New_York",
                        "STK",
                        "USD",
                        None,
                        None,
                    ]
                },
                index=idx
            )
            return pd.concat((prices, securities))

        def mock_download_account_balances(f, **kwargs):
            balances = pd.DataFrame(dict(Account=["U123"],
                                         NetLiquidation=[85000],
                                         Currency=["USD"]))
            balances.to_csv(f, index=False)
            f.seek(0)

        def mock_download_exchange_rates(f, **kwargs):
            rates = pd.DataFrame(dict(BaseCurrency=["USD"],
                                      QuoteCurrency=["USD"],
                                         Rate=[1.0]))
            rates.to_csv(f, index=False)
            f.seek(0)

        def mock_list_positions(**kwargs):
            return []

        with patch("moonshot.strategies.base.get_historical_prices", new=mock_get_historical_prices):
            with patch("moonshot.strategies.base.download_account_balances", new=mock_download_account_balances):
                with patch("moonshot.strategies.base.download_exchange_rates", new=mock_download_exchange_rates):
                    with patch("moonshot.strategies.base.list_positions", new=mock_list_positions):

                        orders = BuyBelow10ShortAbove10Overnight().trade({"U123": 0.5})

        self.assertSetEqual(
            set(orders.columns),
            {'ConId',
             'Account',
             'Action',
             'OrderRef',
             'TotalQuantity',
             'Exchange',
             'LmtPrice',
             'OrderType',
             'Tif'}
        )

        self.assertListEqual(
            orders.to_dict(orient="records"),
            [
                {
                    'ConId': 12345,
                    'Account': 'U123',
                    'Action': 'SELL',
                    'OrderRef': 'long-short-10',
                    'TotalQuantity': 1012,
                    'Exchange': 'SMART',
                    'OrderType': 'LMT',
                    'LmtPrice': 11.0,
                    'Tif': 'Day'
                },
                {
                    'ConId': 23456,
                    'Account': 'U123',
                    'Action': 'BUY',
                    'OrderRef': 'long-short-10',
                    'TotalQuantity': 1250,
                    'Exchange': 'SMART',
                    'OrderType': 'LMT',
                    'LmtPrice': 11.25,
                    'Tif': 'Day'
                }
            ]
        )