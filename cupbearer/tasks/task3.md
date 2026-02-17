# Task 3: Twilio WhatsApp Transport

## Objective
Provide reliable inbound/outbound messaging through Twilio WhatsApp as the MVP channel.

## Scope
- Implement Twilio WhatsApp inbound webhook handling.
- Verify Twilio signatures and normalize inbound payloads.
- Persist inbound events with idempotency keys.
- Implement outbound WhatsApp sender with retriable error handling.
- Add transport-level observability (provider IDs, delivery status hooks if available).

## Deliverables
- WhatsApp webhook endpoint.
- Outbound WhatsApp client module.
- Idempotency middleware/utilities for duplicate deliveries.

## Acceptance Criteria
- Inbound WhatsApp messages are persisted as immutable events.
- Outbound replies are sent successfully in sandbox/dev environment.
- Duplicate webhook delivery does not produce duplicate downstream side effects.
