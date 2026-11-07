# Category Mapper

Maps a supplier's product categories onto your shop's category tree —
the boring, error-prone step of every catalog import, automated to a
review-ready Excel table.

Given a supplier price list (`csv`/`xlsx`) and the site category tree
(`csv`/`xlsx`/`txt`), it produces `mapping.xlsx`:

| supplier_category | proposed_site_category | score | alternatives |
|---|---|---|---|
| Кабели и переходники | Электроника / Кабели и переходники | 0.41 | … |

- **Fuzzy matching** — normalization (lowercase, `ё`→`е`, punctuation
  cleanup) + token overlap and `difflib` scoring, with a synonym table
  for common marketplace vocabulary (extends `SYNONYMS` in code).
- **Review-ready output** — rows sorted by confidence; low-score rows
  (`<0.5`) are the ones a human finishes by hand — that's exactly the
  "pass through the tree" work this tool cuts from hours to minutes.
- **Alternatives column** — runner-up categories with their scores, so
  the manual pass is a pick-list, not a search.
- Single file, `pandas` + `openpyxl` only.

## Quick start

```bash
pip install -r requirements.txt

python mapper.py --supplier supplier_price.xlsx --site shop_tree.xlsx
# -> mapping.xlsx
```

Try it on the bundled demo data (real output in `docs/demo_mapping.xlsx`):

```bash
python mapper.py --supplier docs/demo_supplier.xlsx --site docs/demo_site.xlsx
```

## Input formats

- `--supplier FILE` — supplier price list (`csv`/`xlsx`). The category
  column is auto-detected or set with `--sup-cat COL`.
- `--site FILE` — shop category tree (`csv`/`xlsx`/`txt`): either one line
  per path like `Электроника/Кабели`, or separate columns.
- `--out FILE` — output path (default `mapping.xlsx`).
- `--sup-cat COL`, `--site-cat COL` — explicit column names when
  auto-detection guesses wrong.

## License

MIT — see LICENSE.
