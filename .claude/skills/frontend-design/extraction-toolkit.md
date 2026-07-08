# Design Extraction Toolkit

Scripts and techniques for extracting design tokens, CSS values, and behavioral specifications from live websites using Browser MCP. Use when analyzing reference sites, cloning designs, or verifying implementation fidelity.

**Requires:** Browser MCP (Chrome MCP, Playwright MCP, Puppeteer MCP, or Browserbase MCP)

---

## 1. Asset Discovery Script

Run this in the browser console (via Browser MCP's executeJavaScript or equivalent) to discover all visual assets on a page.

```javascript
JSON.stringify(
  {
    images: [...document.querySelectorAll("img")].map((img) => ({
      src: img.src || img.currentSrc,
      alt: img.alt,
      width: img.naturalWidth,
      height: img.naturalHeight,
      parentClasses: img.parentElement?.className
        ?.toString()
        .split(" ")
        .slice(0, 3)
        .join(" "),
      position: getComputedStyle(img).position,
      zIndex: getComputedStyle(img).zIndex,
    })),
    videos: [...document.querySelectorAll("video")].map((v) => ({
      src: v.src || v.querySelector("source")?.src,
      poster: v.poster,
      autoplay: v.autoplay,
      loop: v.loop,
      muted: v.muted,
    })),
    backgroundImages: [...document.querySelectorAll("*")]
      .filter((el) => {
        const bg = getComputedStyle(el).backgroundImage;
        return bg && bg !== "none";
      })
      .slice(0, 50)
      .map((el) => ({
        url: getComputedStyle(el).backgroundImage,
        element:
          el.tagName + "." + (el.className?.toString().split(" ")[0] || ""),
      })),
    svgCount: document.querySelectorAll("svg").length,
    fonts: [
      ...new Set(
        [...document.querySelectorAll("*")]
          .slice(0, 200)
          .map((el) => getComputedStyle(el).fontFamily),
      ),
    ],
    favicons: [...document.querySelectorAll('link[rel*="icon"]')].map((l) => ({
      href: l.href,
      sizes: l.sizes?.toString(),
    })),
  },
  null,
  2,
);
```

**What this captures:**

- All `<img>` elements with natural dimensions, alt text, and positioning context
- All `<video>` elements with playback attributes
- Background images (limited to first 50 to avoid performance issues)
- Total SVG count (extract individually later)
- All unique font-family values in use
- Favicon/icon links

**Gotcha -- layered compositions:** A section that looks like one image is often multiple layers: a background gradient, a foreground PNG, and an overlay SVG. Check `zIndex` and `position` values to identify stacking. If you see `position: absolute` elements sharing a parent with `position: relative`, you likely have a layered composition that needs each layer extracted separately.

---

## 2. Component CSS Extraction Script

Recursive DOM walker that extracts exact `getComputedStyle()` values for every element up to 4 levels deep. Replace `SELECTOR` with the target CSS selector.

```javascript
(function (selector) {
  const el = document.querySelector(selector);
  if (!el) return JSON.stringify({ error: "Element not found: " + selector });

  const props = [
    "fontSize",
    "fontWeight",
    "fontFamily",
    "lineHeight",
    "letterSpacing",
    "color",
    "textTransform",
    "textDecoration",
    "backgroundColor",
    "background",
    "padding",
    "paddingTop",
    "paddingRight",
    "paddingBottom",
    "paddingLeft",
    "margin",
    "marginTop",
    "marginRight",
    "marginBottom",
    "marginLeft",
    "width",
    "height",
    "maxWidth",
    "minWidth",
    "maxHeight",
    "minHeight",
    "display",
    "flexDirection",
    "justifyContent",
    "alignItems",
    "gap",
    "gridTemplateColumns",
    "gridTemplateRows",
    "borderRadius",
    "border",
    "boxShadow",
    "overflow",
    "position",
    "top",
    "right",
    "bottom",
    "left",
    "zIndex",
    "opacity",
    "transform",
    "transition",
    "cursor",
    "objectFit",
    "objectPosition",
    "mixBlendMode",
    "filter",
    "backdropFilter",
    "whiteSpace",
    "textOverflow",
    "WebkitLineClamp",
  ];

  function extractStyles(element) {
    const cs = getComputedStyle(element);
    const styles = {};
    props.forEach((p) => {
      const v = cs[p];
      if (
        v &&
        v !== "none" &&
        v !== "normal" &&
        v !== "auto" &&
        v !== "0px" &&
        v !== "rgba(0, 0, 0, 0)" &&
        v !== "rgb(0, 0, 0)"
      ) {
        styles[p] = v;
      }
    });
    return styles;
  }

  function walk(element, depth) {
    if (depth > 4) return null;
    const children = [...element.children];
    return {
      tag: element.tagName.toLowerCase(),
      classes: element.className?.toString().split(" ").slice(0, 5).join(" "),
      text:
        element.childNodes.length === 1 && element.childNodes[0].nodeType === 3
          ? element.textContent.trim().slice(0, 200)
          : null,
      styles: extractStyles(element),
      images:
        element.tagName === "IMG"
          ? { src: element.src, alt: element.alt }
          : null,
      childCount: children.length,
      children: children
        .slice(0, 20)
        .map((c) => walk(c, depth + 1))
        .filter(Boolean),
    };
  }

  return JSON.stringify(walk(el, 0), null, 2);
})("SELECTOR");
```

**Usage:**

1. Navigate to target page via Browser MCP
2. Identify the component's outermost container selector (inspect DOM)
3. Replace `SELECTOR` with the CSS selector (e.g., `'section.hero'`, `'[data-section="features"]'`, `'header nav'`)
4. Execute the script
5. Parse the JSON output into a component spec

**What this captures per element:**

- Tag name and CSS classes
- Text content (first 200 chars, text nodes only)
- 50+ computed CSS properties (filtered to non-default values)
- Image src/alt for `<img>` elements
- Child count and recursive child extraction (up to 4 levels, 20 children per level)

**Gotcha -- default filtering:** The script filters out `none`, `normal`, `auto`, `0px`, and transparent black. If a property intentionally uses one of these values (e.g., `transform: none` as an explicit reset), it won't appear in output. For targeted property checks, query `getComputedStyle(el).propertyName` directly.

---

## 3. Font Discovery Script

Detailed font analysis including weights, sizes, letter-spacing, and OpenType features across 500 elements.

```javascript
(function () {
  const samples = [...document.querySelectorAll("*")].slice(0, 500);
  const fontMap = {};

  samples.forEach((el) => {
    const cs = getComputedStyle(el);
    const family = cs.fontFamily;
    const weight = cs.fontWeight;
    const size = cs.fontSize;
    const letterSpacing = cs.letterSpacing;
    const features = cs.fontFeatureSettings;

    if (!fontMap[family])
      fontMap[family] = {
        weights: new Set(),
        sizes: new Set(),
        letterSpacings: new Set(),
        features: new Set(),
      };
    fontMap[family].weights.add(weight);
    fontMap[family].sizes.add(size);
    if (letterSpacing !== "normal")
      fontMap[family].letterSpacings.add(letterSpacing);
    if (features !== "normal") fontMap[family].features.add(features);
  });

  const result = {};
  for (const [family, data] of Object.entries(fontMap)) {
    result[family] = {
      weights: [...data.weights].sort(),
      sizes: [...data.sizes].sort((a, b) => parseFloat(a) - parseFloat(b)),
      letterSpacings: [...data.letterSpacings],
      features: [...data.features],
    };
  }

  return JSON.stringify(result, null, 2);
})();
```

**What this reveals:**

- Every font family in use across the page
- All weight variants used per font (reveals the weight ceiling)
- All size variants sorted ascending (reveals the type scale)
- Non-default letter-spacing values (reveals the tracking system)
- OpenType features in use (ligatures, tabular numbers, stylistic sets)

**Gotcha -- inherited fonts:** Many elements inherit their font-family from a parent. The output may show the same font under slightly different resolved strings (e.g., with and without quotes). Group by the base font name when analyzing results.

---

## 4. Multi-State Extraction Workflow

For extracting animations and transitions by comparing CSS before and after a state change.

### Step-by-Step Process

**Step 1: Identify the trigger**

- Scroll position? Note the scroll threshold
- Click? Note the target element
- Hover? Note the hover target
- Time? Note the delay

**Step 2: Capture State A**

Run the Component CSS Extraction Script (Section 2) on the target element in its DEFAULT state.

**Step 3: Trigger the state change**

Via Browser MCP:

- Scroll: `window.scrollTo({ top: [threshold], behavior: 'instant' })`
- Click: `document.querySelector('[selector]').click()`
- Hover: Move cursor to element coordinates
- Time: Wait for the specified duration

**Step 4: Capture State B**

Run the same extraction script again on the same element in its CHANGED state.

**Step 5: Diff the states**

Compare State A and State B JSON outputs. The changed properties are your animation specification.

**Step 6: Extract transition timing**

Run this on the element to get its transition/animation properties:

```javascript
(function (selector) {
  const el = document.querySelector(selector);
  if (!el) return JSON.stringify({ error: "Element not found: " + selector });
  const cs = getComputedStyle(el);
  return JSON.stringify(
    {
      transition: cs.transition,
      transitionProperty: cs.transitionProperty,
      transitionDuration: cs.transitionDuration,
      transitionTimingFunction: cs.transitionTimingFunction,
      transitionDelay: cs.transitionDelay,
      animation: cs.animation,
      animationName: cs.animationName,
      animationDuration: cs.animationDuration,
      animationTimingFunction: cs.animationTimingFunction,
      animationDelay: cs.animationDelay,
      willChange: cs.willChange,
    },
    null,
    2,
  );
})("SELECTOR");
```

### Worked Example: Header Scroll Transition

1. Navigate to page, scroll to top
2. Extract header CSS at scroll position 0 (State A)
3. Scroll to position 200px via `window.scrollTo({ top: 200, behavior: 'instant' })`
4. Extract header CSS at scroll position 200 (State B)
5. Diff reveals changed properties:

| Property        | State A (top) | State B (scrolled)         | Transition                     |
| --------------- | ------------- | -------------------------- | ------------------------------ |
| height          | 80px          | 56px                       | height 200ms ease-out          |
| padding         | 24px 32px     | 12px 32px                  | padding 200ms ease-out         |
| background      | transparent   | rgba(255,255,255,0.95)     | background 200ms ease-out      |
| backdrop-filter | none          | blur(12px)                 | backdrop-filter 200ms ease-out |
| box-shadow      | none          | 0 1px 3px rgba(0,0,0,0.08) | box-shadow 200ms ease-out      |
| logo font-size  | 24px          | 18px                       | font-size 200ms ease-out       |

6. Extract transition timing: `all 200ms cubic-bezier(0.25, 1, 0.5, 1)`
7. Write spec:
   ```
   Trigger: scroll > 100px (IntersectionObserver)
   Transition: height, background, box-shadow, backdrop-filter, padding, font-size
   Duration: 200ms
   Easing: cubic-bezier(0.25, 1, 0.5, 1)
   ```

**Gotcha -- capture timing:** Trigger the state change with `behavior: 'instant'` to skip the scroll animation itself. If you use `behavior: 'smooth'`, you may capture an intermediate state instead of the final one. Wait 300-500ms after triggering before capturing State B to ensure transitions have completed.

---

## 5. Color Palette Extraction

Extract the complete color system from a page, sorted by frequency. Top 15 per category.

```javascript
(function () {
  const colors = { backgrounds: {}, texts: {}, borders: {} };
  const samples = [...document.querySelectorAll("*")].slice(0, 300);

  samples.forEach((el) => {
    const cs = getComputedStyle(el);

    const bg = cs.backgroundColor;
    if (bg && bg !== "rgba(0, 0, 0, 0)" && bg !== "transparent") {
      colors.backgrounds[bg] = (colors.backgrounds[bg] || 0) + 1;
    }

    const color = cs.color;
    if (color) {
      colors.texts[color] = (colors.texts[color] || 0) + 1;
    }

    const borderColor = cs.borderColor;
    if (
      borderColor &&
      borderColor !== "rgb(0, 0, 0)" &&
      cs.borderWidth !== "0px"
    ) {
      colors.borders[borderColor] = (colors.borders[borderColor] || 0) + 1;
    }
  });

  const sortByFreq = (obj) =>
    Object.entries(obj)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 15);

  return JSON.stringify(
    {
      backgrounds: sortByFreq(colors.backgrounds),
      texts: sortByFreq(colors.texts),
      borders: sortByFreq(colors.borders),
    },
    null,
    2,
  );
})();
```

**What this reveals:**

- Most-used background colors (sorted by frequency) -- reveals the surface hierarchy
- Most-used text colors -- reveals the contrast hierarchy
- Most-used border colors -- reveals the depth strategy (transparent borders vs solid)

**Gotcha -- RGB vs hex:** `getComputedStyle` always returns RGB/RGBA format, not hex. Convert with: `rgb(23, 23, 23)` = `#171717`. Online converters or a quick `toString(16)` call handles this.

---

## Usage Notes

1. **Browser MCP required.** These scripts run in the browser context. They need a Browser MCP tool that supports JavaScript execution (Chrome MCP `executeJavaScript`, Playwright `evaluate`, Puppeteer `page.evaluate`).

2. **Performance.** The scripts sample the first 200-500 elements to avoid performance issues on heavy pages. For specific components, use the targeted Component CSS Extraction Script (Section 2) with a precise selector instead of scanning the whole DOM.

3. **Accuracy.** `getComputedStyle()` returns the ACTUAL rendered values, not the authored CSS. This means you get resolved values (e.g., `rgb(23, 23, 23)` not `var(--foreground)`). Map back to design tokens manually when building the implementation.

4. **Layered composition detection.** Always check for stacked elements. A hero section that looks like a single image often has: background gradient layer, foreground image, overlay with mix-blend-mode, and text on top. Look for `position: absolute` children inside `position: relative` parents, and check `zIndex` ordering.

5. **Integration with interaction-patterns.md.** Use these extraction tools to populate the Component Specification Template. Extract CSS for State A, trigger change, extract State B, then diff for the States and Behaviors section of the spec.

6. **Large pages.** If a page has thousands of elements, increase the slice limit cautiously. Going beyond 500 elements can cause noticeable lag in the browser tab. For full-page analysis, run the scripts section by section using targeted selectors.

---

## Sources

Extraction patterns adapted from [JCodesMore/ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template) (MIT license).
