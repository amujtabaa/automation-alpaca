# Analytics Tracking Setup

## Overview

Expert guidance for implementing and optimizing analytics tracking and measurement. Covers tracking plans, event naming conventions, GA4 implementation, Google Tag Manager setup, UTM strategy, and debugging/validation. Focus on tracking that drives decisions, not just data collection.

---

## When to Use

**Trigger phrases:**
- "set up tracking", "analytics tracking", "event tracking"
- "GA4", "Google Analytics", "Google Tag Manager", "GTM"
- "conversion tracking", "UTM parameters"
- "tracking plan", "analytics implementation"
- "what to track", "event naming"

**Use cases:**
- Setting up analytics from scratch
- Creating a tracking plan document
- Implementing GA4 events
- Configuring Google Tag Manager
- Establishing UTM conventions
- Debugging tracking issues
- Auditing existing implementation

---

## Inputs Required

### Business Context
- What decisions will this data inform?
- What are the key conversion actions?
- What questions need answering?

### Current State
- What tracking exists?
- What tools are in use (GA4, Mixpanel, Amplitude, etc.)?
- What's working/not working?

### Technical Context
- What's the tech stack?
- Who will implement and maintain?
- Any privacy/compliance requirements?

---

## Core Principles

### 1. Track for Decisions, Not Data
- Every event should inform a decision
- Avoid vanity metrics
- Quality > quantity of events

### 2. Start with the Questions
- What do you need to know?
- What actions will you take based on this data?
- Work backwards to what you need to track

### 3. Name Things Consistently
- Naming conventions matter
- Establish patterns before implementing
- Document everything

### 4. Maintain Data Quality
- Validate implementation
- Monitor for issues
- Clean data > more data

---

## Tracking Plan Framework

### Structure
```
Event Name | Event Category | Properties | Trigger | Notes
---------- | ------------- | ---------- | ------- | -----
```

### Event Types

**Pageviews**
- Automatic in most tools
- Enhanced with page metadata

**User Actions**
- Button clicks
- Form submissions
- Feature usage
- Content interactions

**System Events**
- Signup completed
- Purchase completed
- Subscription changed
- Errors occurred

**Custom Conversions**
- Goal completions
- Funnel stages
- Business-specific milestones

---

## Event Naming Conventions

### Format Options

**Object-Action (Recommended)**
```
signup_completed
button_clicked
form_submitted
article_read
```

**Action-Object**
```
click_button
submit_form
complete_signup
```

**Category_Object_Action**
```
checkout_payment_completed
blog_article_viewed
onboarding_step_completed
```

### Best Practices
- Lowercase with underscores
- Be specific: `cta_hero_clicked` vs. `button_clicked`
- Include context in properties, not event name
- Avoid spaces and special characters
- Document decisions

---

## Essential Events to Track

### Marketing Site

**Navigation**
| Event | Description | Properties |
|-------|-------------|------------|
| page_view | Enhanced pageview | page_title, content_group |
| outbound_link_clicked | External link clicks | destination_url |
| scroll_depth | Page scroll milestones | percentage (25, 50, 75, 100) |

**Engagement**
| Event | Description | Properties |
|-------|-------------|------------|
| cta_clicked | CTA button clicks | button_text, location |
| video_played | Video engagement | video_id, duration |
| form_started | Form interaction begins | form_type |
| form_submitted | Form completion | form_type, fields_count |
| resource_downloaded | Content downloads | resource_name, format |

**Conversion**
| Event | Description | Properties |
|-------|-------------|------------|
| signup_started | Signup initiation | source, page |
| signup_completed | Signup completion | method, plan |
| demo_requested | Demo form submission | company_size, industry |
| contact_submitted | Contact form completion | topic, urgency |

### Product/App

**Onboarding**
| Event | Description | Properties |
|-------|-------------|------------|
| signup_completed | Account created | method, plan |
| onboarding_step_completed | Progress through steps | step_number, step_name |
| onboarding_completed | Full onboarding done | total_time, steps_completed |
| first_key_action_completed | Activation milestone | action_type |

**Core Usage**
| Event | Description | Properties |
|-------|-------------|------------|
| feature_used | Feature interaction | feature_name, context |
| action_completed | Key user actions | action_type, result |
| session_started | Session begins | entry_page |
| session_ended | Session closes | duration, pages_viewed |

**Monetization**
| Event | Description | Properties |
|-------|-------------|------------|
| trial_started | Trial activation | plan, duration |
| pricing_viewed | Pricing page view | current_plan |
| checkout_started | Checkout initiation | plan, value |
| purchase_completed | Successful purchase | plan, value, currency |
| subscription_cancelled | Churn event | plan, tenure, reason |

### E-commerce

**Browsing**
| Event | Description | Properties |
|-------|-------------|------------|
| product_viewed | PDP views | product_id, category, price |
| product_list_viewed | Category/collection views | list_name, products |
| product_searched | Search queries | query, results_count |

**Cart**
| Event | Description | Properties |
|-------|-------------|------------|
| product_added_to_cart | Add to cart | product_id, quantity, value |
| product_removed_from_cart | Remove from cart | product_id, quantity |
| cart_viewed | Cart page view | total_value, items_count |

**Checkout**
| Event | Description | Properties |
|-------|-------------|------------|
| checkout_started | Checkout initiation | value, items_count |
| checkout_step_completed | Step progression | step_number, step_name |
| payment_info_entered | Payment details added | payment_method |
| purchase_completed | Order completion | order_id, value, products |

---

## Event Properties (Parameters)

### Standard Properties

**Page/Screen**
- page_title
- page_location (URL)
- page_referrer
- content_group

**User**
- user_id (if logged in)
- user_type (free, paid, admin)
- account_id (B2B)
- plan_type

**Campaign**
- source
- medium
- campaign
- content
- term

**Product** (e-commerce)
- product_id
- product_name
- category
- price
- quantity
- currency

**Timing**
- timestamp
- session_duration
- time_on_page

### Best Practices
- Use consistent property names
- Include relevant context
- Don't duplicate GA4 automatic properties
- Avoid PII in properties
- Document expected values

---

## GA4 Implementation

### Configuration

**Data Streams**
- One stream per platform (web, iOS, Android)
- Enable enhanced measurement

**Enhanced Measurement Events** (automatic)
- page_view
- scroll (90% depth)
- outbound_click
- site_search
- video_engagement
- file_download

**Recommended Events**
- Use Google's predefined events when possible
- Correct naming for enhanced reporting
- Reference: https://support.google.com/analytics/answer/9267735

### Custom Events (GA4)

**Using gtag.js:**
```javascript
gtag('event', 'signup_completed', {
  'method': 'email',
  'plan': 'free'
});
```

**Using dataLayer (for GTM):**
```javascript
dataLayer.push({
  'event': 'signup_completed',
  'method': 'email',
  'plan': 'free'
});
```

### Conversions Setup

1. Collect event in GA4
2. Mark as conversion in Admin > Events
3. Set conversion counting (once per session or every time)
4. Import to Google Ads if needed

### Custom Dimensions and Metrics

**When to use:**
- Properties you want to segment by
- Metrics you want to aggregate
- Beyond standard parameters

**Setup:**
1. Create in Admin > Custom definitions
2. Scope: Event, User, or Item
3. Parameter name must match

---

## Google Tag Manager Implementation

### Container Structure

**Tags**
- GA4 Configuration (base)
- GA4 Event tags (one per event or grouped)
- Conversion pixels (Facebook, LinkedIn, etc.)

**Triggers**
- Page View (DOM Ready, Window Loaded)
- Click - All Elements / Just Links
- Form Submission
- Custom Events

**Variables**
- Built-in: Click Text, Click URL, Page Path, etc.
- Data Layer variables
- JavaScript variables
- Lookup tables

### Best Practices
- Use folders to organize
- Consistent naming (Tag_Type_Description)
- Version notes on every publish
- Preview mode for testing
- Workspaces for team collaboration

### Data Layer Pattern

**Push custom event:**
```javascript
dataLayer.push({
  'event': 'form_submitted',
  'form_name': 'contact',
  'form_location': 'footer'
});
```

**Set user properties:**
```javascript
dataLayer.push({
  'user_id': '12345',
  'user_type': 'premium'
});
```

**E-commerce event:**
```javascript
dataLayer.push({
  'event': 'purchase',
  'ecommerce': {
    'transaction_id': 'T12345',
    'value': 99.99,
    'currency': 'USD',
    'items': [{
      'item_id': 'SKU123',
      'item_name': 'Product Name',
      'price': 99.99
    }]
  }
});
```

---

## UTM Parameter Strategy

### Standard Parameters

| Parameter | Purpose | Examples |
|-----------|---------|----------|
| utm_source | Where traffic comes from | google, facebook, newsletter |
| utm_medium | Marketing medium | cpc, email, social, referral |
| utm_campaign | Campaign name | spring_sale, product_launch |
| utm_content | Differentiate versions | hero_cta, sidebar_link |
| utm_term | Paid search keywords | running+shoes |

### Naming Conventions

**Rules:**
- Lowercase everything (google, not Google)
- Use underscores or hyphens consistently
- Be specific but concise
- Document all conventions

**Examples:**
```
Good: blog_footer_cta
Bad: cta1

Good: 2024_q1_promo
Bad: promo

Good: product-launch-email-1
Bad: email
```

### UTM Documentation

Track all UTMs in a spreadsheet:

| Campaign | Source | Medium | Content | Full URL | Owner | Date |
|----------|--------|--------|---------|----------|-------|------|
| Q1 Launch | linkedin | cpc | banner_a | [url] | Marketing | Jan 2024 |

---

## Debugging and Validation

### Testing Tools

**GA4 DebugView**
- Real-time event monitoring
- Enable with `?debug_mode=true`
- Or via Chrome extension

**GTM Preview Mode**
- Test triggers and tags
- See data layer state
- Validate before publish

**Browser Extensions**
- GA Debugger
- Tag Assistant
- dataLayer Inspector

### Validation Checklist

- [ ] Events firing on correct triggers
- [ ] Property values populating correctly
- [ ] No duplicate events
- [ ] Works across browsers
- [ ] Works on mobile
- [ ] Conversions recorded correctly
- [ ] User ID passing when logged in
- [ ] No PII leaking

### Common Issues

**Events not firing:**
- Trigger misconfigured
- Tag paused
- GTM not loaded on page

**Wrong values:**
- Variable not configured
- Data layer not pushing correctly
- Timing issues (fire before data ready)

**Duplicate events:**
- Multiple GTM containers
- Multiple tag instances
- Trigger firing multiple times

---

## Privacy and Compliance

### Considerations
- Cookie consent required in EU/UK/CA
- No PII in analytics properties
- Data retention settings
- User deletion capabilities
- Cross-device tracking consent

### Implementation

**Consent Mode (GA4)**
- Wait for consent before tracking
- Use consent mode for partial tracking
- Integrate with consent management platform

**Data Minimization**
- Only collect what you need
- IP anonymization
- No PII in custom dimensions

---

## Output Templates

### Tracking Plan Document

```markdown
# [Site/Product] Tracking Plan

## Overview
- Tools: GA4, GTM
- Last updated: [Date]
- Owner: [Name]

## Events

### Marketing Events

| Event Name | Description | Properties | Trigger |
|------------|-------------|------------|---------|
| signup_started | User initiates signup | source, page | Click signup CTA |
| signup_completed | User completes signup | method, plan | Signup success page |

### Product Events
[Similar table]

## Custom Dimensions

| Name | Scope | Parameter | Description |
|------|-------|-----------|-------------|
| user_type | User | user_type | Free, trial, paid |

## Conversions

| Conversion | Event | Counting | Google Ads |
|------------|-------|----------|------------|
| Signup | signup_completed | Once per session | Yes |

## UTM Convention
[Guidelines]
```

### Implementation Spec
- Ready-to-use code snippets
- GTM tag configurations
- Data layer specifications

### Testing Checklist
- Specific validation steps per event
- Expected values and behaviors
- Edge cases to verify

---

## Quality Checklist

Before going live:
- [ ] Tracking plan documented and approved
- [ ] Event naming follows convention
- [ ] All key conversion events defined
- [ ] Properties capture necessary context
- [ ] UTM convention documented
- [ ] Consent handling implemented
- [ ] Testing completed across devices
- [ ] Team trained on using data

---

## Related Skills

- **cro/ab-testing**: Experiment tracking and analysis
- **seo/workflow-a-audit**: Organic traffic analysis
- **cro/page-cro**: Conversion optimization (uses this data)
- **paid/skill-overview.md**: Paid campaign tracking
- **growth-loops/referral-program**: Referral attribution tracking
