#!/usr/bin/env python3
"""Build data/terms.csv, data/sources.csv, data/evidence.csv, data/open_issues.csv
from the hand-checked table data/raw/terms_verified_v2_2026-11-12.csv.

Columns that v2 does not have (specialty, category, pos, term_type, in_skillbridge)
are taken from data/raw/terms_metadata_2026-11-11.csv.

One-off migration script: after it has been run, data/terms.csv is the single
source of truth and is edited by hand. Kept for reproducibility.
Standard library only.
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
V2 = RAW / "terms_verified_v2_2026-11-12.csv"
OLD = RAW / "terms_metadata_2026-11-11.csv"

COLUMNS = ["id", "specialty", "category", "en", "ru", "kk", "kk_variants", "kk_latn",
           "pos", "term_type", "source_kk", "status", "in_skillbridge",
           "definition_en", "definition_kk", "wikidata", "notes"]

# --------------------------------------------------------------------------- sources
# (id, type, title, author_or_org, year, language, url, notes, match prefix in v2)
SOURCES = [
    ("S01", "terminology_database", "Termincom: terminology database of the State Terminology Commission",
     "State Terminology Commission of RK", "", "ru;kk", "https://termincom.kz/",
     "Per-term search URLs and approval years are in evidence.csv.", "termincom.kz"),
    ("S02", "encyclopedia", "Kazakh Wikipedia", "Wikimedia", "", "kk", "https://kk.wikipedia.org/",
     "Hint only; never sufficient for status=verified.", "kk.wikipedia"),
    ("S03", "legal_act", "Unified requirements in the field of ICT and information security (Government Decree No. 832)",
     "Government of RK", "2016", "ru;kk", "https://adilet.zan.kz/", "Parallel RU/KK text; clause numbers in evidence.csv.",
     "adilet.zan.kz Единые требования в области ИКТ"),
    ("S04", "legal_act", "Safety rules for the operation of consumer electrical installations (Order of the Minister of Energy No. 222)",
     "Ministry of Energy of RK", "2015", "ru;kk", "https://adilet.zan.kz/kaz/docs/V1500010889",
     "Parallel RU/KK text; clause numbers in evidence.csv.", "adilet.zan.kz Правила ТБ"),
    ("S05", "legal_act", "Rules for the technical operation of consumer electrical installations (Order of the Minister of Energy No. 246)",
     "Ministry of Energy of RK", "2015", "ru;kk", "https://adilet.zan.kz/kaz/docs/V1500010949",
     "Parallel RU/KK text; clause numbers in evidence.csv.", "adilet.zan.kz Правила технической эксплуатации"),
    ("S06", "legal_act", "Sanitary rules: sanitary-epidemiological requirements for public catering facilities (Order No. ҚР ДСМ-16)",
     "Ministry of Healthcare of RK", "2022", "ru;kk", "https://adilet.zan.kz/kaz/docs/V2200026866",
     "Parallel RU/KK text; clause numbers in evidence.csv.", "adilet.zan.kz Санправила"),
    ("S07", "textbook", "Қоғамдық тамақтандыру (textbook)", "Күзембаев К., Күзембаева Г.К., Смағұлова А.Қ.", "",
     "kk", "", "Kazakh-language textbook; page numbers to be added.", "Күзембаев"),
    ("S08", "dictionary", "Multitran", "multitran.com", "", "en;ru;kk", "https://www.multitran.com/",
     "Used for EN–RU equivalence; not a Kazakh authority.", "multitran"),
    ("S09", "encyclopedia", "Russian Wikipedia", "Wikimedia", "", "ru", "https://ru.wikipedia.org/", "RU hint only.", "ru.wikipedia"),
    ("S10", "web", "culinaryschool.ru", "", "", "ru", "https://culinaryschool.ru/", "RU culinary usage.", "culinaryschool.ru"),
    ("S11", "web", "dpoprof.ru (cook training courses)", "", "", "ru", "https://dpoprof.ru/", "RU culinary usage.", "dpoprof.ru"),
    ("S12", "web", "getpelican.app", "", "", "ru", "https://getpelican.app/", "RU culinary usage.", "getpelican.app"),
    ("S13", "expert_record", "Electrical teacher E02, handwritten translations (2026-11-12)", "E02 (anonymised)", "2026",
     "kk", "", "Attests usage variants only; not a normative source. Photo kept privately.", None),
]
AUTHORITATIVE_KK = {"S01", "S03", "S04", "S05", "S06", "S07"}

# --------------------------------------------------------------------------- manual decisions
# Terms whose Kazakh form is NOT attested as a whole: only its parts are (v2 comments).
# Per the spec they stay `draft` until a source with the whole term or a subject teacher confirms them.
COMPONENT_ONLY = {
    "T0009": "act has «қолданбалы бағдарламалаудың стандартты интерфейстері», not this exact form",
    "T0013": "termincom «қолданысқа енгізу» = «введение в действие», not «развёртывание»",
    "T0016": "termincom has the longer «желіге қолжеткізуді бақылау (NAC)»",
    "T0021": "only «коммутатор» attested; «желілік» added",
    "T0031": "termincom has «программалық қамтымды жаңарту» (different wording)",
    "T0032": "only «ақауларды іздеу» and «ақаулықтарды жою» attested separately",
    "T0033": "act has «қол жеткізу құқықтары»; full phrase not attested",
    "T0059": "only «қысқыш» / «клеммник» attested as separate words",
    "T0065": "only «электр сымы» attested",
    "T0066": "«бүтіндік» attested in other phrases; full term not attested",
    "T0067": "termincom has «профилактикалық техникалық қызмет ету»",
    "T0070": "only «тоғыспалы» and «ластану» attested separately",
    "T0072": "only a sentence in S06 («температурасын бақылау»)",
    "T0078": "no single-word term; parts attested",
    "T0081": "termincom has «буға піскен…», not the process noun",
    "T0091": "only «безендіру» / «порцияланған және безендірілген» attested",
    "T0093": "termincom «аспаз пышағы» = «кухонный нож» (broader than chef's knife)",
    "T0094": "only «термометр» attested",
    "T0097": "only «шикі» and «ингредиент» attested separately",
}

# Variants attested in a source (v2 comments) or by teacher E02.
VARIANTS = {
    "T0002": ["деректер базасы", "деректер қоры"],
    "T0013": ["орналастыру"],
    "T0016": ["қолжетімді бақылау"],
    "T0017": ["аутентификация"],
    "T0020": ["маршруттауыш"],
    "T0022": ["аналық тақша"],
    "T0024": ["оперативтік жад"],
    "T0027": ["IP мекенжай"],
    "T0031": ["программалық қамтымды жаңарту"],
    "T0036": ["жеке қорғаныс құралдары"],
    "T0038": ["электр тогы соғуы", "электр тогынан зақымдану"],
    "T0043": ["асқын жүктелу", "артық жүктеме"],
    "T0044": ["электр тоғы"],
    "T0052": ["қорғауышты өшіру құрылғысы"],
    "T0055": ["электрқозғалтқыш"],
    "T0057": ["түйістіргіш"],
    "T0059": ["қысқыштар блогы"],
    "T0061": ["кернеу индикаторы"],
    "T0064": ["кәбіл"],
    "T0067": ["профилактикалық техникалық қызмет ету"],
    "T0068": ["азық-түліктердің қауіпсіздігі"],
    "T0075": ["санитарлық өңдеу"],
    "T0077": ["ХАССП"],
    "T0089": ["еріту"],
    "T0099": ["ресеп"],
}
VARIANT_FROM_E02 = {("T0036", "жеке қорғаныс құралдары"), ("T0043", "артық жүктеме")}

# Main form chosen when v2 has "term (other)" in one cell.
SPLIT_MAIN = {"T0017": "сәйкестендірме", "T0059": "клеммник",
              "T0077": "қауіпті факторларды және бақылаудың сындарлы нүктелерін талдау"}
RU_FIX = {"T0077": "анализ опасных факторов и критические точки контроля"}

# term_type re-annotated after the Kazakh form changed (proposed; to be confirmed by the author).
TERM_TYPE_FIX = {
    "T0011": ("calque", "native", "оңдау: Kazakh stem, does not mirror «отладка»"),
    "T0017": ("borrowing", "native", "сәйкестендірме: Kazakh derivation from сәйкес"),
    "T0020": ("borrowing", "native", "бағдарғылауыш: neologism from бағдар, no foreign model"),
    "T0059": ("hybrid", "borrowing", "клеммник: borrowed as a whole"),
    "T0076": ("borrowing", "calque", "залал-сыз-дандыру mirrors обез-зараж-ивание"),
    "T0086": ("native", "hybrid", "фермент (borrowed) + -те (Kazakh verbal suffix)"),
    "T0090": ("native", "hybrid", "порция (borrowed) + -ла (Kazakh verbal suffix)"),
    # consistency with rule 1 (borrowed stem + Kazakh derivational suffix), cf. маринадтау = hybrid
    "T0012": ("borrowing", "hybrid", "тест (borrowed) + -іле (Kazakh verbal suffix), like маринадтау"),
    "T0087": ("borrowing", "hybrid", "пастер (borrowed) + -ле (Kazakh verbal suffix), like маринадтау"),
}

# IT reviewer disagreements with the v2 form (screenshot 2026-11-12). Not applied: author decides.
IT_REVIEW = {
    "T0009": "reviewer suggests «қолданбалы бағдарламалау интерфейсі (API)»",
    "T0011": "reviewer: «оңдау» too general; suggests «қателерді түзету»",
    "T0013": "reviewer suggests checking «өрістету» in Termincom",
    "T0017": "reviewer: «сәйкестендіру» = identification; suggests «түпнұсқалықты растау»",
    "T0020": "reviewer: «бағдарғылауыш» rarely used; suggests «маршрутизатор (роутер)»",
    "T0025": "reviewer: «жинауыш» unfortunate; suggests «қатты денелі жинақтағыш (SSD)»",
    "T0033": "reviewer prefers «пайдаланушы құқықтары» (A2 form)",
}


def lower_first(s):
    """Lowercase the first letter unless the first word is an abbreviation (IP, SSD, ХАССП)."""
    s = " ".join(s.split())
    if not s:
        return s
    if len(s) > 1 and s[1].isupper():  # IP мекенжайы, IP-адрес, ХАССП
        return s
    return s[0].lower() + s[1:]


def strip_paren(s):
    return re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()


def parse_sources(cell):
    """'name: url; name: url' -> [(source_id, locator, url)]"""
    out = []
    starts = "|".join(re.escape(s[8].split()[0]) for s in SOURCES if s[8])
    for seg in re.split(rf";\s*(?=(?:{starts}))", cell):
        seg = seg.strip()
        if not seg:
            continue
        m = re.match(r"(.*?):\s*(https?://\S+)\s*$", seg)
        name, url = (m.group(1).strip(), m.group(2)) if m else (seg, "")
        sid = next((s[0] for s in SOURCES if s[8] and name.startswith(s[8])), None)
        if sid is None:
            raise ValueError(f"unknown source: {name!r}")
        loc = ""
        lm = re.search(r"п\.\s*([^()]*?(?:\([^)]*\))?)\s*\(рус", name) or re.search(r"п\.(.*)$", name)
        if sid in {"S03", "S04", "S05", "S06"} and lm:
            loc = "п." + lm.group(1).strip()
        out.append((sid, loc, url))
    return out


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(path, fieldnames, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main():
    v2 = {r["ID"]: r for r in read(V2)}
    old = read(OLD)
    terms, evidence, issues = [], [], []

    for o in old:
        tid = o["id"]
        r = v2[tid]
        kk_raw = " ".join(r["Қазақша (итог)"].split())
        kk = SPLIT_MAIN.get(tid) or lower_first(strip_paren(kk_raw))
        ru = RU_FIX.get(tid) or lower_first(r["Русский (итог)"])

        variants = [v for v in VARIANTS.get(tid, []) if v != kk]

        kk_src = parse_sources(r["Источник KK"])
        ru_src = parse_sources(r["Источник RU"]) if r["Источник RU"].strip() else []
        for lang, items in (("kk", kk_src), ("ru", ru_src)):
            for sid, loc, url in items:
                evidence.append({"id": tid, "lang": lang, "source_id": sid, "locator": loc, "url": url})
        for v in variants:
            if (tid, v) in VARIANT_FROM_E02:
                evidence.append({"id": tid, "lang": "kk_variant", "source_id": "S13", "locator": v, "url": ""})

        ids = []
        for sid, _, _ in kk_src:
            if sid in AUTHORITATIVE_KK and sid not in ids:
                ids.append(sid)

        if tid in COMPONENT_ONLY:
            status = "draft"
            ev = "component-only: " + COMPONENT_ONLY[tid]
        elif ids:
            status = "verified"
            ev = "whole term attested"
        else:
            status = "draft"
            ev = "no authoritative KK source"

        term_type = o["term_type"]
        if tid in TERM_TYPE_FIX:
            before, after, why = TERM_TYPE_FIX[tid]
            assert term_type == before, (tid, term_type, before)
            term_type = after
            issues.append({"id": tid, "kind": "term_type_changed",
                           "detail": f"{before} -> {after}: {why}", "action": "confirm type"})

        notes = [ev, "v2: " + r["Комментарий"].strip()]
        if tid == "T0077":
            notes.append("RU/KK abbreviation: ХАССП")
        terms.append({
            "id": tid, "specialty": o["specialty"], "category": o["category"],
            "en": lower_first(o["en"]).replace("’", "'"), "ru": ru, "kk": kk,
            "kk_variants": ";".join(variants), "kk_latn": "", "pos": o["pos"],
            "term_type": term_type, "source_kk": ";".join(ids), "status": status,
            "in_skillbridge": o["in_skillbridge"], "definition_en": "", "definition_kk": "",
            "wikidata": "", "notes": " | ".join(notes),
        })

        if tid in IT_REVIEW:
            issues.append({"id": tid, "kind": "it_reviewer_disagrees", "detail": IT_REVIEW[tid],
                           "action": "decide main form / add variant; confirm reviewer is a human teacher"})
        if tid in COMPONENT_ONLY:
            issues.append({"id": tid, "kind": "component_only_draft", "detail": COMPONENT_ONLY[tid],
                           "action": "find whole-term source or get teacher confirmation"})

    write(ROOT / "data" / "terms.csv", COLUMNS, terms)
    write(ROOT / "data" / "evidence.csv", ["id", "lang", "source_id", "locator", "url"], evidence)
    write(ROOT / "data" / "sources.csv",
          ["id", "type", "title", "author_or_org", "year", "language", "url", "access_date", "notes"],
          [{"id": s[0], "type": s[1], "title": s[2], "author_or_org": s[3], "year": s[4],
            "language": s[5], "url": s[6], "access_date": "2026-11-12", "notes": s[7]} for s in SOURCES])
    issues.sort(key=lambda x: (x["kind"], x["id"]))
    write(ROOT / "data" / "open_issues.csv", ["id", "kind", "detail", "action"], issues)

    by = lambda k: {v: sum(t[k] == v for t in terms) for v in sorted({t[k] for t in terms})}
    print(len(terms), "terms;", by("status"), by("term_type"))
    print(len(evidence), "evidence rows;", len(issues), "open issues")


if __name__ == "__main__":
    main()
