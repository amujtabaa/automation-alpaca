# Domain 3: Database Architecture Deep Dive

**Focus:** Schema design, migrations, types, RLS, performance

---

## Questions to Answer

### Current Schema
- What tables exist?
- What's the migration workflow?
- How are types generated?
- What indexes exist?

### New Schema Needs
- What new tables are required?
- Relationships between tables?
- RLS policies needed?
- Performance considerations?

---

## Files to Review

```
/prisma/schema.prisma or /supabase/migrations/
/types/ or /lib/database/types.ts
/lib/db/ or /lib/supabase/
```

---

## Schema Design Template

```sql
-- Migration: [timestamp]_[description].sql

-- 1. Create enum types
CREATE TYPE opportunity_status AS ENUM ('new', 'viewed', 'replied', 'ignored');

-- 2. Create tables
CREATE TABLE opportunities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,

  -- Core fields
  external_id TEXT NOT NULL,
  title TEXT NOT NULL,
  url TEXT NOT NULL,

  -- Metrics
  traffic_value DECIMAL(10,2),
  engagement_score INTEGER,

  -- Status
  status opportunity_status DEFAULT 'new',

  -- Timestamps
  detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Constraints
  UNIQUE(workspace_id, external_id)
);

-- 3. Create indexes
CREATE INDEX opportunities_workspace_status_idx
ON opportunities(workspace_id, status);

CREATE INDEX opportunities_detected_at_idx
ON opportunities(detected_at DESC);

-- 4. Enable RLS
ALTER TABLE opportunities ENABLE ROW LEVEL SECURITY;

-- 5. Create RLS policies
CREATE POLICY "Users can view own workspace opportunities"
ON opportunities FOR SELECT
TO authenticated
USING (
  EXISTS (
    SELECT 1 FROM workspace_members wm
    WHERE wm.workspace_id = opportunities.workspace_id
    AND wm.user_id = auth.uid()
  )
);

CREATE POLICY "Users can update own workspace opportunities"
ON opportunities FOR UPDATE
TO authenticated
USING (
  EXISTS (
    SELECT 1 FROM workspace_members wm
    WHERE wm.workspace_id = opportunities.workspace_id
    AND wm.user_id = auth.uid()
  )
);
```

---

## Type Generation

### Prisma
```bash
npx prisma generate
npx prisma db push
```

### Supabase
```bash
supabase gen types typescript --local > types/supabase.ts
```

---

## Common Table Patterns

### Settings Table
```sql
CREATE TABLE workspace_settings (
  workspace_id UUID PRIMARY KEY REFERENCES workspaces(id),
  min_traffic_value INTEGER DEFAULT 100,
  notification_email BOOLEAN DEFAULT true,
  notification_frequency TEXT DEFAULT 'instant',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### Cache Table
```sql
CREATE TABLE api_cache (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX api_cache_expires_idx ON api_cache(expires_at);
```

---

## Output Checklist

- [ ] Complete migration files
- [ ] All RLS policies
- [ ] Indexes for common queries
- [ ] Type generation commands
- [ ] Entity relationship diagram

---
