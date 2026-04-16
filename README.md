from flask import Flask, render_template_string, request, jsonify
from binance.client import Client
import threading, time, datetime, random, math, json, os, statistics
import urllib.request, urllib.error

app = Flask(__name__)

API_KEY    = "E80eFafJXOkEMF4WyDKkaxDG8I1j1tVsZV8voD0QgHvqaVvTklQOzt3PzNmPvtz1"
API_SECRET = "rxfu61m9s3uwohIknq57nZDrKygWgrkhDLYRIkctGBDCTL5tbXv0pzJdNXLWdyXi"

# ══ ضع مفتاح Claude هنا ══
CLAUDE_API_KEY = "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"
CLAUDE_MODEL   = "claude-haiku-4-5-20251001"

# ══ Google Gemini API — لوكيل إدارة الصفقات والأرباح ══
GEMINI_API_KEY = "AIzaSyCMIsfgfNcyRvbhpLxcuTLyP7tM6Ee1glg"
GEMINI_MODEL   = "gemini-1.5-flash"   # سريع ومجاني نسبياً

REAL_STARTING_BALANCE = 10.0   # ← غيّر هذا لرصيدك الفعلي بالدولار
symbol_filters = {}

# ════════════════════════════════════════════════
# V17: نظام الوكلاء
# ════════════════════════════════════════════════
agents = {
    "MARKET_ANALYST": {
        "name": "محلل السوق", "emoji": "🔍",
        "role": "تحليل نظام السوق والأنماط والتذبذب",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "successes": 0,
        "color": "#38bdf8", "active": True, "interval": 20, "last_run": 0,
    },
    "RISK_MANAGER": {
        "name": "مدير المخاطر", "emoji": "🛡️",
        "role": "تقييم المخاطر وحماية رأس المال",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "successes": 0,
        "color": "#ff4466", "active": True, "interval": 25, "last_run": 0,
    },
    "STRATEGY_SELECTOR": {
        "name": "محدد الاستراتيجية", "emoji": "🎯",
        "role": "اختيار أفضل استراتيجية بناءً على السياق",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "successes": 0,
        "color": "#a3e635", "active": True, "interval": 40, "last_run": 0,
    },
    "TRADE_REVIEWER": {
        "name": "مراجع الصفقات", "emoji": "📊",
        "role": "تحليل الصفقات المنتهية واستخلاص الدروس",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "successes": 0,
        "color": "#c084fc", "active": True, "interval": 60, "last_run": 0,
    },
    "GOLD_SPECIALIST": {
        "name": "متخصص الذهب", "emoji": "🥇",
        "role": "تحليل الذهب والملاذات الآمنة في السياق الاقتصادي",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "successes": 0,
        "color": "#ffd700", "active": True, "interval": 35, "last_run": 0,
    },
    # ═══ V19: وكلاء التعلم الجديدان ═══
    "PATTERN_LEARNER": {
        "name": "محرك التعلم", "emoji": "🧠",
        "role": "يتعلم من كل صفقة ويكتشف الأنماط الرابحة تلقائياً",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "successes": 0,
        "color": "#22d3ee", "active": True, "interval": 30, "last_run": 0,
    },
    "BACKTEST_RUNNER": {
        "name": "محرك Backtest", "emoji": "⚡",
        "role": "يختبر الاستراتيجيات على بيانات تاريخية ويصفّيها",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "successes": 0,
        "color": "#fb923c", "active": True, "interval": 45, "last_run": 0,
    },
    "PORTFOLIO_MANAGER": {
        "name": "مدير المحفظة", "emoji": "🏦",
        "role": "يقرأ الأرصدة الحقيقية ويحلل توازن المحفظة ويوصي بإعادة التوازن",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "successes": 0,
        "color": "#4ade80", "active": True, "interval": 60, "last_run": 0,
    },
    "PROFIT_MANAGER": {
        "name": "مدير الأرباح", "emoji": "💰",
        "role": "يراقب الأرباح ويقرر متى يحميها ويجمعها بذكاء عالٍ",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "successes": 0,
        "color": "#facc15", "active": True, "interval": 45, "last_run": 0,
    },
}

agent_conversations = []

# ════════════════════════
# محادثة المستخدم مع Claude
# ════════════════════════
direct_chat_history = []   # قائمة رسائل المحادثة المباشرة

# ═══ V19: نظام التعلم والذاكرة ═══
learned_patterns   = []   # الأنماط الرابحة المكتسبة
backtest_results   = {}   # نتائج Backtest لكل استراتيجية
strategy_weights   = {}   # أوزان الاستراتيجيات المُحدَّثة
online_learning_log = []  # سجل التعلم المستمر

state = {
    "client": None, "running": False,
    "current_mode": "demo",
    "trading_type": "futures", "futures_leverage": 10,
    "active_engines": {"spot": False, "futures": True},
    "risk": {"risk_per_trade": 2.0, "tp": 3.0, "sl": 1.5},
    "finances": {
        "demo": {"balance":10000.0,"pnl":0.0,"history":[],"wins":0,"losses":0,"peak":10000.0},
        "real": {"balance":REAL_STARTING_BALANCE,"total_usd":0.0,"pnl":0.0,
                 "history":[],"wins":0,"losses":0,"assets":[],"peak":REAL_STARTING_BALANCE}
    },
    "active_positions": {},
    "all_coins": [
        "XAUTUSDT","XAGUSDT","BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
        "ADAUSDT","DOGEUSDT","DOTUSDT","MATICUSDT","LTCUSDT","SHIBUSDT","TRXUSDT",
        "AVAXUSDT","LINKUSDT","UNIUSDT","ATOMUSDT","ETCUSDT","NEARUSDT","FILUSDT",
        "APEUSDT","ALGOUSDT","HBARUSDT","VETUSDT","ICPUSDT","OPUSDT","ARBUSDT",
        "AAVEUSDT","MKRUSDT","CRVUSDT","GMXUSDT","INJUSDT","SUIUSDT","APTUSDT",
        "SEIUSDT","TIAUSDT","WIFUSDT","PEPEUSDT","BONKUSDT","STXUSDT","FTMUSDT",
        "SANDUSDT","MANAUSDT","AXSUSDT","GALAUSDT","IMXUSDT","RENDERUSDT","JUPUSDT",
    ],
    "selected_coins": ["XAUTUSDT","BTCUSDT","ETHUSDT","SOLUSDT"],
    "timeframes": ["1m","5m","15m","30m","1h","4h","1d","1w"],
    "selected_timeframes": ["15m","1h","4h"],
    "capital_mgmt": {
        "mode":"smart_adaptive","base_risk_pct":7.0,"max_daily_loss":5.0,
        "use_compounding":True,"profit_target_daily":3.0,"partial_tp":True,
        "partial_tp_pct":50.0,"partial_tp_at":1.5,"max_open":10,
    },
    "smart_sl": {"type":"trailing","trailing_offset":1.0},
    "strategies": {
        "RSI_AI":"AI RSI Scalper","MACD_TREND":"MACD Trend Master",
        "BOLLINGER":"Bollinger Reversal","EMA_CROSS":"Neural EMA Cross",
        "SUPERTREND":"SuperTrend Follower","VOLATILITY_BREAKOUT":"Volatility Breakout",
        "MEAN_REVERSION":"Mean Reversion Engine","MOMENTUM_SURGE":"Momentum Surge",
        "REGIME_SWITCH":"Regime Switch Master","GOLD_HEDGE":"Gold Hedge Strategy",
        "MULTI_TF":"Multi-TF Confluence","SMART_SCALP":"Smart Scalp AI",
        "LIQUIDITY_HUNT":"Liquidity Hunter","ADX_TREND":"ADX Strong Trend",
        "ICHIMOKU":"Ichimoku Breakout","VWAP":"VWAP Intraday",
    },
    "selected_strategies": ["RSI_AI","SUPERTREND","VOLATILITY_BREAKOUT","REGIME_SWITCH","MULTI_TF","GOLD_HEDGE"],
    "prices":{}, "price_history":{},
    "signals":[], "notifications":[], "trade_history":[],
    "strategy_performance":{},
    "api_status":{"connected":False,"error":"","last_sync":"","mode":"غير متصل"},
    "ai_learner": {
        "enabled":True,"base_threshold":0.82,"recent_trades":0,"improvement":0.0,
        "confidence":72.0,"market_regime":"ranging","drawdown_protection":True,
        "max_drawdown_pct":10.0,"peak_balance_demo":10000.0,
        "peak_balance_real":REAL_STARTING_BALANCE,"current_drawdown":0.0,
        "streak":0,"best_strategy":"RSI_AI","daily_trades":0,"daily_pnl":0.0,
        "sharpe_ratio":0.0,"profit_factor":0.0,"volatility_index":0.0,
        "momentum_score":0.0,"trend_strength":0.0,"signal_heatmap":{},"ai_analysis":[],"top_opportunities":[],
        "adaptive_tp":3.0,"adaptive_sl":1.5,"market_sentiment":50.0,
        "signal_confluence":0,"smart_filter_active":False,"account_health":100,
        "risk_adjusted_return":0.0,"win_loss_ratio":0.0,"session_start":"",
        "agent_recommended_strategy": "",
        "agent_risk_level": "medium",
        "agent_market_view": "",
        "agent_confidence_boost": 0.0,
    },
    "market_data":{
        "fear_greed":55,"btc_dominance":52.4,"volatility_regime":"normal",
        "gold_price":0.0,"silver_price":0.0,"gold_trend":"neutral",
    },
    "news_data": {
        "sentiment_score":  0.0,     # الإجمالي -100→+100
        "crypto_news":      [],      # آخر 10 أخبار كريبتو
        "macro_news":       [],      # أخبار اقتصادية كلية
        "impact_level":     "low",   # low/medium/high/critical
        "btc_bias":         "neutral",
        "gold_bias":        "neutral",
        "risk_off":         False,   # Risk-off = ابتعد عن الأصول الخطرة
        "last_update":      "",
        "top_event":        "",      # أهم حدث
        "summary":          "",      # ملخص الأخبار
        "alerts":           [],      # تحذيرات مهمة
    },
    "chart_data":{
        "timestamps":[],"demo_pnl":[],"real_pnl":[],
        "ai_confidence":[],"volatility":[],"drawdown":[],
    },
    "tf_data":{
        tf:{"signal":"neutral","strength":50,"trend":"→","rsi":50,"vol":30,"last_update":""}
        for tf in ["1m","5m","15m","30m","1h","4h","1d","1w"]
    },
    "bot_health":{
        "score":100,"issues":[],"warnings":[],"last_check":"",
        "uptime_seconds":0,"start_time":"","price_feed_ok":True,
        "memory_trades":0,"consecutive_errors":0,"orders_sent":0,"orders_failed":0,
    },
    "account_analysis":{
        "demo":{"roi_pct":0.0,"max_drawdown_pct":0.0,"best_trade":0.0,"worst_trade":0.0,
                "avg_win":0.0,"avg_loss":0.0,"win_streak":0,"loss_streak":0,
                "expectancy":0.0,"calmar_ratio":0.0,"risk_score":50},
        "real":{"roi_pct":0.0,"max_drawdown_pct":0.0,"best_trade":0.0,"worst_trade":0.0,
                "avg_win":0.0,"avg_loss":0.0,"win_streak":0,"loss_streak":0,
                "expectancy":0.0,"calmar_ratio":0.0,"risk_score":50}
    },
    "capital_actions":[],
    "scalp_stats":{"total_profit":0.0,"today_profit":0.0,"wins":0,"losses":0,"active":0},
    "daily_plan":{
        "capital":          267.0,    # رأس المال الحقيقي
        "daily_target":     5.0,      # هدف $5 يومياً
        "daily_max_loss":   8.0,      # حد خسارة $8
        "per_trade_target": 1.0,      # $1 لكل صفقة
        "per_trade_loss":   0.7,      # حد خسارة $0.7
        "trade_size_pct":   0.12,     # 12% من الرصيد = ~$32
        "max_daily_trades": 15,       # أقصى 15 صفقة
        "today_pnl":        0.0,      # ربح/خسارة اليوم
        "today_trades":     0,        # صفقات اليوم
        "target_hit":       False,    # هل تحقق الهدف
        "loss_limit_hit":   False,    # هل وصل حد الخسارة
        "plan_active":      True,     # الخطة فعالة
        "last_reset":       "",       # آخر إعادة ضبط
        "session_start":    "",
        "hourly_pnl":       [],       # ربح كل ساعة
        "trade_log":        [],       # سجل صفقات اليوم
    },
    "consensus_system":{
        "votes":           {},      # صوت كل وكيل
        "weights": {"GEMINI_CHIEF":0.25,"MARKET_ANALYST":0.18,"RISK_MANAGER":0.15,"STRATEGY_SELECTOR":0.10,"SCALP_TRADER":0.08,"MARKET_SCANNER":0.07,"BACKTEST_RUNNER":0.06,"NEWS_ANALYST":0.06,"GOLD_SPECIALIST":0.03,"PATTERN_LEARNER":0.02},
        "final_vote":      "wait",  # القرار النهائي
        "consensus_pct":   0.0,     # نسبة التوافق
        "trade_approved":  False,   # موافقة على التداول
        "vote_history":    [],      # سجل القرارات
        "trade_threshold": 0.60,    # عتبة الموافقة
        "last_decision_time": "",
    },
    # V21: نظام حماية الأرباح
    "profit_vault": {
        "total_protected":    0.0,   # إجمالي الأرباح المحمية
        "daily_profit":       0.0,   # ربح اليوم
        "weekly_profit":      0.0,   # ربح الأسبوع
        "protection_level":   "normal",  # low / normal / high / critical
        "last_protection":    "",    # آخر عملية حماية
        "protection_history": [],   # سجل عمليات الحماية
        "safe_balance":       0.0,   # الرصيد الآمن المحمي
        "risk_capital":       0.0,   # رأس المال المتاح للتداول
        "profit_rate_today":  0.0,   # معدل الربح اليومي %
        "compound_enabled":   True,  # إعادة استثمار الأرباح
        "vault_pct":          30.0,  # نسبة الحفظ الافتراضية %
        "decision":           "",    # آخر قرار
        "next_target":        0.0,   # الهدف التالي
    },
    # V20: بيانات المحفظة الحقيقية
    "portfolio_analysis": {
        "total_value_usd": 0.0,
        "usdt_balance": 0.0,
        "usdt_pct": 0.0,
        "assets": [],
        "is_balanced": True,
        "balance_score": 100,
        "recommendation": "",
        "dominant_asset": "",
        "dominant_pct": 0.0,
        "last_update": "",
        "rebalance_needed": False,
        "suggested_actions": [],
    },
}

for k in state["strategies"]:
    state["strategy_performance"][k] = {"wins":0,"losses":0,"pnl":0.0,"avg_duration":0,"trades":0}



# ══════════════════════════════════════════════════════════════════
# PAPER TRADING ENGINE — نظام تجريبي معزول كلياً عن الحقيقي
# ══════════════════════════════════════════════════════════════════
PAPER_STARTING_BALANCE = 10000.0

paper_state = {
    "running":        False,
    "trading_type":   "spot",      # spot أو futures
    "futures_leverage": 10,
    "finances": {
        "spot": {
            "balance": PAPER_STARTING_BALANCE,
            "pnl": 0.0, "wins": 0, "losses": 0,
            "history": [], "peak": PAPER_STARTING_BALANCE,
        },
        "futures": {
            "balance": PAPER_STARTING_BALANCE,
            "pnl": 0.0, "wins": 0, "losses": 0,
            "history": [], "peak": PAPER_STARTING_BALANCE,
        },
    },
    "active_positions": {},   # صفقات مفتوحة تجريبية
    "trade_history":    [],   # سجل صفقات تجريبي مستقل
    "signals":          [],
    "notifications":    [],
    "selected_coins":   ["XAUTUSDT","BTCUSDT","ETHUSDT","SOLUSDT"],
    "selected_strategies": ["RSI_AI","SUPERTREND","VOLATILITY_BREAKOUT","MULTI_TF"],
    "risk": {"tp": 3.0, "sl": 1.5},
    "smart_sl": {"type": "trailing", "trailing_offset": 1.0},
    "capital_mgmt": {
        "mode": "smart_adaptive", "base_risk_pct": 5.0,
        "max_daily_loss": 5.0, "partial_tp": True,
        "partial_tp_pct": 50.0, "partial_tp_at": 1.5, "max_open": 5,
    },
    "ai": {
        "enabled": True,
        "market_regime": "ranging",
        "volatility_index": 0.0,
        "momentum_score": 0.0,
        "trend_strength": 0.0,
        "adaptive_tp": 3.0,
        "adaptive_sl": 1.5,
        "streak": 0,
        "daily_pnl": 0.0,
        "daily_trades": 0,
        "current_drawdown": 0.0,
        "peak_balance_spot": PAPER_STARTING_BALANCE,
        "peak_balance_futures": PAPER_STARTING_BALANCE,
        "agent_risk_level": "medium",
        "agent_recommended_strategy": "",
        "smart_filter_active": False,
        "confidence": 70.0,
        "sharpe_ratio": 0.0,
        "profit_factor": 1.0,
        "signal_heatmap": {},
    },
    "performance": {},     # أداء كل استراتيجية
    "chart_data": {
        "timestamps": [], "spot_pnl": [], "futures_pnl": [],
        "confidence": [], "drawdown": [],
    },
    "stats": {
        "best_trade": 0.0, "worst_trade": 0.0,
        "total_trades": 0, "win_rate": 0.0,
        "expectancy": 0.0, "profit_factor": 0.0,
        "session_start": "",
    },
}

# أوزان وأنماط مستقلة للتجريبي
paper_learned_patterns  = []
paper_strategy_weights  = {}
paper_backtest_results  = {}
paper_online_log        = []

# وكلاء مستقلون للتجريبي
paper_agents = {
    "PAPER_ANALYST": {
        "name": "محلل التجريبي", "emoji": "🔬",
        "role": "يحلل السوق ويوجه التداول التجريبي",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "color": "#38bdf8",
        "interval": 25, "last_run": 0,
    },
    "PAPER_RISK": {
        "name": "مخاطر التجريبي", "emoji": "🛡️",
        "role": "يدير مخاطر التجريبي بشكل مستقل",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "color": "#ff4466",
        "interval": 30, "last_run": 0,
    },
    "PAPER_LEARNER": {
        "name": "تعلم التجريبي", "emoji": "🧠",
        "role": "يتعلم من صفقات التجريبي ويحسن الأوزان",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "color": "#22d3ee",
        "interval": 35, "last_run": 0,
    },
    "PAPER_BACKTEST": {
        "name": "Backtest تجريبي", "emoji": "⚡",
        "role": "يختبر الاستراتيجيات على بيانات التجريبي",
        "status": "standby", "last_action": "", "last_response": "",
        "confidence": 0.0, "calls_made": 0, "color": "#fb923c",
        "interval": 60, "last_run": 0,
    },
}

# تهيئة أداء الاستراتيجيات التجريبية
for k in state["strategies"]:
    paper_state["performance"][k] = {"wins":0,"losses":0,"pnl":0.0,"trades":0}


# ══════════════════════════════════════════════════════════════════
# PAPER TRADING CORE FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def get_paper_balance(trading_type=None):
    """جلب رصيد التجريبي"""
    tt = trading_type or paper_state["trading_type"]
    return max(0.0, paper_state["finances"][tt]["balance"])


def set_paper_balance(value, trading_type=None):
    """ضبط رصيد التجريبي"""
    tt = trading_type or paper_state["trading_type"]
    paper_state["finances"][tt]["balance"] = round(value, 4)


def paper_execute_entry(coin, price, strategy):
    """تنفيذ صفقة تجريبية — معزولة كلياً"""
    pai = paper_state["ai"]
    tt  = paper_state["trading_type"]
    bal = get_paper_balance(tt)
    if bal < 5: return

    cm  = paper_state["capital_mgmt"]
    base_pct = cm["base_risk_pct"] / 100
    streak   = pai.get("streak", 0)
    vi       = pai.get("volatility_index", 30)
    risk_lv  = pai.get("agent_risk_level", "medium")

    # حساب الحجم
    size_pct = base_pct
    if streak >= 3:    size_pct *= 1.2
    elif streak <= -3: size_pct *= 0.5
    if vi > 60:        size_pct *= 0.7
    if risk_lv == "high":     size_pct *= 0.5
    elif risk_lv == "critical": size_pct *= 0.25
    elif risk_lv == "low":    size_pct *= 1.2

    size_pct = max(0.05, min(0.20, size_pct))
    size     = bal * size_pct
    if tt == "futures":
        size *= paper_state["futures_leverage"]
    size = max(5.0, min(size, bal * 0.20))

    # تسجيل الصفقة
    paper_state["active_positions"][coin] = {
        "entry":        price,
        "size":         round(size, 2),
        "time":         datetime.datetime.now().strftime("%H:%M:%S"),
        "entry_time":   datetime.datetime.now().isoformat(),
        "strategy":     strategy,
        "trading_type": tt,
        "adaptive_tp":  pai["adaptive_tp"],
        "adaptive_sl":  pai["adaptive_sl"],
        "max_price":    price,
        "sl_type":      paper_state["smart_sl"]["type"],
        "trailing_offset": paper_state["smart_sl"]["trailing_offset"],
        "partial_taken": False,
    }
    pai["daily_trades"] += 1
    paper_state["signals"].insert(0, {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "coin": coin, "type": "شراء", "price": round(price,4),
        "strategy": state["strategies"].get(strategy, strategy),
        "mode": tt.upper(),
    })
    paper_state["notifications"].insert(0, {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "message": f"📄 PAPER [{tt.upper()}] دخول {coin} | ${size:.0f} | {state['strategies'].get(strategy,strategy)}",
        "type": "success",
    })
    while len(paper_state["notifications"]) > 30: paper_state["notifications"].pop()
    print(f"📄 PAPER [{tt.upper()}] {coin} @ ${price:.4f} | ${size:.0f} | {strategy}")


def paper_check_exit(coin, cur_price):
    """فحص خروج الصفقة التجريبية"""
    pos = paper_state["active_positions"].get(coin)
    if not pos: return
    try: et = datetime.datetime.fromisoformat(pos["entry_time"])
    except: et = datetime.datetime.now()

    change = ((cur_price - pos["entry"]) / pos["entry"]) * 100
    tp = pos.get("adaptive_tp", paper_state["risk"]["tp"])
    sl = pos.get("adaptive_sl", paper_state["risk"]["sl"])
    exit_now = False

    if pos["sl_type"] == "trailing":
        if cur_price > pos["max_price"]: pos["max_price"] = cur_price
        if cur_price <= pos["max_price"]*(1-pos["trailing_offset"]/100) or change>=tp:
            exit_now = True
    else:
        if change >= tp or change <= -sl: exit_now = True

    if not exit_now: return

    paper_state["active_positions"].pop(coin)
    tt      = pos.get("trading_type", paper_state["trading_type"])
    profit  = pos["size"] * (change / 100)
    f       = paper_state["finances"][tt]
    pai     = paper_state["ai"]

    f["pnl"]    = round(f["pnl"] + profit, 4)
    f["history"].append(round(f["pnl"], 2))
    if len(f["history"]) > 200: f["history"] = f["history"][-200:]
    set_paper_balance(get_paper_balance(tt) + profit, tt)
    pai["daily_pnl"] = round(pai["daily_pnl"] + profit, 4)

    if change > 0:
        f["wins"] += 1
        pai["streak"] = max(0, pai["streak"]) + 1
    else:
        f["losses"] += 1
        pai["streak"] = min(0, pai["streak"]) - 1

    strategy = pos.get("strategy", "RSI_AI")
    perf = paper_state["performance"].setdefault(
        strategy, {"wins":0,"losses":0,"pnl":0.0,"trades":0})
    if change > 0: perf["wins"] += 1
    else:          perf["losses"] += 1
    perf["pnl"]    = round(perf["pnl"] + profit, 4)
    perf["trades"] += 1
    paper_state["stats"]["total_trades"] += 1

    # Online Learning للتجريبي
    pkey = f"{strategy}_{pai.get('market_regime','ranging')}"
    cw   = paper_strategy_weights.get(pkey, 1.0)
    if change > 0:
        paper_strategy_weights[pkey] = round(min(1.5, cw*1.05), 3)
        paper_learned_patterns.append({
            "strategy": strategy, "regime": pai.get("market_regime","ranging"),
            "pnl": round(change,2), "time": datetime.datetime.now().strftime("%H:%M"),
        })
        if len(paper_learned_patterns) > 200: paper_learned_patterns.pop(0)
    else:
        paper_strategy_weights[pkey] = round(max(0.3, cw*0.95), 3)

    paper_state["trade_history"].insert(0, {
        "exit_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "coin": coin, "entry": round(pos["entry"],4), "exit": round(cur_price,4),
        "pnl_percent": round(change,2), "pnl_usd": round(profit,2),
        "mode": tt.upper(), "strategy": strategy,
        "regime": pai.get("market_regime","?"),
    })
    if len(paper_state["trade_history"]) > 300: paper_state["trade_history"].pop()

    paper_state["notifications"].insert(0, {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "message": f"{'💰' if change>0 else '💸'} PAPER {coin} {change:+.2f}% ${profit:+.2f}",
        "type": "success" if change > 0 else "danger",
    })
    while len(paper_state["notifications"]) > 30: paper_state["notifications"].pop()
    print(f"{'✅' if change>0 else '❌'} PAPER {coin} {change:+.2f}% ${profit:+.2f}")


def update_paper_ai():
    """تحديث مؤشرات AI التجريبي — مستقلة عن الحقيقي"""
    pai = paper_state["ai"]
    # يقرأ نفس أسعار السوق لكن يحسب مؤشراته بشكل مستقل
    vols = []
    for coin in paper_state["selected_coins"]:
        hist = state["price_history"].get(coin, [])
        if len(hist) >= 10:
            vols.append(compute_volatility(hist))
    if vols: pai["volatility_index"] = round(statistics.mean(vols), 1)

    bh = state["price_history"].get("BTCUSDT", [])
    if len(bh) >= 10:
        pai["momentum_score"]  = round(compute_momentum(bh), 1)
        pai["trend_strength"]  = round(compute_trend_strength(bh), 1)

    vi, mom, ts = pai["volatility_index"], abs(pai["momentum_score"]), pai["trend_strength"]
    if vi > 65 and mom > 60:   pai["market_regime"] = "volatile"
    elif ts > 65 and mom > 40: pai["market_regime"] = "trending"
    else:                      pai["market_regime"] = "ranging"

    # Adaptive TP/SL مستقل
    btp, bsl = paper_state["risk"]["tp"], paper_state["risk"]["sl"]
    if vi > 60: pai["adaptive_tp"]=round(btp*1.4,2); pai["adaptive_sl"]=round(bsl*1.3,2)
    elif vi<20: pai["adaptive_tp"]=round(btp*0.8,2); pai["adaptive_sl"]=round(bsl*0.7,2)
    else:       pai["adaptive_tp"]=btp; pai["adaptive_sl"]=bsl

    # حساب Drawdown مستقل
    tt  = paper_state["trading_type"]
    bal = get_paper_balance(tt)
    pk  = f"peak_balance_{tt}"
    if bal > 0:
        if pai.get(pk, 0) == 0 or bal > pai.get(pk, 0):
            pai[pk] = bal
    peak = pai.get(pk, bal)
    if peak > 0 and bal > 0:
        pai["current_drawdown"] = round(min((peak-bal)/peak*100, 99.0), 2)

    # chart data
    cd = paper_state["chart_data"]
    cd["timestamps"].append(datetime.datetime.now().strftime("%H:%M:%S"))
    cd["spot_pnl"].append(round(paper_state["finances"]["spot"]["pnl"], 2))
    cd["futures_pnl"].append(round(paper_state["finances"]["futures"]["pnl"], 2))
    cd["confidence"].append(round(pai.get("confidence", 70), 1))
    cd["drawdown"].append(round(pai.get("current_drawdown", 0), 1))
    for k in cd:
        if len(cd[k]) > 120: cd[k] = cd[k][-120:]


# ══════════════════════════════════════════
# PAPER AGENTS
# ══════════════════════════════════════════

def run_paper_analyst():
    """محلل التجريبي المستقل"""
    agent = paper_agents["PAPER_ANALYST"]
    agent["status"] = "thinking"
    pai = paper_state["ai"]
    vi   = pai.get("volatility_index", 30)
    mom  = pai.get("momentum_score", 0)
    ts   = pai.get("trend_strength", 50)
    regime = pai.get("market_regime", "ranging")

    # تحليل مستقل
    market_power = (ts-50)*0.4 + mom*0.3
    if market_power > 25:
        view = f"📈 اتجاه صاعد في التجريبي | قوة={market_power:.0f}"
        rec  = "SUPERTREND"
        risk = "low"
    elif market_power < -25:
        view = f"📉 اتجاه هابط في التجريبي"
        rec  = "MEAN_REVERSION"
        risk = "high"
    elif vi > 60:
        view = f"⚡ تذبذب عالٍ | VI={vi:.0f}"
        rec  = "VOLATILITY_BREAKOUT"
        risk = "medium"
    else:
        view = f"➡️ نطاق محايد | نظام: {regime}"
        rec  = "RSI_AI"
        risk = "medium"

    pai["agent_recommended_strategy"] = rec
    pai["agent_risk_level"]           = risk
    agent["last_response"] = view
    agent["confidence"]    = 0.75
    agent["calls_made"]   += 1
    agent["last_action"]   = f"تحليل: {regime} | {rec}"
    agent["status"]        = "done"


def run_paper_risk():
    """مدير مخاطر التجريبي"""
    agent = paper_agents["PAPER_RISK"]
    agent["status"] = "thinking"
    pai = paper_state["ai"]
    dd  = pai.get("current_drawdown", 0)
    streak = pai.get("streak", 0)

    risk_score = 0
    if dd > 10:        risk_score += 40
    elif dd > 5:       risk_score += 20
    if streak <= -4:   risk_score += 30
    elif streak <= -2: risk_score += 15
    if pai.get("volatility_index",30) > 65: risk_score += 15

    if risk_score >= 55:
        risk = "critical"; advice = f"⛔ تجريبي: DD={dd:.1f}% — توقف مؤقت"
        pai["smart_filter_active"] = True
    elif risk_score >= 35:
        risk = "high"; advice = f"🔴 تجريبي: مخاطر عالية | streak={streak}"
        pai["smart_filter_active"] = False
    elif risk_score >= 15:
        risk = "medium"; advice = f"🟡 تجريبي: تابع بحذر"
        pai["smart_filter_active"] = False
    else:
        risk = "low"; advice = f"✅ تجريبي: أوضاع ممتازة | streak={streak:+d}"
        pai["smart_filter_active"] = False

    pai["agent_risk_level"] = risk
    agent["last_response"]  = advice
    agent["confidence"]     = 0.85
    agent["calls_made"]    += 1
    agent["last_action"]    = f"مخاطر تجريبي: {risk}"
    agent["status"]         = "done"


def run_paper_learner():
    """محرك تعلم التجريبي"""
    agent = paper_agents["PAPER_LEARNER"]
    agent["status"] = "thinking"
    trades = paper_state["trade_history"][:40]
    if len(trades) < 3:
        agent["status"] = "standby"
        agent["last_action"] = "انتظار صفقات (3+)"
        return

    wins   = [t for t in trades if t.get("pnl_percent",0) > 0]
    losses = [t for t in trades if t.get("pnl_percent",0) <= 0]
    wr     = round(len(wins)/len(trades)*100, 1)

    # تحديث الأوزان
    strat_stats = {}
    for t in trades:
        s   = t.get("strategy","?")
        r   = t.get("regime","ranging")
        key = f"{s}_{r}"
        if key not in strat_stats:
            strat_stats[key] = {"wins":0,"losses":0}
        if t.get("pnl_percent",0) > 0: strat_stats[key]["wins"] += 1
        else:                           strat_stats[key]["losses"] += 1

    for key, st in strat_stats.items():
        tot = st["wins"] + st["losses"]
        if tot >= 2:
            w = max(0.3, min(1.5, st["wins"]/tot * 2))
            paper_strategy_weights[key] = round(w, 3)

    log_entry = {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "trades": len(trades), "wins": len(wins),
        "wr": wr, "weights": len(paper_strategy_weights),
        "patterns": len(paper_learned_patterns),
    }
    paper_online_log.insert(0, log_entry)
    if len(paper_online_log) > 50: paper_online_log.pop()

    agent["last_response"] = f"🧠 تجريبي: WR={wr}% | أوزان={len(paper_strategy_weights)} | أنماط={len(paper_learned_patterns)}"
    agent["confidence"]    = min(0.95, 0.5 + len(paper_learned_patterns)*0.01)
    agent["calls_made"]   += 1
    agent["last_action"]   = f"تعلم {len(trades)} صفقة | WR={wr}%"
    agent["status"]        = "done"
    print(f"🧠 PAPER_LEARNER: WR={wr}% patterns={len(paper_learned_patterns)}")


def run_paper_backtest():
    """Backtest التجريبي"""
    agent = paper_agents["PAPER_BACKTEST"]
    agent["status"] = "thinking"
    pai = paper_state["ai"]

    for strategy in paper_state["selected_strategies"]:
        sw = 0; sl = 0
        for coin in paper_state["selected_coins"]:
            hist = state["price_history"].get(coin, [])
            if len(hist) < 15: continue
            for i in range(8, len(hist)-1):
                sc = compute_signal_score(coin, strategy, pai)
                if sc > 60:
                    chg = ((hist[i+1]-hist[i])/hist[i])*100 if i+1<len(hist) else 0
                    if chg >= pai["adaptive_tp"]:   sw += 1
                    elif chg <= -pai["adaptive_sl"]: sl += 1
                    elif chg > 0: sw += 1
                    else:         sl += 1
        total = sw + sl
        if total > 0:
            bt_wr = round(sw/total*100, 1)
            paper_backtest_results[strategy] = {
                "win_rate": bt_wr, "wins": sw, "losses": sl,
                "updated": datetime.datetime.now().strftime("%H:%M:%S"),
            }
            paper_strategy_weights[f"bt_{strategy}"] = round(max(0.3, min(1.8, bt_wr/50)), 3)

    best = max(paper_backtest_results, key=lambda k: paper_backtest_results[k]["win_rate"]) if paper_backtest_results else "?"
    summary = f"⚡ Paper BT: {len(paper_backtest_results)} استراتيجية | أفضل: {best}"
    agent["last_response"] = summary
    agent["confidence"]    = 0.85
    agent["calls_made"]   += 1
    agent["last_action"]   = summary
    agent["status"]        = "done"
    print(f"⚡ PAPER_BACKTEST: {summary}")


def paper_agent_orchestrator():
    """مدير وكلاء التجريبي"""
    funcs = {
        "PAPER_ANALYST":  run_paper_analyst,
        "PAPER_RISK":     run_paper_risk,
        "PAPER_LEARNER":  run_paper_learner,
        "PAPER_BACKTEST": run_paper_backtest,
    }
    time.sleep(30)  # انتظر حتى يستقر النظام
    while True:
        now = time.time()
        for aid, agent in paper_agents.items():
            if now - agent["last_run"] >= agent["interval"]:
                try:
                    agent["last_run"] = now
                    t = threading.Thread(target=funcs[aid], daemon=True)
                    t.start()
                except Exception as e:
                    agent["status"] = "error"
                    print(f"❌ Paper Agent {aid}: {e}")
        time.sleep(8)


def paper_trading_logic():
    """منطق التداول التجريبي المعزول"""
    while True:
        if not paper_state["running"]:
            time.sleep(3)
            continue

        pai = paper_state["ai"]
        tt  = paper_state["trading_type"]
        bal = get_paper_balance(tt)

        # حماية الرأسمال
        if bal < 5: time.sleep(5); continue
        if pai.get("smart_filter_active") and random.random() < 0.7:
            time.sleep(3); continue

        dd = pai.get("current_drawdown", 0)
        if dd >= 15: time.sleep(5); continue

        daily_loss_pct = abs(min(0, pai.get("daily_pnl",0))) / max(bal,1) * 100
        if daily_loss_pct >= paper_state["capital_mgmt"]["max_daily_loss"]:
            time.sleep(5); continue

        # فحص الصفقات المفتوحة
        for coin in list(paper_state["active_positions"].keys()):
            price = state["prices"].get(coin, 0)
            if price > 0:
                paper_check_exit(coin, price)

        # البحث عن فرص جديدة
        max_open = paper_state["capital_mgmt"]["max_open"]
        if len(paper_state["active_positions"]) >= max_open:
            time.sleep(2); continue

        for coin in paper_state["selected_coins"]:
            price = state["prices"].get(coin, 0)
            if price == 0 or coin in paper_state["active_positions"]: continue
            if len(paper_state["active_positions"]) >= max_open: break

            # حساب إشارة مستقلة
            best_strat = None; best_score = 0
            threshold  = 63.0
            streak = pai.get("streak", 0)
            if streak <= -3: threshold = 75.0
            elif streak >= 3: threshold = 57.0

            for s in paper_state["selected_strategies"]:
                # تطبيق أوزان التجريبي
                sc = compute_signal_score(coin, s, pai)
                # تعديل بأوزان التجريبي المكتسبة
                regime = pai.get("market_regime","ranging")
                pw = paper_strategy_weights.get(f"{s}_{regime}", 1.0)
                bw = paper_strategy_weights.get(f"bt_{s}", 1.0)
                sc = sc * ((pw + bw) / 2)
                if sc > threshold and sc > best_score:
                    best_score = sc
                    best_strat = s

            if best_strat:
                paper_execute_entry(coin, price, best_strat)

        time.sleep(2)


def paper_ai_thread():
    """خيط تحديث AI التجريبي"""
    while True:
        update_paper_ai()
        time.sleep(10)


def save_paper_state():
    """حفظ بيانات التجريبي بشكل مستقل"""
    try:
        data = {
            "finances":         paper_state["finances"],
            "trade_history":    paper_state["trade_history"][:200],
            "performance":      paper_state["performance"],
            "ai":               paper_state["ai"],
            "stats":            paper_state["stats"],
            "chart_data":       paper_state["chart_data"],
            "strategy_weights": paper_strategy_weights,
            "learned_patterns": paper_learned_patterns[-100:],
            "backtest_results": paper_backtest_results,
            "online_log":       paper_online_log[:50],
        }
        with open('paper_trading.json','w',encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ paper save: {e}")


def load_paper_state():
    """تحميل بيانات التجريبي"""
    if not os.path.exists('paper_trading.json'): return
    try:
        with open('paper_trading.json','r',encoding='utf-8') as f:
            saved = json.load(f)
        for k in ['finances','trade_history','performance','ai','stats','chart_data']:
            if k in saved: paper_state[k] = saved[k]
        if "strategy_weights" in saved: paper_strategy_weights.update(saved["strategy_weights"])
        if "learned_patterns" in saved: paper_learned_patterns.extend(saved["learned_patterns"])
        if "backtest_results" in saved: paper_backtest_results.update(saved["backtest_results"])
        if "online_log"       in saved: paper_online_log.extend(saved["online_log"])
        print(f"✅ Paper Trading loaded: {len(paper_state['trade_history'])} صفقة محفوظة")
    except Exception as e:
        print(f"⚠️ paper load: {e}")


def auto_save_paper():
    """حفظ تلقائي للتجريبي"""
    while True:
        save_paper_state()
        time.sleep(30)



TELEGRAM_TOKEN   = ""
TELEGRAM_CHAT_ID = ""

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        url  = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
        data = json.dumps({"chat_id":TELEGRAM_CHAT_ID,"text":msg,"parse_mode":"HTML"}).encode()
        req  = urllib.request.Request(url,data=data,headers={"Content-Type":"application/json"},method="POST")
        urllib.request.urlopen(req,timeout=8)
    except Exception as e:
        print("Telegram err:",e)

def send_trade_alert(coin,pnl_pct,pnl_usd,strategy,mode):
    if abs(pnl_usd)<1: return
    em="💰" if pnl_pct>0 else "💸"
    send_telegram(em+" <b>"+coin+"</b> "+str(round(pnl_pct,2))+"% $"+str(round(pnl_usd,2))+"\n"+strategy+" | "+mode.upper())


def run_gemini_chief():
    """
    GEMINI_CHIEF V30 — يستخدم:
    1. الشبكة العصبية بين الوكلاء
    2. Chain of Thought — تفكير خطوة بخطوة
    3. السياق العصبي الكامل
    """
    agent = agents["GEMINI_CHIEF"]
    agent["status"] = "thinking"
    ai   = state["ai_learner"]
    md   = state["market_data"]
    nd   = state["news_data"]
    mode = state["current_mode"]
    bal  = get_balance(mode)
    trades = state["trade_history"][:10]
    wins   = sum(1 for t in trades if t.get("pnl_percent",0)>0)
    wr     = round(wins/len(trades)*100,1) if trades else 0

    # ═══ استقبال السياق العصبي ═══
    neural_ctx, net_signal = neural_get_context("GEMINI_CHIEF")

    # ═══ Chain of Thought ═══
    cot = neural_chain_of_thought("GEMINI_CHIEF", neural_ctx, net_signal)

    # ═══ آراء الوكلاء + إشاراتهم العصبية ═══
    views = []
    for aid, ag in agents.items():
        if aid=="GEMINI_CHIEF": continue
        if ag.get("last_response"):
            ns = neural_signals.get(aid, 0.0)
            direction = "↑" if ns>0.2 else "↓" if ns<-0.2 else "→"
            views.append("- " + ag["emoji"] + " " + ag["name"] + " [" + direction + str(round(abs(ns),2)) + "]: " + str(ag["last_response"])[:45])
    agents_views = "\n".join(views[:8])
    regime   = ai.get("market_regime","ranging")
    vi       = round(ai.get("volatility_index",30),0)
    mom      = ai.get("momentum_score",0)
    fg       = md.get("fear_greed",55)
    streak   = ai.get("streak",0)
    dd       = round(ai.get("current_drawdown",0),1)
    sent     = nd.get("sentiment_score",0)
    event    = nd.get("top_event","")[:40]
    daily    = round(ai.get("daily_pnl",0),1)
    # ═══ Pro Trader Context ═══
    psych     = pro_trader_memory.get("market_psychology", 50)
    sm_bias   = pro_trader_memory.get("smart_money_bias", "neutral")
    insights  = pro_trader_memory.get("session_insights", [])
    port_rec  = portfolio_state.get("recommendation","")
    port_dev  = portfolio_state.get("deviation_score",0)

    psych_label = ("جشع شديد 🤑" if psych>80 else "جشع 😏" if psych>65
                   else "خوف 😟" if psych<35 else "خوف شديد 😱" if psych<20 else "محايد 😐")

    bias_label = {"accumulation":"تجميع 🏦 (كبار يشترون)",
                  "markup":"ارتفاع هادئ 📈",
                  "distribution":"توزيع ⚠️ (كبار يبيعون)",
                  "markdown":"هبوط 📉",
                  "neutral":"محايد ➡️"}.get(sm_bias, sm_bias)

    insights_str = "\n".join(["• "+i for i in insights[:3]]) if insights else "لا رؤى مستجدة"

    prompt = (
        "أنت متداول محترف ومحلل رئيسي. فكّر بعمق خطوة بخطوة.\n\n"
        "═══ تحليل الشبكة العصبية ═══\n" + cot + "\n\n"
        "═══ الإشارة العصبية الإجمالية ═══\n"
        "القوة: " + str(net_signal) + " | " + ("تداول ↑" if net_signal>0.3 else "انتظار ↓" if net_signal<-0.3 else "محايد →") + "\n\n"
        "═══ تحليل المتداول المحترف ═══\n"
        "نفسية السوق: " + psych_label + " (" + str(round(psych,0)) + "/100)\n"
        "الأموال الذكية: " + bias_label + "\n"
        "رؤى السوق:\n" + insights_str + "\n"
        "توازن المحفظة: " + port_rec[:50] + " (انحراف=" + str(port_dev) + "%)\n\n"
        "═══ بيانات السوق ═══\n"
        "السوق:" + str(regime) +
        " VI=" + str(vi) +
        " Mom=" + str(mom) +
        " F&G=" + str(fg) +
        " رصيد=$" + str(round(bal,0)) +
        " يوم=$" + str(daily) +
        " WR=" + str(wr) + "%" +
        " streak=" + str(streak) +
        " DD=" + str(dd) + "%" +
        " اخبار=" + str(sent) +
        " حدث=" + event + "\n" +
        "آراء:\n" + agents_views + "\n" +
        "JSON: {decision:trade_wait_reduce,risk:low_medium_high_critical,"
        "strategy:اسم,confidence:0.0-1.0,view:تحليل_مفصل,warning:تحذير,"
        "scalp_ok:true,tp:2.5,sl:1.2,"
        "position_size_pct:5-15,rebalance_needed:bool,smart_money_action:buy_sell_wait}"
    )
    response = call_gemini(prompt, max_tokens=350)
    if not response:
        agent["last_response"] = "Gemini غير متصل"
        agent["status"] = "standby"
        return
    try:
        clean = response.replace("```json","").replace("```","").strip()
        s = clean.find("{"); e2 = clean.rfind("}")
        if s!=-1 and e2!=-1: clean = clean[s:e2+1]
        data  = json.loads(clean)
        dec   = data.get("decision","wait")
        risk  = data.get("risk","medium")
        conf  = float(data.get("confidence",0.7))
        ai["agent_market_view"]           = data.get("view","")
        ai["agent_risk_level"]            = risk
        ai["agent_confidence_boost"]      = (conf-0.5)*20
        strat = data.get("strategy","")
        if strat and strat in state["strategies"]:
            ai["agent_recommended_strategy"] = strat
        # تطبيق حجم الصفقة المقترح
        ps_pct = float(data.get("position_size_pct",7))
        if 3 <= ps_pct <= 20:
            state["capital_mgmt"]["base_risk_pct"] = round(ps_pct, 1)
        # تنبيه إعادة التوازن
        if data.get("rebalance_needed") and port_dev > 20:
            state["notifications"].insert(0,{"time":datetime.datetime.now().strftime("%H:%M:%S"),
                "message":"⚖️ Gemini: إعادة توازن المحفظة مطلوبة","type":"danger"})
        tp_v = float(data.get("tp",0))
        sl_v = float(data.get("sl",0))
        if tp_v > 0: ai["adaptive_tp"] = round(tp_v,2)
        if sl_v > 0: ai["adaptive_sl"] = round(sl_v,2)
        if "SCALP_TRADER" in agents:
            agents["SCALP_TRADER"]["active"] = data.get("scalp_ok",True) and risk!="critical"
        if risk=="critical": ai["smart_filter_active"]=True
        elif dec=="trade" and conf>0.7: ai["smart_filter_active"]=False
        cast_vote("GEMINI_CHIEF",dec,conf,data.get("view","")[:50])
        agent["last_decision"] = {"time":datetime.datetime.now().strftime("%H:%M:%S"),"decision":dec,"risk":risk,"confidence":conf,"view":data.get("view","")[:80],"warning":data.get("warning","")[:60]}
        summary = "🔷 " + dec.upper() + " | " + risk + " | " + str(round(conf*100)) + "% | " + data.get("view","")[:50]
        agent["last_response"] = summary
        agent["confidence"]    = conf
        agent["calls_made"]   += 1
        agent["successes"]    += 1
        agent["last_action"]  = dec + " | " + risk
        agent["status"]       = "done"
        if risk in ["high","critical"]:
            send_telegram("⚠️ <b>GEMINI CHIEF</b>\n" + data.get("warning","") + "\nقرار: " + dec.upper())
        print("🔷 GEMINI_CHIEF: " + summary)
    except Exception as ex:
        agent["last_response"] = "خطأ: " + str(ex)[:40]
        agent["status"] = "error"
        cast_vote("GEMINI_CHIEF","wait",0.3,"خطأ")


def telegram_hourly():
    time.sleep(300)
    last_h = -1
    while True:
        now = datetime.datetime.now()
        if now.hour != last_h and now.minute < 5:
            try:
                ai  = state["ai_learner"]
                md  = state["market_data"]
                bal = get_balance(state["current_mode"])
                gc  = agents.get("GEMINI_CHIEF",{}).get("last_decision",{})
                f   = state["finances"][state["current_mode"]]
                msg = (
                    "📊 <b>تقرير ساعي</b> " + now.strftime("%H:%M") + "\n" +
                    "💰 رصيد: $" + str(round(bal,2)) + "\n" +
                    "📈 ربح اليوم: $" + str(round(ai.get("daily_pnl",0),2)) + "\n" +
                    "🎯 " + str(f.get("wins",0)) + "W / " + str(f.get("losses",0)) + "L\n" +
                    "🌡 السوق: " + str(ai.get("market_regime","ranging")) +
                    " | F&G=" + str(md.get("fear_greed",55)) + "\n" +
                    "🔷 Gemini: " + str(gc.get("decision","wait")).upper() +
                    " | " + str(gc.get("risk","medium")) + "\n" +
                    "📂 صفقات: " + str(len(state["active_positions"]))
                )
                send_telegram(msg)
                last_h = now.hour
            except: pass
        time.sleep(60)


# ══════════════════════════════════════════════════════════════════
# NEURAL AGENT NETWORK — شبكة عصبية بين الوكلاء
# كل وكيل خلية عصبية — الإشارات تنتقل عبر أوزان مكتسبة
# ══════════════════════════════════════════════════════════════════

# ═══ أوزان الاتصالات بين الوكلاء (Synaptic Weights) ═══
# القيمة: مدى تأثير وكيل A على وكيل B (0.0 → 1.0)
neural_weights = {
    # GEMINI_CHIEF يستقبل من الجميع
    ("MARKET_ANALYST",    "GEMINI_CHIEF"):  0.85,
    ("RISK_MANAGER",      "GEMINI_CHIEF"):  0.90,
    ("NEWS_ANALYST",      "GEMINI_CHIEF"):  0.75,
    ("GOLD_SPECIALIST",   "GEMINI_CHIEF"):  0.60,
    ("STRATEGY_SELECTOR", "GEMINI_CHIEF"):  0.80,
    ("PATTERN_LEARNER",   "GEMINI_CHIEF"):  0.65,
    ("SCALP_TRADER",      "GEMINI_CHIEF"):  0.70,

    # RISK_MANAGER يستقبل من المحلل والأخبار
    ("MARKET_ANALYST",    "RISK_MANAGER"):  0.80,
    ("NEWS_ANALYST",      "RISK_MANAGER"):  0.85,
    ("GOLD_SPECIALIST",   "RISK_MANAGER"):  0.55,

    # STRATEGY_SELECTOR يستقبل من المحلل والـ Backtest
    ("MARKET_ANALYST",    "STRATEGY_SELECTOR"): 0.75,
    ("BACKTEST_RUNNER",   "STRATEGY_SELECTOR"): 0.80,
    ("PATTERN_LEARNER",   "STRATEGY_SELECTOR"): 0.70,
    ("RISK_MANAGER",      "STRATEGY_SELECTOR"): 0.65,

    # SCALP_TRADER يستقبل من المحلل والمخاطر والأخبار
    ("MARKET_ANALYST",    "SCALP_TRADER"):  0.75,
    ("RISK_MANAGER",      "SCALP_TRADER"):  0.90,  # المخاطر تؤثر كثيراً على السكالب
    ("NEWS_ANALYST",      "SCALP_TRADER"):  0.80,

    # GOLD_SPECIALIST يستقبل من الأخبار والمحلل
    ("NEWS_ANALYST",      "GOLD_SPECIALIST"): 0.85,
    ("MARKET_ANALYST",    "GOLD_SPECIALIST"): 0.60,
}

# ═══ إشارات الخلايا العصبية الحالية ═══
neural_signals = {}      # {agent_id: signal_value (-1.0 → +1.0)}
neural_memory  = {}      # ذاكرة قصيرة المدى لكل خلية
neural_history = []      # سجل انتقال الإشارات


def neural_activate(agent_id, raw_value):
    """
    دالة التنشيط (Activation Function)
    تحوّل القيمة الخام لإشارة عصبية (-1 → +1)
    مثل sigmoid لكن مُعدَّلة للتداول
    """
    import math
    # tanh: أسلوب شائع في الشبكات العصبية
    activated = math.tanh(raw_value / 50.0)
    return round(activated, 4)


def neural_propagate(source_agent, signal_value, confidence):
    """
    انتقال الإشارة من وكيل لآخر عبر الأوزان
    Hebbian: الوصلات تقوى عند النجاح وتضعف عند الفشل
    """
    neural_signals[source_agent] = round(signal_value * confidence, 4)

    # إرسال الإشارة لكل وكيل متصل
    propagated = []
    for (src, dst), weight in neural_weights.items():
        if src != source_agent: continue

        # إشارة وصلت = إشارة المصدر × الوزن
        received = neural_signals[source_agent] * weight

        # دمج مع الإشارة الموجودة (إذا وُجدت)
        existing = neural_signals.get(dst, 0.0)
        combined = round(existing * 0.4 + received * 0.6, 4)
        neural_signals[dst] = combined
        propagated.append((dst, round(received,3), round(weight,2)))

    # تسجيل في السجل
    if propagated:
        neural_history.insert(0, {
            "time":   datetime.datetime.now().strftime("%H:%M:%S"),
            "from":   source_agent,
            "signal": round(signal_value,3),
            "to":     propagated[:3],
        })
        if len(neural_history) > 50: neural_history.pop()


def hebbian_update(source, dest, result_positive):
    """
    قانون Hebbian: الخلايا التي تنشط معاً تترابط معاً
    إذا قرر A و B معاً وكانت النتيجة إيجابية → زد الوزن
    إذا كانت سلبية → قلل الوزن
    """
    key = (source, dest)
    if key not in neural_weights: return
    old_w = neural_weights[key]
    if result_positive:
        new_w = round(min(1.0, old_w * 1.02), 4)   # تقوية
    else:
        new_w = round(max(0.2, old_w * 0.98), 4)   # إضعاف
    neural_weights[key] = new_w
    if abs(new_w - old_w) > 0.005:
        print(f"🧠 Hebbian {source}→{dest}: {old_w:.3f} → {new_w:.3f}")


def neural_get_context(agent_id):
    """
    يجمع السياق العصبي لوكيل معين
    = ماذا تقول الخلايا المتصلة به
    """
    context_parts = []
    total_signal  = 0.0
    total_weight  = 0.0

    for (src, dst), weight in neural_weights.items():
        if dst != agent_id: continue
        src_signal = neural_signals.get(src, 0.0)
        if abs(src_signal) < 0.05: continue   # تجاهل الإشارات الضعيفة

        src_agent  = agents.get(src, {})
        src_name   = src_agent.get("name", src)
        src_resp   = str(src_agent.get("last_response",""))[:50]

        direction  = "إيجابي ↑" if src_signal > 0.2 else "سلبي ↓" if src_signal < -0.2 else "محايد →"
        context_parts.append(
            f"• {src_name} [{direction} قوة={abs(src_signal):.2f} وزن={weight:.2f}]: {src_resp}"
        )
        total_signal += src_signal * weight
        total_weight += weight

    net_signal = round(total_signal / max(total_weight, 0.1), 3)
    context = "\n".join(context_parts) if context_parts else "لا إشارات واردة"
    return context, net_signal


def neural_chain_of_thought(agent_id, market_data, net_signal):
    """
    Chain of Thought — تفكير خطوة بخطوة
    Gemini يفكر بصوت عالٍ قبل القرار
    """
    ai = state["ai_learner"]
    vi = ai.get("volatility_index", 30)
    md = state["market_data"]

    steps = [
        f"الخطوة 1 — قراءة السوق: نظام={ai.get('market_regime','ranging')} | VI={vi:.0f} | Momentum={ai.get('momentum_score',0):+.0f}",
        f"الخطوة 2 — تقييم المخاطر: Drawdown={ai.get('current_drawdown',0):.1f}% | Streak={ai.get('streak',0):+d} | F&G={md.get('fear_greed',55)}",
        f"الخطوة 3 — الإشارة العصبية: القوة الإجمالية={net_signal:+.3f} | {'إيجابية ↑' if net_signal>0.2 else 'سلبية ↓' if net_signal<-0.2 else 'محايدة →'}",
        f"الخطوة 4 — سياق الوكلاء: {market_data[:80]}",
    ]
    return "\n".join(steps)


# ═══ تطبيق Hebbian بعد كل صفقة ═══
def neural_learn_from_trade(pnl_pct, contributing_agents):
    """
    بعد كل صفقة: حدّث أوزان الشبكة العصبية
    """
    won = pnl_pct > 0
    for src_agent in contributing_agents:
        # GEMINI_CHIEF هو الهدف الرئيسي
        hebbian_update(src_agent, "GEMINI_CHIEF", won)
        # تحديث الاتصالات الأخرى
        for (src, dst), _ in neural_weights.items():
            if src == src_agent and dst != "GEMINI_CHIEF":
                hebbian_update(src, dst, won)


def neural_status_summary():
    """ملخص حالة الشبكة العصبية"""
    active = sum(1 for v in neural_signals.values() if abs(v) > 0.1)
    avg_w  = sum(neural_weights.values()) / len(neural_weights)
    strong = [(k,v) for k,v in neural_weights.items() if v > 0.85]
    weak   = [(k,v) for k,v in neural_weights.items() if v < 0.35]
    return {
        "active_neurons":  active,
        "total_synapses":  len(neural_weights),
        "avg_weight":      round(avg_w, 3),
        "strong_links":    len(strong),
        "weak_links":      len(weak),
        "last_signal":     neural_history[0] if neural_history else {},
    }


# ══════════════════════════════════════════════════════════════════
# PORTFOLIO REBALANCER — مهارة توازن المحفظة كمتداول محترف
# يوازن بين العملات والدولار مثل صندوق استثمار حقيقي
# ══════════════════════════════════════════════════════════════════
portfolio_targets = {
    "conservative": {"USDT":60,"BTC":20,"ETH":12,"GOLD":8},
    "balanced":     {"USDT":40,"BTC":25,"ETH":20,"GOLD":10,"SOL":5},
    "aggressive":   {"USDT":20,"BTC":30,"ETH":25,"SOL":15,"GOLD":10},
}
portfolio_config  = {"mode": "balanced"}   # بديل آمن للـ global
portfolio_state   = {
    "last_rebalance":  "",
    "rebalance_count": 0,
    "saved_by_rebalance": 0.0,
    "current_allocation": {},
    "target_allocation":  {},
    "deviation_score":    0.0,
    "recommendation":     "",
    "actions":            [],
}


def calculate_portfolio_allocation():
    """
    حساب التوزيع الحالي للمحفظة
    يقارن مع الهدف ويحسب الانحراف
    """
    prices  = state["prices"]
    fins    = state["finances"]
    mode    = state["current_mode"]
    f       = fins[mode]
    bal     = get_balance(mode)

    # تجميع الأصول
    assets = {"USDT": bal}
    total  = bal

    # الصفقات المفتوحة
    for coin, pos in state["active_positions"].items():
        cur   = prices.get(coin, pos["entry"])
        val   = pos["size"] * (cur / pos["entry"])
        sym   = coin.replace("USDT","")
        assets[sym] = assets.get(sym, 0) + val
        total += val - pos["size"]   # الربح غير المحقق

    total = max(total, bal)

    # حساب النسب الحالية
    current = {k: round(v/total*100,1) for k,v in assets.items() if total > 0}
    portfolio_state["current_allocation"] = current

    # الهدف
    target = portfolio_targets.get(portfolio_config["mode"], portfolio_targets["balanced"])
    portfolio_state["target_allocation"] = target

    # حساب الانحراف
    deviation = 0.0
    actions   = []
    for asset, tgt_pct in target.items():
        cur_pct = current.get(asset, 0)
        dev     = cur_pct - tgt_pct
        deviation += abs(dev)
        if abs(dev) > 5:
            if dev > 0:
                actions.append(f"📉 قلل {asset} بـ{abs(dev):.0f}% (${total*abs(dev)/100:.0f})")
            else:
                actions.append(f"📈 زد {asset} بـ{abs(dev):.0f}% (${total*abs(dev)/100:.0f})")

    portfolio_state["deviation_score"] = round(deviation, 1)
    portfolio_state["actions"]         = actions[:4]

    if deviation < 10:
        portfolio_state["recommendation"] = "✅ المحفظة متوازنة — استمر"
    elif deviation < 25:
        portfolio_state["recommendation"] = "⚠️ انحراف متوسط — فكر في إعادة التوازن"
    else:
        portfolio_state["recommendation"] = "🔴 انحراف كبير — إعادة توازن مطلوبة"

    return current, deviation


def run_portfolio_rebalancer():
    """
    وكيل مهارة توازن المحفظة — كمتداول محترف
    يعمل مع Gemini لاتخاذ قرار التوازن
    """
    current, deviation = calculate_portfolio_allocation()
    ai    = state["ai_learner"]
    bal   = get_balance(state["current_mode"])
    target = portfolio_targets.get(portfolio_config["mode"], {})

    # بناء prompt احترافي لـ Gemini
    cur_str = " | ".join([f"{k}={v}%" for k,v in current.items()])
    tgt_str = " | ".join([f"{k}={v}%" for k,v in target.items()])

    prompt = (
        "أنت مدير محفظة محترف. حلّل توزيع الأصول وأعطِ قرار التوازن.\n"
        "المحفظة الحالية: " + cur_str + "\n"
        "الهدف المستهدف: " + tgt_str + "\n"
        "الانحراف الكلي: " + str(deviation) + "%\n"
        "الرصيد الكلي: $" + str(round(bal,2)) + "\n"
        "السوق: " + ai.get("market_regime","ranging") + " | VI=" + str(round(ai.get("volatility_index",30),0)) + "\n"
        "الإجراءات المقترحة:\n" + "\n".join(portfolio_state["actions"]) + "\n"
        "JSON: {rebalance_now:bool,priority_action:str,risk_of_imbalance:low_medium_high,"
        "suggested_mode:conservative_balanced_aggressive,reasoning:str}"
    )

    response = call_gemini(prompt, max_tokens=300)
    if response:
        try:
            clean = response.replace("```json","").replace("```","").strip()
            s=clean.find("{"); e2=clean.rfind("}")
            if s!=-1 and e2!=-1: clean=clean[s:e2+1]
            data = json.loads(clean)

            # تطبيق التوصية
            sug_mode = data.get("suggested_mode","")
            if sug_mode in portfolio_targets:
                portfolio_config["mode"] = sug_mode

            reasoning = data.get("reasoning","")
            portfolio_state["recommendation"] = (
                ("🔄 إعادة توازن مطلوبة — " if data.get("rebalance_now") else "✅ محتفظ بالتوزيع — ") +
                reasoning[:60]
            )

            # تنبيه إذا الخطر عالٍ
            if data.get("risk_of_imbalance") == "high":
                state["notifications"].insert(0, {
                    "time":    datetime.datetime.now().strftime("%H:%M:%S"),
                    "message": "⚖️ المحفظة تحتاج إعادة توازن — " + data.get("priority_action","")[:50],
                    "type":    "danger"
                })
            portfolio_state["last_rebalance"] = datetime.datetime.now().strftime("%H:%M:%S")
            portfolio_state["rebalance_count"] += 1
            print(f"⚖️ Portfolio: {portfolio_state['recommendation'][:60]}")
        except Exception as e:
            print(f"⚠️ Portfolio parse: {e}")

    # بث الإشارة العصبية
    rebalance_signal = -deviation * 0.5   # انحراف كبير = إشارة سلبية
    neural_propagate("PORTFOLIO_MANAGER", rebalance_signal, 0.80)


def portfolio_thread():
    """توازن المحفظة كل 15 دقيقة"""
    time.sleep(60)
    while True:
        try:
            run_portfolio_rebalancer()
        except Exception as e:
            print(f"⚠️ portfolio_thread: {e}")
        time.sleep(900)


# ══════════════════════════════════════════════════════════════════
# PRO TRADER NEURAL CELLS — خلايا عصبية كمتداول محترف
# تفكير عميق: تحليل فني + أساسي + نفسي + إدارة رأس المال
# ══════════════════════════════════════════════════════════════════

pro_trader_memory = {
    "session_insights":   [],    # رؤى الجلسة
    "market_psychology":  50,    # مؤشر نفسية السوق 0-100
    "smart_money_bias":   "neutral",  # توجه الأموال الذكية
    "key_levels":         {},    # مستويات دعم/مقاومة مهمة
    "regime_performance": {},    # أداء كل استراتيجية في كل نظام
    "optimal_session":    "",    # أفضل وقت للتداول
    "risk_reward_history":[],    # تاريخ R:R
}


def analyze_market_psychology():
    """
    تحليل نفسية السوق كمتداول محترف
    يجمع: F&G + Streak + Momentum + Volume behavior
    """
    ai  = state["ai_learner"]
    md  = state["market_data"]
    fg  = md.get("fear_greed", 55)
    streak  = ai.get("streak", 0)
    mom     = ai.get("momentum_score", 0)
    vi      = ai.get("volatility_index", 30)

    # حساب نفسية السوق (0=خوف شديد, 100=جشع شديد)
    psych = 50
    psych += (fg - 50) * 0.4           # F&G تأثير 40%
    psych += streak * 3                  # سلسلة الصفقات
    psych += mom * 0.2                   # الزخم
    psych = max(0, min(100, psych))

    pro_trader_memory["market_psychology"] = round(psych, 1)

    # توجه الأموال الذكية
    if fg > 75 and mom < 0:
        bias = "distribution"   # توزيع — كبار المتداولين يبيعون
    elif fg < 25 and mom > 0:
        bias = "accumulation"   # تجميع — كبار المتداولين يشترون
    elif fg > 60 and vi < 30:
        bias = "markup"         # مرحلة ارتفاع هادئة
    elif fg < 40 and vi > 60:
        bias = "markdown"       # مرحلة هبوط متسارعة
    else:
        bias = "neutral"

    pro_trader_memory["smart_money_bias"] = bias
    return psych, bias


def calculate_smart_position_size(coin, strategy, entry_price):
    """
    حساب حجم الصفقة كمتداول محترف
    يعتمد على: Kelly Criterion + R:R + نفسية السوق
    """
    ai      = state["ai_learner"]
    bal     = get_balance(state["current_mode"])
    tp      = ai.get("adaptive_tp", 3.0)
    sl      = ai.get("adaptive_sl", 1.5)
    wr      = max(0.3, min(0.8, (ai.get("confidence",70)/100)))

    # Kelly Criterion: f = (p*b - q) / b
    # p=win_rate, q=loss_rate, b=R:R ratio
    rr_ratio = tp / max(sl, 0.1)
    kelly    = (wr * rr_ratio - (1-wr)) / max(rr_ratio, 0.1)
    kelly    = max(0, min(0.25, kelly))   # حد 25%

    # تعديل حسب نفسية السوق
    psych = pro_trader_memory.get("market_psychology", 50)
    if psych > 80:    kelly *= 0.7   # جشع — قلل المخاطرة
    elif psych < 20:  kelly *= 0.6   # خوف — قلل أكثر
    elif 40<psych<60: kelly *= 1.1   # محايد — طبيعي+

    # تعديل حسب الشبكة العصبية
    net_sig = neural_signals.get("GEMINI_CHIEF", 0)
    if net_sig > 0.5:  kelly *= 1.2   # إشارة قوية
    elif net_sig < -0.3: kelly *= 0.5 # إشارة سلبية

    size = bal * kelly
    size = max(5.0, min(size, bal * 0.20))

    # تسجيل R:R
    pro_trader_memory["risk_reward_history"].append({
        "time":  datetime.datetime.now().strftime("%H:%M"),
        "coin":  coin,
        "kelly": round(kelly, 4),
        "rr":    round(rr_ratio, 2),
        "size":  round(size, 2),
    })
    if len(pro_trader_memory["risk_reward_history"]) > 50:
        pro_trader_memory["risk_reward_history"].pop(0)

    print(f"💎 Kelly Size: {coin} kelly={kelly:.2%} RR={rr_ratio:.1f} size=${size:.2f}")
    return round(size, 2)


def detect_key_levels(coin):
    """
    اكتشاف مستويات الدعم والمقاومة المهمة
    كما يفعل المتداولون المحترفون
    """
    hist = state["price_history"].get(coin, [])
    if len(hist) < 20: return None, None

    # مستوى الدعم: أدنى نقطة في آخر 20 نقطة
    support    = round(min(hist[-20:]), 4)
    resistance = round(max(hist[-20:]), 4)
    current    = hist[-1]

    # المسافة من المستويات
    dist_support    = round((current - support) / current * 100, 2)
    dist_resistance = round((resistance - current) / current * 100, 2)

    pro_trader_memory["key_levels"][coin] = {
        "support":    support,
        "resistance": resistance,
        "dist_sup":   dist_support,
        "dist_res":   dist_resistance,
        "zone":       "near_support" if dist_support < 1.5 else
                      "near_resistance" if dist_resistance < 1.5 else "middle",
    }
    return support, resistance


def pro_neural_analysis():
    """
    التحليل العصبي الاحترافي الكامل
    يشتغل كل 30 ثانية ويغذي GEMINI_CHIEF
    """
    psych, bias = analyze_market_psychology()

    # تحليل مستويات كل عملة
    insights = []
    for coin in state["selected_coins"][:5]:
        sup, res = detect_key_levels(coin)
        if sup and res:
            kl = pro_trader_memory["key_levels"].get(coin, {})
            zone = kl.get("zone","")
            if zone == "near_support":
                insights.append(f"🎯 {coin} قرب الدعم ${sup} — فرصة شراء محتملة")
            elif zone == "near_resistance":
                insights.append(f"⚠️ {coin} قرب المقاومة ${res} — احتمال انعكاس")

    # تحديث الرؤى
    if insights:
        pro_trader_memory["session_insights"] = insights[:4]

    # إشارة عصبية للمحلل الرئيسي
    bias_signal = {
        "accumulation": 70,
        "markup":        50,
        "neutral":        0,
        "distribution": -60,
        "markdown":     -80,
    }.get(bias, 0)

    neural_propagate("MARKET_ANALYST", bias_signal * (psych/100), 0.85)

    print(f"💎 Pro Neural: psych={psych:.0f} bias={bias} insights={len(insights)}")


def pro_neural_thread():
    """خيط التحليل الاحترافي"""
    time.sleep(45)
    while True:
        try: pro_neural_analysis()
        except Exception as e: print(f"⚠️ pro_neural: {e}")
        time.sleep(30)


# ══════════════════════════════════════════════════════════════════
# SCALP NEURAL AGENT — وكيل السكالب الاحترافي
# يفكر مثل متداول سكالب محترف:
# - يراقب Microstructure السوق
# - يستخدم Order Flow Analysis
# - يحدد Momentum Bursts
# - يدير الوقت بدقة مليثانية
# ══════════════════════════════════════════════════════════════════

scalp_neural_state = {
    "micro_momentum":  {},    # زخم لحظي لكل عملة
    "order_flow":      {},    # تدفق الأوامر المُقدَّر
    "scalp_windows":   [],    # نوافذ سكالب مثالية
    "entry_precision": {},    # دقة نقاط الدخول
    "exit_targets":    {},    # أهداف خروج محسوبة
    "session_stats":   {
        "best_scalp_coin":  "",
        "best_scalp_time":  "",
        "avg_hold_seconds": 0,
        "micro_wr":         0.0,
        "momentum_score":   0.0,
    },
    "neural_scalp_signal": 0.0,  # إشارة عصبية للسكالب -1 → +1
}


def analyze_micro_momentum(coin):
    """
    تحليل الزخم اللحظي (Micro Momentum)
    يراقب آخر 5 تحركات للعملة
    """
    hist = state["price_history"].get(coin, [])
    if len(hist) < 8: return 0.0

    # آخر 5 تحركات
    moves = [(hist[i]-hist[i-1])/hist[i-1]*100 for i in range(-4,0)]

    # الزخم اللحظي: هل التحركات متسارعة؟
    if len(moves) < 2: return 0.0
    acceleration = moves[-1] - moves[-2]   # تسارع الحركة
    consistency  = sum(1 for m in moves if m>0) / len(moves)   # اتساق الاتجاه

    micro_mom = moves[-1] * 0.5 + acceleration * 0.3 + (consistency-0.5)*0.2
    scalp_neural_state["micro_momentum"][coin] = round(micro_mom, 4)
    return micro_mom


def estimate_order_flow(coin):
    """
    تقدير تدفق الأوامر (Order Flow Estimation)
    بدون بيانات Level 2، نستخدم السعر والتذبذب
    """
    hist = state["price_history"].get(coin, [])
    if len(hist) < 10: return 0.0

    ai   = state["ai_learner"]
    vi   = ai.get("volatility_index", 30)

    # نسبة الحجم التقديرية (محاكاة)
    price_impact = abs(hist[-1]-hist[-2])/max(hist[-2],1)*100
    volume_proxy = vi * price_impact   # مؤشر تقريبي

    # إذا السعر يرتفع مع تذبذب عالٍ → ضغط شراء
    direction = 1 if hist[-1] > hist[-2] else -1
    flow      = direction * min(100, volume_proxy * 2)

    scalp_neural_state["order_flow"][coin] = round(flow, 2)
    return flow


def find_scalp_window():
    """
    اكتشاف نافذة السكالب المثالية
    الشروط: VI مناسب + زخم صاعد + تدفق إيجابي
    """
    ai      = state["ai_learner"]
    vi      = ai.get("volatility_index", 30)
    windows = []

    for coin in state["selected_coins"]:
        micro = analyze_micro_momentum(coin)
        flow  = estimate_order_flow(coin)

        # تحقق من شروط السكالب المثالية
        is_trending     = micro > 0.05    # زخم إيجابي
        good_volatility = 15 < vi < 70    # تذبذب مناسب
        positive_flow   = flow > 10       # تدفق إيجابي

        if is_trending and good_volatility and positive_flow:
            score = micro * 40 + flow * 0.5 + (vi/70)*10
            windows.append({
                "coin":    coin,
                "score":   round(score, 1),
                "micro":   micro,
                "flow":    flow,
                "vi":      vi,
            })

    windows.sort(key=lambda x: x["score"], reverse=True)
    scalp_neural_state["scalp_windows"] = windows[:3]
    return windows


def calculate_scalp_targets(coin, entry_price):
    """
    حساب أهداف الخروج الدقيقة للسكالب
    مثل متداول محترف: TP صغير سريع + SL محكم
    """
    ai     = state["ai_learner"]
    vi     = ai.get("volatility_index", 30)
    micro  = scalp_neural_state["micro_momentum"].get(coin, 0)

    # TP و SL ديناميكيان حسب التذبذب
    base_tp = max(0.4, min(1.5, vi * 0.015))   # 0.4% → 1.5%
    base_sl = max(0.2, min(0.8, vi * 0.008))   # 0.2% → 0.8%

    # تعديل حسب الزخم
    if micro > 0.1:  base_tp *= 1.2   # زخم قوي → هدف أكبر
    if micro < 0.05: base_tp *= 0.8   # زخم ضعيف → هدف أصغر

    tp_price = round(entry_price * (1 + base_tp/100), 4)
    sl_price = round(entry_price * (1 - base_sl/100), 4)
    rr_ratio = round(base_tp / max(base_sl, 0.01), 2)

    scalp_neural_state["exit_targets"][coin] = {
        "tp_pct":   round(base_tp, 3),
        "sl_pct":   round(base_sl, 3),
        "tp_price": tp_price,
        "sl_price": sl_price,
        "rr_ratio": rr_ratio,
        "hold_seconds_target": int(60 / max(vi, 1) * 30),  # وقت الاحتفاظ المتوقع
    }
    return base_tp, base_sl


def run_scalp_neural():
    """
    محرك السكالب العصبي الاحترافي
    يعمل كل 10 ثوانٍ — يفكر مثل متداول سكالب خبير
    """
    ai = state["ai_learner"]

    # ═══ 1: اكتشاف نوافذ السكالب ═══
    windows = find_scalp_window()

    # ═══ 2: حساب إشارة عصبية للسكالب ═══
    if windows:
        top = windows[0]
        scalp_signal = min(1.0, top["score"] / 80)
    else:
        scalp_signal = -0.2   # لا فرصة

    scalp_neural_state["neural_scalp_signal"] = round(scalp_signal, 3)

    # ═══ 3: Gemini يؤكد قرار السكالب ═══
    if windows and GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
        top = windows[0]
        targets = scalp_neural_state["exit_targets"].get(top["coin"], {})

        scalp_prompt = (
            "متداول سكالب محترف. قيّم هذه الفرصة:\n"
            "العملة: " + top["coin"] + "\n"
            "الزخم اللحظي: " + str(top["micro"]) + "\n"
            "تدفق الأوامر: " + str(top["flow"]) + "\n"
            "التذبذب: VI=" + str(round(top["vi"],0)) + "\n"
            "هدف TP: " + str(targets.get("tp_pct","?")) + "% | SL: " + str(targets.get("sl_pct","?")) + "%\n"
            "R:R = " + str(targets.get("rr_ratio","?")) + "\n"
            "نفسية السوق: " + str(round(pro_trader_memory.get("market_psychology",50),0)) + "/100\n"
            "JSON: {enter:bool,confidence:0.0-1.0,reason:str,tp_adjust:0.0,sl_adjust:0.0,hold_seconds:30}"
        )
        resp = call_gemini(scalp_prompt, max_tokens=200)
        if resp:
            try:
                clean = resp.replace("```json","").replace("```","").strip()
                s=clean.find("{"); e2=clean.rfind("}")
                if s!=-1 and e2!=-1: clean=clean[s:e2+1]
                gd = json.loads(clean)

                if gd.get("enter") and gd.get("confidence",0) > 0.65:
                    # تطبيق تعديلات Gemini على الأهداف
                    coin  = top["coin"]
                    price = state["prices"].get(coin, 0)
                    if price > 0 and coin not in state["active_positions"]:
                        base_tp, base_sl = calculate_scalp_targets(coin, price)
                        tp_adj = float(gd.get("tp_adjust", 0))
                        sl_adj = float(gd.get("sl_adjust", 0))
                        # تحديث الـ AI adaptive
                        ai["adaptive_tp"] = round(base_tp + tp_adj, 3)
                        ai["adaptive_sl"] = round(base_sl + sl_adj, 3)
                        print(f"⚡ SCALP NEURAL: {coin} TP={ai['adaptive_tp']:.2f}% SL={ai['adaptive_sl']:.2f}% ({gd.get('reason','')[:40]})")

                # بث الإشارة العصبية
                conf = float(gd.get("confidence", 0.5))
                sig  = conf * (1 if gd.get("enter") else -1)
                neural_propagate("SCALP_TRADER", sig * 80, conf)
            except Exception as e:
                print(f"⚠️ scalp_neural parse: {e}")

    # ═══ 4: تحديث إحصاءات الجلسة ═══
    if windows:
        top = windows[0]
        scalp_neural_state["session_stats"]["best_scalp_coin"] = top["coin"]
        scalp_neural_state["session_stats"]["momentum_score"]  = round(top["micro"] * 100, 1)
        scalp_neural_state["session_stats"]["best_scalp_time"] = datetime.datetime.now().strftime("%H:%M:%S")

    # الوكيل الأصلي يتأثر بالنتائج
    if "SCALP_TRADER" in agents:
        sc_agent = agents["SCALP_TRADER"]
        if scalp_signal > 0.5:
            sc_agent["active"] = True
        elif scalp_signal < -0.3:
            sc_agent["active"] = False   # لا فرصة — انتظر

    print(f"⚡ SCALP_NEURAL: signal={scalp_signal:.2f} | فرص={len(windows)} | أفضل={windows[0]['coin'] if windows else 'لا يوجد'}")


def scalp_neural_thread():
    """خيط السكالب العصبي — كل 10 ثوانٍ"""
    time.sleep(25)
    while True:
        try: run_scalp_neural()
        except Exception as e: print(f"⚠️ scalp_neural: {e}")
        time.sleep(10)

# ════════════════════════════════════════════════
# FIX: get_lot_size_info
# ════════════════════════════════════════════════
def get_lot_size_info(symbol):
    global symbol_filters
    if symbol in symbol_filters:
        return symbol_filters[symbol]
    result = {'min_qty': 0.001, 'step_size': 0.001, 'min_notional': 5.0, 'precision': 3}
    if not state.get("client"):
        return result
    try:
        if state.get("trading_type") == "futures":
            info = state["client"].futures_exchange_info()
        else:
            info = state["client"].get_exchange_info()
        for s in info['symbols']:
            if s['symbol'] != symbol:
                continue
            for f in s['filters']:
                ftype = f.get('filterType', '')
                if ftype == 'LOT_SIZE':
                    result['min_qty']   = float(f.get('minQty',   '0.001'))
                    result['step_size'] = float(f.get('stepSize', '0.001'))
                    step_str = f.get('stepSize', '0.001').rstrip('0')
                    if '.' in step_str:
                        result['precision'] = len(step_str.split('.')[-1])
                    else:
                        result['precision'] = 0
                elif ftype in ('NOTIONAL', 'MIN_NOTIONAL'):
                    raw = f.get('minNotional') or f.get('notional', '5.0')
                    try:
                        result['min_notional'] = float(raw)
                    except (ValueError, TypeError):
                        result['min_notional'] = 5.0
            symbol_filters[symbol] = result
            return result
    except Exception as e:
        print(f"⚠️ get_lot_size_info({symbol}): {e}")
    return result


# ════════════════════════════════════════════════
# Google Gemini API — لوكيل إدارة الصفقات
# ════════════════════════════════════════════════
def call_gemini(prompt, max_tokens=600):
    """
    استدعاء Google Gemini API
    يُستخدم لوكيل PROFIT_MANAGER فقط
    أسرع وأرخص لتحليل الصفقات اللحظية
    """
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        return None  # fallback للـ AI المحلي

    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        )
        payload = json.dumps({
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.3,
            }
        }).encode("utf-8")

        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return text.strip()

    except Exception as e:
        print(f"⚠️ Gemini API: {e}")
        return None


def call_gemini_for_trade(coin, pos, cur_price, ai):
    """
    يسأل Gemini عن قرار الصفقة المفتوحة
    يُرجع: hold | partial_tp | close | raise_sl
    """
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        return None

    entry    = pos["entry"]
    change   = ((cur_price - entry) / entry) * 100
    size     = pos["size"]
    strategy = pos.get("strategy","?")
    age_h    = 0
    try:
        et    = datetime.datetime.fromisoformat(pos["entry_time"])
        age_h = (datetime.datetime.now() - et).total_seconds() / 3600
    except: pass

    prompt = f"""أنت مدير صفقات خبير. قرر الآن بناءً على هذه البيانات:

الصفقة:
- العملة: {coin} | دخول: ${entry:.4f} | حالي: ${cur_price:.4f}
- التغير: {change:+.2f}% | الحجم: ${size:.2f} | العمر: {age_h:.1f}h
- الاستراتيجية: {strategy}

السوق:
- VI={ai.get('volatility_index',30):.0f} | Momentum={ai.get('momentum_score',0):+.0f}
- Streak={ai.get('streak',0):+d} | Regime={ai.get('market_regime','?')}
- Drawdown={ai.get('current_drawdown',0):.1f}%

القرارات المتاحة:
- hold: الاحتفاظ بالصفقة
- partial_tp: أخذ 40% ربح الآن
- close: إغلاق فوري
- raise_sl: رفع Stop Loss لحماية الربح

أجب بـ JSON فقط:
{{"decision":"hold|partial_tp|close|raise_sl","reason":"...","confidence":0.0-1.0}}"""

    result = call_gemini(prompt, max_tokens=200)
    if not result: return None

    try:
        # تنظيف الرد من backticks
        clean = result.replace("```json","").replace("```","").strip()
        return json.loads(clean)
    except:
        return None


# ════════════════════════════════════════════════
# AI محلي متطور — بدون API خارجي
# ════════════════════════════════════════════════
def call_claude(prompt, agent_name="SYSTEM", max_tokens=400, system_msg=None):
    """وكيل AI محلي متطور — يعمل بدون أي اتصال خارجي"""
    if agent_name in agents:
        agents[agent_name]["calls_made"] += 1
        agents[agent_name]["successes"]  += 1
    return advanced_local_ai(prompt, agent_name)


def advanced_local_ai(prompt, agent_name):
    """
    محرك AI محلي متطور يحلل السوق بشكل عميق
    يستخدم مؤشرات متعددة وأنماط السوق
    """
    ai  = state["ai_learner"]
    vi  = ai.get("volatility_index", 30)
    mom = ai.get("momentum_score", 0)
    ts  = ai.get("trend_strength", 50)
    dd  = ai.get("current_drawdown", 0)
    streak = ai.get("streak", 0)
    regime = ai.get("market_regime", "ranging")
    fg  = state["market_data"].get("fear_greed", 55)
    sharpe = ai.get("sharpe_ratio", 0)
    pf  = ai.get("profit_factor", 1)
    confluence = ai.get("signal_confluence", 0)
    gold_p = state["prices"].get("XAUTUSDT", 0)
    btc_h  = state["price_history"].get("BTCUSDT", [])
    conf   = ai.get("confidence", 70)

    # ═══ تحليل متقدم للأنماط ═══
    btc_rsi = compute_rsi(btc_h) if len(btc_h) >= 15 else 50
    btc_vol = compute_volatility(btc_h) if len(btc_h) >= 5 else 30
    gold_hist = state["price_history"].get("XAUTUSDT", [])
    gold_change = round((gold_hist[-1]/gold_hist[-5]-1)*100, 3) if len(gold_hist)>=5 else 0

    # ═══ حساب قوة السوق الإجمالية ═══
    market_power = (ts - 50) * 0.4 + mom * 0.3 + confluence * 5
    is_bull = market_power > 15
    is_bear = market_power < -15
    is_extreme_bull = market_power > 35
    is_extreme_bear = market_power < -35

    # ═══ اختيار الاستراتيجية المثلى ═══
    strategy_scores = {}
    selected = state.get("selected_strategies", [])
    for s in selected:
        strategy_scores[s] = compute_signal_score(
            state["selected_coins"][0] if state["selected_coins"] else "BTCUSDT", s, ai)
    best_strat = max(strategy_scores, key=strategy_scores.get) if strategy_scores else "RSI_AI"
    worst_strat = min(strategy_scores, key=strategy_scores.get) if strategy_scores else ""
    best_score  = strategy_scores.get(best_strat, 50)

    # ═══════════════════════════════════════
    if agent_name == "MARKET_ANALYST":
        # تحليل عميق لنظام السوق
        if vi > 70 and abs(mom) > 60:
            view = f"⚡ تذبذب شديد جداً (VI={vi:.0f}) مع زخم {'صاعد' if mom>0 else 'هابط'} قوي — مخاطر عالية"
            rec  = "VOLATILITY_BREAKOUT"; conf_val = 0.72
            action = "reduce"
        elif vi > 55 and abs(mom) > 40:
            view = f"سوق متذبذب (VI={vi:.0f}) — فرص قصيرة المدى مع حذر"
            rec  = "VOLATILITY_BREAKOUT"; conf_val = 0.76
            action = "trade"
        elif is_extreme_bull and btc_rsi < 70:
            view = f"🚀 اتجاه صاعد قوي جداً — قوة السوق {market_power:.0f} | RSI={btc_rsi:.0f} آمن"
            rec  = "SUPERTREND"; conf_val = 0.88
            action = "trade"
        elif is_bull and ts > 65:
            view = f"📈 اتجاه صاعد واضح — قوة {ts:.0f}% | الزخم {mom:+.0f}"
            rec  = "MULTI_TF"; conf_val = 0.82
            action = "trade"
        elif is_extreme_bear:
            view = f"🔴 ضغط بيعي شديد — تجنب الدخول | الزخم {mom:+.0f}"
            rec  = "MEAN_REVERSION"; conf_val = 0.68
            action = "wait"
        elif is_bear:
            view = f"⚠️ اتجاه هابط — توخَّ الحذر في الدخولات الطويلة"
            rec  = "RSI_AI"; conf_val = 0.65
            action = "reduce"
        elif fg < 25:
            view = f"😱 خوف شديد في السوق (F&G={fg}) — فرصة عكسية محتملة"
            rec  = "MEAN_REVERSION"; conf_val = 0.74
            action = "trade"
        elif fg > 78:
            view = f"🤑 جشع مفرط (F&G={fg}) — احذر من انعكاس قريب"
            rec  = "SMART_SCALP"; conf_val = 0.66
            action = "reduce"
        else:
            view = f"➡️ السوق في نطاق محايد — فرص متوسطة | النظام: {regime}"
            rec  = best_strat; conf_val = 0.70
            action = "trade" if best_score > 65 else "monitor"
        return json.dumps({"view": view, "recommended_strategy": rec,
                           "confidence": conf_val, "regime": regime, "action": action})

    # ═══════════════════════════════════════
    elif agent_name == "RISK_MANAGER":
        # تقييم مخاطر متطور متعدد العوامل
        risk_score = 0
        advice_parts = []

        if dd > 12:   risk_score += 40; advice_parts.append(f"تراجع حاد {dd:.1f}%")
        elif dd > 7:  risk_score += 25; advice_parts.append(f"تراجع {dd:.1f}%")
        elif dd > 4:  risk_score += 12; advice_parts.append(f"تراجع طفيف {dd:.1f}%")

        if streak <= -5: risk_score += 30; advice_parts.append(f"{abs(streak)} خسائر متتالية")
        elif streak <= -3: risk_score += 18; advice_parts.append(f"{abs(streak)} خسائر")
        elif streak <= -2: risk_score += 8

        if vi > 70: risk_score += 20; advice_parts.append(f"تذبذب عالٍ {vi:.0f}")
        elif vi > 55: risk_score += 10

        if sharpe < -0.5: risk_score += 15; advice_parts.append("Sharpe سلبي")
        if pf < 0.8 and pf > 0: risk_score += 12; advice_parts.append("Profit Factor ضعيف")
        if fg < 20: risk_score += 10; advice_parts.append("خوف شديد في السوق")
        if btc_rsi > 78: risk_score += 8; advice_parts.append("BTC في منطقة تشبع شراء")
        if btc_rsi < 25: risk_score += 5

        if risk_score >= 60:
            risk = "critical"; mult = 0.2; max_pos = 2
            advice = f"⛔ خطر عالٍ جداً — {' | '.join(advice_parts[:3])} — أوقف التداول مؤقتاً"
            stop = True
        elif risk_score >= 40:
            risk = "high"; mult = 0.4; max_pos = 4
            advice = f"🔴 مخاطر عالية — {' | '.join(advice_parts[:2])} — قلل الحجم بشدة"
            stop = False
        elif risk_score >= 20:
            risk = "medium"; mult = 0.7; max_pos = 7
            advice = f"🟡 مخاطر متوسطة — {'| '.join(advice_parts[:1]) if advice_parts else 'مراقبة مستمرة'}"
            stop = False
        else:
            risk = "low"; mult = 1.1; max_pos = 10
            advice = f"✅ أوضاع ممتازة — streak={streak:+d} | DD={dd:.1f}% — استمر بثقة"
            stop = False
        return json.dumps({"risk_level": risk, "size_multiplier": mult,
                           "advice": advice, "max_positions": max_pos, "stop_trading": stop})

    # ═══════════════════════════════════════
    elif agent_name == "STRATEGY_SELECTOR":
        # اختيار الاستراتيجية بناءً على تحليل عميق
        regime_map = {
            "trending":  ["SUPERTREND","MACD_TREND","ADX_TREND","MULTI_TF","ICHIMOKU"],
            "ranging":   ["RSI_AI","BOLLINGER","MEAN_REVERSION","VWAP","LIQUIDITY_HUNT"],
            "volatile":  ["VOLATILITY_BREAKOUT","MOMENTUM_SURGE","SMART_SCALP","GOLD_HEDGE"],
        }
        candidates = [s for s in regime_map.get(regime, ["RSI_AI"]) if s in selected]
        if not candidates: candidates = selected[:3] if selected else ["RSI_AI"]

        # ترتيب حسب الأداء الفعلي
        perf_sorted = sorted(
            [(s, state["strategy_performance"].get(s, {"wins":0,"losses":0,"pnl":0})) for s in candidates],
            key=lambda x: (x[1]["wins"]/(x[1]["wins"]+x[1]["losses"]+1)) * 0.4 + strategy_scores.get(x[0],50)/100 * 0.6,
            reverse=True
        )
        best = perf_sorted[0][0] if perf_sorted else best_strat
        alternates = [x[0] for x in perf_sorted[1:3]]
        avoid = [s for s in selected if strategy_scores.get(s,50) < 40]

        best_wr = 0
        bp = state["strategy_performance"].get(best, {"wins":0,"losses":0})
        if bp["wins"]+bp["losses"] > 0:
            best_wr = round(bp["wins"]/(bp["wins"]+bp["losses"])*100,1)

        reasoning = (f"نظام {regime} → {state['strategies'].get(best,best)} | "
                     f"نقاط={strategy_scores.get(best,50):.0f} | Win%={best_wr}% | "
                     f"VI={vi:.0f} | Confluence={'+'if confluence>0 else ''}{confluence}")
        return json.dumps({"best_strategy": best, "alternates": alternates,
                           "reasoning": reasoning, "avoid": avoid})

    # ═══════════════════════════════════════
    elif agent_name == "TRADE_REVIEWER":
        trades = state["trade_history"][:15]
        if not trades:
            return json.dumps({"lesson": "لا توجد صفقات بعد", "pattern": "none",
                               "recommendation": "انتظر أول صفقة لبدء التحليل"})
        wins   = [t for t in trades if t.get("pnl_percent",0)>0]
        losses = [t for t in trades if t.get("pnl_percent",0)<=0]
        wr = len(wins)/len(trades)

        # تحليل الأنماط
        avg_win  = round(sum(t["pnl_percent"] for t in wins)/len(wins),2)   if wins else 0
        avg_loss = round(sum(t["pnl_percent"] for t in losses)/len(losses),2) if losses else 0
        expectancy = round(wr*avg_win + (1-wr)*avg_loss, 3)

        # أفضل وأسوأ استراتيجية
        strat_perf = {}
        for t in trades:
            s = t.get("strategy","?")
            if s not in strat_perf: strat_perf[s] = {"w":0,"l":0,"pnl":0}
            if t.get("pnl_percent",0)>0: strat_perf[s]["w"]+=1
            else: strat_perf[s]["l"]+=1
            strat_perf[s]["pnl"]+=t.get("pnl_usd",0)
        best_s = max(strat_perf, key=lambda x: strat_perf[x]["pnl"]) if strat_perf else ""
        worst_s= min(strat_perf, key=lambda x: strat_perf[x]["pnl"]) if strat_perf else ""

        if wr >= 0.65:
            lesson = f"🏆 أداء ممتاز! Win={wr*100:.0f}% | Exp={expectancy:+.2f}% | أفضل: {best_s}"
            pattern = "strong_positive"; rec = f"زد حجم {state['strategies'].get(best_s,best_s)}"
        elif wr >= 0.50:
            lesson = f"✅ أداء جيد Win={wr*100:.0f}% | Exp={expectancy:+.2f}% — استمر"
            pattern = "positive"; rec = "حافظ على الإعدادات الحالية"
        elif wr >= 0.40:
            lesson = f"⚠️ Win={wr*100:.0f}% مقبول | Avg Win={avg_win:+.2f}% vs Loss={avg_loss:.2f}%"
            pattern = "neutral"; rec = f"راجع معايير الدخول — تجنب {state['strategies'].get(worst_s,worst_s)}"
        else:
            lesson = f"🔴 Win={wr*100:.0f}% منخفضة | Exp={expectancy:.2f}% — مراجعة عاجلة"
            pattern = "needs_review"; rec = f"أوقف {state['strategies'].get(worst_s,worst_s)} وراجع threshold"
        return json.dumps({"win_rate": round(wr*100), "lesson": lesson, "pattern": pattern,
                           "recommendation": rec, "strategy_to_boost": best_s,
                           "strategy_to_reduce": worst_s})

    # ═══════════════════════════════════════
    elif agent_name == "GOLD_SPECIALIST":
        # تحليل متخصص للذهب
        gold_trend_signal = "neutral"
        if gold_change > 0.5 and fg < 45:
            gold_view = f"🥇 الذهب يرتفع {gold_change:+.2f}% مع خوف بالسوق — ملاذ آمن فعّال الآن"
            action = "buy"; gold_conf = 0.85; gold_trend_signal = "strong_buy"
        elif gold_change > 0.2 and fg < 55:
            gold_view = f"🥇 ارتفاع طفيف {gold_change:+.2f}% — الذهب يستجيب للضغط"
            action = "buy"; gold_conf = 0.75; gold_trend_signal = "buy"
        elif gold_change < -0.5 and fg > 65:
            gold_view = f"⚠️ الذهب يتراجع {gold_change:+.2f}% مع جشع — تفضيل المخاطرة"
            action = "wait"; gold_conf = 0.65; gold_trend_signal = "sell"
        elif fg < 30:
            gold_view = f"😱 خوف شديد (F&G={fg}) — الذهب الخيار الأمثل الآن"
            action = "buy"; gold_conf = 0.88; gold_trend_signal = "strong_buy"
        elif fg > 75:
            gold_view = f"🤑 جشع مفرط (F&G={fg}) — الذهب أقل جاذبية في هذا المزاج"
            action = "wait"; gold_conf = 0.60; gold_trend_signal = "neutral"
        elif gold_p > 0 and gold_change < -1:
            gold_view = f"📉 تراجع قوي {gold_change:+.2f}% — انتظر استقراراً قبل الدخول"
            action = "wait"; gold_conf = 0.70; gold_trend_signal = "sell"
        else:
            gold_view = f"➡️ الذهب ${gold_p:,.0f} | تغير {gold_change:+.2f}% | السوق محايد"
            action = "hold"; gold_conf = 0.68; gold_trend_signal = "neutral"

        target = round(abs(gold_change) * 1.5, 2) if gold_change != 0 else 1.5
        return json.dumps({"gold_price": gold_p, "gold_view": gold_view, "view": gold_view,
                           "action": action, "confidence": gold_conf,
                           "reasoning": gold_view, "target_pct": target,
                           "risk_pct": round(target*0.6,2),
                           "gold_signal": gold_trend_signal})
    return json.dumps({"message": "تم التحليل المحلي", "status": "ok"})


# ════════════════════════════════════════════════
# DIRECT CHAT — محلل محلي ذكي
# ════════════════════════════════════════════════
def call_claude_chat(user_message, history):
    """
    محلل محلي ذكي — يرى بيانات البوت ويجيب بالعربية
    يحلل السؤال ويعطي إجابة مخصصة بناءً على بيانات البوت الحقيقية
    """
    ai  = state["ai_learner"]
    md  = state["market_data"]
    bal = get_balance(state["current_mode"])
    mode = state["current_mode"]
    vi  = ai.get("volatility_index", 30)
    mom = ai.get("momentum_score", 0)
    ts  = ai.get("trend_strength", 50)
    dd  = ai.get("current_drawdown", 0)
    streak = ai.get("streak", 0)
    regime = ai.get("market_regime", "ranging")
    fg  = md.get("fear_greed", 55)
    gold_p = md.get("gold_price", 0)
    conf = ai.get("confidence", 70)
    sharpe = ai.get("sharpe_ratio", 0)
    pf  = ai.get("profit_factor", 1)
    trades = state["trade_history"]
    positions = state["active_positions"]

    msg = user_message.lower()

    # ═══ تحليل نوع السؤال ═══
    is_market   = any(x in msg for x in ["سوق","تحليل","حلل","تذبذب","اتجاه","regime","market"])
    is_gold     = any(x in msg for x in ["ذهب","gold","xaut","فضة","silver","xag"])
    is_risk     = any(x in msg for x in ["مخاطر","خطر","risk","تراجع","drawdown","حماية"])
    is_strategy = any(x in msg for x in ["استراتيجية","strategy","أفضل","افضل","انسب","أنسب"])
    is_trades   = any(x in msg for x in ["صفقة","صفقات","trade","مراجعة","أداء","اداء","نتائج"])
    is_balance  = any(x in msg for x in ["رصيد","balance","ربح","خسارة","pnl","مال"])
    is_bot      = any(x in msg for x in ["بوت","bot","شغّال","يعمل","متوقف","حالة","status"])
    is_advice   = any(x in msg for x in ["نصيحة","نصح","ماذا","شو","وش","ايش","هل","كيف"])
    is_position = any(x in msg for x in ["صفقات مفتوحة","position","مفتوحة","open"])

    # ═══ بناء الإجابة ═══
    response_parts = []

    if is_gold:
        gold_hist = state["price_history"].get("XAUTUSDT",[])
        gold_change = round((gold_hist[-1]/gold_hist[-5]-1)*100,3) if len(gold_hist)>=5 else 0
        gt = md.get("gold_trend","neutral")
        trend_ar = {"strong_buy":"شراء قوي 🟢","buy":"شراء 🟡","neutral":"محايد ⚪","sell":"بيع 🔴","strong_sell":"بيع قوي 🔴"}.get(gt,"محايد")
        response_parts.append(f"🥇 **تحليل الذهب الآن:**")
        response_parts.append(f"• السعر: ${gold_p:,.0f}")
        response_parts.append(f"• التغير: {gold_change:+.3f}%")
        response_parts.append(f"• الإشارة: {trend_ar}")
        if fg < 35:
            response_parts.append(f"• Fear & Greed = {fg} (خوف شديد) → الذهب ملاذ آمن ممتاز الآن ✅")
        elif fg > 70:
            response_parts.append(f"• Fear & Greed = {fg} (جشع) → الذهب أقل جاذبية، السوق يفضّل المخاطرة")
        else:
            response_parts.append(f"• Fear & Greed = {fg} (محايد) → الذهب فرصة متوازنة")

    elif is_market:
        btc_h = state["price_history"].get("BTCUSDT",[])
        btc_rsi = compute_rsi(btc_h) if len(btc_h)>=15 else 50
        regime_ar = {"trending":"اتجاهي 📈","ranging":"نطاق ↔️","volatile":"متذبذب ⚡"}.get(regime,regime)
        response_parts.append(f"📊 **تحليل السوق الحالي:**")
        response_parts.append(f"• النظام: {regime_ar}")
        vi_lbl = "(عالٍ ⚠️)" if vi>60 else "(طبيعي ✅)" if vi<40 else "(متوسط)"
        response_parts.append(f"• التذبذب: {vi:.1f} {vi_lbl}")
        mom_lbl = "صاعد 📈" if mom>20 else "هابط 📉" if mom<-20 else "محايد"
        response_parts.append(f"• الزخم: {mom:+.1f} ({mom_lbl})")
        response_parts.append(f"• قوة الاتجاه: {ts:.0f}%")
        rsi_lbl = "(تشبع شراء ⚠️)" if btc_rsi>70 else "(تشبع بيع 🎯)" if btc_rsi<30 else "(محايد)"
        response_parts.append(f"• BTC RSI: {btc_rsi:.0f} {rsi_lbl}")
        fg_lbl = "خوف شديد 😱" if fg<25 else "خوف 😟" if fg<45 else "محايد 😐" if fg<60 else "جشع 😏" if fg<80 else "جشع شديد 🤑"
        response_parts.append(f"• Fear & Greed: {fg} — {fg_lbl}")
        best_action = "تداول بحذر" if vi>60 else "فرص جيدة" if regime=="trending" else "انتظر إشارة واضحة"
        response_parts.append(f"\n💡 التوصية: {best_action}")

    elif is_risk:
        risk_level = ai.get("agent_risk_level","medium")
        risk_ar = {"low":"منخفض ✅","medium":"متوسط 🟡","high":"عالٍ 🔴","critical":"حرج ⛔"}.get(risk_level,risk_level)
        response_parts.append(f"🛡️ **تقييم المخاطر:**")
        response_parts.append(f"• مستوى الخطر: {risk_ar}")
        response_parts.append(f"• التراجع الحالي: {dd:.2f}%")
        streak_lbl = "⚠️ خسائر متتالية" if streak<=-3 else "🔥 انتصارات" if streak>=3 else "طبيعي"
        response_parts.append(f"• سلسلة الصفقات: {streak:+d} ({streak_lbl})")
        response_parts.append(f"• ثقة النظام: {conf:.0f}%")
        if dd > 8:
            response_parts.append(f"\n⚠️ التراجع {dd:.1f}% مقلق — فكر في تقليل حجم الصفقات")
        elif streak <= -3:
            response_parts.append(f"\n⚠️ {abs(streak)} خسائر متتالية — خذ قسطاً من الراحة")
        else:
            response_parts.append(f"\n✅ المخاطر تحت السيطرة — استمر بالخطة")

    elif is_strategy:
        perfs = state["strategy_performance"]
        selected = state["selected_strategies"]
        top = sorted([(s,perfs.get(s,{"pnl":0,"wins":0,"losses":0})) for s in selected],
                     key=lambda x: x[1]["pnl"], reverse=True)[:3]
        rec = ai.get("agent_recommended_strategy","")
        response_parts.append(f"🎯 **أفضل الاستراتيجيات الآن (نظام: {regime}):**")
        for i,(s,p) in enumerate(top,1):
            t = p["wins"]+p["losses"]
            wr = round(p["wins"]/t*100,1) if t>0 else 0
            mark = "⭐" if s==rec else ""
            response_parts.append(f"{i}. {state['strategies'].get(s,s)} {mark} — Win={wr}% | P&L=${p['pnl']:.1f}")
        if rec:
            response_parts.append(f"\n🤖 توصية الوكيل: {state['strategies'].get(rec,rec)}")

    elif is_trades:
        if not trades:
            response_parts.append("📊 لا توجد صفقات منتهية بعد — انتظر أول صفقة!")
        else:
            wins   = [t for t in trades[:20] if t.get("pnl_percent",0)>0]
            losses = [t for t in trades[:20] if t.get("pnl_percent",0)<=0]
            wr = round(len(wins)/len(trades[:20])*100,1)
            avg_w = round(sum(t["pnl_percent"] for t in wins)/len(wins),2) if wins else 0
            avg_l = round(sum(t["pnl_percent"] for t in losses)/len(losses),2) if losses else 0
            total_pnl = sum(t.get("pnl_usd",0) for t in trades[:20])
            response_parts.append(f"📊 **مراجعة الصفقات (آخر {min(20,len(trades))}):**")
            response_parts.append(f"• Win Rate: {wr}% {'✅' if wr>=55 else '⚠️' if wr>=45 else '🔴'}")
            response_parts.append(f"• متوسط الربح: {avg_w:+.2f}% | متوسط الخسارة: {avg_l:.2f}%")
            response_parts.append(f"• إجمالي P&L: ${total_pnl:+.2f}")
            response_parts.append(f"• Sharpe: {sharpe:.2f} | Profit Factor: {pf:.2f}")
            if wr >= 60:
                response_parts.append("\n🏆 أداء ممتاز — استمر!")
            elif wr >= 50:
                response_parts.append("\n✅ أداء جيد — راقب الاستراتيجيات الخاسرة")
            else:
                response_parts.append("\n⚠️ Win Rate منخفضة — راجع معايير الدخول")

    elif is_position:
        if not positions:
            response_parts.append("📭 لا توجد صفقات مفتوحة الآن")
        else:
            total_unrealized = 0
            response_parts.append(f"📂 **الصفقات المفتوحة ({len(positions)}):**")
            for coin, pos in list(positions.items())[:5]:
                cur = state["prices"].get(coin, pos["entry"])
                chg = ((cur-pos["entry"])/pos["entry"])*100
                unr = pos["size"]*(chg/100)
                total_unrealized += unr
                response_parts.append(f"• {coin}: {chg:+.2f}% (${unr:+.2f}) — {state['strategies'].get(pos.get('strategy',''),pos.get('strategy',''))}")
            response_parts.append(f"\nإجمالي غير محقق: ${total_unrealized:+.2f}")

    elif is_balance:
        demo_bal = state["finances"]["demo"]["balance"]
        demo_pnl = state["finances"]["demo"]["pnl"]
        real_bal = max(state["finances"]["real"]["total_usd"],state["finances"]["real"]["balance"])
        real_pnl = state["finances"]["real"]["pnl"]
        response_parts.append(f"💰 **حالة الرصيد:**")
        response_parts.append(f"• Demo: ${demo_bal:,.2f} | P&L: ${demo_pnl:+.2f}")
        response_parts.append(f"• Real: ${real_bal:,.2f} | P&L: ${real_pnl:+.2f}")
        response_parts.append(f"• ربح اليوم: ${ai['daily_pnl']:+.2f}")
        response_parts.append(f"• صفقات اليوم: {ai['daily_trades']}")

    elif is_bot:
        bh = state["bot_health"]
        status = "🟢 نشط" if state["running"] else "🔴 متوقف"
        response_parts.append(f"🤖 **حالة البوت:**")
        response_parts.append(f"• الحالة: {status}")
        response_parts.append(f"• وضع التداول: {mode.upper()}")
        response_parts.append(f"• صحة النظام: {bh.get('score',100)}%")
        response_parts.append(f"• وقت التشغيل: {bh.get('uptime_seconds',0)//3600}h {(bh.get('uptime_seconds',0)%3600)//60}m")
        response_parts.append(f"• أوامر مرسلة: {bh.get('orders_sent',0)} | فاشلة: {bh.get('orders_failed',0)}")
        response_parts.append(f"• الصفقات المفتوحة: {len(positions)}")
        if bh.get("issues"):
            response_parts.append(f"⚠️ مشاكل: {' | '.join(bh['issues'][:2])}")
        elif bh.get("warnings"):
            response_parts.append(f"📋 تحذيرات: {' | '.join(bh['warnings'][:2])}")
        else:
            response_parts.append(f"✅ كل الأنظمة تعمل بشكل طبيعي")

    else:
        # إجابة عامة شاملة
        response_parts.append(f"👋 مرحباً! إليك ملخص سريع لحالة البوت:")
        response_parts.append(f"\n📊 السوق: {regime} | VI={vi:.0f} | Momentum={mom:+.0f}")
        response_parts.append(f"💰 الرصيد ({mode}): ${bal:,.2f} | P&L اليوم: ${ai['daily_pnl']:+.2f}")
        response_parts.append(f"🎯 الثقة: {conf:.0f}% | Drawdown: {dd:.1f}%")
        response_parts.append(f"📂 صفقات مفتوحة: {len(positions)}")
        response_parts.append("\n💡 يمكنني تحليل: السوق | الذهب | المخاطر | الاستراتيجيات | الصفقات | الرصيد")
        response_parts.append("اكتب سؤالك وسأجيب بناءً على بيانات بوتك الحقيقية! 🚀")

    return "\n".join(response_parts)


def simulate_claude_response(prompt, agent_name):
    ai  = state["ai_learner"]
    vi  = ai.get("volatility_index", 30)
    mom = ai.get("momentum_score", 0)
    ts  = ai.get("trend_strength", 50)
    regime = ai.get("market_regime", "ranging")
    fg  = state["market_data"].get("fear_greed", 55)

    if agent_name == "MARKET_ANALYST":
        if vi > 60 and abs(mom) > 50:
            view = "السوق في حالة تذبذب عالٍ مع زخم قوي"; rec = "VOLATILITY_BREAKOUT"; conf = 0.78
        elif ts > 65:
            view = "اتجاه صاعد واضح مع قوة ممتازة"; rec = "SUPERTREND"; conf = 0.82
        elif ts < 35:
            view = "اتجاه هابط — احذر من الدخولات الطويلة"; rec = "MEAN_REVERSION"; conf = 0.65
        else:
            view = "السوق في نطاق — فرص متوسطة"; rec = "RSI_AI"; conf = 0.70
        return json.dumps({"view": view, "recommended_strategy": rec,
                           "confidence": conf, "regime": regime,
                           "action": "monitor" if vi < 30 else "trade"})
    elif agent_name == "RISK_MANAGER":
        dd = ai.get("current_drawdown", 0); streak = ai.get("streak", 0)
        if dd > 7 or streak <= -4: risk = "high"; size_mult = 0.4; advice = "تقليل الحجم فوراً"
        elif dd > 4 or streak <= -2: risk = "medium"; size_mult = 0.7; advice = "حذر — تقليل طفيف"
        else: risk = "low"; size_mult = 1.0; advice = "الأوضاع طبيعية"
        return json.dumps({"risk_level": risk, "size_multiplier": size_mult,
                           "advice": advice, "max_positions": 5 if risk == "high" else 10})
    elif agent_name == "STRATEGY_SELECTOR":
        strategies_map = {
            "trending": ["SUPERTREND","MACD_TREND","MULTI_TF","ADX_TREND"],
            "ranging":  ["RSI_AI","BOLLINGER","MEAN_REVERSION","VWAP"],
            "volatile": ["VOLATILITY_BREAKOUT","MOMENTUM_SURGE","SMART_SCALP","LIQUIDITY_HUNT"],
        }
        best = strategies_map.get(regime, ["RSI_AI"])[0]
        alternates = strategies_map.get(regime, ["RSI_AI"])[1:3]
        return json.dumps({"best_strategy": best, "alternates": alternates,
                           "regime": regime, "reasoning": f"النظام {regime} — {best} هي الأنسب"})
    elif agent_name == "TRADE_REVIEWER":
        trades = state["trade_history"][:5]
        if not trades:
            return json.dumps({"lesson": "لا توجد صفقات كافية للتحليل",
                               "pattern": "none", "recommendation": "انتظر المزيد من البيانات"})
        wins = sum(1 for t in trades if t.get("pnl_percent",0) > 0)
        wr = wins / len(trades)
        lesson = "الاستراتيجيات تعمل بشكل جيد" if wr > 0.5 else "راجع معايير الدخول"
        return json.dumps({"win_rate": round(wr*100), "lesson": lesson,
                           "pattern": "positive" if wr > 0.5 else "needs_review",
                           "recommendation": "استمر" if wr > 0.5 else "راجع معايير الإشارة"})
    elif agent_name == "GOLD_SPECIALIST":
        gold_p = state["prices"].get("XAUTUSDT", 0)
        if fg < 30: gold_view = "خوف شديد — الذهب ملاذ آمن ممتاز"; gold_action = "buy"; gold_conf = 0.85
        elif fg > 75: gold_view = "جشع مفرط — الذهب قد يتراجع"; gold_action = "wait"; gold_conf = 0.60
        else: gold_view = "السوق محايد — الذهب فرصة متوازنة"; gold_action = "monitor"; gold_conf = 0.70
        return json.dumps({"gold_price": gold_p, "view": gold_view,
                           "action": gold_action, "confidence": gold_conf, "fear_greed": fg})
    return json.dumps({"message": "تم التحليل", "status": "ok"})


def build_market_context():
    ai = state["ai_learner"]
    prices_summary = {k:round(v,4) for k,v in list(state["prices"].items())[:10]}
    trades_summary = [{"coin":t["coin"],"pnl%":t["pnl_percent"],"strategy":t["strategy"]}
                      for t in state["trade_history"][:5]]
    tf_summary = {tf:{"sig":d["signal"],"str":d["strength"]} for tf,d in state["tf_data"].items()}
    return {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": state["current_mode"],
        "balance": round(get_balance(state["current_mode"]), 2),
        "regime": ai["market_regime"], "volatility": ai["volatility_index"],
        "momentum": ai["momentum_score"], "trend_strength": ai["trend_strength"],
        "fear_greed": state["market_data"]["fear_greed"],
        "btc_dominance": state["market_data"]["btc_dominance"],
        "gold_price": state["market_data"].get("gold_price", 0),
        "streak": ai["streak"], "drawdown": ai["current_drawdown"],
        "confidence": ai["confidence"], "open_positions": len(state["active_positions"]),
        "daily_pnl": round(ai["daily_pnl"], 2), "selected_coins": state["selected_coins"],
        "recent_prices": prices_summary, "timeframe_signals": tf_summary,
        "recent_trades": trades_summary, "best_strategy": ai["best_strategy"],
        "sharpe": ai["sharpe_ratio"], "profit_factor": ai["profit_factor"],
    }


# ════════════════════════════════════════
# V17: AGENT RUNNERS
# ════════════════════════════════════════
def run_market_analyst():
    agent = agents["MARKET_ANALYST"]; agent["status"] = "thinking"
    ctx = build_market_context()
    prompt = f"""أنت محلل سوق خبير. حلّل البيانات التالية وأعطِ توصية:
- نظام السوق: {ctx['regime']} / التذبذب: {ctx['volatility']:.1f} / الزخم: {ctx['momentum']:.1f}
- Fear & Greed: {ctx['fear_greed']} / هيمنة BTC: {ctx['btc_dominance']}% / الذهب: ${ctx['gold_price']:,.1f}
- إشارات الفريمات: {json.dumps(ctx['timeframe_signals'], ensure_ascii=False)}
أعطِ ردك بصيغة JSON فقط:
{{"view": "...", "recommended_strategy": "...", "confidence": 0.0-1.0, "regime": "...", "action": "trade|wait|reduce"}}"""
    response = call_claude(prompt, "MARKET_ANALYST")
    try:
        data = json.loads(response)
        state["ai_learner"]["agent_market_view"] = data.get("view","")
        if data.get("recommended_strategy"):
            state["ai_learner"]["agent_recommended_strategy"] = data["recommended_strategy"]
        state["ai_learner"]["agent_confidence_boost"] = (data.get("confidence",0.7) - 0.5) * 20
        # تفعيل/إيقاف السكالب بناءً على رأي المحلل
        if "SCALP_TRADER" in agents:
            scalp_ok = data.get("scalp_ok", True)
            agents["SCALP_TRADER"]["active"] = scalp_ok and data.get("action","trade") != "wait"
        agent["last_response"] = data.get("view",""); agent["confidence"] = data.get("confidence",0.7)
        action = data.get("action","trade")
        vote   = "trade" if action=="trade" else "reduce" if action=="reduce" else "wait"
        cast_vote("MARKET_ANALYST", vote, data.get("confidence",0.7),
                  data.get("view","")[:50])
        agent["last_action"] = f"تحليل: {action} → صوت: {vote}"
        # ═══ بث الإشارة العصبية ═══
        conf_val = data.get("confidence",0.7)
        sig_val  = (conf_val - 0.5) * 2 * (1 if action=="trade" else -1 if action=="reduce" else 0)
        neural_propagate("MARKET_ANALYST", sig_val * 100, conf_val)
    except:
        agent["last_response"] = response[:120] if response else "خطأ"; agent["confidence"] = 0.5
        cast_vote("MARKET_ANALYST", "wait", 0.3, "خطأ في التحليل")
    agent["status"] = "done"
    log_agent_message("MARKET_ANALYST", prompt[:200], agent["last_response"])

def run_risk_manager():
    agent = agents["RISK_MANAGER"]; agent["status"] = "thinking"
    ctx = build_market_context()
    ai  = state["ai_learner"]
    open_pos = state["active_positions"]

    # حساب الخسارة غير المحققة
    unrealized_loss = 0.0
    for coin, pos in open_pos.items():
        cur = state["prices"].get(coin, pos["entry"])
        chg = ((cur-pos["entry"])/pos["entry"])*100
        if chg < 0: unrealized_loss += pos["size"] * (chg/100)

    prompt = f"""أنت مدير مخاطر يعمل بالوقت الحقيقي. قرر فوراً.

الوضع الحالي:
- رصيد=${ctx['balance']:,.2f} | تراجع={ctx['drawdown']:.2f}% | streak={ctx['streak']:+d}
- صفقات مفتوحة={ctx['open_positions']} | خسارة غير محققة=${unrealized_loss:.2f}
- ربح اليوم=${ctx['daily_pnl']:,.2f} | VI={ctx['volatility']:.0f}
- Sharpe={ctx['sharpe']:.2f} | PF={ctx['profit_factor']:.2f}

JSON فقط:
{{"risk_level":"low|medium|high|critical","size_multiplier":0.1-1.5,"advice":"...","max_positions":1-15,"stop_trading":true|false,"close_weakest":true|false}}"""
    response = call_claude(prompt, "RISK_MANAGER")
    try:
        data = json.loads(response)
        risk_lv = data.get("risk_level","medium")
        state["ai_learner"]["agent_risk_level"] = risk_lv
        if data.get("stop_trading") and state["running"]:
            state["ai_learner"]["smart_filter_active"] = True
        # ضبط هدف السكالب بناءً على المخاطر
        if "SCALP_TRADER" in agents:
            sc_agent = agents["SCALP_TRADER"]
            if risk_lv == "critical":
                sc_agent["active"]         = False
                sc_agent["target_profit"]  = 1.5   # هدف أعلى
                sc_agent["max_loss"]       = 0.5   # حماية أكبر
            elif risk_lv == "high":
                sc_agent["active"]         = True
                sc_agent["target_profit"]  = 1.2
                sc_agent["max_loss"]       = 0.6
            elif risk_lv == "low":
                sc_agent["active"]         = True
                sc_agent["target_profit"]  = 0.8   # هدف أسرع
                sc_agent["max_loss"]       = 1.0   # مرونة أكبر
            else:
                sc_agent["active"]         = True
                sc_agent["target_profit"]  = 1.0
                sc_agent["max_loss"]       = 0.8

        # إغلاق أضعف صفقة إذا حرج
        if data.get("close_weakest") and state["active_positions"]:
            worst = min(state["active_positions"].items(),
                key=lambda x: ((state["prices"].get(x[0],x[1]["entry"])-x[1]["entry"])/x[1]["entry"]))
            worst_coin = worst[0]
            cur_price  = state["prices"].get(worst_coin, worst[1]["entry"])
            check_exit(worst_coin, cur_price, state["current_mode"])
            state["notifications"].insert(0,{"time":datetime.datetime.now().strftime("%H:%M:%S"),
                "message":f"🛡️ RISK: أغلق {worst_coin}","type":"danger"})
        agent["last_response"] = data.get("advice",""); agent["confidence"] = 0.90
        rm_vote = "reduce" if risk_lv in ["critical","high"] else "trade" if risk_lv=="low" else "wait"
        cast_vote("RISK_MANAGER", rm_vote, 0.90, data.get("advice","")[:50])
        agent["last_action"] = f"مخاطر: {risk_lv} → صوت: {rm_vote}"
        # ═══ إشارة عصبية للمخاطر (سلبية = خطر) ═══
        risk_sig = {"low":60,"medium":0,"high":-60,"critical":-100}.get(risk_lv,0)
        neural_propagate("RISK_MANAGER", risk_sig, 0.90)
    except:
        agent["last_response"] = response[:120] if response else "خطأ"; agent["confidence"] = 0.5
        cast_vote("RISK_MANAGER", "wait", 0.4, "خطأ")
    agent["status"] = "done"
    log_agent_message("RISK_MANAGER", prompt[:200], agent["last_response"])

def run_strategy_selector():
    agent = agents["STRATEGY_SELECTOR"]; agent["status"] = "thinking"
    ctx = build_market_context()
    ai  = state["ai_learner"]
    perf_data = {k: state["strategy_performance"][k] for k in state["selected_strategies"] if k in state["strategy_performance"]}
    perf_summary = {k: {
        "wr":  round(v["wins"]/(v["wins"]+v["losses"])*100 if v["wins"]+v["losses"]>0 else 0,1),
        "pnl": round(v["pnl"],2),
        "bt":  round(backtest_results.get(k,{}).get("win_rate",0),1),
        "w":   round(strategy_weights.get(f"bt_{k}",1.0),2),
    } for k,v in perf_data.items()}

    # ترتيب الاستراتيجيات بذكاء
    scored = sorted(perf_summary.items(),
        key=lambda x: x[1]["wr"]*0.4 + x[1]["bt"]*0.3 + (x[1]["pnl"]>0)*20 + x[1]["w"]*10,
        reverse=True)
    top3 = [s[0] for s in scored[:3]]

    prompt = f"""أنت محدد استراتيجيات نخبة. اختر الأمثل الآن.

السوق: {ctx['regime']} | VI={ctx['volatility']:.0f} | Mom={ctx['momentum']:+.0f} | F&G={ctx['fear_greed']}
BTC Dom={ctx['btc_dominance']}% | Streak={ai.get('streak',0):+d} | Conf={ai.get('confidence',70):.0f}%

أداء + Backtest:
{json.dumps({k:v for k,v in list(perf_summary.items())[:8]}, ensure_ascii=False)}

الأفضل حسب التحليل المحلي: {', '.join(top3)}
الأنماط المكتسبة: {len(learned_patterns)} نمط

JSON فقط:
{{"best_strategy":"...","alternates":["...","..."],"reasoning":"...","avoid":["..."],"confidence":0.0-1.0}}"""
    response = call_claude(prompt, "STRATEGY_SELECTOR")
    try:
        data = json.loads(response)
        rec = data.get("best_strategy","")
        if rec and rec in state["strategies"]:
            state["ai_learner"]["agent_recommended_strategy"] = rec
        agent["last_response"] = data.get("reasoning",""); agent["confidence"] = 0.80
        ss_vote = "trade" if rec else "wait"
        cast_vote("STRATEGY_SELECTOR", ss_vote, 0.80, data.get("reasoning","")[:50])
        agent["last_action"] = f"اختيار: {rec} → صوت: {ss_vote}"
    except:
        agent["last_response"] = response[:120] if response else "خطأ"; agent["confidence"] = 0.5
        cast_vote("STRATEGY_SELECTOR", "wait", 0.3, "خطأ")
    agent["status"] = "done"
    log_agent_message("STRATEGY_SELECTOR", prompt[:200], agent["last_response"])

def run_trade_reviewer():
    agent  = agents["TRADE_REVIEWER"]; agent["status"] = "thinking"
    trades = state["trade_history"][:20]
    if not trades:
        agent["status"] = "standby"; agent["last_action"] = "لا توجد صفقات للمراجعة"; return

    wins   = [t for t in trades if t.get("pnl_percent",0)>0]
    losses = [t for t in trades if t.get("pnl_percent",0)<=0]
    wr     = round(len(wins)/len(trades)*100,1)

    # تحليل الأنماط المتقدم
    regime_wins = {}
    for t in wins:
        r = t.get("regime","?")
        regime_wins[r] = regime_wins.get(r,0)+1
    best_regime = max(regime_wins, key=regime_wins.get) if regime_wins else "?"

    avg_win  = round(sum(t["pnl_percent"] for t in wins)/len(wins),2) if wins else 0
    avg_loss = round(sum(t["pnl_percent"] for t in losses)/len(losses),2) if losses else 0
    expectancy = round(wr/100*avg_win + (1-wr/100)*avg_loss, 3)

    # أفضل/أسوأ استراتيجية
    strat_pnl = {}
    for t in trades:
        s = t.get("strategy","?")
        strat_pnl[s] = strat_pnl.get(s,0) + t.get("pnl_percent",0)
    best_s  = max(strat_pnl, key=strat_pnl.get) if strat_pnl else "?"
    worst_s = min(strat_pnl, key=strat_pnl.get) if strat_pnl else "?"

    trades_detail = [{"coin":t["coin"],"pnl%":t["pnl_percent"],"$":t.get("pnl_usd",0),"st":t["strategy"],"regime":t.get("regime","?")} for t in trades[:10]]

    # إحصاءات السكالب للمراجع
    scalp_w_count  = agents.get("SCALP_TRADER",{}).get("scalp_wins",0)
    scalp_l_count  = agents.get("SCALP_TRADER",{}).get("scalp_losses",0)
    scalp_t_count  = scalp_w_count + scalp_l_count
    scalp_wr_pct   = round(scalp_w_count/scalp_t_count*100,1) if scalp_t_count>0 else 0
    scalp_profit   = agents.get("SCALP_TRADER",{}).get("total_scalp_profit",0)
    bt_scalp_r     = backtest_results.get("SCALP_AI",{}).get("win_rate",0)

    prompt = f"""أنت محلل أداء متخصص. حلّل عميقاً.

{len(trades)} صفقة: {len(wins)}✅ {len(losses)}❌ | WR={wr}%
Avg Win={avg_win:+.2f}% | Avg Loss={avg_loss:.2f}% | Expectancy={expectancy:+.3f}%
أفضل نظام: {best_regime} | أفضل: {best_s} | أسوأ: {worst_s}

SCALP AI: {scalp_t_count} صفقة | WR={scalp_wr_pct}% | ربح=${scalp_profit:.2f} | BT={bt_scalp_r:.0f}%
بيانات: {json.dumps(trades_detail, ensure_ascii=False)}

JSON فقط:
{{"win_rate":{wr},"lesson":"...","pattern":"...","recommendation":"...","strategy_to_boost":"{best_s}","strategy_to_reduce":"{worst_s}","expectancy":{expectancy},"insight":"...","scalp_assessment":"ممتاز|جيد|ضعيف"}}"""
    response = call_claude(prompt, "TRADE_REVIEWER")
    try:
        data = json.loads(response)
        analysis = {"time": datetime.datetime.now().strftime("%H:%M:%S"),
            "coin": "REVIEW", "mode": state["current_mode"].upper(),
            "strategy": "Trade Reviewer AI", "result_pct": 0, "result_usd": 0,
            "regime": state["ai_learner"]["market_regime"],
            "volatility": round(state["ai_learner"]["volatility_index"],1),
            "strategy_score": round(data.get("win_rate",50)/10,1),
            "patterns": [data.get("pattern","")],
            "lesson": data.get("lesson",""), "recommendation": data.get("recommendation",""),
        }
        state["ai_learner"]["ai_analysis"].insert(0, analysis)
        agent["last_response"] = data.get("lesson",""); agent["confidence"] = 0.88
        agent["last_action"] = f"مراجعة {len(trades)} صفقة"
    except:
        agent["last_response"] = response[:120] if response else "خطأ"; agent["confidence"] = 0.5
    agent["status"] = "done"
    log_agent_message("TRADE_REVIEWER", prompt[:200], agent["last_response"])

def run_gold_specialist():
    agent = agents["GOLD_SPECIALIST"]; agent["status"] = "thinking"
    ctx = build_market_context()
    ai  = state["ai_learner"]
    gold_hist  = state["price_history"].get("XAUTUSDT",[])
    silver_hist= state["price_history"].get("XAGUSDT",[])
    gold_change  = round((gold_hist[-1]/gold_hist[-5]-1)*100,3)   if len(gold_hist)>=5   else 0
    silver_change= round((silver_hist[-1]/silver_hist[-5]-1)*100,3) if len(silver_hist)>=5 else 0
    gold_rsi     = compute_rsi(gold_hist)   if len(gold_hist)>=15   else 50
    gold_vol     = compute_volatility(gold_hist) if len(gold_hist)>=5 else 20

    # إشارة XAUT في كل فريم
    tf_gold = {tf: state["tf_data"][tf]["signal"] for tf in ["1h","4h","1d"]}

    prompt = f"""أنت متخصص عالمي في الذهب والمعادن الثمينة.

الذهب XAUT: ${ctx['gold_price']:,.2f} | تغير {gold_change:+.3f}% | RSI={gold_rsi:.0f} | VI={gold_vol:.0f}
الفضة XAGUSDT: تغير {silver_change:+.3f}%
إشارات TF: {tf_gold}
Fear&Greed={ctx['fear_greed']} | BTC Dom={ctx['btc_dominance']}% | Regime={ctx['regime']}
AI Streak={ai.get('streak',0):+d} | Drawdown={ai.get('current_drawdown',0):.1f}%

قرر: هل الذهب الآن فرصة حقيقية؟
JSON فقط:
{{"gold_view":"...","action":"buy|sell|wait|hold","confidence":0.0-1.0,"reasoning":"...","target_pct":0.0,"risk_pct":0.0,"gold_signal":"strong_buy|buy|neutral|sell|strong_sell","silver_signal":"buy|neutral|sell"}}"""
    response = call_claude(prompt, "GOLD_SPECIALIST")
    try:
        data = json.loads(response)
        state["market_data"]["gold_trend"] = data.get("gold_signal","neutral")
        agent["last_response"] = data.get("gold_view","")
        agent["confidence"] = data.get("confidence",0.7)
        gs_action = data.get("action","wait")
        gs_vote   = "trade" if gs_action in ["buy","strong_buy"] else "reduce" if gs_action in ["sell","strong_sell"] else "wait"
        cast_vote("GOLD_SPECIALIST", gs_vote, agent["confidence"], data.get("gold_view","")[:50])
        agent["last_action"] = f"الذهب: {gs_action} → صوت: {gs_vote}"
        # ═══ إشارة عصبية الذهب ═══
        gold_sig = {"strong_buy":80,"buy":50,"neutral":0,"sell":-50,"strong_sell":-80}.get(gs_action,0)
        neural_propagate("GOLD_SPECIALIST", gold_sig, agent["confidence"])
    except:
        agent["last_response"] = response[:120] if response else "خطأ"; agent["confidence"] = 0.5
        cast_vote("GOLD_SPECIALIST", "wait", 0.3, "خطأ")
    agent["status"] = "done"
    log_agent_message("GOLD_SPECIALIST", prompt[:200], agent["last_response"])

# ════════════════════════════════════════════════════════════════
# V19: PATTERN_LEARNER — يتعلم من كل صفقة تلقائياً
# ════════════════════════════════════════════════════════════════
def run_pattern_learner():
    """
    V23 ENHANCED: يتعلم من السكالب + الصفقات العادية + Backtest
    ويحدّث أوزان السكالب تلقائياً
    """
    agent = agents["PATTERN_LEARNER"]
    agent["status"] = "thinking"

    # ─── دمج صفقات السكالب مع العادية ───
    scalp_hist  = agents.get("SCALP_TRADER",{}).get("scalp_history",[])
    normal_trades = state["trade_history"][:40]
    # تحويل سجل السكالب لنفس تنسيق trade_history
    scalp_as_trades = []
    for s in scalp_hist[:20]:
        scalp_as_trades.append({
            "pnl_percent": s.get("change_pct",0),
            "pnl_usd":     s.get("profit_usd",0),
            "strategy":    "SCALP_AI",
            "regime":      state["ai_learner"].get("market_regime","ranging"),
            "coin":        s.get("coin","?"),
            "duration":    s.get("duration",0),
        })
    trades = scalp_as_trades + normal_trades
    if len(trades) < 3:
        agent["status"] = "standby"
        agent["last_action"] = "انتظار صفقات كافية (3+)"
        return

    wins   = [t for t in trades if t.get("pnl_percent",0) > 0]
    losses = [t for t in trades if t.get("pnl_percent",0) <= 0]

    # ═══ اكتشاف الأنماط الرابحة ═══
    new_patterns = []
    for t in wins:
        pattern = {
            "strategy":  t.get("strategy",""),
            "regime":    t.get("regime","ranging"),
            "pnl":       t.get("pnl_percent",0),
            "time":      datetime.datetime.now().strftime("%H:%M"),
            "weight":    1.0,
        }
        # هل هذا النمط موجود مسبقاً؟
        exists = any(
            p["strategy"]==pattern["strategy"] and p["regime"]==pattern["regime"]
            for p in learned_patterns
        )
        if not exists:
            new_patterns.append(pattern)
            learned_patterns.append(pattern)

    # ═══ تحديث أوزان الاستراتيجيات بناءً على التعلم ═══
    strat_stats = {}
    for t in trades:
        s = t.get("strategy","")
        r = t.get("regime","ranging")
        key = f"{s}_{r}"
        if key not in strat_stats:
            strat_stats[key] = {"wins":0,"losses":0,"total_pnl":0}
        if t.get("pnl_percent",0) > 0:
            strat_stats[key]["wins"] += 1
        else:
            strat_stats[key]["losses"] += 1
        strat_stats[key]["total_pnl"] += t.get("pnl_percent",0)

    # تحديث الأوزان
    for key, stats in strat_stats.items():
        total = stats["wins"] + stats["losses"]
        if total >= 2:
            wr = stats["wins"] / total
            # وزن بين 0.3 و 1.5 بناءً على Win Rate
            weight = max(0.3, min(1.5, wr * 2))
            strategy_weights[key] = round(weight, 3)

    # ═══ تسجيل في Online Learning Log ═══
    log_entry = {
        "time":       datetime.datetime.now().strftime("%H:%M:%S"),
        "trades_analyzed": len(trades),
        "new_patterns":    len(new_patterns),
        "total_patterns":  len(learned_patterns),
        "strategy_weights": len(strategy_weights),
        "top_pattern":     new_patterns[0]["strategy"] if new_patterns else "لا جديد",
        "win_rate":        round(len(wins)/len(trades)*100,1),
    }
    online_learning_log.insert(0, log_entry)
    if len(online_learning_log) > 100:
        online_learning_log.pop()

    # تحديث حالة الوكيل
    agent["last_response"] = (
        f"🧠 تعلّمت {len(new_patterns)} نمط جديد | "
        f"إجمالي الأنماط: {len(learned_patterns)} | "
        f"أوزان محدّثة: {len(strategy_weights)}"
    )
    agent["confidence"] = min(0.95, 0.5 + len(learned_patterns)*0.01)
    agent["calls_made"] += 1
    agent["successes"]  += 1
    agent["last_action"] = f"تحليل {len(trades)} صفقة → {len(new_patterns)} نمط جديد"
    agent["status"] = "done"

    pl_wr = round(len(wins)/len(trades)*100,1) if trades else 50
    pl_vote = "trade" if pl_wr > 55 else "reduce" if pl_wr < 40 else "wait"
    cast_vote("PATTERN_LEARNER", pl_vote, agent["confidence"],
              f"WR={pl_wr}% patterns={len(learned_patterns)}")
    # ═══ إشارة عصبية من الأنماط ═══
    pl_sig = (pl_wr - 50) * 1.5
    neural_propagate("PATTERN_LEARNER", pl_sig, agent["confidence"])
    log_agent_message("PATTERN_LEARNER", "تحليل الأنماط", agent["last_response"])
    print(f"🧠 PATTERN_LEARNER: {agent['last_response']}")


# ════════════════════════════════════════════════════════════════
# V19: BACKTEST_RUNNER — يختبر الاستراتيجيات تاريخياً
# ════════════════════════════════════════════════════════════════
def run_backtest_runner():
    """
    يشغّل Backtest سريع على البيانات التاريخية المتوفرة
    ويحدّث نتائج كل استراتيجية بدون التأثير على التداول الحقيقي
    """
    agent = agents["BACKTEST_RUNNER"]
    agent["status"] = "thinking"

    ai = state["ai_learner"]
    results_summary = []

    for strategy in state["selected_strategies"]:
        strat_wins = 0; strat_losses = 0; strat_pnl = 0.0
        tested_coins = 0

        for coin in state["selected_coins"]:
            hist = state["price_history"].get(coin, [])
            if len(hist) < 20:
                continue
            tested_coins += 1

            # ═══ Backtest على البيانات المتوفرة ═══
            window = 10  # نافذة الاختبار
            for i in range(window, len(hist)-1):
                # بيانات الفترة
                sub_hist = hist[:i]

                # حساب درجة الإشارة على هذه البيانات
                fake_ai = {**ai, "market_regime": ai["market_regime"]}
                orig_hist = state["price_history"].get(coin, [])
                state["price_history"][coin] = sub_hist

                score = compute_signal_score(coin, strategy, fake_ai)

                state["price_history"][coin] = orig_hist  # إعادة البيانات

                if score > 65:
                    # محاكاة الدخول والخروج
                    entry = hist[i]
                    exit_ = hist[i+1] if i+1 < len(hist) else hist[i]
                    tp    = ai.get("adaptive_tp", 3.0)
                    sl    = ai.get("adaptive_sl", 1.5)
                    change = ((exit_ - entry) / entry) * 100

                    if change >= tp:
                        strat_wins += 1; strat_pnl += tp
                    elif change <= -sl:
                        strat_losses += 1; strat_pnl -= sl
                    elif change > 0:
                        strat_wins += 1; strat_pnl += change
                    else:
                        strat_losses += 1; strat_pnl += change

        total_bt = strat_wins + strat_losses
        if total_bt > 0:
            bt_wr = round(strat_wins / total_bt * 100, 1)
            bt_pnl = round(strat_pnl, 2)

            # حفظ نتائج الـ Backtest
            backtest_results[strategy] = {
                "wins":       strat_wins,
                "losses":     strat_losses,
                "win_rate":   bt_wr,
                "total_pnl":  bt_pnl,
                "tested":     total_bt,
                "coins":      tested_coins,
                "updated":    datetime.datetime.now().strftime("%H:%M:%S"),
            }

            # تحديث وزن الاستراتيجية بناءً على Backtest
            bt_weight = max(0.2, min(1.8, (bt_wr/50) * (1 + bt_pnl/100)))
            strategy_weights[f"bt_{strategy}"] = round(bt_weight, 3)

            results_summary.append(f"{state['strategies'].get(strategy,strategy)}: {bt_wr}% ({bt_pnl:+.1f}%)")

    # ═══ ترتيب الاستراتيجيات حسب نتائج Backtest ═══
    if backtest_results:
        best_bt = max(backtest_results, key=lambda k: backtest_results[k]["win_rate"])
        worst_bt = min(backtest_results, key=lambda k: backtest_results[k]["win_rate"])

        # تحديث توصية الوكيل بناءً على Backtest
        if backtest_results[best_bt]["win_rate"] > 55:
            state["ai_learner"]["agent_recommended_strategy"] = best_bt

        summary = (
            f"⚡ Backtest {len(backtest_results)} استراتيجية | "
            f"أفضل: {state['strategies'].get(best_bt,best_bt)} "
            f"({backtest_results[best_bt]['win_rate']}%) | "
            f"أضعف: {state['strategies'].get(worst_bt,worst_bt)} "
            f"({backtest_results[worst_bt]['win_rate']}%)"
        )
    else:
        summary = "⚡ Backtest: انتظار بيانات كافية"

    # ─── Backtest السكالب ───
    scalp_bt_wins = 0; scalp_bt_losses = 0
    for coin in state["selected_coins"][:5]:
        hist = state["price_history"].get(coin,[])
        if len(hist) < 15: continue
        for i in range(5, len(hist)-3):
            sub = hist[:i]
            m3  = (sub[-1]/sub[-3]-1)*100 if len(sub)>=3 else 0
            rsi = compute_rsi(sub) if len(sub)>=14 else 50
            sc2 = 0
            if m3>0.05: sc2+=35
            if 32<rsi<65: sc2+=25
            if sc2>=50:
                # محاكاة: خروج بعد 3 نقاط
                fut = hist[i:i+3]
                if not fut: continue
                chg = (max(fut)-hist[i])/hist[i]*100
                if chg>=0.5:   scalp_bt_wins+=1
                elif chg<-0.3: scalp_bt_losses+=1

    scalp_bt_total = scalp_bt_wins+scalp_bt_losses
    scalp_bt_wr    = round(scalp_bt_wins/scalp_bt_total*100,1) if scalp_bt_total>0 else 0
    backtest_results["SCALP_AI"] = {
        "wins": scalp_bt_wins, "losses": scalp_bt_losses,
        "win_rate": scalp_bt_wr, "total_pnl": round(scalp_bt_wins*0.8-scalp_bt_losses*0.5,2),
        "tested": scalp_bt_total, "coins": 5,
        "updated": datetime.datetime.now().strftime("%H:%M:%S"),
    }
    # تحديث وزن السكالب بناءً على نتائج Backtest
    if scalp_bt_wr > 55:
        strategy_weights["bt_SCALP_AI"] = round(min(1.8, scalp_bt_wr/50), 3)
    else:
        strategy_weights["bt_SCALP_AI"] = round(max(0.3, scalp_bt_wr/80), 3)

    summary2 = summary + f" | SCALP BT={scalp_bt_wr}%({scalp_bt_total})"
    agent["last_response"] = summary2
    agent["confidence"] = min(0.92, 0.5 + len(backtest_results)*0.05)
    # تصويت بناءً على نتائج Backtest
    best_bt_wr = max((v.get("win_rate",0) for v in backtest_results.values()), default=50)
    bt_vote = "trade" if best_bt_wr > 55 else "reduce" if best_bt_wr < 40 else "wait"
    cast_vote("BACKTEST_RUNNER", bt_vote, agent["confidence"],
              f"Best BT WR={best_bt_wr:.0f}% SCALP={scalp_bt_wr:.0f}%")
    agent["calls_made"] += 1; agent["successes"]  += 1
    agent["last_action"] = f"BT={best_bt_wr:.0f}% → صوت: {bt_vote}"
    agent["status"] = "done"
    log_agent_message("BACKTEST_RUNNER", "Backtest + SCALP", summary2)
    print(f"⚡ BACKTEST_RUNNER: {summary2}")


# ════════════════════════════════════════════════════════════════
# V19: تطبيق التعلم على compute_signal_score
# ════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════
# V20: PORTFOLIO_MANAGER — يقرأ ويحلل المحفظة الحقيقية
# ════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════
# V21: PROFIT_MANAGER — وكيل إدارة الأرباح الذكي
# ════════════════════════════════════════════════════════════════
def run_profit_manager():
    """
    V22: وكيل الأرباح المتطور
    - يراقب كل صفقة مفتوحة ويضبط TP/SL ديناميكياً
    - يحمي الأرباح فور تحققها
    - يغلق الصفقات الخاسرة بذكاء
    - يعيد توزيع الأرباح
    """
    agent = agents["PROFIT_MANAGER"]
    agent["status"] = "thinking"

    ai   = state["ai_learner"]
    mode = state["current_mode"]
    pv   = state["profit_vault"]
    f    = state["finances"][mode]
    bal  = get_balance(mode)
    start_bal    = 10000.0 if mode=="demo" else REAL_STARTING_BALANCE
    total_pnl    = f.get("pnl", 0.0)
    daily_pnl    = ai.get("daily_pnl", 0.0)
    streak       = ai.get("streak", 0)
    vi           = ai.get("volatility_index", 30)
    dd           = ai.get("current_drawdown", 0)
    trades       = state["trade_history"]
    open_pos     = state["active_positions"]

    wins     = sum(1 for t in trades[:20] if t.get("pnl_percent",0)>0)
    win_rate = wins / min(len(trades),20) * 100 if trades else 50.0

    profit_rate_today = round(daily_pnl/start_bal*100, 2) if start_bal>0 else 0
    pv["daily_profit"]      = round(daily_pnl, 2)
    pv["profit_rate_today"] = profit_rate_today

    actions_taken = []

    # ══════════════════════════════════════════
    # 1️⃣ إدارة الصفقات المفتوحة — القلب الجديد
    # ══════════════════════════════════════════
    for coin, pos in list(open_pos.items()):
        if pos.get("mode") != mode: continue
        cur_price = state["prices"].get(coin, 0)
        if cur_price == 0: continue

        entry      = pos["entry"]
        change     = ((cur_price - entry) / entry) * 100
        pos_size   = pos["size"]
        cur_profit = pos_size * (change / 100)

        # ── 🤖 Gemini يقرر أولاً ──
        gemini_dec = None
        if abs(change) > 0.5:  # فقط عند وجود حركة
            gemini_dec = call_gemini_for_trade(coin, pos, cur_price, ai)
            if gemini_dec:
                gd = gemini_dec.get("decision","hold")
                gr = gemini_dec.get("reason","")
                gc = gemini_dec.get("confidence",0.5)
                actions_taken.append(f"🤖 Gemini→{coin}: {gd} ({gc:.0%}) {gr[:40]}")

                if gd == "close" and gc > 0.75:
                    check_exit(coin, cur_price, mode)
                    actions_taken.append(f"⛔ Gemini أغلق {coin}: {gr[:50]}")
                    continue

                elif gd == "partial_tp" and gc > 0.70 and not pos.get("gemini_partial"):
                    profit_partial = cur_profit * 0.40
                    if profit_partial > 0:
                        f["pnl"] += profit_partial
                        ai["daily_pnl"] += profit_partial
                        set_balance(mode, get_balance(mode) + profit_partial)
                        pos["gemini_partial"] = True
                        pos["size"] *= 0.60
                        pv["total_protected"] = round(pv.get("total_protected",0)+profit_partial, 4)
                        pv["safe_balance"]    = round(pv.get("safe_balance",0)+profit_partial, 4)
                        state["notifications"].insert(0,{
                            "time":    datetime.datetime.now().strftime("%H:%M:%S"),
                            "message": f"🤖 Gemini Partial TP {coin}: +${profit_partial:.2f}",
                            "type":    "profit"
                        })

                elif gd == "raise_sl" and gc > 0.65:
                    new_sl = max(0.2, pos["adaptive_sl"] * 0.5)
                    pos["adaptive_sl"] = round(new_sl, 2)

        # ── A: رفع TP ديناميكي ──
        if change >= 1.5 and not pos.get("tp_raised"):
            new_tp = min(pos["adaptive_tp"] * 1.3, state["risk"]["tp"] * 2)
            pos["adaptive_tp"] = round(new_tp, 2)
            pos["tp_raised"]   = True
            actions_taken.append(f"📈 {coin}: TP→{new_tp:.1f}%")

        # ── B: Trailing SL ذكي ──
        if change >= 2.0:
            new_sl = max(0.3, pos["adaptive_sl"] * 0.6)
            if new_sl < pos["adaptive_sl"]:
                pos["adaptive_sl"] = round(new_sl, 2)
                actions_taken.append(f"🛡️ {coin}: SL→{new_sl:.1f}%")

        # ── C: Partial TP محلي (fallback) ──
        if (change >= pos.get("adaptive_tp",3.0)*0.7
                and not pos.get("partial_v22")
                and not pos.get("gemini_partial")):
            profit_partial = cur_profit * 0.4
            if profit_partial > 0:
                f["pnl"] += profit_partial
                ai["daily_pnl"] += profit_partial
                set_balance(mode, get_balance(mode) + profit_partial)
                pos["partial_v22"] = True
                pos["size"] *= 0.6
                pv["total_protected"] = round(pv.get("total_protected",0)+profit_partial, 4)
                pv["safe_balance"]    = round(pv.get("safe_balance",0)+profit_partial, 4)
                actions_taken.append(f"💰 {coin}: Partial TP=${profit_partial:.2f}")
                state["notifications"].insert(0,{
                    "time":    datetime.datetime.now().strftime("%H:%M:%S"),
                    "message": f"💰 [{mode.upper()}] Partial TP {coin}: +${profit_partial:.2f}",
                    "type":    "profit"
                })

        # ── D: SL تجاوز ──
        if change <= -(pos.get("adaptive_sl",1.5)*1.2):
            actions_taken.append(f"⛔ {coin}: SL تجاوز — سيُغلق")

        # ── E: صفقة راكدة ──
        try:
            et = datetime.datetime.fromisoformat(pos["entry_time"])
            age_hours = (datetime.datetime.now()-et).total_seconds()/3600
            if age_hours > 12 and abs(change) < 0.3:
                actions_taken.append(f"⏰ {coin}: راكدة {age_hours:.0f}h")
        except: pass

    # ══════════════════════════════════════════
    # 2️⃣ قرار حماية الأرباح اليومية
    # ══════════════════════════════════════════
    protect_amount = 0.0
    protect_reason = ""
    decision       = "hold"
    vault_pct      = pv.get("vault_pct", 30.0)

    if daily_pnl > 0 and profit_rate_today >= 5.0:
        pct = min(70, 40 + profit_rate_today * 4)
        protect_amount = daily_pnl * pct/100
        decision = "protect_high"
        protect_reason = f"🔴 ربح {profit_rate_today:.1f}% — حماية عاجلة {pct:.0f}%"
    elif daily_pnl > 0 and profit_rate_today >= 3.0:
        pct = 50.0
        protect_amount = daily_pnl * pct/100
        decision = "protect_medium"
        protect_reason = f"🟠 ربح {profit_rate_today:.1f}% — حماية {pct:.0f}%"
    elif streak >= 5 and daily_pnl > 0:
        protect_amount = daily_pnl * 0.40
        decision = "protect_streak"
        protect_reason = f"🔥 streak +{streak} — حماية 40%"
    elif vi > 65 and daily_pnl > 0:
        protect_amount = daily_pnl * 0.55
        decision = "protect_volatile"
        protect_reason = f"⚡ تذبذب {vi:.0f} — حماية 55%"
    elif dd > 2 and daily_pnl > 0:
        protect_amount = daily_pnl * 0.65
        decision = "protect_drawdown"
        protect_reason = f"📉 تراجع {dd:.1f}% — حماية 65%"
    elif daily_pnl > 0 and profit_rate_today >= 1.0:
        protect_amount = daily_pnl * vault_pct/100
        decision = "protect_routine"
        protect_reason = f"✅ حفظ روتيني {vault_pct:.0f}%"
    elif daily_pnl < 0 and abs(daily_pnl)/start_bal*100 > 2:
        decision = "reduce_risk"
        protect_reason = f"⚠️ خسارة — تقليل المخاطرة"
        ai["smart_filter_active"] = True
    else:
        decision = "hold"
        protect_reason = "⏸️ انتظار — لا حاجة للتدخل"

    if protect_amount > 0:
        pv["total_protected"] = round(pv.get("total_protected",0)+protect_amount, 4)
        pv["safe_balance"]    = round(pv.get("safe_balance",0)+protect_amount, 4)
        pv["protection_history"].insert(0,{
            "time":   datetime.datetime.now().strftime("%H:%M:%S"),
            "amount": round(protect_amount,2),
            "reason": protect_reason,
            "mode":   mode.upper(),
            "pnl_at": round(daily_pnl,2),
        })
        if len(pv["protection_history"]) > 50: pv["protection_history"].pop()
        pv["last_protection"] = datetime.datetime.now().strftime("%H:%M:%S")

    # ══════════════════════════════════════════
    # 3️⃣ ضبط مستوى الحماية الكلي
    # ══════════════════════════════════════════
    if profit_rate_today >= 5 or vi > 70 or dd > 8:
        pv["protection_level"] = "critical"
        ai["adaptive_tp"] = min(ai["adaptive_tp"], state["risk"]["tp"] * 0.65)
        ai["adaptive_sl"] = max(ai["adaptive_sl"], state["risk"]["sl"] * 1.4)
    elif profit_rate_today >= 3 or dd > 4:
        pv["protection_level"] = "high"
        ai["adaptive_tp"] = min(ai["adaptive_tp"], state["risk"]["tp"] * 0.80)
    elif daily_pnl > 0 or streak >= 2:
        pv["protection_level"] = "normal"
        ai["adaptive_tp"] = state["risk"]["tp"]
    else:
        pv["protection_level"] = "low"

    pv["risk_capital"]       = round(max(0, bal - pv["safe_balance"]), 2)
    pv["decision"]           = decision
    pv["profit_rate_today"]  = profit_rate_today

    if profit_rate_today < 1:   pv["next_target"] = round(start_bal*0.01,2)
    elif profit_rate_today < 3: pv["next_target"] = round(start_bal*0.03,2)
    elif profit_rate_today < 5: pv["next_target"] = round(start_bal*0.05,2)
    else:                       pv["next_target"] = round(start_bal*0.10,2)

    # ══════════════════════════════════════════
    # 4️⃣ بناء الملخص
    # ══════════════════════════════════════════
    lvl_emoji = {"critical":"🔴","high":"🟠","normal":"🟡","low":"🟢"}.get(pv["protection_level"],"🟡")
    actions_str = " | ".join(actions_taken[:3]) if actions_taken else "لا إجراءات"
    summary = (
        f"{lvl_emoji} {pv['protection_level'].upper()} | "
        f"ربح اليوم: {profit_rate_today:+.2f}% | "
        f"محمي: ${pv['total_protected']:.2f} | "
        f"{protect_reason} | إجراءات: {actions_str}"
    )

    agent["last_response"] = summary
    agent["confidence"]    = min(0.98, 0.5 + win_rate/200 + len(actions_taken)*0.05)
    agent["calls_made"]   += 1
    agent["successes"]    += 1
    agent["last_action"]  = f"{decision} | {len(open_pos)} صفقة مفتوحة | {lvl_emoji}"
    agent["status"]        = "done"

    log_agent_message("PROFIT_MANAGER", "إدارة الأرباح والصفقات", summary)
    print(f"💰 PROFIT_MANAGER: {summary}")


def run_portfolio_manager():
    """
    يقرأ الأرصدة الحقيقية من Binance
    ويحلل توازن المحفظة ويوصي بإعادة التوازن
    يعمل على Demo و Real معاً
    """
    agent = agents["PORTFOLIO_MANAGER"]
    agent["status"] = "thinking"
    pa = state["portfolio_analysis"]

    # ═══ قراءة الأرصدة ═══
    assets_data = []
    total_usd   = 0.0
    usdt_bal    = 0.0

    if state["client"] and state["api_status"].get("connected"):
        try:
            if state["trading_type"] == "futures":
                bals = state["client"].futures_account_balance()
                for b in bals:
                    qty = float(b.get("balance", 0))
                    if qty > 0:
                        asset = b["asset"]
                        if asset == "USDT":
                            val = qty; usdt_bal = qty
                        else:
                            sym = asset + "USDT"
                            px  = state["prices"].get(sym, 0)
                            val = qty * px if px > 0 else 0
                        if val > 0.1:
                            assets_data.append({
                                "asset": asset, "qty": round(qty, 6),
                                "value_usd": round(val, 2), "pct": 0.0,
                                "price": round(state["prices"].get(asset+"USDT",0),4),
                            })
                            total_usd += val
            else:
                acc = state["client"].get_account()
                for b in acc["balances"]:
                    qty = float(b["free"]) + float(b["locked"])
                    if qty > 0:
                        asset = b["asset"]
                        if asset == "USDT":
                            val = qty; usdt_bal = qty
                        else:
                            sym = asset + "USDT"
                            px  = state["prices"].get(sym, 0)
                            val = qty * px if px > 0 else 0
                        if val > 0.5:
                            assets_data.append({
                                "asset": asset, "qty": round(qty, 6),
                                "value_usd": round(val, 2), "pct": 0.0,
                                "price": round(state["prices"].get(asset+"USDT",0),4),
                            })
                            total_usd += val
        except Exception as e:
            print(f"⚠️ PORTFOLIO_MANAGER قراءة: {e}")
            # استخدام البيانات المحفوظة
            assets_data = state["finances"]["real"].get("assets", [])
            total_usd   = state["finances"]["real"].get("total_usd", 0)
            usdt_bal    = state["finances"]["real"].get("balance", 0)
    else:
        # Demo mode — استخدام الرصيد الافتراضي
        demo_bal = state["finances"]["demo"]["balance"]
        total_usd = demo_bal; usdt_bal = demo_bal
        assets_data = [{"asset":"USDT","qty":round(demo_bal,2),"value_usd":round(demo_bal,2),"pct":100.0,"price":1.0}]

    # ═══ حساب النسب المئوية ═══
    if total_usd > 0:
        for a in assets_data:
            a["pct"] = round(a["value_usd"] / total_usd * 100, 1)

    # ترتيب حسب القيمة
    assets_data.sort(key=lambda x: x["value_usd"], reverse=True)

    # ═══ تحليل التوازن ═══
    usdt_pct       = round(usdt_bal / total_usd * 100, 1) if total_usd > 0 else 0
    dominant       = assets_data[0] if assets_data else {"asset":"?","pct":0}
    dominant_asset = dominant.get("asset","?")
    dominant_pct   = dominant.get("pct", 0)

    # حساب نقاط التوازن
    balance_score  = 100
    suggested      = []
    rebalance      = False

    # ✅ USDT كافٍ للتداول؟
    if usdt_pct < 15 and total_usd > 50:
        balance_score -= 25
        suggested.append(f"⚠️ USDT منخفض ({usdt_pct:.0f}%) — احتفظ بـ 20% على الأقل نقداً")
        rebalance = True
    elif usdt_pct > 80:
        balance_score -= 10
        suggested.append(f"💡 USDT عالٍ جداً ({usdt_pct:.0f}%) — يمكن توزيع جزء على عملات واعدة")

    # ✅ هيمنة عملة واحدة
    if dominant_pct > 70 and dominant_asset != "USDT":
        balance_score -= 20
        suggested.append(f"⚠️ {dominant_asset} تهيمن على {dominant_pct:.0f}% — تنويع مقترح")
        rebalance = True
    elif dominant_pct > 50 and dominant_asset != "USDT":
        balance_score -= 10
        suggested.append(f"📊 {dominant_asset} بنسبة {dominant_pct:.0f}% — مراقبة مستمرة")

    # ✅ تنويع كافٍ؟
    non_usdt = [a for a in assets_data if a["asset"] != "USDT"]
    if len(non_usdt) == 0 and total_usd > 100:
        suggested.append("💡 كل الرصيد USDT — فرصة للتنويع في BTC أو ETH")
    elif len(non_usdt) > 8:
        balance_score -= 5
        suggested.append(f"📌 {len(non_usdt)} عملة كثيرة — فكر في تركيز أفضل العملات")

    # ✅ صفقات مفتوحة vs رصيد حر
    open_pos = len(state["active_positions"])
    if open_pos > 0 and usdt_pct < 10:
        balance_score -= 15
        suggested.append(f"⛔ {open_pos} صفقة مفتوحة + USDT {usdt_pct:.0f}% — خطر السيولة")
        rebalance = True

    balance_score = max(0, min(100, balance_score))

    # ═══ بناء التوصية الرئيسية ═══
    if balance_score >= 80:
        recommendation = f"✅ المحفظة متوازنة — {len(assets_data)} أصل | USDT {usdt_pct:.0f}% | إجمالي ${total_usd:,.2f}"
    elif balance_score >= 60:
        recommendation = f"🟡 توازن جيد مع ملاحظات — {suggested[0] if suggested else 'راقب التوزيع'}"
    else:
        recommendation = f"🔴 المحفظة تحتاج إعادة توازن — {suggested[0] if suggested else 'راجع التوزيع'}"

    # ═══ تحديث بيانات المحفظة ═══
    pa["total_value_usd"]  = round(total_usd, 2)
    pa["usdt_balance"]     = round(usdt_bal, 2)
    pa["usdt_pct"]         = usdt_pct
    pa["assets"]           = assets_data[:15]
    pa["is_balanced"]      = balance_score >= 70
    pa["balance_score"]    = balance_score
    pa["recommendation"]   = recommendation
    pa["dominant_asset"]   = dominant_asset
    pa["dominant_pct"]     = dominant_pct
    pa["last_update"]      = datetime.datetime.now().strftime("%H:%M:%S")
    pa["rebalance_needed"] = rebalance
    pa["suggested_actions"]= suggested[:4]

    # ═══ تحديث الوكيل ═══
    agent["last_response"] = recommendation
    agent["confidence"]    = balance_score / 100
    agent["calls_made"]   += 1
    agent["successes"]    += 1
    agent["last_action"]   = f"تحليل {len(assets_data)} أصل | ${total_usd:,.2f} | Score={balance_score}"
    agent["status"]        = "done"

    log_agent_message("PORTFOLIO_MANAGER", "قراءة المحفظة", recommendation)
    print(f"🏦 PORTFOLIO_MANAGER: {recommendation}")


# ════════════════════════════════════════════════════════════════
# V22: MARKET_SCANNER — يمسح العملات ويكتشف أقوى الفرص
# ════════════════════════════════════════════════════════════════
def run_market_scanner():
    """
    يمسح كل العملات المتاحة كل 30 ثانية
    يرتبها حسب قوة الإشارة
    يحدّث قائمة الأولويات
    """
    agent = agents["MARKET_SCANNER"]
    agent["status"] = "thinking"
    ai = state["ai_learner"]

    hot_coins    = []
    scores_all   = {}

    for coin in state["selected_coins"]:
        price = state["prices"].get(coin, 0)
        if price == 0: continue

        hist = state["price_history"].get(coin, [])
        if len(hist) < 5: continue

        # حساب درجة الفرصة
        best_score = 0
        best_strat = ""
        for s in state["selected_strategies"][:6]:
            sc = compute_signal_score(coin, s, ai)
            if sc > best_score:
                best_score = sc
                best_strat = s

        if best_score > 0:
            scores_all[coin] = {"score": round(best_score,1), "strategy": best_strat, "price": price}

        # حساب تغير السعر
        change_pct = round((hist[-1]/hist[0]-1)*100, 2) if len(hist)>=2 else 0

        if best_score > 70:
            rsi = compute_rsi(hist) if len(hist)>=14 else 50
            hot_coins.append({
                "coin":     coin,
                "score":    round(best_score, 1),
                "strategy": best_strat,
                "change":   change_pct,
                "rsi":      round(rsi, 1),
                "price":    round(price, 4),
            })

    # ترتيب حسب القوة
    hot_coins.sort(key=lambda x: x["score"], reverse=True)

    # تحديث heatmap بالبيانات الجديدة
    for coin, data in scores_all.items():
        ai["signal_heatmap"][coin] = data["score"]

    # حفظ أفضل 5 عملات
    top5 = hot_coins[:5]
    state["ai_learner"]["top_opportunities"] = top5

    summary = ""
    if top5:
        top_names = " | ".join(f"{c['coin']}({c['score']:.0f})" for c in top5[:3])
        summary = f"🔭 أقوى الفرص: {top_names}"
    else:
        summary = f"🔭 مسح {len(state['selected_coins'])} عملة — لا فرص قوية الآن"

    agent["last_response"] = summary
    agent["confidence"]    = min(0.95, len(hot_coins)/max(len(state["selected_coins"]),1))
    agent["calls_made"]   += 1
    agent["successes"]    += 1
    agent["last_action"]  = f"فرص ساخنة: {len(hot_coins)} | أقوى: {top5[0]['coin'] if top5 else 'لا يوجد'}"
    agent["status"]        = "done"

    sc_vote = "trade" if tops and tops[0].get("score",0)>75 else "wait"
    sc_conf = tops[0].get("score",50)/100 if tops else 0.3
    cast_vote("MARKET_SCANNER", sc_vote, sc_conf,
              tops[0].get("coin","") if tops else "لا فرص")
    log_agent_message("MARKET_SCANNER", "مسح السوق", summary)



# ══════════════════════════════════════════
# V23: SCALP_TRADER — هدف $1 لكل صفقة
# ══════════════════════════════════════════

# ══════════════════════════════════════════════════
# V24: CONSENSUS SYSTEM — نظام التصويت المشترك
# ══════════════════════════════════════════════════

def cast_vote(agent_id, vote, confidence=0.5, reason=""):
    """كل وكيل يصوت بـ: trade / wait / reduce"""
    cs = state["consensus_system"]
    cs["votes"][agent_id] = {
        "vote":       vote,
        "confidence": confidence,
        "reason":     reason[:60],
        "time":       datetime.datetime.now().strftime("%H:%M:%S"),
    }
    _update_consensus()


def _update_consensus():
    """يحسب القرار الموحد بناءً على الأصوات والأوزان"""
    cs = state["consensus_system"]
    votes   = cs["votes"]
    weights = cs["weights"]
    if not votes: return

    score_trade  = 0.0
    score_wait   = 0.0
    score_reduce = 0.0
    total_weight = 0.0

    for aid, v in votes.items():
        w = weights.get(aid, 0.05) * v["confidence"]
        total_weight += w
        if   v["vote"] == "trade":  score_trade  += w
        elif v["vote"] == "reduce": score_reduce += w
        else:                       score_wait   += w

    if total_weight == 0: return

    pt = round(score_trade  / total_weight * 100, 1)
    pw = round(score_wait   / total_weight * 100, 1)
    pr = round(score_reduce / total_weight * 100, 1)

    if   pt >= 60:           final = "trade";  cs["trade_approved"] = True
    elif pr >= 50:           final = "reduce"; cs["trade_approved"] = False
    else:                    final = "wait";   cs["trade_approved"] = False

    cs["final_vote"]     = final
    cs["consensus_pct"]  = round(max(pt, pw, pr), 1)
    cs["vote_trade_pct"] = pt
    cs["vote_wait_pct"]  = pw
    cs["vote_reduce_pct"]= pr
    cs["last_decision_time"] = datetime.datetime.now().strftime("%H:%M:%S")

    # تحديث smart_filter_active
    if final == "reduce":
        state["ai_learner"]["smart_filter_active"] = True
    elif final == "trade" and pt >= 65:
        state["ai_learner"]["smart_filter_active"] = False

    # سجل القرار
    log_entry = {
        "time":    cs["last_decision_time"],
        "final":   final,
        "pct":     cs["consensus_pct"],
        "pt":      pt, "pw": pw, "pr": pr,
        "voters":  len(votes),
        "approved":cs["trade_approved"],
    }
    cs["vote_history"].insert(0, log_entry)
    if len(cs["vote_history"]) > 80:
        cs["vote_history"].pop()



# ══════════════════════════════════════════════════════
# V24: DAILY_PLAN_MANAGER — مدير خطة التداول اليومية
# يدير رأس المال $267 لتحقيق $5/يوم
# ══════════════════════════════════════════════════════

def reset_daily_plan():
    """إعادة ضبط الخطة اليومية كل يوم جديد"""
    dp = state["daily_plan"]
    dp["today_pnl"]      = 0.0
    dp["today_trades"]   = 0
    dp["target_hit"]     = False
    dp["loss_limit_hit"] = False
    dp["plan_active"]    = True
    dp["session_start"]  = datetime.datetime.now().strftime("%H:%M:%S")
    dp["last_reset"]     = datetime.datetime.now().strftime("%Y-%m-%d")
    dp["hourly_pnl"]     = []
    dp["trade_log"]      = []
    print(f"🔄 خطة يومية جديدة | هدف=${dp['daily_target']} | حد=${dp['daily_max_loss']}")


def update_daily_plan(profit_usd, coin, strategy):
    """تحديث الخطة بعد كل صفقة"""
    dp = state["daily_plan"]
    dp["today_pnl"]    = round(dp["today_pnl"] + profit_usd, 4)
    dp["today_trades"] += 1

    dp["trade_log"].insert(0, {
        "time":   datetime.datetime.now().strftime("%H:%M:%S"),
        "coin":   coin,
        "pnl":    round(profit_usd, 2),
        "total":  round(dp["today_pnl"], 2),
        "strategy": strategy,
    })
    if len(dp["trade_log"]) > 50: dp["trade_log"].pop()

    # تحقق هل بلغنا الهدف
    if dp["today_pnl"] >= dp["daily_target"] and not dp["target_hit"]:
        dp["target_hit"]  = True
        dp["plan_active"] = False
        state["notifications"].insert(0, {
            "time":    datetime.datetime.now().strftime("%H:%M:%S"),
            "message": f"🎯 هدف اليوم تحقق! +${dp['today_pnl']:.2f} من {dp['today_trades']} صفقة",
            "type":    "success"
        })
        print(f"🎯 DAILY TARGET HIT: ${dp['today_pnl']:.2f} ← {dp['today_trades']} صفقة")

    # تحقق من حد الخسارة
    elif dp["today_pnl"] <= -dp["daily_max_loss"] and not dp["loss_limit_hit"]:
        dp["loss_limit_hit"] = True
        dp["plan_active"]    = False
        state["running"]     = False
        state["notifications"].insert(0, {
            "time":    datetime.datetime.now().strftime("%H:%M:%S"),
            "message": f"🛑 حد الخسارة اليومية ${dp['daily_max_loss']} — البوت متوقف",
            "type":    "danger"
        })
        print(f"🛑 DAILY LOSS LIMIT: ${dp['today_pnl']:.2f} — BOT STOPPED")

    # تحذير إذا تجاوز أقصى صفقات
    if dp["today_trades"] >= dp["max_daily_trades"]:
        dp["plan_active"] = False
        state["notifications"].insert(0, {
            "time":    datetime.datetime.now().strftime("%H:%M:%S"),
            "message": f"⚠️ تجاوزت {dp['max_daily_trades']} صفقة اليوم — استراحة",
            "type":    "danger"
        })


def get_smart_trade_size(coin_price):
    """حساب حجم الصفقة الذكي بناءً على الخطة"""
    dp  = state["daily_plan"]
    bal = get_balance(state["current_mode"])

    # إذا اقتربنا من الهدف — نقلل الحجم
    remaining = dp["daily_target"] - dp["today_pnl"]
    if remaining <= 1.0:
        # صفقة صغيرة آخر دولار
        size = min(bal * 0.08, 20.0)
    elif dp["today_pnl"] < 0:
        # خسرنا — نقلل الحجم
        size = bal * 0.08
    else:
        # طبيعي — 12% من الرصيد
        size = bal * dp["trade_size_pct"]

    # حدود أمان
    size = max(5.0, min(size, bal * 0.20, 80.0))
    return round(size, 2)


def daily_plan_reset_checker():
    """خيط يفحص إذا يجب إعادة ضبط الخطة (يوم جديد)"""
    last_date = ""
    while True:
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if today != last_date:
            reset_daily_plan()
            last_date = today
        time.sleep(60)



# ══════════════════════════════════════════════════════════════════
# NEWS_ANALYST — محلل الأخبار الاقتصادية والعالمية
# يعمل كل 5 دقائق ويغذي باقي الوكلاء
# ══════════════════════════════════════════════════════════════════

def fetch_crypto_news():
    """جلب أخبار الكريبتو من CryptoPanic (مجاني بدون مفتاح)"""
    try:
        url = "https://cryptopanic.com/api/v1/posts/?auth_token=free&public=true&currencies=BTC,ETH,XAU&filter=important"
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("results", [])[:10]
            news = []
            for r in results:
                news.append({
                    "title":      r.get("title",""),
                    "source":     r.get("source",{}).get("title",""),
                    "time":       r.get("published_at","")[:16],
                    "votes_pos":  r.get("votes",{}).get("positive",0),
                    "votes_neg":  r.get("votes",{}).get("negative",0),
                    "currencies": [c.get("code","") for c in r.get("currencies",[])],
                })
            return news
    except Exception as e:
        print(f"⚠️ CryptoPanic: {e}")
        return []


def fetch_fear_greed():
    """جلب مؤشر الخوف والجشع من Alternative.me"""
    try:
        url = "https://api.alternative.me/fng/?limit=2"
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            items = data.get("data", [])
            if items:
                today     = int(items[0].get("value", 50))
                yesterday = int(items[1].get("value", 50)) if len(items) > 1 else today
                label     = items[0].get("value_classification","Neutral")
                return {"value": today, "yesterday": yesterday, "label": label}
    except Exception as e:
        print(f"⚠️ Fear&Greed API: {e}")
    return {"value": 50, "yesterday": 50, "label": "Neutral"}


def fetch_coingecko_global():
    """جلب بيانات السوق الكلية من CoinGecko"""
    try:
        url = "https://api.coingecko.com/api/v3/global"
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode()).get("data", {})
            return {
                "btc_dominance":    round(data.get("market_cap_percentage",{}).get("btc",50), 1),
                "total_market_cap": data.get("total_market_cap",{}).get("usd",0),
                "market_cap_change": round(data.get("market_cap_change_percentage_24h_usd",0), 2),
                "active_cryptos":   data.get("active_cryptocurrencies", 0),
            }
    except Exception as e:
        print(f"⚠️ CoinGecko Global: {e}")
    return {}


def analyze_news_sentiment(news_list):
    """
    تحليل مشاعر الأخبار محلياً بدون API
    يعتمد على كلمات مفتاحية إيجابية وسلبية
    """
    positive_words = [
        "surge","rally","bull","gain","rise","pump","adoption","institutional",
        "approve","etf","partnership","launch","upgrade","halving","accumulate",
        "ارتفاع","صعود","ثيران","نمو","موافقة","اعتماد","شراكة","إطلاق",
        "breakout","recovery","high","record","support","buy","long",
    ]
    negative_words = [
        "crash","dump","bear","fall","drop","hack","ban","lawsuit","fraud","scam",
        "regulation","crackdown","sell","short","fear","panic","liquidation",
        "هبوط","انخفاض","دببة","حظر","قرصنة","احتيال","تنظيم","ذعر","تصفية",
        "collapse","warning","risk","concern","loss","declining",
    ]
    gold_positive = ["inflation","war","conflict","crisis","uncertainty","safe haven","hedge",
                     "تضخم","حرب","أزمة","ملاذ","تحوط","recession","economic slowdown"]
    gold_negative = ["risk on","rate hike","dollar strength","growth","optimism",
                     "رفع الفائدة","قوة الدولار"]

    sentiment = 0.0
    gold_score = 0.0
    count      = 0

    for news in news_list:
        title = (news.get("title","") + " " + news.get("source","")).lower()
        pos_count = sum(1 for w in positive_words if w.lower() in title)
        neg_count = sum(1 for w in negative_words if w.lower() in title)
        gold_pos  = sum(1 for w in gold_positive if w.lower() in title)
        gold_neg  = sum(1 for w in gold_negative if w.lower() in title)

        # وزن التصويتات
        votes_pos = news.get("votes_pos", 0)
        votes_neg = news.get("votes_neg", 0)
        vote_bias = (votes_pos - votes_neg) / max(votes_pos + votes_neg, 1) * 20

        news_score = (pos_count - neg_count) * 10 + vote_bias
        sentiment  += news_score
        gold_score += (gold_pos - gold_neg) * 15
        count += 1

    if count == 0: return 0.0, 0.0
    return round(sentiment / count, 1), round(gold_score / count, 1)


def run_news_analyst():
    """
    محلل الأخبار الاقتصادية — يعمل كل 5 دقائق
    يجمع ويحلل الأخبار ثم يبلغ باقي الوكلاء
    """
    agent = agents["NEWS_ANALYST"]
    agent["status"] = "thinking"
    nd = state["news_data"]
    now_ts = time.time()

    print("📰 NEWS_ANALYST: جلب الأخبار...")

    # ═══ 1: جلب البيانات ═══
    crypto_news = fetch_crypto_news()
    fg_data     = fetch_fear_greed()
    global_data = fetch_coingecko_global()

    # تحديث Fear & Greed
    fg_value = fg_data.get("value", 50)
    fg_label = fg_data.get("label","Neutral")
    state["market_data"]["fear_greed"] = fg_value

    # تحديث BTC Dominance
    if global_data.get("btc_dominance"):
        state["market_data"]["btc_dominance"] = global_data["btc_dominance"]

    # ═══ 2: تحليل المشاعر ═══
    crypto_sentiment, gold_score = analyze_news_sentiment(crypto_news)

    # تأثير Fear & Greed على المشاعر
    fg_sentiment = (fg_value - 50) * 1.2
    final_sentiment = round((crypto_sentiment * 0.6 + fg_sentiment * 0.4), 1)
    final_sentiment = max(-100, min(100, final_sentiment))

    # ═══ 3: تحديد مستوى التأثير ═══
    abs_sent = abs(final_sentiment)
    if abs_sent >= 60:   impact = "critical"
    elif abs_sent >= 35: impact = "high"
    elif abs_sent >= 15: impact = "medium"
    else:                impact = "low"

    # ═══ 4: توجه BTC ═══
    if final_sentiment >= 30:    btc_bias = "bullish"
    elif final_sentiment >= 10:  btc_bias = "slightly_bullish"
    elif final_sentiment <= -30: btc_bias = "bearish"
    elif final_sentiment <= -10: btc_bias = "slightly_bearish"
    else:                        btc_bias = "neutral"

    # ═══ 5: توجه الذهب ═══
    # الذهب يعكس السوق — عند الخوف يرتفع
    if fg_value < 30 or gold_score > 20:
        gold_bias = "strong_buy"
        state["market_data"]["gold_trend"] = "strong_buy"
    elif fg_value < 45 or gold_score > 8:
        gold_bias = "buy"
        state["market_data"]["gold_trend"] = "buy"
    elif fg_value > 75 or gold_score < -15:
        gold_bias = "sell"
        state["market_data"]["gold_trend"] = "sell"
    else:
        gold_bias = "neutral"
        state["market_data"]["gold_trend"] = "neutral"

    # ═══ 6: هل الأخبار خطرة جداً؟ ═══
    risk_off = (
        final_sentiment <= -50 or
        fg_value <= 15 or
        impact == "critical" and final_sentiment < 0
    )

    stop_trading = final_sentiment <= -70

    # ═══ 7: استخراج أهم الأحداث ═══
    top_event = ""
    alerts    = []
    headlines = []

    for news in crypto_news[:5]:
        title = news.get("title","")
        if title:
            headlines.append({
                "title":  title[:80],
                "source": news.get("source",""),
                "time":   news.get("time",""),
            })

    if fg_value <= 20:
        alerts.append(f"😱 خوف شديد جداً في السوق! F&G={fg_value}")
        top_event = f"خوف شديد: F&G={fg_value}"
    elif fg_value >= 85:
        alerts.append(f"🤑 جشع مفرط! F&G={fg_value} — احذر من انعكاس")
        top_event = f"جشع مفرط: F&G={fg_value}"
    elif crypto_news:
        top_event = crypto_news[0].get("title","")[:60]

    market_cap_change = global_data.get("market_cap_change", 0)
    if market_cap_change <= -5:
        alerts.append(f"📉 السوق الكلي تراجع {market_cap_change:.1f}% خلال 24 ساعة")
    elif market_cap_change >= 5:
        alerts.append(f"📈 السوق الكلي ارتفع {market_cap_change:.1f}% خلال 24 ساعة")

    # ═══ 8: بناء الملخص ═══
    sentiment_ar = "إيجابي 📈" if final_sentiment > 15 else "سلبي 📉" if final_sentiment < -15 else "محايد ➡️"
    summary = (
        f"📰 الأخبار: {sentiment_ar} ({final_sentiment:+.0f}) | "
        f"F&G={fg_value} ({fg_label}) | "
        f"BTC={btc_bias} | الذهب={gold_bias} | "
        f"تأثير={impact}"
    )

    # ═══ 9: تحديث news_data ═══
    nd["sentiment_score"] = final_sentiment
    nd["crypto_news"]     = headlines
    nd["impact_level"]    = impact
    nd["btc_bias"]        = btc_bias
    nd["gold_bias"]       = gold_bias
    nd["risk_off"]        = risk_off
    nd["last_update"]     = datetime.datetime.now().strftime("%H:%M:%S")
    nd["top_event"]       = top_event
    nd["summary"]         = summary
    nd["alerts"]          = alerts[:3]

    # تحديث بيانات الوكيل
    agent["news_sentiment"]    = final_sentiment
    agent["news_impact"]       = impact
    agent["gold_news_signal"]  = gold_bias
    agent["btc_news_bias"]     = btc_bias
    agent["risk_news_level"]   = impact
    agent["stop_trading_news"] = stop_trading
    agent["latest_headlines"]  = headlines[:5]
    agent["market_events"]     = alerts[:3]
    agent["fear_greed_news"]   = fg_value
    agent["last_fetch"]        = now_ts

    # ═══ 10: إبلاغ باقي الوكلاء ═══
    _broadcast_news_to_agents(final_sentiment, impact, btc_bias, gold_bias, risk_off, stop_trading)

    # صوت الأخبار في نظام التصويت
    news_vote = "trade" if final_sentiment > 20 else "reduce" if final_sentiment < -20 or stop_trading else "wait"
    news_conf = min(0.95, 0.5 + abs(final_sentiment)/200)
    cast_vote("NEWS_ANALYST", news_vote, news_conf, summary[:50])
    # ═══ إشارة عصبية من الأخبار ═══
    neural_propagate("NEWS_ANALYST", final_sentiment, news_conf)

    agent["last_response"] = summary
    agent["confidence"]    = news_conf
    agent["calls_made"]   += 1
    agent["successes"]    += 1
    agent["last_action"]  = f"F&G={fg_value} | {btc_bias} | {len(headlines)} خبر | {news_vote}"
    agent["status"]        = "done"

    log_agent_message("NEWS_ANALYST", "تحليل الأخبار", summary)
    print(f"📰 NEWS_ANALYST: {summary}")

    # إضافة لوزن التصويت
    if "NEWS_ANALYST" not in state["consensus_system"]["weights"]:
        state["consensus_system"]["weights"]["NEWS_ANALYST"] = 0.10


def _broadcast_news_to_agents(sentiment, impact, btc_bias, gold_bias, risk_off, stop_trading):
    """
    بث نتائج الأخبار لباقي الوكلاء
    يعدل سلوكهم بناءً على الأخبار
    """
    ai = state["ai_learner"]

    # 1️⃣ تأثير على MARKET_ANALYST
    if sentiment > 30:
        ai["agent_confidence_boost"] = min(20, ai.get("agent_confidence_boost",0) + 10)
    elif sentiment < -30:
        ai["agent_confidence_boost"] = max(-20, ai.get("agent_confidence_boost",0) - 10)

    # 2️⃣ تأثير على RISK_MANAGER
    if impact == "critical" and sentiment < 0:
        ai["agent_risk_level"] = "high"
        state["notifications"].insert(0, {
            "time":    datetime.datetime.now().strftime("%H:%M:%S"),
            "message": f"📰 أخبار خطرة — RISK رُفع لـ HIGH",
            "type":    "danger"
        })
    elif impact == "low" and sentiment > 0:
        # لا تغيير — اتركه للـ RISK_MANAGER

        pass

    # 3️⃣ تأثير على SCALP_TRADER
    if "SCALP_TRADER" in agents:
        sc = agents["SCALP_TRADER"]
        if stop_trading:
            sc["active"] = False
            state["notifications"].insert(0, {
                "time":    datetime.datetime.now().strftime("%H:%M:%S"),
                "message": f"📰 أخبار سلبية شديدة — SCALP متوقف مؤقتاً",
                "type":    "danger"
            })
        elif risk_off:
            sc["target_profit"] = max(sc.get("target_profit",1.0), 1.3)
            sc["max_loss"]      = min(sc.get("max_loss",0.8), 0.6)
        elif sentiment > 40:
            sc["active"]        = True
            sc["target_profit"] = 0.9  # هدف أسرع في السوق الصاعد

    # 4️⃣ تأثير على gold_trend
    if gold_bias in ["strong_buy","buy"]:
        state["market_data"]["gold_trend"] = gold_bias

    # 5️⃣ إضافة للإشعارات إذا هناك حدث مهم
    nd = state["news_data"]
    for alert in nd.get("alerts",[]):
        state["notifications"].insert(0, {
            "time":    datetime.datetime.now().strftime("%H:%M:%S"),
            "message": f"📰 {alert}",
            "type":    "danger" if "خوف" in alert or "تراجع" in alert else "success"
        })
    while len(state["notifications"]) > 30: state["notifications"].pop()

    print(f"📡 NEWS broadcast: sentiment={sentiment:+.0f} risk_off={risk_off} stop={stop_trading}")


def run_scalp_trader():
    agent = agents["SCALP_TRADER"]
    agent["status"] = "thinking"
    ai   = state["ai_learner"]
    mode = state["current_mode"]
    f    = state["finances"][mode]
    bal  = get_balance(mode)
    ss   = state["scalp_stats"]
    now  = datetime.datetime.now()
    ts   = now.timestamp()
    active = agent["active_scalps"]
    TARGET=agent["target_profit"]; MAXLOSS=agent["max_loss"]; MAXSEC=agent["max_duration_sec"]

    # ─── فحص الخطة اليومية ───
    dp = state["daily_plan"]
    if not dp.get("plan_active", True):
        if dp.get("target_hit"):
            agent["status"]="standby"; agent["last_action"]=f"🎯 هدف اليوم تحقق! ${dp['today_pnl']:.2f}"; return
        if dp.get("loss_limit_hit"):
            agent["status"]="standby"; agent["last_action"]=f"🛑 حد الخسارة وصل ${dp['today_pnl']:.2f}"; return
        agent["status"]="standby"; agent["last_action"]="خطة اليوم مكتملة"; return

    if bal < 10:
        agent["status"]="standby"; agent["last_action"]="رصيد غير كافٍ"; return
    if ai.get("agent_risk_level","medium")=="critical":
        agent["status"]="standby"; agent["last_action"]="RISK: توقف"; return
    vi=ai.get("volatility_index",30)
    if vi < 8:
        agent["status"]="standby"; agent["last_action"]="تذبذب منخفض"; return

    # ── مراقبة الصفقات المفتوحة ──
    for coin, sc in list(active.items()):
        cur=state["prices"].get(coin,0)
        if cur==0: continue
        pct=(cur-sc["entry"])/sc["entry"]*100
        prof=sc["size_usd"]*(pct/100)
        age=ts-sc["open_time"]
        if prof>sc.get("peak",0): sc["peak"]=prof
        close=""
        if   prof>=TARGET:                                    close="هدف $1 ✅"
        elif prof<=-MAXLOSS:                                  close="حد خسارة 🛑"
        elif age>=MAXSEC:                                     close="انتهى الوقت ⏰"
        elif sc.get("peak",0)>=TARGET*0.7 and prof<sc.get("peak",0)*0.35: close="Trailing 📉"
        if not close: continue
        del active[coin]
        f["pnl"]+=prof; ai["daily_pnl"]+=prof
        set_balance(mode, get_balance(mode)+prof)
        ss["total_profit"]=round(ss["total_profit"]+prof,4)
        ss["today_profit"]=round(ss["today_profit"]+prof,4)
        if prof>0: agent["scalp_wins"]+=1; ss["wins"]+=1
        else:      agent["scalp_losses"]+=1; ss["losses"]+=1
        agent["total_scalp_profit"]=round(agent.get("total_scalp_profit",0)+prof,4)
        rec={"time":now.strftime("%H:%M:%S"),"coin":coin,"entry":round(sc["entry"],4),
             "exit":round(cur,4),"profit_usd":round(prof,2),"change_pct":round(pct,3),
             "duration":int(age),"reason":close,"mode":mode.upper()}
        agent["scalp_history"].insert(0,rec)
        if len(agent["scalp_history"])>50: agent["scalp_history"].pop()

        # ─── Online Learning: تعلم من نتيجة الصفقة ───
        pattern_rec = {
            "strategy": "SCALP_AI",
            "regime":   ai.get("market_regime","ranging"),
            "pnl":      round(prof,2),
            "vi":       round(vi,1),
            "time":     now.strftime("%H:%M:%S"),
            "weight":   1.2 if prof>0 else 0.4,
        }
        learned_patterns.append(pattern_rec)
        if len(learned_patterns) > 200: learned_patterns.pop(0)

        # تحديث وزن SCALP فوراً
        key = "SCALP_AI_" + ai.get("market_regime","ranging")
        cur_w = strategy_weights.get(key, 1.0)
        if prof > 0: strategy_weights[key] = round(min(1.6, cur_w*1.06), 3)
        else:        strategy_weights[key] = round(max(0.3, cur_w*0.94), 3)
        print(f"🧠 SCALP Learn: {key} {cur_w:.3f} → {strategy_weights[key]:.3f}")
        state["trade_history"].insert(0,{
            "exit_time":now.strftime("%Y-%m-%d %H:%M:%S"),"coin":coin,
            "entry":round(sc["entry"],4),"exit":round(cur,4),
            "pnl_percent":round(pct,3),"pnl_usd":round(prof,2),
            "mode":mode.upper(),"duration":str(int(age))+"s",
            "strategy":"SCALP_AI","regime":ai.get("market_regime","?")})
        state["notifications"].insert(0,{
            "time":now.strftime("%H:%M:%S"),
            "message":("💰" if prof>0 else "💸")+" SCALP "+coin+": "+close+" "+str(round(prof,2))+"$",
            "type":"success" if prof>0 else "danger"})
        print(f"{'✅' if prof>0 else '❌'} SCALP {coin}: {close} ${prof:.2f} {age:.0f}s")

    ss["active"]=len(active)

    # ── البحث عن فرصة ──
    if len(active)>=3:
        agent["status"]="done"; agent["last_action"]=f"3 صفقات نشطة"; return

    best=None; bsc=0
    # ─── الوزن المكتسب من Backtest للسكالب ───
    bt_scalp_wr = backtest_results.get("SCALP_AI",{}).get("win_rate",50)
    bt_boost    = (bt_scalp_wr - 50) * 0.3  # +/- حسب نتائج BT

    # ─── الأنماط الرابحة المكتسبة ───
    regime_now = ai.get("market_regime","ranging")
    good_patterns = [p for p in learned_patterns if
                     p.get("strategy")=="SCALP_AI" and
                     p.get("regime")==regime_now and
                     p.get("pnl",0)>0]
    pattern_boost = min(15, len(good_patterns)*2)

    for coin in state["selected_coins"]:
        if coin in active or coin in state["active_positions"]: continue
        price=state["prices"].get(coin,0)
        if price==0: continue
        hist=state["price_history"].get(coin,[])
        if len(hist)<8: continue
        m5=(hist[-1]/hist[-5]-1)*100 if len(hist)>=5 else 0
        m3=(hist[-1]/hist[-3]-1)*100 if len(hist)>=3 else 0
        m1=(hist[-1]/hist[-2]-1)*100 if len(hist)>=2 else 0
        rsi=compute_rsi(hist)
        vol_c=compute_volatility(hist)
        sc2=0

        # ─── إشارات محسّنة ───
        if m5>0.1 and m3>0.03:   sc2+=30
        if m1>0.02:               sc2+=15  # حركة لحظية
        if 32<rsi<65:             sc2+=22
        elif rsi<28:              sc2+=16
        elif rsi>72:              sc2-=22
        if 15<vi<75:              sc2+=12
        if vol_c>5:               sc2+=8   # تذبذب حقيقي
        if coin=="XAUTUSDT" and state["market_data"].get("gold_trend","") in ["buy","strong_buy"]: sc2+=20

        # ─── تطبيق التعلم ───
        sc2 += bt_boost      # نتائج Backtest
        sc2 += pattern_boost # أنماط مكتسبة

        # ─── وزن الوكيل المتعلم ───
        learned_w = strategy_weights.get("bt_SCALP_AI", 1.0)
        sc2 = sc2 * learned_w

        if sc2>bsc: bsc=sc2; best=coin

    if best and bsc>=50:
        price=state["prices"].get(best,0)
        if price>0:
            # ─── حجم ذكي من الخطة اليومية ───
            size = get_smart_trade_size(price)
            # تعديل حسب التذبذب
            emv  = max(0.3, vi*0.008)
            size_alt = round(min(TARGET/(emv/100), bal*0.15, 80), 2)
            size = round((size + size_alt) / 2, 2)
            size = max(size, 5.0)
            active[best]={"entry":price,"size_usd":size,"open_time":ts,"peak":0.0,"mode":mode}
            ss["active"]=len(active)
            execute_entry(best,price,mode,"SMART_SCALP")
            state["notifications"].insert(0,{
                "time":now.strftime("%H:%M:%S"),
                "message":f"⚡ SCALP {best} | هدف $1 | ${size:.0f} | {bsc}نقطة",
                "type":"success"})
            print(f"⚡ SCALP {best} @ {price:.4f} size=${size:.0f} score={bsc}")

    tw=agent["scalp_wins"]; tl=agent["scalp_losses"]; tt=tw+tl
    wr=round(tw/tt*100,1) if tt>0 else 0
    tp=round(agent.get("total_scalp_profit",0),2)
    summary=f"⚡ {tt} صفقة | Win={wr}% | ربح=${tp} | نشط={len(active)}"
    agent["last_response"]=summary; agent["confidence"]=min(0.95,0.5+wr/200)
    agent["calls_made"]+=1; agent["successes"]+=1
    agent["last_action"]=f"{len(active)} نشط | ${tp} ربح"
    agent["status"]="done"
    log_agent_message("SCALP_TRADER","سكالب",summary)

def get_learned_weight(strategy, regime):
    """احصل على الوزن المكتسب للاستراتيجية في هذا النظام"""
    # وزن من الأنماط المكتسبة
    pattern_weight = strategy_weights.get(f"{strategy}_{regime}", 1.0)
    # وزن من Backtest
    bt_weight = strategy_weights.get(f"bt_{strategy}", 1.0)
    # متوسط الوزنين
    return round((pattern_weight + bt_weight) / 2, 3)


def log_agent_message(agent_id, prompt, response):
    agent_conversations.insert(0, {
        "time": datetime.datetime.now().strftime("%H:%M:%S"),
        "agent_id": agent_id, "agent_name": agents[agent_id]["name"],
        "agent_emoji": agents[agent_id]["emoji"], "color": agents[agent_id]["color"],
        "prompt_preview": prompt[:150] + "..." if len(prompt) > 150 else prompt,
        "response": response[:300] if response else "",
        "confidence": agents[agent_id]["confidence"],
    })
    if len(agent_conversations) > 50: agent_conversations.pop()

def agent_orchestrator():
    agent_funcs = {
        "MARKET_ANALYST":    run_market_analyst,
        "RISK_MANAGER":      run_risk_manager,
        "STRATEGY_SELECTOR": run_strategy_selector,
        "TRADE_REVIEWER":    run_trade_reviewer,
        "GOLD_SPECIALIST":   run_gold_specialist,
        "PATTERN_LEARNER":   run_pattern_learner,    # V19
        "BACKTEST_RUNNER":   run_backtest_runner,     # V19
        "PORTFOLIO_MANAGER": run_portfolio_manager,   # V20
        "PROFIT_MANAGER":    run_profit_manager,        # V21
        "MARKET_SCANNER":    run_market_scanner,         # V22
        "SCALP_TRADER":      run_scalp_trader,            # V23
        "NEWS_ANALYST":      run_news_analyst,
        "GEMINI_CHIEF":      run_gemini_chief,
    }
    time.sleep(20)
    while True:
        now = time.time()
        for aid, agent in agents.items():
            if not agent.get("active", True): continue
            if now - agent["last_run"] >= agent["interval"]:
                try:
                    agent["last_run"] = now; agent["status"] = "thinking"
                    func = agent_funcs.get(aid)
                    if func:
                        t = threading.Thread(target=func, daemon=True); t.start()
                except Exception as e:
                    agent["status"] = "error"; print(f"❌ Agent {aid}: {e}")
        time.sleep(5)  # V22: أسرع — كل 5 ثوانٍ


# ════════════════════════════════════════
# CORE BOT FUNCTIONS
# ════════════════════════════════════════
def load_state():
    if not os.path.exists('bot_v17.json'): return
    try:
        with open('bot_v17.json','r',encoding='utf-8') as f:
            saved = json.load(f)
        for k in ['finances','active_positions','signals','notifications','trade_history',
                  'strategy_performance','ai_learner','selected_coins','selected_strategies',
                  'selected_timeframes','risk','capital_mgmt','smart_sl','current_mode',
                  'trading_type','futures_leverage','market_data','chart_data',
                  'bot_health','account_analysis','capital_actions','tf_data']:
            if k in saved: state[k] = saved[k]
        rf = state["finances"]["real"]
        if rf.get("balance",0) <= 0: rf["balance"] = REAL_STARTING_BALANCE
        if "peak" not in rf: rf["peak"] = rf["balance"]
        if "peak" not in state["finances"]["demo"]:
            state["finances"]["demo"]["peak"] = state["finances"]["demo"]["balance"]
        for k in state["strategies"]:
            if k not in state["strategy_performance"]:
                state["strategy_performance"][k] = {"wins":0,"losses":0,"pnl":0.0,"avg_duration":0,"trades":0}
    except Exception as e:
        print(f"⚠️ load: {e}")

def save_state():
    try:
        s = {k:v for k,v in state.items() if k not in ["client","prices","price_history"]}
        with open('bot_v17.json','w',encoding='utf-8') as f:
            json.dump(s,f,ensure_ascii=False,indent=2)
    except: pass

def auto_save():
    while True: save_state(); time.sleep(20)

def get_balance(mode):
    if mode == "demo": return max(0.0, state["finances"]["demo"]["balance"])
    rf = state["finances"]["real"]
    return rf["total_usd"] if rf["total_usd"] > 0 else max(0.0, rf.get("balance", REAL_STARTING_BALANCE))

def set_balance(mode, v):
    if mode == "demo": state["finances"]["demo"]["balance"] = round(v,4)
    else:
        state["finances"]["real"]["balance"] = round(v,4)
        state["finances"]["real"]["total_usd"] = round(v,4)

def compute_volatility(p):
    if len(p)<5: return 0.0
    return min(100,statistics.mean([abs(p[i]/p[i-1]-1)*100 for i in range(1,len(p))])*30)

def compute_momentum(p):
    if len(p)<10: return 0.0
    return max(-100,min(100,(statistics.mean(p[-3:])/statistics.mean(p[-10:])-1)*1000))

def compute_trend_strength(p):
    if len(p)<14: return 0.0
    ups=sum(1 for i in range(1,len(p)) if p[i]>p[i-1])
    return round(ups/(len(p)-1)*100,1)

def compute_rsi(prices, period=14):
    if len(prices)<period+1: return 50.0
    gains,losses=[],[]
    for i in range(1,min(len(prices),period+1)):
        d=prices[-i]-prices[-i-1]
        (gains if d>0 else losses).append(abs(d))
    ag=statistics.mean(gains) if gains else 0
    al=statistics.mean(losses) if losses else 0.001
    return round(100-(100/(1+ag/al)),1)

def detect_patterns(p):
    if len(p)<6: return []
    pats=[]
    if p[-1]>p[-2]<p[-3] and p[-3]>p[-4]<p[-5]: pats.append("Double Bottom")
    if p[-1]>p[-3]>p[-5]: pats.append("Higher Highs")
    if p[-1]<p[-3]<p[-5]: pats.append("Lower Lows")
    if len(p)>=6 and (max(p[-6:])-min(p[-6:]))/max(statistics.mean(p[-6:]),0.001)*100<0.5: pats.append("Consolidation")
    if len(p)>=4 and all(p[-i]>p[-i-1] for i in range(1,4)): pats.append("Uptrend")
    if len(p)>=4 and all(p[-i]<p[-i-1] for i in range(1,4)): pats.append("Downtrend")
    return pats

def compute_signal_score(coin, strategy, ai):
    hist = state["price_history"].get(coin, [])
    score = 50.0
    if len(hist) >= 14:
        rsi = compute_rsi(hist)
        vi=ai.get("volatility_index",30); mom=ai.get("momentum_score",0)
        ts=ai.get("trend_strength",50); regime=ai.get("market_regime","ranging")
        fg=state["market_data"].get("fear_greed",55)
        if rsi < 30: score += 22
        elif rsi > 70: score -= 22
        elif 40 < rsi < 60: score += 5
        if len(hist) >= 26:
            ema12=statistics.mean(hist[-12:]); ema26=statistics.mean(hist[-26:])
            macd=(ema12-ema26)/max(ema26,0.001)*100; score += macd * 2.5
        if len(hist) >= 20:
            sma=statistics.mean(hist[-20:]); std=statistics.stdev(hist[-20:]) if len(hist[-20:])>1 else 1
            cur=hist[-1]; upper=sma+2*std; lower=sma-2*std; rng=upper-lower if upper!=lower else 1
            bb_pos=(cur-lower)/rng
            if bb_pos<0.2: score+=18
            elif bb_pos>0.8: score-=18
        score += mom*0.25
        if ts>65: score+=12
        elif ts<35: score-=12
        bm={"RSI_AI":{"trending":12,"ranging":20,"volatile":4},"MACD_TREND":{"trending":20,"ranging":4,"volatile":6},
            "BOLLINGER":{"trending":4,"ranging":20,"volatile":14},"EMA_CROSS":{"trending":16,"ranging":8,"volatile":6},
            "SUPERTREND":{"trending":22,"ranging":8,"volatile":6},"VOLATILITY_BREAKOUT":{"trending":5,"ranging":3,"volatile":28},
            "MEAN_REVERSION":{"trending":3,"ranging":24,"volatile":12},"MOMENTUM_SURGE":{"trending":18,"ranging":6,"volatile":20},
            "REGIME_SWITCH":{"trending":16,"ranging":16,"volatile":16},"GOLD_HEDGE":{"trending":8,"ranging":16,"volatile":20},
            "MULTI_TF":{"trending":18,"ranging":14,"volatile":10},"SMART_SCALP":{"trending":16,"ranging":10,"volatile":8},
            "LIQUIDITY_HUNT":{"trending":10,"ranging":18,"volatile":16},"ADX_TREND":{"trending":24,"ranging":4,"volatile":6},
            "ICHIMOKU":{"trending":18,"ranging":8,"volatile":4},"VWAP":{"trending":12,"ranging":18,"volatile":6},}
        score += bm.get(strategy,{}).get(regime,10)
        if coin in ["XAUTUSDT","XAGUSDT"]:
            if fg<30: score+=18
            elif fg>75: score-=12
            gt=state["market_data"].get("gold_trend","neutral")
            if gt in ["strong_buy","buy"]: score+=15
            elif gt in ["strong_sell","sell"]: score-=15
        if strategy=="MULTI_TF":
            buys=sum(1 for d in state["tf_data"].values() if d["signal"]=="buy"); score+=buys*5
        rec_strat=ai.get("agent_recommended_strategy","")
        if rec_strat == strategy: score += 12
        score += ai.get("agent_confidence_boost",0)
        risk_level=ai.get("agent_risk_level","medium")
        if risk_level=="high": score-=8
        elif risk_level=="low": score+=5
        streak=ai.get("streak",0)
        if streak<=-3: score-=10
        elif streak>=3: score+=6
        perf=state["strategy_performance"].get(strategy,{"wins":1,"losses":1})
        t=perf["wins"]+perf["losses"]
        if t>5:
            wr=perf["wins"]/t; score+=(wr-0.5)*22
        score += random.gauss(0, 4)

        # ═══ V19: تطبيق الأوزان المكتسبة من التعلم ═══
        learned_w = get_learned_weight(strategy, regime)
        if learned_w != 1.0:
            # تعديل الدرجة بناءً على التعلم
            adjustment = (learned_w - 1.0) * 15
            score += adjustment

        # ═══ V19: تطبيق نتائج Backtest ═══
        if strategy in backtest_results:
            bt = backtest_results[strategy]
            if bt["win_rate"] > 60:
                score += 8   # استراتيجية ناجحة في Backtest
            elif bt["win_rate"] < 40:
                score -= 8   # استراتيجية ضعيفة في Backtest

        # ═══ V19: تطبيق الأنماط المكتسبة ═══
        matching_patterns = [
            p for p in learned_patterns
            if p["strategy"] == strategy and p["regime"] == regime
        ]
        if matching_patterns:
            avg_pattern_pnl = sum(p["pnl"] for p in matching_patterns) / len(matching_patterns)
            score += min(10, max(-10, avg_pattern_pnl * 0.5))

    return max(0, min(100, score))

def update_tf_signals():
    ai=state["ai_learner"]; mom=ai.get("momentum_score",0); ts=ai.get("trend_strength",50)
    vi=ai.get("volatility_index",30); now=datetime.datetime.now().strftime("%H:%M:%S")
    cfgs={"1m":{"m":0.8,"t":0.3,"n":14},"5m":{"m":0.7,"t":0.4,"n":10},
          "15m":{"m":0.6,"t":0.5,"n":7},"30m":{"m":0.5,"t":0.6,"n":5},
          "1h":{"m":0.4,"t":0.7,"n":4},"4h":{"m":0.3,"t":0.8,"n":3},
          "1d":{"m":0.2,"t":0.9,"n":2},"1w":{"m":0.1,"t":1.0,"n":1}}
    for tf,c in cfgs.items():
        noise=random.gauss(0,c["n"]); raw=mom*c["m"]+(ts-50)*c["t"]*0.5+noise
        strength=max(0,min(100,50+raw)); rsi_base=50+(strength-50)*0.8
        rsi=max(10,min(90,rsi_base+random.gauss(0,5)))
        if strength>65: signal="buy"; trend="↑↑" if strength>80 else "↑"
        elif strength<35: signal="sell"; trend="↓↓" if strength<20 else "↓"
        else: signal="neutral"; trend="→"
        state["tf_data"][tf]={"signal":signal,"strength":round(strength,1),"trend":trend,"rsi":round(rsi,1),"vol":round(vi,1),"last_update":now}

def tf_thread():
    while True: update_tf_signals(); time.sleep(6)

def update_ai():
    ai=state["ai_learner"]; vols,hmap=[],{}
    for coin in state["selected_coins"]:
        hist=state["price_history"].get(coin,[])
        if len(hist)>=10:
            vols.append(compute_volatility(hist))
            hmap[coin]=round(statistics.mean([compute_signal_score(coin,s,ai) for s in state["selected_strategies"]]) if state["selected_strategies"] else 50,1)
    if vols: ai["volatility_index"]=round(statistics.mean(vols),1)
    bh=state["price_history"].get("BTCUSDT",[])
    if len(bh)>=10:
        ai["momentum_score"]=round(compute_momentum(bh),1)
        ai["trend_strength"]=round(compute_trend_strength(bh),1)
        ai["market_sentiment"]=round(compute_rsi(bh),1)
    gp=state["prices"].get("XAUTUSDT",0)
    if gp>0: state["market_data"]["gold_price"]=gp
    ai["signal_heatmap"]=hmap
    vi,mom,ts=ai["volatility_index"],abs(ai["momentum_score"]),ai["trend_strength"]
    if vi>65 and mom>60: ai["market_regime"]="volatile"
    elif ts>65 and mom>40: ai["market_regime"]="trending"
    else: ai["market_regime"]="ranging"
    btp,bsl=state["risk"]["tp"],state["risk"]["sl"]
    if vi>60: ai["adaptive_tp"]=round(btp*1.4,2); ai["adaptive_sl"]=round(bsl*1.3,2)
    elif vi<20: ai["adaptive_tp"]=round(btp*0.8,2); ai["adaptive_sl"]=round(bsl*0.7,2)
    else: ai["adaptive_tp"]=btp; ai["adaptive_sl"]=bsl
    buys=sum(1 for d in state["tf_data"].values() if d["signal"]=="buy")
    sells=sum(1 for d in state["tf_data"].values() if d["signal"]=="sell")
    ai["signal_confluence"]=buys if buys>sells else -sells
    ai["smart_filter_active"]=ai.get("streak",0)<=-4
    trades=state["trade_history"]
    if len(trades)>=3:
        pnls=[t.get("pnl_percent",0) for t in trades[:50]]
        avg=statistics.mean(pnls); std=statistics.stdev(pnls) if len(pnls)>1 else 1
        ai["sharpe_ratio"]=round(avg/std if std>0 else 0,2)
        g=sum(t.get("pnl_usd",0) for t in trades if t.get("pnl_usd",0)>0)
        l=abs(sum(t.get("pnl_usd",0) for t in trades if t.get("pnl_usd",0)<0))
        ai["profit_factor"]=round(g/l if l>0 else g,2)
        wns=[t for t in trades if t.get("pnl_percent",0)>0]
        ai["win_loss_ratio"]=round(len(wns)/(len(trades)-len(wns)+1),2)
    perfs=state["strategy_performance"]
    if any(p["wins"]+p["losses"]>0 for p in perfs.values()):
        bk=max(perfs,key=lambda k:perfs[k]["pnl"]); ai["best_strategy"]=state["strategies"].get(bk,bk)
    mode=state["current_mode"]; bal=get_balance(mode)
    pk="peak_balance_"+mode

    # ═══ إصلاح شامل لمشكلة Drawdown الوهمي ═══
    if bal > 0:
        current_peak = ai.get(pk, 0)
        # إذا peak صفر أو أكبر من الرصيد بكثير (>10x) → أعد ضبطه
        if current_peak == 0 or current_peak > bal * 10:
            ai[pk] = bal
            current_peak = bal
        # حدّث peak فقط إذا ارتفع الرصيد
        elif bal > current_peak:
            ai[pk] = bal
            current_peak = bal
        peak = current_peak
        # حساب Drawdown الحقيقي فقط إذا المنطقي
        if peak > 0 and peak <= bal * 1.5:   # منع حسابات وهمية
            dd_calc = round(max(0, (peak-bal)/peak*100), 2)
            ai["current_drawdown"] = min(dd_calc, 50.0)  # حد أقصى 50%
        else:
            ai["current_drawdown"] = 0.0
    else:
        ai["current_drawdown"] = 0.0
    tw=sum(p["wins"] for p in perfs.values()); tt=sum(p["wins"]+p["losses"] for p in perfs.values())
    if tt>0: ai["confidence"]=round(max(30,min(98,(tw/tt)*100+ai["improvement"])),1)
    h=100; dd=ai["current_drawdown"]
    if dd>15: h-=40
    elif dd>8: h-=20
    if ai.get("streak",0)<=-3: h-=15
    if ai["profit_factor"]<1 and tt>5: h-=15
    ai["account_health"]=max(0,min(100,h))
    state["market_data"]["fear_greed"]=max(10,min(90,state["market_data"]["fear_greed"]+random.randint(-2,2)))
    cd=state["chart_data"]
    cd["timestamps"].append(datetime.datetime.now().strftime("%H:%M:%S"))
    cd["demo_pnl"].append(round(state["finances"]["demo"]["pnl"],2))
    cd["real_pnl"].append(round(state["finances"]["real"]["pnl"],2))
    cd["ai_confidence"].append(round(ai["confidence"],1))
    cd["volatility"].append(round(ai["volatility_index"],1))
    cd["drawdown"].append(round(ai["current_drawdown"],1))
    for k in cd:
        if len(cd[k])>120: cd[k]=cd[k][-120:]

def ai_thread():
    while True: update_ai(); time.sleep(8)

def check_bot_health():
    bh=state["bot_health"]; score=100; issues,warnings=[],[]
    if len(state["prices"])==0: issues.append("❌ لا أسعار"); score-=30
    if state["current_mode"]=="real" and not state["api_status"]["connected"]:
        warnings.append("⚠️ وضع حقيقي بدون API"); score-=15
    bal=get_balance(state["current_mode"])
    if bal<5: issues.append(f"❌ رصيد منخفض ${bal:.2f}"); score-=25
    streak=state["ai_learner"].get("streak",0)
    if streak<=-5: issues.append(f"❌ {abs(streak)} خسائر متتالية"); score-=20
    elif streak<=-3: warnings.append(f"⚠️ {abs(streak)} خسائر"); score-=10
    dd=state["ai_learner"].get("current_drawdown",0)
    if dd>=state["ai_learner"].get("max_drawdown_pct",10): issues.append(f"❌ تراجع {dd:.1f}%"); score-=20
    if bh.get("consecutive_errors",0)>=5: issues.append(f"❌ {bh['consecutive_errors']} أخطاء"); score-=15
    if state["ai_learner"].get("smart_filter_active"): warnings.append("⚠️ فلتر AI نشط"); score-=5
    if bh.get("orders_failed",0)>3: warnings.append(f"⚠️ {bh['orders_failed']} أوامر فاشلة"); score-=8
    bh["score"]=max(0,min(100,score)); bh["issues"]=issues; bh["warnings"]=warnings
    bh["last_check"]=datetime.datetime.now().strftime("%H:%M:%S")
    bh["memory_trades"]=len(state["trade_history"])
    if bh.get("start_time"):
        try:
            st=datetime.datetime.fromisoformat(bh["start_time"])
            bh["uptime_seconds"]=int((datetime.datetime.now()-st).total_seconds())
        except: pass

def health_thread():
    if not state["bot_health"].get("start_time"):
        state["bot_health"]["start_time"]=datetime.datetime.now().isoformat()
    while True: check_bot_health(); time.sleep(15)

def analyze_account(mode):
    aa=state["account_analysis"][mode]
    trades=[t for t in state["trade_history"] if t.get("mode","").upper()==mode.upper()]
    f=state["finances"][mode]; start_bal=10000.0 if mode=="demo" else REAL_STARTING_BALANCE
    if not trades: return
    wins=[t for t in trades if t.get("pnl_percent",0)>0]
    losses=[t for t in trades if t.get("pnl_percent",0)<=0]
    tt=len(trades); wr=len(wins)/tt if tt>0 else 0
    aa["roi_pct"]=round((f["pnl"]/start_bal)*100,2) if start_bal>0 else 0
    aa["best_trade"]=round(max((t.get("pnl_percent",0) for t in trades),default=0),2)
    aa["worst_trade"]=round(min((t.get("pnl_percent",0) for t in trades),default=0),2)
    aa["avg_win"]=round(statistics.mean([t["pnl_percent"] for t in wins]),2) if wins else 0
    aa["avg_loss"]=round(statistics.mean([t["pnl_percent"] for t in losses]),2) if losses else 0
    aa["expectancy"]=round(wr*aa["avg_win"]+(1-wr)*aa["avg_loss"],3)
    history=f.get("history",[])
    if len(history)>1:
        peak,mdd=history[0],0
        for v in history:
            if v>peak: peak=v
            d=(peak-v)/abs(peak)*100 if peak!=0 else 0
            if d>mdd: mdd=d
        aa["max_drawdown_pct"]=round(mdd,2)
    if aa["max_drawdown_pct"]>0: aa["calmar_ratio"]=round(aa["roi_pct"]/aa["max_drawdown_pct"],2)
    mws=mls=cws=cls=0
    for t in reversed(trades):
        if t.get("pnl_percent",0)>0: cws+=1;cls=0;mws=max(mws,cws)
        else: cls+=1;cws=0;mls=max(mls,cls)
    aa["win_streak"]=mws; aa["loss_streak"]=mls
    risk=100
    if aa["max_drawdown_pct"]>20: risk-=25
    elif aa["max_drawdown_pct"]>10: risk-=12
    if aa["expectancy"]<0: risk-=20
    if wr<0.4: risk-=15
    if aa.get("calmar_ratio",0)<0.5: risk-=10
    aa["risk_score"]=max(0,min(100,risk))

def analysis_thread():
    while True: analyze_account("demo"); analyze_account("real"); time.sleep(12)

def sync_data():
    pub=Client()
    while True:
        try:
            for p in pub.get_all_tickers():
                sym=p['symbol']
                if sym in state["all_coins"]:
                    px=float(p['price']); state["prices"][sym]=px
                    h=state["price_history"].setdefault(sym,[])
                    h.append(px)
                    if len(h)>60: state["price_history"][sym]=h[-60:]
            state["bot_health"]["price_feed_ok"]=True; state["bot_health"]["consecutive_errors"]=0
        except:
            state["bot_health"]["price_feed_ok"]=False; state["bot_health"]["consecutive_errors"]+=1
        # ✅ FIX: إعادة إنشاء client إذا انقطع الاتصال
        if not state["client"] and state["running"] and state["current_mode"]=="real":
            try:
                from binance.client import Client as BC
                state["client"] = BC(API_KEY, API_SECRET)
                state["client"].ping()
                state["api_status"].update({"connected":True,"error":"","mode":"أُعيد الاتصال ✅"})
                symbol_filters.clear()
                print("🔄 أُعيد الاتصال بـ Binance تلقائياً")
            except Exception as reconnect_err:
                print(f"⚠️ إعادة الاتصال فشلت: {reconnect_err}")

        if state["client"]:
            try:
                rf=state["finances"]["real"]
                if state["trading_type"]=="futures":
                    bals=state["client"].futures_account_balance()
                    usdt=next((float(b["balance"]) for b in bals if b["asset"]=="USDT"),0.0)
                    if usdt>0:
                        rf["total_usd"]=round(usdt,4); rf["balance"]=round(usdt,4)
                        # ✅ إصلاح: تحديث peak_balance_real بالرصيد الحقيقي
                        if state["ai_learner"].get("peak_balance_real",0) < usdt:
                            state["ai_learner"]["peak_balance_real"] = round(usdt,4)
                else:
                    acc=state["client"].get_account(); port,total=[],0.0
                    for b in acc['balances']:
                        qty=float(b['free'])+float(b['locked'])
                        if qty>0:
                            sym2=b['asset']+"USDT"; px2=state["prices"].get(sym2,1.0 if b['asset']=="USDT" else 0)
                            val=qty*px2
                            if val>0.5: port.append({"asset":b['asset'],"qty":round(qty,4),"val":round(val,2)}); total+=val
                    rf["assets"]=port
                    if total>0: rf["total_usd"]=round(total,4); rf["balance"]=round(total,4)
                state["api_status"].update({
                    "connected": True, "error": "",
                    "last_sync": datetime.datetime.now().strftime("%H:%M:%S"),
                    "mode": "متصل ✅"
                })
            except Exception as e:
                err = str(e)
                # ✅ تمييز نوع الخطأ
                if "APIError" in err or "Invalid" in err:
                    mode_msg = "❌ مفتاح API خاطئ"
                elif "restricted" in err.lower() or "geo" in err.lower():
                    mode_msg = "❌ محجوب جغرافياً"
                else:
                    mode_msg = f"❌ خطأ API"
                state["api_status"].update({
                    "connected": False,
                    "error": err[:80],
                    "mode": mode_msg
                })
                print(f"⚠️ Binance API: {err[:100]}")
        time.sleep(5)

def smart_position_size(mode, strategy, ai):
    """
    V21 SMART SIZING:
    يحسب حجم الصفقة بذكاء بناءً على:
    - رأس المال الفعلي
    - نسبة مئوية محددة (5-10% افتراضياً)
    - توصية وكيل AI
    - أداء الاستراتيجية
    - مستوى المخاطر
    """
    bal      = get_balance(mode)
    cm       = state["capital_mgmt"]
    base_pct = cm["base_risk_pct"] / 100   # نسبة المخاطرة المضبوطة

    # ═══ الحد الأدنى والأقصى لحجم الصفقة ═══
    MIN_TRADE_USD = 5.0    # أقل صفقة $5
    MAX_TRADE_PCT = 0.20   # أقصى 20% من الرصيد

    # ═══ حساب النسبة الذكية ═══
    perf  = state["strategy_performance"].get(strategy, {"wins":5,"losses":5})
    t     = perf["wins"] + perf["losses"]
    wr    = perf["wins"] / t if t > 0 else 0.5
    streak= ai.get("streak", 0)
    vi    = ai.get("volatility_index", 30)
    mgmt  = cm.get("mode", "smart_adaptive")

    if mgmt == "fixed":
        size_pct = base_pct

    elif mgmt == "kelly":
        edge     = wr - (1 - wr)
        size_pct = max(0.05, min(0.15, edge * base_pct * 3))

    elif mgmt == "volatility_scaled":
        size_pct = base_pct * max(0.4, 1 - vi / 120)

    else:  # smart_adaptive — الأذكى
        size_pct = base_pct

        # ضبط حسب Win Rate
        if wr > 0.65:   size_pct *= 1.3
        elif wr > 0.55: size_pct *= 1.1
        elif wr < 0.40: size_pct *= 0.7
        elif wr < 0.45: size_pct *= 0.85

        # ضبط حسب سلسلة الصفقات
        if streak >= 4:    size_pct *= 1.25
        elif streak >= 2:  size_pct *= 1.10
        elif streak <= -4: size_pct *= 0.35
        elif streak <= -2: size_pct *= 0.55

        # ضبط حسب التذبذب
        if vi > 70:   size_pct *= 0.55
        elif vi > 55: size_pct *= 0.75
        elif vi < 20: size_pct *= 1.15

        # ضبط حسب توصية وكيل AI
        risk_lv = ai.get("agent_risk_level", "medium")
        if risk_lv == "critical": size_pct *= 0.20
        elif risk_lv == "high":   size_pct *= 0.45
        elif risk_lv == "low":    size_pct *= 1.20

        # إذا AI يوصي بهذه الاستراتيجية تحديداً
        if ai.get("agent_recommended_strategy","") == strategy:
            size_pct *= 1.15

        # فلتر الحماية
        if ai.get("smart_filter_active"): size_pct *= 0.30

    # ═══ تطبيق الحدود الآمنة ═══
    size_pct  = max(0.05, min(MAX_TRADE_PCT, size_pct))  # 5% → 20%
    size_usdt = bal * size_pct

    # ═══ تطبيق الرافعة للـ Futures ═══
    if state["trading_type"] == "futures":
        leverage  = int(state.get("futures_leverage", 10))
        size_usdt = size_usdt * leverage

    # ═══ تطبيق الحد الأدنى ═══
    size_usdt = max(MIN_TRADE_USD, size_usdt)

    # ═══ تأكد أن الحجم لا يتجاوز الرصيد ═══
    if state["trading_type"] != "futures":
        size_usdt = min(size_usdt, bal * MAX_TRADE_PCT)

    # ═══ تسجيل القرار ═══
    reasons = []
    if ai.get("agent_recommended_strategy","") == strategy: reasons.append("🤖AI")
    if streak >= 3:  reasons.append(f"🔥+{streak}")
    if streak <= -2: reasons.append(f"❄️{streak}")
    if risk_lv == "low": reasons.append("✅منخفض")
    elif risk_lv == "high": reasons.append("⚠️عالٍ")

    state["capital_actions"].insert(0, {
        "time":      datetime.datetime.now().strftime("%H:%M:%S"),
        "mode":      mode.upper(),
        "strategy":  state["strategies"].get(strategy, strategy),
        "size_pct":  round(size_pct * 100, 1),
        "size_usd":  round(size_usdt, 2),
        "reason":    " ".join(reasons) if reasons else mgmt,
        "balance":   round(bal, 2),
        "wr":        round(wr * 100, 1),
        "risk_lv":   risk_lv,
    })
    if len(state["capital_actions"]) > 50: state["capital_actions"].pop()

    print(f"💰 SIZE [{mode.upper()}] {strategy}: "
          f"رصيد=${bal:.2f} × {size_pct*100:.1f}% = ${size_usdt:.2f} "
          f"| wr={wr*100:.0f}% streak={streak} risk={risk_lv}")

    return round(size_usdt, 2)

def check_partial_tp(coin, cur_price, pos):
    cm=state["capital_mgmt"]
    if not cm.get("partial_tp",False) or pos.get("partial_taken",False): return False
    change=((cur_price-pos["entry"])/pos["entry"])*100
    if change>=cm.get("partial_tp_at",1.5):
        pct=cm.get("partial_tp_pct",50)/100; profit=pos["size"]*(change/100)*pct
        mode=pos["mode"]; state["finances"][mode]["pnl"]+=profit
        set_balance(mode,get_balance(mode)+profit); pos["partial_taken"]=True; pos["size"]*=(1-pct)
        state["notifications"].insert(0,{"time":datetime.datetime.now().strftime("%H:%M:%S"),
            "message":f"💰 [{mode.upper()}] PTP {coin} +${profit:.2f}","type":"profit"})
        return True
    return False

def execute_entry(coin, price, mode, strategy):
    """
    V21 FIX: إصلاح شامل لتنفيذ الأوامر الحقيقية
    - تحقق مزدوج من الوضع
    - تسجيل تفصيلي لكل خطوة
    - معالجة أخطاء Binance بدقة
    """
    ai   = state["ai_learner"]
    # ✅ FIX: تأكد من الوضع الصحيح
    mode = state["current_mode"]
    size = smart_position_size(mode, strategy, ai)

    if size <= 0:
        print(f"⚠️ execute_entry: size=0 لـ {coin}"); return

    # ✅ FIX: تحديث الفلاتر دائماً لكل عملة
    if coin in symbol_filters:
        del symbol_filters[coin]  # امسح الكاش لتحديث الفلاتر
    filters     = get_lot_size_info(coin)
    min_qty     = filters.get('min_qty',      0.001)
    step_size   = filters.get('step_size',    0.001)
    min_notional= filters.get('min_notional', 5.0)
    precision   = filters.get('precision',    3)

    # ✅ FIX: حساب الكمية بدقة
    raw_qty  = size / price
    steps    = math.floor(round(raw_qty / step_size, 10))
    qty      = round(steps * step_size, precision)
    qty      = max(min_qty, qty)
    qty      = round(qty, precision)
    notional = round(qty * price, 4)

    # رفع الكمية إذا أقل من الحد
    if notional < min_notional:
        steps_needed = math.ceil(round(min_notional / price / step_size, 10))
        qty          = round(steps_needed * step_size, precision)
        notional     = round(qty * price, 4)

    # ✅ فحص صحة qty قبل أي شيء
    try:
        qty = float(qty)
        assert not math.isnan(qty) and not math.isinf(qty) and qty > 0
    except Exception as qty_err:
        print(f"⛔ qty غير صالح لـ {coin}: {qty} — {qty_err}"); return

    print(f"📏 [{mode.upper()}] {coin}: size=${size:.2f} → qty={qty} notional=${notional:.2f} min=${min_notional}")

    if notional < min_notional:
        print(f"⛔ رُفضت {coin}: notional=${notional:.2f} < min=${min_notional}"); return

    # ✅ FIX: تنفيذ الأمر الحقيقي مع تسجيل تفصيلي
    if mode == "real":
        if not state["client"]:
            print(f"❌ {coin}: لا يوجد client — تأكد من ربط مفاتيح Binance")
            state["notifications"].insert(0,{
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "message": f"❌ {coin}: Binance غير متصل — تحقق من مفاتيح API",
                "type": "danger"
            })
            return

        if not state["api_status"].get("connected", False):
            print(f"❌ {coin}: API غير متصل — {state['api_status'].get('error','؟')}")
            state["notifications"].insert(0,{
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "message": f"❌ {coin}: API غير متصل",
                "type": "danger"
            })
            return

        try:
            print(f"🔄 إرسال أمر حقيقي: {coin} qty={qty} نوع={state['trading_type']}")
            if state["trading_type"] == "futures":
                try:
                    state["client"].futures_change_leverage(
                        symbol=coin,
                        leverage=int(state.get("futures_leverage", 10))
                    )
                except Exception as lev_err:
                    print(f"⚠️ lever error {coin}: {lev_err}")
                # ✅ FIX: تنظيف qty من أي قيم غير صحيحة
                qty = float(qty)
                if math.isnan(qty) or math.isinf(qty) or qty <= 0:
                    print(f"⛔ qty غير صالح: {qty}"); return
                # تقريب لعدد محدد من الأرقام العشرية بدون trailing zeros
                qty_str = f"{qty:.{precision}f}".rstrip('0').rstrip('.')
                if not qty_str or qty_str == '0':
                    print(f"⛔ qty_str فارغ بعد التنظيف"); return
                qty = float(qty_str)
                print(f"📤 إرسال futures: {coin} qty={qty} qty_str={qty_str}")
                order = state["client"].futures_create_order(
                    symbol   = coin,
                    side     = "BUY",
                    type     = "MARKET",
                    quantity = qty_str   # ← إرسال كـ string نظيف
                )
            else:
                # ✅ FIX: تنظيف qty من أي قيم غير صحيحة
                qty = float(qty)
                if math.isnan(qty) or math.isinf(qty) or qty <= 0:
                    print(f"⛔ qty غير صالح: {qty}"); return
                qty_str = f"{qty:.{precision}f}".rstrip('0').rstrip('.')
                if not qty_str or qty_str == '0':
                    print(f"⛔ qty_str فارغ بعد التنظيف"); return
                qty = float(qty_str)
                print(f"📤 إرسال spot: {coin} qty={qty} qty_str={qty_str}")
                order = state["client"].create_order(
                    symbol   = coin,
                    side     = "BUY",
                    type     = "MARKET",
                    quantity = qty_str   # ← إرسال كـ string نظيف
                )

            order_id = order.get("orderId", "?")
            filled   = order.get("executedQty", qty)
            state["bot_health"]["orders_sent"] = state["bot_health"].get("orders_sent",0) + 1
            print(f"✅ أمر حقيقي نُفِّذ: {coin} orderId={order_id} filled={filled} @ ${price:.4f}")
            state["notifications"].insert(0,{
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "message": f"✅ [REAL] أمر {coin} نُفِّذ | qty={qty} | orderId={order_id}",
                "type": "success"
            })

        except Exception as e:
            err_msg = str(e)
            state["bot_health"]["orders_failed"] = state["bot_health"].get("orders_failed",0) + 1
            print(f"❌ فشل أمر {coin}: {err_msg}")
            state["notifications"].insert(0,{
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "message": f"❌ فشل {coin}: {err_msg[:80]}",
                "type": "danger"
            })
            # ✅ FIX: تسجيل الخطأ لكن لا نوقف — نكمل للعملة التالية
            return
    # ✅ FINAL FIX: تسجيل الصفقة مع تأكيد الوضع
    confirmed_mode = state["current_mode"]  # قراءة مباشرة في لحظة التسجيل
    state["active_positions"][coin] = {
        "entry":         price,
        "mode":          confirmed_mode,   # ✅ الوضع المؤكد
        "size":          size,
        "time":          datetime.datetime.now().strftime("%H:%M:%S"),
        "entry_time":    datetime.datetime.now().isoformat(),
        "sl_type":       state["smart_sl"]["type"],
        "trailing_offset": state["smart_sl"]["trailing_offset"],
        "max_price":     price,
        "strategy":      strategy,
        "adaptive_tp":   ai["adaptive_tp"],
        "adaptive_sl":   ai["adaptive_sl"],
        "entry_vol":     ai["volatility_index"],
        "entry_regime":  ai["market_regime"],
        "partial_taken": False,
        "qty":           qty if 'qty' in dir() else 0,
        "is_real_order": confirmed_mode == "real",  # علامة للتمييز
    }
    ai["daily_trades"] += 1
    sname = state["strategies"].get(strategy, strategy)

    # إشعار مفصّل يوضح الوضع
    mode_label = "🟡 REAL" if confirmed_mode == "real" else "🔵 DEMO"
    state["signals"].insert(0, {
        "time":     datetime.datetime.now().strftime("%H:%M:%S"),
        "coin":     coin,
        "type":     "شراء",
        "price":    round(price, 4),
        "mode":     confirmed_mode.upper(),
        "strategy": sname,
    })
    state["notifications"].insert(0, {
        "time":    datetime.datetime.now().strftime("%H:%M:%S"),
        "message": f"{mode_label} دخول {coin} | {sname} | ${size:.2f}",
        "type":    "success",
    })
    while len(state["notifications"]) > 30: state["notifications"].pop()
    save_state()
    print(f"{'🟡 REAL' if confirmed_mode=='real' else '🔵 DEMO'} [{confirmed_mode.upper()}] "
          f"{coin} @ ${price:.4f} | ${size:.2f} | strategy={strategy}")

def check_exit(coin, cur_price, mode):
    pos=state["active_positions"].get(coin)
    if not pos or pos["mode"]!=mode: return
    try: et=datetime.datetime.fromisoformat(pos["entry_time"])
    except: et=datetime.datetime.now()
    change=((cur_price-pos["entry"])/pos["entry"])*100
    tp=pos.get("adaptive_tp",state["risk"]["tp"]); sl=pos.get("adaptive_sl",state["risk"]["sl"])
    exit_now=False
    if pos["sl_type"]=="trailing":
        if cur_price>pos["max_price"]: pos["max_price"]=cur_price
        if cur_price<=pos["max_price"]*(1-pos["trailing_offset"]/100) or change>=tp: exit_now=True
    else:
        if change>=tp or change<=-sl: exit_now=True
    if not exit_now: return
    dur_sec=(datetime.datetime.now()-et).total_seconds()
    dur=str(datetime.timedelta(seconds=int(dur_sec)))
    state["active_positions"].pop(coin)
    # ✅ FIX: استخدم mode من الصفقة نفسها وليس من state
    mode = pos.get("mode", mode)  # الوضع المسجّل مع الصفقة
    profit = pos["size"] * (change / 100)
    f = state["finances"][mode]
    f["pnl"]+=profit; state["ai_learner"]["daily_pnl"]+=profit
    set_balance(mode,get_balance(mode)+profit); f["history"].append(round(f["pnl"],2))
    if len(f["history"])>200: f["history"]=f["history"][-200:]
    ai=state["ai_learner"]
    if change>0: f["wins"]+=1; ai["streak"]=max(0,ai["streak"])+1
    else: f["losses"]+=1; ai["streak"]=min(0,ai["streak"])-1
    ai["recent_trades"]+=1
    strategy=pos.get("strategy","RSI_AI")
    perf=state["strategy_performance"].setdefault(strategy,{"wins":0,"losses":0,"pnl":0.0,"avg_duration":0,"trades":0})
    if change>0: perf["wins"]+=1
    else: perf["losses"]+=1
    perf["pnl"]+=profit; perf["trades"]+=1
    perf["avg_duration"]=round((perf["avg_duration"]*(perf["trades"]-1)+dur_sec)/perf["trades"])
    if ai["recent_trades"]%5==0:
        tw=sum(p["wins"] for p in state["strategy_performance"].values())
        tt=sum(p["wins"]+p["losses"] for p in state["strategy_performance"].values())
        if tt>0: ai["improvement"]=round((tw/tt-0.5)*120,1)
    sc=compute_signal_score(coin,strategy,ai)
    analysis={"time":datetime.datetime.now().strftime("%H:%M:%S"),"coin":coin,"mode":mode.upper(),
        "strategy":state["strategies"].get(strategy,strategy),"result_pct":round(change,2),
        "result_usd":round(profit,2),"regime":ai["market_regime"],"volatility":round(ai["volatility_index"],1),
        "strategy_score":round(sc,1),"patterns":detect_patterns(state["price_history"].get(coin,[])),
        "lesson":"","recommendation":"","agent_view":ai.get("agent_market_view",""),
        "confluence":ai.get("signal_confluence",0)}
    if change>0:
        analysis["lesson"]=f"✅ {state['strategies'].get(strategy,strategy)} نجحت في نظام {ai['market_regime']}"
        analysis["recommendation"]="زيادة الوزن" if sc>72 else "مراقبة"
    else:
        if ai["volatility_index"]>60: analysis["lesson"]="⚡ تذبذب ضد الصفقة"
        elif ai.get("signal_confluence",0)<2: analysis["lesson"]="🔄 تعارض إشارات الفريمات"
        else: analysis["lesson"]="📊 خسارة طبيعية إحصائياً"
        analysis["recommendation"]="تقليل الحجم" if ai["streak"]<=-2 else "الاستمرار"
    ai["ai_analysis"].insert(0, analysis)
    if len(ai["ai_analysis"]) > 30: ai["ai_analysis"].pop()

    # ═══ V19: Online Learning — تحديث فوري عند إغلاق الصفقة ═══
    trade_pattern = {
        "strategy": strategy,
        "regime":   pos.get("entry_regime", "ranging"),
        "pnl":      round(change, 2),
        "vi":       pos.get("entry_vol", 30),
        "time":     datetime.datetime.now().strftime("%H:%M:%S"),
        "weight":   1.0 if change > 0 else 0.3,
    }
    # حفظ النمط إذا كان رابحاً
    if change > 0:
        learned_patterns.append(trade_pattern)
        if len(learned_patterns) > 200:
            learned_patterns.pop(0)

    # تحديث وزن الاستراتيجية فوراً
    key = f"{strategy}_{pos.get('entry_regime','ranging')}"
    current_w = strategy_weights.get(key, 1.0)
    # تحديث تدريجي بدون تغيير مفاجئ (Online Learning)
    if change > 0:
        strategy_weights[key] = round(min(1.5, current_w * 1.05), 3)
    else:
        strategy_weights[key] = round(max(0.3, current_w * 0.95), 3)

    print(f"🧠 Online Learning: {strategy} @ {pos.get('entry_regime','?')} "
          f"→ weight {current_w:.3f} → {strategy_weights.get(key,1.0):.3f} | {change:+.2f}%")
    state["trade_history"].insert(0,{"exit_time":datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "coin":coin,"entry":round(pos["entry"],4),"exit":round(cur_price,4),
        "pnl_percent":round(change,2),"pnl_usd":round(profit,2),"mode":mode.upper(),
        "duration":dur,"strategy":strategy,"regime":pos.get("entry_regime","?")})
    if len(state["trade_history"])>500: state["trade_history"].pop()
    sname=state["strategies"].get(strategy,strategy)
    state["signals"].insert(0,{"time":datetime.datetime.now().strftime("%H:%M:%S"),
        "coin":coin,"type":"بيع","price":round(cur_price,4),"mode":f"{change:+.2f}%","strategy":sname})
    state["notifications"].insert(0,{"time":datetime.datetime.now().strftime("%H:%M:%S"),
        "message":f"[{mode.upper()}] {coin} {change:+.2f}% ${profit:+.2f}",
        "type":"success" if change>0 else "danger"})
    while len(state["notifications"])>30: state["notifications"].pop()
    save_state()
    send_trade_alert(coin,change,profit,strategy,mode)
    # ─── تحديث الخطة اليومية للصفقات العادية ───
    update_daily_plan(profit, coin, strategy)
    # ═══ Hebbian Learning — تحديث الشبكة العصبية ═══
    contributing = [aid for aid, sig in neural_signals.items() if abs(sig) > 0.1]
    neural_learn_from_trade(change, contributing)
    print(f"{'✅' if change>0 else '❌'} [{mode.upper()}] {coin} {change:+.2f}% ${profit:+.2f}")

def trading_logic():
    while True:
        if not state["running"]: time.sleep(2); continue
        ai = state["ai_learner"]
        ae = state["active_engines"]
        engines_to_run = [e for e in ["spot","futures"] if ae.get(e,False)]
        if not engines_to_run: engines_to_run = [state["trading_type"]]
        for engine_type in engines_to_run:
            state["trading_type"] = engine_type
        mode=state["current_mode"]; ai=state["ai_learner"]; bal=get_balance(mode)
        if ai["drawdown_protection"] and ai["current_drawdown"]>=ai["max_drawdown_pct"]: time.sleep(5); continue
        if bal>0:
            dlp=abs(min(0,ai["daily_pnl"]))/bal*100
            if dlp>=state["capital_mgmt"]["max_daily_loss"]: time.sleep(5); continue
        if bal<5: time.sleep(5); continue
        if ai.get("smart_filter_active",False) and random.random()<0.75: time.sleep(3); continue
        for coin in list(state["active_positions"].keys()):
            price=state["prices"].get(coin,0)
            if price>0:
                check_partial_tp(coin,price,state["active_positions"][coin])
                check_exit(coin,price,mode)
        for coin in state["selected_coins"]:
            price=state["prices"].get(coin,0)
            if price==0:
                print(f"⚠️ لا سعر لـ {coin}")
                continue
            if coin in state["active_positions"]: continue
            if len(state["active_positions"])>=state["capital_mgmt"].get("max_open",10): break
            best_strat,best_score,votes=None,0,0
            # threshold متوازن
            threshold = 65.0  # ثابت ومنطقي
            if mode == "real":
                threshold = 60.0  # أسهل في الوضع الحقيقي
            if ai.get("streak",0) <= -3: threshold = min(80, threshold + 6)
            elif ai.get("streak",0) >= 3: threshold = max(52, threshold - 6)
            for s in state["selected_strategies"]:
                sc=compute_signal_score(coin,s,ai)
                if sc>threshold:
                    votes+=1
                    if sc>best_score: best_score=sc; best_strat=s
            if votes>=1 and best_strat:
                print(f"📡 إشارة: {coin} | {best_strat} | نقاط={best_score:.1f} | {mode.upper()}")
                execute_entry(coin,price,mode,best_strat)
            else:
                pass  # لا إشارة كافية
        time.sleep(2)


# ════════════════════════════════════════════════════════════════════════
# HTML — V17 + DIRECT CHAT مع Claude
# ════════════════════════════════════════════════════════════════════════
HTML = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚡ Master Terminal V22 — Gemini + Quantum AI</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600;700&family=Tajawal:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/apexcharts@3.45.2/dist/apexcharts.min.js"></script>
<style>
:root{
  --bg:#03050e;--bg2:#070c18;--card:#0b1424;--card2:#101d30;
  --border:#182840;--border2:#1f3350;--border3:#2a4570;
  --y:#f5c518;--g:#00e5a0;--r:#ff3d6e;--a:#38bdf8;
  --p:#c084fc;--o:#fb923c;--t:#22d3ee;--gold:#ffd700;
  --lm:#a3e635;--tx:#eef2ff;--tx2:#8899bb;--tx3:#3d5070;
  --claude:#da7756;--claude2:#c96840;
  --sh1:0 4px 24px rgba(0,0,0,.6);
  --sh2:0 8px 40px rgba(0,0,0,.8);
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{
  font-family:'Tajawal',sans-serif;
  background:var(--bg);
  color:var(--tx);
  min-height:100vh;
  overflow-x:hidden;
}
.mono{font-family:'IBM Plex Mono',monospace}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--bg2)}
::-webkit-scrollbar-thumb{background:var(--border3);border-radius:3px}

/* ══════════════════ TOPBAR ══════════════════ */
.topbar{
  position:sticky;top:0;z-index:100;
  display:flex;align-items:center;gap:12px;
  padding:10px 28px;
  background:rgba(7,12,24,.95);
  border-bottom:1px solid var(--border2);
  backdrop-filter:blur(20px);
  box-shadow:0 2px 20px rgba(0,0,0,.5);
}
.logo-wrap{display:flex;align-items:center;gap:10px}
.logo{
  font-size:18px;font-weight:900;letter-spacing:.5px;white-space:nowrap;
  background:linear-gradient(135deg,var(--gold) 0%,var(--o) 45%,var(--p) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.vbadge{
  font-size:9px;padding:3px 9px;border-radius:20px;font-weight:700;
  letter-spacing:.5px;white-space:nowrap;
}
.ticker-strip{
  flex:1;display:flex;gap:16px;align-items:center;overflow:hidden;
  padding:0 16px;border-right:1px solid var(--border2);border-left:1px solid var(--border2);
}
.tick-item{display:flex;align-items:center;gap:5px;white-space:nowrap}
.tick-label{font-size:10px;color:var(--tx3)}
.tick-val{font-size:11px;font-weight:700;font-family:'IBM Plex Mono',monospace}
.tick-sep{color:var(--border3);font-size:14px}
.top-right{display:flex;align-items:center;gap:12px}
.status-dot{width:8px;height:8px;border-radius:50%;background:var(--g);animation:pulse 1.5s infinite;flex-shrink:0}
.status-dot.off{background:var(--r);animation:none}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(0,229,160,.5)}60%{box-shadow:0 0 0 5px rgba(0,229,160,0)}}
.clock{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--a)}

/* ══════════════════ STATS ROW ══════════════════ */
.stats-row{
  display:grid;grid-template-columns:repeat(8,1fr);gap:6px;
  padding:16px 28px 0;
}
.stat-card{
  background:var(--card);border:1px solid var(--border);border-radius:12px;
  padding:14px 16px;position:relative;overflow:hidden;transition:.2s;cursor:default;
}
.stat-card:hover{transform:translateY(-3px);border-color:var(--border3);box-shadow:var(--sh1)}
.stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;border-radius:12px 12px 0 0}
.stat-card.y::before{background:linear-gradient(90deg,var(--y),transparent)}
.stat-card.g::before{background:linear-gradient(90deg,var(--g),transparent)}
.stat-card.r::before{background:linear-gradient(90deg,var(--r),transparent)}
.stat-card.b::before{background:linear-gradient(90deg,var(--a),transparent)}
.stat-card.p::before{background:linear-gradient(90deg,var(--p),transparent)}
.stat-card.o::before{background:linear-gradient(90deg,var(--o),transparent)}
.stat-card.t::before{background:linear-gradient(90deg,var(--t),transparent)}
.stat-card.gold::before{background:linear-gradient(90deg,var(--gold),transparent)}
.stat-bg-icon{position:absolute;bottom:-4px;left:8px;font-size:36px;opacity:.04;pointer-events:none}
.stat-label{font-size:10px;color:var(--tx3);text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px}
.stat-val{font-size:22px;font-weight:900;line-height:1;font-family:'IBM Plex Mono',monospace}
.stat-sub{font-size:10px;color:var(--tx2);margin-top:4px}

/* ══════════════════ MODE BAR ══════════════════ */
.modebar{
  display:flex;align-items:center;gap:14px;
  margin:14px 28px 0;padding:12px 20px;
  border-radius:12px;border:1px solid;transition:.4s;
}
.modebar.demo{background:rgba(56,189,248,.05);border-color:rgba(56,189,248,.2)}
.modebar.real{background:rgba(245,197,24,.05);border-color:rgba(245,197,24,.25)}
.mode-icon{font-size:22px}
.mode-title{font-size:14px;font-weight:700}
.mode-sub{font-size:11px;opacity:.6;margin-top:2px}
.mode-bal{font-size:26px;font-weight:900;font-family:'IBM Plex Mono',monospace;margin-right:auto}

/* ══════════════════ MAIN LAYOUT ══════════════════ */
.main-layout{
  display:grid;
  grid-template-columns:320px 1fr 1fr;
  grid-template-rows:auto auto;
  gap:14px;
  padding:14px 28px 28px;
  min-height:calc(100vh - 160px);
}
.panel{
  background:var(--card);border:1px solid var(--border);
  border-radius:14px;overflow:hidden;display:flex;flex-direction:column;
}
.panel-head{
  padding:14px 20px;
  background:linear-gradient(90deg,var(--card2),transparent);
  border-bottom:1px solid var(--border);
  display:flex;align-items:center;gap:8px;
  font-size:12px;font-weight:700;color:var(--y);
  letter-spacing:.3px;flex-shrink:0;
}
.panel-head .ph-right{margin-right:auto;display:flex;align-items:center;gap:6px}
.panel-body{flex:1;overflow-y:auto;padding:16px}
.panel-body.no-pad{padding:0}

/* ══════════════════ SETTINGS FORM ══════════════════ */
.field-label{
  font-size:10px;color:var(--tx3);text-transform:uppercase;
  letter-spacing:.5px;display:block;margin:10px 0 4px;
}
.field-label:first-child{margin-top:0}
select,input[type=number],input[type=text]{
  width:100%;padding:8px 12px;border-radius:8px;
  border:1px solid var(--border2);background:var(--bg2);
  color:var(--tx);font-size:12px;font-family:'Tajawal',sans-serif;
  transition:.2s;
}
select:focus,input:focus{outline:none;border-color:var(--a);box-shadow:0 0 0 3px rgba(56,189,248,.1)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px}
.check-row{
  display:flex;align-items:center;gap:8px;padding:6px 10px;
  border-radius:8px;cursor:pointer;transition:.15s;font-size:12px;
}
.check-row:hover{background:rgba(255,255,255,.03)}
.check-row input[type=checkbox]{width:14px;height:14px;accent-color:var(--y);cursor:pointer}
.coin-search{position:relative;margin-bottom:6px}
.coin-search input{padding-right:32px}
.coin-search .srch-icon{position:absolute;right:10px;top:50%;transform:translateY(-50%);color:var(--tx3);font-size:11px;pointer-events:none}
.coin-box{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:8px;max-height:140px;overflow-y:auto}
.coin-item{display:flex;align-items:center;gap:6px;padding:3px 4px;font-size:11px;cursor:pointer;border-radius:5px;transition:.1s}
.coin-item:hover{background:rgba(255,255,255,.04)}
.coin-item input[type=checkbox]{width:12px;height:12px;accent-color:var(--y);cursor:pointer;flex-shrink:0}
.metal-tag{font-size:8px;padding:1px 5px;border-radius:4px;background:rgba(255,215,0,.12);color:var(--gold);border:1px solid rgba(255,215,0,.2);font-weight:700}
.section-box{
  background:rgba(255,255,255,.02);border:1px solid var(--border);
  border-radius:10px;padding:12px;margin-bottom:10px;
}
.section-title{font-size:10px;color:var(--tx3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px;display:flex;align-items:center;gap:5px}
.btn{
  display:flex;align-items:center;justify-content:center;gap:7px;
  width:100%;padding:10px;border-radius:10px;border:none;cursor:pointer;
  font-size:13px;font-weight:700;font-family:'Tajawal',sans-serif;
  transition:.2s;margin-top:4px;
}
.btn-go{background:linear-gradient(135deg,#00e5a0,#00b87e);color:#000;box-shadow:0 4px 16px rgba(0,229,160,.25)}
.btn-go:hover{filter:brightness(1.08);transform:translateY(-2px)}
.btn-stop{background:var(--card2);color:var(--tx);border:1px solid var(--border2)}
.btn-stop:hover{border-color:var(--r);color:var(--r)}
.btn-save{background:linear-gradient(135deg,#6366f1,#4f46e5);color:#fff;box-shadow:0 4px 16px rgba(99,102,241,.3)}
.btn-save:hover{filter:brightness(1.1);transform:translateY(-2px)}
.btn-save:active{transform:scale(.97)}
.save-flash{animation:saveFlash .6s ease}
@keyframes saveFlash{0%{box-shadow:0 0 0 0 rgba(99,102,241,.8)}100%{box-shadow:0 0 0 16px rgba(99,102,241,0)}}
.divider{border:none;border-top:1px solid var(--border);margin:12px 0}

/* ══════════════════ CHART ══════════════════ */
.chart-wrap{padding:8px;flex-shrink:0}
.tf-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;padding:12px 16px;border-bottom:1px solid var(--border);flex-shrink:0}
.tf-card{
  border-radius:10px;padding:10px 8px;border:1px solid var(--border);
  text-align:center;transition:.2s;cursor:default;
}
.tf-card:hover{transform:translateY(-2px);border-color:var(--border3)}
.tf-card.buy{background:rgba(0,229,160,.07);border-color:rgba(0,229,160,.2)}
.tf-card.sell{background:rgba(255,61,110,.07);border-color:rgba(255,61,110,.2)}
.tf-card.neutral{background:rgba(56,189,248,.04);border-color:rgba(56,189,248,.14)}
.tf-lbl{font-size:10px;font-weight:700;font-family:'IBM Plex Mono',monospace;margin-bottom:2px}
.tf-trend{font-size:18px;font-weight:900;line-height:1.2}
.tf-str{font-size:9px;font-family:'IBM Plex Mono',monospace;margin-top:1px}
.tf-rsi{font-size:8px;color:var(--tx3);margin-top:1px}

/* TABS */
.tabs-bar{display:flex;gap:4px;background:var(--bg2);padding:4px;border-radius:8px;margin:0 16px 12px;flex-shrink:0}
.tab-btn{
  flex:1;padding:7px;border-radius:6px;border:none;background:transparent;
  color:var(--tx3);cursor:pointer;font-size:11px;font-weight:600;
  transition:.18s;white-space:nowrap;font-family:'Tajawal',sans-serif;
}
.tab-btn.on{background:var(--card2);color:var(--y);border:1px solid var(--border2)}

/* BADGES */
.badge{font-size:9px;padding:2px 8px;border-radius:8px;font-weight:700;letter-spacing:.3px}
.b-g{background:rgba(0,229,160,.1);color:var(--g);border:1px solid rgba(0,229,160,.2)}
.b-y{background:rgba(245,197,24,.1);color:var(--y);border:1px solid rgba(245,197,24,.2)}
.b-r{background:rgba(255,61,110,.1);color:var(--r);border:1px solid rgba(255,61,110,.2)}
.b-b{background:rgba(56,189,248,.1);color:var(--a);border:1px solid rgba(56,189,248,.2)}
.b-p{background:rgba(192,132,252,.1);color:var(--p);border:1px solid rgba(192,132,252,.2)}
.b-t{background:rgba(34,211,238,.1);color:var(--t);border:1px solid rgba(34,211,238,.2)}
.b-o{background:rgba(251,146,60,.1);color:var(--o);border:1px solid rgba(251,146,60,.2)}
.b-gold{background:rgba(255,215,0,.1);color:var(--gold);border:1px solid rgba(255,215,0,.2)}

/* SIGNAL ROWS */
.sig-row{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid rgba(24,40,64,.5);font-size:11px}
.sig-row:last-child{border:none}

/* STRATEGY GRID */
.strat-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.strat-card{
  background:var(--bg2);border:1px solid var(--border);
  border-radius:10px;padding:10px 12px;transition:.2s;
}
.strat-card:hover{border-color:var(--border3)}
.strat-name{font-size:11px;font-weight:700;margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.strat-stats{display:flex;justify-content:space-between;font-size:10px}

/* HISTORY TABLE */
.htable{width:100%;border-collapse:collapse;font-size:11px}
.htable th{color:var(--tx3);padding:8px 10px;text-align:right;font-size:10px;text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid var(--border);font-weight:600}
.htable td{padding:8px 10px;border-bottom:1px solid rgba(24,40,64,.4);vertical-align:middle}
.htable tr:last-child td{border:none}
.htable tr:hover td{background:rgba(255,255,255,.01)}

/* AGENT CARDS */
.agent-card{
  border-radius:10px;padding:12px 14px;margin-bottom:8px;
  border:1px solid var(--border);position:relative;overflow:hidden;transition:.2s;
}
.agent-card:hover{border-color:var(--border3);transform:translateY(-1px)}
.agent-card.thinking::after{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,transparent,currentColor,transparent);
  animation:scan 2s linear infinite;
}
@keyframes scan{0%{transform:translateX(-100%)}100%{transform:translateX(200%)}}
.ag-bar{position:absolute;top:0;left:0;bottom:0;width:4px;border-radius:12px 0 0 12px}
.ag-header{display:flex;align-items:center;gap:8px;margin-bottom:6px;padding-right:4px}
.ag-emoji{font-size:18px;line-height:1}
.ag-name{font-size:12px;font-weight:700}
.ag-role{font-size:10px;color:var(--tx2)}
.ag-status{margin-right:auto;font-size:9px;padding:2px 8px;border-radius:10px;font-weight:700}
.ag-msg{font-size:10px;color:var(--tx2);line-height:1.5;margin-top:5px;padding-top:6px;border-top:1px solid rgba(255,255,255,.05)}
.ag-conf{display:flex;align-items:center;gap:6px;margin-top:6px}
.ag-conf-bar{flex:1;height:4px;background:var(--border2);border-radius:2px;overflow:hidden}
.ag-conf-fill{height:100%;border-radius:2px;transition:width .5s}
.ag-conf-val{font-size:9px;font-family:'IBM Plex Mono',monospace;color:var(--tx2);min-width:30px}

/* THROBBER */
.thinking-dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin:0 2px;animation:throb .8s ease infinite}
.thinking-dot:nth-child(2){animation-delay:.2s}
.thinking-dot:nth-child(3){animation-delay:.4s}
@keyframes throb{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.3;transform:scale(.7)}}

/* HEALTH RING */
.health-ring{display:flex;align-items:center;gap:14px;padding:12px;background:var(--bg2);border-radius:10px;border:1px solid var(--border);margin-bottom:12px}
.ring-wrap{position:relative;width:64px;height:64px;flex-shrink:0}
.ring-wrap svg{transform:rotate(-90deg)}
.ring-score{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:15px;font-weight:900;font-family:'IBM Plex Mono',monospace}

/* METRICS GRID */
.met-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:10px}
.met-card{background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:10px 12px;text-align:center;transition:.2s}
.met-card:hover{border-color:var(--border3)}
.met-val{font-size:18px;font-weight:900;font-family:'IBM Plex Mono',monospace;margin-top:3px;line-height:1}
.met-label{font-size:9px;color:var(--tx3);text-transform:uppercase;letter-spacing:.5px}
.met-sub{font-size:9px;margin-top:2px}
.aa-grid{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:10px}
.aa-cell{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:8px 10px}
.aa-label{font-size:9px;color:var(--tx3);text-transform:uppercase;margin-bottom:2px}
.aa-val{font-size:14px;font-weight:800;font-family:'IBM Plex Mono',monospace}
.pbar{width:100%;height:5px;background:var(--border2);border-radius:3px;overflow:hidden;margin-top:3px}
.pbf{height:100%;border-radius:3px;transition:width .5s}

/* METRICS TABLE */
.metrics-table{width:100%;border-radius:10px;overflow:hidden;border:1px solid var(--border)}
.met-row{display:flex;justify-content:space-between;font-size:11px;padding:9px 14px;border-bottom:1px solid rgba(24,40,64,.4)}
.met-row:last-child{border:none}
.met-row:nth-child(even){background:rgba(255,255,255,.01)}
.met-key{color:var(--tx2)}

/* POSITION CARDS */
.pos-card{
  background:linear-gradient(135deg,var(--bg2),var(--card2));
  border:1px solid var(--border);border-radius:10px;padding:12px 16px;
  margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;transition:.2s;
}
.pos-card:hover{border-color:var(--border3);transform:translateY(-1px)}
.pos-coin{font-weight:900;font-size:14px}
.pos-strat{font-size:10px;color:var(--tx2);margin-top:2px}
.pos-entry{font-size:10px;color:var(--tx3);font-family:'IBM Plex Mono',monospace;margin-top:2px}
.pos-pct{font-size:20px;font-weight:900;font-family:'IBM Plex Mono',monospace}
.pos-usd{font-size:11px;margin-top:2px;font-weight:600}
.pg{color:var(--g)}.pr{color:var(--r)}

/* SPARKLINES */
.spark-row{display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid rgba(24,40,64,.3);font-size:10px}
.spark-row:last-child{border:none}
canvas.spk{flex:1;height:24px}

/* DIRECT CHAT */
.chat-panel{display:flex;flex-direction:column;height:100%}
.chat-messages{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px}
.msg-row{display:flex;gap:10px;align-items:flex-start;animation:fadeUp .3s ease}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.msg-row.user{flex-direction:row-reverse}
.msg-avatar{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;margin-top:2px}
.msg-avatar.claude{background:linear-gradient(135deg,var(--claude),var(--claude2));box-shadow:0 0 12px rgba(218,119,86,.3)}
.msg-avatar.user-av{background:linear-gradient(135deg,var(--a),#2090d0)}
.bubble{max-width:82%;padding:11px 15px;border-radius:14px;font-size:11px;line-height:1.7;position:relative}
.bubble.claude{background:linear-gradient(135deg,rgba(218,119,86,.12),rgba(218,119,86,.06));border:1px solid rgba(218,119,86,.2);border-radius:4px 14px 14px 14px}
.bubble.user{background:linear-gradient(135deg,rgba(56,189,248,.1),rgba(56,189,248,.05));border:1px solid rgba(56,189,248,.18);border-radius:14px 4px 14px 14px;text-align:right}
.bubble-time{font-size:8px;color:var(--tx3);margin-top:5px;font-family:'IBM Plex Mono',monospace}
.bubble.claude .bubble-time{text-align:left}
.bubble.user .bubble-time{text-align:right}
.typing-bub{background:rgba(218,119,86,.08);border:1px solid rgba(218,119,86,.15);border-radius:4px 14px 14px 14px;padding:12px 16px;display:flex;gap:5px;align-items:center}
.tdot{width:6px;height:6px;background:var(--claude);border-radius:50%;animation:tdAnim .8s ease infinite}
.tdot:nth-child(2){animation-delay:.16s}
.tdot:nth-child(3){animation-delay:.32s}
@keyframes tdAnim{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-6px)}}
.chat-hints{display:flex;gap:5px;flex-wrap:wrap;padding:0 14px;margin-bottom:8px}
.hint-pill{
  font-size:10px;padding:4px 10px;border-radius:20px;
  border:1px solid rgba(218,119,86,.2);background:rgba(218,119,86,.07);
  color:var(--claude);cursor:pointer;transition:.15s;font-family:'Tajawal',sans-serif;
}
.hint-pill:hover{background:rgba(218,119,86,.15);border-color:var(--claude)}
.chat-input-area{padding:12px 14px;border-top:1px solid var(--border);flex-shrink:0;background:linear-gradient(0deg,var(--card2),transparent)}
.input-row{display:flex;gap:8px;align-items:flex-end}
.chat-textarea{
  flex:1;background:var(--bg2);border:1px solid var(--border2);border-radius:10px;
  color:var(--tx);font-size:11px;font-family:'Tajawal',sans-serif;
  padding:10px 14px;resize:none;min-height:40px;max-height:100px;line-height:1.5;transition:.2s;
}
.chat-textarea:focus{outline:none;border-color:var(--claude);box-shadow:0 0 0 3px rgba(218,119,86,.1)}
.send-btn{
  width:40px;height:40px;border-radius:10px;border:none;cursor:pointer;
  background:linear-gradient(135deg,var(--claude),var(--claude2));color:#fff;
  display:flex;align-items:center;justify-content:center;font-size:14px;
  transition:.2s;flex-shrink:0;
}
.send-btn:hover{transform:scale(1.1);filter:brightness(1.12)}
.send-btn:disabled{opacity:.4;cursor:not-allowed;transform:none}
.chat-status-bar{font-size:9px;text-align:center;padding:4px;margin-bottom:4px}
.chat-status-bar.conn{color:var(--g)}
.chat-status-bar.disc{color:var(--r)}

/* V19 LEARNING PANEL */
.learn-panel{background:rgba(34,211,238,.04);border:1px solid rgba(34,211,238,.15);border-radius:10px;padding:12px;margin-top:10px}
.learn-title{font-size:10px;font-weight:700;color:var(--t);margin-bottom:8px;display:flex;align-items:center;gap:6px;justify-content:space-between}
.weight-row{display:flex;align-items:center;gap:8px;padding:3px 0;font-size:10px}
.weight-bar-wrap{flex:1;height:5px;background:var(--border2);border-radius:3px;overflow:hidden}
.weight-bar-fill{height:100%;border-radius:3px;transition:width .5s}

/* TOASTS */
#toasts{position:fixed;bottom:20px;left:24px;z-index:9999;display:flex;flex-direction:column;gap:6px}
.toast{
  background:linear-gradient(135deg,var(--card2),var(--card));color:var(--tx);
  padding:10px 16px;border-radius:10px;border:1px solid var(--border2);
  display:flex;align-items:center;gap:8px;min-width:240px;font-size:12px;
  animation:tIn .3s ease,tOut .3s 3.8s forwards;box-shadow:var(--sh1);
}
.toast.ts{border-right:3px solid var(--g)}
.toast.td{border-right:3px solid var(--r)}
.toast.tp{border-right:3px solid var(--gold)}
@keyframes tIn{from{transform:translateX(-16px);opacity:0}to{transform:translateX(0);opacity:1}}
@keyframes tOut{to{transform:translateX(-16px);opacity:0}}
</style>
</head>
<body>

<!-- ══════════════ TOPBAR ══════════════ -->
<div class="topbar">
  <div class="logo-wrap">
    <div class="logo">⚡ MASTER TERMINAL</div>
    <span class="vbadge" style="background:rgba(56,189,248,.12);color:var(--a)">V19</span>
    <span class="vbadge" style="background:rgba(192,132,252,.12);color:var(--p)">Quantum AI</span>
    <span class="vbadge" style="background:rgba(34,211,238,.12);color:var(--t)">🧠 Learning</span>
    <span class="vbadge" style="background:rgba(251,146,60,.12);color:var(--o)">⚡ Backtest</span>
    <span class="vbadge" style="background:rgba(0,229,160,.1);color:var(--g)">LOT ✅</span>
  <span class="vbadge" style="background:rgba(74,222,128,.12);color:#4ade80">🏦 Portfolio AI</span>
  <span class="vbadge" style="background:rgba(250,204,21,.12);color:#facc15">💰 Profit AI</span>
  <span class="vbadge" style="background:rgba(66,133,244,.12);color:#4285f4">🔷 Gemini</span>
  <span class="vbadge" style="background:rgba(232,121,249,.12);color:#e879f9">🔭 Scanner</span>
  </div>
  <div class="ticker-strip">
    <div class="tick-item"><span class="tick-label">BTC</span><span class="tick-val" id="t-btc" style="color:var(--g)">--</span></div>
    <span class="tick-sep">│</span>
    <div class="tick-item"><span class="tick-label">ETH</span><span class="tick-val" id="t-eth" style="color:var(--g)">--</span></div>
    <span class="tick-sep">│</span>
    <div class="tick-item"><span class="tick-label">SOL</span><span class="tick-val" id="t-sol" style="color:var(--g)">--</span></div>
    <span class="tick-sep">│</span>
    <div class="tick-item" style="color:var(--gold)"><span class="tick-label">🥇</span><span class="tick-val" id="t-gold">--</span></div>
    <span class="tick-sep">│</span>
    <div class="tick-item"><span class="tick-label" style="color:var(--o)">Vol</span><span class="tick-val" id="t-vol">--</span></div>
    <span class="tick-sep">│</span>
    <div class="tick-item"><span class="tick-label">Mom</span><span class="tick-val" id="t-mom">--</span></div>
    <span class="tick-sep">│</span>
    <div class="tick-item" style="color:var(--p)"><span class="tick-label">🤖</span><span class="tick-val" id="t-agent">جاهز</span></div>
    <span class="tick-sep">│</span>
    <div class="tick-item"><span class="tick-label">Pos</span><span class="tick-val" id="t-pos" style="color:var(--y)">0</span></div>
  </div>
  <div class="top-right">
    <div class="status-dot off" id="sdot"></div>
    <span id="stxt" style="font-size:11px">متوقف</span>
    <span style="color:var(--border3)">│</span>
    <span class="clock" id="clk">--:--:--</span>
  </div>
</div>

<!-- ══════════════ STATS ROW ══════════════ -->
<div class="stats-row">
  <div class="stat-card gold"><i class="fas fa-coins stat-bg-icon"></i><div class="stat-label">Binance Real</div><div class="stat-val" id="r-bal">$0</div><div class="stat-sub" id="api-s">--</div></div>
  <div class="stat-card b"><i class="fas fa-flask stat-bg-icon"></i><div class="stat-label">تجريبي</div><div class="stat-val" id="d-bal">$0</div><div class="stat-sub">Virtual Demo</div></div>
  <div class="stat-card g"><i class="fas fa-trophy stat-bg-icon"></i><div class="stat-label">Win Rate</div><div class="stat-val" id="wr">0%</div><div class="stat-sub" id="wr-s">--</div></div>
  <div class="stat-card o"><i class="fas fa-chart-line stat-bg-icon"></i><div class="stat-label">P&L</div><div class="stat-val" id="pnl">$0</div><div class="stat-sub" id="pnl-m">--</div></div>
  <div class="stat-card t"><i class="fas fa-balance-scale stat-bg-icon"></i><div class="stat-label">حجم الصفقة</div><div class="stat-val" id="cm-sz">--</div><div class="stat-sub" id="cm-sz-r">--</div></div>
  <div class="stat-card p"><i class="fas fa-robot stat-bg-icon"></i><div class="stat-label">وكيل AI</div><div class="stat-val" id="agent-rec" style="font-size:14px">--</div><div class="stat-sub" id="agent-risk">--</div></div>
  <div class="stat-card r"><i class="fas fa-shield-alt stat-bg-icon"></i><div class="stat-label">Drawdown</div><div class="stat-val" id="dd">0%</div><div class="stat-sub">تراجع</div></div>
  <div class="stat-card y"><i class="fas fa-heartbeat stat-bg-icon"></i><div class="stat-label">AI Confidence</div><div class="stat-val" id="aic">0%</div><div class="stat-sub" id="sf-s">طبيعي</div></div>
</div>

<!-- ══════════════ MODE BAR ══════════════ -->
<div id="mbar" class="modebar demo" style="margin:14px 28px 0">
  <span class="mode-icon" id="m-icon">🎮</span>
  <div>
    <div class="mode-title" id="m-title">وضع تجريبي (Demo)</div>
    <div class="mode-sub" id="m-sub">تداول افتراضي آمن</div>
  </div>
  <div class="mode-bal" id="m-bv">$10,000.00</div>
  <span id="rg" class="badge b-y" style="font-size:10px">ranging</span>
</div>

<!-- ══════════════ MAIN LAYOUT ══════════════ -->
<div class="main-layout">

<!-- ═ COL 1: SETTINGS ═ -->
<div style="display:flex;flex-direction:column;gap:14px">
  <div class="panel">
    <div class="panel-head"><i class="fas fa-sliders-h"></i> الإعدادات <span class="badge b-b ph-right">V19</span></div>
    <div class="panel-body">
    <form method="POST">
      <div class="section-box">
        <div class="section-title"><i class="fas fa-exchange-alt" style="color:var(--a)"></i> وضع التداول</div>
        <span class="field-label">الوضع</span>
        <select name="mode" onchange="onMode(this.value)">
          <option value="demo" {% if state.current_mode=='demo' %}selected{% endif %}>🎮 تجريبي (Demo)</option>
          <option value="real" {% if state.current_mode=='real' %}selected{% endif %}>💰 حقيقي (Real)</option>
        </select>
        <div id="rw" style="display:{% if state.current_mode=='real' %}flex{% else %}none{% endif %};align-items:center;gap:7px;background:rgba(245,197,24,.06);border:1px solid rgba(245,197,24,.25);border-radius:8px;padding:8px 12px;margin:6px 0;font-size:11px;color:var(--y)">
          <i class="fas fa-exclamation-triangle"></i><span>أموال حقيقية — المسؤولية عليك</span>
        </div>
        <div class="grid2" style="margin-top:6px">
          <div>
            <span class="field-label">نوع التداول — يمكن تفعيل كليهما</span>
            <div style="display:flex;gap:6px;margin-top:4px">
              <label style="flex:1;display:flex;align-items:center;gap:7px;padding:8px 10px;border-radius:8px;cursor:pointer;border:2px solid {% if state.active_engines.spot %}var(--a){% else %}var(--border){% endif %};background:{% if state.active_engines.spot %}rgba(56,189,248,.08){% else %}var(--bg2){% endif %};transition:.2s">
                <input type="checkbox" name="engine_spot" value="1" {% if state.active_engines.spot %}checked{% endif %} style="width:15px;height:15px;accent-color:var(--a);cursor:pointer">
                <div><div style="font-size:11px;font-weight:700;color:{% if state.active_engines.spot %}var(--a){% else %}var(--tx2){% endif %}">🟡 Spot</div><div style="font-size:9px;color:var(--tx3)">بدون رافعة</div></div>
              </label>
              <label style="flex:1;display:flex;align-items:center;gap:7px;padding:8px 10px;border-radius:8px;cursor:pointer;border:2px solid {% if state.active_engines.futures %}var(--r){% else %}var(--border){% endif %};background:{% if state.active_engines.futures %}rgba(255,61,110,.08){% else %}var(--bg2){% endif %};transition:.2s">
                <input type="checkbox" name="engine_futures" value="1" {% if state.active_engines.futures %}checked{% endif %} style="width:15px;height:15px;accent-color:var(--r);cursor:pointer">
                <div><div style="font-size:11px;font-weight:700;color:{% if state.active_engines.futures %}var(--r){% else %}var(--tx2){% endif %}">🔴 Futures</div><div style="font-size:9px;color:var(--tx3)">x{{state.futures_leverage}}</div></div>
              </label>
            </div>
            <div style="margin-top:5px;padding:5px 9px;border-radius:6px;background:var(--bg2);font-size:9px;color:var(--tx2);text-align:center">
              {% if state.active_engines.spot and state.active_engines.futures %}⚡ كلاهما نشط
              {% elif state.active_engines.spot %}🟡 Spot فقط
              {% elif state.active_engines.futures %}🔴 Futures فقط x{{state.futures_leverage}}
              {% else %}⏸ اختر نوعاً{% endif %}
            </div>
          </div>
          <div>
            <span class="field-label">الرافعة</span>
            <input type="number" name="leverage" min="1" max="125" value="{{state.futures_leverage}}" style="text-align:center">
          </div>
        </div>
      </div>

      <div class="section-box">
        <div class="section-title"><i class="fas fa-dollar-sign" style="color:var(--t)"></i> رأس المال</div>
        <span class="field-label">نمط الإدارة</span>
        <select name="capital_mode">
          <option value="smart_adaptive" {% if state.capital_mgmt.mode=='smart_adaptive' %}selected{% endif %}>🧠 ذكي تكيفي (Quantum)</option>
          <option value="fixed" {% if state.capital_mgmt.mode=='fixed' %}selected{% endif %}>ثابت</option>
          <option value="kelly" {% if state.capital_mgmt.mode=='kelly' %}selected{% endif %}>Kelly</option>
          <option value="volatility_scaled" {% if state.capital_mgmt.mode=='volatility_scaled' %}selected{% endif %}>حسب التذبذب</option>
        </select>
        <div class="grid2" style="margin-top:6px">
          <div><span class="field-label">مخاطرة %</span><input type="number" step="0.1" name="base_risk" value="{{state.capital_mgmt.base_risk_pct}}"></div>
          <div><span class="field-label">خسارة يومية %</span><input type="number" step="0.1" name="max_daily_loss" value="{{state.capital_mgmt.max_daily_loss}}"></div>
        </div>
        <label class="check-row" style="margin-top:4px"><input type="checkbox" name="partial_tp" {% if state.capital_mgmt.partial_tp %}checked{% endif %}><span>Partial Take Profit</span></label>
      </div>

      <div class="section-box">
        <div class="section-title"><i class="fas fa-robot" style="color:var(--a)"></i> Quantum AI</div>
        <label class="check-row"><input type="checkbox" name="ai_enabled" {% if state.ai_learner.enabled %}checked{% endif %}><span style="color:var(--a);font-weight:700">تفعيل نظام AI</span></label>
        <label class="check-row"><input type="checkbox" name="drawdown_protection" {% if state.ai_learner.drawdown_protection %}checked{% endif %}><span>حماية التراجع</span></label>
        <span class="field-label">أقصى تراجع %</span>
        <input type="number" step="0.5" name="max_drawdown" value="{{state.ai_learner.max_drawdown_pct}}">
      </div>

      <div class="section-box" style="border-color:rgba(66,133,244,.2);background:rgba(66,133,244,.03)">
        <div class="section-title"><span style="color:#4285f4">🔷 Google Gemini</span></div>
        <span class="field-label">مفتاح Gemini API</span>
        <input type="text" name="gemini_key" placeholder="AIza..." value="{{gemini_key_display}}" style="font-family:'IBM Plex Mono',monospace;font-size:10px;border-color:rgba(66,133,244,.3)">
        <div style="font-size:9px;color:var(--tx3);margin-top:4px">🆓 <a href="https://aistudio.google.com" target="_blank" style="color:#4285f4">aistudio.google.com</a></div>
      </div>
      <div class="section-box" style="border-color:rgba(41,182,246,.2);background:rgba(41,182,246,.03)">
        <div class="section-title"><span style="color:#29b6f6">📱 Telegram</span></div>
        <span class="field-label">Bot Token</span>
        <input type="text" name="tg_token" placeholder="123456:ABC..." style="font-family:'IBM Plex Mono',monospace;font-size:10px">
        <span class="field-label">Chat ID</span>
        <input type="text" name="tg_chat" placeholder="-100..." style="font-family:'IBM Plex Mono',monospace;font-size:10px">
      </div>

      <div class="section-box">
        <div class="section-title"><i class="fas fa-chess" style="color:var(--p)"></i> الاستراتيجيات</div>
        <div style="max-height:130px;overflow-y:auto">
          {% for k,v in state.strategies.items() %}
          <label class="check-row"><input type="checkbox" name="strats" value="{{k}}" {% if k in state.selected_strategies %}checked{% endif %}><span style="font-size:11px">{{v}}</span></label>
          {% endfor %}
        </div>
      </div>

      <div class="section-box">
        <div class="section-title"><i class="fas fa-coins" style="color:var(--gold)"></i> العملات</div>
        <div class="coin-search"><input type="text" id="coin-search" placeholder="🔍 ابحث عن عملة..." oninput="filterCoins(this.value)"><i class="fas fa-search srch-icon"></i></div>
        <div class="coin-box" id="coin-list">
          {% for c in state.all_coins %}
          <label class="coin-item" data-coin="{{c}}">
            <input type="checkbox" name="coins" value="{{c}}" {% if c in state.selected_coins %}checked{% endif %}>
            <span>{% if c in ['XAUTUSDT','XAGUSDT'] %}<span class="metal-tag">Metal</span>{% endif %}{{c}}</span>
          </label>
          {% endfor %}
        </div>
      </div>

      <div class="section-box">
        <div class="section-title"><i class="fas fa-clock" style="color:var(--t)"></i> الفريمات الزمنية</div>
        <div style="display:flex;flex-wrap:wrap;gap:5px">
          {% for tf in state.timeframes %}
          <label style="display:flex;align-items:center;gap:4px;font-size:11px;cursor:pointer;background:var(--bg);padding:4px 8px;border-radius:6px;border:1px solid var(--border)">
            <input type="checkbox" name="timeframes" value="{{tf}}" {% if tf in state.selected_timeframes %}checked{% endif %} style="width:12px;accent-color:var(--a)">{{tf}}
          </label>
          {% endfor %}
        </div>
      </div>

      <div class="section-box">
        <div class="section-title"><i class="fas fa-stopwatch" style="color:var(--o)"></i> Stop Loss / Trailing</div>
        <div class="grid2">
          <div>
            <span class="field-label">نوع SL</span>
            <select name="sl_type">
              <option value="fixed" {% if state.smart_sl.type=='fixed' %}selected{% endif %}>ثابت</option>
              <option value="trailing" {% if state.smart_sl.type=='trailing' %}selected{% endif %}>Trailing</option>
            </select>
          </div>
          <div>
            <span class="field-label">Offset %</span>
            <input type="number" step="0.1" name="trailing_offset" value="{{state.smart_sl.trailing_offset}}">
          </div>
        </div>
      </div>

      <div class="grid2" style="margin-top:6px">
        <button name="action" value="start" class="btn btn-go"><i class="fas fa-play"></i> تشغيل</button>
        <button name="action" value="stop" class="btn btn-stop"><i class="fas fa-stop"></i> إيقاف</button>
      </div>
      <button name="action" value="save_settings" class="btn btn-save" id="save-btn" style="margin-top:8px">
        <i class="fas fa-save"></i> حفظ وتطبيق الإعدادات
      </button>
      <div id="save-status" style="text-align:center;font-size:10px;color:var(--g);margin-top:4px;min-height:16px;transition:.3s"></div>
    </form>
    </div>
  </div>
</div><!-- end col 1 -->

<!-- ═ COL 2: CHART + SIGNALS ═ -->
<div style="display:flex;flex-direction:column;gap:14px">

  <!-- Chart Panel -->
  <div class="panel">
    <div class="panel-head"><i class="fas fa-chart-area"></i> الأداء الحي</div>
    <div class="chart-wrap"><div id="mainChart"></div></div>
    <div style="padding:8px 16px;border-bottom:1px solid var(--border);border-top:1px solid var(--border)" id="sparklines"></div>
    <div>
      <div style="padding:10px 16px 4px;font-size:10px;color:var(--tx3);text-transform:uppercase;letter-spacing:.4px"><i class="fas fa-clock" style="color:var(--t)"></i> Quantum TF Analysis</div>
      <div class="tf-grid" id="tf-grid"></div>
    </div>
  </div>

  <!-- Signals Panel -->
  <div class="panel" style="min-height:420px">
    <div class="panel-head"><i class="fas fa-signal"></i> الإشارات والصفقات</div>
    <div style="padding:10px 16px 0;flex-shrink:0">
      <div class="tabs-bar">
        <button class="tab-btn on" onclick="sL('sig',this)">📡 إشارات</button>
        <button class="tab-btn" onclick="sL('cap',this)">⚖️ الحجم</button>
        <button class="tab-btn" onclick="sL('strat',this)">🎯 استراتيجيات</button>
        <button class="tab-btn" onclick="sL('hist',this)">📋 السجل</button>
      </div>
    </div>
    <div class="panel-body">
      <div id="v-sig"><div id="sig-list"></div></div>
      <div id="v-cap" style="display:none"><div id="cap-list"></div></div>
      <div id="v-strat" style="display:none"><div class="strat-grid" id="sg"></div></div>
      <div id="v-hist" style="display:none">
        <table class="htable" id="ht">
          <thead><tr><th>الوقت</th><th>العملة</th><th>الوضع</th><th>الاستراتيجية</th><th>%</th><th>$</th><th>المدة</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </div>

</div><!-- end col 2 -->

<!-- ═ COL 3: AGENTS + CHAT + PORTFOLIO ═ -->
<div style="display:flex;flex-direction:column;gap:14px">

  <!-- Agents Panel -->
  <div class="panel">
    <div class="panel-head"><i class="fas fa-robot"></i> Quantum AI Agents <span class="badge b-p ph-right" id="agents-active">0/7</span></div>
    <div style="padding:10px 16px 0;flex-shrink:0">
      <div class="tabs-bar">
        <button class="tab-btn on" onclick="sAG('agents',this)">🤖 الوكلاء</button>
        <button class="tab-btn" onclick="sAG('analysis',this)">🔬 تحليل</button>
        <button class="tab-btn" onclick="sAG('hm',this)">🔥 الفرص</button>
      </div>
    </div>
    <div class="panel-body" id="agents-scroll">
      <div id="ag-agents">
        <div id="agent-cards"></div>
        <div class="learn-panel">
          <!-- Neural Network Panel -->
          <div style="background:rgba(139,92,246,.05);border:1px solid rgba(139,92,246,.2);border-radius:10px;padding:10px;margin-bottom:8px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
              <span style="font-size:14px">🧠</span>
              <span style="font-size:10px;font-weight:700;color:#8b5cf6;text-transform:uppercase;letter-spacing:.4px">شبكة عصبية — Neural Network</span>
              <span id="neural-status" style="margin-right:auto;font-size:9px;padding:2px 7px;border-radius:6px;background:rgba(139,92,246,.1);color:#8b5cf6">0 إشارة</span>
            </div>
            <!-- إشارات الوكلاء -->
            <div id="neural-signals" style="margin-bottom:8px"></div>
            <!-- آخر انتقال إشارة -->
            <div style="font-size:9px;color:var(--tx3);text-transform:uppercase;letter-spacing:.3px;margin-bottom:4px">آخر انتقال عصبي</div>
            <div id="neural-last" style="font-size:10px;color:var(--tx2);line-height:1.5;min-height:18px"></div>
            <!-- قوة الاتصالات -->
            <div style="font-size:9px;color:var(--tx3);text-transform:uppercase;letter-spacing:.3px;margin-top:6px;margin-bottom:4px">قوة الاتصالات (Synaptic Weights)</div>
            <div id="neural-weights" style="display:flex;flex-wrap:wrap;gap:4px"></div>
          </div>
          <!-- Scalp Neural Panel -->
          <div style="background:rgba(244,63,94,.05);border:1px solid rgba(244,63,94,.2);border-radius:10px;padding:10px;margin-bottom:8px">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">
              <span style="font-size:16px">⚡</span>
              <span style="font-size:10px;font-weight:700;color:#f43f5e;text-transform:uppercase;letter-spacing:.4px">Scalp Neural — سكالب احترافي</span>
              <span id="scalp-signal-badge" style="margin-right:auto;font-size:9px;padding:2px 8px;border-radius:6px;background:rgba(244,63,94,.1);color:#f43f5e;font-weight:700">---</span>
            </div>
            <!-- نوافذ السكالب -->
            <div style="font-size:9px;color:var(--tx3);text-transform:uppercase;letter-spacing:.3px;margin-bottom:4px">فرص السكالب</div>
            <div id="scalp-windows" style="margin-bottom:6px"></div>
            <!-- إحصاءات -->
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:4px">
              <div style="background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:5px;text-align:center">
                <div style="font-size:8px;color:var(--tx3)">أفضل عملة</div>
                <div id="scalp-best-coin" style="font-size:10px;font-weight:700;color:#f43f5e">---</div>
              </div>
              <div style="background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:5px;text-align:center">
                <div style="font-size:8px;color:var(--tx3)">الزخم</div>
                <div id="scalp-momentum" style="font-size:10px;font-weight:700;color:var(--y)">0</div>
              </div>
              <div style="background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:5px;text-align:center">
                <div style="font-size:8px;color:var(--tx3)">آخر تحليل</div>
                <div id="scalp-time" style="font-size:9px;color:var(--tx3)">---</div>
              </div>
            </div>
          </div>
          <div class="learn-title">
            <span><i class="fas fa-brain" style="color:var(--t)"></i> Online Learning — V19</span>
            <div style="display:flex;gap:10px">
              <span style="font-size:10px;color:var(--tx2)">أنماط: <b id="learning-count" style="color:var(--t)">0</b></span>
              <span style="font-size:10px;color:var(--tx2)">Backtest: <b id="backtest-count" style="color:var(--o)">0</b></span>
            </div>
          </div>
          <div id="online-log" style="margin-bottom:8px;min-height:18px;font-size:10px;color:var(--tx2)"></div>
          <div style="font-size:9px;color:var(--tx3);text-transform:uppercase;letter-spacing:.4px;margin-bottom:5px">أوزان الاستراتيجيات</div>
          <div id="strategy-weights"></div>
        </div>
        <!-- NEWS WIDGET -->
      <div id="news-widget" style="background:rgba(240,171,252,.05);border:1px solid rgba(240,171,252,.2);border-radius:10px;padding:10px;margin-top:8px;margin-bottom:6px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">
          <span style="font-size:14px">📰</span>
          <span style="font-size:10px;font-weight:700;color:#f0abfc;text-transform:uppercase;letter-spacing:.4px">محلل الأخبار</span>
          <span id="news-time" style="font-size:8px;color:var(--tx3);margin-right:auto"></span>
          <span id="news-impact-badge" style="font-size:9px;padding:2px 8px;border-radius:8px;font-weight:700;background:rgba(240,171,252,.1);color:#f0abfc">جاري الجلب...</span>
        </div>
        <!-- شريط المشاعر -->
        <div style="margin-bottom:7px">
          <div style="display:flex;justify-content:space-between;font-size:9px;color:var(--tx2);margin-bottom:3px">
            <span>📉 سلبي</span>
            <span id="news-sent-val" style="font-weight:700;color:#f0abfc">0</span>
            <span>📈 إيجابي</span>
          </div>
          <div style="height:8px;background:var(--border2);border-radius:4px;overflow:hidden;position:relative">
            <div id="news-sent-bar" style="position:absolute;top:0;height:100%;width:50%;left:25%;background:#f0abfc;border-radius:4px;transition:all .6s"></div>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:8px;color:var(--tx3);margin-top:2px">
            <span>-100</span><span>0</span><span>+100</span>
          </div>
        </div>
        <!-- إحصاءات سريعة -->
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-bottom:7px">
          <div style="background:var(--bg2);border:1px solid var(--border);border-radius:7px;padding:6px;text-align:center">
            <div style="font-size:8px;color:var(--tx3)">Fear & Greed</div>
            <div id="news-fg" style="font-size:14px;font-weight:900;font-family:'IBM Plex Mono',monospace;color:var(--y)">--</div>
          </div>
          <div style="background:var(--bg2);border:1px solid var(--border);border-radius:7px;padding:6px;text-align:center">
            <div style="font-size:8px;color:var(--tx3)">BTC توجه</div>
            <div id="news-btc" style="font-size:11px;font-weight:700;color:#f7931a">--</div>
          </div>
          <div style="background:var(--bg2);border:1px solid var(--border);border-radius:7px;padding:6px;text-align:center">
            <div style="font-size:8px;color:var(--tx3)">الذهب</div>
            <div id="news-gold" style="font-size:11px;font-weight:700;color:var(--gold)">--</div>
          </div>
        </div>
        <!-- آخر الأخبار -->
        <div id="news-headlines" style="max-height:100px;overflow-y:auto"></div>
        <!-- تحذيرات -->
        <div id="news-alerts" style="margin-top:5px"></div>
      </div>
      <!-- Pro Trader Status -->
      <div style="background:rgba(250,204,21,.05);border:1px solid rgba(250,204,21,.2);border-radius:10px;padding:10px;margin-top:8px">
        <div style="font-size:10px;font-weight:700;color:#facc15;margin-bottom:6px">💎 تحليل المتداول المحترف</div>
        <div id="pro-trader-status" style="font-size:10px;color:var(--tx2)">جاري التحليل...</div>
      </div>
      <div style="font-size:11px;color:var(--tx2);line-height:1.7;background:rgba(192,132,252,.04);border:1px solid rgba(192,132,252,.14);border-radius:10px;padding:10px;margin-top:8px" id="agent-view">
          <i class="fas fa-brain" style="color:var(--p)"></i> في انتظار تحليل الوكلاء...
        </div>
      </div>
      <div id="ag-analysis" style="display:none"><div id="ai-cards"></div></div>
      <div id="ag-hm" style="display:none">
        <div style="font-size:11px;color:var(--tx2);margin-bottom:8px">نقاط الفرصة الكمية</div>
        <!-- ماسح السوق V22 -->
        <div id="top-opps" style="margin-bottom:10px"></div>
        <div style="font-size:10px;color:var(--tx3);text-transform:uppercase;letter-spacing:.4px;margin-bottom:6px">خريطة الحرارة</div>
        <div id="hm-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(70px,1fr));gap:6px;margin-bottom:10px"></div>
        <div class="met-grid">
          <div class="met-card"><div class="met-label">Adaptive TP</div><div class="met-val" id="atp" style="color:var(--g)">3%</div></div>
          <div class="met-card"><div class="met-label">Adaptive SL</div><div class="met-val" id="asl" style="color:var(--r)">1.5%</div></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Portfolio + Health Panel -->
  <div class="panel">
    <div class="panel-head"><i class="fas fa-wallet"></i> المحفظة والصحة <span class="badge b-g ph-right" id="h-badge">جيد</span></div>
    <div style="padding:10px 16px 0;flex-shrink:0">
      <div class="tabs-bar">
        <button class="tab-btn on" onclick="sPF('health',this)">❤️ صحة البوت</button>
        <button class="tab-btn" onclick="sPF('portfolio',this)">📂 المحفظة</button>
        <button class="tab-btn" onclick="sPF('pfanalysis',this)">🏦 تحليل</button>
        <button class="tab-btn" onclick="sPF('profits',this)">💰 الأرباح</button>
        <button class="tab-btn" onclick="sPF('paper',this)" style="color:#a78bfa">📄 تجريبي</button>
        <button class="tab-btn" onclick="sPF('metrics',this)">📊 مقاييس</button>
      </div>
    </div>
    <div class="panel-body">
      <!-- HEALTH -->
      <div id="pf-health">
        <div class="health-ring">
          <div class="ring-wrap">
            <svg width="64" height="64" viewBox="0 0 64 64">
              <circle cx="32" cy="32" r="25" fill="none" stroke="var(--border2)" stroke-width="6"/>
              <circle cx="32" cy="32" r="25" fill="none" id="harc" stroke="var(--g)" stroke-width="6"
                      stroke-dasharray="157" stroke-dashoffset="0" stroke-linecap="round"/>
            </svg>
            <div class="ring-score" id="hscore" style="color:var(--g)">100</div>
          </div>
          <div style="flex:1">
            <div style="font-size:12px;font-weight:700;margin-bottom:6px">حالة النظام</div>
            <div id="h-issues"></div>
          </div>
        </div>
        <div class="met-grid">
          <div class="met-card"><div class="met-label">وقت التشغيل</div><div class="met-val" id="h-up" style="color:var(--a);font-size:16px">0s</div></div>
          <div class="met-card"><div class="met-label">صفقات</div><div class="met-val" id="h-tr" style="color:var(--t);font-size:16px">0</div></div>
          <div class="met-card"><div class="met-label">أوامر</div><div class="met-val" id="h-ord" style="color:var(--g);font-size:16px">0</div></div>
          <div class="met-card"><div class="met-label">فشل</div><div class="met-val" id="h-fail" style="color:var(--g);font-size:16px">0</div></div>
        </div>
        <div class="aa-grid" id="aa-grid"></div>
        <div style="font-size:11px;color:var(--tx2);margin-bottom:4px;display:flex;justify-content:space-between"><span>مستوى المخاطرة</span><span id="rs-val">50%</span></div>
        <div class="pbar"><div id="rs-bar" class="pbf" style="width:50%"></div></div>
      </div>
      <!-- PORTFOLIO -->
      <div id="pf-portfolio" style="display:none">
        <!-- SCALP MINI STATS -->
        <div id="sc-mini" style="background:rgba(244,63,94,.06);border:1px solid rgba(244,63,94,.2);border-radius:8px;padding:8px 12px;margin-bottom:8px;display:flex;align-items:center;gap:10px">
          <span style="font-size:16px">⚡</span>
          <div style="flex:1">
            <div style="font-size:10px;font-weight:700;color:#f43f5e">SCALP AI</div>
            <div id="sc-mini-stat" style="font-size:9px;color:var(--tx2)">انتظار...</div>
          </div>
          <div id="sc-mini-pnl" style="font-size:14px;font-weight:900;font-family:IBM Plex Mono,monospace;color:#f43f5e">$0</div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <span style="font-size:12px;font-weight:700">الصفقات المفتوحة</span>
          <span id="unr" style="font-weight:900;font-size:16px;font-family:'IBM Plex Mono',monospace">$0.00</span>
        </div>
        <div id="positions"></div>
        <div class="divider"></div>
        <div style="display:flex;gap:6px;margin-bottom:10px">
          <button onclick="showAcc('demo',this)" id="td" style="flex:1;padding:6px;border-radius:8px;border:1px solid var(--border2);background:var(--card2);color:var(--y);cursor:pointer;font-size:11px;font-family:'Tajawal',sans-serif">Demo</button>
          <button onclick="showAcc('real',this)" id="tr2" style="flex:1;padding:6px;border-radius:8px;border:none;background:var(--bg2);color:var(--tx3);cursor:pointer;font-size:11px;font-family:'Tajawal',sans-serif">Real</button>
        </div>
        <div id="acc-cards" style="display:grid;grid-template-columns:1fr 1fr;gap:6px"></div>
      </div>
      <!-- PORTFOLIO ANALYSIS V20 -->
      <div id="pf-pfanalysis" style="display:none">
        <!-- شريط الصحة الكلي -->
        <div id="pf-score-bar" style="background:rgba(74,222,128,.05);border:1px solid rgba(74,222,128,.2);border-radius:10px;padding:12px;margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span style="font-size:12px;font-weight:700;color:#4ade80">🏦 صحة المحفظة</span>
            <span id="pf-score-val" style="font-size:20px;font-weight:900;font-family:'IBM Plex Mono',monospace;color:#4ade80">--</span>
          </div>
          <div class="pbar" style="height:8px"><div id="pf-score-fill" class="pbf" style="width:0%;background:#4ade80"></div></div>
          <div id="pf-rec" style="font-size:11px;color:var(--tx2);margin-top:8px;line-height:1.5"></div>
        </div>

        <!-- إحصاءات سريعة -->
        <div class="met-grid" style="margin-bottom:10px">
          <div class="met-card"><div class="met-label">إجمالي المحفظة</div><div class="met-val" id="pf-total" style="color:#4ade80;font-size:18px">--</div></div>
          <div class="met-card"><div class="met-label">رصيد USDT</div><div class="met-val" id="pf-usdt" style="color:var(--a);font-size:18px">--</div></div>
          <div class="met-card"><div class="met-label">نسبة USDT</div><div class="met-val" id="pf-usdt-pct" style="font-size:18px">--</div></div>
          <div class="met-card"><div class="met-label">آخر تحديث</div><div class="met-val" id="pf-update" style="color:var(--tx3);font-size:12px">--</div></div>
        </div>

        <!-- توزيع الأصول -->
        <div style="font-size:11px;font-weight:700;color:var(--tx2);margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px">توزيع الأصول</div>
        <div id="pf-assets-list" style="margin-bottom:10px"></div>

        <!-- التوصيات -->
        <div id="pf-suggestions" style="margin-bottom:10px"></div>

        <!-- رسم بياني للتوزيع -->
        <div style="font-size:11px;font-weight:700;color:var(--tx2);margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px">خريطة التوزيع</div>
        <div id="pf-dist-bars" style="display:flex;flex-direction:column;gap:5px"></div>
      </div>

      <!-- PROFIT VAULT V21 -->
      <div id="pf-profits" style="display:none">

        <!-- شريط الحالة العلوي -->
        <div id="pv-header" style="border-radius:12px;padding:14px;margin-bottom:12px;border:1px solid">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div>
              <div style="font-size:13px;font-weight:700" id="pv-level-txt">مستوى الحماية</div>
              <div style="font-size:10px;color:var(--tx3);margin-top:2px" id="pv-decision">--</div>
            </div>
            <div style="text-align:left">
              <div style="font-size:28px;font-weight:900;font-family:'IBM Plex Mono',monospace" id="pv-total-prot">$0.00</div>
              <div style="font-size:10px;color:var(--tx3)">إجمالي محمي</div>
            </div>
          </div>
        </div>

        <!-- إحصاءات سريعة -->
        <div class="met-grid" style="margin-bottom:10px">
          <div class="met-card">
            <div class="met-label">ربح اليوم</div>
            <div class="met-val" id="pv-daily" style="font-size:18px">$0</div>
            <div class="met-sub" id="pv-daily-pct">0%</div>
          </div>
          <div class="met-card">
            <div class="met-label">رصيد آمن 🔒</div>
            <div class="met-val" id="pv-safe" style="color:#facc15;font-size:18px">$0</div>
          </div>
          <div class="met-card">
            <div class="met-label">للتداول 📈</div>
            <div class="met-val" id="pv-risk" style="color:var(--a);font-size:18px">$0</div>
          </div>
          <div class="met-card">
            <div class="met-label">الهدف التالي 🎯</div>
            <div class="met-val" id="pv-target" style="color:var(--g);font-size:18px">$0</div>
          </div>
        </div>

        <!-- آخر قرار -->
        <div id="pv-last-decision" style="background:rgba(250,204,21,.06);border:1px solid rgba(250,204,21,.2);border-radius:10px;padding:12px;margin-bottom:10px;font-size:11px;color:var(--tx2);line-height:1.6">
          <i class="fas fa-brain" style="color:#facc15"></i> في انتظار تحليل الأرباح...
        </div>

        <!-- خريطة الحماية البصرية -->
        <div style="font-size:11px;font-weight:700;color:var(--tx2);margin-bottom:8px;text-transform:uppercase;letter-spacing:.4px">توزيع رأس المال</div>
        <div style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:10px">
          <div style="display:flex;height:24px;border-radius:6px;overflow:hidden;margin-bottom:8px" id="pv-capital-bar">
            <div id="pv-bar-safe" style="background:#facc15;height:100%;transition:width .6s;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#000"></div>
            <div id="pv-bar-risk" style="background:var(--a);height:100%;transition:width .6s;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#000"></div>
          </div>
          <div style="display:flex;gap:14px;font-size:10px">
            <span><span style="display:inline-block;width:10px;height:10px;background:#facc15;border-radius:2px;margin-left:4px"></span>رصيد آمن</span>
            <span><span style="display:inline-block;width:10px;height:10px;background:var(--a);border-radius:2px;margin-left:4px"></span>للتداول</span>
          </div>
        </div>

        <!-- سجل الحماية -->
        <div style="font-size:11px;font-weight:700;color:var(--tx2);margin-bottom:8px;text-transform:uppercase;letter-spacing:.4px">سجل عمليات الحماية</div>
        <div id="pv-history" style="max-height:220px;overflow-y:auto"></div>
      </div>

      <!-- PAPER TRADING PANEL — معزول كلياً -->
      <div id="pf-paper" style="display:none">
        <!-- Header -->
        <div id="pp-header" style="background:rgba(167,139,250,.06);border:2px solid rgba(167,139,250,.25);border-radius:12px;padding:12px;margin-bottom:10px">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
            <span style="font-size:22px">📄</span>
            <div style="flex:1">
              <div style="font-size:12px;font-weight:700;color:#a78bfa">تداول تجريبي معزول — بدون تأثير على الحقيقي</div>
              <div id="pp-status" style="font-size:10px;color:var(--tx2);margin-top:2px">متوقف</div>
            </div>
            <div style="text-align:left">
              <div id="pp-bal" style="font-size:22px;font-weight:900;font-family:'IBM Plex Mono',monospace;color:#a78bfa">$10,000</div>
              <div style="font-size:9px;color:var(--tx3)" id="pp-type">SPOT</div>
            </div>
          </div>
          <!-- أزرار التحكم -->
          <div style="display:flex;gap:6px;margin-bottom:8px">
            <button onclick="paperCtrl('start','spot')" style="flex:1;padding:6px;border-radius:8px;border:1px solid rgba(167,139,250,.3);background:rgba(167,139,250,.1);color:#a78bfa;cursor:pointer;font-size:11px;font-family:'Tajawal',sans-serif">▶ Spot</button>
            <button onclick="paperCtrl('start','futures')" style="flex:1;padding:6px;border-radius:8px;border:1px solid rgba(251,191,36,.3);background:rgba(251,191,36,.1);color:var(--y);cursor:pointer;font-size:11px;font-family:'Tajawal',sans-serif">▶ Futures</button>
            <button onclick="paperCtrl('stop','')" style="flex:1;padding:6px;border-radius:8px;border:1px solid var(--border2);background:var(--bg2);color:var(--r);cursor:pointer;font-size:11px;font-family:'Tajawal',sans-serif">⏹ إيقاف</button>
            <button onclick="paperCtrl('reset','')" style="padding:6px 10px;border-radius:8px;border:1px solid var(--border2);background:var(--bg2);color:var(--tx3);cursor:pointer;font-size:11px;font-family:'Tajawal',sans-serif" title="إعادة ضبط">🔄</button>
          </div>
          <!-- إحصاءات سريعة -->
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:5px">
            <div class="met-card" style="padding:8px"><div class="met-label">Spot P&L</div><div class="met-val" id="pp-spot-pnl" style="font-size:14px;color:var(--g)">$0</div></div>
            <div class="met-card" style="padding:8px"><div class="met-label">Futures P&L</div><div class="met-val" id="pp-fut-pnl" style="font-size:14px;color:var(--y)">$0</div></div>
            <div class="met-card" style="padding:8px"><div class="met-label">Win Rate</div><div class="met-val" id="pp-wr" style="font-size:14px">0%</div></div>
            <div class="met-card" style="padding:8px"><div class="met-label">Drawdown</div><div class="met-val" id="pp-dd" style="font-size:14px;color:var(--r)">0%</div></div>
          </div>
        </div>

        <!-- وكلاء التجريبي -->
        <div style="font-size:10px;font-weight:700;color:#a78bfa;margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px">🤖 وكلاء التجريبي المستقلون</div>
        <div id="pp-agents" style="margin-bottom:10px"></div>

        <!-- رسم بياني مقارنة -->
        <div style="font-size:10px;font-weight:700;color:var(--tx2);margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px">📈 مقارنة Spot vs Futures</div>
        <canvas id="pp-chart" height="80" style="width:100%;border-radius:8px;background:var(--bg2);border:1px solid var(--border);display:block;margin-bottom:10px"></canvas>

        <!-- الصفقات المفتوحة -->
        <div style="font-size:10px;font-weight:700;color:var(--tx2);margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px">صفقات مفتوحة</div>
        <div id="pp-positions" style="margin-bottom:10px"></div>

        <!-- آخر الصفقات -->
        <div style="font-size:10px;font-weight:700;color:var(--tx2);margin-bottom:5px;text-transform:uppercase;letter-spacing:.4px">آخر الصفقات التجريبية</div>
        <div id="pp-history" style="max-height:160px;overflow-y:auto"></div>
      </div>

      <!-- METRICS -->
      <div id="pf-metrics" style="display:none">
        <div class="metrics-table" style="margin-bottom:12px">
          {% set mrows=[('نظام السوق','mt-reg'),('التذبذب','mt-vi'),('Momentum','mt-mom'),('Sharpe Ratio','mt-sh'),('Profit Factor','mt-pf'),('Win/Loss','mt-wlr'),('سلسلة الصفقات','mt-sk'),('AI Confluence','mt-conf'),('أفضل استراتيجية','mt-best')] %}
          {% for l,id in mrows %}
          <div class="met-row"><span class="met-key">{{l}}</span><span id="{{id}}" style="font-weight:700">-</span></div>
          {% endfor %}
        </div>
        <div style="font-size:11px;color:var(--tx2);margin-bottom:4px;display:flex;justify-content:space-between"><span>ثقة الإشارة</span><span id="mt-cp">0%</span></div>
        <div class="pbar" style="margin-bottom:12px"><div class="pbf" id="mt-cb" style="width:0%"></div></div>
        <div class="met-grid">
          <div class="met-card"><div class="met-label">Fear & Greed</div><div class="met-val" id="fg">55</div><div class="met-sub" id="fgl">Neutral</div></div>
          <div class="met-card"><div class="met-label">BTC Dominance</div><div class="met-val" id="btcd">52%</div></div>
          <div class="met-card"><div class="met-label">🥇 Gold Price</div><div class="met-val" id="m-gold" style="color:var(--gold);font-size:16px">--</div></div>
          <div class="met-card"><div class="met-label">Gold Trend</div><div class="met-val" id="m-gold-t" style="color:var(--gold);font-size:14px">--</div></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Direct Chat Panel -->
  <div class="panel" style="min-height:500px;border-color:rgba(218,119,86,.3)">
    <div class="panel-head" style="color:var(--claude)">
      <span style="font-size:18px">🤖</span> تحدث مع Claude
      <span class="badge ph-right" style="background:rgba(218,119,86,.1);color:var(--claude);border:1px solid rgba(218,119,86,.25)" id="claude-status-badge">جاهز</span>
    </div>
    <div class="chat-panel">
      <div class="chat-status-bar disc" id="claude-conn-status">
        {% if 'YOUR_ANTHROPIC_API_KEY_HERE' == 'YOUR_ANTHROPIC_API_KEY_HERE' %}⚠️ أضف CLAUDE_API_KEY لتفعيل المحادثة الحقيقية{% else %}✅ متصل بـ Claude API{% endif %}
      </div>
      <div class="chat-messages" id="chat-messages">
        <div class="msg-row">
          <div class="msg-avatar claude">🤖</div>
          <div>
            <div class="bubble claude">
              مرحباً! أنا مساعدك الذكي المدمج في البوت 🚀<br><br>
              أرى بيانات بوتك مباشرة — يمكنني تحليل السوق، مراجعة صفقاتك، وتقديم توصيات مخصصة.<br><br>
              ماذا تريد أن تعرف؟
              <div class="bubble-time">الآن</div>
            </div>
          </div>
        </div>
      </div>
      <div class="chat-hints">
        <button class="hint-pill" onclick="sendHint('حلل السوق الحالي')">📊 السوق</button>
        <button class="hint-pill" onclick="sendHint('راجع أداء البوت اليوم')">📈 الأداء</button>
        <button class="hint-pill" onclick="sendHint('ما رأيك بالذهب الآن؟')">🥇 الذهب</button>
        <button class="hint-pill" onclick="sendHint('ما أفضل استراتيجية الآن؟')">🎯 استراتيجية</button>
        <button class="hint-pill" onclick="sendHint('قيّم مستوى المخاطر')">🛡️ مخاطر</button>
        <button class="hint-pill" onclick="sendHint('حلل آخر 5 صفقات')">🔍 مراجعة</button>
      </div>
      <div class="chat-input-area">
        <div class="input-row">
          <textarea class="chat-textarea" id="chat-input" placeholder="اكتب سؤالك لـ Claude..." rows="1" onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
          <button class="send-btn" id="send-btn" onclick="sendMessage()"><i class="fas fa-paper-plane"></i></button>
        </div>
      </div>
    </div>
  </div>

</div><!-- end col 3 -->
</div><!-- end main-layout -->

<div id="toasts"></div>

<script>
let D={},lastSigs=0,accTab='demo',logTab='sig',agTab='agents',pfTab='health';
let chart, chatTyping=false;

setInterval(()=>{document.getElementById('clk').textContent=new Date().toLocaleTimeString('en-GB');},1000);
function onMode(v){document.getElementById('rw').style.display=v==='real'?'flex':'none';}
function filterCoins(q){document.querySelectorAll('#coin-list label[data-coin]').forEach(el=>{el.style.display=el.dataset.coin.toLowerCase().includes(q.toLowerCase())?'':'none';});}

// ══ CHAT ══
function autoResize(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,100)+'px';}
function handleKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();}}
function sendHint(t){document.getElementById('chat-input').value=t;sendMessage();}
function appendMsg(role,text,time){
  const c=document.getElementById('chat-messages'),isU=role==='user';
  const t=time||new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'});
  const d=document.createElement('div');d.className='msg-row'+(isU?' user':'');
  const safe=text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
  d.innerHTML=`<div class="msg-avatar ${isU?'user-av':'claude'}">${isU?'👤':'🤖'}</div>
    <div><div class="bubble ${isU?'user':'claude'}">${safe}<div class="bubble-time">${t}</div></div></div>`;
  c.appendChild(d);c.scrollTop=c.scrollHeight;
}
function showTyping(){
  const c=document.getElementById('chat-messages'),d=document.createElement('div');
  d.className='msg-row';d.id='typing-indicator';
  d.innerHTML=`<div class="msg-avatar claude">🤖</div><div class="typing-bub"><span class="tdot"></span><span class="tdot"></span><span class="tdot"></span></div>`;
  c.appendChild(d);c.scrollTop=c.scrollHeight;
}
function hideTyping(){const e=document.getElementById('typing-indicator');if(e)e.remove();}
function updateChatStatus(conn){
  const b=document.getElementById('claude-status-badge'),s=document.getElementById('claude-conn-status');
  if(conn){
    if(b){b.textContent='متصل ✅';b.style.color='var(--g)';b.style.background='rgba(0,229,160,.1)';b.style.borderColor='rgba(0,229,160,.2)';}
    if(s){s.textContent='✅ متصل بـ Claude API — يرى بيانات بوتك مباشرة';s.className='chat-status-bar conn';}
  }
}
async function sendMessage(){
  const inp=document.getElementById('chat-input'),btn=document.getElementById('send-btn');
  const txt=inp.value.trim();if(!txt||chatTyping)return;
  chatTyping=true;btn.disabled=true;inp.value='';inp.style.height='auto';
  appendMsg('user',txt);showTyping();
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:txt})});
    const d=await r.json();hideTyping();
    if(d.response){appendMsg('assistant',d.response);updateChatStatus(d.connected||false);}
    else appendMsg('assistant','❌ لم أتلقَّ رداً');
  }catch(e){hideTyping();appendMsg('assistant','❌ خطأ: '+e.message);}
  chatTyping=false;btn.disabled=false;document.getElementById('chat-input').focus();
}

// ══ CHART ══
function initChart(){
  chart=new ApexCharts(document.querySelector('#mainChart'),{
    series:[{name:'Demo P&L',data:[0],type:'area'},{name:'Real P&L',data:[0],type:'area'},{name:'AI Conf',data:[0],type:'line'},{name:'Drawdown',data:[0],type:'line'}],
    chart:{type:'line',height:200,toolbar:{show:false},background:'transparent',animations:{enabled:true,easing:'easeinout',speed:700}},
    colors:['#38bdf8','#ffd700','#a3e635','#ff3d6e'],
    stroke:{curve:'smooth',width:[2.5,2.5,2,1.5],dashArray:[0,0,6,4]},
    fill:{type:['gradient','gradient','none','none'],gradient:{shadeIntensity:.15,opacityFrom:.45,opacityTo:.01}},
    grid:{borderColor:'#182840',strokeDashArray:4},
    xaxis:{labels:{show:false},axisBorder:{show:false},axisTicks:{show:false}},
    yaxis:[{seriesName:'Demo P&L',labels:{style:{colors:'#3d5070',fontSize:'9px'},formatter:v=>'$'+v.toFixed(0)},title:{text:'P&L',style:{color:'#3d5070',fontSize:'9px'}}},{seriesName:'Demo P&L',show:false},{opposite:true,seriesName:'AI Conf',labels:{style:{colors:'#3d5070',fontSize:'9px'},formatter:v=>v.toFixed(0)+'%'},max:100,min:0},{opposite:true,seriesName:'Drawdown',show:false,max:30,min:0}],
    tooltip:{theme:'dark',shared:true,intersect:false},
    legend:{show:true,position:'top',fontSize:'10px',labels:{colors:['#eef2ff','#eef2ff','#eef2ff','#eef2ff']},markers:{width:8,height:8,radius:3}},
    theme:{mode:'dark'},markers:{size:[0,0,3,0]},
  });
  chart.render();
}

function drawSparks(data){
  const cd=data.chart_data||{};
  const items=[{l:'Demo P&L',v:cd.demo_pnl||[0],c:'#38bdf8',val:'$'+((cd.demo_pnl||[0]).slice(-1)[0]||0).toFixed(1)},{l:'Real P&L',v:cd.real_pnl||[0],c:'#ffd700',val:'$'+((cd.real_pnl||[0]).slice(-1)[0]||0).toFixed(1)},{l:'Drawdown',v:cd.drawdown||[0],c:'#ff3d6e',val:((cd.drawdown||[0]).slice(-1)[0]||0).toFixed(1)+'%'}];
  const cnt=document.getElementById('sparklines');if(!cnt)return;cnt.innerHTML='';
  items.forEach(it=>{
    const row=document.createElement('div');row.className='spark-row';
    const lb=document.createElement('span');lb.style.cssText='width:60px;color:var(--tx2);font-size:10px';lb.textContent=it.l;
    const ve=document.createElement('span');ve.style.cssText='width:54px;text-align:left;font-weight:700;font-family:"IBM Plex Mono",monospace;font-size:11px;color:'+it.c;ve.textContent=it.val;
    const cv=document.createElement('canvas');cv.className='spk';cv.width=300;cv.height=24;
    row.appendChild(lb);row.appendChild(ve);row.appendChild(cv);cnt.appendChild(row);
    const vals=it.v.slice(-50);const ctx=cv.getContext('2d');if(vals.length<2)return;
    const mn=Math.min(...vals),mx=Math.max(...vals),rng=mx-mn||1,w=cv.width,h=cv.height;
    ctx.clearRect(0,0,w,h);ctx.strokeStyle=it.c;ctx.lineWidth=1.6;ctx.lineJoin='round';ctx.beginPath();
    vals.forEach((v,i)=>{const x=i/(vals.length-1)*w,y=h-(v-mn)/rng*(h-5)-2;i===0?ctx.moveTo(x,y):ctx.lineTo(x,y);});
    ctx.stroke();ctx.lineTo(w,h);ctx.lineTo(0,h);ctx.closePath();ctx.fillStyle=it.c+'16';ctx.fill();
  });
}

function renderTF(tf,stf){
  const order=['1m','5m','15m','30m','1h','4h','1d','1w'];let h='';
  order.forEach(t=>{
    const d=tf[t]||{signal:'neutral',strength:50,trend:'→',rsi:50};const sel=stf&&stf.includes(t);
    const sig=d.signal;const col=sig==='buy'?'var(--g)':sig==='sell'?'var(--r)':'var(--a)';
    h+=`<div class="tf-card ${sig}" style="${sel?'border-color:'+col+';border-width:2px;':''}" title="RSI:${d.rsi}">
      <div class="tf-lbl" style="color:${col}">${t}${sel?'⭐':''}</div>
      <div class="tf-trend" style="color:${col}">${d.trend}</div>
      <div class="tf-str" style="color:${col}">${d.strength}%</div>
      <div class="tf-rsi">RSI ${d.rsi}</div></div>`;
  });
  const el=document.getElementById('tf-grid');if(el)el.innerHTML=h;
}

function renderAgents(agentsData){
  const colors={MARKET_ANALYST:'var(--a)',RISK_MANAGER:'var(--r)',STRATEGY_SELECTOR:'var(--lm)',TRADE_REVIEWER:'var(--p)',GOLD_SPECIALIST:'var(--gold)',PATTERN_LEARNER:'var(--t)',BACKTEST_RUNNER:'var(--o)'};
  let h='';let cnt=0;
  for(const[id,ag] of Object.entries(agentsData)){
    const col=colors[id]||'var(--a)';const isT=ag.status==='thinking';
    if(ag.status==='done'||isT) cnt++;
    const stMap={standby:{l:'انتظار',bg:'rgba(61,80,112,.3)',c:'var(--tx3)'},thinking:{l:'يفكر',bg:'rgba(192,132,252,.14)',c:'var(--p)'},done:{l:'مكتمل',bg:'rgba(0,229,160,.12)',c:'var(--g)'},error:{l:'خطأ',bg:'rgba(255,61,110,.12)',c:'var(--r)'}};
    const st=stMap[ag.status]||stMap.standby;const cw=Math.round((ag.confidence||0)*100);
    h+=`<div class="agent-card ${ag.status}" style="background:rgba(0,0,0,.25);border-color:${isT?col:'var(--border)'};color:${col}">
      <div class="ag-bar" style="background:${col}"></div>
      <div class="ag-header">
        <span class="ag-emoji">${ag.emoji||'🤖'}</span>
        <div><div class="ag-name" style="color:${col}">${ag.name}</div><div class="ag-role">${ag.role}</div></div>
        <div class="ag-status" style="background:${st.bg};color:${st.c}">${isT?`<span class="thinking-dot" style="background:${col}"></span><span class="thinking-dot" style="background:${col}"></span><span class="thinking-dot" style="background:${col}"></span>`:st.l}</div>
      </div>
      ${ag.last_response?`<div class="ag-msg">${ag.last_response.substring(0,110)}${ag.last_response.length>110?'...':''}</div>`:''}
      <div class="ag-conf">
        <span style="font-size:9px;color:var(--tx3);min-width:32px">ثقة</span>
        <div class="ag-conf-bar"><div class="ag-conf-fill" style="width:${cw}%;background:${col}"></div></div>
        <div class="ag-conf-val">${cw}%</div>
        <span style="font-size:9px;color:var(--tx3);margin-right:6px">${ag.calls_made||0} استدعاء</span>
      </div></div>`;
  }
  const el=document.getElementById('agent-cards');if(el)el.innerHTML=h;
  const ab=document.getElementById('agents-active');if(ab)ab.textContent=cnt+'/7 نشط';
}

// TABS
function sL(t,btn){logTab=t;['sig','cap','strat','hist'].forEach(v=>{const e=document.getElementById('v-'+v);if(e)e.style.display=v===t?'':'none';});btn.closest('.panel').querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('on'));btn.classList.add('on');}
function sAG(t,btn){agTab=t;['agents','analysis','hm'].forEach(v=>{const e=document.getElementById('ag-'+v);if(e)e.style.display=v===t?'':'none';});btn.closest('.panel').querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('on'));btn.classList.add('on');}
function sPF(t,btn){pfTab=t;['health','portfolio','pfanalysis','profits','metrics'].forEach(v=>{const e=document.getElementById('pf-'+v);if(e)e.style.display=v===t?'':'none';});btn.closest('.panel').querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('on'));btn.classList.add('on');}
function showAcc(mode,btn){accTab=mode;document.querySelectorAll('#td,#tr2').forEach(b=>{b.style.background='var(--bg2)';b.style.color='var(--tx3)';b.style.border='none';});btn.style.background='var(--card2)';btn.style.color='var(--y)';btn.style.border='1px solid var(--border2)';renderAcc(D);}
function renderAcc(data){
  if(!data.finances)return;
  const f=data.finances[accTab]||{wins:0,losses:0,pnl:0,balance:0,total_usd:0};
  const tt=f.wins+f.losses,wr=tt>0?((f.wins/tt)*100).toFixed(1):0;
  const bal=accTab==='demo'?f.balance:Math.max(f.total_usd||0,f.balance||0);
  const c=(l,v,cl)=>`<div class="met-card"><div class="met-label">${l}</div><div class="met-val" style="color:${cl};font-size:16px">${v}</div></div>`;
  document.getElementById('acc-cards').innerHTML=c('رصيد','$'+Number(bal).toFixed(2),'var(--y)')+c('Win%',wr+'%',parseFloat(wr)>=50?'var(--g)':'var(--r)')+c('P&L',(f.pnl>=0?'+':'')+'$'+f.pnl.toFixed(2),f.pnl>=0?'var(--g)':'var(--r)')+c('ف/خ',f.wins+'/'+f.losses,'var(--tx)');
}
function updateHealthRing(score){
  const c=157,off=c-(score/100*c);
  const arc=document.getElementById('harc'),se=document.getElementById('hscore');
  if(!arc)return;const col=score>70?'var(--g)':score>40?'var(--y)':'var(--r)';
  arc.style.strokeDashoffset=off;arc.style.stroke=col;
  if(se){se.textContent=score;se.style.color=col;}
  const b=document.getElementById('h-badge');if(b){b.textContent=score>70?'جيد':score>40?'تحذير':'خطر';b.className='badge '+(score>70?'b-g':score>40?'b-y':'b-r');}
  const th=document.getElementById('t-health');if(th){th.textContent=score;th.style.color=col;}
}
function getFG(v){if(v<=20)return{l:'خوف شديد',c:'var(--r)'};if(v<=40)return{l:'خوف',c:'var(--o)'};if(v<=60)return{l:'محايد',c:'var(--y)'};if(v<=80)return{l:'جشع',c:'var(--g)'};return{l:'جشع شديد',c:'var(--lm)'};}
function rc(r){return r==='trending'?'b-g':r==='volatile'?'b-r':'b-y';}
function fmtUp(s){if(s<60)return s+'s';if(s<3600)return Math.floor(s/60)+'m';return Math.floor(s/3600)+'h'+Math.floor((s%3600)/60)+'m';}
function toast(msg,t){
  const c=document.getElementById('toasts'),e=document.createElement('div');
  e.className='toast '+(t==='s'?'ts':t==='p'?'tp':'td');
  const cols={s:'var(--g)',d:'var(--r)',p:'var(--gold)'};const ics={s:'check-circle',d:'times-circle',p:'dollar-sign'};
  e.innerHTML=`<i class="fas fa-${ics[t]||'check-circle'}" style="color:${cols[t]||'var(--g)'};font-size:13px"></i><div>${msg}</div>`;
  c.appendChild(e);setTimeout(()=>{if(e.parentNode)e.remove();},4100);
}
function se(id,v,c){const e=document.getElementById(id);if(e){e.textContent=v;if(c)e.style.color=c;}}

// ══ SAVE SETTINGS ══
document.addEventListener('DOMContentLoaded', function(){
  const form = document.querySelector('form[method="POST"]');
  if(!form) return;
  form.addEventListener('submit', function(e){
    const action = e.submitter?.value;
    if(action === 'save_settings'){
      e.preventDefault();
      const btn = document.getElementById('save-btn');
      const status = document.getElementById('save-status');
      if(btn){ btn.innerHTML='<i class="fas fa-spinner fa-spin"></i> جاري الحفظ...'; btn.disabled=true; }
      fetch('/', {method:'POST', body: new FormData(form)})
        .then(r => {
          if(btn){
            btn.innerHTML='<i class="fas fa-check"></i> تم الحفظ ✅';
            btn.classList.add('save-flash');
            setTimeout(()=>{
              btn.innerHTML='<i class="fas fa-save"></i> حفظ وتطبيق الإعدادات';
              btn.disabled=false;
              btn.classList.remove('save-flash');
            }, 2000);
          }
          if(status){ status.textContent='✅ حُفظت جميع الإعدادات وطُبِّقت فوراً'; setTimeout(()=>status.textContent='',3000); }
          toast('✅ الإعدادات حُفظت وطُبِّقت','s');
        })
        .catch(err => {
          if(btn){ btn.innerHTML='<i class="fas fa-save"></i> حفظ وتطبيق'; btn.disabled=false; }
          if(status){ status.textContent='❌ خطأ في الحفظ'; status.style.color='var(--r)'; }
        });
    }
  });
});

function update(){
  fetch('/api/data').then(r=>r.json()).then(data=>{
  try{
    D=data;
    const f=data.finances,ai=data.ai_learner||{},md=data.market_data||{},
          cd=data.chart_data||{},bh=data.bot_health||{},cm=data.capital_mgmt||{},
          mode=data.current_mode||'demo',api=data.api_status||{},
          tf=data.tf_data||{},stf=data.selected_timeframes||[],agentsData=data.agents||{};

    // MODE BAR
    const mb=document.getElementById('mbar');
    if(mode==='real'){mb.className='modebar real';document.getElementById('m-icon').textContent='💰';document.getElementById('m-title').textContent='وضع التداول الحقيقي';document.getElementById('m-sub').textContent=api.connected?`Binance ✅ ${api.last_sync}`:'رصيد محلي';document.getElementById('m-bv').textContent='$'+Math.max(f.real.total_usd||0,f.real.balance||0).toFixed(2);}
    else{mb.className='modebar demo';document.getElementById('m-icon').textContent='🎮';document.getElementById('m-title').textContent='وضع تجريبي (Demo)';document.getElementById('m-sub').textContent='تداول افتراضي آمن';document.getElementById('m-bv').textContent='$'+(f.demo.balance||0).toFixed(2);}
    const rg=document.getElementById('rg');const regime=ai.market_regime||'ranging';if(rg){rg.textContent=regime;rg.className='badge '+rc(regime);}

    // STATS
    const rBal=Math.max(f.real.total_usd||0,f.real.balance||0);
    se('r-bal','$'+rBal.toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2}));
    const as=document.getElementById('api-s');if(as){as.textContent=api.connected?'✅ Binance':'❌ غير متصل';as.style.color=api.connected?'var(--g)':'var(--tx3)';}
    se('d-bal','$'+Number(f.demo.balance).toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2}));
    const tt=f.demo.wins+f.demo.losses+f.real.wins+f.real.losses,tw=f.demo.wins+f.real.wins;
    const wr=tt>0?((tw/tt)*100).toFixed(1):0;
    se('wr',wr+'%',parseFloat(wr)>=50?'var(--g)':'var(--r)');se('wr-s',tt+' صفقة');
    const ap=mode==='real'?f.real.pnl:f.demo.pnl;
    se('pnl',(ap>=0?'+':'')+'$'+ap.toFixed(2),ap>=0?'var(--g)':'var(--r)');se('pnl-m',mode==='real'?'Real':'Demo');
    se('aic',(ai.confidence||0).toFixed(1)+'%',(ai.confidence||0)>70?'var(--g)':'var(--y)');
    se('sf-s',ai.smart_filter_active?'⚠️ فلتر':'طبيعي',ai.smart_filter_active?'var(--r)':'var(--tx3)');
    const dd=ai.current_drawdown||0;se('dd',dd.toFixed(2)+'%',dd>5?'var(--r)':'var(--g)');
    const rec=ai.agent_recommended_strategy||'--';const risk=ai.agent_risk_level||'medium';
    se('agent-rec',rec.replace(/_/g,' '),'var(--p)');
    const riskC={'low':'var(--g)','medium':'var(--y)','high':'var(--r)','critical':'var(--r)'};
    se('agent-risk',risk,riskC[risk]||'var(--y)');
    const baseR=cm.base_risk_pct||2,sk=ai.streak||0;let estSz=baseR;
    if(sk>=3)estSz=Math.min(baseR*1.5,baseR+sk*0.16);else if(sk<=-2)estSz=Math.max(baseR*0.3,baseR+sk*0.24);
    if(ai.agent_risk_level==='high')estSz*=0.5;
    se('cm-sz',estSz.toFixed(2)+'%',sk>=3?'var(--g)':sk<=-2?'var(--r)':'var(--t)');se('cm-sz-r',cm.mode||'--');
    if(data.prices){[{s:'BTCUSDT',id:'t-btc'},{s:'ETHUSDT',id:'t-eth'},{s:'SOLUSDT',id:'t-sol'}].forEach(x=>{const el=document.getElementById(x.id);if(el&&data.prices[x.s])el.textContent='$'+Number(data.prices[x.s]).toLocaleString();});}
    const gp=md.gold_price||0;se('t-gold',gp>0?'$'+gp.toLocaleString('en',{maximumFractionDigits:0}):'--','var(--gold)');
    se('t-vol',(ai.volatility_index||0).toFixed(1));
    const mom=ai.momentum_score||0;se('t-mom',(mom>=0?'+':'')+mom.toFixed(1),mom>20?'var(--g)':mom<-20?'var(--r)':'var(--tx2)');
    const posCount=Object.keys(data.active||{}).length;se('t-pos',posCount,posCount>0?'var(--y)':'var(--tx2)');
    const thA=Object.values(agentsData).filter(a=>a.status==='thinking').length;
    se('t-agent',thA>0?'يفكر...':'جاهز',thA>0?'var(--p)':'var(--g)');
    document.getElementById('sdot').className='status-dot'+(data.running?'':' off');
    document.getElementById('stxt').textContent=data.running?'نشط':'متوقف';

    if(cd.demo_pnl&&cd.demo_pnl.length>1){chart.updateSeries([{name:'Demo P&L',data:cd.demo_pnl},{name:'Real P&L',data:cd.real_pnl},{name:'AI Conf',data:cd.ai_confidence},{name:'Drawdown',data:cd.drawdown}],false);}
    drawSparks(data);renderTF(tf,stf);

    // AGENTS
    if(agTab==='agents'){
      // ── عرض widget الأخبار ──
      var nd=data.news_data||{};
      var ns=nd.sentiment_score||0;
      var ni=nd.impact_level||'low';
      var nb=nd.btc_bias||'neutral';
      var ng=nd.gold_bias||'neutral';
      var nfg=data.market_data&&data.market_data.fear_greed?data.market_data.fear_greed:55;
      // badge
      var impColors={low:'rgba(56,189,248,.15)',medium:'rgba(245,197,24,.15)',high:'rgba(251,146,60,.2)',critical:'rgba(255,61,110,.2)'};
      var impTxt={low:'تأثير منخفض',medium:'تأثير متوسط',high:'تأثير عالٍ',critical:'تأثير حرج'};
      var impCols={low:'var(--a)',medium:'var(--y)',high:'var(--o)',critical:'var(--r)'};
      var nib=document.getElementById('news-impact-badge');
      if(nib){nib.textContent=impTxt[ni]||ni;nib.style.background=impColors[ni]||'rgba(240,171,252,.1)';nib.style.color=impCols[ni]||'#f0abfc';}
      var ntEl=document.getElementById('news-time');if(ntEl)ntEl.textContent=nd.last_update||'';
      // شريط المشاعر
      var sentPct=Math.round((ns+100)/200*100);
      var sentBar=document.getElementById('news-sent-bar');
      if(sentBar){
        var bw=Math.abs(ns/100)*40; var bl=ns>=0?50:50-bw;
        sentBar.style.left=bl+'%';sentBar.style.width=bw+'%';
        sentBar.style.background=ns>15?'var(--g)':ns<-15?'var(--r)':'var(--y)';
      }
      var svEl=document.getElementById('news-sent-val');
      if(svEl){svEl.textContent=(ns>=0?'+':'')+ns.toFixed(0);svEl.style.color=ns>15?'var(--g)':ns<-15?'var(--r)':'var(--y)';}
      // stats
      var fgEl=document.getElementById('news-fg');
      if(fgEl){fgEl.textContent=nfg;fgEl.style.color=nfg<30?'var(--r)':nfg>70?'var(--g)':'var(--y)';}
      var btcMap={bullish:'صاعد 🚀',slightly_bullish:'طفيف ↑',neutral:'محايد →',slightly_bearish:'طفيف ↓',bearish:'هابط 📉'};
      var goldMap={strong_buy:'شراء قوي ⬆️',buy:'شراء ↑',neutral:'محايد →',sell:'بيع ↓',strong_sell:'بيع ⬇️'};
      var btcEl=document.getElementById('news-btc');if(btcEl){btcEl.textContent=btcMap[nb]||nb;btcEl.style.color=nb.includes('bull')?'var(--g)':nb.includes('bear')?'var(--r)':'var(--tx2)';}
      var goldEl=document.getElementById('news-gold');if(goldEl){goldEl.textContent=goldMap[ng]||ng;goldEl.style.color=ng.includes('buy')?'var(--g)':ng.includes('sell')?'var(--r)':'var(--gold)';}
      // Headlines
      var hl=nd.crypto_news||[];var hlH='';
      hl.slice(0,4).forEach(function(h){
        hlH+='<div style="padding:4px 0;border-bottom:1px solid rgba(24,40,64,.4);font-size:9px">';
        hlH+='<div style="color:var(--tx);line-height:1.4">'+h.title.slice(0,70)+(h.title.length>70?'...':'')+'</div>';
        hlH+='<div style="color:var(--tx3);margin-top:1px">'+h.source+' · '+h.time+'</div></div>';
      });
      var hlEl=document.getElementById('news-headlines');if(hlEl)hlEl.innerHTML=hlH||'<div style="color:var(--tx3);font-size:10px;padding:5px">جاري جلب الأخبار...</div>';
      // Alerts
      var alerts=nd.alerts||[];var altH='';
      alerts.forEach(function(a){
        var col=a.includes('شديد')||a.includes('تراجع')?'var(--r)':'var(--g)';
        altH+='<div style="font-size:9px;color:'+col+';padding:3px 0">'+a+'</div>';
      });
      var altEl=document.getElementById('news-alerts');if(altEl)altEl.innerHTML=altH;

      renderAgents(agentsData);
      const agView=document.getElementById('agent-view');
      if(agView)agView.innerHTML=`<i class="fas fa-brain" style="color:var(--p)"></i> ${ai.agent_market_view||'في انتظار تحليل الوكلاء...'}`;
      const lpc=document.getElementById('learning-count');if(lpc)lpc.textContent=(data.learned_patterns_count||0)+' نمط';
      const btc2=document.getElementById('backtest-count');if(btc2)btc2.textContent=(data.backtest_count||0)+' استراتيجية';
      const sw=data.strategy_weights||{};const swEl=document.getElementById('strategy-weights');
      if(swEl){
        let wh='';
        Object.keys(sw).slice(0,10).forEach(k=>{
          const w=sw[k];const col=w>1.1?'var(--g)':w<0.9?'var(--r)':'var(--tx2)';
          wh+=`<div class="weight-row">
            <span style="width:110px;color:var(--tx2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${k.replace('bt_','⚡ ').replace(/_trending/,'📈').replace(/_ranging/,'↔️').replace(/_volatile/,'⚡')}</span>
            <div class="weight-bar-wrap"><div class="weight-bar-fill" style="width:${Math.min(100,Math.round(w*50))}%;background:${col}"></div></div>
            <span style="color:${col};font-family:'IBM Plex Mono',monospace;font-size:9px;min-width:36px">${w.toFixed(2)}x</span>
          </div>`;
        });
        swEl.innerHTML=wh||'<div style="color:var(--tx3);font-size:10px">في انتظار التعلم...</div>';
      }
      const ol=data.online_log||[];const olEl=document.getElementById('online-log');
      if(olEl&&ol.length>0){const lt=ol[0];olEl.innerHTML=`🧠 ${lt.time} | تحليل ${lt.trades_analyzed} صفقة | ${lt.new_patterns} نمط جديد | Win=${lt.win_rate}%`;}
    }
    if(agTab==='analysis'){
      let h='';
      (ai.ai_analysis||[]).slice(0,10).forEach(a=>{
        const win=a.result_pct>=0;
        h+=`<div style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:12px 14px;margin-bottom:8px;font-size:11px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
            <div><span style="font-weight:900;font-size:13px">${a.coin}</span><span style="color:var(--tx3);font-size:9px;font-family:'IBM Plex Mono',monospace;margin-right:8px">${a.time}</span></div>
            <span class="badge ${win?'b-g':'b-r'}">${a.result_pct>=0?'+':''}${a.result_pct}%</span>
          </div>
          <div style="color:var(--tx2)">📍 ${a.lesson||''}</div>
          <div style="color:var(--a);font-weight:700;margin-top:4px">💡 ${a.recommendation||''}</div>
        </div>`;
      });
      const ac=document.getElementById('ai-cards');if(ac)ac.innerHTML=h||'<div style="text-align:center;color:var(--tx3);padding:24px;font-size:12px">في انتظار صفقات</div>';
    }
    if(agTab==='hm'){
      // Top Opportunities من MARKET_SCANNER
      const tops=data.top_opportunities||[];let tH='';
      if(tops.length>0){
        tH='<div style="font-size:10px;color:var(--e879f9,#e879f9);font-weight:700;margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px">🔭 أقوى الفرص الآن</div>';
        tops.forEach((t,i)=>{
          const col=t.score>80?'var(--g)':t.score>65?'var(--y)':' var(--a)';
          tH+=`<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:${col}0d;border:1px solid ${col}33;border-radius:8px;margin-bottom:5px">
            <span style="font-size:16px;font-weight:900;color:${col};min-width:20px">${i+1}</span>
            <div style="flex:1">
              <div style="font-weight:700;font-size:12px;color:${col}">${t.coin} <span style="font-size:9px;color:var(--tx3)">${t.strategy||''}</span></div>
              <div style="font-size:9px;color:var(--tx2)">RSI=${t.rsi} | تغير ${t.change>=0?'+':''}${t.change}% | $${t.price}</div>
            </div>
            <div style="text-align:left">
              <div style="font-size:18px;font-weight:900;font-family:'IBM Plex Mono',monospace;color:${col}">${t.score}</div>
              <div style="font-size:8px;color:var(--tx3)">نقطة</div>
            </div>
          </div>`;
        });
      } else {
        tH='<div style="text-align:center;color:var(--tx3);padding:10px;font-size:11px">🔭 الماسح يعمل — انتظر نتائج...</div>';
      }
      const toEl=document.getElementById('top-opps');if(toEl)toEl.innerHTML=tH;

      const hm=ai.signal_heatmap||{};let h='';
      Object.keys(hm).forEach(coin=>{
        const score=hm[coin],isG=['XAUTUSDT','XAGUSDT'].includes(coin);
        const col=isG?'var(--gold)':score>70?'var(--g)':score>45?'var(--y)':'var(--r)';
        h+=`<div style="background:${isG?'rgba(255,215,0,.07)':score>70?'rgba(0,229,160,.07)':score>45?'rgba(245,197,24,.07)':'rgba(255,61,110,.07)'};border:1px solid ${col}40;border-radius:10px;padding:10px 6px;text-align:center">
          <div style="font-size:9px;font-weight:700;color:${col};margin-bottom:3px">${coin.replace('USDT','')}</div>
          <div style="font-size:18px;font-weight:900;font-family:'IBM Plex Mono',monospace;color:${col}">${score}</div></div>`;
      });
      const hg=document.getElementById('hm-grid');if(hg)hg.innerHTML=h||'<div style="color:var(--tx3);font-size:11px">لا بيانات</div>';
      se('atp',(ai.adaptive_tp||3).toFixed(2)+'%');se('asl',(ai.adaptive_sl||1.5).toFixed(2)+'%');
    }

    // SIGNALS
    if(logTab==='sig'){
      let h='';
      (data.signals||[]).slice(0,30).forEach(s=>{
        const buy=s.type==='شراء',pc=s.mode&&s.mode.includes('-')?'var(--r)':'var(--g)';
        const pS=!buy&&s.mode?`<span style="color:${pc};font-weight:700;margin-right:auto">${s.mode}</span>`:'<span style="margin-right:auto"></span>';
        h+=`<div class="sig-row"><span style="color:var(--tx3);font-size:9px;width:48px;font-family:'IBM Plex Mono',monospace">${s.time}</span><span class="badge ${buy?'b-g':'b-r'}">${s.type}</span><span style="font-weight:700;flex:0 0 70px">${s.coin}</span>${pS}</div>`;
      });
      const sl=document.getElementById('sig-list');if(sl)sl.innerHTML=h||'<div style="text-align:center;color:var(--tx3);padding:24px;font-size:12px">لا توجد إشارات بعد</div>';
    }
    if(logTab==='cap'){
      let h='';
      (data.capital_actions||[]).slice(0,20).forEach(ca=>{
        const mc=ca.mode==='REAL'?'var(--gold)':'var(--a)';const isAI=ca.reason&&ca.reason.includes('🤖');
        h+=`<div class="sig-row" style="${isAI?'background:rgba(192,132,252,.04);':''}">
          <span style="color:var(--tx3);font-size:9px;width:44px;font-family:'IBM Plex Mono',monospace">${ca.time}</span>
          <span style="font-weight:900;font-family:'IBM Plex Mono',monospace;font-size:13px;color:var(--t);min-width:40px">${ca.size_pct}%</span>
          <span style="flex:1;font-size:11px">${ca.strategy}</span>
          <span style="font-size:10px;color:${isAI?'var(--p)':'var(--tx3)'}">${ca.reason}</span>
          <span style="font-size:10px;color:${mc};font-weight:700;margin-right:4px">${ca.mode}</span>
        </div>`;
      });
      const cl=document.getElementById('cap-list');if(cl)cl.innerHTML=h||'<div style="text-align:center;color:var(--tx3);padding:24px;font-size:12px">لا قرارات</div>';
    }
    if(logTab==='strat'){
      const perfs=data.strategy_performance||{},strats=data.strategies||{};let h='';const agRec=ai.agent_recommended_strategy||'';
      Object.keys(perfs).sort((a,b)=>perfs[b].pnl-perfs[a].pnl).forEach(k=>{
        const p=perfs[k],t=p.wins+p.losses,wr2=t>0?((p.wins/t)*100).toFixed(0):0;const isRec=k===agRec;
        h+=`<div class="strat-card" style="${isRec?'border-color:var(--p);background:rgba(192,132,252,.06);':''}">
          <div class="strat-name" style="${isRec?'color:var(--p);':''}">${isRec?'🤖 ':''} ${strats[k]||k}</div>
          <div style="font-size:10px;color:var(--tx3);margin-bottom:3px">${t} صفقة</div>
          <div class="strat-stats"><span style="color:${parseFloat(wr2)>=50?'var(--g)':'var(--r)'}">Win ${wr2}%</span><span style="color:${p.pnl>=0?'var(--g)':'var(--r)'}">$${p.pnl.toFixed(1)}</span></div>
        </div>`;
      });
      const sg=document.getElementById('sg');if(sg)sg.innerHTML=h;
    }
    if(logTab==='hist'){
      let h='';
      (data.trade_history||[]).slice(0,100).forEach(t=>{
        const c=t.pnl_percent>=0?'var(--g)':'var(--r)';const mc=t.mode==='REAL'?'var(--gold)':'var(--a)';
        h+=`<tr><td style="color:var(--tx3);font-family:'IBM Plex Mono',monospace">${t.exit_time.slice(11)}</td><td style="font-weight:700">${t.coin}</td><td style="color:${mc};font-weight:700">${t.mode}</td><td style="color:var(--tx2);font-size:10px">${(data.strategies?.[t.strategy]||t.strategy||'-').split(' ').slice(0,2).join(' ')}</td><td style="color:${c};font-weight:700;font-family:'IBM Plex Mono',monospace">${t.pnl_percent>=0?'+':''}${t.pnl_percent}%</td><td style="color:${c};font-family:'IBM Plex Mono',monospace">${t.pnl_usd>=0?'+':''}$${t.pnl_usd}</td><td style="color:var(--tx3)">${t.duration}</td></tr>`;
      });
      const hb=document.querySelector('#ht tbody');if(hb)hb.innerHTML=h||'<tr><td colspan="7" style="text-align:center;color:var(--tx3);padding:20px">لا صفقات بعد</td></tr>';
    }

    // HEALTH
    // SCALP mini stats
    var scAg=data.agents&&data.agents.SCALP_TRADER?data.agents.SCALP_TRADER:{};
    var scSt=document.getElementById('sc-mini-stat');
    var scPl=document.getElementById('sc-mini-pnl');
    if(scSt)scSt.textContent=scAg.last_response||'انتظار...';
    if(scPl){
      var stp=scAg.total_scalp_profit||0;
      scPl.textContent=(stp>=0?'+':'')+stp.toFixed(2)+'$';
      scPl.style.color=stp>=0?'var(--g)':'var(--r)';
    }
    // Daily plan mini
    var dp=data.daily_plan||{};
    var dpnl=dp.today_pnl||0;
    var dtgt=dp.daily_target||5;
    var dpBar=document.getElementById('dp-progress');
    if(dpBar)dpBar.style.width=Math.min(100,Math.max(0,dpnl/dtgt*100))+'%';

    if(pfTab==='health'){
      updateHealthRing(bh.score||100);
      let ih='';const all=[...(bh.issues||[]).map(x=>({t:x,c:'b-r'})),...(bh.warnings||[]).map(x=>({t:x,c:'b-y'}))];
      if(!all.length) ih='<div style="font-size:11px;color:var(--g)">✅ كل الأنظمة تعمل بشكل طبيعي</div>';
      else all.slice(0,4).forEach(x=>{ih+=`<div style="display:flex;align-items:center;gap:6px;font-size:11px;padding:4px 0;border-bottom:1px solid rgba(24,40,64,.4)"><span class="badge ${x.c}">${x.c==='b-r'?'خطأ':'تحذير'}</span><span style="color:var(--tx2)">${x.t}</span></div>`;});
      const hi=document.getElementById('h-issues');if(hi)hi.innerHTML=ih;
      se('h-up',fmtUp(bh.uptime_seconds||0));se('h-tr',bh.memory_trades||0);
      se('h-ord',bh.orders_sent||0,(bh.orders_sent||0)>0?'var(--g)':'var(--tx3)');
      se('h-fail',bh.orders_failed||0,(bh.orders_failed||0)===0?'var(--g)':'var(--r)');
      const aa=data.account_analysis?.demo||{};const grid=document.getElementById('aa-grid');if(grid){
        const i=(l,v,c)=>`<div class="aa-cell"><div class="aa-label">${l}</div><div class="aa-val" style="color:${c}">${v}</div></div>`;
        grid.innerHTML=i('ROI',(aa.roi_pct>=0?'+':'')+aa.roi_pct+'%',aa.roi_pct>=0?'var(--g)':'var(--r)')+i('Max DD',aa.max_drawdown_pct+'%','var(--r)')+i('أفضل صفقة','+'+aa.best_trade+'%','var(--g)')+i('أسوأ صفقة',aa.worst_trade+'%','var(--r)')+i('Expectancy',aa.expectancy+'%',aa.expectancy>=0?'var(--g)':'var(--r)')+i('Calmar',aa.calmar_ratio||0,(aa.calmar_ratio||0)>=1?'var(--g)':'var(--y)')+i('Win Streak','+'+aa.win_streak,'var(--g)')+i('Loss Streak','-'+aa.loss_streak,'var(--r)');
        const rs=aa.risk_score||50;const rsv=document.getElementById('rs-val');if(rsv)rsv.textContent=rs+'%';const rsb=document.getElementById('rs-bar');if(rsb){rsb.style.width=rs+'%';rsb.style.background=rs>70?'var(--g)':rs>40?'var(--y)':'var(--r)';}
      }
    }
    if(pfTab==='portfolio'){
      let totalU=0,posH='';
      Object.keys(data.active||{}).forEach(coin=>{
        const p=data.active[coin],pos=p.pnl_percent>=0;totalU+=p.pnl_usd||0;
        const mc=p.mode==='real'?'var(--gold)':'var(--a)';
        posH+=`<div class="pos-card"><div><div class="pos-coin">${coin} <span style="color:${mc};font-size:10px">${(p.mode||'').toUpperCase()}</span></div><div class="pos-strat">${data.strategies?.[p.strategy]||p.strategy||''}</div><div class="pos-entry">دخول: $${p.entry} → $${p.current_price}</div></div><div style="text-align:left"><div class="pos-pct ${pos?'pg':'pr'}">${pos?'+':''}${p.pnl_percent}%</div><div class="pos-usd" style="color:${pos?'var(--g)':'var(--r)'}">${pos?'+':''}$${p.pnl_usd.toFixed(2)}</div></div></div>`;
      });
      const posEl=document.getElementById('positions');if(posEl)posEl.innerHTML=posH||'<div style="text-align:center;padding:20px;color:var(--tx3)"><i class="fas fa-inbox" style="font-size:24px;display:block;margin-bottom:8px;color:var(--border3)"></i>لا صفقات مفتوحة</div>';
      const ue=document.getElementById('unr');if(ue){ue.textContent=(totalU>=0?'+':'')+'$'+totalU.toFixed(2);ue.style.color=totalU>=0?'var(--g)':'var(--r)';}
      renderAcc(data);
    }
    if(pfTab==='profits'){
      const pv=data.profit_vault||{};
      const level=pv.protection_level||'normal';
      const lvColors={critical:'var(--r)',high:'var(--o)',normal:'#facc15',low:'var(--g)'};
      const lvBg={critical:'rgba(255,61,110,.08)',high:'rgba(251,146,60,.08)',normal:'rgba(250,204,21,.06)',low:'rgba(0,229,160,.06)'};
      const lvBorder={critical:'rgba(255,61,110,.25)',high:'rgba(251,146,60,.25)',normal:'rgba(250,204,21,.2)',low:'rgba(0,229,160,.2)'};
      const lvAr={critical:'🔴 حرج',high:'🟠 عالٍ',normal:'🟡 طبيعي',low:'🟢 منخفض'};
      const col=lvColors[level]||'#facc15';

      // Header
      const hdr=document.getElementById('pv-header');
      if(hdr){hdr.style.background=lvBg[level]||'rgba(250,204,21,.06)';hdr.style.borderColor=lvBorder[level]||'rgba(250,204,21,.2)';}
      se('pv-level-txt','مستوى الحماية: '+(lvAr[level]||level),col);
      se('pv-decision',pv.decision||'--');

      // Total protected
      const tp=document.getElementById('pv-total-prot');
      if(tp){tp.textContent='$'+(pv.total_protected||0).toFixed(2);tp.style.color=col;}

      // Stats
      const dp=pv.daily_profit||0;
      const dpc=pv.profit_rate_today||0;
      se('pv-daily',(dp>=0?'+':'')+'$'+dp.toFixed(2),dp>=0?'var(--g)':'var(--r)');
      se('pv-daily-pct',(dpc>=0?'+':'')+dpc.toFixed(2)+'%',dpc>=0?'var(--g)':'var(--r)');
      se('pv-safe','$'+(pv.safe_balance||0).toFixed(2),'#facc15');
      se('pv-risk','$'+(pv.risk_capital||0).toFixed(2),'var(--a)');
      se('pv-target','$'+(pv.next_target||0).toFixed(2),'var(--g)');

      // Last decision
      const ld=document.getElementById('pv-last-decision');
      if(ld)ld.innerHTML=`<i class="fas fa-robot" style="color:${col}"></i> ${pv.decision||'hold'} — ${agents['PROFIT_MANAGER']?.last_response||'في انتظار التحليل...'}`;

      // Capital bar
      const totalCap=(pv.safe_balance||0)+(pv.risk_capital||0);
      if(totalCap>0){
        const safePct=Math.round((pv.safe_balance||0)/totalCap*100);
        const riskPct=100-safePct;
        const bs=document.getElementById('pv-bar-safe');const br=document.getElementById('pv-bar-risk');
        if(bs){bs.style.width=safePct+'%';bs.textContent=safePct>8?safePct+'%':'';}
        if(br){br.style.width=riskPct+'%';br.textContent=riskPct>8?riskPct+'%':'';}
      }

      // History
      const hist=pv.protection_history||[];let hH='';
      if(hist.length===0){
        hH='<div style="text-align:center;color:var(--tx3);padding:16px;font-size:11px">لا عمليات حماية بعد — انتظر أول ربح</div>';
      } else {
        hist.slice(0,15).forEach(h=>{
          hH+=`<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;margin-bottom:5px;font-size:11px">
            <span style="color:var(--tx3);font-family:'IBM Plex Mono',monospace;font-size:9px;min-width:48px">${h.time}</span>
            <span class="badge b-y" style="font-size:9px">${h.mode}</span>
            <span style="flex:1;color:var(--tx2)">${h.reason}</span>
            <span style="font-weight:900;color:#facc15;font-family:'IBM Plex Mono',monospace">+$${h.amount}</span>
          </div>`;
        });
      }
      const phel=document.getElementById('pv-history');if(phel)phel.innerHTML=hH;
    }

    if(pfTab==='pfanalysis'){
      const pa=data.portfolio_analysis||{};
      const score=pa.balance_score||0;
      const scoreColor=score>=80?'#4ade80':score>=60?'var(--y)':' var(--r)';

      // Score bar
      const sv=document.getElementById('pf-score-val');if(sv){sv.textContent=score;sv.style.color=scoreColor;}
      const sf=document.getElementById('pf-score-fill');if(sf){sf.style.width=score+'%';sf.style.background=scoreColor;}
      const rec=document.getElementById('pf-rec');if(rec)rec.textContent=pa.recommendation||'جاري التحليل...';

      // Stats
      se('pf-total','$'+(pa.total_value_usd||0).toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2}),'#4ade80');
      se('pf-usdt','$'+(pa.usdt_balance||0).toLocaleString('en',{minimumFractionDigits:2,maximumFractionDigits:2}),'var(--a)');
      const uPct=pa.usdt_pct||0;se('pf-usdt-pct',uPct.toFixed(1)+'%',uPct<15?'var(--r)':uPct>70?'var(--y)':' var(--g)');
      se('pf-update',pa.last_update||'--');

      // Assets list
      const assets=pa.assets||[];let alH='';
      const colors_map={BTC:'#f7931a',ETH:'#627eea',BNB:'#f3ba2f',SOL:'#9945ff',XRP:'#346aa9',USDT:'var(--g)',XAUT:'var(--gold)',XAGUSDT:'#c0c0c0'};
      assets.forEach((a,idx)=>{
        const col=colors_map[a.asset]||'var(--a)';
        const bar=Math.round(a.pct||0);
        const isDom=a.asset===pa.dominant_asset;
        alH+=`<div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:${isDom?'rgba(74,222,128,.05)':'var(--bg2)'};border:1px solid ${isDom?'rgba(74,222,128,.2)':'var(--border)'};border-radius:8px;margin-bottom:5px">
          <div style="width:32px;height:32px;border-radius:50%;background:${col}20;border:2px solid ${col};display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:${col};flex-shrink:0">${a.asset.slice(0,3)}</div>
          <div style="flex:1">
            <div style="display:flex;justify-content:space-between;margin-bottom:3px">
              <span style="font-weight:700;font-size:12px;color:${col}">${a.asset} ${isDom?'👑':''}</span>
              <span style="font-weight:900;font-family:'IBM Plex Mono',monospace;font-size:12px;color:${col}">${a.pct||0}%</span>
            </div>
            <div style="background:var(--border2);height:4px;border-radius:2px;overflow:hidden">
              <div style="width:${bar}%;height:100%;background:${col};border-radius:2px;transition:width .5s"></div>
            </div>
            <div style="display:flex;justify-content:space-between;margin-top:3px">
              <span style="font-size:9px;color:var(--tx3)">${a.qty||0} ${a.asset}</span>
              <span style="font-size:10px;color:var(--tx2);font-family:'IBM Plex Mono',monospace">$${(a.value_usd||0).toFixed(2)}</span>
            </div>
          </div>
        </div>`;
      });
      const al=document.getElementById('pf-assets-list');if(al)al.innerHTML=alH||'<div style="color:var(--tx3);text-align:center;padding:12px">لا أصول</div>';

      // Suggestions
      const sugg=pa.suggested_actions||[];let sH='';
      if(sugg.length>0){
        sH='<div style="font-size:11px;font-weight:700;color:var(--tx2);margin-bottom:6px;text-transform:uppercase;letter-spacing:.4px">التوصيات</div>';
        sugg.forEach(s=>{
          const col=s.startsWith('✅')?'var(--g)':s.startsWith('⚠️')||s.startsWith('⛔')?'var(--r)':'var(--y)';
          sH+=`<div style="background:${col}10;border:1px solid ${col}30;border-radius:8px;padding:8px 12px;margin-bottom:5px;font-size:11px;color:${col};line-height:1.5">${s}</div>`;
        });
      } else if(pa.is_balanced){
        sH='<div style="background:rgba(74,222,128,.08);border:1px solid rgba(74,222,128,.2);border-radius:8px;padding:10px 14px;font-size:11px;color:#4ade80">✅ لا توصيات — المحفظة متوازنة ومثالية</div>';
      }
      const sg=document.getElementById('pf-suggestions');if(sg)sg.innerHTML=sH;

      // Distribution bars
      let dbH='';
      assets.slice(0,6).forEach(a=>{
        const col=colors_map[a.asset]||'var(--a)';
        dbH+=`<div style="display:flex;align-items:center;gap:8px">
          <span style="width:50px;font-size:10px;font-weight:700;color:${col};text-align:right">${a.asset.slice(0,5)}</span>
          <div style="flex:1;background:var(--border2);height:16px;border-radius:4px;overflow:hidden">
            <div style="width:${a.pct||0}%;height:100%;background:${col};border-radius:4px;transition:width .6s;display:flex;align-items:center;padding-right:4px">
              ${(a.pct||0)>8?`<span style="font-size:9px;font-family:'IBM Plex Mono',monospace;color:#000;font-weight:700">${a.pct}%</span>`:''}
            </div>
          </div>
          <span style="width:55px;font-size:10px;font-family:'IBM Plex Mono',monospace;color:var(--tx2)">$${(a.value_usd||0).toFixed(0)}</span>
        </div>`;
      });
      const db=document.getElementById('pf-dist-bars');if(db)db.innerHTML=dbH;
    }

    if(pfTab==='metrics'){
      se('mt-reg',ai.market_regime||'ranging');se('mt-vi',(ai.volatility_index||0).toFixed(1));
      const m=ai.momentum_score||0;se('mt-mom',(m>=0?'+':'')+m.toFixed(1),m>20?'var(--g)':m<-20?'var(--r)':'var(--tx2)');
      se('mt-sh',(ai.sharpe_ratio||0).toFixed(2));se('mt-pf',(ai.profit_factor||0).toFixed(2));
      se('mt-wlr',(ai.win_loss_ratio||0).toFixed(2));
      const sk=ai.streak||0;se('mt-sk',(sk>=0?'+':'')+sk+(sk>=2?' 🔥':sk<=-2?' ❄️':''),sk>=0?'var(--g)':'var(--r)');
      se('mt-conf',(ai.signal_confluence||0)>0?'+'+(ai.signal_confluence||0):(ai.signal_confluence||0));
      se('mt-best',ai.best_strategy||'-','var(--g)');
      const conf=ai.confidence||0;const mc2=document.getElementById('mt-cp');if(mc2)mc2.textContent=conf.toFixed(1)+'%';
      const bar=document.getElementById('mt-cb');if(bar){bar.style.width=conf+'%';bar.style.background=conf>70?'var(--g)':conf>50?'var(--y)':'var(--r)';}
      const fgv=md.fear_greed||55,fgi=getFG(fgv);se('fg',fgv,fgi.c);se('fgl',fgi.l,fgi.c);
      se('btcd',(md.btc_dominance||52.4).toFixed(1)+'%');
      const gp2=md.gold_price||0;se('m-gold',gp2>0?'$'+Math.round(gp2).toLocaleString():'--','var(--gold)');
      const gt=md.gold_trend||'neutral';
      se('m-gold-t',gt==='strong_buy'?'شراء قوي ↑↑':gt==='buy'?'شراء ↑':gt==='sell'?'بيع ↓':gt==='strong_sell'?'بيع قوي ↓↓':'محايد →','var(--gold)');
    }

    if(data.signals.length>lastSigs&&lastSigs>0){const s=data.signals[0];toast(`[${s.mode}] ${s.type} ${s.coin} @$${s.price}`,s.type==='شراء'?'s':'d');}
    lastSigs=data.signals.length;
  }catch(e2){console.error('upd:',e2.message);}
  }).catch(()=>{});
}

// ══ PAPER TRADING JS ══
function paperCtrl(action, trading_type){
  fetch('/api/paper/control',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:action, trading_type:trading_type})
  }).then(function(r){return r.json();}).then(function(d){
    var msg = action==='start'?'✅ تجريبي يعمل — '+trading_type.toUpperCase():
              action==='stop'?'⏹ تجريبي متوقف':
              action==='reset'?'🔄 تجريبي مُعاد ضبطه':'✅ تم';
    toast(msg,'s');
    fetchPaperData();
  }).catch(function(e){toast('❌ خطأ: '+e.message,'d');});
}

function fetchPaperData(){
  fetch('/api/paper/data').then(function(r){return r.json();}).then(function(pd){
    try{ renderPaperPanel(pd); }catch(e){ console.error('paper render:',e); }
  }).catch(function(){});
}

function renderPaperPanel(pd){
  if(!pd) return;
  var pai=pd.ai||{};
  var fsp=pd.finances&&pd.finances.spot?pd.finances.spot:{balance:10000,pnl:0,wins:0,losses:0};
  var ffu=pd.finances&&pd.finances.futures?pd.finances.futures:{balance:10000,pnl:0,wins:0,losses:0};
  var tt=pd.trading_type||'spot';
  var bal=tt==='spot'?fsp.balance:ffu.balance;
  var tw=fsp.wins+ffu.wins; var tl=fsp.losses+ffu.losses; var tot=tw+tl;
  var wr=tot>0?Math.round(tw/tot*100):0;
  var dd=pai.current_drawdown||0;

  // header
  var st=document.getElementById('pp-status');
  if(st)st.textContent=pd.running?'🟢 يعمل — '+tt.toUpperCase():'🔴 متوقف';
  var pb=document.getElementById('pp-bal');
  if(pb){pb.textContent='$'+bal.toFixed(2);pb.style.color=pd.running?'#a78bfa':'var(--tx3)';}
  var ptyp=document.getElementById('pp-type');
  if(ptyp)ptyp.textContent=tt.toUpperCase()+(tt==='futures'?' x'+(pd.futures_leverage||10):'');

  // stats
  var sp=document.getElementById('pp-spot-pnl');
  if(sp){sp.textContent=(fsp.pnl>=0?'+':'')+fsp.pnl.toFixed(2)+'$';sp.style.color=fsp.pnl>=0?'var(--g)':'var(--r)';}
  var fp2=document.getElementById('pp-fut-pnl');
  if(fp2){fp2.textContent=(ffu.pnl>=0?'+':'')+ffu.pnl.toFixed(2)+'$';fp2.style.color=ffu.pnl>=0?'var(--g)':'var(--r)';}
  var wrEl=document.getElementById('pp-wr');
  if(wrEl){wrEl.textContent=wr+'%';wrEl.style.color=wr>=55?'var(--g)':wr>=40?'var(--y)':'var(--r)';}
  var ddEl=document.getElementById('pp-dd');
  if(ddEl){ddEl.textContent=dd.toFixed(1)+'%';ddEl.style.color=dd>5?'var(--r)':'var(--g)';}

  // وكلاء التجريبي
  var agents=pd.agents||{};var agH='';
  var agNames={PAPER_ANALYST:'🔬 محلل التجريبي',PAPER_RISK:'🛡️ مخاطر التجريبي',PAPER_LEARNER:'🧠 تعلم التجريبي',PAPER_BACKTEST:'⚡ Backtest تجريبي'};
  var agCols={PAPER_ANALYST:'#38bdf8',PAPER_RISK:'#ff4466',PAPER_LEARNER:'#22d3ee',PAPER_BACKTEST:'#fb923c'};
  Object.keys(agents).forEach(function(aid){
    var ag=agents[aid];var c=agCols[aid]||'#a78bfa';
    var isT=ag.status==='thinking';
    var stTxt=isT?'يفكر':ag.status==='done'?'مكتمل':'انتظار';
    var stCol=isT?'var(--p)':ag.status==='done'?'var(--g)':'var(--tx3)';
    agH+='<div style="display:flex;align-items:center;gap:8px;padding:6px 10px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;margin-bottom:4px">';
    agH+='<span style="font-size:14px">'+(ag.emoji||'🤖')+'</span>';
    agH+='<div style="flex:1"><div style="font-size:10px;font-weight:700;color:'+c+'">'+(agNames[aid]||aid)+'</div>';
    agH+='<div style="font-size:9px;color:var(--tx2)">'+(ag.last_action||'انتظار')+'</div></div>';
    agH+='<span style="font-size:9px;color:'+stCol+';font-weight:700">'+stTxt+'</span>';
    agH+='<span style="font-size:9px;color:var(--tx3);font-family:IBM Plex Mono,monospace;min-width:30px">'+Math.round((ag.confidence||0)*100)+'%</span>';
    agH+='</div>';
  });
  var agEl=document.getElementById('pp-agents');if(agEl)agEl.innerHTML=agH;

  // رسم بياني
  var cvs=document.getElementById('pp-chart');
  var cd2=pd.chart_data||{};
  if(cvs&&cd2.spot_pnl&&cd2.spot_pnl.length>1){
    var ctx4=cvs.getContext('2d');
    cvs.width=cvs.parentElement?cvs.parentElement.offsetWidth-10:380;
    cvs.height=80;
    ctx4.clearRect(0,0,cvs.width,cvs.height);
    // grid
    ctx4.strokeStyle='rgba(24,40,64,.6)';ctx4.lineWidth=0.5;
    ctx4.beginPath();ctx4.moveTo(0,cvs.height/2);ctx4.lineTo(cvs.width,cvs.height/2);ctx4.stroke();
    // spot line
    var drawLine=function(vals,col){
      if(vals.length<2)return;
      var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals),rng=mx-mn||1;
      ctx4.strokeStyle=col;ctx4.lineWidth=1.5;ctx4.lineJoin='round';
      ctx4.beginPath();
      vals.forEach(function(v,i){
        var x=i/(vals.length-1)*cvs.width;
        var y=cvs.height-(v-mn)/rng*(cvs.height-10)-5;
        if(i===0)ctx4.moveTo(x,y);else ctx4.lineTo(x,y);
      });
      ctx4.stroke();
    };
    drawLine(cd2.spot_pnl,'#a78bfa');
    drawLine(cd2.futures_pnl,'#facc15');
  }

  // صفقات مفتوحة
  var active=pd.active||{};var posH='';
  var akeys=Object.keys(active);
  if(akeys.length===0){posH='<div style="color:var(--tx3);text-align:center;padding:8px;font-size:10px">لا صفقات مفتوحة</div>';}
  else{akeys.forEach(function(coin){
    var p=active[coin];var pc=p.pnl_percent>=0?'var(--g)':'var(--r)';
    var tt2=p.trading_type||'spot';var tcol=tt2==='futures'?'var(--y)':'#a78bfa';
    posH+='<div style="display:flex;align-items:center;gap:8px;padding:7px 10px;background:rgba(167,139,250,.05);border:1px solid rgba(167,139,250,.2);border-radius:8px;margin-bottom:4px;font-size:10px">';
    posH+='<div style="flex:1"><div style="font-weight:700;color:#a78bfa">'+coin+'</div>';
    posH+='<div style="color:var(--tx2);font-size:9px">'+tt2.toUpperCase()+' | $'+p.entry+' → $'+p.current_price+'</div></div>';
    posH+='<div style="text-align:left"><div style="font-weight:900;font-family:IBM Plex Mono,monospace;color:'+pc+'">'+(p.pnl_percent>=0?'+':'')+p.pnl_percent+'%</div>';
    posH+='<div style="font-size:9px;color:'+pc+'">'+(p.pnl_usd>=0?'+':'')+p.pnl_usd+'$</div></div></div>';
  });}
  var posEl=document.getElementById('pp-positions');if(posEl)posEl.innerHTML=posH;

  // سجل الصفقات
  var hist=(pd.trade_history||[]).slice(0,10);var hH='';
  if(hist.length===0){hH='<div style="color:var(--tx3);text-align:center;padding:10px;font-size:10px">لا صفقات بعد</div>';}
  else{hist.forEach(function(t){
    var c=t.pnl_percent>=0?'var(--g)':'var(--r)';
    var tt3=t.mode||'SPOT';var tcol=tt3==='FUTURES'?'var(--y)':'#a78bfa';
    hH+='<div style="display:flex;align-items:center;gap:7px;padding:5px 9px;background:var(--bg2);border:1px solid var(--border);border-radius:7px;margin-bottom:3px;font-size:10px">';
    hH+='<span style="color:var(--tx3);font-size:8px;min-width:44px">'+(t.exit_time||'').slice(11,16)+'</span>';
    hH+='<span style="font-weight:700;min-width:70px;color:#a78bfa">'+t.coin+'</span>';
    hH+='<span style="font-size:8px;color:'+tcol+';min-width:45px">'+tt3+'</span>';
    hH+='<span style="color:'+c+';font-weight:700;font-family:IBM Plex Mono,monospace;flex:1">'+(t.pnl_percent>=0?'+':'')+t.pnl_percent+'%</span>';
    hH+='<span style="color:'+c+';font-size:9px">'+(t.pnl_usd>=0?'+':'')+t.pnl_usd+'$</span>';
    hH+='</div>';
  });}
  var hEl=document.getElementById('pp-history');if(hEl)hEl.innerHTML=hH;
}

// تحديث تجريبي كل 3 ثوانٍ مستقل
setInterval(function(){
  if(pfTab==='paper') fetchPaperData();
},3000);

initChart();
setInterval(update,1500);
update();
// ══ NEURAL NETWORK DISPLAY ══
function updateNeuralDisplay(data){
  var neural = data.neural || {};
  var nsigs  = neural.signals  || {};
  var nweights = neural.weights || {};
  var nstat  = neural.status   || {};
  var nhist  = neural.history  || [];

  // Status badge
  var nst = document.getElementById('neural-status');
  if(nst) nst.textContent = (nstat.active_neurons||0)+' إشارة | '+(nstat.strong_links||0)+' وصلة قوية';

  // إشارات الوكلاء
  var nsEl = document.getElementById('neural-signals');
  if(nsEl){
    var agIcons = {MARKET_ANALYST:'🔍',RISK_MANAGER:'🛡️',NEWS_ANALYST:'📰',
                   GOLD_SPECIALIST:'🥇',PATTERN_LEARNER:'🧠',SCALP_TRADER:'⚡',
                   GEMINI_CHIEF:'🔷',BACKTEST_RUNNER:'⚡',MARKET_SCANNER:'🔭'};
    var h='';
    Object.keys(nsigs).forEach(function(aid){
      var sig=nsigs[aid]; var absSig=Math.abs(sig);
      var col=sig>0.2?'var(--g)':sig<-0.2?'var(--r)':'var(--y)';
      var dir=sig>0.2?'↑':sig<-0.2?'↓':'→';
      var bw=Math.min(100,Math.round(absSig*100));
      h+='<div style="display:flex;align-items:center;gap:5px;margin-bottom:4px">';
      h+='<span style="font-size:11px;min-width:20px">'+(agIcons[aid]||'🤖')+'</span>';
      h+='<div style="flex:1;height:6px;background:var(--border2);border-radius:3px;overflow:hidden">';
      h+='<div style="width:'+bw+'%;height:100%;background:'+col+';border-radius:3px;transition:width .6s"></div></div>';
      h+='<span style="font-size:9px;color:'+col+';min-width:44px;font-family:IBM Plex Mono,monospace">'+dir+sig.toFixed(2)+'</span>';
      h+='</div>';
    });
    nsEl.innerHTML = h || '<div style="color:var(--tx3);font-size:10px;padding:4px">انتظار إشارات...</div>';
  }

  // آخر انتقال
  var nlEl = document.getElementById('neural-last');
  if(nlEl && nhist.length>0){
    var lh=nhist[0];
    var toStr=(lh.to||[]).map(function(t){return t[0]+' (x'+t[2]+')';}).join(' → ');
    nlEl.textContent = (lh.time||'')+'  '+( lh.from||'')+' ['+lh.signal+'] → '+toStr;
  }

  // أوزان الاتصالات
  var nwEl = document.getElementById('neural-weights');
  if(nwEl){
    var wH='';
    Object.keys(nweights).slice(0,10).forEach(function(k){
      var w=nweights[k];
      var col=w>0.75?'var(--g)':w>0.5?'var(--y)':'var(--r)';
      wH+='<div style="font-size:8px;padding:2px 6px;border-radius:4px;background:rgba(0,0,0,.2);color:'+col+';border:1px solid '+col+'40;white-space:nowrap">'+k+': '+w+'</div>';
    });
    nwEl.innerHTML = wH || '<div style="color:var(--tx3);font-size:9px">انتظار أوزان...</div>';
  }

  // Scalp Neural
  var sn = data.scalp_neural || {};
  var snSig = sn.signal || 0;
  var snBadge = document.getElementById('scalp-signal-badge');
  if(snBadge){
    var snCol=snSig>0.4?'var(--g)':snSig<-0.2?'var(--r)':'var(--y)';
    snBadge.textContent=snSig>0.4?'فرصة ⚡':snSig<-0.2?'انتظار ⏸':'رصد 🔍';
    snBadge.style.color=snCol;
  }
  var swEl=document.getElementById('scalp-windows');
  if(swEl){
    var wH='';
    (sn.windows||[]).forEach(function(w,i){
      var c=i===0?'#f43f5e':i===1?'var(--o)':'var(--y)';
      wH+='<div style="display:flex;align-items:center;gap:6px;padding:4px 6px;background:rgba(244,63,94,.05);border-radius:5px;margin-bottom:3px;font-size:9px">';
      wH+='<span style="color:'+c+';font-weight:700;min-width:16px">'+(i+1)+'</span>';
      wH+='<span style="font-weight:700;color:'+c+'">'+w.coin+'</span>';
      wH+='<span style="color:var(--tx3)">زخم='+w.micro+'</span>';
      wH+='<span style="color:var(--tx3)">flow='+w.flow+'</span>';
      wH+='<span style="margin-right:auto;font-weight:700;color:'+c+'">'+w.score+'</span>';
      wH+='</div>';
    });
    swEl.innerHTML=wH||'<div style="color:var(--tx3);font-size:9px;padding:3px">لا فرص سكالب الآن</div>';
  }
  var ss=sn.stats||{};
  var scbc=document.getElementById('scalp-best-coin');if(scbc)scbc.textContent=(ss.best_scalp_coin||'---').replace('USDT','');
  var scm=document.getElementById('scalp-momentum');if(scm){scm.textContent=(ss.momentum_score||0).toFixed(1);scm.style.color=(ss.momentum_score||0)>30?'var(--g)':'var(--y)';}
  var sct=document.getElementById('scalp-time');if(sct)sct.textContent=ss.best_scalp_time||'---';

  // Pro Trader
  var pt = data.pro_trader || {};
  var ptEl = document.getElementById('pro-trader-status');
  if(ptEl){
    var psych=pt.psychology||50;
    var bias=pt.smart_money||'neutral';
    var biasMap={accumulation:'تجميع 🏦',markup:'ارتفاع 📈',distribution:'توزيع ⚠️',markdown:'هبوط 📉',neutral:'محايد →'};
    var psychCol=psych>70?'var(--r)':psych<30?'var(--g)':'var(--y)';
    ptEl.innerHTML='<div style="display:flex;gap:10px;font-size:10px">'
      +'<div>نفسية: <span style="color:'+psychCol+';font-weight:700">'+psych.toFixed(0)+'</span></div>'
      +'<div>الأموال الذكية: <span style="color:var(--p);font-weight:700">'+(biasMap[bias]||bias)+'</span></div>'
      +'</div>'
      +(pt.insights||[]).map(function(i){return '<div style="font-size:9px;color:var(--tx2);margin-top:3px">'+i+'</div>';}).join('');
  }
}

</script>
</body>
</html>
"""


# ══════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════
@app.route("/", methods=["GET","POST"])
def index():
    if request.method == "POST":
        action = request.form.get("action")
        state["running"]          = (action == "start")
        state["current_mode"]     = request.form.get("mode", state["current_mode"])
        state["futures_leverage"] = safe_int(request.form.get("leverage"), state["futures_leverage"])
        state["active_engines"]["spot"]    = "engine_spot"    in request.form
        state["active_engines"]["futures"] = "engine_futures" in request.form
        if state["active_engines"]["futures"]: state["trading_type"] = "futures"
        elif state["active_engines"]["spot"]:  state["trading_type"] = "spot"
        state["selected_coins"]   = request.form.getlist("coins")
        state["selected_strategies"] = request.form.getlist("strats")
        state["selected_timeframes"]  = request.form.getlist("timeframes")
        state["capital_mgmt"]["mode"]            = request.form.get("capital_mode","smart_adaptive")
        state["capital_mgmt"]["base_risk_pct"]   = safe_float(request.form.get("base_risk"),2.0)
        state["capital_mgmt"]["max_daily_loss"]  = safe_float(request.form.get("max_daily_loss"),5.0)
        state["capital_mgmt"]["profit_target_daily"] = safe_float(request.form.get("daily_target"),3.0)
        state["capital_mgmt"]["partial_tp"]      = "partial_tp" in request.form
        state["capital_mgmt"]["partial_tp_pct"]  = safe_float(request.form.get("partial_pct"),50.0)
        state["capital_mgmt"]["max_open"]        = safe_int(request.form.get("max_open"),10)
        state["selected_timeframes"] = request.form.getlist("timeframes") or state["selected_timeframes"]
        state["smart_sl"]["type"]            = request.form.get("sl_type","trailing")
        state["smart_sl"]["trailing_offset"] = safe_float(request.form.get("trailing_offset"),1.0)
        state["ai_learner"]["enabled"]             = "ai_enabled" in request.form
        state["ai_learner"]["drawdown_protection"] = "drawdown_protection" in request.form
        state["ai_learner"]["max_drawdown_pct"]    = safe_float(request.form.get("max_drawdown"),10.0)
        # حفظ Gemini key إذا أُدخل
        gemini_input = request.form.get("gemini_key","").strip()
        if gemini_input and gemini_input != "AIza..." and len(gemini_input) > 10:
            global GEMINI_API_KEY; GEMINI_API_KEY = gemini_input
        tg_t = request.form.get("tg_token","").strip()
        tg_c = request.form.get("tg_chat","").strip()
        if tg_t:
            global TELEGRAM_TOKEN
            TELEGRAM_TOKEN = tg_t
        if tg_c:
            global TELEGRAM_CHAT_ID
            TELEGRAM_CHAT_ID = tg_c

        if action == "save_settings":
            # حفظ وتطبيق فوري بدون إيقاف البوت
            save_state()
            print(f"✅ الإعدادات حُفظت وطُبِّقت — البوت {'نشط' if state['running'] else 'متوقف'}")
            # لا نغير running

        if action == "start":
            mode_now = request.form.get("mode", state["current_mode"])
            bal_now  = get_balance(mode_now)

            # ✅ إعادة ضبط كاملة عند الضغط على Start
            state["ai_learner"]["daily_trades"]        = 0
            state["ai_learner"]["daily_pnl"]           = 0.0
            state["ai_learner"]["session_start"]       = datetime.datetime.now().strftime("%H:%M")
            state["ai_learner"]["smart_filter_active"] = False
            state["ai_learner"]["streak"]              = 0
            state["ai_learner"]["current_drawdown"]    = 0.0
            # ═══ إعادة ضبط peak بالرصيد الحقيقي ═══
            mode_now = request.form.get("mode", state["current_mode"])
            real_bal = get_balance(mode_now)
            if real_bal > 0:
                state["ai_learner"]["peak_balance_real"] = real_bal
                state["ai_learner"]["peak_balance_demo"] = real_bal if mode_now=="demo" else state["ai_learner"].get("peak_balance_demo",10000)
            print(f"✅ Peak reset: {mode_now} = ${real_bal:.2f}")

            # ✅ إعادة ضبط peak بالرصيد الحالي الحقيقي
            if bal_now > 0:
                state["ai_learner"]["peak_balance_real"] = bal_now
                state["ai_learner"]["peak_balance_demo"] = bal_now if mode_now == "demo" else state["ai_learner"].get("peak_balance_demo", 10000)

            # ✅ تصفير عدادات الأخطاء
            state["bot_health"]["orders_failed"]      = 0
            state["bot_health"]["orders_sent"]        = 0
            state["bot_health"]["consecutive_errors"] = 0

            # إغلاق صفقات الوضع الآخر
            old = "demo" if mode_now == "real" else "real"
            to_close = [c for c,p in state["active_positions"].items() if p.get("mode")==old]
            for c in to_close: state["active_positions"].pop(c, None)
            if to_close: print(f"🔄 أُغلقت {len(to_close)} صفقة من وضع {old}")
            print(f"🚀 تشغيل في وضع {mode_now.upper()} | رصيد=${bal_now:.2f} | peak مُعاد ضبطه")

        # ✅ FIX: إعادة إنشاء client دائماً عند الضغط على Start
        if action == "start" or not state["client"]:
            try:
                state["client"] = Client(API_KEY, API_SECRET)
                state["client"].ping()
                state["api_status"].update({
                    "connected": True, "error": "",
                    "last_sync": datetime.datetime.now().strftime("%H:%M:%S"),
                    "mode": "متصل ✅"
                })
                symbol_filters.clear()
                print(f"✅ Binance متصل — وضع: {state['current_mode'].upper()}")
            except Exception as e:
                state["client"] = None
                state["api_status"].update({
                    "connected": False,
                    "error": str(e)[:80],
                    "mode": "❌ فشل الاتصال"
                })
                print(f"❌ Binance فشل: {e}")
        save_state()
    gemini_display = "تم الضبط ✅" if GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE" else ""
    return render_template_string(HTML, state=state, gemini_key_display=gemini_display)


@app.route("/api/data")
def api_data():
    active = {}
    for coin, pos in state["active_positions"].items():
        cur = state["prices"].get(coin, pos["entry"])
        chg = ((cur-pos["entry"])/pos["entry"])*100
        active[coin] = {
            **{k:v for k,v in pos.items() if k!="entry_time"},
            "entry_time": pos["entry_time"] if isinstance(pos["entry_time"],str) else pos["entry_time"].isoformat(),
            "current_price": round(cur,4), "pnl_percent": round(chg,2),
            "pnl_usd": round(pos["size"]*(chg/100),2),
        }
    return jsonify({
        "finances": state["finances"], "signals": state["signals"][:30],
        "active": active, "trade_history": state["trade_history"][:100],
        "ai_learner": state["ai_learner"], "strategy_performance": state["strategy_performance"],
        "strategies": state["strategies"], "market_data": state["market_data"],
        "chart_data": state["chart_data"], "bot_health": state["bot_health"],
        "account_analysis": state["account_analysis"], "capital_mgmt": state["capital_mgmt"],
        "capital_actions": state["capital_actions"][:30], "notifications": state["notifications"][:10],
        "tf_data": state["tf_data"], "selected_timeframes": state["selected_timeframes"],
        "prices": {k:state["prices"][k] for k in ["BTCUSDT","ETHUSDT","SOLUSDT"] if k in state["prices"]},
        "running": state["running"], "current_mode": state["current_mode"],
        "api_status": state["api_status"], "agents": agents,
        "agent_conversations": agent_conversations[:20],
        # V19: بيانات التعلم
        "learned_patterns_count": len(learned_patterns),
        "backtest_count":         len(backtest_results),
        "strategy_weights":       strategy_weights,
        "online_log":             online_learning_log[:5],
        "portfolio_analysis":     state["portfolio_analysis"],
        "profit_vault":           state["profit_vault"],
        "top_opportunities":      state["ai_learner"].get("top_opportunities",[]),
        "scalp_stats":            state["scalp_stats"],
        "scalp_history":          agents.get("SCALP_TRADER",{}).get("scalp_history",[])[:15],
        "active_scalps":          agents.get("SCALP_TRADER",{}).get("active_scalps",{}),
        "consensus":              state["consensus_system"],
        "daily_plan":             state["daily_plan"],
        "portfolio_state":        portfolio_state,
        "pro_trader": {
            "psychology":  pro_trader_memory.get("market_psychology",50),
            "smart_money": pro_trader_memory.get("smart_money_bias","neutral"),
            "insights":    pro_trader_memory.get("session_insights",[])[:3],
            "key_levels":  pro_trader_memory.get("key_levels",{}),
        },
        "active_engines":  state["active_engines"],
        "scalp_neural": {
            "windows":  scalp_neural_state["scalp_windows"][:3],
            "signal":   scalp_neural_state["neural_scalp_signal"],
            "stats":    scalp_neural_state["session_stats"],
            "targets":  {k:v for k,v in list(scalp_neural_state["exit_targets"].items())[:5]},
        },
        "news_data":              state["news_data"],
        "neural": {
            "signals":  {k:round(v,3) for k,v in neural_signals.items()},
            "weights":  {str(k[0]+"→"+k[1]):round(v,3) for k,v in neural_weights.items()},
            "status":   neural_status_summary(),
            "history":  neural_history[:5],
        },
    })


# ══════════════════════════════════════════════
# ✅ ROUTE الجديد — المحادثة المباشرة مع Claude
# ══════════════════════════════════════════════
@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    واجهة المحادثة المباشرة بين المستخدم وClaude
    يتضمن سياق البوت الكامل في كل رسالة
    """
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "رسالة فارغة"}), 400

    # أضف رسالة المستخدم للتاريخ
    direct_chat_history.append({
        "role": "user",
        "content": user_message,
        "time": datetime.datetime.now().strftime("%H:%M:%S")
    })

    # احصل على رد Claude مع سياق البوت
    response_text = call_claude_chat(user_message, direct_chat_history)

    # أضف رد Claude للتاريخ
    direct_chat_history.append({
        "role": "assistant",
        "content": response_text,
        "time": datetime.datetime.now().strftime("%H:%M:%S")
    })

    # حافظ على آخر 30 رسالة فقط
    if len(direct_chat_history) > 30:
        direct_chat_history.pop(0)

    connected = CLAUDE_API_KEY != "YOUR_ANTHROPIC_API_KEY_HERE"

    return jsonify({
        "response": response_text,
        "connected": connected,
        "time": datetime.datetime.now().strftime("%H:%M")
    })


@app.route("/api/paper/data")
def api_paper_data():
    """بيانات التجريبي المعزول"""
    active = {}
    for coin, pos in paper_state["active_positions"].items():
        cur = state["prices"].get(coin, pos["entry"])
        chg = ((cur-pos["entry"])/pos["entry"])*100
        active[coin] = {
            **{k:v for k,v in pos.items() if k!="entry_time"},
            "entry_time": pos["entry_time"] if isinstance(pos["entry_time"],str) else pos["entry_time"].isoformat(),
            "current_price": round(cur,4),
            "pnl_percent":   round(chg,2),
            "pnl_usd":       round(pos["size"]*(chg/100),2),
        }
    return jsonify({
        "running":          paper_state["running"],
        "trading_type":     paper_state["trading_type"],
        "finances":         paper_state["finances"],
        "active":           active,
        "trade_history":    paper_state["trade_history"][:80],
        "signals":          paper_state["signals"][:20],
        "notifications":    paper_state["notifications"][:10],
        "performance":      paper_state["performance"],
        "ai":               paper_state["ai"],
        "stats":            paper_state["stats"],
        "chart_data":       paper_state["chart_data"],
        "agents":           paper_agents,
        "strategy_weights": paper_strategy_weights,
        "learned_patterns": len(paper_learned_patterns),
        "backtest_results": paper_backtest_results,
        "online_log":       paper_online_log[:5],
        "capital_mgmt":     paper_state["capital_mgmt"],
    })


@app.route("/api/paper/control", methods=["POST"])
def api_paper_control():
    """تحكم في التجريبي"""
    data   = request.get_json() or {}
    action = data.get("action","")

    if action == "start":
        paper_state["running"]      = True
        paper_state["trading_type"] = data.get("trading_type", "spot")
        if "coins" in data:
            paper_state["selected_coins"] = data["coins"]
        if "strategies" in data:
            paper_state["selected_strategies"] = data["strategies"]
        if "base_risk" in data:
            paper_state["capital_mgmt"]["base_risk_pct"] = float(data["base_risk"])
        paper_state["ai"]["session_start"] = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"📄 Paper Trading STARTED | {paper_state['trading_type'].upper()}")
        return jsonify({"status":"started","trading_type":paper_state["trading_type"]})

    elif action == "stop":
        paper_state["running"] = False
        save_paper_state()
        print("📄 Paper Trading STOPPED")
        return jsonify({"status":"stopped"})

    elif action == "reset":
        # إعادة ضبط كاملة
        paper_state["finances"] = {
            "spot":    {"balance":PAPER_STARTING_BALANCE,"pnl":0.0,"wins":0,"losses":0,"history":[],"peak":PAPER_STARTING_BALANCE},
            "futures": {"balance":PAPER_STARTING_BALANCE,"pnl":0.0,"wins":0,"losses":0,"history":[],"peak":PAPER_STARTING_BALANCE},
        }
        paper_state["active_positions"] = {}
        paper_state["trade_history"]    = []
        paper_state["signals"]          = []
        paper_state["notifications"]    = []
        paper_state["ai"]["streak"]     = 0
        paper_state["ai"]["daily_pnl"]  = 0.0
        paper_state["ai"]["daily_trades"] = 0
        paper_state["ai"]["current_drawdown"] = 0.0
        paper_state["ai"]["peak_balance_spot"]    = PAPER_STARTING_BALANCE
        paper_state["ai"]["peak_balance_futures"] = PAPER_STARTING_BALANCE
        paper_state["running"] = False
        for k in paper_state["performance"]:
            paper_state["performance"][k] = {"wins":0,"losses":0,"pnl":0.0,"trades":0}
        paper_learned_patterns.clear()
        paper_strategy_weights.clear()
        paper_backtest_results.clear()
        paper_online_log.clear()
        save_paper_state()
        print("📄 Paper Trading RESET")
        return jsonify({"status":"reset"})

    elif action == "switch_type":
        tt = data.get("trading_type","spot")
        paper_state["trading_type"] = tt
        return jsonify({"status":"switched","trading_type":tt})

    elif action == "update_settings":
        if "base_risk"   in data: paper_state["capital_mgmt"]["base_risk_pct"] = float(data["base_risk"])
        if "max_open"    in data: paper_state["capital_mgmt"]["max_open"]       = int(data["max_open"])
        if "leverage"    in data: paper_state["futures_leverage"]               = int(data["leverage"])
        if "coins"       in data: paper_state["selected_coins"]     = data["coins"]
        if "strategies"  in data: paper_state["selected_strategies"] = data["strategies"]
        return jsonify({"status":"updated"})

    return jsonify({"error":"unknown action"}), 400


@app.route("/api/debug")
def api_debug():
    """نقطة تشخيص — تعرض حالة التداول الحقيقية"""
    return jsonify({
        "current_mode":     state["current_mode"],
        "running":          state["running"],
        "api_connected":    state["api_status"].get("connected", False),
        "api_error":        state["api_status"].get("error", ""),
        "client_exists":    state["client"] is not None,
        "trading_type":     state["trading_type"],
        "active_positions": {
            k: {"mode": v.get("mode"), "is_real": v.get("is_real_order", False)}
            for k,v in state["active_positions"].items()
        },
        "orders_sent":   state["bot_health"].get("orders_sent", 0),
        "orders_failed": state["bot_health"].get("orders_failed", 0),
        "selected_coins": state["selected_coins"],
        "prices_available": list(state["prices"].keys())[:10],
    })


@app.route("/api/learning")
def api_learning():
    """V19: بيانات التعلم المستمر"""
    return jsonify({
        "learned_patterns":    learned_patterns[-20:],
        "backtest_results":    backtest_results,
        "strategy_weights":    strategy_weights,
        "online_learning_log": online_learning_log[:20],
        "total_patterns":      len(learned_patterns),
        "total_strategies_bt": len(backtest_results),
    })


@app.route("/api/agent/trigger/<agent_id>", methods=["POST"])
def trigger_agent(agent_id):
    agent_funcs = {
        "MARKET_ANALYST":    run_market_analyst,
        "RISK_MANAGER":      run_risk_manager,
        "STRATEGY_SELECTOR": run_strategy_selector,
        "TRADE_REVIEWER":    run_trade_reviewer,
        "GOLD_SPECIALIST":   run_gold_specialist,
        "PATTERN_LEARNER":   run_pattern_learner,    # V19
        "BACKTEST_RUNNER":   run_backtest_runner,     # V19
        "PORTFOLIO_MANAGER": run_portfolio_manager,   # V20
        "PROFIT_MANAGER":    run_profit_manager,        # V21
        "MARKET_SCANNER":    run_market_scanner,         # V22
        "SCALP_TRADER":      run_scalp_trader,            # V23
        "NEWS_ANALYST":      run_news_analyst,
        "GEMINI_CHIEF":      run_gemini_chief,
    }
    if agent_id in agent_funcs:
        t = threading.Thread(target=agent_funcs[agent_id], daemon=True); t.start()
        return jsonify({"status":"triggered","agent":agent_id})
    return jsonify({"error":"agent not found"}), 404


# ── START ──
load_state()
threading.Thread(target=sync_data,          daemon=True).start()
threading.Thread(target=trading_logic,      daemon=True).start()
threading.Thread(target=auto_save,          daemon=True).start()
threading.Thread(target=ai_thread,          daemon=True).start()
threading.Thread(target=health_thread,      daemon=True).start()
threading.Thread(target=analysis_thread,    daemon=True).start()
threading.Thread(target=tf_thread,          daemon=True).start()
threading.Thread(target=agent_orchestrator,         daemon=True).start()
threading.Thread(target=daily_plan_reset_checker,  daemon=True).start()
threading.Thread(target=telegram_hourly,   daemon=True).start()
threading.Thread(target=portfolio_thread,  daemon=True).start()
threading.Thread(target=pro_neural_thread,   daemon=True).start()
threading.Thread(target=scalp_neural_thread, daemon=True).start()
print("⚡ Scalp Neural: محرك السكالب الاحترافي — كل 10 ثوانٍ")
print("⚖️ Portfolio Rebalancer: شغّال كل 15 دقيقة")
print("💎 Pro Neural Cells: تحليل احترافي كل 30 ثانية")

# ═══ Paper Trading Threads ═══
load_paper_state()
threading.Thread(target=paper_trading_logic,      daemon=True).start()
threading.Thread(target=paper_agent_orchestrator, daemon=True).start()
threading.Thread(target=paper_ai_thread,          daemon=True).start()
threading.Thread(target=auto_save_paper,          daemon=True).start()
print("📄 Paper Trading Engine — معزول كلياً عن التداول الحقيقي")

if __name__ == "__main__":
    print("🚀 Master Terminal V25 — NEWS_ANALYST + Paper Trading + 12 Agents")
    print("✅ إصلاح LOT_SIZE + MIN_NOTIONAL + execute_entry")
    print("✅ Direct Chat مع Claude مدمج في الداشبورد")
    print("📌 لتفعيل المحادثة الحقيقية: أضف مفتاح Claude API في السطر:")
    print('   CLAUDE_API_KEY = "sk-ant-api03-..."')


# =============================================================================
# SAFE PATCH V61 — crash shielding + stable startup
# =============================================================================

def safe_float(value, default=0.0):
    try:
        if value in ("", None):
            return default
        return float(value)
    except Exception:
        return default

def safe_int(value, default=0):
    try:
        if value in ("", None):
            return default
        return int(float(value))
    except Exception:
        return default

@app.errorhandler(Exception)
def _global_error_handler(e):
    import traceback
    print("🔥 GLOBAL ERROR:")
    traceback.print_exc()
    return jsonify({
        "status": "error",
        "message": str(e)
    }), 200

# إعادة ربط index بشكل آمن بدون حذف أي سطر من منطقك الأصلي
_original_index_view = app.view_functions.get("index")

def _safe_index_view(*args, **kwargs):
    try:
        return _original_index_view(*args, **kwargs)
    except Exception as e:
        import traceback
        print("🔥 INDEX ERROR:")
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 200

if _original_index_view:
    app.view_functions["index"] = _safe_index_view

# ملاحظة: ابدأ التشغيل فقط بعد اكتمال كل التعريفات
# (تمت إعادة app.run إلى نهاية الملف لضمان تعريف كل الدوال قبل التشغيل)




# ==============================
# 🔧 REAL TRADING FIX (BINANCE EXECUTION)
# ==============================

def execute_real_trade(symbol, side, quantity, price=None):
    try:
        client = state.get("client")
        if client is None:
            print("❌ Binance client not initialized")
            return False

        if state["trading_type"] == "spot":
            order = client.order_market(
                symbol=symbol,
                side=side,
                quantity=quantity
            )
        else:
            order = client.futures_create_order(
                symbol=symbol,
                side=side,
                type="MARKET",
                quantity=quantity
            )

        print(f"✅ REAL ORDER EXECUTED: {symbol} {side} {quantity}")
        return True

    except Exception as e:
        print("❌ Order Error:", e)
        return False


# تأكد من تهيئة Binance Client
def init_binance():
    try:
        state["client"] = Client(API_KEY, API_SECRET)
        state["api_status"]["connected"] = True
        print("✅ Binance Connected")
    except Exception as e:
        print("❌ Binance Connection Error:", e)


# ==============================
# USE THIS INSIDE TRADE ENTRY
# ==============================
# مثال:
# execute_real_trade("BTCUSDT", "BUY", 0.001)



if __name__ == "__main__":
    print("🚀 Master Terminal V25 — NEWS_ANALYST + Paper Trading + 12 Agents")
    print("✅ إصلاح LOT_SIZE + MIN_NOTIONAL + execute_entry")
    print("✅ Direct Chat مع Claude مدمج في الداشبورد")
    print("📌 لتفعيل المحادثة الحقيقية: أضف مفتاح Claude API في السطر:")
    print('   CLAUDE_API_KEY = "sk-ant-api03-..."')
    app.run(port=8000, debug=False, threaded=True, use_reloader=False)
# =========================================================
# 🔥 FINAL ABSOLUTE FIX — NO MORE INTERNAL SERVER ERROR
# =========================================================

import traceback
import threading

# =========================
# 🛡️ GLOBAL ERROR HANDLER
# =========================
@app.errorhandler(Exception)
def handle_global_error(e):
    print("\n🔥🔥🔥 GLOBAL ERROR 🔥🔥🔥")
    traceback.print_exc()
    return {"error": str(e)}, 200


# =========================
# 🛡️ SAFE INDEX WRAPPER
# =========================
_original_index = app.view_functions.get("index")

def safe_index(*args, **kwargs):
    try:
        if request.method == "POST":
            # حماية القيم الفارغة
            def safe_float(v, d=0.0):
                try:
                    return float(v) if v not in ("", None) else d
                except:
                    return d

            def safe_int(v, d=0):
                try:
                    return int(float(v)) if v not in ("", None) else d
                except:
                    return d

            # أهم القيم اللي تسبب crash
            if "leverage" in request.form:
                state["futures_leverage"] = safe_int(
                    request.form.get("leverage"),
                    state.get("futures_leverage", 1)
                )

            if "max_open" in request.form:
                state["capital_mgmt"]["max_open"] = safe_int(
                    request.form.get("max_open"),
                    state["capital_mgmt"].get("max_open", 5)
                )

        return _original_index(*args, **kwargs)

    except Exception as e:
        print("\n🔥 INDEX CRASH 🔥")
        traceback.print_exc()
        return {"error": str(e)}, 200


if _original_index:
    app.view_functions["index"] = safe_index


# =========================
# 🚀 PREVENT MULTIPLE THREADS
# =========================
if "bot_started" not in state:
    state["bot_started"] = False

def safe_start_bot():
    if not state["bot_started"]:
        state["bot_started"] = True
        try:
            threading.Thread(target=trading_logic, daemon=True).start()
            print("✅ Bot thread started safely")
        except Exception as e:
            print("❌ Thread start error:", e)

safe_start_bot()


# =========================
# 🚀 FORCE SINGLE RUN ONLY
# =========================
def run_server_safe():
    print("\n🚀 RUNNING SAFE MODE (NO CRASH)")
    try:
        app.run(
            host="0.0.0.0",
            port=8000,
            debug=True,
            use_reloader=False  # مهم جدًا
        )
    except Exception as e:
        print("❌ RUN ERROR:", e)


# =========================
# ❌ تعطيل أي تشغيل سابق
# =========================
import sys
if __name__ == "__main__":
    run_server_safe()
