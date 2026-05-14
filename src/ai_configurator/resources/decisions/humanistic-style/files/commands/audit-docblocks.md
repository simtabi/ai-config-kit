---
description: Audit code doc-blocks for the right format per language (PHPDoc / JSDoc / Sphinx). Flag missing or wrong-format blocks.
argument-hint: <path-or-glob>
---

Audit the doc-blocks on public-API surfaces at $1. Default scope:
the current project. Languages covered: Python (Sphinx/reST), PHP
(PHPDoc), JavaScript / TypeScript (JSDoc).

### Step 1: Detect language(s)

```bash
ls *.py composer.json package.json *.php 2>/dev/null
find . -maxdepth 2 -name "*.py" -o -name "*.ts" -o -name "*.tsx" \
       -o -name "*.js" -o -name "*.php" 2>/dev/null | head -5
```

If a project has mixed languages, audit each separately.

### Step 2: Find public API surfaces

**Python**: top-level `def` / `class` in files not starting with `_`,
plus methods on classes not starting with `_`.

```bash
grep -n -E "^(def |class |    def )" src/**/*.py | grep -v "    def _"
```

**PHP / Laravel**: `public function` / `public static function` /
`public class`.

```bash
grep -n -E "public (function|static function|class)" app/**/*.php
```

**JS / TS**: `export function`, `export class`, `export const ... = `,
public methods (not prefixed `_`).

```bash
grep -n -E "^export (function|class|const|interface)" src/**/*.{ts,tsx}
```

### Step 3: Audit format

For each public symbol, check whether a doc-block precedes it. If
present, check the format matches the language:

**Python — Sphinx**:
```python
"""One-line summary.

:param name: Description.
:returns: Description.
:raises ExceptionType: Description.
"""
```

**PHP — PHPDoc**:
```php
/**
 * One-line summary.
 *
 * @param  Type  $name  Description.
 * @return Type
 * @throws ExceptionType
 */
```

**JS / TS — JSDoc**:
```typescript
/**
 * One-line summary.
 *
 * @param name - Description.
 * @returns Description.
 * @throws {ExceptionType} Description.
 */
```

### Step 4: Banned doc-block content

Flag doc-blocks that:

- Restate the function name as prose ("This function does X")
- Include "Note:", "Important:", "Please note"
- Describe what the type signature already says
- Are missing `@throws` / `:raises:` for known exceptions

### Step 5: Report

```
| File | Line | Symbol | Finding | Severity |
|---|---|---|---|---|
| src/api/users.py | 24 | get_user | missing :raises: for UserNotFound | medium |
| src/api/users.py | 60 | _internal | private symbol; doc-block not required | info |
| app/Models/User.php | 12 | profile | missing @return type | high |
```

### Step 6: Do not edit

Stop after the report. The user picks which doc-blocks to fix and
the format. Add doc-blocks AFTER they confirm.

Cite paths as `path:line` everywhere.
