# TODO
An active list of found requirements, out-of-scope work, and potential issues for future triaging

## Examples
### Incomplete
[TODO-XXX is findable elsewhere in the code until crossed off]
```
    [ ] TODO-XXX: Handle case where foo returns null
```

### Complete
[TODO-XXX was removed from the code when completed. The TODO here remains]
```
    [x] TODO-YYY: Bar returns foo when baz is false
```

## Open TODOs
    [ ] TODO-002: FAF API requires OAuth authentication (403 Forbidden). Need to implement OAuth flow or find alternative map discovery method.
    [ ] TODO-003: Create FA version 60 test fixture. Only SC version 56 fixture exists; FA v60 maps have additional fields but no test coverage.
    [ ] TODO-004: Add thread safety tests. FAFApiClient._last_request_time not thread-safe; bulk downloader concurrent writes not stress-tested.
    [ ] TODO-005: Parser stratum mask extraction. Masks stored after decals/props sections in SCMap file; requires extended parsing to extract.
    [ ] TODO-006: Test terrain type tie-breaking. When two terrain types have identical scores, behavior is non-deterministic (dict iteration order).
    [ ] TODO-007: Add URL/path edge case tests. Unicode characters, very long paths, special characters in map names not tested.
    [ ] TODO-008: Test checkpoint/failures file corruption recovery. Partial writes and malformed JSON handling needs validation.
    [ ] TODO-009: Add large file stress tests. Multi-GB zips, 1000+ concurrent downloads, memory efficiency not validated.
    [ ] TODO-010: Test multiple .scmap files in zip. Code picks first silently; behavior should be documented and tested.
    [ ] TODO-011: API response edge cases. Malformed JSON, missing attributes, null values in optional fields not tested.


## Completed TODOs
    [x] TODO-001: Register pytest 'integration' marker in pyproject.toml to eliminate warning
