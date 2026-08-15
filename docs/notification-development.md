# Notification provider development

Notification channels implement `dealfinder.notifications.base.NotificationProvider` and its
asynchronous `notify(events)` method. `DealEvent` is marketplace-neutral and currently represents
new strong deals and material price drops.

Keep delivery credentials in environment variables or a secret manager. A channel must isolate
transport/authentication, apply its own bounded retry and rate-limit policy, avoid logging
secrets, and test against mocked transports. Register built-ins through
`register_notification_provider`; external channel entry-point discovery can be added without
changing event detection because the contracts are already separate.

The built-in console provider emits table-like text or JSON and is the default for `watch`. It is
designed for Kubernetes logs, shell pipelines, and later fan-out controllers—not as a substitute
for reliable external delivery acknowledgements.
