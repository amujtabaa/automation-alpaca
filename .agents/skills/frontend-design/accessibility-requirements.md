# Accessibility & UX Requirements

Mandatory accessibility patterns and UX standards for web interfaces. These are requirements, not suggestions.

**Use alongside:**

- `SKILL.md` - Creative philosophy
- `design-systems-reference.md` - Technical craft
- `dashboard-visual-hierarchy.md` - Color/attention hierarchy

---

## 1. Focus States (CRITICAL)

### Every Interactive Element Needs Visible Focus

```css
/* Standard pattern - Tailwind */
.interactive {
  @apply focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-primary;
}

/* CSS equivalent */
.interactive:focus-visible {
  outline: none;
  box-shadow:
    0 0 0 2px var(--background),
    0 0 0 4px var(--ring);
}
```

### Never Remove Outline Without Replacement

```css
/* BAD - accessibility violation */
button:focus {
  outline: none;
}

/* GOOD - replaced with ring */
button:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--ring-color);
}
```

### Prefer :focus-visible Over :focus

`:focus-visible` only triggers for keyboard navigation, not mouse clicks.

```css
/* Prefer - keyboard only */
button:focus-visible {
  box-shadow: 0 0 0 2px var(--ring);
}

/* Avoid - shows on mouse click too */
button:focus {
  box-shadow: 0 0 0 2px var(--ring);
}
```

---

## 2. Semantic HTML

### Use Correct Elements

| Action           | Correct Element          | Wrong Element                |
| ---------------- | ------------------------ | ---------------------------- |
| Clickable action | `<button>`               | `<div onClick>`              |
| Navigation link  | `<a href>`               | `<button>`, `<span onClick>` |
| Form submission  | `<button type="submit">` | `<div>`, `<a>`               |
| List of items    | `<ul>`, `<ol>`           | `<div>` with divs            |

```tsx
// BAD - not keyboard accessible
<div onClick={handleSubmit} className="btn">Submit</div>

// GOOD - native keyboard support
<button onClick={handleSubmit} className="btn">Submit</button>
```

### Use Landmark Elements

```tsx
<header>...</header>      // Site header
<nav>...</nav>            // Navigation
<main>...</main>          // Primary content (one per page)
<aside>...</aside>        // Sidebar/secondary content
<article>...</article>    // Self-contained content
<footer>...</footer>      // Site footer
```

### Heading Hierarchy

- One `<h1>` per page
- Headings must be hierarchical (never skip levels)
- Use for structure, not styling

```tsx
// BAD - skips h2
<h1>Dashboard</h1>
<h3>Recent Activity</h3>

// GOOD - proper hierarchy
<h1>Dashboard</h1>
<h2>Recent Activity</h2>
<h3>Today</h3>
```

---

## 3. ARIA Patterns

### Icon Buttons Must Have Labels

```tsx
// BAD - screen reader says "button"
<button><SearchIcon /></button>

// GOOD - screen reader says "Search"
<button aria-label="Search"><SearchIcon /></button>

// ALSO GOOD - visible text
<button><SearchIcon /> Search</button>
```

### Form Controls Need Labels

Every input needs either a visible label or ARIA attributes.

```tsx
// Option 1: Visible label (preferred)
<label htmlFor="email">Email</label>
<input id="email" type="email" />

// Option 2: Visually hidden label
<label htmlFor="search" className="sr-only">Search</label>
<input id="search" type="search" placeholder="Search..." />

// Option 3: aria-label (no visible label)
<input type="search" aria-label="Search" placeholder="Search..." />
```

### Error Messages with aria-describedby

```tsx
<div>
  <label htmlFor="email">Email</label>
  <input
    id="email"
    type="email"
    aria-invalid={!!error}
    aria-describedby={error ? "email-error" : undefined}
  />
  {error && (
    <p id="email-error" role="alert" className="text-red-500 text-sm">
      {error}
    </p>
  )}
</div>
```

### Loading States

```tsx
// Announce loading to screen readers
<button disabled={isLoading} aria-busy={isLoading}>
  {isLoading ? "Saving..." : "Save"}
</button>

// Or with live region
<div aria-live="polite">
  {isLoading && <p>Loading results...</p>}
</div>
```

---

## 4. Keyboard Navigation

### Tab Order

- Tab order should follow visual order
- Use `tabindex="0"` to make custom elements focusable
- Use `tabindex="-1"` for programmatic focus only
- Never use `tabindex` greater than 0

### Skip Links

Provide skip link for keyboard users to bypass navigation.

```tsx
// At top of page
<a href="#main-content" className="sr-only focus:not-sr-only focus:absolute ...">
  Skip to main content
</a>

// Main content area
<main id="main-content">...</main>
```

### Focus Trapping in Modals

Modals must trap focus within themselves.

```tsx
// Use Radix Dialog or similar - handles focus trap automatically
import * as Dialog from "@radix-ui/react-dialog";

<Dialog.Root>
  <Dialog.Trigger>Open</Dialog.Trigger>
  <Dialog.Portal>
    <Dialog.Overlay />
    <Dialog.Content>
      {/* Focus is trapped here */}
      <Dialog.Close>Close</Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal>
</Dialog.Root>;
```

---

## 5. Motion Accessibility

### Respect prefers-reduced-motion (REQUIRED)

All animations MUST respect this user preference.

```css
/* Global reset for reduced motion */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

```tsx
// In React/JS
const prefersReducedMotion = window.matchMedia(
  '(prefers-reduced-motion: reduce)'
).matches

// Framer Motion
<motion.div
  animate={{ opacity: 1 }}
  transition={{ duration: prefersReducedMotion ? 0 : 0.3 }}
/>
```

### Animation Performance

Only animate `transform` and `opacity` (GPU-accelerated).

```css
/* BAD - triggers layout recalculation */
.animate {
  transition:
    width 0.3s,
    height 0.3s,
    margin 0.3s;
}

/* GOOD - GPU accelerated */
.animate {
  transition:
    transform 0.3s,
    opacity 0.3s;
}
```

### Never Use transition: all

```css
/* BAD - animates everything including layout */
.element {
  transition: all 0.3s ease;
}

/* GOOD - explicit properties */
.element {
  transition:
    transform 0.2s ease,
    opacity 0.2s ease,
    background-color 0.2s ease;
}
```

---

## 6. Form Best Practices

### Use Correct Input Types

```tsx
<input type="email" />      // Email keyboard on mobile
<input type="tel" />        // Phone keyboard
<input type="url" />        // URL keyboard
<input type="search" />     // Search with clear button
<input type="number" />     // Numeric keyboard
<input type="date" />       // Native date picker
```

### Always Include autocomplete

```tsx
<input type="email" autocomplete="email" />
<input type="password" autocomplete="current-password" />
<input type="password" autocomplete="new-password" />
<input type="text" autocomplete="name" />
<input type="text" autocomplete="given-name" />
<input type="text" autocomplete="family-name" />
<input type="tel" autocomplete="tel" />
<input type="text" autocomplete="street-address" />
```

### Never Block Paste

Paste blocking is an accessibility violation. Password managers need paste.

```tsx
// BAD - breaks password managers
<input type="password" onPaste={(e) => e.preventDefault()} />

// GOOD - allow paste
<input type="password" />
```

### Error Handling

- Display errors inline with the field
- Focus the first error field on form submission
- Keep submit button enabled until submission starts

```tsx
function Form() {
  const [errors, setErrors] = useState({});
  const firstErrorRef = useRef(null);

  function handleSubmit(e) {
    e.preventDefault();
    const newErrors = validate(formData);

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      // Focus first error field
      firstErrorRef.current?.focus();
      return;
    }

    // Submit...
  }

  return (
    <form onSubmit={handleSubmit}>
      <input
        ref={errors.email ? firstErrorRef : null}
        aria-invalid={!!errors.email}
      />
      {/* Submit stays enabled until actual submission */}
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Submitting..." : "Submit"}
      </button>
    </form>
  );
}
```

---

## 7. Images & Media

### Alt Text Required

```tsx
// Informative image - describe content
<img src="/chart.png" alt="Revenue increased 25% from Q1 to Q2" />

// Decorative image - empty alt
<img src="/decoration.svg" alt="" />

// Complex image - longer description
<figure>
  <img src="/diagram.png" alt="System architecture diagram" />
  <figcaption>
    The system consists of three layers: API gateway,
    microservices, and database cluster.
  </figcaption>
</figure>
```

### Explicit Dimensions

Prevents layout shift (CLS).

```tsx
<img src="/hero.jpg" alt="Product dashboard" width={1200} height={630} />
```

### Lazy Loading Below Fold

```tsx
// Above fold - load immediately
<img src="/hero.jpg" alt="..." />

// Below fold - lazy load
<img src="/feature.jpg" alt="..." loading="lazy" />
```

---

## 8. Color & Contrast

### WCAG AA Minimums

| Content Type                         | Minimum Ratio |
| ------------------------------------ | ------------- |
| Normal text (< 18px)                 | 4.5:1         |
| Large text (>= 18px bold or >= 24px) | 3:1           |
| UI components, icons                 | 3:1           |
| Focus indicators                     | 3:1           |

### Never Rely on Color Alone

```tsx
// BAD - only color indicates error
<input className={error ? "border-red-500" : "border-gray-300"} />

// GOOD - color + icon + text
<div>
  <input
    className={error ? "border-red-500" : "border-gray-300"}
    aria-invalid={!!error}
  />
  {error && (
    <p className="text-red-500 flex items-center gap-1">
      <AlertIcon /> {error}
    </p>
  )}
</div>
```

---

## 9. Destructive Actions

### Require Confirmation

```tsx
// Option 1: Confirmation dialog
<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="destructive">Delete Account</Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Delete account?</AlertDialogTitle>
      <AlertDialogDescription>
        This action cannot be undone. All data will be permanently deleted.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction onClick={handleDelete}>Delete</AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>;

// Option 2: Undo capability
function handleDelete() {
  // Soft delete with undo option
  toast({
    title: "Item deleted",
    action: <Button onClick={handleUndo}>Undo</Button>,
    duration: 5000,
  });
}
```

---

## Anti-Patterns Checklist

**NEVER do these:**

| Anti-Pattern                          | Why It's Bad                          |
| ------------------------------------- | ------------------------------------- |
| `user-scalable=no` in viewport        | Blocks zoom for low-vision users      |
| `onPaste={(e) => e.preventDefault()}` | Breaks password managers              |
| `transition: all`                     | Performance killer, animates layout   |
| `outline: none` without replacement   | Removes focus indicator               |
| `<div onClick>` instead of `<button>` | No keyboard support                   |
| Missing labels on inputs              | Screen readers can't describe field   |
| Missing alt on images                 | Screen readers can't describe content |
| Skipping heading levels               | Breaks document structure             |
| `tabindex > 0`                        | Creates confusing tab order           |

---

## Quick Audit Checklist

Before shipping, verify:

**Focus & Keyboard:**

- [ ] All interactive elements have visible focus states
- [ ] Tab order follows visual order
- [ ] Custom components are keyboard accessible
- [ ] Modals trap focus

**Screen Readers:**

- [ ] All images have appropriate alt text
- [ ] All form inputs have labels
- [ ] Icon buttons have aria-label
- [ ] Error messages use aria-describedby

**Motion:**

- [ ] Animations respect prefers-reduced-motion
- [ ] Only animating transform/opacity
- [ ] No `transition: all`

**Forms:**

- [ ] Correct input types used
- [ ] autocomplete attributes present
- [ ] Paste not blocked
- [ ] Errors displayed inline with focus

**Color:**

- [ ] Text meets 4.5:1 contrast (3:1 for large)
- [ ] Information not conveyed by color alone

---

## Sources

- Vercel Web Interface Guidelines
- WCAG 2.1 AA
- MDN Accessibility Documentation

---

_Compiled: January 2025_
