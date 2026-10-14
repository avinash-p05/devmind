# Production Release Notes (September - October 2026)

- 2026-09-22 payment-service v2.14.0 - adds synchronous fraud-check before recording
  a payment. Rolled back to v2.13.4 (INC-2026-1187).
- 2026-09-28 checkout-service v8.2.1 - new stock reservation flow against inventory-service.
- 2026-10-01 inventory-sync v3.8.0 - warehouse API client timeout lowered from 30 s to 5 s.
- 2026-10-02 search-service v7.4.0 - tenant and date filtering on search queries.
- 2026-10-03 notification-service v5.1.0 - worker batch size changed from 100 to 25.
- 2026-10-04 image-processing v2.6.0 - worker concurrency changed from 32 to 8.
- 2026-10-05 auth-service v4.3.0 - new JWT signing certificate. Rolled back to v4.2.7
  (INC-2026-2017).
