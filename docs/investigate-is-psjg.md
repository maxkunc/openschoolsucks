# Investigate is.psjg.cz: student name + Zkoušení

You (Claude in Chrome) have something the developer session doesn't: a real,
logged-in browser session on **is.psjg.cz**. The dev session works on
`maxkunc/openschoolsucks` (a Flask backend that scrapes this site) and
`maxkunc/ispsjginjs` (its React frontend) from a sandbox that cannot reach
is.psjg.cz at all - every piece of scraping code so far has been written
blind, verified only by asking the site's owner to test it live. Two things
are currently wrong because of that:

1. **Student name** shows "studentské portfolio" (a generic UI label) instead
   of the real name - the current code guesses wrong.
2. **Zkoušení** (oral exam tracking) was never implemented, ever, upstream or
   here - nobody has looked at what that page actually contains.

Your job: inspect the real pages and report back exact findings (HTML
snippets, URLs, request/response shapes) precise enough that the dev session
can write correct scraping code from them - not more guessing.

## Before you start

- Log into is.psjg.cz normally in this browser if not already.
- Use DevTools (F12 or right-click → Inspect) - Elements tab for markup,
  Network tab (filter: Fetch/XHR) for requests.
- **Never paste your password anywhere in your findings.** Your name and
  grades are fine to include (or redact if you'd rather - the goal is the
  HTML/URL *structure*, not the specific values).

## Existing pattern worth knowing

This site (built with the Nette PHP framework) exposes data through
components with predictable IDs and export links, e.g. the grades page
uses a component called `studentScoreGrid` and its CSV export is reached via
a URL query string `?studentScoreGrid-id=1&do=studentScoreGrid-export`.
Other working endpoints follow the same shape:
`achievement/view/<studentId>`, `student/student-exam-overview` with
`studentExamOverview-examGrid-id=1&do=studentExamOverview-examGrid-export`.
**Zkoušení likely follows this exact same pattern** - look for a similarly
named grid/component id and an `-export` link (often a small Excel/CSV/print
icon near a table).

---

## Task 1: Find the real student name

The current code guesses the name from two places, both apparently wrong:
the text of the link that goes to the portfolio page (titled "Téma
studentského portfolia" in the HTML), and the `<title>` tag. Both seem to
just contain generic labels, not a personal name.

1. On the site's homepage/dashboard (right after logging in), look at where
   *your actual name* is genuinely displayed - top navbar, a "Vítejte, ..."
   welcome line, a profile/account dropdown, a sidebar, anywhere.
2. Right-click directly on that name text → **Inspect**.
3. In the Elements panel, copy the HTML for that element and 2-3 parent
   levels up (so the surrounding structure/classes are visible).
4. Also open **View Page Source** (Ctrl+U / Cmd+Option+U) and search
   (Ctrl+F in the source view) for your name to confirm it's present in the
   raw server-rendered HTML (not injected by JS afterward) - the backend
   only ever sees this raw HTML, not anything JS adds later.
5. Note whether the same markup/name also appears on other pages (grades,
   portfolio, exam overview) or only on the homepage.

**Report back:**
- The exact tag, id, and/or class of the element containing the name (e.g.
  `<span class="user-name" id="...">`)
- A short HTML snippet (with real name or "REDACTED", your choice) showing
  that element plus its immediate parents
- Whether it's present in raw page source or only added by JavaScript

## Task 2: Find how Zkoušení actually works

1. Find "Zkoušení" in the site's navigation and click into it.
2. Copy the **exact URL** from the address bar (including any query
   string).
3. Look at what's actually shown: a table of past/upcoming oral exams? A
   calendar? A per-subject list? Note the columns/fields for each entry
   (e.g. date, subject, teacher, topic, result/grade).
4. Look for an export icon/link near that table (Excel/CSV/print/download -
   often small icons in a table's corner). If present:
   - Click it, and copy the resulting URL from the address bar or from the
     Network tab request that fired
   - Note the response's format (CSV? Check the column headers) and one
     example row (redact personal details if you'd rather, just keep the
     shape - e.g. `Datum;Předmět;Téma;Výsledek`)
5. Check whether the page respects the semester switcher (the same
   `<select id="frm-switchSemester-semester">` used elsewhere) - does
   switching semester change what Zkoušení shows? Does the URL gain a
   `semesterId` param when you do?
6. If there's a per-subject drill-down (like grades has - clicking a
   subject shows just that subject's exams), note that URL pattern too.
7. If there's nothing there at all (empty page, "no data", feature not
   really used by your school) - that's a valid, useful finding too. Say so.

**Report back:**
- The exact URL(s) for the main Zkoušení page (and any per-subject or
  export variants)
- What query parameters it accepts (semesterId? subjectId? something else?)
- The table's columns / an example of the exported CSV's header row
- Whether switching semester affects it

---

## How to hand this back

Reply with your findings in this shape so they're easy to act on:

```
### Student name
<what you found>

### Zkoušení
<what you found>
```

Paste that back into the conversation with the person who gave you this
file - they'll relay it to the dev session working on this repo.
