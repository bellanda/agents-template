# Component Composition

## Contents

- Items always inside their Group component
- Callouts use Alert
- Empty states use Empty component
- Toast notifications use sonner
- Choosing between overlay components
- Dialog, Sheet, and Drawer always need a Title
- Card structure
- Button has no isPending or isLoading prop
- TabsTrigger must be inside TabsList
- Avatar always needs AvatarFallback
- Use Separator instead of raw hr or border divs
- Use Skeleton for loading placeholders
- Use Badge instead of custom styled spans

---

## Items always inside their Group component

Never render items directly inside the content container.

**Incorrect:**

```tsx
<SelectContent>
    <SelectItem value="apple">Apple</SelectItem>
    <SelectItem value="banana">Banana</SelectItem>
</SelectContent>
```

**Correct:**

```tsx
<SelectContent>
    <SelectGroup>
        <SelectItem value="apple">Apple</SelectItem>
        <SelectItem value="banana">Banana</SelectItem>
    </SelectGroup>
</SelectContent>
```

This applies to all group-based components:

| Item                                                       | Group               |
| ---------------------------------------------------------- | ------------------- |
| `SelectItem`, `SelectLabel`                                | `SelectGroup`       |
| `DropdownMenuItem`, `DropdownMenuLabel`, `DropdownMenuSub` | `DropdownMenuGroup` |
| `MenubarItem`                                              | `MenubarGroup`      |
| `ContextMenuItem`                                          | `ContextMenuGroup`  |
| `CommandItem`                                              | `CommandGroup`      |

---

## Callouts use Alert

```tsx
<Alert>
    <AlertTitle>Warning</AlertTitle>
    <AlertDescription>Something needs attention.</AlertDescription>
</Alert>
```

---

## Empty states use Empty component

```tsx
<Empty>
    <EmptyHeader>
        <EmptyMedia variant="icon">
            <FolderIcon />
        </EmptyMedia>
        <EmptyTitle>No projects yet</EmptyTitle>
        <EmptyDescription>
            Get started by creating a new project.
        </EmptyDescription>
    </EmptyHeader>
    <EmptyContent>
        <Button>Create Project</Button>
    </EmptyContent>
</Empty>
```

---

## Toast notifications use sonner

```tsx
import { toast } from "sonner";

toast.success("Changes saved.");
toast.error("Something went wrong.");
toast("File deleted.", {
    action: { label: "Undo", onClick: () => undoDelete() },
});
```

---

## Choosing between overlay components — Dialog-first

**Default to `Dialog` for any "abre, faz uma coisa, fecha" surface.** Centralized, dismiss on click-outside/ESC returns the user to the exact previous state, strong visual focus. UX is superior in almost every case.

`Sheet` and `Drawer` require an explicit reason to pick over `Dialog` — write it as a code comment when you do.

| Use case                                                   | Component     | Notes                                                                            |
| ---------------------------------------------------------- | ------------- | -------------------------------------------------------------------------------- |
| Focused task, form, snippet, detail view, picker, edit     | `Dialog`      | **Default.** `lg:max-w-2xl`; for code/table-heavy use `lg:max-w-3xl xl:max-w-4xl`. Tall content → `max-h-[85vh] overflow-y-auto`. |
| Destructive action confirmation (delete, reset, sign out)  | `AlertDialog` | Only for confirms — forms still use `Dialog`.                                    |
| Persistent inspector/settings panel side-by-side with main | `Sheet`       | Justify in code: "stays open during navigation/inspection of X".                 |
| Mobile-only flow with swipe gestures (multi-step wizard)   | `Drawer`      | Justify: "mobile-only, gesture-driven".                                          |
| Quick info on hover (non-clickable)                        | `HoverCard`   |                                                                                  |
| Small contextual content on click (filter, picker compact) | `Popover`     | Prefer over `Dialog` only when tightly anchored to a trigger and < 3 fields.     |
| Contextual menu of actions                                 | `DropdownMenu` / `ContextMenu` | Not an overlay for content — for action lists.                      |

> Rule of thumb: if you typed `<Sheet`, ask "why not Dialog?". If the answer isn't "must stay visible while the user keeps working in the page behind it", switch to Dialog.

---

## Dialog, Sheet, and Drawer always need a Title

`DialogTitle`, `SheetTitle`, `DrawerTitle` are required for accessibility. Use `className="sr-only"` if visually hidden.

```tsx
<DialogContent>
    <DialogHeader>
        <DialogTitle>Edit Profile</DialogTitle>
        <DialogDescription>Update your profile.</DialogDescription>
    </DialogHeader>
    ...
</DialogContent>
```

---

## Card structure

Use full composition — don't dump everything into `CardContent`:

```tsx
<Card>
    <CardHeader>
        <CardTitle>Team Members</CardTitle>
        <CardDescription>Manage your team.</CardDescription>
    </CardHeader>
    <CardContent>...</CardContent>
    <CardFooter>
        <Button>Invite</Button>
    </CardFooter>
</Card>
```

---

## Button has no isPending or isLoading prop

Compose with `Spinner` + `data-icon` + `disabled`:

```tsx
<Button disabled>
    <Spinner data-icon="inline-start" />
    Saving...
</Button>
```

---

## TabsTrigger must be inside TabsList

Never render `TabsTrigger` directly inside `Tabs` — always wrap in `TabsList`:

```tsx
<Tabs defaultValue="account">
    <TabsList>
        <TabsTrigger value="account">Account</TabsTrigger>
        <TabsTrigger value="password">Password</TabsTrigger>
    </TabsList>
    <TabsContent value="account">...</TabsContent>
</Tabs>
```

---

## Avatar always needs AvatarFallback

Always include `AvatarFallback` for when the image fails to load:

```tsx
<Avatar>
    <AvatarImage src="/avatar.png" alt="User" />
    <AvatarFallback>JD</AvatarFallback>
</Avatar>
```

---

## Use existing components instead of custom markup

| Instead of                                         | Use                                  |
| -------------------------------------------------- | ------------------------------------ |
| `<hr>` or `<div className="border-t">`             | `<Separator />`                      |
| `<div className="animate-pulse">` with styled divs | `<Skeleton className="h-4 w-3/4" />` |
| `<span className="rounded-full bg-green-100 ...">` | `<Badge variant="secondary">`        |
