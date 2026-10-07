# evalkit

A reusable evaluation framework for RAG, agentic, and LLM systems. Write one
adapter and one dataset per project instead of a new eval suite every time.

```bash
$ evalkit run --config config.yaml
Aggregate scores:
  faithfulness: 0.31
  context_precision: 0.70
  answer_relevancy: 0.43
Report written to report.md
```

## Why

Different systems need different tests — a RAG pipeline needs faithfulness
and context precision, a summarizer needs ROUGE/style checks, a coding agent
needs pass@k. One static test suite can't cover all of that. But the
*harness* around those tests — loading a dataset, calling your system,
scoring it, aggregating results, writing a report — is identical every time.
evalkit is that harness, with the track-specific logic as swappable pieces.

## Install

```bash
pip install evalkit
```

For research-grade RAG metrics on top of the built-in ones, see
[Optional: Ragas-backed evaluator](#optional-ragas-backed-rag-evaluator).

---

## Getting started, step by step

This walks through everything needed to evaluate a real project, in order.
Each step says exactly what file to create and what goes in it.

### 1. Install evalkit into your project's environment

```bash
pip install -e /path/to/evalkit      # from this package, before it's on PyPI
# or, once published:
pip install evalkit
```

Do this inside the virtualenv your project already uses (or a fresh one —
evalkit only needs to be able to reach your system, not live inside its
codebase). If your project is in a different language (e.g. TypeScript),
evalkit still runs as its own Python process alongside it — see step 3.

### 2. Build a dataset

Create a file, e.g. `dataset.jsonl` — one JSON object per line. This is the
set of inputs you're going to test your system against. Full field
reference is in [Dataset format](#dataset-format) below; minimally, each
line needs an `input`.

```json
{"input": "What is our refund policy for orders over 30 days?", "context": ["Refunds are accepted within 30 days of purchase with a receipt."], "metadata": {"precomputed_output": "Refunds are accepted within 30 days of purchase."}}
```

Start with 10-20 real cases if you have them (logs, saved traces, support
tickets) rather than inventing synthetic ones — real examples surface real
weaknesses; made-up ones tend to just confirm what you already believed.

### 3. Write an adapter for your system

This is the one piece of code that's specific to your project. It's a small
class with one method: take an input, return your system's output as text.
Full contract details are in [Adapter format](#adapter-format) below.

**If your system is a live Python function or class:**
```python
# my_adapter.py — lives in YOUR project's repo, not evalkit's
from evalkit.contracts.adapter import BaseAdapter
from my_project.pipeline import answer_query   # your actual entrypoint

class MyAdapter(BaseAdapter):
    def run(self, example_input, metadata=None):
        return answer_query(example_input)
```

**If your system is a service reachable over HTTP (any language, including
TypeScript/Node):**
```python
import httpx
from evalkit.contracts.adapter import BaseAdapter

class MyAdapter(BaseAdapter):
    def __init__(self, base_url="http://localhost:3000/api/query"):
        self.base_url = base_url

    def run(self, example_input, metadata=None):
        response = httpx.post(self.base_url, json={"query": example_input}, timeout=30)
        return response.json()["answer"]
```

**If you already have (input, output) pairs generated offline** (exported
logs, a batch you ran manually) — skip writing an adapter entirely. Put the
output in each dataset example's `metadata.precomputed_output` and use the
built-in `static` adapter (see [Dataset format](#dataset-format)).

### 4. Write a config file

Create `config.yaml` in the same directory (or wherever's convenient — paths
inside it are resolved relative to your current directory when you run
`evalkit`, not relative to the config file itself). Full field reference is
in [Config format](#config-format) below.

```yaml
track: rag                  # rag | generic — see "Which track?" below
dataset: dataset.jsonl
adapter: my_adapter:MyAdapter
judge_backend: dummy        # start here — no API key needed, see step 5
judge_model: dummy
```

**Which track?** Use `rag` if your system retrieves context before
answering (faithfulness/context-precision/answer-relevancy make sense).
Use `generic` otherwise (overall quality and fluency). See
[Metric reference](#metric-reference) for two more built-ins —
`text_similarity` (deterministic, needs a `reference`) and `retrieval`
(deterministic, needs retrieval ground truth) — and
[Computing every possible metric](#computing-every-possible-metric) for
running several evaluators together.

### 5. Run it with the dummy judge first

```bash
evalkit run --config config.yaml
```

`judge_backend: dummy` produces deterministic fake scores with zero API
calls and zero cost — the point of this first run isn't the numbers, it's
confirming the whole pipeline actually works end to end (dataset loads,
your adapter runs without errors, the report gets written) before you spend
anything on real scoring. If this fails, the error is in your adapter or
dataset, not in judging.

### 6. Read the report

Open the generated `report.md`. It's a full write-up: what was tested, how
each metric is computed, and the complete per-example breakdown — not just
the aggregate numbers the terminal showed you. See
[Report formats](#report-formats) for what's in it and why.

### 7. Switch to real scoring

Edit `config.yaml`:
```yaml
judge_backend: litellm
judge_model: gpt-4o-mini    # or claude-haiku-4-5, openrouter/..., a local vLLM endpoint, ...
```
Set the matching provider's API key as an environment variable (e.g.
`OPENAI_API_KEY`) — evalkit never touches credentials directly, LiteLLM
handles that, so this works with 100+ providers without any evalkit code
changing. Run again:
```bash
evalkit run --config config.yaml
```
Now the scores mean something. Read the report again.

### 8. Set thresholds and gate CI on them

Once you have real scores to use as a baseline, add:
```yaml
thresholds:
  - metric: faithfulness
    min: 0.8
```
Then in CI:
```bash
evalkit assert --config config.yaml    # exits 1 if any threshold fails
```
A prompt or model change that quietly tanks quality now fails the build
instead of shipping.

### 9. Compare before/after a change

Before changing a prompt or swapping a model, keep the current config.
After the change, save a second copy and:
```bash
evalkit compare --config-a before.yaml --config-b after.yaml
```
Gives you a direct score diff instead of eyeballing two separate reports.

---

## File formats

### Dataset format

A `.jsonl` file — one JSON object per line, no wrapping array, no commas
between lines.

|  Field  |  Type  |  Required  |  Meaning  |
| ----- | ----- | ----- | ----- |
| `input` | string | **yes** | What's given to your system. |
| `reference` | string | no | A ground-truth answer. Required by `text_similarity`'s metrics; some other evaluators use it when present. |
| `context` | list of strings | no | Retrieved passages — only relevant for RAG/retrieval tracks. Omit entirely for non-RAG evaluation. |
| `metadata` | object | no | Anything else. Two reserved keys: `precomputed_output` (required for the built-in `static` adapter — see below) and `relevant_chunks` (required for `retrieval` track's `precision_at_k`/`recall_at_k`/`mrr` — a list of strings that must exactly match entries in `context` to count as relevant; see [Metric reference](#metric-reference)). |

Full example using every field:
```json
{"input": "What year was the Eiffel Tower completed?", "reference": "1889", "context": ["The Eiffel Tower was completed in 1889 as the entrance arch for the 1889 World's Fair."], "metadata": {"precomputed_output": "It was completed in 1889.", "source": "faq_export_2026"}}
```
Minimal example (no live adapter needed — just scoring existing outputs):
```json
{"input": "What is your return policy?", "metadata": {"precomputed_output": "Returns are accepted within 30 days."}}
```
Blank lines are skipped. A malformed line fails loudly with the exact line
number, not a silent skip.

### Config format

`config.yaml`, loaded by `EvalConfig.from_yaml`. Full field reference:

| Field | Type | Required | Default | Meaning |
|---|---|---|---|---|
| `track` | string, or list of strings | **yes** | — | Which evaluator(s) to run. Built-in: `rag`, `generic` (`ragas` too if the extra is installed). Or a dotted path to your own: `"my_eval:MyEvaluator"`. A list runs every one listed and merges their metrics — see [below](#computing-every-possible-metric). |
| `dataset` | string | **yes** | — | Path to your `.jsonl` file, resolved relative to your current directory when you run `evalkit`. |
| `adapter` | string | **yes** | — | Built-in: `static`. Or a dotted path to your own: `"my_adapter:MyAdapter"`. |
| `adapter_config` | object | no | `{}` | Extra kwargs passed straight to your adapter's constructor, e.g. `{base_url: "..."}`. |
| `evaluator_config` | object | no | `{}` | Extra kwargs for the evaluator's constructor. Single `track`: flat kwargs. List `track`: keyed by track name, e.g. `{ragas: {ragas_model: gpt-4o-mini}}` — a track needing no extra config just omits its key. |
| `metrics` | list of strings | no | `[]` (= every metric the evaluator supports) | Restrict which metrics run, e.g. `[faithfulness]` to skip the others. Applies independently to each evaluator when `track` is a list. |
| `judge_backend` | string | no | `litellm` | Built-in: `litellm` (real scoring, any provider), `dummy` (offline testing, no API key). |
| `judge_model` | string | no | `gpt-4o-mini` | Any LiteLLM model string — only used by the `litellm` judge backend. |
| `max_workers` | integer | no | `5` | Number of dataset examples evaluated concurrently. Set to `1` for sequential execution. |
| `reporter` | string | no | `markdown` | Built-in: `markdown`, `html`, `json`. |
| `output` | string | no | `report.md` | Path the report gets written to. |
| `thresholds` | list of `{metric, min?, max?}` | no | `[]` | Used by `evalkit assert` to gate CI. `min`: fails if the average is below it (quality metrics). `max`: fails if above it (latency, cost — lower is better). At least one of the two is required per entry. |

Full annotated example:
```yaml
track: rag
dataset: dataset.jsonl
adapter: my_adapter:MyAdapter
adapter_config:
  base_url: "http://localhost:3000/api/query"
metrics: [faithfulness, context_precision, answer_relevancy]   # omit this line entirely for "all metrics"
judge_backend: litellm
judge_model: gpt-4o-mini
reporter: markdown
output: report.md
thresholds:
  - metric: faithfulness
    min: 0.8
```

### Adapter format

A Python class in *your* project (never inside evalkit itself), implementing
one method. Returning a plain string remains fully supported:

```python
from evalkit.contracts.adapter import BaseAdapter

class MyAdapter(BaseAdapter):
    def run(self, example_input: str, metadata: dict | None = None) -> str:
        # call your system however it's actually invoked, return its output as text
        ...
```

For RAG/GraphRAG systems, return `AdapterResponse` to expose the context actually
retrieved at runtime:

```python
from evalkit.contracts.adapter import AdapterResponse, BaseAdapter

class MyAdapter(BaseAdapter):
    def run(self, example_input: str, metadata: dict | None = None) -> AdapterResponse:
        answer, chunks = my_system(example_input)
        return AdapterResponse(
            output=answer,
            context=chunks,
            metadata={"retrieval_mode": "hybrid"},
        )
```

`example_input` is the dataset row's `input` field. `metadata` is that row's
`metadata` object, if any. If `AdapterResponse.context` is provided, it takes
precedence over the dataset row's static `context`; otherwise evalkit falls back
to the dataset context. `latency_ms` is optional — evalkit measures adapter wall
time automatically when it is omitted.

Constructor args are up to you; whatever you put in config's
`adapter_config` gets passed to them as keyword arguments.

**Built-in `static` adapter** — no code needed if you already have outputs:
it reads `metadata.precomputed_output` from each dataset row and returns it
directly. Use `adapter: static` in config with no `adapter_config`.

---

## Metric reference

Every metric every built-in evaluator can compute, what it needs, and what
it costs. "Cost" means LLM API calls — deterministic metrics are free and
instant; judge-based ones cost one call per metric per example (except
where noted as shared).

### `track: rag` — LLM-judge, provider-agnostic via LiteLLM

| Metric | Needs | Cost |
|---|---|---|
| `faithfulness` | `context` | 1 judge call |
| `context_precision` | `context` | 1 judge call |
| `answer_relevancy` | nothing extra | 1 judge call |
| `hallucination_rate` | `context` | shares the `faithfulness` call — free if you also request `faithfulness` |

### `track: ragas` — same four metrics via peer-reviewed Ragas implementations, requires `pip install evalkit[ragas]`

Same names and requirements as `rag` above, computed by Ragas instead of
evalkit's hand-rolled prompts — see
[Optional: Ragas-backed evaluator](#optional-ragas-backed-rag-evaluator) for
the provider tradeoff.

### `track: generic` — LLM-judge, any track without a specialized evaluator

| Metric | Needs | Cost |
|---|---|---|
| `quality` | nothing (uses `reference` if present) | 1 judge call |
| `fluency` | nothing | 1 judge call |

### `track: text_similarity` — deterministic, requires `reference`

| Metric | Needs | Cost |
|---|---|---|
| `exact_match` | `reference` | free, instant |
| `f1` | `reference` | free, instant |
| `bleu` | `reference` + `pip install evalkit[text-metrics]` | free, instant |
| `rouge_l` | `reference` + `pip install evalkit[text-metrics]` | free, instant |
| `embedding_similarity` | `reference` | 1 embedding call (cheaper than a judge call, still an API call) |

Examples with no `reference` score nothing for this track — not an error,
just no signal to compare against.

### `track: retrieval` — deterministic, no LLM calls at all

| Metric | Needs | Cost |
|---|---|---|
| `precision_at_k` | `context` + `metadata.relevant_chunks` | free, instant |
| `recall_at_k` | `context` + `metadata.relevant_chunks` | free, instant |
| `mrr` | `context` + `metadata.relevant_chunks` | free, instant |
| `chunk_utilization` | `context` only | free, instant |

`relevant_chunks` is a list of strings that must **exactly match** entries
in `context` — no fuzzy matching, no chunk IDs. Example:
```json
{"input": "...", "context": ["Paris is the capital of France.", "The Eiffel Tower is in Paris."], "metadata": {"relevant_chunks": ["Paris is the capital of France."]}}
```
Examples without `relevant_chunks` skip these three metrics silently — most
datasets won't have ranked ground truth on day one, so this degrades
gracefully rather than erroring.

`chunk_utilization` needs no ground truth: it's a word-overlap heuristic
between each retrieved chunk and the final output, approximating whether
the generator actually used what was retrieved. Treat it as a rough signal,
not a precise measure — it's lexical overlap, not semantic understanding.

**Not built-in, and why:** NDCG needs *graded* relevance labels (not just
binary relevant/not-relevant), which is a bigger data-collection ask than
this framework's reference-free-by-default philosophy fits — added if
someone actually has graded judgments to use it with. Citation coverage
needs your system to emit citations in a specific parseable format, which
varies per project — build it as a custom evaluator (see
[Extending evalkit](#extending-evalkit)) once your citation format is
settled, rather than evalkit guessing at one.

### `track: graph` — GraphRAG relational dimensions (deterministic + LLM judge)

| Metric | Needs | Cost |
|---|---|---|
| `graph_utilization_rate` | `context` (or `metadata.graph_facts_retrieved`) | free, deterministic |
| `community_coherence` | `context` (or `metadata.community_context`) | 1 judge call |
| `global_diversity` | `output` | free, deterministic |
| `entity_relation_coverage` | `reference` (or `metadata.gold_entities`) | free if sets provided, 1 judge call if unanchored |

- `graph_utilization_rate`: computes the fraction of retrieved graph edges or facts utilized in the final output (defaults to 0.0 on explicit evidence refusals).
- `community_coherence`: prompts the judge to evaluate whether a community summary coherently represents its grouped member chunks without apparent hallucination.
- `global_diversity`: evaluates distinct unigram and bigram coverage across distinct themes for global/aggregation queries.
- `entity_relation_coverage`: compares extracted entities and relationships against gold reference sets or source reference text.

### Always present, any track: `latency_ms`

Wall-clock time for your adapter's `run()` call, in milliseconds — measures
your system's response time, not evaluator overhead. Not a 0.0-1.0 score:
shown in its own format in reports, no pass/fail marker, and gated with
`max` (not `min`) in thresholds:
```yaml
thresholds:
  - metric: latency_ms
    max: 3000
```

---

## Computing every possible metric

Two independent knobs control this — use either or both:

**Every metric one evaluator supports:** leave `metrics` out of config
entirely (or set it to `[]`). This is already the default — you don't have
to opt into it, you have to opt *out* by listing a subset.

**Every metric from every evaluator you have:** set `track` to a list
instead of a single name:
```yaml
track: [rag, ragas]         # requires: pip install evalkit[ragas]
```
Every evaluator listed runs against the same dataset, and their scores are
merged into one report — metric names get prefixed with the track name
(`rag.faithfulness`, `ragas.faithfulness`) so two evaluators computing a
metric with the same name never collide. This is how you see the hand-rolled
RAG metrics *and* the peer-reviewed Ragas ones side by side, in one report,
instead of picking one evaluator's view of the project.

`evaluator_config` becomes nested in this mode — keyed by track name:
```yaml
track: [rag, ragas]
evaluator_config:
  ragas:
    ragas_model: gpt-4o-mini
    # "rag" needs no extra config, so it's simply omitted here
```

## Report formats

The CLI's terminal output is always short — aggregate scores and the report
path, nothing else. The report **file** is the full write-up:

- **`markdown`** (default) — run metadata, a summary table, a methodology
  section explaining how each metric is computed, and the complete,
  untruncated per-example breakdown (input, output, reference, retrieved
  context, scores). Meant to be read as documentation and diffed in a PR —
  this is the git-diffable artifact the `compare` command is built around.
- **`html`** — compact single-file visual summary with pass/fail coloring,
  truncated cells. Good for a quick glance or a README screenshot.
- **`json`** — raw per-example results, for piping into your own tooling.

If a run used the `dummy` judge backend, the markdown report says so
explicitly at the top — those scores are a deterministic test signal, not a
real quality measurement.

## CLI

```bash
# Core execution
evalkit run --config config.yaml                      # score a run, write report, and persist run
evalkit run --config config.yaml --isolated           # run in isolation: disables caching and run persistence
evalkit run --config config.yaml --no-cache           # run with fresh judge calls (no cache hits)
evalkit run --config config.yaml --no-save-run        # run without saving historical run record

# CI assertions
evalkit assert --config config.yaml                   # exit non-zero if any threshold fails

# Diffing & regression analysis
evalkit runs list                                     # list all saved historical runs
evalkit diff <run_id_a> <run_id_b>                    # compare two saved runs without re-executing
evalkit compare --config-a a.yaml --config-b b.yaml  # run two configs and diff scores

# Cache management
evalkit cache clear                                   # clear all cached judge scores
```

## Caching & Isolated Execution

To reduce remote LLM judge latency and API calls, evaluations cache judge scores by default:
- **Location**: Cached as SHA-256 keyed JSON payloads in `.evalkit/cache`.
- **Invalidation**: Same judge model, backend, and prompt reuse the cached evaluation.
- **Disabling Cache**: Pass `--no-cache` via the CLI or set `cache: false` in YAML.
- **Clearing Cache**: `evalkit cache clear` removes all cached responses.

### Single-Parameter Isolation (`isolated: true`)

When testing a pipeline in complete isolation without reusing previous judge calls or writing run records to disk:
```yaml
# In config.yaml
isolated: true    # Disables both cache and save_run in one setting
```
Or via the command line:
```bash
evalkit run --config config.yaml --isolated
```
This single setting disables judge cache reuse and avoids saving run records to `.evalkit/runs`.

---

## Run Storage & Historical Diffing (`evalkit diff`)

Every evaluation is saved by default to `.evalkit/runs/<run_id>.json` (timestamped ID by default, or customized via `--run-id`). This enables offline comparative diffing without re-executing model calls:

1. **List past runs**:
   ```bash
   evalkit runs list
   ```
2. **Diff two runs**:
   ```bash
   evalkit diff 2026-10-06_run_baseline 2026-10-07_run_candidate --regression-threshold 0.05
   ```
   Reports aggregate score shifts and lists any per-example regressions exceeding the threshold.

To disable run saving for disposable or testing runs, set `save_run: false` or pass `--no-save-run`.

## Optional: Ragas-backed RAG evaluator

The built-in `rag` track uses hand-rolled LLM-judge prompts — reasonable,
fully provider-agnostic, zero extra dependencies. For research-grade metrics
instead, install the optional extra and switch tracks:

```bash
pip install evalkit[ragas]
```

```yaml
track: ragas          # instead of: rag — or track: [rag, ragas] for both, see above
dataset: dataset.jsonl
adapter: static
metrics: [faithfulness, context_precision, answer_relevancy]
evaluator_config:
  ragas_model: gpt-4o-mini          # any OpenAI model; see provider note below
  ragas_embedding_model: text-embedding-3-small
```

Same `BaseEvaluator` contract, same config shape — `evaluator_config` passes
extra kwargs straight to the evaluator's constructor (mirrors `adapter_config`
for adapters).

**Provider note:** unlike the built-in `rag` track (fully provider-agnostic
via LiteLLM), the ragas-backed evaluator manages its own LLM/embedding calls
and defaults to OpenAI. For another provider, pass your own `ragas_client`
via `evaluator_config`, pointed at any OpenAI-compatible endpoint — see
[ragas's LLM Adapters guide](https://docs.ragas.io/en/stable/howtos/llm-adapters/).
This is the real tradeoff of using ragas's metrics instead of evalkit's own:
less provider-agnostic, in exchange for peer-reviewed metric implementations.

**Known current upstream issue (as of ragas 0.4.3):** a fresh `pip install
ragas` pulls in the latest `langchain-community`, which has removed a module
ragas still imports unconditionally — this breaks *all* of ragas on import,
regardless of which provider you use. evalkit's `ragas` extra pins
`langchain-community<0.4` to work around it. If you see a `ModuleNotFoundError`
mentioning `langchain_community.chat_models.vertexai` anyway, you've got an
unpinned ragas install elsewhere in your environment — check
[ragas's GitHub](https://github.com/vibrantlabsai/ragas) for a fix before
assuming it's evalkit's bug.

## Extending evalkit

Every piece is swappable the same way — a dotted path in config, pointing at
a class in *your* repo:

| Extension point | Contract | Config key |
|---|---|---|
| New track | `evalkit.contracts.BaseEvaluator` | `track` |
| Your own system | `evalkit.contracts.BaseAdapter` | `adapter` |
| Custom judge logic | `evalkit.contracts.BaseJudgeBackend` | `judge_backend` |
| Custom output format | `evalkit.contracts.BaseReporter` | `reporter` |

Each contract has exactly one required method. Implement it, reference it by
dotted path, done.

```python
# my_eval.py
from evalkit.contracts.evaluator import BaseEvaluator

class SummarizationEvaluator(BaseEvaluator):
    METRIC_DESCRIPTIONS = {"length_ratio": "Output length / reference length."}  # optional, shows up in the report

    def __init__(self, judge, metrics=None):
        self.judge = judge

    def evaluate(self, example_input, output, reference, context, metadata):
        # your metrics here — length ratio, ROUGE against reference, a
        # judge call via self.judge.score(prompt), whatever the track needs
        ...
```
```yaml
track: my_eval:SummarizationEvaluator
```

### Why no plugin ecosystem (entry-points, `pip install evalkit-*`)

On purpose. Auto-discovered third-party packages mean evalkit ends up
implicitly responsible for other people's code breaking on a new release —
that's not sustainable for a project maintained by one person. Dotted-path
config gives you the same practical extensibility (write a class, point
config at it) without evalkit ever importing code it doesn't own. If you
want to share an evaluator, publish it as a normal package and tell people
its dotted path.

## Contract stability

`BaseEvaluator`, `BaseAdapter`, `BaseJudgeBackend`, and `BaseReporter` are
frozen at one required method each as of 1.0. New optional parameters may be
added later; required signatures won't change. A custom evaluator you write
today keeps working on every future 1.x release.

## Status

Early — RAG and a generic LLM-judge track are the built-ins today.
Summarization and codegen tracks are natural additions once there's a
concrete need; the contract above is exactly what a contribution for either
would implement.

## Contributing

Issues and PRs welcome. No SLA on response time — this is maintained by one
person alongside other work.

## License

MIT
