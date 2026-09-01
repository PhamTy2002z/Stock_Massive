"""Application configuration using pydantic-settings."""
from datetime import date
from functools import lru_cache

from pydantic import field_validator
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

    # Alpha Desk — tuyến LLM, hai model theo workload, và giá của chúng
    # (src/core/llm/). Tắt mặc định: đây là kênh trả tiền, nên
    # một lần triển khai phải chủ động bật chứ không phải chủ động tắt.
    #
    # Mã model nằm ở đây và không ở đâu khác trong mã nguồn. Đó chính là lý do
    # tồn tại của boundary — đổi tuyến phải chỉ là đổi biến môi trường, mà một
    # hằng số biên dịch trong module thì sống sót qua lần đổi đó. Giá trị mặc
    # định là cặp production đã chốt; lane dev trỏ LLM_BASE_URL vào CLIProxyAPI
    # cục bộ và ghi đè cả hai model.
    alpha_desk_enabled: bool = False
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
    # bằng chứng, và transcript không giữ chỗ cho nó — nên cờ này chỉ khiến
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
    # Whether this route reads images. Off by default and for the same reason
    # `prompt_cache_control` is: the only way to learn what a proxied route does
    # with a block it was not measured on is to send it one. Turn it on after
    # `make probe-vision` passes, never before.
    #
    # This is deliberately *not* a sixth Capability Probe check.
    # `enforce_capability_probe` raises when a check the route *answered* fails
    # and Alpha Desk is enabled, so a missing side capability would stop the API
    # from booting — and the probe already spends five real model calls on every
    # restart.
    llm_vision_enabled: bool = False
    # The model string `make probe-vision` last passed on. `_cached_result` in
    # the probe is process-global and not keyed by model, so nothing else would
    # notice `LLM_MODEL_SESSION` moving to a model the flag was never measured
    # against. Startup compares the two and says so; it does not block, for the
    # same reason this is not a probe check.
    llm_vision_measured_model: str = ""

    # Open-web tools use their own Redis lane and Tavily credential. They are
    # off by default because each enabled Turn can spend external-provider
    # allowance independently of the model budget ledger.
    tavily_api_key: str = ""
    web_tools_enabled: bool = False
    web_fetch_max_bytes: int = 512 * 1024
    web_domain_denylist: str = ""
    # Redis-backed fleet windows. The first preserves the existing provider
    # allowance; the second prevents one hot publisher from consuming all of
    # it. Per-Turn egress remains owned by the agent lane profile.
    web_fleet_requests_per_minute: int = 30
    web_domain_requests_per_minute: int = 30

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

    # Năm trần chi tiêu per-user. Là cấu hình chứ không phải hằng số vì
    # một account được tiêu bao nhiêu trong ngày là quyết định chi tiêu: bản
    # nội bộ chạy qua route thuê bao trả lời khác hẳn bản phục vụ người lạ trên
    # một API tính tiền theo call. Con số dưới đây là mặc định, nên hợp
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
    # Turn chứ không theo IP. Sau proxy Next mọi user chung một
    # IP, nên limiter `heavy` sẽ chặn tất cả cùng lúc ngay đợt reconnect đầu.
    # Trần rộng hơn `heavy` một cách có chủ ý: EventSource tự kết nối lại sau
    # khoảng ba giây, nên một mạng chập chờn sinh ra nhiều lần thử hợp lệ.
    alpha_turn_subscribe_user_max: int = 60  # lượt/cửa sổ, mỗi user
    alpha_turn_subscribe_turn_max: int = 30  # lượt/cửa sổ, mỗi Turn
    alpha_turn_subscribe_window: int = 60  # giây

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

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
