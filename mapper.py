"""mapper.py — сопоставление категорий поставщика → категорий сайта.

Вход:
  --supplier FILE   прайс поставщика (csv/xlsx), колонка категории определяется
                    автоматически или через --sup-cat COL
  --site FILE       дерево категорий магазина (csv/xlsx/txt, одна строка = путь
                    вида "Главная/Подкатегория" или отдельные колонки)
Выход:
  mapping.xlsx — таблица: категория_поставщика | предложенная_категория_сайта |
                 score | альтернативы
Логика: нормализация (нижний регистр, ё→е, мусор) + токен-совпадение
(difflib + пересечение слов). Человек дожимает спорные строки вручную —
это и есть "проход по дереву", который продаём заказчику.
"""
import argparse
import difflib
import re
import sys

import pandas as pd


def norm(s):
    s = str(s).lower().replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9 ]", " ", s)


# синонимы/роды — расширяют токены перед сравнением
SYNONYMS = {
    "кабели": ["переходники", "провода"],
    "адаптеры": ["переходники"],
    "hdmi": ["переходники", "кабели"],
    "usb": ["переходники", "кабели"],
    "чехлы": ["аксессуары", "телефонов", "смартфонов"],
    "чехол": ["аксессуары", "телефонов"],
    "наушники": ["аудио"],
    "гарнитуры": ["аудио"],
    "колонки": ["аудио"],
    "мыши": ["периферия", "компьютеры"],
    "мышь": ["периферия", "компьютеры"],
    "клавиатуры": ["периферия", "компьютеры"],
    "картриджи": ["периферия", "расходники"],
    "тонер": ["периферия", "расходники"],
    "ssd": ["накопители", "компьютеры"],
    "накопители": ["компьютеры"],
    "фильтры": ["сетевое", "оборудование"],
    "сетевые": ["сетевое", "оборудование"],
    "держатели": ["держатели", "крепления"],
    "автомобильные": ["авто", "держатели", "крепления"],
    "бумага": ["бумажная", "продукция"],
    "блокноты": ["бумажная", "продукция"],
    "ежедневники": ["бумажная", "продукция"],
    "ручки": ["письменные", "принадлежности"],
    "степлеры": ["письменные", "принадлежности"],
    "смартфонов": ["телефонов", "аксессуары"],
    "аксессуары": ["аксессуары"],
}


def base_tokens(s):
    return {w for w in norm(s).split() if len(w) > 2}


def expand(ts):
    out = set(ts)
    for w in ts:
        out.update(SYNONYMS.get(w, ()))
    return out


# простой стеммер: режем типовые русские окончания, чтобы
# «ручки»/«ручка», «наушники»/«наушник» считались одним словом
_ENDINGS = ("иями", "ями", "ами", "ией", "ий", "ый", "ой", "ая", "яя",
            "ые", "ие", "ое", "ее", "ы", "и", "а", "я", "о", "е",
            "у", "ю", "ем", "ом")


def stem(w):
    for e in _ENDINGS:
        if w.endswith(e) and len(w) - len(e) >= 3:
            return w[:-len(e)]
    return w


def _match(ta, tb):
    """токен совпал с множеством: точно, по стему или fuzzy (>=0.8)"""
    if ta in tb or stem(ta) in {stem(t) for t in tb}:
        return True
    return any(difflib.SequenceMatcher(None, ta, t).ratio() >= 0.8
               for t in tb)


def score(a, b):
    ta_base, tb_base = base_tokens(a), base_tokens(b)
    ta_exp, tb_exp = expand(ta_base), expand(tb_base)
    # покрытие: сколько базовых токенов поставщика нашли пару на сайте
    # (синонимы работают мостом в обе стороны)
    cov = sum(1 for t in ta_base
              if _match(t, tb_exp) or _match(t, tb_base)
              or any(_match(s, tb_base | tb_exp)
                     for s in SYNONYMS.get(t, ()))) / max(1, len(ta_base))
    # jaccard по расширенным множествам (пересечение «в лоб»)
    inter = len(ta_exp & tb_exp)
    jacc = inter / max(1, len(ta_exp | tb_exp))
    seq = difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()
    return round(0.5 * cov + 0.3 * jacc + 0.2 * seq, 3)


def read_table(path):
    if str(path).lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path, dtype=str)
    for enc in ("utf-8", "cp1251", "utf-8-sig"):
        try:
            return pd.read_csv(path, dtype=str, encoding=enc,
                               sep=None, engine="python")
        except Exception:
            continue
    raise SystemExit(f"не читается {path}")


def supplier_cats(path, col=None):
    df = read_table(path)
    if col and col in df.columns:
        ser = df[col]
    else:
        # эвристика: колонка со словом категор/раздел/групп
        cand = [c for c in df.columns
                if re.search(r"категор|раздел|групп|section|categor", str(c),
                             re.I)]
        ser = df[cand[0]] if cand else df.iloc[:, 0]
    cats = []
    for v in ser.dropna():
        # «путь/через/слэш» берём целиком и листовой элемент отдельно
        v = str(v).strip()
        if v and v not in cats:
            cats.append(v)
    return cats


def site_cats(path):
    df = read_table(path)
    cats = []
    for _, row in df.iterrows():
        vals = [str(v).strip() for v in row if pd.notna(v) and str(v).strip()]
        if vals:
            cats.append(" / ".join(vals))
    return cats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--supplier", required=True)
    ap.add_argument("--site", required=True)
    ap.add_argument("--sup-cat")
    ap.add_argument("--out", default="mapping.xlsx")
    a = ap.parse_args()

    sup = supplier_cats(a.supplier, a.sup_cat)
    site = site_cats(a.site)
    print(f"категорий поставщика: {len(sup)}, сайта: {len(site)}")

    rows = []
    for s in sup:
        scored = sorted(((score(s, c), c) for c in site), reverse=True)
        best = scored[0] if scored else (0, "")
        alts = "; ".join(f"{c} ({sc})" for sc, c in scored[1:4])
        rows.append({"категория_поставщика": s,
                     "предложенная_категория_сайта": best[1],
                     "score": best[0],
                     "альтернативы": alts})
    out = pd.DataFrame(rows).sort_values("score")
    out.to_excel(a.out, index=False)
    print(f"→ {a.out}: {len(out)} строк "
          f"(score<0.5 требуют ручной проверки: "
          f"{(out.score < 0.5).sum()})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
