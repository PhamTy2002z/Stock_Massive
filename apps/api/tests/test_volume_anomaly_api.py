#!/usr/bin/env python
"""Integration test script for volume anomaly detection API endpoint."""
import time
import sys
import json
from typing import Dict, Any
import httpx

API_BASE_URL = "http://localhost:8000/api/v1/stocks"
TEST_SYMBOLS = ["VCB", "FPT", "VNM"]
INVALID_SYMBOL = "INVALID123"


def check_endpoint(symbol: str, days: int = 20) -> Dict[str, Any]:
    """Test volume anomaly endpoint and measure response time."""
    url = f"{API_BASE_URL}/{symbol}/volume-anomalies?days={days}"

    start_time = time.time()
    try:
        response = httpx.get(url, timeout=10.0)
        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "symbol": symbol,
            "status_code": response.status_code,
            "response_time_ms": elapsed_ms,
            "success": response.status_code == 200,
            "data": response.json() if response.status_code == 200 else None,
            "error": response.json() if response.status_code != 200 else None,
        }
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "symbol": symbol,
            "status_code": None,
            "response_time_ms": elapsed_ms,
            "success": False,
            "data": None,
            "error": str(e),
        }


def validate_response_structure(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate response structure matches VolumeAnomalyResponse schema."""
    errors = []
    warnings = []

    # Required fields
    required_fields = ["symbol", "days_analyzed", "trading_session", "time_slots", "generated_at", "latest_date"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if "time_slots" in data:
        time_slots = data["time_slots"]

        # Check 72 slots
        if len(time_slots) != 72:
            errors.append(f"Expected 72 time slots, got {len(time_slots)}")

        # Validate first slot structure
        if time_slots:
            slot = time_slots[0]
            required_slot_fields = ["hour", "minute_bucket", "time_label", "current_volume",
                                   "avg_volume", "volume_ratio", "anomaly_level", "sample_count"]
            for field in required_slot_fields:
                if field not in slot:
                    errors.append(f"Missing slot field: {field}")

            # Check anomaly level values
            valid_levels = ["normal", "elevated", "high", "very_high"]
            if "anomaly_level" in slot and slot["anomaly_level"] not in valid_levels:
                errors.append(f"Invalid anomaly_level: {slot['anomaly_level']}")

            # Check time range
            hours = [s["hour"] for s in time_slots if "hour" in s]
            if hours:
                if min(hours) != 9:
                    warnings.append(f"First hour is {min(hours)}, expected 9")
                if max(hours) != 14:
                    warnings.append(f"Last hour is {max(hours)}, expected 14")

        # Verify trading session format
        if "trading_session" in data and data["trading_session"] != "09:00-15:00":
            warnings.append(f"Trading session: {data['trading_session']}, expected '09:00-15:00'")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def main():
    """Run all integration tests."""
    print("=" * 80)
    print("VOLUME ANOMALY DETECTION API INTEGRATION TESTS")
    print("=" * 80)
    print()

    results = []

    # Test 1-3: Valid symbols
    print(f"Testing valid symbols: {TEST_SYMBOLS}")
    print("-" * 80)
    for symbol in TEST_SYMBOLS:
        print(f"\nTesting {symbol}...")
        result = check_endpoint(symbol)
        results.append(result)

        print(f"  Status: {result['status_code']}")
        print(f"  Response Time: {result['response_time_ms']:.2f}ms")

        if result["success"]:
            validation = validate_response_structure(result["data"])
            print(f"  Validation: {'PASS' if validation['valid'] else 'FAIL'}")

            if validation["errors"]:
                print(f"  Errors: {validation['errors']}")
            if validation["warnings"]:
                print(f"  Warnings: {validation['warnings']}")

            # Show key metrics
            data = result["data"]
            print(f"  Symbol: {data.get('symbol')}")
            print(f"  Days Analyzed: {data.get('days_analyzed')}")
            print(f"  Time Slots: {len(data.get('time_slots', []))}")
            print(f"  Latest Date: {data.get('latest_date')}")

            # Show anomaly distribution
            if data.get("time_slots"):
                anomaly_counts = {}
                for slot in data["time_slots"]:
                    level = slot.get("anomaly_level", "unknown")
                    anomaly_counts[level] = anomaly_counts.get(level, 0) + 1
                print(f"  Anomaly Distribution: {anomaly_counts}")
        else:
            print(f"  ERROR: {result.get('error')}")

    # Test 4: Invalid symbol (should return 404)
    print(f"\n\nTesting invalid symbol: {INVALID_SYMBOL}")
    print("-" * 80)
    result = check_endpoint(INVALID_SYMBOL)
    results.append(result)

    print(f"  Status: {result['status_code']}")
    print(f"  Response Time: {result['response_time_ms']:.2f}ms")
    print(f"  Expected 404: {'PASS' if result['status_code'] == 404 else 'FAIL'}")
    if result.get("error"):
        print(f"  Error Message: {result['error'].get('detail', 'N/A')}")

    # Test 5: Custom days parameter
    print(f"\n\nTesting custom days parameter (VCB with days=30)")
    print("-" * 80)
    result = check_endpoint("VCB", days=30)
    results.append(result)

    print(f"  Status: {result['status_code']}")
    print(f"  Response Time: {result['response_time_ms']:.2f}ms")
    if result["success"]:
        print(f"  Days Analyzed: {result['data'].get('days_analyzed')}")
        print(f"  Expected 30: {'PASS' if result['data'].get('days_analyzed') == 30 else 'FAIL'}")

    # Summary
    print("\n\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    total_tests = len(results)
    passed_tests = sum(1 for r in results if r["success"])
    failed_tests = total_tests - passed_tests

    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")

    # Performance check
    print("\nPerformance Check (<500ms threshold):")
    for result in results[:3]:  # Only valid symbols
        if result["success"]:
            status = "PASS" if result["response_time_ms"] < 500 else "FAIL"
            print(f"  {result['symbol']}: {result['response_time_ms']:.2f}ms - {status}")

    # Check 404 test
    invalid_test = next((r for r in results if r["symbol"] == INVALID_SYMBOL), None)
    if invalid_test:
        print(f"\n404 Test: {'PASS' if invalid_test['status_code'] == 404 else 'FAIL'}")

    # Validation summary
    validation_failures = []
    for result in results[:3]:  # Only valid symbols
        if result["success"]:
            validation = validate_response_structure(result["data"])
            if not validation["valid"]:
                validation_failures.append((result["symbol"], validation["errors"]))

    if validation_failures:
        print("\nValidation Failures:")
        for symbol, errors in validation_failures:
            print(f"  {symbol}: {errors}")
    else:
        print("\nAll response structures valid: PASS")

    # Exit code
    exit_code = 0 if failed_tests == 0 and not validation_failures else 1

    print("\n" + "=" * 80)
    print(f"Overall Status: {'PASS' if exit_code == 0 else 'FAIL'}")
    print("=" * 80)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
