---
name: email-infrastructure
description: "Email infrastructure setup and management. Covers cold email (Instantly + Migadoo + SES), marketing newsletters (Maillayer + SES), DNS configuration, and credential management. Use for email system setup, domain verification, warmup procedures, or troubleshooting deliverability."
---

# Email Infrastructure

> **TEMPLATE** - Architecture overview for a two-system email stack. Replace example domains, keys, and IDs with your own. Keep your customized copy private once it holds real credentials.

---

## Architecture Overview

Two parallel email systems serving different purposes:

### System A: Cold Email (Outbound Sales)

```
Domains (Hostinger/Netim)
  → Mailboxes on Migadoo (IMAP receiving)
  → Connect to Instantly:
      - Amazon SES SMTP (sending)
      - Migadoo IMAP (receiving)
  → Manage campaigns in Instantly
  → View replies in Instantly Unibox
```

### System B: Marketing & Newsletters

```
Personal Brand Domain (example.com)
  → user@example.com as sender
  → Maillayer (campaign management)
  → Amazon SES (sending infrastructure)
  → Contact lists per product
```

---

## Why Two Systems?

| Purpose             | Tool      | Reason                                                   |
| ------------------- | --------- | -------------------------------------------------------- |
| Cold outreach       | Instantly | Warmup, lead database, CRM, Unibox, lifetime plan        |
| Product newsletters | Maillayer | Clean separation, pristine reputation, transactional API |

**Domain Separation Strategy:**

- Cold email domains may experience reputation fluctuations
- Marketing domain maintains pristine reputation for customers
- Product inboxes remain customer-facing

---

## Credential Separation

| Tool          | Credential Type | Purpose                      |
| ------------- | --------------- | ---------------------------- |
| **Instantly** | SES SMTP        | Cold email sending           |
| **Maillayer** | SES IAM API     | Marketing/newsletter sending |

Both share the same AWS account, SES limits, and verified domains.

---

## Skill Modules

| Module                                                                 | When to Read                                                                         |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **[email-maillayer-contacts-api.md](email-maillayer-contacts-api.md)** | Programmatic contact management, adding subscribers, syncing customers from checkout |

### Conditional Loading Guide

**Managing contacts programmatically?**
→ Read `email-maillayer-contacts-api.md` (API reference + code examples)

**Setting up cold email or Maillayer?**
→ Follow the architecture above: provision Amazon SES, connect your sending tool (Instantly for cold, Maillayer for marketing), verify your domains in DNS, and store credentials in your own gitignored `keys/` file. Keep a private runbook with your specific domains, DNS records, and credentials.

---

## Quick Reference

### Cold Email Stack

| Component               | Service    | Notes                         |
| ----------------------- | ---------- | ----------------------------- |
| Domain registration     | Hostinger  | .com recommended              |
| Email hosting (receive) | Migadoo    | $19/year, unlimited mailboxes |
| Email sending           | Amazon SES | $0.10/1,000 emails            |
| Campaign management     | Instantly  | Lifetime plan                 |

### Marketing Stack

| Component           | Service        | Notes                      |
| ------------------- | -------------- | -------------------------- |
| Campaign management | Maillayer      | One-time $69-99            |
| Deployment          | Coolify on VPS | $12/month                  |
| Email sending       | Amazon SES API | Same account as cold email |
| Reply receiving     | Migadoo        | Same as cold email         |

---

## Key Procedures

| Procedure                 | Location                    | Timeline                 |
| ------------------------- | --------------------------- | ------------------------ |
| Add new cold email domain | your private runbook        | 4-5 weeks (incl. warmup) |
| Set up Maillayer          | Coolify deploy + SES verify | 1-2 days                 |
| Quick domain checklist    | your private runbook        | Reference                |

---

## Cost Summary

| Stack      | Annual Cost                 |
| ---------- | --------------------------- |
| Cold Email | ~$76-136/year               |
| Marketing  | ~$210-225/year (first year) |
| **Total**  | ~$300/year                  |

**Savings vs alternatives:** 70-93% cheaper than Mailchimp, ConvertKit, SparkPost
