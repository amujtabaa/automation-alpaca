# Domain 5: UI Components Deep Dive

**Focus:** Dashboard layout, data tables, forms, modals, filters

---

## Questions to Answer

### Existing Components
- What UI library is used (Shadcn, etc.)?
- What components are available?
- What's the layout pattern?
- How are data tables implemented?

### Components Needed
- What pages to build?
- What custom components?
- Filtering/sorting needs?
- Form requirements?

---

## Files to Review

```
/components/ui/
/app/(authenticated)/ or /app/dashboard/
/lib/hooks/ (data fetching)
```

---

## Dashboard Page Pattern

```typescript
// app/(authenticated)/opportunities/page.tsx
import { db } from '@/lib/database';
import { getWorkspace } from '@/lib/auth';
import { OpportunitiesDashboard } from '@/components/opportunities/dashboard';

export default async function OpportunitiesPage() {
  const workspace = await getWorkspace();

  const opportunities = await db.opportunity.findMany({
    where: { workspace_id: workspace.id },
    orderBy: { detected_at: 'desc' },
    take: 100,
  });

  return (
    <div className="container py-6">
      <h1 className="text-2xl font-bold mb-6">Opportunities</h1>
      <OpportunitiesDashboard initialData={opportunities} />
    </div>
  );
}
```

---

## Data Table Pattern (TanStack Table)

```typescript
// components/opportunities/table.tsx
'use client';

import {
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
} from '@tanstack/react-table';

const columns = [
  {
    accessorKey: 'title',
    header: 'Title',
    cell: ({ row }) => (
      <a href={row.original.url} target="_blank" className="hover:underline">
        {row.getValue('title')}
      </a>
    ),
  },
  {
    accessorKey: 'traffic_value',
    header: 'Traffic Value',
    cell: ({ row }) => `$${row.getValue('traffic_value')}`,
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => <StatusBadge status={row.getValue('status')} />,
  },
  // ... more columns
];

export function OpportunitiesTable({ data }) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    // Table implementation
  );
}
```

---

## Filter Component Pattern

```typescript
// components/opportunities/filters.tsx
'use client';

import { useRouter, useSearchParams } from 'next/navigation';

export function OpportunityFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const updateFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams);
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    router.push(`?${params.toString()}`);
  };

  return (
    <div className="flex gap-4 mb-4">
      <Select onValueChange={(v) => updateFilter('status', v)}>
        <SelectTrigger className="w-[180px]">
          <SelectValue placeholder="Filter by status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="new">New</SelectItem>
          <SelectItem value="viewed">Viewed</SelectItem>
          <SelectItem value="replied">Replied</SelectItem>
        </SelectContent>
      </Select>

      {/* More filters */}
    </div>
  );
}
```

---

## Modal Pattern

```typescript
// components/opportunities/details-modal.tsx
'use client';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

export function OpportunityDetailsModal({
  opportunity,
  open,
  onOpenChange
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{opportunity.title}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Opportunity details */}

          <div className="flex gap-2">
            <Button variant="outline" onClick={() => markAsViewed(opportunity.id)}>
              Mark as Viewed
            </Button>
            <Button onClick={() => requestReply(opportunity.id)}>
              Request Reply
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

---

## Server Action Pattern

```typescript
// app/(authenticated)/opportunities/actions.ts
'use server';

import { db } from '@/lib/database';
import { getWorkspace } from '@/lib/auth';
import { revalidatePath } from 'next/cache';

export async function updateOpportunityStatus(
  opportunityId: string,
  status: string
) {
  const workspace = await getWorkspace();

  await db.opportunity.update({
    where: {
      id: opportunityId,
      workspace_id: workspace.id, // Security: ensure ownership
    },
    data: {
      status,
      updated_at: new Date(),
    },
  });

  revalidatePath('/opportunities');
}
```

---

## Output Checklist

- [ ] Page layouts
- [ ] Data table components
- [ ] Filter components
- [ ] Modal/dialog components
- [ ] Form components
- [ ] Server actions
- [ ] Loading/empty states

---
