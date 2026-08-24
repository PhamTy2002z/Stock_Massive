"""Application configuration using pydantic-settings."""
from datetime import date
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/stockmassive"

    # Auth (JWT)
    auth_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # CORS
    cors_origins: str = "http://localhost:3000"  # Comma-separated origins

    # Vnstock
    vnstock_source: str = "VCI"  # Default data source (VCI is most reliable)
    # VNSTOCK_API_KEY cố ý không khai ở đây: vnstock đọc thẳng từ os.environ để
    # quyết định tier (20 request/phút khi không thấy, 60 khi thấy). Khai lại
    # thành setting sẽ đọc được cả từ .env — nơi vnstock không nhìn tới — nên hai
    # bên có thể lệch nhau. Xem API_KEY_ENV_VAR ở src/core/quota.py, nơi cùng
    # biến môi trường đó quyết định giãn cách của Redis arbiter.

    # FiinQuant — Main Source cho market và valuation, xem docs/adr/0002
    fiinquant_username: str = ""
    fiinquant_password: str = ""

    # Universe — tập mã được thu thập và phục vụ, trần 100 mã (src/stocks/universe.py).
    # Rỗng là hợp lệ: ứng dụng chạy được và Collector không có gì để làm.
    universe_symbols: str = ""  # Comma-separated

    # DNSE realtime ingestion is opt-in because it opens a long-lived external
    # feed and writes continuously. Enabling it requires credentials and Redis;
    # startup rejects a partial configuration instead of running without hot
    # projections or reconnect-safe health.
    realtime_ingestion_enabled: bool = False
    dnse_api_key: SecretStr | None = None
    dnse_api_secret: SecretStr | None = None
    dnse_board_ids: str = "G1"
    realtime_queue_size: int = Field(default=2_000, ge=1, le=100_000)
    realtime_worker_count: int = Field(default=1, ge=1, le=8)
    realtime_shutdown_timeout_seconds: float = Field(default=15.0, gt=0, le=120)

    # Upstash Redis (supports both naming conventions)
    upstash_redis_url: str = ""
    upstash_redis_token: str = ""
    upstash_redis_rest_url: str = ""  # Alternative name from Upstash dashboard
    upstash_redis_rest_token: str = ""  # Alternative name from Upstash dashboard
    cache_redis_url: str = ""  # Standard Redis URL for local/self-hosted deployments

    @property
    def redis_url(self) -> str:
        """Get Redis URL (supports both naming conventions)."""
        return self.upstash_redis_rest_url or self.upstash_redis_url

    @property
    def redis_token(self) -> str:
        """Get Redis token (supports both naming conventions)."""
        return self.upstash_redis_rest_token or self.upstash_redis_token

    # Scheduler
    scheduler_enabled: bool = True
    intraday_collect_hour: int = 15
    intraday_collect_minute: int = 30
    intraday_symbols: str = "VCB,FPT,VNM,VIC,VHM"  # Comma-separated VN30 subset
    intraday_retention_days: int = 30

    # Profit Ranking Census — đếm lợi nhuận toàn bộ HOSE+HNX để dựng Profit
    # Leaders Cohort (src/stocks/census.py, docs/adr/0004). Chiếm đúng khung
    # Chủ nhật 02:00 mà job financial_statements đã bỏ lại.
    #
    # Hạn mức vnstock là chỗ nghẽn thật: ~1.600 mã × 2 request, trên 20
    # request/phút khi không có API key. Một lần chạy đầy không xong trong một
    # lượt, nên lần sau bỏ qua mã đã có số ở kỳ đang xét. Lần thử lại hằng ngày
    # lúc 03:00 chỉ đuổi theo số mã còn thiếu ở kỳ mới, nên nó không đọc lại
    # danh sách niêm yết.
    #
    # Không còn tham số giãn nhịp riêng: nhịp gọi thuộc về tài khoản, và
    # src/core/quota.py giữ nó cho mọi đường gọi vnstock (docs/adr/0014).
    profit_census_enabled: bool = True
    profit_census_weekday: int = 6  # Chủ nhật
    profit_census_hour: int = 2
    profit_census_minute: int = 0
    profit_census_retry_hour: int = 3
    profit_census_retry_minute: int = 0

    # Cohort — 50 chỗ trong Universe dành cho nhóm dẫn đầu lợi nhuận
    # (src/stocks/cohort.py). Ngưỡng kích hoạt là 45 chứ không phải 50: chờ đủ
    # cả 50 mã evaluable sẽ để một mã gặp sự cố nhà cung cấp giữ cả bảng xếp
    # hạng của một quý ngoài vòng phục vụ. Ngưỡng 0,95 là mức phủ mà một kỳ báo
    # cáo phải đạt trước khi được xếp hạng — xếp hạng một kỳ mà nửa thị trường
    # chưa báo cáo là tôn vinh ai nộp sớm.
    cohort_size: int = 50
    cohort_activation_min_members: int = 45
    rankable_period_coverage: float = 0.95

    # Collector — chu kỳ thu thập Snapshot cho Universe (src/stocks/collector.py).
    # Bật mặc định: Universe rỗng thì chu kỳ không làm gì, và với Universe đã khai
    # thì đây là đường duy nhất dữ liệu chảy vào SnapshotStore. Chạy sau khi thị
    # trường đóng cửa lúc 15:00. Đặt 16:15 để không đụng khung giờ của các job
    # sẵn có (intraday 15:30, sector historical 15:45, cleanup 16:00):
    # tiến trình chỉ có một worker, và hai job gọi ra nhà cung cấp cùng lúc là
    # hai job tranh nhau đúng một kết nối FiinQuant.
    collector_enabled: bool = True
    collector_hour: int = 16
    collector_minute: int = 15

    # Backfill — nạp lịch sử sâu một lần cho mỗi mã (src/stocks/backfill.py).
    # Tắt mặc định như các job nặng khác: đây là thứ tiêu hạn mức vnstock nhiều
    # nhất trong hệ thống, nên bật là một quyết định của người vận hành. Chạy
    # sau chu kỳ thu thập; trần số mã mỗi lần chạy để không tiêu hết hạn mức mà
    # chu kỳ hằng ngày cũng đang dùng.
    backfill_enabled: bool = False
    backfill_hour: int = 17
    backfill_minute: int = 0
    backfill_symbols_per_run: int = 5
    # Độ sâu lịch sử cần nạp, và mốc mà Main Source đã với tới (đo thực tế:
    # FiinQuant free trả ~5 năm nến ngày). Khai bằng cấu hình vì cả hai đều là
    # lựa chọn sản phẩm chứ không phải giới hạn kỹ thuật, và vì hạ mốc dưới
    # xuống là cách đóng khoảng lịch sử mà hiện chưa nguồn nào nạp.
    backfill_depth_days: int = 10 * 365
    backfill_main_source_days: int = 5 * 365

    # Corporate Actions — nạp sự kiện quyền của Universe
    # (src/stocks/corporate_action_collector.py, docs/adr/0006). Nhịp chậm vì
    # sự kiện quyền diễn ra vài lần một năm, không phải mỗi phiên: một request
    # cho mỗi mã, cả Universe gọn trong một lần chạy dưới hạn mức vnstock.
    #
    # Bật mặc định như Collector: Universe rỗng thì không có gì để nạp, còn khi
    # đã khai thì đây là đầu vào duy nhất của việc điều chỉnh giá lúc đọc — thiếu
    # nó, mọi cửa sổ chứa một ex-date đều bị từ chối.
    #
    # Sáng thứ Bảy 04:00: tránh khung census Chủ nhật 02:00 và lần thử lại 03:00
    # hằng ngày, vì cả ba tiêu cùng một hạn mức vnstock.
    corporate_actions_enabled: bool = True
    corporate_actions_weekday: int = 5  # Thứ Bảy
    corporate_actions_hour: int = 4
    corporate_actions_minute: int = 0

    # Warm-up — nạp lại cửa sổ tín hiệu gần đây cho một mã (src/stocks/warmup.py).
    # 25 phiên: một Volume Spike cần 20 phiên nền cộng phiên đích, phần dư để
    # một phiên nhà cung cấp chưa kịp bổ sung không làm mã đó thiếu nền.
    warmup_window_trading_days: int = 25

    # Market index — nạp chuỗi phiên của chỉ số làm benchmark
    # (src/stocks/market_index.py, docs/adr/0017). Bật mặc định như Collector:
    # một chỉ số là một request mỗi lần chạy, và đây là đầu vào duy nhất của
    # `relative_strength.beta_vs_market_index`.
    #
    # 275 phiên = 250 phiên field khai + biên 25 phiên. Hằng số mặc định nằm ở
    # `MARKET_INDEX_WINDOW_TRADING_DAYS` và được viết bằng chính mức sàn của
    # field, để hạ độ sâu ở đây là một quyết định vận hành chứ không phải một
    # thay đổi âm thầm làm field từ chối vì `insufficient_history`.
    #
    # 23:30: sau lần thu thập bù 23:00, để chỉ số và các mã cùng dừng ở một
    # Trading Day — beta đo trên hai chuỗi lệch nhau một phiên là beta trên hai
    # đoạn thị trường khác nhau.
    market_index_enabled: bool = True
    market_index_hour: int = 23
    market_index_minute: int = 30
    market_index_window_trading_days: int = 275

    # Market catch-up — thu thập lại khi Trading Day chưa nhúc nhích
    # (docs/adr/0005, spec 0003 §11). Main Source bổ sung phiên vừa đóng vào
    # muộn trong tối, nên chu kỳ 16:15 thường xuyên chỉ lấy được phiên hôm
    # trước; không có lần chạy này thì phiên đó không bao giờ được thu.
    #
    # Ba mốc chứ không phải một: lần chạy 23:00 duy nhất trước đây để cả buổi
    # tối trôi qua trước khi thử lại, mà hạn phục vụ là 07:00 ICT và mỗi lần
    # thử sớm hơn là thêm vài giờ cho đường ống chạy. Mỗi mốc là cùng một lời
    # gọi và tự bỏ qua ngay khi một Trading Day mới đã tồn tại, nên chi phí của
    # ba mốc trong một tối bình thường là ba câu truy vấn.
    market_catchup_enabled: bool = True
    market_catchup_times: str = "18:30,21:30,23:00"

    # Analysis Run — cửa sổ trước khi một lượt dựng Analysis còn kẹt ở
    # `producing` bị coi là đã chết và được thu dọn (src/alpha/analysis_run.py).
    # Một tiến trình chết hoặc một lần deploy giữa chừng để lại lượt chạy ở
    # `producing` mà không còn ai đẩy tiếp; không có mốc này thì mã đó giữ chỗ
    # cho tới khi có người để ý — với nhịp chạy hằng đêm nghĩa là cả một ngày.
    #
    # 30 phút: dài hơn hẳn một lượt dựng thật (một lần gọi model, không có vòng
    # tool), nên không bao giờ thu dọn nhầm một lượt đang chạy.
    #
    # Nhịp quét đặt đúng bằng cửa sổ chứ không thêm một tham số nữa: một lượt
    # chết được thu dọn trong khoảng một tới hai lần cửa sổ, đủ nhanh và bớt
    # được một núm vặn mà không ai chỉnh riêng.
    analysis_run_stuck_minutes: int = 30

    # Nhịp rút hàng đợi Analysis (src/alpha/dispatcher.py). Một phút, vì cái
    # đang chờ là một người: một mã thêm vào Watchlist đi theo lane on-demand và
    # đứng đầu hàng đợi, nên khoảng cách giữa hai tick là phần lớn thời gian họ
    # nhìn spinner. Với cohort hằng đêm nhịp này gần như vô nghĩa — hàng đợi
    # được rút liên tục trong một tick cho tới khi cạn.
    #
    # Một tick không rút quá ngần này lượt. Cái được chặn không phải chi phí —
    # ngân sách đã có trần riêng ở admission — mà là một tick chạy hàng giờ trên
    # cohort lớn rồi chồng lên tick sau; hàng đợi chính là bảng, nên phần chưa
    # rút không mất đi đâu cả.
    analysis_dispatch_interval_seconds: int = 60
    analysis_dispatch_batch_size: int = 25

    # Alpha Desk — tuyến LLM, hai model theo workload, và giá của chúng
    # (src/core/llm/, docs/adr/0014). Tắt mặc định: đây là kênh trả tiền, nên
    # một lần triển khai phải chủ động bật chứ không phải chủ động tắt.
    #
    # Mã model nằm ở đây và không ở đâu khác trong mã nguồn. Đó chính là lý do
    # tồn tại của boundary — đổi tuyến phải chỉ là đổi biến môi trường, mà một
    # hằng số biên dịch trong module thì sống sót qua lần đổi đó. Giá trị mặc
    # định là cặp production đã chốt; lane dev trỏ LLM_BASE_URL vào CLIProxyAPI
    # cục bộ và ghi đè cả hai model.
    alpha_desk_enabled: bool = False
    # Whether an Analysis is produced by the evidence loop or by the one shot it
    # replaced (``src/alpha/analysis_loop.py`` vs ``generation.py``). Both are
    # reachable on purpose: the loop trades reproducibility for audit, and a
    # deployment that finds the trade wrong turns it off here rather than waiting
    # for a revert. Off, an Analysis is stamped ``promptVersion v1`` and reads
    # eleven fixed figures; on, ``v2`` and whatever the model asked for.
    analysis_evidence_loop_enabled: bool = True
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model_batch: str = "gpt-5.6-luna"
    llm_model_session: str = "gpt-5.6-terra"
    llm_request_timeout_seconds: float = 120.0
    # Streaming là mặc định, nhưng nó là thuộc tính của *tuyến*, không phải của
    # lời gọi: một tuyến OpenAI-compatible có thể stream tool call mà không gửi
    # kèm index của upstream, và `StreamAssembler` từ chối đoán index — đó là bug
    # đã đo được, không phải sự khắt khe vô cớ. Gemini qua endpoint
    # OpenAI-compatible là tuyến như vậy: mỗi fragment là một tool call trọn vẹn
    # nhưng không có `index`, nên chỉ đường không-stream mới dùng được. Tắt cờ
    # này thì tuyến vẫn chạy đủ chức năng: câu trả lời tới nguyên khối, và không
    # có token nào được phát ra client giữa đường (loop phát activity và block,
    # không phát token).
    llm_streaming_enabled: bool = True
    # Một tuyến phục vụ *thinking model* có thể đòi lịch sử suy luận của chính nó
    # quay lại cùng lịch sử tool-call: DeepSeek v4-pro qua TokenRouter từ chối vòng
    # thứ hai với `messages[1].reasoning_content is required for thinking tool-call
    # history`. Transcript ở đây không lưu chuỗi suy luận của model — nó không phải
    # bằng chứng, và Evidence Manifest không có chỗ cho nó — nên cờ này chỉ khiến
    # mỗi assistant turn có tool call mang theo một chỗ giữ chỗ hợp lệ. Đo được:
    # tuyến nhận một khoảng trắng nhưng từ chối chuỗi rỗng.
    llm_reasoning_history_required: bool = False
    # Explicit paid-call switch for the boot-time Capability Probe. Test code
    # turns this off by name; no code path guesses that pytest is running.
    llm_capability_probe_enabled: bool = True
    # Breaker rate-limit dùng chung qua Redis (`core/llm/breaker.py`). Bật mặc
    # định vì nó chỉ tiết kiệm đúng một request đã bị tuyến từ chối; tắt được
    # bằng một biến vì đây là cơ chế mới nhất trong tuyến LLM. Redis chết thì
    # breaker admit lời gọi — fail-open, khác `core/quota.py` một cách có chủ ý,
    # và lý do nằm ở docstring của module đó.
    llm_route_breaker_enabled: bool = True
    # `cache_control` trên prefix ổn định của system prompt. Mặc định **tắt**:
    # nó là cú pháp của Anthropic mà một tuyến OpenAI-compatible có thể từ chối,
    # và `cache_control` đặt sai chỗ phá cache thay vì tạo cache. Quy trình bật:
    # đặt cờ, chạy Capability Probe, và chỉ giữ cờ nếu check
    # `prompt_cache_control` xanh.
    llm_prompt_cache_control_enabled: bool = False

    # Câu hỏi gợi ý dưới mỗi câu trả lời (docs/adr/0020). Một lần gọi model rẻ
    # nữa cho mỗi Turn hoàn tất, nên nó có công tắc riêng: giá trị của nó là
    # tiện lợi, còn chi phí thì cộng dồn trên mọi Turn.
    alpha_desk_suggestions_enabled: bool = True

    # Open-web tools use their own Redis lane and Tavily credential. They are
    # off by default because each enabled Turn can spend external-provider
    # allowance independently of the vnstock account arbiter.
    tavily_api_key: str = ""
    web_tools_enabled: bool = False
    web_fetch_max_bytes: int = 512 * 1024
    web_domain_denylist: str = ""

    # Bản build nào đã trả lời — một trong các trường của Evidence Manifest
    # (docs/adr/0015). Chỉ image build mới biết SHA, nên nó vào bằng biến môi
    # trường; mặc định "unknown" là câu trả lời trung thực cho một lần chạy cục
    # bộ, và trung thực hơn hẳn một chuỗi đoán được từ thư mục làm việc.
    git_sha: str = "unknown"

    # Khối giá mà Budget Validation đọc lúc khởi động. Đơn vị USD trên một
    # triệu token, khai riêng cho từng workload: batch và interactive là hai
    # model khác nhau với giá khác nhau, một khối dùng chung sẽ định sai giá
    # cho lane mà nó không được viết cho.
    #
    # Số 0 không phải "miễn phí": đó là một key chưa ai điền, và Budget
    # Validation từ chối nó thay vì chấp nhận một cấu hình mà trên giấy tờ
    # không tốn gì. Token suy luận không có giá riêng — nó tính theo giá
    # output, nên năm bộ đếm gặp bốn mức giá.
    llm_pricing_version: str = ""
    llm_pricing_effective_date: date | None = None
    llm_price_batch_input_usd_per_mtok: float = 0.0
    llm_price_batch_cached_input_usd_per_mtok: float = 0.0
    llm_price_batch_cache_write_usd_per_mtok: float = 0.0
    llm_price_batch_output_usd_per_mtok: float = 0.0
    llm_price_session_input_usd_per_mtok: float = 0.0
    llm_price_session_cached_input_usd_per_mtok: float = 0.0
    llm_price_session_cache_write_usd_per_mtok: float = 0.0
    llm_price_session_output_usd_per_mtok: float = 0.0

    # Hạn mức $45/tháng và ba lane chia nhau nó. Là cấu hình chứ không phải
    # hằng số vì hạn mức là một quyết định chi tiêu, không phải lời hứa của sản
    # phẩm; Budget Validation kiểm tra ba lane vẫn cộng đúng bằng hạn mức đó.
    llm_budget_monthly_usd: float = 45.0
    llm_budget_analysis_usd: float = 10.0
    llm_budget_turn_usd: float = 30.0
    llm_budget_emergency_usd: float = 5.0

    # Năm trần per-user của docs/adr/0014. Là cấu hình chứ không phải hằng số vì
    # một account được tiêu bao nhiêu trong ngày là quyết định chi tiêu: bản
    # nội bộ chạy qua route thuê bao trả lời khác hẳn bản phục vụ người lạ trên
    # một API tính tiền theo call. Con số của ADR vẫn là mặc định ở đây, nên hợp
    # đồng còn một chỗ được ghi lại và một biến env là đủ để siết lại.
    #
    # `0` = không giới hạn: mọi call vẫn được ghi vào `llm_call_usage`, chỉ bỏ
    # phần từ chối.
    llm_user_turn_starts_per_day: int = 20
    llm_user_active_turns: int = 1
    llm_system_active_turns: int = 3
    llm_user_daily_usd: float = 3.0
    llm_user_rolling_30d_usd: float = 15.0


    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_standard_max: int = 100  # requests per window
    rate_limit_standard_window: int = 60  # seconds
    rate_limit_heavy_max: int = 20  # requests per window
    rate_limit_heavy_window: int = 60  # seconds

    # Đăng ký và kết nối lại một Turn có bộ đếm riêng, tính theo user và theo
    # Turn chứ không theo IP (docs/adr/0013). Sau proxy Next mọi user chung một
    # IP, nên limiter `heavy` sẽ chặn tất cả cùng lúc ngay đợt reconnect đầu.
    # Trần rộng hơn `heavy` một cách có chủ ý: EventSource tự kết nối lại sau
    # khoảng ba giây, nên một mạng chập chờn sinh ra nhiều lần thử hợp lệ.
    alpha_turn_subscribe_user_max: int = 60  # lượt/cửa sổ, mỗi user
    alpha_turn_subscribe_turn_max: int = 30  # lượt/cửa sổ, mỗi Turn
    alpha_turn_subscribe_window: int = 60  # giây

    # Sector Historical Performance Job
    # Disabled until a persisted cache exists; otherwise every restart after
    # 15:45 retries a broad vnstock scan and starves interactive requests.
    sector_historical_enabled: bool = False
    sector_historical_hour: int = 15  # 15:45 ICT (after sector-performance job at 15:30)
    sector_historical_minute: int = 45
    sector_historical_delay: float = 1.2  # seconds between API calls (~50 req/min)

    @field_validator("llm_pricing_effective_date", mode="before")
    @classmethod
    def _blank_date_is_unset(cls, value: object) -> object:
        """Một biến môi trường rỗng nghĩa là chưa ai điền, không phải ngày sai.

        `docker-compose.yml` chuyển tiếp cả khối giá bằng `${VAR:-}`, nên một
        key chưa khai vào container dưới dạng chuỗi rỗng chứ không phải vắng
        mặt. Để nguyên thì container chết ngay ở `Settings()` — trước cả khi
        Budget Validation kịp nói ra điều nó muốn nói, rằng bảng giá này chưa
        được điền.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("market_catchup_times")
    @classmethod
    def _readable_catchup_times(cls, value: str) -> str:
        """Một mốc viết sai phải nổ lúc `Settings()` chứ không lúc lên lịch.

        Kiểm ở validator chứ không ở property đọc ra sau: property chỉ chạy khi
        `setup_scheduler` gọi tới, tức là sau khi tiến trình đã khởi động xong và
        người vận hành đã rời console. Đây cũng là quy ước của package signals —
        một khai báo tự kiểm chính nó ngay lúc được khai.

        Giờ và phút được kiểm biên chứ không chỉ kiểm kiểu: `"25:99"` là số hợp
        lệ và là một mốc không bao giờ nổ ra, tức một buổi tối im lặng không thu
        được phiên nào mà chẳng có gì báo.
        """
        _parse_catchup_times(value)
        return value

    @model_validator(mode="after")
    def _complete_realtime_configuration(self):
        if not self.realtime_ingestion_enabled:
            return self
        if (
            self.dnse_api_key is None
            or self.dnse_api_secret is None
            or not self.dnse_api_key.get_secret_value().strip()
            or not self.dnse_api_secret.get_secret_value().strip()
        ):
            raise ValueError(
                "realtime ingestion requires DNSE_API_KEY and DNSE_API_SECRET"
            )
        if not self.cache_redis_url and not (self.redis_url and self.redis_token):
            raise ValueError("realtime ingestion requires a configured Redis service")
        boards = [board.strip().upper() for board in self.dnse_board_ids.split(",")]
        if not boards or any(
            not board
            or len(board) > 32
            or any(
                character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for character in board
            )
            for board in boards
        ):
            raise ValueError("DNSE_BOARD_IDS contains an invalid board")
        return self

    @property
    def realtime_boards(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                board.strip().upper()
                for board in self.dnse_board_ids.split(",")
                if board.strip()
            )
        )

    @property
    def market_catchup_schedule(self) -> tuple[tuple[int, int], ...]:
        """Mỗi mốc thu thập bù dưới dạng `(giờ, phút)`, theo thứ tự trong ngày."""
        return _parse_catchup_times(self.market_catchup_times)


def _parse_catchup_times(declared: str) -> tuple[tuple[int, int], ...]:
    """Đọc `"18:30,21:30,23:00"` thành các mốc, hoặc từ chối cả chuỗi."""
    parsed: list[tuple[int, int]] = []
    for entry in declared.split(","):
        entry = entry.strip()
        if not entry:
            continue
        hour, separator, minute = entry.partition(":")
        if not separator or not hour.isdigit() or not minute.isdigit():
            raise ValueError(
                f"{entry!r} không phải một mốc `HH:MM` trong MARKET_CATCHUP_TIMES"
            )
        if not (0 <= int(hour) <= 23 and 0 <= int(minute) <= 59):
            raise ValueError(
                f"{entry!r} nằm ngoài một ngày, nên là một mốc không bao giờ chạy"
            )
        parsed.append((int(hour), int(minute)))
    return tuple(sorted(parsed))


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
