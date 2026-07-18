---
name: email-templates
description: "Use this skill when creating transactional or marketing emails. Provides the design system, component patterns, and React Email templates for code-generated emails, plus guidance for composing marketing campaign HTML."
---

## Two email channels

| Channel                                                 | Pipeline                                                                                                              | Use for                                                                                       |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| **Code-generated** (transactional, in-app, lifecycle)   | React Email JSX components compiled to HTML, sent via Maillayer's transactional API or another transactional provider | Order receipts, password reset, post-purchase onboarding, drip sequences with personalization |
| **Marketing campaigns** (newsletters, launches, promos) | Raw HTML composed in the Maillayer dashboard, sent to a brand's contact list                                          | Launch announcements, version updates, discount pushes, build-in-public newsletters           |

The design system below is the source of truth for **code-generated** emails (React Email + Tailwind). **Marketing campaigns** are often authored directly in the Maillayer dashboard's HTML editor and do not all need to follow this design system, but keeping an archive of your actual sends (with engagement data: opens, clicks, unsubscribes) is the fastest way to learn which subject lines, layouts, and CTAs perform.

When authoring a new campaign:

- Review your own archive of past sends first to see what subject lines, layouts, and CTAs have shipped and how they performed.
- For consistency, lift the design tokens (zinc palette, Inter/DM Sans, 16px radius main card) from this skill even when composing in the dashboard.
- For one-off transactional emails, build a React Email component using the patterns below.

---

## Tech Stack (code-generated emails)

**Framework**: React Email (`@react-email/components`)
**Styling**: Tailwind CSS (via `<Tailwind>` wrapper) + inline styles for email client compatibility
**Location**: `apps/web/src/emails/`

React Email compiles to HTML tables for maximum email client compatibility while letting you write in JSX with Tailwind classes.

---

## Design System

### Color Palette (Zinc-based)

| Purpose                    | Color     | Hex       |
| -------------------------- | --------- | --------- |
| Headlines, strong text     | zinc-900  | `#18181b` |
| Body text                  | zinc-600  | `#52525b` |
| Muted/secondary text       | zinc-500  | `#71717a` |
| Lighter muted              | zinc-400  | `#a1a1aa` |
| Card backgrounds           | zinc-50   | `#fafafa` |
| Borders                    | zinc-200  | `#e4e4e7` |
| Dark card background       | zinc-900  | `#18181b` |
| Dark card muted            | zinc-800  | `#27272a` |
| Accent (urgency/highlight) | amber-400 | `#fbbf24` |
| White text on dark         | white     | `#ffffff` |

### Typography

| Element        | Font    | Size | Weight         |
| -------------- | ------- | ---- | -------------- |
| Headlines      | DM Sans | 24px | 600            |
| Body           | Inter   | 16px | 400            |
| Strong in body | Inter   | 16px | 500-600        |
| Small/muted    | Inter   | 14px | 400            |
| Labels/badges  | Inter   | 12px | 600, uppercase |
| Large numbers  | DM Sans | 32px | 600            |

**Font stack**: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif`

### Spacing

- Main card padding: 40px
- Section spacing: 24px margin-bottom
- Paragraph spacing: 20px margin-bottom
- Feature card padding: 20px
- Button padding: 14px 28px

### Border Radius

- Main card: 16px
- Inner cards/badges: 12px
- Buttons: 10px
- Code/tags: 6px
- Icon containers: 10px

---

## Layout Structure

```
White background (#ffffff)
  |
  +-- Centered container (max-width: 640px, padding: 48px 20px)
       |
       +-- Main Card (white bg, 1px border #e4e4e7, border-radius: 16px, shadow)
            |
            +-- Content area (padding: 40px)
                 |
                 +-- Greeting
                 +-- Body paragraphs
                 +-- [Optional] Feature cards or promo badge
                 +-- CTA Button (centered)
                 +-- Sign-off (name)
```

---

## Component Patterns

### Main Card Container

```tsx
<Section
  style={{
    maxWidth: "640px",
    backgroundColor: "#ffffff",
    borderRadius: "16px",
    border: "1px solid #e4e4e7",
    overflow: "hidden",
    boxShadow: "0 1px 3px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.05)",
  }}
>
  <Section style={{ padding: "40px" }}>{/* Content */}</Section>
</Section>
```

### Body Paragraph

```tsx
<Text
  style={{
    margin: "0 0 20px 0",
    color: "#52525b",
    fontSize: "16px",
    lineHeight: "1.6",
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    fontWeight: 400,
  }}
>
  Your message here. Use <strong style={{ color: "#18181b" }}>bold</strong> for
  emphasis.
</Text>
```

### CTA Button (Dark)

```tsx
<Section style={{ marginBottom: "28px", textAlign: "center" }}>
  <Button
    href="https://your-url.com"
    style={{
      display: "inline-block",
      backgroundColor: "#18181b",
      color: "#ffffff",
      textDecoration: "none",
      fontSize: "14px",
      fontWeight: 600,
      padding: "14px 28px",
      borderRadius: "10px",
      fontFamily: "'Inter', -apple-system, sans-serif",
    }}
  >
    Button Text
  </Button>
</Section>
```

### Dark Promotional Badge/Card

```tsx
<Section
  style={{
    padding: "24px",
    backgroundColor: "#18181b",
    borderRadius: "12px",
    textAlign: "center",
    marginBottom: "24px",
  }}
>
  <Text
    style={{
      margin: "0 0 4px 0",
      color: "#fbbf24",
      fontSize: "12px",
      fontWeight: 600,
      textTransform: "uppercase",
      letterSpacing: "1px",
    }}
  >
    Limited Time
  </Text>
  <Text
    style={{
      margin: "0 0 8px 0",
      color: "#a1a1aa",
      fontSize: "14px",
      fontWeight: 500,
    }}
  >
    Subtitle text
  </Text>
  <Text
    style={{
      margin: "0 0 4px 0",
      color: "#ffffff",
      fontSize: "32px",
      fontWeight: 600,
      fontFamily: "'DM Sans', -apple-system, sans-serif",
    }}
  >
    50% OFF
  </Text>
  <Text style={{ margin: 0, color: "#71717a", fontSize: "14px" }}>
    Use code{" "}
    <span
      style={{
        color: "#ffffff",
        fontWeight: 600,
        backgroundColor: "#27272a",
        padding: "4px 10px",
        borderRadius: "6px",
        fontFamily: "monospace",
      }}
    >
      CODE123
    </span>
  </Text>
</Section>
```

### Feature Card (Light background)

```tsx
<Section
  style={{
    padding: "20px",
    backgroundColor: "#fafafa",
    borderRadius: "12px",
    border: "1px solid #e4e4e7",
    marginBottom: "12px",
  }}
>
  <Row>
    <Column width={48} style={{ verticalAlign: "top" }}>
      <div
        style={{
          width: "40px",
          height: "40px",
          backgroundColor: "#f0f0ff",
          borderRadius: "10px",
          textAlign: "center",
          lineHeight: "40px",
        }}
      >
        <span style={{ color: "#6366f1", fontSize: "18px" }}>Icon</span>
      </div>
    </Column>
    <Column style={{ paddingLeft: "16px" }}>
      <Text
        style={{
          margin: "0 0 4px 0",
          color: "#18181b",
          fontSize: "16px",
          fontWeight: 500,
        }}
      >
        Feature Title
      </Text>
      <Text
        style={{
          margin: 0,
          color: "#71717a",
          fontSize: "14px",
          lineHeight: "1.5",
        }}
      >
        Feature description text here.
      </Text>
    </Column>
  </Row>
</Section>
```

### Sign-off

```tsx
<Text style={{
  margin: '0 0 8px 0',
  color: '#52525b',
  fontSize: '16px',
  lineHeight: '1.6',
}}>
  Thanks for your support.
</Text>
<Text style={{
  margin: 0,
  color: '#18181b',
  fontSize: '16px',
  fontWeight: 500,
}}>
  Alex
</Text>
```

---

## Email Template Structure

```tsx
import {
  Body,
  Button,
  Column,
  Container,
  Head,
  Html,
  Preview,
  Row,
  Section,
  Tailwind,
  Text,
} from "@react-email/components";
import { siteConfig } from "~/config/site";

export type YourEmailProps = {
  to: string;
  name: string;
  // ... other props
};

const YourEmail = ({ to, name }: YourEmailProps) => {
  return (
    <Html>
      <Head>
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@600&family=Inter:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </Head>
      <Preview>Preview text shown in inbox</Preview>
      <Tailwind>
        <Body
          style={{
            margin: 0,
            padding: 0,
            backgroundColor: "#ffffff",
            fontFamily:
              "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          }}
        >
          {/* Email wrapper */}
          <Container
            style={{
              backgroundColor: "#ffffff",
              padding: "48px 20px",
            }}
          >
            {/* Main card */}
            <Section
              style={{
                maxWidth: "640px",
                margin: "0 auto",
                backgroundColor: "#ffffff",
                borderRadius: "16px",
                border: "1px solid #e4e4e7",
                overflow: "hidden",
                boxShadow:
                  "0 1px 3px rgba(0,0,0,0.05), 0 4px 12px rgba(0,0,0,0.05)",
              }}
            >
              <Section style={{ padding: "40px" }}>
                {/* Greeting */}
                <Text
                  style={{
                    margin: "0 0 20px 0",
                    color: "#52525b",
                    fontSize: "16px",
                    lineHeight: "1.6",
                  }}
                >
                  Hi {name},
                </Text>

                {/* Body content */}
                <Text
                  style={{
                    margin: "0 0 24px 0",
                    color: "#52525b",
                    fontSize: "16px",
                    lineHeight: "1.6",
                  }}
                >
                  Your email content here.
                </Text>

                {/* Optional: Promo badge or feature cards */}

                {/* CTA Button */}
                <Section style={{ marginBottom: "28px", textAlign: "center" }}>
                  <Button
                    href={`${siteConfig.url}/#pricing`}
                    style={{
                      display: "inline-block",
                      backgroundColor: "#18181b",
                      color: "#ffffff",
                      textDecoration: "none",
                      fontSize: "14px",
                      fontWeight: 600,
                      padding: "14px 28px",
                      borderRadius: "10px",
                    }}
                  >
                    Call to Action
                  </Button>
                </Section>

                {/* Sign-off */}
                <Text
                  style={{
                    margin: "0 0 8px 0",
                    color: "#52525b",
                    fontSize: "16px",
                    lineHeight: "1.6",
                  }}
                >
                  Thanks for your support.
                </Text>
                <Text
                  style={{
                    margin: 0,
                    color: "#18181b",
                    fontSize: "16px",
                    fontWeight: 500,
                  }}
                >
                  Alex
                </Text>
              </Section>
            </Section>
          </Container>
        </Body>
      </Tailwind>
    </Html>
  );
};

export default YourEmail;
```

---

## Quick Reference

**When creating a new email:**

1. Copy the template structure above
2. Update props type and component name
3. Write preview text (shows in inbox)
4. Add greeting with personalization
5. Write body paragraphs (max 3-4)
6. Add ONE visual element (promo badge OR feature cards, not both)
7. Add single CTA button
8. Sign off with name

**Style rules:**

- One button per email
- One visual accent element max (dark badge or feature cards)
- Keep paragraphs short (2-3 sentences)
- Personal sign-off always
- No footer clutter (handled by wrapper if needed)
- Zinc color palette only
- DM Sans for headlines/numbers, Inter for everything else
