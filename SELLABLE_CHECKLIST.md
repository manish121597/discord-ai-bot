# Sellable Readiness Checklist

Use this before calling the current build ready for a private client rollout.

## Deployment

- Bot service deploys from a clean repo checkout
- Dashboard API deploys with strict env validation
- Frontend deploys with the correct API base URL
- `DASHBOARD_ALLOWED_ORIGINS` is explicit and not `*`
- Bot syncs to the correct dashboard API URL

## Bot behavior

- Giveaway flow works for Discord wins
- Giveaway flow works for Twitter/X wins
- Giveaway flow works for Kick wins
- Incomplete proof triggers only missing-item prompts
- Wrong or unclear proof does not auto-escalate
- Escalated tickets do not trigger noisy AI follow-up replies
- Post-escalation messages still sync to the dashboard

## Dashboard behavior

- New ticket appears in realtime
- New message appears in realtime
- Ticket detail shows latest attachments
- Escalation summary shows proof verdict
- Browser notification opt-in works
- Admin login works with configured credentials only

## Operations

- `/reloadrules` works
- `/rulesstatus` works
- `/showrules` works
- Staff can claim, pause, resume, and close tickets
- Required env vars are documented
- Known limitations are documented

## Minimum release decision

The build is ready for controlled private use when:

- all checks above pass in staging
- all checks above pass once in a live-like server
- no open blocker remains in bot flow, sync flow, or auth/deployment setup
