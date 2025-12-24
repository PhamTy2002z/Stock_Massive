#!/usr/bin/env python3
"""Test script for validating Supabase migration endpoints"""

import requests
import time
import json
from typing import Dict, List, Tuple

BASE_URL = "http://localhost:8000"

def test_endpoint(url: str, name: str) -> Dict:
    """Test a single endpoint and return results"""
    try:
        start_time = time.time()
        response = requests.get(url, timeout=10)
        elapsed = time.time() - start_time

        return {
            "name": name,
            "url": url,
            "status": response.status_code,
            "time": f"{elapsed:.3f}s",
            "success": response.status_code == 200,
            "data_sample": str(response.json())[:100] if response.status_code == 200 else None,
            "error": None
        }
    except Exception as e:
        return {
            "name": name,
            "url": url,
            "status": "ERROR",
            "time": "N/A",
            "success": False,
            "data_sample": None,
            "error": str(e)
        }

def main():
    """Run all endpoint tests"""

    endpoints = [
        # Health checks
        (f"{BASE_URL}/health", "Health Check"),
        (f"{BASE_URL}/docs", "Swagger Docs"),

        # Market Data
        (f"{BASE_URL}/api/v1/stocks/market-indices", "Market Indices"),
        (f"{BASE_URL}/api/v1/stocks/vn30-overview", "VN30 Overview"),
        (f"{BASE_URL}/api/v1/stocks/sector-performance", "Sector Performance"),

        # Stock Detail
        (f"{BASE_URL}/api/v1/stocks/VCB/detail", "Stock Detail (VCB)"),
        (f"{BASE_URL}/api/v1/stocks/VCB/history", "Stock History (VCB)"),

        # Analytics - CRITICAL (Database-dependent)
        (f"{BASE_URL}/api/v1/stocks/analytics/financial-statements?limit=10", "Financial Statements"),
        (f"{BASE_URL}/api/v1/stocks/analytics/volume-spikes", "Volume Spikes"),

        # Financials
        (f"{BASE_URL}/api/v1/stocks/VCB/financials/ratios", "Financial Ratios (VCB)"),
    ]

    results = []
    print("=" * 80)
    print("SUPABASE MIGRATION VALIDATION TEST")
    print("=" * 80)
    print()

    for url, name in endpoints:
        print(f"Testing: {name}...", end=" ")
        result = test_endpoint(url, name)
        results.append(result)

        if result["success"]:
            print(f"✓ OK ({result['time']})")
        else:
            error_msg = result.get('error') or f"Status: {result['status']}"
            print(f"✗ FAILED - {error_msg}")

    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()

    # Print table
    print(f"{'Endpoint':<30} {'Status':<10} {'Time':<10} {'Result':<10}")
    print("-" * 80)
    for r in results:
        status_str = str(r['status'])
        result_str = "✓ PASS" if r['success'] else "✗ FAIL"
        print(f"{r['name']:<30} {status_str:<10} {r['time']:<10} {result_str:<10}")

    print()
    print(f"Total: {len(results)} | Passed: {sum(1 for r in results if r['success'])} | Failed: {sum(1 for r in results if not r['success'])}")

    # Save results to JSON
    with open('/Users/typham/Documents/GitHub/Stock_Massive/test_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print()
    print("Results saved to: test_results.json")

    # Return exit code
    return 0 if all(r['success'] for r in results) else 1

if __name__ == "__main__":
    exit(main())
