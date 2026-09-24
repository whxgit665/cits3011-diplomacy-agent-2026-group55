# CITS3011 Group 55 - Harbour

## Submission files

- `agent_55.py`: agent implementation; the default configuration enables C + R.
- `test_55.py`: experiments and functional checks.
- `report_55.pdf`: four-page report with three editable name/student-number rows.
- `llm_usage_55.pdf`: AI assistance disclosure and recorded prompts.

Fill in all three members' details before submission. The files have not been uploaded to LMS. The assignment deadline in the supplied specification is 2 October 2026, 23:59 AWST.

## Setup and checks

Use Python 3.12 and the supplied dependency versions:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONHASHSEED=0 python test_55.py --checks
PYTHONHASHSEED=0 python test_55.py --repeats 1 --workers 4 --output results/my_check_01
```

The quick experiment runs seven games per scenario, one for each power. Use a new output prefix on each run; existing result files are not overwritten.

## Reproduce the report

```bash
PYTHONHASHSEED=0 python test_55.py --variants all --scenarios 2 --repeats 10 --seed 1000 --workers 4 --output results/development_rerun
PYTHONHASHSEED=0 python test_55.py --variants all --scenarios 1 --repeats 1 --seed 1000 --workers 4 --output results/static_all_rerun
PYTHONHASHSEED=0 python test_55.py --variants no_coverage --scenarios 2 --repeats 10 --seed 9000 --workers 4 --output results/holdout_rerun
PYTHONHASHSEED=0 python test_55.py --variants no_coverage --scenarios 1 --repeats 1 --seed 9000 --workers 4 --output results/final_static_rerun
```

Development used 560 games across eight configurations. Final Scenario 2 evaluation used 70 separate-seed games: 58 wins and 16.70 mean supply centres. Final Scenario 1 evaluation won all seven games. The pilot overlaps development seeds and is not additional independent evidence. Local results do not guarantee marking results; the official Hidden Agent and tournament were unavailable.

## Retained configurations

| Variant | Global coverage G | Coordination C | Adaptive risk R |
|---|---|---|---|
| base | Off | Off | Off |
| coverage | On | Off | Off |
| coordination | Off | On | Off |
| risk | Off | Off | On |
| no_coverage (default) | Off | On | On |
| no_coordination | On | Off | On |
| no_risk | On | On | Off |
| full | On | On | On |

All three modifications remain implemented and evaluated. G is disabled in the final configuration because the development comparisons favoured C + R. The final agent hash differs from the development hash only because the constructor default changed; the explicitly selected experimental configurations use the same decision logic.

The supplied `game.py`, `agent_baselines.py`, `requirements.txt` and `standard.map` are unchanged. `visualize.py` adapts the supplied example to run this agent as France. The agent itself does not write files or use networking, LLMs or GPUs; the experiment driver writes result files. Timing is machine-specific, and recorded worker memory includes opponents and engine copies.

The original assessment documents prohibit AI report writing; the user reported a subsequent teacher policy change allowing it. This provenance is disclosed in the usage record. Append subsequent assessment-related prompts and any other group members' actual AI use before submission.
