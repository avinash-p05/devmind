# Payment Service Log Extract

```text
2026-10-05T14:03:11Z ERROR service=payment-service request_id=req-1842
QueuePool limit reached, connection checkout timed out

2026-10-05T14:03:12Z WARN service=payment-service route=/checkout
request exceeded timeout=3000ms

2026-10-05T14:03:15Z ERROR service=payment-service deployment=2026.10.05.1
upstream request failed with status=503
```

The log extract correlates the checkout timeout with database pool exhaustion
immediately after deployment `2026.10.05.1`.
