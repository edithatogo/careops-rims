# RIMS user-based access scope

## Decision

The current implementation is scoped to the authenticated user’s existing
Power Platform and Microsoft 365 access. Development and acceptance use
isolated personal DEV SharePoint lists, user-owned/manual Power Automate runs,
and the existing user-accessible Power BI report/model route.

The current deliverable does not require organisation-wide list ownership,
sharing changes, cross-user subscriptions, mail/calendar delivery, unattended
recurrence, production rebinding, or new licences/capacity. Those capabilities
are future extensions and must not be silently introduced as part of the
current tracks.

## Acceptance boundary

- A successful native gate must identify the current user, isolated target,
  manual trigger/run, and readback evidence.
- Local code may model user keys, categories, preferences, institutional dates
  and delivery ledgers, but it must not imply that another user can access or
  receive them.
- A user-scoped subscription means a preference for the current user only;
  shared watchlists and notifications remain out of scope.
- Flows remain Off unless a manual test is explicitly required and can be
  restored Off after readback.
- Organisation-wide binding, sharing, schedule activation and delivery are
  separate future tracks, not prerequisites for declaring the user-scoped
  local/native tranche complete.

## Conductor impact

Active plans should use “current-user isolated target” and “manual user-owned
operation” for their acceptance language. Historical receipts may mention
organisation-wide targets because they describe earlier scope; they do not
override this decision.
