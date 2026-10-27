# Contributing

Thanks for looking. Tiroir stays small on purpose: standard library only on the server, plain JavaScript in the browser, no build step.

1. Open an issue first for anything bigger than a fix, so we agree on the idea before you write code.
2. `pip install -e ".[dev]" pytest-cov`, then make your change with a test.
3. `ruff check src tests` and `pytest --cov=tiroir` must pass (coverage stays above 80 %).
4. Interface text is written in French and translated in `src/tiroir/static/i18n.js`: wrap new strings with `T('...')` and add the English line.
5. Keep the cabinet metaphor: drawers, tabs, wall. No columns, no database, no external request.

Good first issues are labelled `good first issue`.
