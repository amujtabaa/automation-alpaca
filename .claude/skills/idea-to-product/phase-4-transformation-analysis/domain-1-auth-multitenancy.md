# Domain 1: Authentication & Multi-tenancy Deep Dive

**Focus:** User management, session handling, workspace isolation, RLS policies

---

## Questions to Answer

### Authentication System
- How does the kit handle user sessions?
- What auth methods are supported (email, social, magic link)?
- Where is auth configured?
- How are protected routes implemented?

### Multi-tenancy
- Does the kit support workspaces/organizations?
- How are users linked to workspaces?
- How is data isolated between tenants?
- Can users belong to multiple workspaces?

### Row Level Security
- Are RLS policies used?
- What's the RLS policy pattern?
- Helper functions for workspace membership?

---

## Files to Review

```
/lib/auth/ or /lib/supabase/
/app/(authenticated)/ or /app/dashboard/
/middleware.ts
/supabase/migrations/ (RLS policies)
```

---

## Common Requirements

- [ ] User registration/login
- [ ] Email verification
- [ ] Password reset
- [ ] Social login (Google)
- [ ] Magic link auth
- [ ] Session management
- [ ] Workspace creation
- [ ] Team invitations
- [ ] Role-based access (admin/member)
- [ ] RLS for all tables

---

## Implementation Patterns

### Workspace-Scoped Table
```typescript
// All new tables should follow this pattern
export const opportunitiesTable = pgTable('opportunities', {
  id: uuid('id').primaryKey().defaultRandom(),
  workspace_id: uuid('workspace_id').notNull().references(() => workspacesTable.id),
  // ... other fields
  created_at: timestamp('created_at').defaultNow(),
});
```

### RLS Policy Pattern
```sql
CREATE POLICY "Users can view own workspace data"
ON opportunities FOR SELECT
TO authenticated
USING (
  EXISTS (
    SELECT 1 FROM workspace_members wm
    WHERE wm.workspace_id = opportunities.workspace_id
    AND wm.user_id = auth.uid()
  )
);
```

### Protected Route Pattern
```typescript
// app/(authenticated)/layout.tsx
import { redirect } from 'next/navigation';
import { getSession } from '@/lib/auth';

export default async function AuthLayout({ children }) {
  const session = await getSession();
  if (!session) redirect('/login');
  return <>{children}</>;
}
```

---

## Output Checklist

- [ ] Auth flow diagram
- [ ] New tables with workspace_id
- [ ] RLS policies for each new table
- [ ] Role checks needed
- [ ] Custom user metadata fields

---
