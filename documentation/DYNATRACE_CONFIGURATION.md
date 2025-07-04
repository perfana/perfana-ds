# Dynatrace Configuration

This document describes the required environment variables and token permissions for integrating with Dynatrace.

## Environment Variables

### DYNATRACE_URL
**Required**: Yes (when using Dynatrace integration)  
**Type**: String  
**Description**: The base URL of your Dynatrace environment  
**Format**: `https://{your-environment-id}.live.dynatrace.com`

**Example**:
```bash
DYNATRACE_URL=https://abc12345.live.dynatrace.com
```

**Notes**:
- The URL should NOT include trailing slashes
- The system will automatically append the appropriate API endpoints

### DYNATRACE_PLATFORM_TOKEN
**Required**: Yes (for DQL queries)  
**Type**: String  
**Description**: Platform token for accessing Dynatrace Grail platform APIs  
**Used for**: DQL (Dynatrace Query Language) queries via `/platform/storage/query/v1/query:execute`

**Example**:
```bash
DYNATRACE_PLATFORM_TOKEN=dt0s16.ABC123...XYZ789
```

### DYNATRACE_API_TOKEN
**Required**: Optional (fallback for legacy APIs)  
**Type**: String  
**Description**: Classic API token for accessing traditional Dynatrace APIs  
**Used for**: Legacy metric queries via `/api/v2/metrics/query` (currently not used in main pipeline)

**Example**:
```bash
DYNATRACE_API_TOKEN=dt0c01.ABC123...XYZ789
```

## Token Types and Permissions

### Platform Token (DYNATRACE_PLATFORM_TOKEN)

**Token Type**: Platform Token  
**Format**: `dt0s16.{token-id}.{secret}`  
**Authentication**: Bearer token authentication  
**Scope**: Grail platform access

#### Required Permissions:
- **`storage:query:read`** - Execute DQL queries on Grail data
- **`storage:buckets:read`** - Access data buckets (if using custom buckets)

#### Token Creation:
1. Go to Dynatrace → **Settings** → **Access tokens** → **Generate new token**
2. Select **Platform** as token type
3. Add required scopes:
   - `storage:query:read`
   - `storage:buckets:read` (if needed)
4. Set appropriate expiration date
5. Generate and copy the token

### API Token (DYNATRACE_API_TOKEN) - Legacy

**Token Type**: API Token  
**Format**: `dt0c01.{token-id}.{secret}`  
**Authentication**: Api-Token header authentication  
**Scope**: Classic Dynatrace APIs

#### Required Permissions:
- **`metrics.read`** - Read metrics via metrics API
- **`entities.read`** - Read entity information (if needed)

## Usage in Pipeline

### DQL Query Flow
1. **Collection**: Queries stored in `dynatraceDql` MongoDB collection
2. **Processing**: DQL queries are identified by containing `timeseries` keyword or `|` character
3. **Authentication**: Uses `DYNATRACE_PLATFORM_TOKEN` with Bearer authentication
4. **Endpoints**:
   - Execute: `{DYNATRACE_URL}/platform/storage/query/v1/query:execute`
   - Poll: `{DYNATRACE_URL}/platform/storage/query/v1/query:poll`

### Authentication Logic
```python
# DQL queries (timeseries, aggregations)
if 'timeseries' in query.lower() or '|' in query:
    headers = {"Authorization": f"Bearer {DYNATRACE_PLATFORM_TOKEN}"}
    url = f"{DYNATRACE_URL}/platform/storage/query/v1/query:execute"

# Legacy metric queries (currently not used)
else:
    headers = {"Authorization": f"Api-Token {DYNATRACE_API_TOKEN}"}
    url = f"{DYNATRACE_URL}/api/v2/metrics/query"
```

## Security Best Practices

### Token Management
- **Store securely**: Use environment variables or secret management systems
- **Rotate regularly**: Set reasonable expiration dates and rotate tokens
- **Principle of least privilege**: Only grant required permissions
- **Monitor usage**: Track token usage in Dynatrace audit logs

### Environment Security
- Never commit tokens to version control
- Use different tokens for different environments (dev/staging/prod)
- Implement token validation in deployment pipelines
- Monitor for unauthorized access attempts

## Troubleshooting

### Common Issues

#### 401 Unauthorized
- **Cause**: Invalid or expired token
- **Solution**: 
  1. Verify token format and validity
  2. Check token permissions in Dynatrace
  3. Ensure correct authentication method (Bearer vs Api-Token)

#### 400 Bad Request on DQL
- **Cause**: Invalid DQL syntax or missing permissions
- **Solution**:
  1. Validate DQL syntax in Dynatrace notebooks
  2. Verify `storage:query:read` permission
  3. Check data availability for query timeframe

#### Missing DYNATRACE_PLATFORM_TOKEN
- **Cause**: Environment variable not set
- **Solution**: Set the `DYNATRACE_PLATFORM_TOKEN` environment variable

### Token Validation
```bash
# Test platform token
curl -H "Authorization: Bearer $DYNATRACE_PLATFORM_TOKEN" \
     "$DYNATRACE_URL/platform/storage/query/v1/query:execute" \
     -d '{"query": "fetch dt.system.host | limit 1"}'

# Test API token  
curl -H "Authorization: Api-Token $DYNATRACE_API_TOKEN" \
     "$DYNATRACE_URL/api/v2/metrics"
```

## Integration Points

### Pipeline Integration
The Dynatrace integration is automatically included in:
- `/data/analyzeTest/{testRunId}` - Full test analysis
- `/data/reevaluate/batch` - Batch reevaluation  
- `/data/refresh/batch` - Batch refresh
- `/data/dynatrace/{testRunId}` - Direct Dynatrace processing

### Data Flow
1. **Input**: DQL queries from `dynatraceDql` collection
2. **Processing**: Execute queries against Dynatrace Grail platform
3. **Output**: 
   - `dsPanel` documents (dashboard panels)
   - `dsMetric` documents (individual metrics)
   - `dsMetricStatistics` documents (statistical analysis)

### Filtering
- **Application/Environment**: Only processes queries matching TestRun application and testEnvironment
- **Metric Patterns**: Optional regex filtering via `matchMetricPattern` in collection documents
- **Time Range**: Automatic replacement with TestRun start/end times

## Monitoring

### Key Metrics to Monitor
- Token usage and rate limits
- Query execution times
- Authentication failures
- Data availability and freshness

### Logging
The pipeline provides detailed logging for:
- Token authentication attempts
- Query execution and polling
- Data processing and filtering
- Error conditions and retries