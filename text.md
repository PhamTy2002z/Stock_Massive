
# Thu thập OHLCV hằng ngày — tắt theo yêu cầu 2026-08-08
DAILY_OHLCV_ENABLED=false

# Backfill lịch sử sâu — bật 2026-08-12 để nạp 20 mã VN30 mới thêm vào Universe.
# Chạy 5 mã mỗi lượt (backfill_symbols_per_run), cron 17:00 sau chu kỳ 16:15.
# Tự hết việc khi mọi mã đạt completed; tắt lại nếu cần dành hạn mức vnstock.
BACKFILL_ENABLED=true
UPSTASH_REDIS_REST_URL=https://tolerant-lynx-201156.upstash.io
UPSTASH_REDIS_REST_TOKEN=gQAAAAAAAxHEAAIgcDJjY2FiZjUxNmU0Y2Y0MjZhODVhOWJiYzU5OGZiNTZhYg

FIINQUANT_USERNAME=ty.pham.glm@gmail.com
FIINQUANT_PASSWORD=Robertoty2002@
VNSTOCK_API_KEY=vnstock_2c28e101fce4f495aed82a7aad0f3a5a

# Universe — toàn bộ rổ VN30, lấy từ Listing().symbols_by_group('VN30') ngày
# 2026-08-12. HOSE cân lại rổ định kỳ, nên đối chiếu lại sau mỗi lần rebalance;
# thứ tự để theo alphabet cho dễ diff với danh sách provider trả về.
UNIVERSE_SYMBOLS=ACB,BID,BSR,CTG,FPT,GAS,GVR,HDB,HPG,LPB,MBB,MCH,MSN,MWG,SAB,SHB,SSB,SSI,STB,TCB,TCX,VCB,VHM,VIB,VIC,VJC,VNM,VPB,VPL,VRE

# ========================================
# Alpha Desk — dev route straight to OpenRouter, 2026-08-17.
#
# Replaces the CLIProxyAPI route (docs/adr/0014): that proxy's account fell
# below the balance OpenRouter converts into a prompt-token ceiling, and every
# agent call died with `billing_error: Prompt tokens limit exceeded (… > 13203)`
# while a Turn needs ~10.4k tokens of System Prompt Contract and tool schemas
# before it has read anything. Measured on the free model: 24k-token prompts
# answer 200 and usage comes back `cost: 0`.
#
# The model is a free one that passes all four Capability Probe checks, which
# is why the probe is back on: forced `tool_choice`, parallel tool calls while
# streaming, structured output and a closed tool loop were all verified against
# it directly. gpt-oss-20b:free was tried first and rejected — it refuses forced
# `tool_choice`, spends 70-145s per Turn, times out on about half of them, and
# degenerated into a wall of "!" once the financial tool result grew to eight
# quarters. This one answered a 24k-token prompt in 3.6s and issued two tool
# calls in a single round.
# ========================================
ALPHA_DESK_ENABLED=true
# CLIProxyAPI cuc bo (ccs, goi codex subscription). Container doc qua
# host.docker.internal; chay API tren host (`make dev`) thi doi thanh
# http://127.0.0.1:8317/v1.
LLM_BASE_URL=http://host.docker.internal:8317/v1
LLM_API_KEY=ccs-internal-managed
# Batch giu Luna cho re; session dung Terra dung cap production (config.py).
LLM_MODEL_BATCH=gpt-5.6-luna
LLM_MODEL_SESSION=gpt-5.6-terra
LLM_REQUEST_TIMEOUT_SECONDS=120
LLM_CAPABILITY_PROBE_ENABLED=true

# The production price table the dev route stands in for (budget.py module
# docstring). Left at these values even though the model bills nothing: a zero
# price is refused at startup — "a zero price is not free service; it is a key
# nobody filled in" — and it would turn admission into a no-op. Spend recorded
# against this table is therefore notional; real spend on this route is zero.
# Values match the table tests/test_budget_validation.py proves fundable.
LLM_PRICING_VERSION=2026-08-dev-cliproxy
LLM_PRICING_EFFECTIVE_DATE=2026-08-01
LLM_PRICE_BATCH_INPUT_USD_PER_MTOK=0.5
LLM_PRICE_BATCH_CACHED_INPUT_USD_PER_MTOK=0.05
LLM_PRICE_BATCH_CACHE_WRITE_USD_PER_MTOK=0.5
LLM_PRICE_BATCH_OUTPUT_USD_PER_MTOK=1.0
LLM_PRICE_SESSION_INPUT_USD_PER_MTOK=2.0
LLM_PRICE_SESSION_CACHED_INPUT_USD_PER_MTOK=0.2
LLM_PRICE_SESSION_CACHE_WRITE_USD_PER_MTOK=2.5
LLM_PRICE_SESSION_OUTPUT_USD_PER_MTOK=10.0

# Dev/noi bo tren route thue bao: khong tran USD, khong tran per-user.
# Doi lai 50/10/30/5/5 va 20/1/3/3/15 khi tro vao API tinh tien theo call.
LLM_BUDGET_MONTHLY_USD=0
LLM_BUDGET_ANALYSIS_USD=0
LLM_BUDGET_TURN_USD=0
LLM_BUDGET_EMERGENCY_USD=0
LLM_BUDGET_EVAL_USD=0
LLM_USER_TURN_STARTS_PER_DAY=0
LLM_USER_ACTIVE_TURNS=0
LLM_SYSTEM_ACTIVE_TURNS=0
LLM_USER_DAILY_USD=0
LLM_USER_ROLLING_30D_USD=0

# Alpha Desk external retrieval. This file is git-ignored; never copy this
# credential into Compose, manifests, fixtures, or committed configuration.
TAVILY_API_KEY=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
WEB_TOOLS_ENABLED=true
EXECUTOR_ENABLED=true
LLM_EVAL_RUN_COST_CEILING_USD=0

#DNSE Lightspeed API
API_KEY=eyJvcmciOiJkbnNlIiwiaWQiOiIxYmY3ZjcyMDg5NDA0NGIyYWM3MzNlYzE3NWE2MjFjZSIsImgiOiJtdXJtdXIxMjgifQ==
API_SECRECT=7wKDzvYA724o98OFORs5Q7VdnpJ5StDF8pqAO8LHWO8N-AFypBzH1okDrWjAj1ilVXgkLj9CKSW1v4FN8nAMiw
