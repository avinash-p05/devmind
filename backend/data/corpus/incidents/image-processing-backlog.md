# Image Processing Worker Incident

Incident ID: INC-2026-3041
Service: image-processing
Severity: SEV-2
Date: 2026-10-04

## Summary

After image-processing version 2.6.0 was deployed, background image-processing jobs
started accumulating in the worker queue.

The API remained healthy, but asynchronous image-processing jobs experienced
significant delays.

## Timeline

- 16:00 UTC - version 2.6.0 deployment started.
- 16:05 UTC - deployment completed.
- 16:12 UTC - queue depth began increasing.
- 16:20 UTC - processing latency exceeded the alert threshold.
- 16:31 UTC - workers were inspected.
- 16:38 UTC - worker concurrency configuration was identified.
- 16:45 UTC - concurrency configuration was corrected.
- 16:53 UTC - queue depth returned to normal.

## Impact

- Image-processing jobs were delayed by up to 18 minutes.
- No image data was lost.
- API request latency was unaffected.

## Investigation

The previous worker configuration allowed 32 concurrent jobs per worker.

Version 2.6.0 changed the worker concurrency value to 8.

The deployment therefore reduced processing capacity even though the number of
worker instances remained unchanged.

## Corrective Action

Worker concurrency was restored to 32.

The deployment validation process should compare worker throughput configuration
against expected queue processing capacity before production rollout.