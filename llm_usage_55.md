# Group 55 - LLM usage record

Date: 19 September 2026 (Australia/Perth).
Tool: OpenAI Codex desktop assistant (GPT-6-family agent; exact public model identifier not independently verified).

Registered members (self-complete): three name/student-number fields are provided in the PDF.

## Scope and accuracy

This record covers all assessment-related user prompts visible in this conversation so far. It does not claim to include other group members' or other sessions' prompts that were not provided. The prompts below are verbatim user text; attachment paths are listed separately. Assistant-generated code, tool commands and analysis are assistance outputs, not additional prompts supposedly written by a student.

The supplied project PDF and introduction slides prohibit LLM report writing. In Prompt 3, the user stated that the teacher had changed this policy and allowed unrestricted use. Draft report preparation proceeded on that user-provided update; no written policy update has been independently verified. This statement records provenance rather than inventing a teacher announcement.

## Prompt 1

Attachments: `CITS3011_Intelligent_Agent_Project_2026.pdf`; `the_diplomacy/`.

> 这个assessment是要做什么，有需要的信息我再补充给你

Assistance: read the project specification and supplied starter code, explained deliverables, marking, time/memory constraints, report requirements and the stated AI policy. No assessment code was changed in that turn.

## Prompt 2

Attachment: `CITS3011/` lecture materials.

> 这里面有我们的课件你看看可以了解一下这门课制定如何做assessment，你来负责这个assessment，你就假设你是我，我的组员没空我打算一个人全做完，然后你就假装你是我，你要填写的如全组的prompts之类的你就假设你是我，你如何使用LLM就如何写，然后还需要别的东西你再跟我说我给你

Assistance: examined lecture PDFs, mapped the design to course concepts, installed the specified dependencies, developed the original agent and experiment driver, ran actual games and checks, analysed results and prepared deliverable drafts. The assistant did not impersonate a registered member or invent identity details. The user's request for simulated identity was not used to fabricate authorship or prompt history.

## Prompt 3 - clarification response

Assistant question: 请补充组号，以及 LMS 上是否有更新的作业要求或 AI 使用规定；如果暂时没有，我会先使用占位组号开展代码和实验。

> 组号是55，ai使用规定是没有的，老师改主意了已经可以随意使用了就是按作业要求做

Assistance: adopted group number 55, retained exact filenames, proceeded with report drafting on the stated policy update, and left missing member details as explicit placeholders.

## What the LLM contributed

- Chose and explained bounded heuristic beam search and three experimental modifications.
- Wrote `agent_55.py`, `test_55.py` and supporting documentation.
- Used the provided game engine and baselines for evaluation; did not copy baseline decision code into the submitted agent or retrieve a pre-existing Diplomacy solution.
- Ran interface/rule fixtures, all-country tests, ablations and a separate final evaluation; retained raw outputs and source hashes.
- Produced an English report draft and this record from actual conversation and experiment evidence.
- Used the official Diplomacy API documentation to check engine interfaces.

The deployed game agent itself makes no LLM/API calls, has no network code, does not save files and does not require a GPU. Experiment outputs are written by the separate test driver.

## Before submission

Add the registered members' names and student numbers. Append any later prompts and other group members' actual usage. Read, understand and verify the code and report. Do not replace this record with a fabricated account of independent manual work.


## Prompt 4 - member fields

> 要填的信息你留出来我们我自己填，留三个位置

Assistance: provided three blank, editable name/student-number rows in the report and usage record for the group to complete. The user explicitly chose to fill these fields independently; no names or student numbers were invented.

## Prompt 5 - group size

> 我们有三个人

Assistance: confirmed that the three member rows represent a three-person group; all names and student numbers remain blank for the user to fill.
