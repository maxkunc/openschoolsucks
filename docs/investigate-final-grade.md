# Investigate is.psjg.cz: the subjects table's "final grade" column

You (Claude in Chrome) have something the dev session doesn't: a real,
logged-in browser session on **is.psjg.cz**. The dev session works on
`maxkunc/openschoolsucks` (a Flask backend that scrapes this site) and
`maxkunc/ispsjginjs` (its React frontend) from a sandbox that cannot reach
is.psjg.cz at all - scraping code here has always been written blind and
verified only by inspection sessions like this one.

**The ask:** the site's main dashboard page has a subjects table (headed
"Předmět") with several columns, one of which is the running/current grade
and another which is (allegedly) the *final* grade - the one that ends up
on the report card / diploma ("vysvědčení"). The backend already scrapes
*something* into a field called `finalGrade`, but it does so by raw column
**position**, never by matching the actual header text - so nobody has ever
confirmed it's grabbing the right column, or that it reliably has a value.
Your job: look at the real table and settle that.

## Before you start

- Log into is.psjg.cz normally in this browser if not already.
- Use DevTools (F12 or right-click → Inspect) - Elements tab for markup.
- **Never paste your password anywhere in your findings.** Grades/subject
  names are fine to include, or redact them if you'd rather - the goal is
  the table's *structure* (headers, column order, what's empty vs filled),
  not your specific grades.

## What the current code assumes (unverified)

On the site's homepage/dashboard, right after login, there's a `<table>`
whose first header cell (`<th>`) reads exactly `Předmět`. The code finds
that table, then for each subject row reads exactly 4 data cells (`<td>`)
in this assumed order:

| index | assumed content | example |
|---|---|---|
| 0 | subject name (a link, its `href` has `?subjectId=...`) | `Matematika` |
| 1 | combined points/percentage text | `89,0 / 97,0 (91,75%)` |
| 2 | current/running grade | `Známka` column, e.g. `2` |
| 3 | **final grade** (assumed) | `Výsledná známka` column, e.g. `1` |

Cell 3 is what gets exposed to the frontend as `finalGrade`. This has never
been checked against the real table - it might be right, might be off by a
column, or might be reliably empty until some point in the term.

## Task: confirm the subjects table's real structure

1. Go to the site's homepage/dashboard where the subjects table with
   header "Předmět" appears.
2. Right-click the table's **header row** → Inspect. Copy the full row of
   `<th>` cells in order (View Page Source / Ctrl+F for "Předmět" also
   works if DevTools feels slower) - I need every column header's exact
   Czech text, in order, e.g. `Předmět | Bodové hodnocení | Známka |
   Výsledná známka | ...` (there may be more or fewer columns than that,
   or a different order).
3. Pick one subject row and Inspect its full `<tr>` - copy the HTML for
   all of its `<td>` cells (values can be real or "REDACTED", I just need
   the structure and which cell holds what).
4. Identify which column is genuinely **the grade that ends up on your
   report card / vysvědčení** for that subject - if you know which one
   that is from using the site, say so directly. If more than one column
   could plausibly be "the final grade" (e.g. a running grade *and* a
   separate official term grade), describe the difference between them.
5. Check a subject where the term/grading period isn't finished yet
   (recently-added subject, or just early in a term) if you have one -
   what does that column show when there's no final grade yet? Empty
   string? A dash `-`? Not rendered at all (row shorter than expected)?
6. Check whether this differs between the two semesters (pololetí) - e.g.
   does semester 1 ever have a genuine "final" grade, or does that concept
   only really apply to semester 2 / end of year? Switch semesters with
   the dropdown near the top and re-check the table if useful.
7. If there's a **separate dedicated page** for the official report card /
   vysvědčení (distinct from this dashboard table) - check the site's
   navigation for anything like "Vysvědčení" - note its URL and what it
   shows, since that might be the more authoritative source for "grade
   that appears on the diploma" rather than this table.

**Report back:**
- The full header row, in order, exact Czech text
- Which column index (0-based, counting only `<td>`, not counting any
  hidden/id-only cells) is truly the final/report-card grade
- An HTML snippet of one full `<tr>` (values redacted is fine) showing the
  cell structure
- What an "unfinalized" cell looks like (empty/dash/absent), if you found
  one
- Whether semester switching changes any of this
- Whether a separate "Vysvědčení" page/URL exists and what it shows

---

## How to hand this back

Reply with your findings in this shape so they're easy to act on:

```
### Subjects table header row
<full ordered list of <th> text>

### Column that's the real final/report-card grade
<index + column header text>

### Example row HTML
<snippet>

### Unfinalized value
<what it looks like, or "didn't have an example">

### Semester differences
<what you found>

### Separate Vysvědčení page
<URL + notes, or "doesn't exist">
```

Paste that back into the conversation with the person who gave you this
file - they'll relay it to the dev session working on this repo.
