from dataclasses import dataclass, field
from datetime import datetime


# Common
@dataclass
class CompanyOfficer:
    age: int = 0
    exercisedValue: int = 0
    fiscalYear: int = 0
    maxAge: int = 0
    name: str | None = None
    title: str | None = None
    totalPay: int = 0
    unexercisedValue: int = 0
    yearBorn: int = 0


# Asset Profile
@dataclass
class AssetProfile:
    address1: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | int = 0
    country: str | None = None
    phone: str | None = None
    website: str | None = None
    industry: str | None = None
    industryKey: str | None = None
    industryDisp: str | None = None
    sector: str | None = None
    sectorKey: str | None = None
    sectorDisp: str | None = None
    longBusinessSummary: str | None = None
    fullTimeEmployees: int = 0
    companyOfficers: list[CompanyOfficer] = field(default_factory=list)
    compensationAsOfEpochDate: datetime | None = None
    executiveTeam: list[CompanyOfficer] = field(default_factory=list)
    maxAge: int = 0


# Balance Sheet History
@dataclass
class BalanceSheetStatement:
    maxAge: int = 0
    endDate: datetime | None = None


@dataclass
class BalanceSheetHistory:
    balanceSheetStatements: list[BalanceSheetStatement] = field(default_factory=list)


@dataclass
class BalanceSheetHistoryQuarterly:
    balanceSheetStatements: list[BalanceSheetStatement] = field(default_factory=list)


# Calendar Events
@dataclass
class EarningsCalendar:
    earningsDate: list[str] = field(default_factory=list)
    earningsAverage: float = 0.0
    earningsHigh: float = 0.0
    earningsLow: float = 0.0
    revenueAverage: int = 0
    revenueHigh: int = 0
    revenueLow: int = 0
    earningsCallDate: list[int] = field(default_factory=list)
    isEarningsDateEstimate: bool = False


@dataclass
class CalendarEvents:
    maxAge: int = 0
    earnings: EarningsCalendar = field(default_factory=EarningsCalendar)
    exDividendDate: datetime | None = None
    dividendDate: datetime | None = None


# Cash Flow Statement History
@dataclass
class CashFlowStatement:
    maxAge: int = 0
    endDate: datetime | None = None
    netIncome: int = 0


@dataclass
class CashFlowStatementHistory:
    cashflowStatements: list[CashFlowStatement] = field(default_factory=list)


@dataclass
class CashFlowStatementHistoryQuarterly:
    cashflowStatements: list[CashFlowStatement] = field(default_factory=list)


# Default Key Statistics
@dataclass
class DefaultKeyStatistics:
    fiftyTwoWeekChange: float = 0.0
    SandP52WeekChange: float = 0.0
    beta: float = 0.0
    bookValue: float = 0.0
    category: str | None = None
    dateShortInterest: datetime | None = None
    earningsQuarterlyGrowth: float = 0.0
    enterpriseToEbitda: float = 0.0
    enterpriseToRevenue: float = 0.0
    enterpriseValue: int = 0
    floatShares: int = 0
    forwardEps: float = 0.0
    forwardPE: float = 0.0
    fundFamily: str | None = None
    heldPercentInsiders: float = 0.0
    heldPercentInstitutions: float = 0.0
    impliedSharesOutstanding: int = 0
    lastDividendDate: int = 0
    lastDividendValue: float = 0.0
    lastFiscalYearEnd: datetime | None = None
    lastSplitDate: datetime | None = None
    lastSplitFactor: str | None = None
    latestShareClass: str | None = None
    leadInvestor: str | None = None
    legalType: str | None = None
    maxAge: int = 0
    mostRecentQuarter: datetime | None = None
    netIncomeToCommon: int = 0
    nextFiscalYearEnd: datetime | None = None
    priceHint: int = 0
    priceToBook: float = 0.0
    profitMargins: float = 0.0
    sharesOutstanding: int = 0
    sharesPercentSharesOut: float = 0.0
    sharesShort: int = 0
    sharesShortPreviousMonthDate: datetime | None = None
    sharesShortPriorMonth: int = 0
    shortPercentOfFloat: float = 0.0
    shortRatio: float = 0.0
    trailingEps: float = 0.0


# Earnings
@dataclass
class QuarterlyData:
    date: str | None = None
    actual: float = 0.0
    estimate: float = 0.0
    fiscalQuarter: str | None = None
    calendarQuarter: str | None = None
    difference: float | str | None = None
    surprisePct: float | str | None = None


@dataclass
class EarningsChart:
    maxAge: int = 0
    quarterly: list[QuarterlyData] = field(default_factory=list)
    currentQuarterEstimate: float = 0.0
    currentQuarterEstimateDate: str | None = None
    currentCalendarQuarter: str | None = None
    currentQuarterEstimateYear: int = 0
    currentFiscalQuarter: str | None = None
    earningsDate: list[str] = field(default_factory=list)
    isEarningsDateEstimate: bool = False


@dataclass
class FinancialsChartYearly:
    date: int = 0
    revenue: int = 0
    earnings: int = 0


@dataclass
class FinancialsChartQuarterly:
    date: str | None = None
    fiscalQuarter: str | None = None
    revenue: int = 0
    earnings: int = 0


@dataclass
class FinancialsChart:
    yearly: list[FinancialsChartYearly] = field(default_factory=list)
    quarterly: list[FinancialsChartQuarterly] = field(default_factory=list)


@dataclass
class Earnings:
    maxAge: int = 0
    earningsChart: EarningsChart = field(default_factory=EarningsChart)
    financialsChart: FinancialsChart = field(default_factory=FinancialsChart)
    financialCurrency: str | None = None
    defaultMethodology: str | None = None


# Earnings History
@dataclass
class EarningsHistoryItem:
    maxAge: int = 0
    epsActual: float = 0.0
    epsEstimate: float = 0.0
    epsDifference: float = 0.0
    surprisePercent: float = 0.0
    quarter: datetime | None = None
    currency: str | None = None
    period: str | None = None


@dataclass
class EarningsHistory:
    history: list[EarningsHistoryItem] = field(default_factory=list)
    defaultMethodology: str | None = None
    maxAge: int = 0


# Earnings Trend
@dataclass
class EarningsEstimate:
    avg: float = 0.0
    earningsCurrency: str | None = None
    growth: float = 0.0
    high: float = 0.0
    low: float = 0.0
    numberOfAnalysts: int = 0
    yearAgoEps: float = 0.0


@dataclass
class EpsRevisions:
    downLast30days: int = 0
    downLast7Days: int = 0
    # downLast90days: {}
    epsRevisionsCurrency: str | None = None
    upLast30days: int = 0
    upLast7days: int = 0


@dataclass
class EpsTrend:
    thirtyDaysAgo: float = 0.0
    sixtyDaysAgo: float = 0.0
    sevenDaysAgo: float = 0.0
    ninetyDaysAgo: float = 0.0
    current: float = 0.0
    epsTrendCurrency: str | None = None


@dataclass
class RevenueEstimate:
    avg: int = 0
    growth: float = 0.0
    high: int = 0
    low: int = 0
    numberOfAnalysts: int = 0
    revenueCurrency: str | None = None
    yearAgoRevenue: int = 0


@dataclass
class Trend:
    maxAge: int = 0
    period: str | None = None
    endDate: datetime | None = None
    growth: float = 0.0
    earningsEstimate: EarningsEstimate = field(default_factory=EarningsEstimate)
    revenueEstimate: RevenueEstimate = field(default_factory=RevenueEstimate)
    epsTrend: EpsTrend = field(default_factory=EpsTrend)
    epsRevisions: EpsRevisions = field(default_factory=EpsRevisions)


@dataclass
class EarningsTrend:
    trend: list[Trend] = field(default_factory=list)
    defaultMethodology: str | None = None
    maxAge: int = 0


# Financial Data
@dataclass
class FinancialData:
    currentPrice: float = 0.0
    currentRatio: float = 0.0
    debtToEquity: float = 0.0
    earningsGrowth: float = 0.0
    ebitda: int = 0
    ebitdaMargins: float = 0.0
    financialCurrency: str | None = None
    freeCashflow: int = 0
    grossMargins: float = 0.0
    grossProfits: int = 0
    maxAge: int = 0
    numberOfAnalystOpinions: int = 0
    operatingCashflow: int = 0
    operatingMargins: float = 0.0
    profitMargins: float = 0.0
    quickRatio: float = 0.0
    recommendationKey: str | None = None
    recommendationMean: float = 0.0
    returnOnAssets: float = 0.0
    returnOnEquity: float = 0.0
    revenueGrowth: float = 0.0
    revenuePerShare: float = 0.0
    targetHighPrice: float = 0.0
    targetLowPrice: float = 0.0
    targetMeanPrice: float = 0.0
    targetMedianPrice: float = 0.0
    totalCash: int = 0
    totalCashPerShare: float = 0.0
    totalDebt: int = 0
    totalRevenue: int = 0


# Fund Ownership
@dataclass
class FundOwner:
    maxAge: int = 0
    reportDate: datetime | None = None
    organization: str | None = None
    pctHeld: float = 0.0
    position: int = 0
    value: int = 0
    pctChange: float = 0.0


@dataclass
class FundOwnership:
    maxAge: int = 0
    ownershipList: list[FundOwner] = field(default_factory=list)


# Income Statement History
# Not enough info

# Income Statement History Quarterly
# Not enough info


# Index Trend
@dataclass
class IndexTrendEstimate:
    period: str | None = None
    growth: float = 0.0


@dataclass
class IndexTrend:
    maxAge: int = 0
    symbol: str | None = None
    estimates: list[IndexTrendEstimate] = field(default_factory=list)


# Industry Trend
@dataclass
class IndustryTrendEstimate:
    period: str | None = None
    growth: float = 0.0


@dataclass
class IndustryTrend:
    maxAge: int = 0
    symbol: str | None = None
    estimates: list[IndustryTrendEstimate] = field(default_factory=list)


@dataclass
class InsiderHolder:
    latestTransDate: datetime | None = None
    maxAge: int = 0
    name: str | None = None
    positionDirect: int = 0
    positionDirectDate: datetime | None = None
    relation: str | None = None
    transactionDescription: str | None = None
    url: str | None = None


@dataclass
class InsiderHolders:
    holders: list[InsiderHolder] = field(default_factory=list)
    maxAge: int = 0


# Insider Transactions
@dataclass
class InsiderTransaction:
    maxAge: int = 0
    shares: int = 0
    value: int = 0
    filerUrl: str | None = None
    transactionText: str | None = None
    filerName: str | None = None
    filerRelation: str | None = None
    moneyText: str | None = None
    startDate: datetime | None = None
    ownership: str | None = None


@dataclass
class InsiderTransactions:
    transactions: list[InsiderTransaction] = field(default_factory=list)
    maxAge: int = 0


# Institution Ownership
@dataclass
class InstitutionOwner:
    maxAge: int = 0
    reportDate: datetime | None = None
    organization: str | None = None
    pctHeld: float = 0.0
    position: int = 0
    value: int = 0
    pctChange: float = 0.0


@dataclass
class InstitutionOwnership:
    maxAge: int = 0
    ownershipList: list[InstitutionOwner] = field(default_factory=list)


# Major Holders Breakdown
@dataclass
class MajorHoldersBreakdown:
    maxAge: int = 0
    insidersPercentHeld: float = 0.0
    institutionsPercentHeld: float = 0.0
    institutionsFloatPercentHeld: float = 0.0
    institutionsCount: int = 0


# Net Share Purchase Activity
@dataclass
class NetSharePurchaseActivity:
    maxAge: int = 0
    period: str | None = None
    buyInfoCount: int = 0
    buyInfoShares: int = 0
    buyPercentInsiderShares: float = 0.0
    sellInfoCount: int = 0
    sellInfoShares: int = 0
    sellPercentInsiderShares: float = 0.0
    netInfoCount: int = 0
    netInfoShares: int = 0
    netPercentInsiderShares: float = 0.0
    totalInsiderShares: int = 0


# Page Views
@dataclass
class PageViews:
    shortTermTrend: str | None = None
    midTermTrend: str | None = None
    longTermTrend: str | None = None
    maxAge: int = 0


# Price
@dataclass
class Price:
    currency: str | None = None
    currencySymbol: str | None = None
    exchange: str | None = None
    exchangeDataDelayedBy: int = 0
    exchangeName: str | None = None
    fromCurrency: str | None = None
    lastMarket: str | None = None
    longName: str | None = None
    marketCap: int = 0
    marketState: str | None = None
    maxAge: int = 0
    preMarketChange: float = 0.0
    preMarketChangePercent: float = 0.0
    preMarketPrice: float = 0.0
    preMarketSource: str | None = None
    preMarketTime: datetime | None = None
    priceHint: int = 0
    quoteSourceName: str | None = None
    quoteType: str | None = None
    regularMarketChange: float = 0.0
    regularMarketChangePercent: float = 0.0
    regularMarketDayHigh: float = 0.0
    regularMarketDayLow: float = 0.0
    regularMarketOpen: float = 0.0
    regularMarketPreviousClose: float = 0.0
    regularMarketPrice: float = 0.0
    regularMarketSource: str | None = None
    regularMarketTime: datetime | None = None
    regularMarketVolume: int = 0
    shortName: str | None = None
    symbol: str | None = None
    toCurrency: str | None = None
    underlyingSymbol: str | None = None


# Quote Type
@dataclass
class QuoteType:
    exchange: str | None = None
    firstTradeDateEpochUtc: datetime | None = None
    gmtOffSetMilliseconds: int = 0
    longName: str | None = None
    maxAge: int = 0
    messageBoardId: str | None = None
    quoteType: str | None = None
    shortName: str | None = None
    symbol: str | None = None
    timeZoneFullName: str | None = None
    timeZoneShortName: str | None = None
    underlyingSymbol: str | None = None
    uuid: str | None = None


# Quotes
@dataclass
class Quotes:
    ask: float = 0.0
    askSize: int = 0
    averageAnalystRating: str | None = None
    averageDailyVolume10Day: int = 0
    averageDailyVolume3Month: int = 0
    bid: float = 0.0
    bidSize: int = 0
    bookValue: float = 0.0
    corporateActions: list = field(default_factory=list)
    cryptoTradeable: bool = False
    currency: str | None = None
    customPriceAlertConfidence: str | None = None
    displayName: str | None = None
    dividendDate: int = 0
    dividendRate: float = 0.0
    dividendYield: float = 0.0
    earningsCallTimestampEnd: int = 0
    earningsCallTimestampStart: int = 0
    earningsTimestamp: int = 0
    earningsTimestampEnd: int = 0
    earningsTimestampStart: int = 0
    epsCurrentYear: float = 0.0
    epsForward: float = 0.0
    epsTrailingTwelveMonths: float = 0.0
    esgPopulated: bool = False
    exchange: str | None = None
    exchangeDataDelayedBy: int = 0
    exchangeTimezoneName: str | None = None
    exchangeTimezoneShortName: str | None = None
    fiftyDayAverage: float = 0.0
    fiftyDayAverageChange: float = 0.0
    fiftyDayAverageChangePercent: float = 0.0
    fiftyTwoWeekChangePercent: float = 0.0
    fiftyTwoWeekHigh: float = 0.0
    fiftyTwoWeekHighChange: float = 0.0
    fiftyTwoWeekHighChangePercent: float = 0.0
    fiftyTwoWeekLow: float = 0.0
    fiftyTwoWeekLowChange: float = 0.0
    fiftyTwoWeekLowChangePercent: float = 0.0
    fiftyTwoWeekRange: str | None = None
    financialCurrency: str | None = None
    firstTradeDateMilliseconds: int = 0
    forwardPE: float = 0.0
    fullExchangeName: str | None = None
    gmtOffSetMilliseconds: int = 0
    hasPrePostMarketData: bool = False
    isEarningsDateEstimate: bool = False
    language: str | None = None
    longName: str | None = None
    market: str | None = None
    marketCap: int = 0
    marketState: str | None = None
    messageBoardId: str | None = None
    priceEpsCurrentYear: float = 0.0
    priceHint: int = 0
    priceToBook: float = 0.0
    quoteSourceName: str | None = None
    quoteType: str | None = None
    region: str | None = None
    regularMarketChange: float = 0.0
    regularMarketChangePercent: float = 0.0
    regularMarketDayHigh: float = 0.0
    regularMarketDayLow: float = 0.0
    regularMarketDayRange: str | None = None
    regularMarketOpen: float = 0.0
    regularMarketPreviousClose: float = 0.0
    regularMarketPrice: float = 0.0
    regularMarketTime: int = 0
    regularMarketVolume: int = 0
    sharesOutstanding: int = 0
    shortName: str | None = None
    sourceInterval: int = 0
    tradeable: bool = False
    trailingAnnualDividendRate: float = 0.0
    trailingAnnualDividendYield: float = 0.0
    trailingPE: float = 0.0
    triggerable: bool = False
    twoHundredDayAverage: float = 0.0
    twoHundredDayAverageChange: float = 0.0
    twoHundredDayAverageChangePercent: float = 0.0
    typeDisp: str | None = None


# Recommendation Trend
@dataclass
class RecommendationTrendItem:
    buy: int = 0
    hold: int = 0
    period: str | None = None
    sell: int = 0
    strongBuy: int = 0
    strongSell: int = 0


@dataclass
class RecommendationTrend:
    trend: list[RecommendationTrendItem] = field(default_factory=list)
    maxAge: int = 0


# SEC Filings
@dataclass
class SecFilingExhibit:
    downloadUrl: str | None = None
    type: str | None = None
    url: str | None = None


@dataclass
class SecFiling:
    date: datetime | None = None
    edgarUrl: str | None = None
    epochDate: datetime | None = None
    exhibits: list[SecFilingExhibit] = field(default_factory=list)
    maxAge: int = 0
    title: str | None = None
    type: str | None = None


@dataclass
class SecFilings:
    filings: list[SecFiling] = field(default_factory=list)
    maxAge: int = 0


# Sector Trend
# Not enough info


# Summary Detail
@dataclass
class SummaryDetail:
    algorithm: str | None = None
    allTimeHigh: float = 0.0
    allTimeLow: float = 0.0
    ask: float = 0.0
    askSize: int = 0
    averageDailyVolume10Day: int = 0
    averageVolume: int = 0
    averageVolume10days: int = 0
    beta: float = 0.0
    bid: float = 0.0
    bidSize: int = 0
    coinMarketCapLink: str | None = None
    currency: str | None = None
    dayHigh: float = 0.0
    dayLow: float = 0.0
    dividendRate: float = 0.0
    dividendYield: float = 0.0
    exDividendDate: datetime | None = None
    fiftyDayAverage: float = 0.0
    fiftyTwoWeekHigh: float = 0.0
    fiftyTwoWeekLow: float = 0.06
    forwardPE: float = 0.0
    fromCurrency: str | None = None
    lastMarket: str | None = None
    marketCap: int = 0
    maxAge: int = 0
    open: float = 0.0
    payoutRatio: float = 0.0
    previousClose: float = 0.0
    priceHint: int = 0
    priceToSalesTrailing12Months: float = 0.0
    regularMarketDayHigh: float = 0.0
    regularMarketDayLow: float = 0.0
    regularMarketOpen: float = 0.0
    regularMarketPreviousClose: float = 0.0
    regularMarketVolume: int = 0
    toCurrency: str | None = None
    tradeable: bool = False
    trailingAnnualDividendRate: float = 0.0
    trailingAnnualDividendYield: float = 0.0
    trailingPE: float = 0.0
    twoHundredDayAverage: float = 0.0
    volume: int = 0


# Summary Profile
@dataclass
class SummaryProfile:
    address1: str | None = None
    city: str | None = None
    companyOfficers: list[CompanyOfficer] = field(default_factory=list)
    country: str | None = None
    executiveTeam: list[CompanyOfficer] = field(default_factory=list)
    fullTimeEmployees: int = 0
    industry: str | None = None
    industryDisp: str | None = None
    industryKey: str | None = None
    irWebsite: str | None = None
    longBusinessSummary: str | None = None
    maxAge: int = 0
    phone: str | None = None
    sector: str | None = None
    sectorDisp: str | None = None
    sectorKey: str | None = None
    state: str | None = None
    website: str | None = None
    zip: str | int = 0


# Technical Insights
@dataclass
class CompanySnapshotCompany:
    dividends: float = 0.0
    earningsReports: float = 0.0
    hiring: float = 0.0
    innovativeness: float = 0.0
    insiderSentiments: float = 0.0
    sustainability: float = 0.0


@dataclass
class CompanySnapshotSector:
    dividends: float = 0.0
    earningsReports: float = 0.0
    hiring: float = 0.0
    innovativeness: float = 0.0
    insiderSentiments: float = 0.0
    sustainability: float = 0.0


@dataclass
class CompanySnapshot:
    company: CompanySnapshotCompany = field(default_factory=CompanySnapshotCompany)
    sector: CompanySnapshotSector = field(default_factory=CompanySnapshotSector)
    sectorInfo: str | None = None


@dataclass
class KeyTechnicals:
    provider: str | None = None
    resistance: float = 0.0
    stopLoss: float = 0.0
    support: float = 0.0


@dataclass
class TechnicalEventOutlook:
    direction: str | None = None
    indexDirection: str | None = None
    indexScore: int = 0
    indexScoreDescription: str | None = None
    score: int = 0
    scoreDescription: str | None = None
    sectorDirection: str | None = None
    sectorScore: int = 0
    sectorScoreDescription: str | None = None
    stateDescription: str | None = None


@dataclass
class TechnicalEvents:
    intermediateTermOutlook: TechnicalEventOutlook = field(
        default_factory=TechnicalEventOutlook
    )
    longTermOutlook: TechnicalEventOutlook = field(
        default_factory=TechnicalEventOutlook
    )
    provider: str | None = None
    secto: str | None = None
    shortTermOutlook: TechnicalEventOutlook = field(
        default_factory=TechnicalEventOutlook
    )


@dataclass
class Valuation:
    color: float = 0.0
    discount: str | None = None
    provider: str | None = None
    relativeValue: str | None = None


@dataclass
class InstrumentInfo:
    keyTechnicals: KeyTechnicals = field(default_factory=KeyTechnicals)
    technicalEvents: TechnicalEvents = field(default_factory=TechnicalEvents)
    valuation: Valuation = field(default_factory=Valuation)


@dataclass
class Recommendation:
    provider: str | None = None
    rating: str | None = None
    targetPrice: float = 0.0


@dataclass
class SecReport:
    description: str | None = None
    filingDate: int = 0
    formType: str | None = None
    id: str | None = None
    snapshotUrl: str | None = None
    title: str | None = None
    type: str | None = None


@dataclass
class TechnicalInsights:
    companySnapshot: CompanySnapshot = field(default_factory=CompanySnapshot)
    instrumentInfo: InstrumentInfo = field(default_factory=InstrumentInfo)
    recommendation: Recommendation = field(default_factory=Recommendation)
    secReports: list[SecReport] = field(default_factory=list)


@dataclass
class UpgradeDowngradeHistoryItem:
    epochGradeDate: datetime | None = None
    firm: str | None = None
    toGrade: str | None = None
    fromGrade: str | None = None
    action: str | None = None
    priceTargetAction: str | None = None
    currentPriceTarget: float = 0.0
    priorPriceTarget: float = 0.0


@dataclass
class UpgradeDowngradeHistory:
    history: list[UpgradeDowngradeHistoryItem] = field(default_factory=list)
    maxAge: int = 0


@dataclass
class AllModules:
    assetProfile: AssetProfile = field(default_factory=AssetProfile)
    balanceSheetHistory: BalanceSheetHistory = field(
        default_factory=BalanceSheetHistory
    )
    balanceSheetHistoryQuarterly: BalanceSheetHistoryQuarterly = field(
        default_factory=BalanceSheetHistoryQuarterly
    )
    calendarEvents: CalendarEvents = field(default_factory=CalendarEvents)
    cashflowStatementHistory: CashFlowStatementHistory = field(
        default_factory=CashFlowStatementHistory
    )
    cashFlowStatementHistoryQuarterly: CashFlowStatementHistoryQuarterly = field(
        default_factory=CashFlowStatementHistoryQuarterly
    )
    defaultKeyStatistics: DefaultKeyStatistics = field(
        default_factory=DefaultKeyStatistics
    )
    earnings: Earnings = field(default_factory=Earnings)
    earningsHistory: EarningsHistory = field(default_factory=EarningsHistory)
    earningsTrend: EarningsTrend = field(default_factory=EarningsTrend)
    financialData: FinancialData = field(default_factory=FinancialData)
    fundOwnership: FundOwnership = field(default_factory=FundOwnership)
    indexTrend: IndexTrend = field(default_factory=IndexTrend)
    industryTrend: IndustryTrend = field(default_factory=IndustryTrend)
    insiderHolders: InsiderHolders = field(default_factory=InsiderHolders)
    insiderTransactions: InsiderTransactions = field(
        default_factory=InsiderTransactions
    )
    institutionOwnership: InstitutionOwnership = field(
        default_factory=InstitutionOwnership
    )
    majorHoldersBreakdown: MajorHoldersBreakdown = field(
        default_factory=MajorHoldersBreakdown
    )
    netSharePurchaseActivity: NetSharePurchaseActivity = field(
        default_factory=NetSharePurchaseActivity
    )
    pageViews: PageViews = field(default_factory=PageViews)
    quoteType: QuoteType = field(default_factory=QuoteType)
    price: Price = field(default_factory=Price)
    recommendationTrend: RecommendationTrend = field(
        default_factory=RecommendationTrend
    )
    secFilings: SecFilings = field(default_factory=SecFilings)
    summaryDetail: SummaryDetail = field(default_factory=SummaryDetail)
    summaryProfile: SummaryProfile = field(default_factory=SummaryProfile)
    upgradeDowngradeHistory: UpgradeDowngradeHistory = field(
        default_factory=UpgradeDowngradeHistory
    )


@dataclass
class QuoteData:
    symbol: str = ""
    current: float = 0.0
    previous: float = 0.0
    change: str = ""
    change_pct: str = ""
    currency_symbol: str = ""
    assetProfile: AssetProfile = field(default_factory=AssetProfile)
    balanceSheetHistory: BalanceSheetHistory = field(
        default_factory=BalanceSheetHistory
    )
    balanceSheetHistoryQuarterly: BalanceSheetHistoryQuarterly = field(
        default_factory=BalanceSheetHistoryQuarterly
    )
    calendarEvents: CalendarEvents = field(default_factory=CalendarEvents)
    cashflowStatementHistory: CashFlowStatementHistory = field(
        default_factory=CashFlowStatementHistory
    )
    cashFlowStatementHistoryQuarterly: CashFlowStatementHistoryQuarterly = field(
        default_factory=CashFlowStatementHistoryQuarterly
    )
    defaultKeyStatistics: DefaultKeyStatistics = field(
        default_factory=DefaultKeyStatistics
    )
    earnings: Earnings = field(default_factory=Earnings)
    earningsHistory: EarningsHistory = field(default_factory=EarningsHistory)
    earningsTrend: EarningsTrend = field(default_factory=EarningsTrend)
    financialData: FinancialData = field(default_factory=FinancialData)
    fundOwnership: FundOwnership = field(default_factory=FundOwnership)
    indexTrend: IndexTrend = field(default_factory=IndexTrend)
    industryTrend: IndustryTrend = field(default_factory=IndustryTrend)
    insiderHolders: InsiderHolders = field(default_factory=InsiderHolders)
    insiderTransactions: InsiderTransactions = field(
        default_factory=InsiderTransactions
    )
    institutionOwnership: InstitutionOwnership = field(
        default_factory=InstitutionOwnership
    )
    majorHoldersBreakdown: MajorHoldersBreakdown = field(
        default_factory=MajorHoldersBreakdown
    )
    netSharePurchaseActivity: NetSharePurchaseActivity = field(
        default_factory=NetSharePurchaseActivity
    )
    pageViews: PageViews = field(default_factory=PageViews)
    quoteType: QuoteType = field(default_factory=QuoteType)
    quotes: Quotes = field(default_factory=Quotes)
    price: Price = field(default_factory=Price)
    recommendationTrend: RecommendationTrend = field(
        default_factory=RecommendationTrend
    )
    secFilings: SecFilings = field(default_factory=SecFilings)
    summaryDetail: SummaryDetail = field(default_factory=SummaryDetail)
    summaryProfile: SummaryProfile = field(default_factory=SummaryProfile)
    technicalInsights: TechnicalInsights = field(default_factory=TechnicalInsights)
    upgradeDowngradeHistory: UpgradeDowngradeHistory = field(
        default_factory=UpgradeDowngradeHistory
    )
