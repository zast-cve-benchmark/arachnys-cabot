---
name: create-csrf-util
description: Analyze the codebase's CSRF protection and generate a Python utility that fetches CSRF tokens and prepares authenticated requests for PoC scripts.
disable-model-invocation: true
argument-hint: [TARGET_API_BASE]
version: 1.0.0
---

# Create CSRF Utility

Analyze the codebase to understand its CSRF (Cross-Site Request Forgery) protection mechanism,
then create a Python utility module that automatically handles CSRF token fetching and request preparation.

## Configuration

- **TARGET_API_BASE**: `$ARGUMENTS[0]`
- **AUTH_HEADERS**: `$ARGUMENTS[1]`

## Core Method

Implement the following methods:

```python
import os
from typing import Any, Dict, TypedDict


class RequestKwargs(TypedDict, total=False):
    """Optional request parameters for CSRF-protected requests.

    All fields are optional and may be included based on the endpoint's
    CSRF protection strategy.
    """
    headers: Dict[str, str]
    data: Dict[str, str]
    json: Dict[str, str]
    params: Dict[str, str]


# Base URL for the target server, read from environment variable
API_BASE_URL: str = os.environ["TARGET_API_BASE"]


def prepare_request_with_csrf(endpoint: str, auth_headers: str) -> RequestKwargs:
    """Prepare request parameters with CSRF token for a specific API endpoint.

    Args:
        endpoint: The API endpoint path (e.g., "/api/user/update").
        auth_headers: HTTP headers in standard format (newline-separated). Cookie headers remain as strings.

    Returns:
        RequestKwargs: Optional dictionary for use with `requests` library.
            Returns empty dict if no CSRF protection for this endpoint.
    """
    raise NotImplementedError()


def _fetch_csrf_token(endpoint: str, auth_headers: str) -> str:
    """Fetch CSRF token from the service.

    Args:
        endpoint: The API endpoint path requiring CSRF protection.
        auth_headers: HTTP headers for authentication.

    Returns:
        The fetched CSRF token.
    """
    raise NotImplementedError()
```

## Implementation Logic

### `prepare_request_with_csrf`

1. Use regex patterns to determine endpoint's CSRF strategy:
   - Which endpoints need CSRF protection
   - Where to place the token (headers/data/json/params)
   - What field name to use (e.g., 'X-CSRF-Token', '_csrf', 'csrf_token')
2. If CSRF is needed:
   - Extract session info from auth_headers (e.g., Cookie header)
   - Handle empty/missing session gracefully (obtain new session if empty)
   - Call `_fetch_csrf_token(auth_headers)` to get token
   - Add token to the appropriate location based on strategy
3. Update auth_headers with CSRF token if needed
4. Return the complete request parameters

### `_fetch_csrf_token`

- Discover the endpoint that provides CSRF tokens (e.g., /api/csrf, /csrf-token)
- Use global `API_BASE_URL` to construct the full URL
- Parse the response to extract the token (could be in JSON, HTML meta tag, etc.)
- Handle cookies properly (some tokens are tied to session cookies)
- Disable SSL verification for testing purposes

## CSRF Strategy Detection

Agent should analyze the codebase to determine:

1. **Which endpoints need CSRF protection**: Typically state-changing operations (POST, PUT, DELETE, PATCH)

2. **Token placement strategy**: Based on the framework and endpoint type:
   - **headers**: For REST APIs (e.g., `X-CSRF-Token`, `X-XSRF-Token`)
   - **data**: For form submissions (e.g., `_csrf`, `csrf_token`, `_token`)
   - **json**: For JSON APIs (e.g., `_csrf` field in JSON body)
   - **params**: For URL parameters (e.g., `csrf_token` query param)

3. **CSRF token source endpoint**: The endpoint that provides CSRF tokens:
   - May be a single global endpoint (e.g., `/api/csrf`)
   - May vary by target endpoint pattern (e.g., `/api/auth/` for auth endpoints)
   - Could be extracted from HTML pages (meta tags, hidden inputs)

4. **Use regex patterns** to match endpoints to their strategies, for example:
   ```python
   CSRF_STRATEGIES = [
       # Auth endpoints don't need CSRF
       (r'^/api/auth/.*$', None),

       # REST APIs - token in headers
       (r'^/api/.*$', {
           'location': 'headers',
           'field': 'X-CSRF-Token',
           'token_source': '/api/csrf'
       }),

       # Form endpoints - token in data
       (r'^/form/.*$', {
           'location': 'data',
           'field': '_csrf',
           'token_source': '/csrf-token'
       }),
   ]
   ```

## Expected Usage

```python
import os
import sys
import requests

# IMPORTANT: Set environment variable BEFORE importing csrf_util
os.environ['TARGET_API_BASE'] = 'http://localhost:8080'

# Now import after environment variable is set
from zast_utils.csrf_util import prepare_request_with_csrf

# User prepares auth headers
auth_headers = """Authorization: Bearer token123
X-Api-Key: abc123
Cookie: session_id=xyz789"""

# User prepares their own request parameters
req_kwargs = {
    'data': {'name': 'test', 'email': 'test@example.com'}
}

# Get request parameters with CSRF token (e.g., {'headers': {...}, 'data': {'_csrf': 'xxx'}})
csrf_kwargs = prepare_request_with_csrf('/api/user/update', auth_headers)

# Merge CSRF parameters into user's request parameters
# Note: csrf_kwargs may add/overwrite keys like 'headers' or add fields to 'data'
req_kwargs.update(csrf_kwargs)

# Send request with merged parameters
response = requests.post(
    os.environ['TARGET_API_BASE'] + '/api/user/update',
    **req_kwargs
)
```

## Requirements

- **Set TARGET_API_BASE and AUTH_HEADERS environment variables from provided arguments (`$ARGUMENTS[0]`, `$ARGUMENTS[1]`) when running tests**
- Disable SSL verification for all requests (`verify=False`)
- Handle missing session gracefully (obtain new session in this case)
- Cookie should remain as string in headers, not parsed into separate cookies dict
- Save implementation to `.zast/llm-auditor/zast_utils/csrf_util.py`
- Create test script at `.zast/llm-auditor/zast_utils/tests/test_csrf_util.py`:
  - Write standalone test functions (no pytest/unittest)
  - **IMPORTANT**: Set environment variables BEFORE importing csrf_util
    ```python
    import os
    import sys

    # Add parent directory to path for imports
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # Set environment variables BEFORE importing
    os.environ['TARGET_API_BASE'] = 'http://localhost:8080'
    os.environ['AUTH_HEADERS'] = """Authorization: Bearer token123
    X-Api-Key: abc123
    Cookie: session_id=xyz789"""

    # Now safe to import
    import csrf_util

    ... # Write tests
    ```
- Run tests with `python .zast/llm-auditor/zast_utils/tests/test_csrf_util.py`
- Do not hardcode credentials in the implementation

## Testing Checklist

- [ ] Test with endpoint that doesn't require CSRF (should return headers only)
- [ ] Test with endpoint requiring CSRF in headers
- [ ] Test with endpoint requiring CSRF in body
- [ ] Test with empty auth_headers (should obtain new session)
- [ ] Test with auth_headers containing Cookie
- [ ] Test with auth_headers without Cookie
