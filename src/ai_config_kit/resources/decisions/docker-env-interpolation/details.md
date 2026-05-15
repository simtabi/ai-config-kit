# docker-env-interpolation

Ships a Python script that flattens one or more `.env` files into a
single fully-interpolated file. Handles `${VAR}`, `${VAR:-default}`,
and `${VAR:?required}` syntax. Reads the precedence chain Docker
Compose uses (shell env > later .env > earlier .env > defaults), so
the output matches what Docker would resolve at runtime.

## Why this exists

Docker Compose **does** interpolate `${VAR}` inside `.env` files now
(per <https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/>),
so simple cases work natively. The script is for:

- **Non-Docker tools that read `.env`**: many CI shells, older
  deployment tools, raw `env $(cat .env)` patterns, language-
  specific dotenv libs that don't interpolate.
- **Cross-file resolution**: combine `.env`, `.env.local`,
  `.env.production` with the right precedence and emit one flat file.
- **Validation**: catch unresolved references before deploy. Refuse
  to write the output if any `${VAR}` is left unresolved.
- **Rendering `.env.example` → `.env`** with sensible defaults filled in.
- **Auditing what Docker would actually see**: the resolved file is
  what every consumer ends up reading; compare to the source to spot
  surprises.

## What ships

| File | Purpose |
|---|---|
| `scripts/render-env.sh` | The interpolator. Stdlib only. Takes `--input`, `--local`, `--example`, `--strict`. Writes to stdout or `--output`. |
| `CLAUDE.md.docker-env-interpolation.fragment` | When to use it, how to wire into your Dockerfile / compose / CI. |
| `commands/render-env.md` | `/render-env` slash command that walks the user through running it. |

## Apply

Auto-applied on `ai-config-kit init`. The script lands at
`~/.claude/scripts/render-env.sh` (via the content-dir symlink).

To use in a project, either:

**Reference the global script**:

```bash
~/.claude/scripts/render-env.sh --input .env --output .env.resolved
```

**Or vendor it into the project**:

```bash
cp ~/.claude/scripts/render-env.sh scripts/
# commit to the project; teammates use the project copy
```
