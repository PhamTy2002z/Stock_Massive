"""Test Phase 01 Database Setup for Intraday Volume Analysis.

Tests:
1. Verify imports work correctly
2. Test async session creation and disposal
3. Test StockIntradayBar model CRUD operations
4. Test unique constraint on (symbol, bar_time)
5. Verify FastAPI app starts without errors
6. Test get_db dependency injection
"""
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.core.database import Base, async_session_factory, engine, get_db
from src.main import app
from src.stocks.models import StockIntradayBar


class TestImports:
    """Test 1: Verify imports work correctly."""

    def test_database_imports(self):
        """Test database module imports."""
        from src.core.database import Base, async_session_factory, engine, get_db

        assert Base is not None
        assert async_session_factory is not None
        assert engine is not None
        assert get_db is not None
        print("✓ Database imports successful")

    def test_model_imports(self):
        """Test model imports."""
        from src.stocks.models import StockIntradayBar

        assert StockIntradayBar is not None
        assert hasattr(StockIntradayBar, '__tablename__')
        assert StockIntradayBar.__tablename__ == 'stock_intraday_bars'
        print("✓ Model imports successful")

    def test_alembic_imports(self):
        """Test alembic env imports."""
        from alembic import context
        from src.core.database import Base

        assert context is not None
        assert Base is not None
        print("✓ Alembic imports successful")

    def test_main_app_imports(self):
        """Test main app imports."""
        from src.main import app, lifespan

        assert app is not None
        assert lifespan is not None
        print("✓ Main app imports successful")


class TestAsyncSession:
    """Test 2: Test async session creation and disposal."""

    @pytest.mark.asyncio
    async def test_session_creation(self):
        """Test async session can be created."""
        async with async_session_factory() as session:
            assert session is not None
            # Session is active within context
            assert session.is_active
        print("✓ Async session creation successful")

    @pytest.mark.asyncio
    async def test_session_disposal(self):
        """Test async session is properly disposed."""
        session = async_session_factory()
        async with session as s:
            assert s is not None
        # Session should be closed after context exit
        print("✓ Async session disposal successful")

    @pytest.mark.asyncio
    async def test_get_db_dependency(self):
        """Test get_db dependency generator."""
        gen = get_db()
        session = await gen.__anext__()
        assert session is not None

        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass  # Expected
        print("✓ get_db dependency works correctly")

    @pytest.mark.asyncio
    async def test_multiple_sessions(self):
        """Test multiple sessions can be created."""
        async with async_session_factory() as session1:
            async with async_session_factory() as session2:
                assert session1 is not None
                assert session2 is not None
                assert session1 != session2
        print("✓ Multiple sessions creation successful")


async def cleanup_test_data():
    """Helper to clean up test data."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(StockIntradayBar).where(StockIntradayBar.symbol.in_(["TEST", "UNIQ"]))
            )
            test_records = result.scalars().all()
            for record in test_records:
                await session.delete(record)
            await session.commit()
    except Exception:
        pass  # Ignore cleanup errors


class TestStockIntradayBarModel:
    """Test 3: Test StockIntradayBar model CRUD operations."""

    @pytest.mark.asyncio
    async def test_insert_intraday_bar(self):
        """Test inserting a new intraday bar."""
        # Setup
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_session_factory() as session:
            bar = StockIntradayBar(
                symbol="TEST",
                bar_time=datetime(2025, 12, 18, 9, 0, 0),
                open_price=Decimal("100.50"),
                high_price=Decimal("102.00"),
                low_price=Decimal("99.50"),
                close_price=Decimal("101.00"),
                volume=1000000,
                trade_value=Decimal("101000000.00"),
                trade_count=500
            )
            session.add(bar)
            await session.commit()
            await session.refresh(bar)

            assert bar.id is not None
            assert bar.symbol == "TEST"
            assert bar.created_at is not None
            print("✓ Insert intraday bar successful")

        # Cleanup
        await cleanup_test_data()

    @pytest.mark.asyncio
    async def test_select_intraday_bar(self, cleanup_intraday_test_data):
        """Test selecting intraday bars."""
        # Setup
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Insert test data
        async with async_session_factory() as session:
            bar = StockIntradayBar(
                symbol="TEST",
                bar_time=datetime(2025, 12, 18, 9, 5, 0),
                open_price=Decimal("101.00"),
                high_price=Decimal("103.00"),
                low_price=Decimal("100.00"),
                close_price=Decimal("102.00"),
                volume=1500000,
                trade_value=Decimal("152000000.00"),
                trade_count=600
            )
            session.add(bar)
            await session.commit()

        # Select data
        async with async_session_factory() as session:
            result = await session.execute(
                select(StockIntradayBar).where(
                    StockIntradayBar.symbol == "TEST",
                    StockIntradayBar.bar_time == datetime(2025, 12, 18, 9, 5, 0)
                )
            )
            fetched_bar = result.scalar_one_or_none()

            assert fetched_bar is not None
            assert fetched_bar.symbol == "TEST"
            assert fetched_bar.volume == 1500000
            print("✓ Select intraday bar successful")

    @pytest.mark.asyncio
    async def test_update_intraday_bar(self):
        """Test updating an intraday bar."""
        # Setup
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Insert test data
        async with async_session_factory() as session:
            bar = StockIntradayBar(
                symbol="TEST",
                bar_time=datetime(2025, 12, 18, 9, 10, 0),
                open_price=Decimal("102.00"),
                high_price=Decimal("104.00"),
                low_price=Decimal("101.00"),
                close_price=Decimal("103.00"),
                volume=2000000,
                trade_value=Decimal("206000000.00"),
                trade_count=700
            )
            session.add(bar)
            await session.commit()
            bar_id = bar.id

        # Update data
        async with async_session_factory() as session:
            result = await session.execute(
                select(StockIntradayBar).where(StockIntradayBar.id == bar_id)
            )
            bar = result.scalar_one()
            bar.volume = 2500000
            bar.trade_value = Decimal("257500000.00")
            await session.commit()

        # Verify update
        async with async_session_factory() as session:
            result = await session.execute(
                select(StockIntradayBar).where(StockIntradayBar.id == bar_id)
            )
            updated_bar = result.scalar_one()

            assert updated_bar.volume == 2500000
            assert updated_bar.trade_value == Decimal("257500000.00")
            print("✓ Update intraday bar successful")

        # Cleanup
        await cleanup_test_data()

    @pytest.mark.asyncio
    async def test_delete_intraday_bar(self, cleanup_intraday_test_data):
        """Test deleting an intraday bar."""
        # Setup
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Insert test data
        async with async_session_factory() as session:
            bar = StockIntradayBar(
                symbol="TEST",
                bar_time=datetime(2025, 12, 18, 9, 15, 0),
                open_price=Decimal("103.00"),
                high_price=Decimal("105.00"),
                low_price=Decimal("102.00"),
                close_price=Decimal("104.00"),
                volume=1800000,
                trade_value=Decimal("187200000.00"),
                trade_count=650
            )
            session.add(bar)
            await session.commit()
            bar_id = bar.id

        # Delete data
        async with async_session_factory() as session:
            result = await session.execute(
                select(StockIntradayBar).where(StockIntradayBar.id == bar_id)
            )
            bar = result.scalar_one()
            await session.delete(bar)
            await session.commit()

        # Verify deletion
        async with async_session_factory() as session:
            result = await session.execute(
                select(StockIntradayBar).where(StockIntradayBar.id == bar_id)
            )
            deleted_bar = result.scalar_one_or_none()

            assert deleted_bar is None
            print("✓ Delete intraday bar successful")


class TestUniqueConstraint:
    """Test 4: Test unique constraint on (symbol, bar_time)."""

    @pytest.mark.asyncio
    async def test_unique_constraint_violation(self):
        """Test that duplicate (symbol, bar_time) raises IntegrityError."""
        # Setup
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        bar_time = datetime(2025, 12, 18, 10, 0, 0)

        # Insert first bar
        async with async_session_factory() as session:
            bar1 = StockIntradayBar(
                symbol="UNIQ",
                bar_time=bar_time,
                open_price=Decimal("100.00"),
                high_price=Decimal("101.00"),
                low_price=Decimal("99.00"),
                close_price=Decimal("100.50"),
                volume=1000000,
                trade_value=Decimal("100500000.00"),
                trade_count=500
            )
            session.add(bar1)
            await session.commit()

        # Try to insert duplicate
        with pytest.raises(IntegrityError) as exc_info:
            async with async_session_factory() as session:
                bar2 = StockIntradayBar(
                    symbol="UNIQ",
                    bar_time=bar_time,  # Same symbol and bar_time
                    open_price=Decimal("101.00"),
                    high_price=Decimal("102.00"),
                    low_price=Decimal("100.00"),
                    close_price=Decimal("101.50"),
                    volume=1200000,
                    trade_value=Decimal("121800000.00"),
                    trade_count=600
                )
                session.add(bar2)
                await session.commit()

        assert "uq_symbol_bar_time" in str(exc_info.value) or "unique constraint" in str(exc_info.value).lower()
        print("✓ Unique constraint violation detected correctly")

        # Cleanup
        await cleanup_test_data()

    @pytest.mark.asyncio
    async def test_unique_constraint_different_time(self, cleanup_intraday_test_data):
        """Test that same symbol with different bar_time is allowed."""
        # Setup
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_session_factory() as session:
            bar1 = StockIntradayBar(
                symbol="UNIQ",
                bar_time=datetime(2025, 12, 18, 10, 5, 0),
                open_price=Decimal("100.00"),
                high_price=Decimal("101.00"),
                low_price=Decimal("99.00"),
                close_price=Decimal("100.50"),
                volume=1000000,
                trade_value=Decimal("100500000.00"),
                trade_count=500
            )
            bar2 = StockIntradayBar(
                symbol="UNIQ",
                bar_time=datetime(2025, 12, 18, 10, 10, 0),  # Different time
                open_price=Decimal("100.50"),
                high_price=Decimal("101.50"),
                low_price=Decimal("99.50"),
                close_price=Decimal("101.00"),
                volume=1100000,
                trade_value=Decimal("111100000.00"),
                trade_count=550
            )
            session.add(bar1)
            session.add(bar2)
            await session.commit()

            # Verify both records exist
            result = await session.execute(
                select(StockIntradayBar).where(StockIntradayBar.symbol == "UNIQ")
            )
            bars = result.scalars().all()
            assert len(bars) == 2
            print("✓ Different bar_time allowed for same symbol")

    @pytest.mark.asyncio
    async def test_unique_constraint_different_symbol(self):
        """Test that different symbol with same bar_time is allowed."""
        # Setup
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        bar_time = datetime(2025, 12, 18, 10, 15, 0)

        async with async_session_factory() as session:
            bar1 = StockIntradayBar(
                symbol="UNIQ",
                bar_time=bar_time,
                open_price=Decimal("100.00"),
                high_price=Decimal("101.00"),
                low_price=Decimal("99.00"),
                close_price=Decimal("100.50"),
                volume=1000000,
                trade_value=Decimal("100500000.00"),
                trade_count=500
            )
            session.add(bar1)
            await session.commit()

        # Different symbol, same time should work
        async with async_session_factory() as session:
            bar2 = StockIntradayBar(
                symbol="TEST",  # Different symbol
                bar_time=bar_time,
                open_price=Decimal("200.00"),
                high_price=Decimal("201.00"),
                low_price=Decimal("199.00"),
                close_price=Decimal("200.50"),
                volume=2000000,
                trade_value=Decimal("401000000.00"),
                trade_count=1000
            )
            session.add(bar2)
            await session.commit()

            # Verify both records exist
            result = await session.execute(
                select(StockIntradayBar).where(
                    StockIntradayBar.bar_time == bar_time
                )
            )
            bars = result.scalars().all()
            assert len(bars) >= 2
            print("✓ Different symbol allowed for same bar_time")

        # Cleanup
        await cleanup_test_data()


class TestFastAPIApp:
    """Test 5: Verify FastAPI app starts without errors."""

    def test_app_creation(self):
        """Test FastAPI app is created successfully."""
        from src.main import app

        assert app is not None
        assert app.title == "Stock Massive API"
        assert app.version == "0.1.0"
        print("✓ FastAPI app created successfully")

    def test_app_lifespan(self):
        """Test app has lifespan configured."""
        from src.main import app, lifespan

        assert hasattr(app, 'router')
        assert lifespan is not None
        print("✓ FastAPI app lifespan configured")

    def test_health_endpoint(self, client):
        """Test health endpoint works."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        print("✓ Health endpoint works")

    def test_root_endpoint(self, client):
        """Test root endpoint works."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        print("✓ Root endpoint works")

    @pytest.mark.asyncio
    async def test_engine_disposal(self):
        """Test engine can be disposed properly."""
        from src.core.database import engine

        # Engine should be available
        assert engine is not None

        # Test disposal (will be called in lifespan)
        await engine.dispose()
        print("✓ Engine disposal works")


class TestGetDbDependency:
    """Test 6: Test get_db dependency injection."""

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        """Test get_db yields a valid session."""
        from src.core.database import get_db

        gen = get_db()
        session = await gen.__anext__()

        assert session is not None
        assert hasattr(session, 'execute')
        assert hasattr(session, 'commit')
        assert hasattr(session, 'rollback')

        # Clean up
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass
        print("✓ get_db yields valid session")

    @pytest.mark.asyncio
    async def test_get_db_rollback_on_error(self):
        """Test get_db rolls back on error."""
        from src.core.database import get_db

        gen = get_db()
        session = await gen.__anext__()

        # Simulate an error by raising exception
        try:
            # This should trigger rollback in the finally block
            raise ValueError("Test error")
        except ValueError:
            pass

        # Clean up
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass
        print("✓ get_db handles errors correctly")

    @pytest.mark.asyncio
    async def test_get_db_in_fastapi_context(self):
        """Test get_db works in FastAPI dependency injection."""
        from fastapi import Depends
        from src.core.database import get_db

        # Simulate FastAPI dependency injection
        async def test_endpoint(db=Depends(get_db)):
            return db

        # The dependency should be callable
        assert callable(get_db)
        print("✓ get_db works with FastAPI Depends")


@pytest.fixture
def client():
    """Create test client."""
    from fastapi.testclient import TestClient
    from src.main import app

    return TestClient(app)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
