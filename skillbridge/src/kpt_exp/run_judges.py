"""Send every (answer, reference condition, repeat) to a judge and log the raw responses.

- One request per answer; versions of the same item are never sent together.
- Request order is shuffled with a recorded seed.
- Every response (including failures) is appended to runs/<judge>/<run_name>.jsonl with the
  prompt and input hashes, settings, SDK version, request id and the full raw response.
- A request already present with status ok/parse_failed is not sent again, so an interrupted
  run can simply be restarted. Requests that ended in api_error are retried on restart.

Usage:
  python -m kpt_exp.run_judges --provider sim --model sim-null --run pilot_sim --repeats 5
  python -m kpt_exp.run_judges --provider anthropic --model claude-haiku-4-5-20251001 --run main --repeats 5
  python -m kpt_exp.run_judges --provider gemini --model gemini-3.8-flash --run main --repeats 5
  python -m kpt_exp.run_judges --provider openai_compat --model sherkala-8b --run main --repeats 5
Add --limit N for a smoke test on the first N requests.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import random
import re
import sys
import time

from . import BUILD, ITEMS, PROMPT, REF_CONDITIONS, RUNS, SEED, TERMS
from . import simulate

KEYS = ["relevance_1to5", "correctness_1to5", "completeness_1to5", "terminology_1to5", "overall_1to5",
        "addressed_essential_points", "missed_essential_points", "evidence"]
SCORE_KEYS = KEYS[:5]
MAX_ATTEMPTS = 3
TEMPERATURE = 0.0
MAX_TOKENS = 1024
FENCE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.S)


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


# ---------------------------------------------------------------- prompts
def load_prompt():
    blocks = re.findall(r"```text\n(.*?)```", PROMPT.read_text(encoding="utf-8"), re.S)
    return blocks[0].strip(), blocks[1].strip()


def load_inputs():
    with open(ITEMS, encoding="utf-8") as f:
        items = {it["item_id"]: it for it in json.load(f)["items"]}
    with open(TERMS, encoding="utf-8") as f:
        terms = {r["id"]: r for r in csv.DictReader(f)}
    stim_path = BUILD / "stimuli.csv"
    if not stim_path.exists():
        sys.exit("build/stimuli.csv is missing: run `make stimuli` first.")
    with open(stim_path, encoding="utf-8") as f:
        stimuli = list(csv.DictReader(f))
    return items, terms, stimuli


def glossary_forms(item, term_row):
    forms = {term_row["kk"], item["official"]}
    forms.update(v.strip() for v in (term_row.get("kk_variants") or "").split(";") if v.strip())
    return sorted(forms)


def render_user(tpl, item, term_row, ref, answer):
    if ref == "R_EN":
        question, points, gloss = item["question_en"], item["ref_en"], ""
    else:
        question = item["question_kk"]
        points = [p.replace("{OFF}", item["official"]) for p in item["ref_kk"]]
        gloss = ""
        if ref == "R_KK_GLOSS":
            gloss = ("accepted_term_variants (all are correct; separated by |): "
                     + " | ".join(glossary_forms(item, term_row)) + "\n")
    vals = {"question_id": item["item_id"], "question": question,
            "reference_points": " | ".join(f"{i}. {p}" for i, p in enumerate(points, 1)),
            "essential_points": ";".join(map(str, item["essential"])),
            "glossary_line": gloss, "student_answer": answer}
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(vals[m.group(1)]), tpl)


# ---------------------------------------------------------------- validation
def validate(obj, essential):
    if not isinstance(obj, dict) or set(obj) != set(KEYS):
        return "keys"
    for k in SCORE_KEYS:
        v = obj[k]
        if not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 5:
            return k
    ad, mi = obj["addressed_essential_points"], obj["missed_essential_points"]
    if not isinstance(ad, list) or not isinstance(mi, list):
        return "points_type"
    if not all(isinstance(x, int) and not isinstance(x, bool) for x in ad + mi):
        return "points_type"
    if len(set(ad)) != len(ad) or len(set(mi)) != len(mi):
        return "points_duplicate"
    if set(ad) & set(mi) or set(ad) | set(mi) != set(essential):
        return "points_partition"
    if not isinstance(obj["evidence"], str) or not obj["evidence"].strip():
        return "evidence"
    return None


def parse(text, essential):
    m = FENCE.fullmatch(text.strip())   # only one ```json ... ``` wrapper is removed
    try:
        obj = json.loads(m.group(1) if m else text)
    except (json.JSONDecodeError, TypeError):
        return None, "json"
    return obj, validate(obj, essential)


# ---------------------------------------------------------------- providers
class Sim:
    """Simulated judge (no API). Model name `sim-null` = no effects; `sim-effect` = known effects."""
    name, sdk = "simulated", "none"
    PRESETS = {
        "sim-null": {},
        "sim-effect": {"penalty": {"R_EN": 0.1, "R_KK": 0.5, "R_KK_GLOSS": 0.15}},
    }

    def __init__(self, model):
        if model not in self.PRESETS:
            sys.exit(f"unknown simulated model {model}; choose from {list(self.PRESETS)}")
        self.model = model
        self.params = json.loads(json.dumps(simulate.DEFAULT))
        self.params.update(self.PRESETS[model])
        self.ctx = None

    def settings(self):
        return {"simulated": True, "params": self.params}

    def call(self, system, user):
        c = self.ctx
        obj = simulate.judge_response(c["item_id"], c["quality"], c["term_form"], c["ref"], c["rep"],
                                      c["n_points"], c["essential"], self.params, seed=SEED)
        return json.dumps(obj, ensure_ascii=False), "sim", self.model, {"simulated": True}


class Anthropic:
    name = "anthropic"
    # temperature 0 is sent with the API version used in the earlier study (see its PREREGISTRATION §4)
    API_VERSION = "2023-06-01"

    def __init__(self, model):
        import anthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("ANTHROPIC_API_KEY is not set.")
        self.client, self.model, self.sdk = anthropic.Anthropic(), model, anthropic.__version__

    def settings(self):
        return {"temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
                "anthropic_version": self.API_VERSION, "sdk": f"anthropic {self.sdk}"}

    def call(self, system, user):
        r = self.client.messages.create(model=self.model, system=system, max_tokens=MAX_TOKENS,
                                        messages=[{"role": "user", "content": user}],
                                        extra_body={"temperature": TEMPERATURE},
                                        extra_headers={"anthropic-version": self.API_VERSION})
        text = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        return text, r.id, r.model, r.model_dump(mode="json")


class Gemini:
    name = "google_gemini"

    def __init__(self, model):
        from google import genai
        from google.genai import types
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            sys.exit("GEMINI_API_KEY is not set.")
        self.client, self.types, self.model = genai.Client(api_key=key), types, model
        self.sdk = getattr(genai, "__version__", "unknown")

    def settings(self):
        return {"temperature_sent": TEMPERATURE, "temperature_note": "ignored by Gemini 3.6+",
                "max_output_tokens": 8192, "seed": SEED, "response_mime_type": "application/json",
                "sdk": f"google-genai {self.sdk}"}

    def call(self, system, user):
        cfg = self.types.GenerateContentConfig(system_instruction=system, temperature=TEMPERATURE,
                                               max_output_tokens=8192, seed=SEED,
                                               response_mime_type="application/json")
        r = self.client.models.generate_content(model=self.model, contents=user, config=cfg)
        raw = r.model_dump(mode="json") if hasattr(r, "model_dump") else str(r)
        return (r.text or ""), getattr(r, "response_id", None), getattr(r, "model_version", None), raw


class OpenAICompat:
    """Any OpenAI-compatible server (e.g. Sherkala-8B through llama.cpp or vLLM): OPENAI_BASE_URL, OPENAI_API_KEY."""
    name = "openai_compatible"

    def __init__(self, model):
        import openai
        self.base = os.environ.get("OPENAI_BASE_URL", "http://localhost:8080/v1")
        self.client = openai.OpenAI(base_url=self.base, api_key=os.environ.get("OPENAI_API_KEY", "none"))
        self.model, self.sdk = model, openai.__version__

    def settings(self):
        return {"temperature": TEMPERATURE, "max_tokens": MAX_TOKENS, "seed": SEED, "base_url": self.base,
                "json_schema": True, "sdk": f"openai {self.sdk}"}

    def call(self, system, user):
        # A JSON schema raised valid Sherkala responses from 26% to 100% in the earlier study.
        schema = {"type": "object", "additionalProperties": False, "required": KEYS, "properties": {
            **{k: {"type": "integer", "minimum": 1, "maximum": 5} for k in SCORE_KEYS},
            "addressed_essential_points": {"type": "array", "items": {"type": "integer"}},
            "missed_essential_points": {"type": "array", "items": {"type": "integer"}},
            "evidence": {"type": "string"}}}
        r = self.client.chat.completions.create(
            model=self.model, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, seed=SEED,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_schema", "json_schema": {"name": "score", "schema": schema}})
        return (r.choices[0].message.content or ""), r.id, r.model, r.model_dump(mode="json")


PROVIDERS = {"sim": Sim, "anthropic": Anthropic, "gemini": Gemini, "openai_compat": OpenAICompat}


# ---------------------------------------------------------------- run
def build_requests(items, terms, stimuli, repeats, system, user_tpl):
    reqs = []
    for s in stimuli:
        it, t = items[s["item_id"]], terms[s["term_id"]]
        for ref in REF_CONDITIONS:
            user = render_user(user_tpl, it, t, ref, s["answer_text"])
            for rep in range(1, repeats + 1):
                key = f"{s['stim_id']}|{ref}|{rep}"
                reqs.append({"key": key, "stim": s, "item": it, "ref": ref, "rep": rep,
                             "user": user, "prompt_sha256": sha(system + "\n\n" + user)})
    random.Random(SEED).shuffle(reqs)
    return reqs


def done_keys(path):
    keys = set()
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r["status"] in ("ok", "parse_failed"):
                    keys.add(r["key"])
    return keys


def judge_once(prov, system, user, essential):
    attempts = []
    for i in range(1, MAX_ATTEMPTS + 1):
        t0 = time.time()
        try:
            text, rid, mv, raw = prov.call(system, user)
            obj, err = parse(text, essential)
        except Exception as e:  # network / API errors are logged, never hidden
            text, rid, mv, raw, obj, err = "", None, None, {"exception": repr(e)}, None, "api_error"
        attempts.append({"attempt": i, "time_utc": now(), "latency_s": round(time.time() - t0, 3),
                         "request_id": rid, "returned_model_version": mv, "error": err,
                         "text": text, "raw_response": raw})
        if err is None:
            return obj, attempts, "ok"
        if not isinstance(prov, Sim):
            time.sleep(2 * i)
    status = "api_error" if all(a["error"] == "api_error" for a in attempts) else "parse_failed"
    return None, attempts, status


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=list(PROVIDERS), required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--run", required=True, help="run name, e.g. main, pilot, smoke")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)

    system, user_tpl = load_prompt()
    items, terms, stimuli = load_inputs()
    prov = PROVIDERS[a.provider](a.model)
    reqs = build_requests(items, terms, stimuli, a.repeats, system, user_tpl)
    if a.limit:
        reqs = reqs[:a.limit]

    out = RUNS / a.model.replace("/", "_") / f"{a.run}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    skip = done_keys(out)
    todo = [r for r in reqs if r["key"] not in skip]
    print(f"{a.provider}:{a.model} run={a.run}: {len(reqs)} requests, {len(skip)} already done, {len(todo)} to send")

    counts = {"ok": 0, "parse_failed": 0, "api_error": 0}
    with open(out, "a", encoding="utf-8") as f:
        for n, r in enumerate(todo, 1):
            s = r["stim"]
            if isinstance(prov, Sim):
                prov.ctx = {"item_id": s["item_id"], "quality": s["quality"], "term_form": s["term_form"],
                            "ref": r["ref"], "rep": r["rep"], "n_points": len(r["item"]["ref_en"]),
                            "essential": r["item"]["essential"]}
            obj, attempts, status = judge_once(prov, system, r["user"], r["item"]["essential"])
            counts[status] += 1
            rec = {"key": r["key"], "status": status, "run": a.run, "provider": prov.name,
                   "judge_model": a.model, "stim_id": s["stim_id"], "item_id": s["item_id"],
                   "term_id": s["term_id"], "specialty": s["specialty"], "quality": s["quality"],
                   "term_form": s["term_form"], "ref": r["ref"], "rep": r["rep"],
                   "prompt_version": "judge_v1.0", "prompt_sha256": r["prompt_sha256"],
                   "answer_sha256": s["answer_sha256"], "settings": prov.settings(),
                   "result": obj, "attempts": attempts, "logged_utc": now()}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if n % 250 == 0:
                f.flush()
                print(f"  {n}/{len(todo)} {counts}")
    print(f"done -> {out}: {counts}")


if __name__ == "__main__":
    main()
