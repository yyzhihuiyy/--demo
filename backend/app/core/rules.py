"""Versioned teaching-rule constants shared by core services; provenance recorded in TASK-101 delivery notes."""
import os

RULES_VERSION = "mvp-v1"
SIM_VERSION = "mvp-sim-v1"
SIM_SEED = 20261012
SIM_TICK_SECONDS = float(os.getenv("SIM_TICK_SECONDS", "3"))

ENTRY_BASE_MIN = 8
ENTRY_BASE_MAX = 16
PROMOTION_ENTRY_BONUS = 6
CLICK_PROB_BASE = 0.1
PRICE_FACTOR_MIN = 0.2
PRICE_FACTOR_MAX = 1.5
SPEECH_INTERACTION_WEIGHT = 0.05
REPLY_INTERACTION_WEIGHT = 0.03
INTERACTION_CAP = 10
BUY_FROM_CLICK_RATIO = 0.35
COUPON_BUY_MULTIPLIER = 1.25
CLICK_PROB_MIN = 0.01
CLICK_PROB_MAX = 0.5
BUY_PROB_MIN = 0.005
BUY_PROB_MAX = 0.3
QUESTION_PROB_PER_TICK = 0.3
ORDER_QTY_CHOICES = (1, 1, 1, 2)
MIN_PAY_CENTS = 1

FORBIDDEN_TERMS = (
    "最低价", "全网最低", "国家级", "最高级", "第一品牌", "销量第一",
    "百分百", "包治", "假一赔十", "无效退款",
)

AUDIENCE_QUESTIONS = (
    "这个产品保质期多久？",
    "能便宜一点吗？有优惠券吗？",
    "什么时候发货？大概几天能到？",
    "买回去不满意可以退吗？",
    "产地是哪里？是当季的吗？",
    "有没有质检报告可以看看？",
)

BUYER_LABELS = (
    "买家小张", "买家小李", "买家王姐", "买家阿豪", "买家陈叔",
    "买家小鹿", "买家大强", "买家燕子", "买家老周", "买家萌萌",
)

TOKEN_TTL_HOURS = 24
