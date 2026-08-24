# LinguistOS

Code for my MSc project on "Morphosyntactically constrained sentence generation for vocabulary practice".

The repository has two separate parts, matching the distinction in the report:

| Part | Role | Location |
|------|------|----------|
| **Experimental framework** | CLI pipeline that runs generation methods on benchmarks, scores outputs with a shared metric suite, and stores results in SQLite experiment databases. This is what produces the technical-method and transfer results. | [`research/`](research/) |
| **User-facing learning prototype** | Interactive vocabulary / sentence-practice app. Demonstrates how the research could sit inside a learning product. It is **not** connected to the experimental framework and is not used for the reported experiments. | [`frontend/`](frontend/) + [`backend/`](backend/) |

## Layout

```
research/   Experimental framework (benchmarks, methods, evaluation, cluster scripts)
frontend/   Next.js learning prototype UI
backend/    FastAPI service for the prototype
docs/       Specs, experiment notes, and report-writing material
```

Setup for each part is in its own README: [research](research/README.md), [frontend](frontend/README.md), [backend](backend/README.md).
