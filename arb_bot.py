import asyncio
import logging
import time
from collections import defaultdict
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

import aiohttp
import krakenex


# --- CONFIGURATION ---
class Config:
    # 0. SCAN MODE ------------------------------------------------------------
    # 'usd_eur' : only pairs quoted in USD or EUR, 3-trade loops. Every loop goes
    #             through EUR, e.g. USD -> ADA -> EUR -> USD or USD -> EUR -> ADA -> USD:
    #             it's buying an asset in one currency and selling it in the other.
    # 'all'     : every pair between any assets in your list (cross pairs like
    #             Q/ADA or AAVE/ETH), with loops up to MAX_PATH_LEGS trades.
    SCAN_MODE = 'usd_eur'

    # 1. API & SECURITY
    KEY_FILE_NAME = 'kraken.key'

    # 2. TRADING STRATEGY
    HOME_CURRENCY = 'ZUSD'
    # Only used if live fees can't be determined (no key loaded, or the API call fails).
    # Real per-pair taker fees are computed from your 30-day volume + each pair's fee schedule.
    FALLBACK_TAKER_FEE_PERCENT = 0.40
    PROFIT_THRESHOLD = 0.05  # minimum net profit, in HOME_CURRENCY, after fees and book depth

    # Asset lists for pair discovery
    MANUAL_KRAKEN_BASES = {'0g': '0G', '1inch': '1INCH', 'aave': 'AAVE', 'ab': 'AB', 'aca': 'ACA', 'ach': 'ACH', 'act': 'ACT', 'acx': 'ACX', 'ada': 'ADA', 'adx': 'ADX', 'aero': 'AERO', 'a': 'A', 'aevo': 'AEVO', 'agld': 'AGLD', 'ai16z': 'AI16Z', 'ai3': 'AI3', 'aioz': 'AIOZ', 'air': 'AIR', 'aixbt': 'AIXBT', 'ake': 'AKE', 'akt': 'AKT', 'alch': 'ALCH', 'alcx': 'ALCX', 'algo': 'ALGO', 'alice': 'ALICE', 'alkimi': 'ALKIMI', 'alpha': 'ALPHA', 'alt': 'ALT', 'ankr': 'ANKR', 'anlog': 'ANLOG', 'anon': 'ANON', 'ape': 'APE', 'apenft': 'APENFT', 'api3': 'API3', 'apt': 'APT', 'apu': 'APU', 'arb': 'ARB', 'arc': 'ARC', 'ar': 'AR', 'arkm': 'ARKM', 'arpa': 'ARPA', 'art': 'ART', 'asrr': 'ASRR', 'astr': 'ASTR', 'ath': 'ATH', 'atlas': 'ATLAS', 'atom': 'ATOM', 'auction': 'AUCTION', 'audio': 'AUDIO', 'zaud': 'ZAUD', 'aura': 'AURA', 'avaai': 'AVAAI', 'avax': 'AVAX', 'avnt': 'AVNT', 'axs': 'AXS', 'b3': 'B3', 'baby': 'BABY', 'badger': 'BADGER', 'bal': 'BAL', 'bananas31': 'BANANAS31', 'band': 'BAND', 'bat': 'BAT', 'bch': 'BCH', 'bdxn': 'BDXN', 'beam': 'BEAM', 'bera': 'BERA', 'bico': 'BICO', 'bigtime': 'BIGTIME', 'billy': 'BILLY', 'bio': 'BIO', 'bit': 'BIT', 'blur': 'BLUR', 'blz': 'BLZ', 'bmt': 'BMT', 'bnb': 'BNB', 'bnc': 'BNC', 'bnt': 'BNT', 'boba': 'BOBA', 'boden': 'BODEN', 'bond': 'BOND', 'bonk': 'BONK', 'brick': 'BRICK', 'bsx': 'BSX', 'btr': 'BTR', 'btt': 'BTT', 'c98': 'C98', 'cake': 'CAKE', 'camp': 'CAMP', 'carv': 'CARV', 'cat': 'CAT', 'ccd': 'CCD', 'celo': 'CELO', 'celr': 'CELR', 'cfg': 'CFG', 'cheems': 'CHEEMS', 'chex': 'CHEX', 'chillhouse': 'CHILLHOUSE', 'chr': 'CHR', 'chz': 'CHZ', 'clanker': 'CLANKER', 'cloud': 'CLOUD', 'clv': 'CLV', 'cmeth': 'CMETH', 'comp': 'COMP', 'cookie': 'COOKIE', 'coq': 'COQ', 'corn': 'CORN', 'coti': 'COTI', 'cow': 'COW', 'cpool': 'CPOOL', 'cqt': 'CQT', 'cro': 'CRO', 'crv': 'CRV', 'csm': 'CSM', 'ctc': 'CTC', 'ctsi': 'CTSI', 'cvc': 'CVC', 'cvx': 'CVX', 'cxt': 'CXT', 'cyber': 'CYBER', 'dai': 'DAI', 'dash': 'DASH', 'dbr': 'DBR', 'deep': 'DEEP', 'degen': 'DEGEN', 'dent': 'DENT', 'dmc': 'DMC', 'dog': 'DOG', 'dogs': 'DOGS', 'dolo': 'DOLO', 'dot': 'DOT', 'drift': 'DRIFT', 'drv': 'DRV', 'duck': 'DUCK', 'dydx': 'DYDX', 'dym': 'DYM', 'edge': 'EDGE', 'egld': 'EGLD', 'eigen': 'EIGEN', 'elx': 'ELX', 'ena': 'ENA', 'enj': 'ENJ', 'ens': 'ENS', 'ept': 'EPT', 'es': 'ES', 'esx': 'ESX', 'xeth': 'XETH', 'ethfi': 'ETHFI', 'ethw': 'ETHW', 'eul': 'EUL', 'zeur': 'ZEUR', 'eurc': 'EURC', 'europ': 'EUROP', 'eurq': 'EURQ', 'eurr': 'EURR', 'ewt': 'EWT', 'farm': 'FARM', 'fartcoin': 'FARTCOIN', 'fet': 'FET', 'fhe': 'FHE', 'fida': 'FIDA', 'fil': 'FIL', 'fis': 'FIS', 'floki': 'FLOKI', 'flow': 'FLOW', 'flr': 'FLR', 'flux': 'FLUX', 'fly': 'FLY', 'forth': 'FORTH', 'fwog': 'FWOG', 'fxs': 'FXS', 'gaia': 'GAIA', 'gala': 'GALA', 'gal': 'GAL', 'gari': 'GARI', 'g': 'G', 'gfi': 'GFI', 'ghibli': 'GHIBLI', 'ghst': 'GHST', 'giga': 'GIGA', 'glmr': 'GLMR', 'gmt': 'GMT', 'gmx': 'GMX', 'gno': 'GNO', 'goat': 'GOAT', 'gomining': 'GOMINING', 'grass': 'GRASS', 'griffain': 'GRIFFAIN', 'grt': 'GRT', 'gst': 'GST', 'gtc': 'GTC', 'gun': 'GUN', 'hbar': 'HBAR', 'hdx': 'HDX', 'h': 'H', 'hft': 'HFT', 'hippo': 'HIPPO', 'hmstr': 'HMSTR', 'hnt': 'HNT', 'honey': 'HONEY', 'house': 'HOUSE', 'hpos10i': 'HPOS10I', 'icnt': 'ICNT', 'icp': 'ICP', 'icx': 'ICX', 'idex': 'IDEX', 'imx': 'IMX', 'init': 'INIT', 'inj': 'INJ', 'intr': 'INTR', 'ip': 'IP', 'jailstool': 'JAILSTOOL', 'jasmy': 'JASMY', 'jitosol': 'JITOSOL', 'joe': 'JOE', 'jst': 'JST', 'jto': 'JTO', 'juno': 'JUNO', 'jup': 'JUP', 'kaito': 'KAITO', 'kar': 'KAR', 'kas': 'KAS', 'kava': 'KAVA', 'keep': 'KEEP', 'kernel': 'KERNEL', 'ket': 'KET', 'key': 'KEY', 'kin': 'KIN', 'kint': 'KINT', 'kmno': 'KMNO', 'knc': 'KNC', 'koban': 'KOBAN', 'kp3r': 'KP3R', 'ksm': 'KSM', 'kta': 'KTA', 'l3': 'L3', 'layer': 'LAYER', 'lcx': 'LCX', 'ldo': 'LDO', 'linea': 'LINEA', 'link': 'LINK', 'lit': 'LIT', 'lmwr': 'LMWR', 'lobo': 'LOBO', 'lockin': 'LOCKIN', 'lofi': 'LOFI', 'lpt': 'LPT', 'lqty': 'LQTY', 'lrc': 'LRC', 'lseth': 'LSETH', 'lsk': 'LSK', 'lssol': 'LSSOL', 'xltc': 'XLTC', 'luna2': 'LUNA2', 'luna': 'LUNA', 'mana': 'MANA', 'mask': 'MASK', 'mat': 'MAT', 'mc': 'MC', 'me': 'ME', 'melania': 'MELANIA', 'meme': 'MEME', 'merl': 'MERL', 'meth': 'METH', 'metis': 'METIS', 'm': 'M', 'mew': 'MEW', 'michi': 'MICHI', 'mim': 'MIM', 'mina': 'MINA', 'mir': 'MIR', 'mirror': 'MIRROR', 'mngo': 'MNGO', 'mnt': 'MNT', 'moca': 'MOCA', 'mog': 'MOG', 'moodeng': 'MOODENG', 'moon': 'MOON', 'morpho': 'MORPHO', 'move': 'MOVE', 'movr': 'MOVR', 'msol': 'MSOL', 'mubarak': 'MUBARAK', 'multi': 'MULTI', 'mv': 'MV', 'mxc': 'MXC', 'nano': 'NANO', 'near': 'NEAR', 'neiro': 'NEIRO', 'nil': 'NIL', 'nmr': 'NMR', 'nobody': 'NOBODY', 'node': 'NODE', 'nodl': 'NODL', 'nos': 'NOS', 'not': 'NOT', 'npc': 'NPC', 'ntrn': 'NTRN', 'nym': 'NYM', 'ocean': 'OCEAN', 'odos': 'ODOS', 'ogn': 'OGN', 'om': 'OM', 'omg': 'OMG', 'omni': 'OMNI', 'ondo': 'ONDO', 'open': 'OPEN', 'op': 'OP', 'orca': 'ORCA', 'order': 'ORDER', 'osmo': 'OSMO', 'oxt': 'OXT', 'oxy': 'OXY', 'parti': 'PARTI', 'paxg': 'PAXG', 'pda': 'PDA', 'peaq': 'PEAQ', 'pendle': 'PENDLE', 'pengu': 'PENGU', 'pepe': 'PEPE', 'perp': 'PERP', 'pha': 'PHA', 'play': 'PLAY', 'plume': 'PLUME', 'pnut': 'PNUT', 'pol': 'POL', 'polis': 'POLIS', 'pols': 'POLS', 'pond': 'POND', 'ponke': 'PONKE', 'popcat': 'POPCAT', 'portal': 'PORTAL', 'powr': 'POWR', 'prcl': 'PRCL', 'prime': 'PRIME', 'pro': 'PRO', 'prompt': 'PROMPT', 'prove': 'PROVE', 'pstake': 'PSTAKE', 'ptb': 'PTB', 'puffer': 'PUFFER', 'pump': 'PUMP', 'pups': 'PUPS', 'pyth': 'PYTH', 'pyusd': 'PYUSD', 'q': 'Q', 'qi': 'QI', 'qnt': 'QNT', 'qtum': 'QTUM', 'rad': 'RAD', 'raiin': 'RAIIN', 'rare': 'RARE', 'rari': 'RARI', 'ray': 'RAY', 'rbc': 'RBC', 'red': 'RED', 'rekt': 'REKT', 'render': 'RENDER', 'ren': 'REN', 'repv2': 'REPV2', 'req': 'REQ', 'retardio': 'RETARDIO', 'rez': 'REZ', 'rize': 'RIZE', 'rlc': 'RLC', 'rlusd': 'RLUSD', 'rook': 'ROOK', 'rpl': 'RPL', 'rsr': 'RSR', 'ruji': 'RUJI', 'rune': 'RUNE', 'safe': 'SAFE', 'saga': 'SAGA', 'sahara': 'SAHARA', 'samo': 'SAMO', 'sand': 'SAND', 'sapien': 'SAPIEN', 'saros': 'SAROS', 'sbr': 'SBR', 'sc': 'SC', 'scrt': 'SCRT', 'sdn': 'SDN', 'sei': 'SEI', 's': 'S', 'sgb': 'SGB', 'shib': 'SHIB', 'sigma': 'SIGMA', 'sky': 'SKY', 'slay': 'SLAY', 'snek': 'SNEK', 'snx': 'SNX', 'sogni': 'SOGNI', 'sol': 'SOL', 'sonic': 'SONIC', 'soso': 'SOSO', 'spell': 'SPELL', 'spice': 'SPICE', 'spk': 'SPK', 'spx': 'SPX', 'srm': 'SRM', 'ssv': 'SSV', 'stbl': 'STBL', 'step': 'STEP', 'stg': 'STG', 'storj': 'STORJ', 'strd': 'STRD', 'strk': 'STRK', 'stx': 'STX', 'sui': 'SUI', 'sundog': 'SUNDOG', 'sun': 'SUN', 'super': 'SUPER', 'sushi': 'SUSHI', 'swarms': 'SWARMS', 'sweat': 'SWEAT', 'swell': 'SWELL', 'sxt': 'SXT', 'syn': 'SYN', 'syrup': 'SYRUP', 'tac': 'TAC', 'tanssi': 'TANSSI', 'tao': 'TAO', 'tbtc': 'TBTC', 'teer': 'TEER', 'term': 'TERM', 't': 'T', 'tia': 'TIA', 'titcoin': 'TITCOIN', 'tlm': 'TLM', 'tnsr': 'TNSR', 'toke': 'TOKE', 'token': 'TOKEN', 'ton': 'TON', 'toshi': 'TOSHI', 'trac': 'TRAC', 'tree': 'TREE', 'tremp': 'TREMP', 'tru': 'TRU', 'trump': 'TRUMP', 'trx': 'TRX', 'turbo': 'TURBO', 'tusd': 'TUSD', 'tvk': 'TVK', 'u': 'U', 'ufd': 'UFD', 'uma': 'UMA', 'unfi': 'UNFI', 'uni': 'UNI', 'unite': 'UNITE', 'usd1': 'USD1', 'usdc': 'USDC', 'zusd': 'ZUSD', 'usdd': 'USDD', 'usdg': 'USDG', 'usdq': 'USDQ', 'usdr': 'USDR', 'usds': 'USDS', 'usdt': 'USDT', 'usduc': 'USDUC', 'useless': 'USELESS', 'ust': 'UST', 'usual': 'USUAL', 'uxlink': 'UXLINK', 'vanry': 'VANRY', 'velodrome': 'VELODROME', 'vine': 'VINE', 'virtual': 'VIRTUAL', 'vsn': 'VSN', 'vvv': 'VVV', 'wal': 'WAL', 'waxl': 'WAXL', 'wbtc': 'WBTC', 'wct': 'WCT', 'well': 'WELL', 'wen': 'WEN', 'w': 'W', 'wif': 'WIF', 'win': 'WIN', 'wld': 'WLD', 'wlfi': 'WLFI', 'wmtx': 'WMTX', 'woo': 'WOO', 'xaut': 'XAUT', 'xxbt': 'XXBT', 'xcn': 'XCN', 'xdc': 'XDC', 'xxdg': 'XXDG', 'xetc': 'XETC', 'xion': 'XION', 'xl1': 'XL1', 'xmln': 'XMLN', 'xxmr': 'XXMR', 'xny': 'XNY', 'xrep': 'XREP', 'xxrp': 'XXRP', 'xrt': 'XRT', 'xter': 'XTER', 'xtz': 'XTZ', 'xxlm': 'XXLM', 'xyo': 'XYO', 'xzec': 'XZEC', 'yfi': 'YFI', 'ygg': 'YGG', 'zerebro': 'ZEREBRO', 'zeta': 'ZETA', 'zeus': 'ZEUS', 'zex': 'ZEX', 'zgbp': 'ZGBP', 'zig': 'ZIG', 'zk': 'ZK', 'zora': 'ZORA', 'zro': 'ZRO', 'zrx': 'ZRX'}
    DESIRED_BASE_ASSETS = set(MANUAL_KRAKEN_BASES.values())
    # None = any asset in DESIRED_BASE_ASSETS may be a quote currency, so cross pairs
    # like Q/ADA are included. Set e.g. {'ZUSD', 'ZEUR', 'XXBT'} to restrict to those.
    # Used in 'all' mode ('usd_eur' mode overrides both to {'ZUSD','ZEUR'} and 3).
    DESIRED_QUOTE_ASSETS = None
    # Longest loop to search, in trades. 3 = triangles. 4 adds USD -> A -> B -> C -> USD
    # loops: many more to scan, and four fees to overcome instead of three.
    MAX_PATH_LEGS = 3

    # 3. EXECUTION & RISK MANAGEMENT
    # AUTO_SIZE on: each trade uses the most profitable size the order books
    # support, up to MAX_TRADE_CAPITAL (and never more than your free balance).
    # AUTO_SIZE off: every trade uses exactly TRADE_CAPITAL.
    AUTO_SIZE = True
    MAX_TRADE_CAPITAL = 10000.00
    TRADE_CAPITAL = 1000.00
    # Extra room on each leg's IOC limit price beyond the worst level the book walk reached.
    # Every bit of this is profit you're willing to give back, so keep it tight.
    SLIPPAGE_TOLERANCE_PERCENT = 0.05
    ORDER_TIMEOUT_SECONDS = 4.0
    MOCK_EXECUTION = True

    # 4. PERFORMANCE & LOGGING
    POLL_INTERVAL = 5                 # seconds; one Ticker call per cycle, so this can be short
    BOOK_DEPTH = 100                  # levels fetched per pair during verification
    MAX_VERIFICATIONS_PER_CYCLE = 3   # each costs one Depth call per distinct pair in the triangle
    ANALYZE_CAPACITY = True           # log what trade size each checked triangle could support
    CAPACITY_MAX = 1_000_000.00       # stop the capacity search here (HOME_CURRENCY)
    CAPACITY_SAMPLES = 60             # trade sizes tested between $1 and the max fillable amount
    FEE_REFRESH_SECONDS = 3600
    TRADE_COOLDOWN_SECONDS = 60
    LOG_FILE = 'arb_bot.log'
    AUDIT_LOG_FILE = 'arb_audit.log'
    COVERAGE_FILE = 'arb_coverage.txt'  # per-asset table of what's being scanned, written at startup
    LOG_LEVEL = logging.INFO

# --- END OF CONFIGURATION ---


API_URL = "https://api.kraken.com"


class KrakenError(Exception):
    pass


def fmt_decimal(value, decimals, rounding):
    """Format a float to a fixed number of decimals as a string, as Kraken expects."""
    quantum = Decimal(1).scaleb(-int(decimals))
    return str(Decimal(repr(value)).quantize(quantum, rounding=rounding))


def leg_str(path):
    return " -> ".join([leg['from'] for leg in path] + [path[-1]['to']])


class ArbitrageBot:
    def __init__(self, config):
        self.config = config
        # Apply SCAN_MODE by setting the two values everything else reads.
        if config.SCAN_MODE == 'usd_eur':
            config.DESIRED_QUOTE_ASSETS = {'ZUSD', 'ZEUR'}
            config.MAX_PATH_LEGS = 3
        elif config.SCAN_MODE != 'all':
            raise ValueError(f"SCAN_MODE must be 'usd_eur' or 'all', not {config.SCAN_MODE!r}")
        self.session = None
        self.kapi = krakenex.API()
        self.has_key = False
        self.pairs = {}       # pair_key -> AssetPairs details (online, filtered)
        self.fees = {}        # pair_key -> taker fee as a fraction (0.004 == 0.40%)
        self.triangles = []   # tuples of 3 legs, each starting/ending at HOME_CURRENCY
        self.last_fee_refresh = 0.0
        self.halted = False   # set if a live leg fails mid-cycle; stops further trading
        self.offline_pairs = defaultdict(list)  # asset -> matching pairs skipped as not online
        self.audit_logger = None
        self.setup_logging()

    # ------------------------------------------------------------------ setup

    def setup_logging(self):
        logging.basicConfig(level=self.config.LOG_LEVEL,
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            handlers=[
                                logging.FileHandler(self.config.LOG_FILE, mode='w'),
                                logging.StreamHandler()
                            ])
        self.audit_logger = logging.getLogger('AuditLogger')
        self.audit_logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(self.config.AUDIT_LOG_FILE, mode='w')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.audit_logger.addHandler(handler)
        self.audit_logger.propagate = False

    async def start(self):
        try:
            self.kapi.load_key(self.config.KEY_FILE_NAME)
            self.has_key = True
            logging.info(f"Loaded API credentials from '{self.config.KEY_FILE_NAME}'.")
        except FileNotFoundError:
            if not self.config.MOCK_EXECUTION:
                logging.error(f"FATAL: '{self.config.KEY_FILE_NAME}' not found and MOCK_EXECUTION is off.")
                return
            logging.warning(f"No key file; running mock with fallback fee "
                            f"{self.config.FALLBACK_TAKER_FEE_PERCENT}%.")

        logging.info(f"Bot starting at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info(f"Home currency: {self.config.HOME_CURRENCY}")
        quotes = self.config.DESIRED_QUOTE_ASSETS
        logging.info(f"Scan mode: {self.config.SCAN_MODE} "
                     f"(quotes: {', '.join(sorted(quotes)) if quotes else 'any listed asset'}; "
                     f"max legs: {self.config.MAX_PATH_LEGS})")
        logging.info(f"MOCK EXECUTION is {'ENABLED' if self.config.MOCK_EXECUTION else 'DISABLED - REAL TRADES'}")

        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        try:
            await self.load_pairs()
            if not self.pairs:
                logging.error("No tradable pairs were loaded. Exiting.")
                return
            self.build_triangles()
            self.report_coverage()
            if not self.triangles:
                logging.error("No triangles found for the configured assets. Exiting.")
                return
            await self.refresh_fees()
            await self.run_polling_mode()
        finally:
            await self.session.close()

    # ------------------------------------------------------------- API calls

    async def _public(self, method, params=None):
        async with self.session.get(f"{API_URL}/0/public/{method}", params=params) as r:
            r.raise_for_status()
            data = await r.json()
        if data.get('error'):
            raise KrakenError(f"{method}: {data['error']}")
        return data['result']

    async def _private(self, method, params=None):
        # krakenex is synchronous; run it in a thread so it doesn't block the event loop.
        data = await asyncio.to_thread(self.kapi.query_private, method, params or {})
        if data.get('error'):
            raise KrakenError(f"{method}: {data['error']}")
        return data['result']

    async def fetch_book(self, pair):
        result = await self._public('Depth', {'pair': pair, 'count': self.config.BOOK_DEPTH})
        book = next(iter(result.values()))
        return {
            'asks': [(float(p), float(v)) for p, v, *_ in book.get('asks', [])],
            'bids': [(float(p), float(v)) for p, v, *_ in book.get('bids', [])],
        }

    # ------------------------------------------------------- market structure

    async def load_pairs(self):
        """Keep every online pair whose base AND quote are both assets we care about.

        With DESIRED_QUOTE_ASSETS = None, any allowed asset can act as the quote, so
        cross pairs such as Q/ADA or ADA/ETH are loaded too, not just X/USD, X/EUR, X/XBT.
        """
        logging.info("Loading asset pairs...")
        all_pairs = await self._public('AssetPairs')
        allowed = self.config.DESIRED_BASE_ASSETS | (self.config.DESIRED_QUOTE_ASSETS or set())
        quotes = self.config.DESIRED_QUOTE_ASSETS or allowed
        pairs, skipped = {}, 0
        for key, p in all_pairs.items():
            base, quote = p.get('base'), p.get('quote')
            if key.endswith('.d') or quote not in quotes or base not in allowed:
                continue
            if p.get('status', 'online') != 'online':
                skipped += 1
                self.offline_pairs[base].append(f"{key} ({p.get('status')})")
                self.offline_pairs[quote].append(f"{key} ({p.get('status')})")
                continue
            pairs[key] = p
        self.pairs = pairs

        # Show which assets serve as quote currencies, so you can see which cross
        # pairs (e.g. something/ADA) actually exist on Kraken.
        quote_counts = defaultdict(int)
        for p in pairs.values():
            quote_counts[p['quote']] += 1
        summary = ", ".join(f"{q}:{n}" for q, n in sorted(quote_counts.items(), key=lambda kv: -kv[1]))
        logging.info(f"Loaded {len(pairs)} online pairs ({skipped} skipped as not fully online).")
        logging.info(f"Pairs per quote currency: {summary}")

    def build_triangles(self):
        """Enumerate every loop that starts and ends at HOME_CURRENCY, with
        3 up to MAX_PATH_LEGS legs, never visiting the same asset twice.

        3 legs: USD -> A -> B -> USD        (e.g. USD -> Q -> ADA -> USD)
        4 legs: USD -> A -> B -> C -> USD   (e.g. USD -> Q -> ADA -> EUR -> USD)
        Loops are found once at startup (the pair list doesn't change); each poll
        just re-prices them. Every leg pays a taker fee, so longer loops need a
        bigger price mismatch to break even.
        """
        edges = defaultdict(list)
        for key, p in self.pairs.items():
            base, quote = p['base'], p['quote']
            edges[quote].append({'pair': key, 'type': 'buy', 'from': quote, 'to': base})
            edges[base].append({'pair': key, 'type': 'sell', 'from': base, 'to': quote})

        home = self.config.HOME_CURRENCY
        max_legs = self.config.MAX_PATH_LEGS
        loops = []

        def extend(path, visited):
            current = path[-1]['to']
            for leg in edges[current]:
                nxt = leg['to']
                if nxt == home:
                    if len(path) + 1 >= 3:      # 2-leg loops are just buy+sell of one pair
                        loops.append(tuple(path + [leg]))
                elif nxt not in visited and len(path) + 1 < max_legs:
                    extend(path + [leg], visited | {nxt})

        for first in edges[home]:
            extend([first], {home, first['to']})

        self.triangles = loops
        by_len = defaultdict(int)
        for lp in loops:
            by_len[len(lp)] += 1
        detail = ", ".join(f"{n}-leg: {c}" for n, c in sorted(by_len.items()))
        logging.info(f"Built {len(loops)} candidate loops from {home} ({detail}).")

    def report_coverage(self):
        """Show, for every asset in your list, whether it's actually being scanned.

        Writes a full per-asset table to COVERAGE_FILE and logs a summary. Each asset
        ends up in one of three states:
          SCANNED       - has pairs, and appears in at least one loop the bot prices
          PAIRS, NO LOOP- has pairs, but none of them connect back to HOME_CURRENCY
                          in MAX_PATH_LEGS trades (e.g. only one pair, to EUR, and
                          no EUR leg that closes the loop)
          NOT FOUND     - no online pair on Kraken between this asset and any other
                          asset in your list. Usually: delisted, a different Kraken
                          code (e.g. Kraken uses XXBT, not BTC), or only offline pairs.
        """
        pairs_by_asset = defaultdict(list)
        for key, p in self.pairs.items():
            pairs_by_asset[p['base']].append(key)
            pairs_by_asset[p['quote']].append(key)

        loops_by_asset = defaultdict(int)
        for loop in self.triangles:
            for asset in {leg['to'] for leg in loop}:
                loops_by_asset[asset] += 1

        listed = sorted(self.config.DESIRED_BASE_ASSETS | (self.config.DESIRED_QUOTE_ASSETS or set()))
        scanned, no_loop, missing = [], [], []
        lines = [f"Coverage report  {time.strftime('%Y-%m-%d %H:%M:%S')}  "
                 f"home={self.config.HOME_CURRENCY}  max_legs={self.config.MAX_PATH_LEGS}",
                 f"{'ASSET':<12} {'STATUS':<15} {'LOOPS':>6}  PAIRS"]
        for asset in listed:
            pairs = pairs_by_asset.get(asset, [])
            loops = loops_by_asset.get(asset, 0)
            if loops:
                status = 'SCANNED'
                scanned.append(asset)
            elif pairs:
                status = 'PAIRS, NO LOOP'
                no_loop.append(asset)
            else:
                status = 'NOT FOUND'
                missing.append(asset)
            detail = ", ".join(sorted(pairs))
            if self.offline_pairs.get(asset):
                detail += ("; " if detail else "") + "offline: " + ", ".join(self.offline_pairs[asset])
            lines.append(f"{asset:<12} {status:<15} {loops:>6}  {detail}")

        with open(self.config.COVERAGE_FILE, 'w') as f:
            f.write("\n".join(lines) + "\n")

        logging.info(f"Coverage: {len(listed)} listed assets -> {len(scanned)} scanned, "
                     f"{len(no_loop)} with pairs but no loop, {len(missing)} not found. "
                     f"Full table in {self.config.COVERAGE_FILE}")
        if no_loop:
            logging.info(f"  Pairs but no loop: {', '.join(no_loop)}")
        if missing:
            logging.info(f"  Not found: {', '.join(missing)}")

    async def refresh_fees(self):
        """Per-pair taker fee = the pair's own fee schedule at your 30-day volume tier."""
        volume = None
        if self.has_key:
            try:
                result = await self._private('TradeVolume')
                volume = float(result['volume'])
                logging.info(f"30-day volume: {volume:,.2f} USD")
            except Exception as e:
                logging.warning(f"Could not fetch TradeVolume ({e}); using fallback fee.")

        fallback = self.config.FALLBACK_TAKER_FEE_PERCENT / 100
        for key, p in self.pairs.items():
            schedule = p.get('fees') or []
            if volume is None or not schedule:
                self.fees[key] = fallback
                continue
            pct = schedule[0][1]
            for tier_volume, tier_pct in schedule:
                if volume >= tier_volume:
                    pct = tier_pct
            self.fees[key] = pct / 100
        self.last_fee_refresh = time.time()

    # ------------------------------------------------------------- discovery

    def leg_rate(self, leg, tickers):
        """Top-of-book conversion rate for one leg, net of fee (fee charged in quote)."""
        t = tickers.get(leg['pair'])
        if not t:
            return None
        fee = self.fees[leg['pair']]
        if leg['type'] == 'buy':
            ask = float(t['a'][0])
            return (1 / ask) / (1 + fee) if ask > 0 else None
        bid = float(t['b'][0])
        return bid * (1 - fee) if bid > 0 else None

    def scan(self, tickers):
        """Price every triangle at top-of-book, net of fees.

        Returns a dict:
          candidates - [(triangle, multiplier)] with multiplier > 1, best first
          best_mult  - highest multiplier seen among priced triangles (even if < 1)
          best_tri   - the triangle that produced best_mult
          priced     - how many triangles had a ticker for all three legs
          skipped    - how many were skipped because a leg had no ticker data
        """
        candidates, best_mult, best_tri = [], 0.0, None
        priced = skipped = 0
        for tri in self.triangles:
            mult = 1.0
            for leg in tri:
                rate = self.leg_rate(leg, tickers)
                if rate is None:
                    skipped += 1
                    break
                mult *= rate
            else:
                priced += 1
                if mult > best_mult:
                    best_mult, best_tri = mult, tri
                if mult > 1:
                    candidates.append((tri, mult))
        candidates.sort(key=lambda c: c[1], reverse=True)
        return {'candidates': candidates, 'best_mult': best_mult, 'best_tri': best_tri,
                'priced': priced, 'skipped': skipped}

    # ---------------------------------------------------------- verification

    def simulate_leg(self, leg, book, amount_in):
        """Walk the book for amount_in of the leg's 'from' asset.
        Returns dict(out, base_volume, cost, worst_price) or None if the book is too thin."""
        fee = self.fees[leg['pair']]
        if leg['type'] == 'buy':
            budget = amount_in / (1 + fee)   # quote spent on fills; fee is charged on top (fciq)
            remaining, base_got, worst = budget, 0.0, None
            for price, vol in book['asks']:
                worst = price
                if price * vol >= remaining:
                    base_got += remaining / price
                    remaining = 0.0
                    break
                base_got += vol
                remaining -= price * vol
            if remaining > 0:
                return None
            return {'out': base_got, 'base_volume': base_got, 'cost': budget, 'worst_price': worst}

        remaining, quote_got, worst = amount_in, 0.0, None
        for price, vol in book['bids']:
            take = min(vol, remaining)
            quote_got += take * price
            remaining -= take
            worst = price
            if remaining <= amount_in * 1e-12:
                remaining = 0.0
                break
        if remaining > 0:
            return None
        return {'out': quote_got * (1 - fee), 'base_volume': amount_in,
                'cost': quote_got, 'worst_price': worst}

    def meets_minimums(self, pair, base_volume, cost):
        p = self.pairs[pair]
        if base_volume < float(p.get('ordermin') or 0):
            return False
        if cost < float(p.get('costmin') or 0):
            return False
        return True

    def simulate_path(self, tri, books, capital):
        """Run `capital` of HOME_CURRENCY through all three legs against the given books.
        Returns {'plan': [...], 'profit': float} on success, or
        {'fail': 'thin' | 'min', 'leg': leg, 'amount': amount_in} if a leg can't be filled."""
        amount = capital
        plan = []
        for leg in tri:
            sim = self.simulate_leg(leg, books[leg['pair']], amount)
            if sim is None:
                return {'fail': 'thin', 'leg': leg, 'amount': amount}
            if not self.meets_minimums(leg['pair'], sim['base_volume'], sim['cost']):
                return {'fail': 'min', 'leg': leg, 'amount': amount}
            plan.append({**leg, 'amount_in': amount, **sim})
            amount = sim['out']
        return {'plan': plan, 'profit': amount - capital}

    def analyze_capacity(self, tri, books):
        """Work out how much HOME_CURRENCY this triangle could actually take.

        Bigger trades eat deeper into each book at worse prices, so profit first
        rises with size, peaks, then falls (and eventually turns negative). This
        finds three sizes:
          max_fill        - largest amount the fetched books can absorb at all
          best_size       - the amount that maximizes net profit in dollars
          max_profitable  - largest amount whose net profit is still >= PROFIT_THRESHOLD
        Limits: only BOOK_DEPTH levels are fetched, so max_fill can understate the
        real book; and it's a snapshot that other traders can take in milliseconds.
        """
        cfg = self.config

        def profit_at(x):
            r = self.simulate_path(tri, books, x)
            return r.get('profit')  # None if unfillable / below minimums at size x

        # 1. Largest fillable amount: double from TRADE_CAPITAL until the books run
        #    out (or we hit CAPACITY_MAX), then binary-search the boundary.
        lo, hi = 0.0, cfg.TRADE_CAPITAL
        if self.simulate_path(tri, books, hi).get('fail') == 'thin':
            # Even TRADE_CAPITAL is too big; search downward instead.
            lo = 0.0
        else:
            while hi < cfg.CAPACITY_MAX and self.simulate_path(tri, books, hi * 2).get('fail') != 'thin':
                hi *= 2
            lo, hi = hi, min(hi * 2, cfg.CAPACITY_MAX)
            if self.simulate_path(tri, books, hi).get('fail') != 'thin':
                lo = hi  # fillable all the way to the cap
        for _ in range(40):
            if hi - lo < 0.01:
                break
            mid = (lo + hi) / 2
            if self.simulate_path(tri, books, mid).get('fail') == 'thin':
                hi = mid
            else:
                lo = mid
        max_fill = lo
        if max_fill < 1:
            return None

        # 2. Sample profit on a log-spaced grid from $1 to max_fill.
        n = cfg.CAPACITY_SAMPLES
        sizes = [max_fill ** (i / (n - 1)) for i in range(n)]  # 1 .. max_fill
        samples = [(x, profit_at(x)) for x in sizes]
        valid = [(x, p) for x, p in samples if p is not None]
        if not valid:
            return {'max_fill': max_fill, 'best_size': None, 'best_profit': None,
                    'min_size': None, 'max_profitable': None}

        best_size, best_profit = max(valid, key=lambda s: s[1])
        min_size = valid[0][0]  # smallest size that clears the pair minimums

        # 3. Largest size still above the profit floor: take the last profitable
        #    sample and binary-search toward the next (unprofitable) one.
        max_profitable = None
        profitable_idx = [i for i, (x, p) in enumerate(samples)
                          if p is not None and p >= cfg.PROFIT_THRESHOLD]
        if profitable_idx:
            i = profitable_idx[-1]
            lo = samples[i][0]
            hi = samples[i + 1][0] if i + 1 < len(samples) else lo
            for _ in range(40):
                if hi - lo < 0.01:
                    break
                mid = (lo + hi) / 2
                p = profit_at(mid)
                if p is not None and p >= cfg.PROFIT_THRESHOLD:
                    lo = mid
                else:
                    hi = mid
            max_profitable = lo

        return {'max_fill': max_fill, 'best_size': best_size, 'best_profit': best_profit,
                'min_size': min_size, 'max_profitable': max_profitable}

    def log_capacity(self, tri, cap):
        """One readable summary line per checked triangle (main log + audit log)."""
        ccy = self.config.HOME_CURRENCY
        if cap is None:
            msg = f"  Capacity {leg_str(tri)}: books too thin to fill even $1."
        elif cap['best_profit'] is None:
            msg = (f"  Capacity {leg_str(tri)}: books absorb up to {cap['max_fill']:,.2f} {ccy}, "
                   f"but no size clears the pairs' minimum order sizes.")
        elif cap['max_profitable'] is None:
            msg = (f"  Capacity {leg_str(tri)}: not profitable at any size "
                   f"(best {cap['best_profit']:+.4f} {ccy} at {cap['best_size']:,.2f}; "
                   f"books absorb up to {cap['max_fill']:,.2f}).")
        else:
            edge = cap['best_profit'] / cap['best_size'] * 100
            msg = (f"  Capacity {leg_str(tri)}: profitable from {cap['min_size']:,.2f} "
                   f"to {cap['max_profitable']:,.2f} {ccy}. "
                   f"Peak net {cap['best_profit']:.4f} {ccy} at {cap['best_size']:,.2f} "
                   f"({edge:+.3f}%). Books absorb up to {cap['max_fill']:,.2f}"
                   f"{' (cap reached)' if cap['max_fill'] >= self.config.CAPACITY_MAX else ''}.")
        logging.info(msg)
        self.audit_logger.info(msg)

    def choose_trade_size(self, tri, books, limit):
        """Find the trade size in [$1, limit] that maximizes net profit in dollars.

        Profit vs. size rises while you're filling at good prices, peaks, then falls
        as deeper (worse) book levels eat the edge. So: test a log-spaced grid of
        sizes to find the rough peak, then narrow in on it with a ternary search
        between the neighbouring grid points. Returns (size, profit) or (None, None)
        if no size in range is fillable and above the pairs' minimums.
        """
        def profit_at(x):
            return self.simulate_path(tri, books, x).get('profit')

        n = self.config.CAPACITY_SAMPLES
        sizes = [limit ** (i / (n - 1)) for i in range(n)]       # 1 .. limit
        samples = [(x, profit_at(x)) for x in sizes]
        valid = [(i, x, p) for i, (x, p) in enumerate(samples) if p is not None]
        if not valid:
            return None, None
        i, best_x, best_p = max(valid, key=lambda v: v[2])

        lo = sizes[i - 1] if i > 0 else sizes[0]
        hi = sizes[i + 1] if i + 1 < n else sizes[-1]
        for _ in range(60):
            if hi - lo < 0.01:
                break
            m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
            p1, p2 = profit_at(m1), profit_at(m2)
            p1 = float('-inf') if p1 is None else p1
            p2 = float('-inf') if p2 is None else p2
            if p1 < p2:
                lo = m1
            else:
                hi = m2
        x = (lo + hi) / 2
        p = profit_at(x)
        if p is not None and p > best_p:
            best_x, best_p = x, p
        return best_x, best_p

    async def available_home_balance(self):
        """Free HOME_CURRENCY in your Kraken account (live mode only)."""
        balances = await self._private('Balance')
        return float(balances.get(self.config.HOME_CURRENCY, 0))

    async def verify(self, tri):
        """Re-price the loop against fresh depth and decide how much to trade.

        AUTO_SIZE on:  trade the most profitable size up to MAX_TRADE_CAPITAL
                       (and, live, up to your actual free balance).
        AUTO_SIZE off: trade exactly TRADE_CAPITAL.
        Also runs the capacity report on the same books. Returns a plan or None."""
        self.audit_logger.info(f"--- VERIFY {leg_str(tri)} ---")
        pairs = list({leg['pair'] for leg in tri})
        results = await asyncio.gather(*(self.fetch_book(p) for p in pairs), return_exceptions=True)
        books = dict(zip(pairs, results))
        for pair, book in books.items():
            if isinstance(book, Exception):
                self.audit_logger.warning(f"  {pair}: book fetch failed ({book})")
                return None

        # How much could this loop take? Logged whether or not it passes, so you
        # can see when a different size would have worked.
        if self.config.ANALYZE_CAPACITY:
            self.log_capacity(tri, self.analyze_capacity(tri, books))

        ccy = self.config.HOME_CURRENCY
        limit = self.config.MAX_TRADE_CAPITAL if self.config.AUTO_SIZE else self.config.TRADE_CAPITAL
        if not self.config.MOCK_EXECUTION:
            # Never size a live trade above what's actually in the account. Keep 1%
            # back so rounding and fees on the first leg can't overdraw it.
            try:
                free = await self.available_home_balance()
            except Exception as e:
                self.audit_logger.warning(f"  Could not read balance ({e}); skipping.")
                return None
            if free * 0.99 < limit:
                logging.info(f"  Free {ccy} balance {free:,.2f} is below the "
                             f"{limit:,.2f} size limit; capping at {free * 0.99:,.2f}.")
                limit = free * 0.99
            if limit < 1:
                logging.warning(f"  Not enough {ccy} to trade (free: {free:,.2f}).")
                return None

        if self.config.AUTO_SIZE:
            capital, _ = self.choose_trade_size(tri, books, limit)
            if capital is None:
                self.audit_logger.info(f"  No fillable size up to {limit:,.2f} {ccy}.")
                return None
            self.audit_logger.info(f"  Auto-size: best size up to {limit:,.2f} is {capital:,.2f} {ccy}")
        else:
            capital = limit
        result = self.simulate_path(tri, books, capital)
        if 'fail' in result:
            leg = result['leg']
            why = "book too thin" if result['fail'] == 'thin' else "below ordermin/costmin"
            self.audit_logger.info(f"  {leg['pair']} ({leg['type'].upper()}): {why} "
                                   f"for {result['amount']:.8g} {leg['from']}")
            return None

        for step in result['plan']:
            self.audit_logger.info(
                f"  {step['pair']} ({step['type'].upper()}): {step['amount_in']:.8g} {step['from']} -> "
                f"{step['out']:.8g} {step['to']}, worst level {step['worst_price']:.8g}, "
                f"fee {self.fees[step['pair']] * 100:.3f}%")
        profit = result['profit']
        self.audit_logger.info(f"  Net profit at {capital:.2f}: {profit:.4f} {self.config.HOME_CURRENCY}")
        if profit < self.config.PROFIT_THRESHOLD:
            return None
        return {'path': result['plan'], 'profit': profit, 'capital': capital}

    # ------------------------------------------------------------- execution

    async def place_leg(self, leg, amount_in):
        """Send one IOC limit order and wait for it to close.
        Returns (received_amount, fully_filled)."""
        p = self.pairs[leg['pair']]
        fee = self.fees[leg['pair']]
        tol = self.config.SLIPPAGE_TOLERANCE_PERCENT / 100

        if leg['type'] == 'buy':
            limit = leg['worst_price'] * (1 + tol)
            volume = amount_in / (1 + fee) / limit
        else:
            limit = leg['worst_price'] * (1 - tol)
            volume = amount_in

        vol_str = fmt_decimal(volume, p['lot_decimals'], ROUND_DOWN)
        px_str = fmt_decimal(limit, p['pair_decimals'], ROUND_HALF_UP)
        params = {
            'pair': leg['pair'], 'type': leg['type'], 'ordertype': 'limit',
            'price': px_str, 'volume': vol_str, 'timeinforce': 'IOC',
            'oflags': 'fciq',  # always pay fees in quote, which is what the simulation assumes
        }
        logging.info(f"  ORDER {leg['type'].upper()} {vol_str} {leg['pair']} @ {px_str} (IOC)")
        result = await self._private('AddOrder', params)
        txid = result['txid'][0]
        order = await self.wait_for_close(txid)

        vol_exec = float(order['vol_exec'])
        cost, fee_paid = float(order['cost']), float(order['fee'])
        received = vol_exec if leg['type'] == 'buy' else cost - fee_paid
        fully_filled = vol_exec >= float(vol_str) * 0.999
        logging.info(f"  FILLED {vol_exec}/{vol_str}, cost {cost}, fee {fee_paid} ({order['status']})")
        return received, fully_filled

    async def wait_for_close(self, txid):
        deadline = time.monotonic() + self.config.ORDER_TIMEOUT_SECONDS
        while True:
            result = await self._private('QueryOrders', {'txid': txid})
            order = result[txid]
            if order['status'] in ('closed', 'canceled', 'expired'):
                return order
            if time.monotonic() > deadline:
                # IOC orders shouldn't linger; cancel defensively and report what filled.
                try:
                    await self._private('CancelOrder', {'txid': txid})
                except Exception:
                    pass
                result = await self._private('QueryOrders', {'txid': txid})
                return result[txid]
            await asyncio.sleep(0.25)

    async def execute_arbitrage(self, opportunity):
        path = opportunity['path']
        capital = opportunity['capital']
        logging.info(f"Executing {leg_str(path)} with {capital:,.2f} {self.config.HOME_CURRENCY}, "
                     f"expected net {opportunity['profit']:.4f} {self.config.HOME_CURRENCY}")

        if self.config.MOCK_EXECUTION:
            for leg in path:
                logging.info(f"  MOCK {leg['type'].upper()} {leg['pair']}: {leg['amount_in']:.8g} "
                             f"{leg['from']} -> {leg['out']:.8g} {leg['to']}")
            logging.info("MOCK EXECUTION complete.")
            return

        logging.warning("ENTERING REAL TRADE EXECUTION.")
        amount = capital
        for i, leg in enumerate(path):
            try:
                received, full = await self.place_leg(leg, amount)
            except Exception as e:
                self._halt(f"leg {i + 1} ({leg['pair']}) errored: {e}", leg['from'], amount)
                return
            if not full:
                self._halt(f"leg {i + 1} ({leg['pair']}) partially filled",
                           f"{leg['to']} and {leg['from']}", received)
                return
            amount = received

        pnl = amount - capital
        logging.info(f"Cycle complete. Realized: {pnl:.4f} {self.config.HOME_CURRENCY} "
                     f"(expected {opportunity['profit']:.4f})")

    def _halt(self, reason, holding, amount):
        # Deliberately no automatic unwind: market-dumping a stranded leg can cost far more
        # than the arb was worth. Stop trading and let a human decide.
        self.halted = True
        logging.critical(f"HALTING TRADING: {reason}. Check balances; may be holding "
                         f"~{amount:.8g} in {holding}. Restart the bot after resolving.")

    # ------------------------------------------------------------- main loop

    async def run_polling_mode(self):
        """Main loop. Each cycle runs a cheap screen over every triangle, then an
        expensive check on the few that pass, then (maybe) a trade.

        Reading the "multiplier" in the logs:
          It's what $1 becomes after going around the triangle, net of every
          taker fees, at the best bid/ask (top of book).
            1.00000  -> break even
            0.99350  -> you'd lose 0.65% (typical: three fees of ~0.2-0.4% each)
            1.00120  -> you'd gain 0.12% *if* the top-of-book quantity were enough
          The log also shows this as "edge", i.e. (multiplier - 1) in percent.
          A multiplier > 1 is only a *candidate*: top-of-book prices ignore how
          much volume sits at that price, so each candidate is re-checked against
          the full order book at real trade sizes before anything is traded.
        """
        cycle = 0
        while True:
            cycle += 1
            cycle_start = time.monotonic()
            try:
                # --- 1. Fees -------------------------------------------------------
                # Your fee tier depends on 30-day volume, which drifts slowly, so we
                # only re-read it every FEE_REFRESH_SECONDS (default: hourly).
                if time.time() - self.last_fee_refresh > self.config.FEE_REFRESH_SECONDS:
                    await self.refresh_fees()
                    logging.info(f"[cycle {cycle}] Fees refreshed for {len(self.fees)} pairs.")

                # --- 2. Screen: price every triangle at top of book ----------------
                # One /Ticker call returns best bid/ask for every pair on Kraken.
                # scan() multiplies the fee-adjusted rates of every leg in each loop.
                tickers = await self._public('Ticker')
                result = self.scan(tickers)
                candidates = result['candidates']
                best_mult, best_tri = result['best_mult'], result['best_tri']
                best_edge = (best_mult - 1) * 100

                # Coverage: if 'skipped' is large, some pairs are missing from the
                # ticker response (delisted, renamed, or temporarily halted).
                logging.debug(f"[cycle {cycle}] Priced {result['priced']} triangles, "
                              f"skipped {result['skipped']} (missing ticker data).")

                if not candidates:
                    # Normal state. The closest-to-profitable loop is still logged so you
                    # can watch how near the market gets to break-even over time.
                    if best_tri:
                        logging.info(f"[cycle {cycle}] Priced {result['priced']}/{len(self.triangles)} loops. "
                                     f"No opportunities. Closest: {leg_str(best_tri)} "
                                     f"multiplier {best_mult:.5f} (edge {best_edge:+.3f}%)")
                    else:
                        logging.warning(f"[cycle {cycle}] No triangles could be priced this cycle.")
                else:
                    # --- 3. Verify: re-price the best few against real depth --------
                    # Each verify() costs one Depth request per distinct pair, so we cap
                    # how many we check (MAX_VERIFICATIONS_PER_CYCLE). Details of each
                    # check (per-leg amounts, worst price reached, fee) go to the audit log.
                    to_check = candidates[:self.config.MAX_VERIFICATIONS_PER_CYCLE]
                    logging.info(f"[cycle {cycle}] {len(candidates)} top-of-book candidate(s). "
                                 f"Best: {leg_str(candidates[0][0])} multiplier {best_mult:.5f} "
                                 f"(edge {best_edge:+.3f}%). Verifying top {len(to_check)}.")

                    for rank, (tri, mult) in enumerate(to_check, start=1):
                        plan = await self.verify(tri)
                        if not plan:
                            # Common reasons: thin book at the trade size, below the pair's
                            # minimum order, or profit under PROFIT_THRESHOLD. See audit log.
                            logging.info(f"  #{rank} {leg_str(tri)} (top-of-book {(mult - 1) * 100:+.3f}%) "
                                         f"rejected after depth check - see {self.config.AUDIT_LOG_FILE}")
                            continue

                        logging.info(f"  #{rank} {leg_str(tri)} VERIFIED: expected net "
                                     f"{plan['profit']:.4f} {self.config.HOME_CURRENCY} on "
                                     f"{plan['capital']:,.2f}"
                                     f"{' (auto-sized)' if self.config.AUTO_SIZE else ''}")

                        # --- 4. Trade (or simulate) the first verified triangle --------
                        # A previous live trade that failed mid-way sets self.halted; we
                        # keep scanning so you can see the market, but never trade again
                        # until restarted.
                        if self.halted:
                            logging.warning(f"  Trading is halted; not executing {leg_str(plan['path'])}.")
                            break
                        await self.execute_arbitrage(plan)

                        # After a real trade, pause so balances settle and we don't chase
                        # the same (now-gone) opportunity. Mock mode skips the pause.
                        if not self.config.MOCK_EXECUTION:
                            logging.info(f"  Cooling down {self.config.TRADE_COOLDOWN_SECONDS}s after trade.")
                            await asyncio.sleep(self.config.TRADE_COOLDOWN_SECONDS)
                        break  # one trade per cycle at most
                    else:
                        # for/else: runs only if the loop finished without 'break',
                        # i.e. none of the checked candidates held up.
                        logging.info(f"[cycle {cycle}] None of the top {len(to_check)} candidate(s) "
                                     f"survived the depth check.")

            except Exception as e:
                # Network blips and Kraken API errors land here. The loop keeps running;
                # repeated errors every cycle usually mean rate limiting or a bad key.
                logging.error(f"[cycle {cycle}] Error in polling loop: {e}", exc_info=True)

            elapsed = time.monotonic() - cycle_start
            logging.debug(f"[cycle {cycle}] Took {elapsed:.2f}s; sleeping {self.config.POLL_INTERVAL}s.")
            await asyncio.sleep(self.config.POLL_INTERVAL)


async def main():
    bot = ArbitrageBot(Config())
    await bot.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot shutting down manually.")
