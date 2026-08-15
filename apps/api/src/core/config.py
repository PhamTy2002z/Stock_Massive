"""Application configuration using pydantic-settings."""
from datetime import date
from functools import lru_cache

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

    # Market catch-up — thu thập lại lúc 23:00 khi Trading Day chưa nhúc nhích
    # (docs/adr/0005). Main Source bổ sung phiên vừa đóng vào muộn trong tối,
    # nên chu kỳ 16:15 thường xuyên chỉ lấy được phiên hôm trước; không có lần
    # chạy này thì phiên đó không bao giờ được thu.
    market_catchup_enabled: bool = True
    market_catchup_hour: int = 23
    market_catchup_minute: int = 0

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
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model_batch: str = "gpt-5.6-luna"
    llm_model_session: str = "gpt-5.6-terra"
    llm_request_timeout_seconds: float = 120.0
    # Explicit paid-call switch for the boot-time Capability Probe. Test code
    # turns this off by name; no code path guesses that pytest is running.
    llm_capability_probe_enabled: bool = True

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

    # Hạn mức $50/tháng và bốn lane chia nhau nó (docs/adr/0014). Là cấu hình
    # chứ không phải hằng số vì hạn mức là một quyết định chi tiêu, không phải
    # lời hứa của sản phẩm; Budget Validation kiểm tra bốn lane vẫn cộng đúng
    # bằng hạn mức đó.
    llm_budget_monthly_usd: float = 50.0
    llm_budget_analysis_usd: float = 10.0
    llm_budget_turn_usd: float = 30.0
    llm_budget_emergency_usd: float = 5.0
    llm_budget_eval_usd: float = 5.0

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_standard_max: int = 100  # requests per window
    rate_limit_standard_window: int = 60  # seconds
    rate_limit_heavy_max: int = 20  # requests per window
    rate_limit_heavy_window: int = 60  # seconds

    # Sector Historical Performance Job
    # Disabled until a persisted cache exists; otherwise every restart after
    # 15:45 retries a broad vnstock scan and starves interactive requests.
    sector_historical_enabled: bool = False
    sector_historical_hour: int = 15  # 15:45 ICT (after sector-performance job at 15:30)
    sector_historical_minute: int = 45
    sector_historical_delay: float = 1.2  # seconds between API calls (~50 req/min)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
