# Experiments

Baseline comparisons on open datasets: can a small chip from the chip lab
match a published detector on the same task and data? Each folder holds its
own code, chip files, `results.json` and a `notes.md` that starts with the
verdict, then the protocol, the data and every difference from the
published method.

| Folder             | Task                     | Verdict            |
| ------------------ | ------------------------ | ------------------ |
| `baselines/af/`    | AF from heartbeat timing | matches, does less |
| `baselines/apnea/` | sleep apnea per minute   | not reached        |
| `baselines/arr/`   | abnormal heartbeats      | not reached        |

- **AF** (`baselines/af/notes.md`, "Verdict (round two)"; protocol fixed
  first in `round2/protocol.md`). Accuracy matches the published chip; it
  does not beat it, and the intervals are about 8 points wide. The circuit is
  much smaller, but it is a smaller function in a different cell library,
  not the same function made smaller. On a second database, run once,
  sensitivity ties and specificity is below. The site's card for this
  comparison is `dashboard/data/af-baseline.json` on `gh-pages`.
- **Apnea** (`baselines/apnea/notes.md`). The pre-registered design matches
  the database's reference rule within noise and is below every published
  learned result.
- **Heartbeats** (`baselines/arr/notes.md`). No fair comparison in which the
  chip matches or beats the published baseline has been shown.

The data come from open PhysioNet databases; the Data section of each
`notes.md` names them.
