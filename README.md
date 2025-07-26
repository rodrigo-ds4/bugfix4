# YamlLint Configuration Bug Fix

## Problem Solved
Fixed configuration parsing bug where empty or invalid configurations caused unexpected errors instead of graceful handling.

## Solution
Added validation for empty/whitespace-only configurations in the `parse()` method to provide clear error messages.

## Test Status
✅ `test_run_with_empty_config` now passes

## Changes Made
- `yamllint/config.py`: Added empty configuration validation
- Clear error message: "invalid config: not a dict"
- Graceful handling instead of file processing errors 