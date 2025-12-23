#!/usr/bin/env python3

import json
import logging
import os
import re
import signal
import sys
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Tuple, cast

import click
from dacite import Config, from_dict
from waybar import glyphs, util
from waybar.data import stock_quotes
from yahooquery import Ticker

sys.stdout.reconfigure(line_buffering=True)  # type: ignore

logger: logging.Logger

DEFAULT_SYMBOLS = ["GOOG", "AAPL"]


class StockQuotes:
    def __init__(self, **kwargs) -> None:
        self.success: bool = True
        self.error: str | None = None

        self.symbols = kwargs.get("symbols", [])
        self.logger = util.configure_logger(
            debug=False, name=os.path.basename(__file__), logfile=logfile
        )
        self.data: list[stock_quotes.QuoteData] = []
        self.updated: str | None = None

    def _validate_symbols(self):
        pass

    def _sanitize_phone_number(self, phone_number: str) -> str:
        parts = re.findall(r"(\d+)", phone_number)
        if parts and len(parts) == 3:
            return "-".join(parts)
        return phone_number

    def _get_change_and_change_percent(
        self, current: float, previous: float
    ) -> Tuple[str, str]:
        amount = current - previous
        percent = (current - previous) / previous * 100

        symbol = "+" if amount > 0 else "-"

        change_amt = f"{symbol}{util.pad_float(abs(amount))}"
        change_pct = f"{symbol}{util.pad_float(abs(percent))}%"

        return change_amt, change_pct

    def to_dollar(self, number: int | float = 0.0, symbol: str = "$") -> str:
        """
        Convert the specified integer as a dollar based format, e.g., $2,000.
        """
        return f"{symbol}{self.numerize(number=number, as_int=False)}"

    def numerize(self, number: float | int = 0, *, as_int: bool = False) -> str:
        abs_number = abs(number)
        sign = "-" if number < 0 else ""

        # Under 1M → actual number
        if abs_number < 1_000_000:
            if as_int:
                return f"{int(number):,}"
            return f"{number:,.2f}"

        # 1M and up → numerized
        if abs_number >= 1_000_000_000_000:
            value, suffix = abs_number / 1_000_000_000_000, "T"
        elif abs_number >= 1_000_000_000:
            value, suffix = abs_number / 1_000_000_000, "B"
        else:
            value, suffix = abs_number / 1_000_000, "M"

        if as_int:
            return f"{sign}{int(value)}{suffix}"

        return f"{sign}{value:.2f}{suffix}"

    def numerize_old(self, number: float | int = 0) -> str:
        """
        Convert something like 1000000000 to 1B.
        """
        abs_number = abs(number)
        if abs_number >= 1000000000000:
            return f"{abs_number / 1000000000000:.2f}T"
        elif abs_number >= 1000000000:
            return f"{abs_number / 1000000000:.2f}B"
        elif abs_number >= 1000000:
            return f"{abs_number / 1000000:.2f}M"
        elif abs_number >= 1000:
            return f"{abs_number / 1000:.2f}K"
        elif abs_number < 0 and abs_number > -10000:
            return f"{abs_number / -1000:.2f}K"
        else:
            return str(number)

    def get_quotes(self):
        quotes_map: dict[str, stock_quotes.QuoteData] = {}

        for symbol in self.symbols:
            quotes_map[symbol] = stock_quotes.QuoteData(symbol=symbol)

        try:
            self.ticker = Ticker(self.symbols)
        except Exception as e:
            self.logger.error(f"failed to get quote data: {e}")
            self.success = False
            self.error = str(e)
            return

        self.logger.info("refreshing data")
        quotes_dict = cast(dict[str, dict], self.ticker.all_modules)
        for symbol, data in quotes_dict.items():
            # Preprocess some stuff that dataclass doesn't like
            try:
                if "52WeekChange" in data["defaultKeyStatistics"]:
                    data["defaultKeyStatistics"]["fiftyTwoWeekChange"] = data[
                        "defaultKeyStatistics"
                    ]["52WeekChange"]
                    del data["defaultKeyStatistics"]["52WeekChange"]
            except Exception:
                pass

            for idx, trend_item in enumerate(data["earningsTrend"]["trend"]):
                if "epsTrend" in data["earningsTrend"]["trend"][idx]:
                    old_eps_trend = data["earningsTrend"]["trend"][idx]["epsTrend"]
                    try:
                        data["earningsTrend"]["trend"][idx]["epsTrend"] = {
                            "thirtyDaysAgo": old_eps_trend["30daysAgo"],
                            "sixtyDaysAgo": old_eps_trend["60daysAgo"],
                            "sevenDaysAgo": old_eps_trend["7daysAgo"],
                            "ninetyDaysAgo": old_eps_trend["90daysAgo"],
                            "current": old_eps_trend["current"],
                            "epsTrendCurrency": old_eps_trend["epsTrendCurrency"],
                        }
                    except Exception:
                        pass

            all_modules = from_dict(
                data_class=stock_quotes.AllModules,
                data=data,
                config=Config(type_hooks={datetime: datetime.fromisoformat}),
            )
            if all_modules.assetProfile.phone:
                all_modules.assetProfile.phone = self._sanitize_phone_number(
                    phone_number=all_modules.assetProfile.phone
                )

            quotes_map[symbol] = stock_quotes.QuoteData(
                symbol=symbol,
                currency_symbol=all_modules.price.currencySymbol
                if all_modules.price.currencySymbol
                else "$",
                assetProfile=all_modules.assetProfile,
                balanceSheetHistory=all_modules.balanceSheetHistory,
                balanceSheetHistoryQuarterly=all_modules.balanceSheetHistoryQuarterly,
                calendarEvents=all_modules.calendarEvents,
                cashflowStatementHistory=all_modules.cashflowStatementHistory,
                cashFlowStatementHistoryQuarterly=all_modules.cashFlowStatementHistoryQuarterly,
                defaultKeyStatistics=all_modules.defaultKeyStatistics,
                earnings=all_modules.earnings,
                earningsHistory=all_modules.earningsHistory,
                earningsTrend=all_modules.earningsTrend,
                financialData=all_modules.financialData,
                fundOwnership=all_modules.fundOwnership,
                indexTrend=all_modules.indexTrend,
                industryTrend=all_modules.industryTrend,
                insiderHolders=all_modules.insiderHolders,
                insiderTransactions=all_modules.insiderTransactions,
                institutionOwnership=all_modules.institutionOwnership,
                majorHoldersBreakdown=all_modules.majorHoldersBreakdown,
                netSharePurchaseActivity=all_modules.netSharePurchaseActivity,
                pageViews=all_modules.pageViews,
                quoteType=all_modules.quoteType,
                price=all_modules.price,
                recommendationTrend=all_modules.recommendationTrend,
                secFilings=all_modules.secFilings,
                summaryDetail=all_modules.summaryDetail,
                summaryProfile=all_modules.summaryProfile,
                upgradeDowngradeHistory=all_modules.upgradeDowngradeHistory,
            )

            quotes_dict = cast(dict[str, dict], self.ticker.quotes)
            if quotes_map[symbol]:
                for symbol, item in quotes_dict.items():
                    quotes = from_dict(
                        data_class=stock_quotes.Quotes,
                        data=cast(dict, item),
                        config=Config(type_hooks={datetime: datetime.fromisoformat}),
                    )
                    quotes_map[symbol].quotes = quotes

            for symbol, item in self.ticker.technical_insights.items():
                if quotes_map[symbol]:
                    technical_insights = from_dict(
                        data_class=stock_quotes.TechnicalInsights,
                        data=cast(dict, item),
                        config=Config(type_hooks={datetime: datetime.fromisoformat}),
                    )
                    quotes_map[symbol].technicalInsights = technical_insights

        for symbol, data in quotes_map.items():
            if (
                data.financialData.currentPrice
                and data.price.regularMarketPreviousClose
            ):
                change_amt, change_pct = self._get_change_and_change_percent(
                    current=data.financialData.currentPrice,
                    previous=data.price.regularMarketPreviousClose,
                )

                quotes_map[symbol].current = data.financialData.currentPrice
                quotes_map[symbol].previous = data.price.regularMarketPreviousClose
                quotes_map[symbol].change = change_amt
                quotes_map[symbol].change_pct = change_pct
            # else:
            #     del quotes_map[symbol]

        if len(quotes_map) <= 0:
            self.logger.error("No quote data found")
            self.success = False
            self.error = "No quote data found"
            return

        if len(quotes_map.keys()) < len(self.symbols):
            missing = list(set(self.symbols).difference(quotes_map.keys()))
            self.logger.error(
                f"the following symbols were not found in the results set: {','.join(missing)}"
            )

        self.logger.info("refresh complete")
        self.updated = util.get_human_timestamp()

        for _, quote in quotes_map.items():
            self.data.append(quote)


cache_dir = util.get_cache_directory()
condition = threading.Condition()
context_settings = dict(help_option_names=["-h", "--help"])
format_index: int = 0
logfile = cache_dir / "waybar-stock-quotes.log"
needs_fetch: bool = False
needs_redraw: bool = False
quotes: StockQuotes = StockQuotes()

formats: list[int] = []

update_event = threading.Event()


def refresh_handler(_signum: int, _frame: object | None):
    global needs_fetch, needs_redraw
    logging.info("received SIGHUP — re-fetching data")
    with condition:
        needs_fetch = True
        needs_redraw = True
        condition.notify()


def toggle_format(_signum: int, _frame: object | None):
    global formats, format_index, needs_redraw, logger

    format_index = (format_index + 1) % len(formats)
    if quotes.data and type(quotes.data) is list:
        symbol = quotes.data[format_index].symbol
    else:
        symbol = format_index + 1
    logger.info(f"received SIGUSR1 - switching output format to {symbol}")
    with condition:
        needs_redraw = True
        condition.notify()


_ = signal.signal(signal.SIGHUP, refresh_handler)
_ = signal.signal(signal.SIGUSR1, toggle_format)


def generate_tooltip():
    global format_index, quotes, logger

    q = quotes.data[format_index]

    logger.debug(f"entering with symbol={q.symbol}")
    tooltip: list[str] = []
    company_info: OrderedDict[str, str | int | float] = OrderedDict()
    if q.price.longName:
        company_info["Company"] = q.price.longName
    if q.assetProfile.website:
        company_info["Web Site"] = q.assetProfile.website
        if (
            q.summaryProfile.address1
            and q.summaryProfile.city
            and q.summaryProfile.state
            and q.summaryProfile.zip
        ):
            company_info["Location"] = (
                f"{q.summaryProfile.address1}, {q.summaryProfile.city}, {q.summaryProfile.state}, {q.summaryProfile.zip}"
            )
        if q.assetProfile.phone:
            company_info["Phone"] = q.assetProfile.phone
        if q.assetProfile.fullTimeEmployees:
            company_info["FT Employees"] = quotes.numerize(
                number=q.assetProfile.fullTimeEmployees, as_int=True
            )
        if q.price.exchangeName:
            company_info["Exchange"] = q.price.exchangeName

    if len(company_info) > 0:
        tooltip.append("Company Info:")
        max_key_length = 0
        for key in company_info.keys():
            max_key_length = len(key) if len(key) > max_key_length else max_key_length

        for key, value in company_info.items():
            tooltip.append(f"  {key:{max_key_length}} {value}")

        if len(tooltip) > 0:
            tooltip.append("")

    key_stats: OrderedDict = OrderedDict()
    if q.summaryDetail.open:
        key_stats["Open"] = quotes.to_dollar(q.summaryDetail.open)
    if q.summaryDetail.dayHigh:
        key_stats["Day High"] = quotes.to_dollar(
            number=q.summaryDetail.dayHigh, symbol=q.currency_symbol
        )
    if q.summaryDetail.dayLow:
        key_stats["Day Low"] = quotes.to_dollar(
            number=q.summaryDetail.dayLow, symbol=q.currency_symbol
        )
    if q.summaryDetail.previousClose:
        key_stats["Previous Close"] = quotes.to_dollar(
            number=q.summaryDetail.previousClose,
            symbol=q.currency_symbol,
        )
    if q.summaryDetail.averageVolume10days:
        key_stats["10 Day Average Volume"] = quotes.numerize(
            q.summaryDetail.averageVolume10days
        )
    # 52 Week
    if q.summaryDetail.fiftyTwoWeekLow and q.summaryDetail.fiftyTwoWeekHigh:
        low = quotes.to_dollar(
            number=q.summaryDetail.fiftyTwoWeekLow,
            symbol=q.currency_symbol,
        )
        high = quotes.to_dollar(
            number=q.summaryDetail.fiftyTwoWeekHigh,
            symbol=q.currency_symbol,
        )
        key_stats["52 Week Range"] = f"{low} - {high}"
    if q.summaryDetail.fiftyTwoWeekLow:
        key_stats["52 Week Low"] = quotes.to_dollar(
            number=q.summaryDetail.fiftyTwoWeekLow,
            symbol=q.currency_symbol,
        )
    if q.quotes.fiftyTwoWeekLowChange:
        key_stats["52 Week Low Change"] = quotes.to_dollar(
            number=q.quotes.fiftyTwoWeekLowChange,
            symbol=q.currency_symbol,
        )
    if q.quotes.fiftyTwoWeekLowChangePercent:
        key_stats["52 Week Low Change %"] = util.float_to_pct(
            number=q.quotes.fiftyTwoWeekLowChangePercent,
        )
    if q.summaryDetail.fiftyTwoWeekHigh:
        key_stats["52 Week High"] = quotes.to_dollar(
            number=q.summaryDetail.fiftyTwoWeekHigh,
            symbol=q.currency_symbol,
        )
    if q.quotes.fiftyTwoWeekHighChange:
        key_stats["52 Week High Change"] = quotes.to_dollar(
            number=q.quotes.fiftyTwoWeekHighChange,
            symbol=q.currency_symbol,
        )
    if q.quotes.fiftyTwoWeekHighChangePercent:
        key_stats["52 Week High Change %"] = util.float_to_pct(
            number=q.quotes.fiftyTwoWeekHighChangePercent,
        )
    if q.defaultKeyStatistics.fiftyTwoWeekChange:
        key_stats["52 Week Change"] = quotes.to_dollar(
            number=q.defaultKeyStatistics.fiftyTwoWeekChange,
            symbol=q.currency_symbol,
        )
    if q.quotes.fiftyTwoWeekChangePercent:
        key_stats["52 Week Change %"] = util.float_to_pct(
            q.quotes.fiftyTwoWeekChangePercent
        )
    # 50 Day
    if q.quotes.fiftyDayAverage:
        key_stats["50 Day Average"] = quotes.to_dollar(
            number=q.quotes.fiftyDayAverage,
            symbol=q.currency_symbol,
        )
    if q.quotes.fiftyDayAverageChange:
        key_stats["50 Day Average Change"] = quotes.to_dollar(
            number=q.quotes.fiftyDayAverageChange,
            symbol=q.currency_symbol,
        )
    if q.quotes.fiftyDayAverageChangePercent:
        key_stats["50 Day Average Change %"] = util.float_to_pct(
            q.quotes.fiftyDayAverageChangePercent
        )
    # Targets
    if q.financialData.targetHighPrice:
        key_stats["Target High Price"] = quotes.to_dollar(
            number=q.financialData.targetHighPrice,
            symbol=q.currency_symbol,
        )
    if q.financialData.targetLowPrice:
        key_stats["Target Low Price"] = quotes.to_dollar(
            number=q.financialData.targetLowPrice,
            symbol=q.currency_symbol,
        )
    if q.financialData.targetMeanPrice:
        key_stats["Target Mean Price"] = quotes.to_dollar(
            number=q.financialData.targetMeanPrice,
            symbol=q.currency_symbol,
        )
    if q.financialData.targetMedianPrice:
        key_stats["Target Median Price"] = quotes.to_dollar(
            number=q.financialData.targetMedianPrice,
            symbol=q.currency_symbol,
        )
    if q.defaultKeyStatistics.beta:
        key_stats["Beta"] = quotes.numerize(
            number=q.defaultKeyStatistics.beta,
        )
    if q.defaultKeyStatistics.sharesOutstanding:
        key_stats["Shares Outstanding"] = quotes.numerize(
            number=q.defaultKeyStatistics.sharesOutstanding
        )
    if q.defaultKeyStatistics.impliedSharesOutstanding:
        key_stats["Implied Shares Outstanding"] = quotes.numerize(
            number=q.defaultKeyStatistics.impliedSharesOutstanding
        )
    if q.defaultKeyStatistics.sharesShort:
        key_stats["Shares Short"] = quotes.numerize(
            number=q.defaultKeyStatistics.sharesShort
        )
    if q.defaultKeyStatistics.sharesShortPriorMonth:
        key_stats["Shares Short Prior Month"] = quotes.numerize(
            number=q.defaultKeyStatistics.sharesShortPriorMonth
        )
    if q.defaultKeyStatistics.sharesShortPreviousMonthDate:
        key_stats["Shares Short Previous Month Date"] = (
            q.defaultKeyStatistics.sharesShortPreviousMonthDate.strftime(
                format="%Y-%m-%d"
            )
        )
    if q.defaultKeyStatistics.floatShares:
        key_stats["Public Float Shares"] = quotes.numerize(
            number=q.defaultKeyStatistics.floatShares
        )
    if q.financialData.totalCash:
        key_stats["Total Cash"] = quotes.to_dollar(
            number=q.financialData.totalCash,
            symbol=q.currency_symbol,
        )
    if q.financialData.totalCashPerShare:
        key_stats["Total Cash/Share"] = quotes.to_dollar(
            number=q.financialData.totalCashPerShare,
            symbol=q.currency_symbol,
        )
    if q.financialData.totalDebt:
        key_stats["Total Debt"] = quotes.to_dollar(
            number=q.financialData.totalDebt,
            symbol=q.currency_symbol,
        )
    if q.financialData.totalRevenue:
        key_stats["Total Revenue"] = quotes.to_dollar(
            number=q.financialData.totalRevenue,
            symbol=q.currency_symbol,
        )
    if q.financialData.debtToEquity:
        key_stats["Total Debt/Equity"] = util.float_to_pct(
            number=q.financialData.debtToEquity
        )
    if q.financialData.recommendationKey:
        key_stats["Recommendation"] = q.financialData.recommendationKey.replace(
            "_", " "
        ).title()

    if len(key_stats) > 0:
        tooltip.append("Key Stats:")
        max_key_length = 0
        for key in key_stats.keys():
            max_key_length = len(key) if len(key) > max_key_length else max_key_length

        for key, value in key_stats.items():
            tooltip.append(f"  {key:{max_key_length}} {value}")

        if len(tooltip) > 0:
            tooltip.append("")

    if q.defaultKeyStatistics and q.summaryDetail:
        dividend_information: OrderedDict = OrderedDict()
        if q.summaryDetail.dividendRate and q.quotes.dividendYield:
            dividend_information["Forward Dividend and Yield"] = (
                f"{util.pad_float(number=q.summaryDetail.dividendRate)} ({util.float_to_pct(number=q.quotes.dividendYield)})"
            )

        if q.defaultKeyStatistics.lastDividendDate:
            dividend_information["Last Dividend Date"] = datetime.fromtimestamp(
                timestamp=q.defaultKeyStatistics.lastDividendDate,
                tz=timezone.utc,
            ).strftime(format="%Y-%m-%d")
        if q.summaryDetail.payoutRatio:
            dividend_information["Payout Ratio"] = util.float_to_pct(
                number=q.summaryDetail.payoutRatio * 100
            )
        # if q.defaultKeyStatistics.lastDividendValue:
        #     dividend_information["Last Dividend Value"] = quotes.to_dollar(
        #         number=q.defaultKeyStatistics.lastDividendValue,
        #         symbol=q.currency_symbol,
        #     )

        if len(dividend_information) > 0:
            tooltip.append("Dividend Information:")
            max_key_length = 0
            for key in dividend_information.keys():
                max_key_length = (
                    len(key) if len(key) > max_key_length else max_key_length
                )

            for key, value in dividend_information.items():
                tooltip.append(f"  {key:{max_key_length}} {value}")

            if len(tooltip) > 0:
                tooltip.append("")

        if q.defaultKeyStatistics and q.price and q.quotes and q.summaryDetail:
            valuation_measures: OrderedDict = OrderedDict()
            if q.price.marketCap:
                valuation_measures["Market Cap"] = quotes.to_dollar(
                    number=q.price.marketCap,
                    symbol=q.currency_symbol,
                )
            if q.defaultKeyStatistics.enterpriseValue:
                valuation_measures["Enterprise Value"] = quotes.to_dollar(
                    number=q.defaultKeyStatistics.enterpriseValue,
                    symbol=q.currency_symbol,
                )
            if q.quotes.trailingPE:
                valuation_measures["Trailing P/E"] = util.pad_float(q.quotes.trailingPE)
            if q.defaultKeyStatistics.forwardPE:
                valuation_measures["Forward P/E"] = util.pad_float(
                    q.defaultKeyStatistics.forwardPE
                )
            if q.summaryDetail.priceToSalesTrailing12Months:
                valuation_measures["Price/Sales (ttm)"] = util.pad_float(
                    q.summaryDetail.priceToSalesTrailing12Months
                )
            if q.defaultKeyStatistics.priceToBook:
                valuation_measures["Price/Book (mrq)"] = util.pad_float(
                    q.defaultKeyStatistics.priceToBook
                )
            if q.defaultKeyStatistics.enterpriseToRevenue:
                valuation_measures["Enterprise Value/Revenue"] = util.pad_float(
                    q.defaultKeyStatistics.enterpriseToRevenue
                )
            if q.defaultKeyStatistics.enterpriseToEbitda:
                valuation_measures["Enterprise Value/EBITDA"] = util.pad_float(
                    q.defaultKeyStatistics.enterpriseToEbitda
                )

            if len(valuation_measures) > 0:
                tooltip.append("Validation Measures")
                max_key_length = 0
                for key in valuation_measures.keys():
                    max_key_length = (
                        len(key) if len(key) > max_key_length else max_key_length
                    )

                for key, value in valuation_measures.items():
                    tooltip.append(f"  {key:{max_key_length}} {value}")

    if len(tooltip) > 0:
        tooltip.append("")
        tooltip.append(f"Last updated {quotes.updated}")

    return "\n".join(tooltip)


def render_output(icon: str | None = None) -> tuple[str, str, str]:
    global format_index, quotes

    icon = icon if icon else glyphs.cod_graph_line

    if quotes.success:
        q = quotes.data[format_index]
        text = f"{icon}{glyphs.icon_spacer}{q.symbol} {util.pad_float(q.current)} {q.change} ({q.change_pct})"
        output_class = "success"
        tooltip = generate_tooltip()
    else:
        text = f"{icon}{glyphs.icon_spacer}Error"
        output_class = "error"
        tooltip = str(quotes.error)
    return text, output_class, tooltip


def worker(symbols: list[str]):
    global quotes, needs_fetch, needs_redraw, format_index, logger

    while True:
        with condition:
            while not (needs_fetch or needs_redraw):
                _ = condition.wait()

            fetch = needs_fetch
            redraw = needs_redraw
            needs_fetch = False
            needs_redraw = False

        logger.info("entering worker loop")
        logger.info(f"symbols = {symbols}")

        if not util.network_is_reachable():
            output = {
                "text": f"{glyphs.md_alert}{glyphs.icon_spacer}the network is unreachable",
                "class": "error",
                "tooltip": "Stock quote update error",
            }
            print(json.dumps(output))
            continue

        if fetch:
            loading = (
                f"{glyphs.md_timer_outline}{glyphs.icon_spacer}Fetching stock quotes..."
            )
            loading_dict = {
                "text": loading,
                "class": "loading",
                "tooltip": "Fetching stock quotes...",
            }

            if quotes.data and type(quotes.data) is list and len(quotes.data) > 0:
                text, output_class, tooltip = render_output(
                    icon=glyphs.md_timer_outline
                )
                output = {
                    "text": text,
                    "class": output_class,
                    "tooltip": tooltip,
                }
                print(
                    json.dumps({"text": text, "class": "loading", "tooltip": tooltip})
                )
            else:
                print(json.dumps(loading_dict))

            quotes.get_quotes()

        if quotes.data is None:
            continue

        if quotes.data and len(quotes.data) > 0:
            if redraw:
                text, output_class, tooltip = render_output()
                output = {
                    "text": text,
                    "class": output_class,
                    "tooltip": tooltip,
                }
                print(json.dumps(output))


@click.command(
    help="Get stock quotes from the Yahoo! Finance API",
    context_settings=context_settings,
)
@click.option(
    "-s",
    "--symbol",
    required=True,
    multiple=True,
    default=["GOOG", "AAPL"],
    help="The symbol to query",
)
@click.option(
    "-i", "--interval", type=int, default=900, help="The update interval (in seconds)"
)
@click.option(
    "-t", "--test", default=False, is_flag=True, help="Print the output and exit"
)
@click.option("-d", "--debug", default=False, is_flag=True, help="Enable debug logging")
def main(symbol: str, debug: bool, test: bool, interval: int):
    global formats, needs_fetch, needs_redraw, quotes, logger

    logger = util.configure_logger(
        debug=debug, name=os.path.basename(__file__), logfile=logfile
    )

    formats = list(range(len(symbol)))

    logger.info("entering function")

    symbols_list: list[str] = []
    for symbol in symbol:
        symbols_list.append(symbol)

    quotes = StockQuotes(symbols=symbols_list)

    if test:
        quotes.get_quotes()
        # pprint(quotes.data)
        # exit()
        text, output_class, tooltip = render_output()
        print(text)
        print(output_class)
        print(tooltip)
        return

    threading.Thread(
        target=worker,
        args=(symbols_list,),
        daemon=True,
    ).start()

    with condition:
        needs_fetch = True
        needs_redraw = True
        condition.notify()

    while True:
        time.sleep(interval)
        with condition:
            needs_fetch = True
            needs_redraw = True
            condition.notify()


if __name__ == "__main__":
    main()
