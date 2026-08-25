# Evaluation run eval-5abb2714e5b849e9

- Artifact digest: `e78715254eb08800`
- Complete: `true` (48/48 trials)
- Data-provider calls: `0`
- Reproduce: `make eval-run EVAL_ROUTE=http://127.0.0.1:8317/v1 EVAL_CEILING=5.0`

## Environment identity

```json
{
  "case_contract_digest": "12d8312a8cf00033",
  "code": {
    "dirty": true,
    "git_sha": "d7c40d38034f48a8104a41db6828c9a10f604325"
  },
  "dataset_digest": "85eb3484ddf286b3",
  "dataset_id": "investment-intelligence-v1",
  "graders": {
    "as-of-publication": "1.0.0",
    "claims-conclusion": "2.0.0",
    "entity-scope": "2.0.0",
    "evidence-health-coverage": "1.1.0",
    "figure-value-unit": "1.1.0",
    "policy-action": "1.0.0",
    "refusal-uncertainty": "2.0.0",
    "terminal-state": "1.0.0",
    "tool-settlement": "1.0.0"
  },
  "mode": "multi-trial",
  "model": {
    "batch_model": "gpt-5.6-luna",
    "batch_prices": {
      "cache_write": 0.5,
      "cached_input": 0.05,
      "input": 0.5,
      "output": 1.0
    },
    "pricing_effective_from": "2026-08-01",
    "pricing_version": "2026-08-dev-cliproxy",
    "prompt_cache_control": false,
    "reasoning_history": false,
    "request_timeout_seconds": 120.0,
    "route_base_url": "http://127.0.0.1:8317/v1",
    "route_breaker_enabled": true,
    "session_model": "gpt-5.6-terra",
    "session_prices": {
      "cache_write": 2.5,
      "cached_input": 0.2,
      "input": 2.0,
      "output": 10.0
    },
    "streaming": true
  },
  "policy_version": "2.0.0",
  "prompts": {
    "contract_sha": "777862cda6b5e381f2e25419f6bceacda751565ec5e6263d863cadeb4f54d7be",
    "generation_version": "v1",
    "loop_version": "v2",
    "version": "2.4.0"
  },
  "provider_capabilities": {
    "capabilities": {
      "fundamental": {
        "capability": "fundamental",
        "cover": null,
        "cover_declared": false,
        "cover_executable": false,
        "main": "vnstock",
        "main_executable": true
      },
      "market": {
        "capability": "market",
        "cover": "vnstock",
        "cover_declared": true,
        "cover_executable": true,
        "main": "fiinquant",
        "main_executable": true
      },
      "market_index": {
        "capability": "market_index",
        "cover": null,
        "cover_declared": false,
        "cover_executable": false,
        "main": "fiinquant",
        "main_executable": true
      },
      "reference": {
        "capability": "reference",
        "cover": null,
        "cover_declared": false,
        "cover_executable": false,
        "main": "vnstock",
        "main_executable": true
      },
      "valuation": {
        "capability": "valuation",
        "cover": "vnstock",
        "cover_declared": true,
        "cover_executable": false,
        "main": "fiinquant",
        "main_executable": true
      }
    },
    "digest": "b71799769f39742a",
    "inventory": {
      "fiinquant": {
        "market": [
          "FiinQuantMarketProvider"
        ],
        "market_index": [
          "FiinQuantMarketIndexProvider"
        ],
        "valuation": [
          "FiinQuantValuationProvider"
        ]
      },
      "vnstock": {
        "corporate_action": [
          "VnstockCorporateActionProvider"
        ],
        "fundamental": [
          "VnstockFundamentalProvider"
        ],
        "market": [
          "VnstockMarketHistoryProvider"
        ],
        "reference": [
          "VnstockReferenceProvider",
          "VnstockListingRosterProvider"
        ]
      }
    },
    "market_schema_version": 2
  },
  "rubric_version": "investment-intelligence-rubric@1",
  "run_id": "eval-5abb2714e5b849e9",
  "schema": "eval.run-manifest@1",
  "tools": {
    "digest": "ee10c69a9f909d30",
    "names": [
      "list_fields",
      "get_field"
    ],
    "unavailable": []
  },
  "trials": 3
}
```

## Hard results

Hard failures: `0`

## Failed samples

None.

## Usage and latency

```json
{
  "candidate_cost_known_trials": 48,
  "candidate_cost_usd": 0.4975967,
  "candidate_tokens": 647973,
  "candidate_usage_known": true,
  "latency_ms": {
    "mean": 20356.229,
    "total": 977099
  },
  "rubric_cost_usd": 0.133352,
  "rubric_tokens": 254467,
  "rubric_usage_known": true
}
```
