# Subtitle Readability Design

## Overview

This document proposes the next quality upgrade for the local YouTube dubbing CLI at `/home/ivan/Projects/YoutubeVideos`.

The current pipeline already downloads, transcribes, translates, and composes final subtitles successfully. The main experience problem is no longer pipeline stability. It is subtitle readability.

Recent generated output shows that the current layout logic can split mixed Chinese and English text at arbitrary character boundaries, which creates visibly broken subtitles such as:

- `Java` / `Script`
- `Axi` / `os`
- `H` / `TTP`
- `2026` / `年`

This makes the output feel machine-generated even when the translation itself is acceptable.

## Problem Statement

The current subtitle logic in `ytdub/media/subtitles.py` is optimized for compact CJK subtitle layout, but it treats many mixed-language strings as plain character sequences once compact layout is selected.

That causes three user-facing problems:

1. English words, acronyms, numbers, and branded terms can be split in the middle.
2. A single sentence can be broken into multiple subtitle cues too aggressively.
3. Line breaks optimize width, but not semantic readability.

As a result, the tool produces subtitles that are technically valid SRT, but not yet pleasant to watch.

## Goals

- Preserve token integrity for mixed-language subtitles.
- Prefer single-line subtitles when they remain readable.
- When wrapping is necessary, break on semantic boundaries instead of raw character counts.
- Avoid splitting one sentence across multiple cues unless timing pressure makes it necessary.
- Keep the implementation deterministic, testable, and local-first.
- Improve subtitle quality without introducing heavy model dependencies into the compose step.

## Non-Goals

- Full LLM-based rewriting during subtitle rendering
- Speaker diarization
- Lip-sync or mouth-shape alignment
- Rich subtitle styling beyond SRT-compatible content
- Replacing the current pipeline architecture

## Design Principles

### Token Safety First

The renderer must never split protected tokens in the middle. Protected tokens include:

- Latin words such as `JavaScript`, `Promise`, `fetch`
- acronyms such as `HTTP`, `AWS`, `CI/CD`
- version-like strings such as `v1.2.3`
- number-plus-unit strings such as `2026年`, `10个`
- URLs, file names, package names, and API names where detectable

This is the single highest-priority rule.

### Sentence Integrity Before Visual Balance

A balanced two-line subtitle is useful only if it still reads naturally. It is better to keep one slightly longer line than to break a short technical term or split a sentence at an unnatural point.

### Single-Line Preferred, Not Forced

The product direction should be:

- single line if it fits
- two lines if needed
- split into multiple cues only when duration, density, or sentence length requires it

This keeps the output close to the style used by stronger open-source subtitle translation projects.

### Time-Aware Layout

Allowed subtitle density should depend on cue duration, not only fixed character thresholds. A 4-second cue and a 1-second cue should not be laid out with the same hard limit.

## Approaches Considered

### Approach A: Extend the existing rule-based layout engine

Add token-aware parsing, semantic wrap points, and duration-aware thresholds on top of the current `reshape_subtitle_segments()` and `render_srt()` flow.

Pros:

- Fits the current architecture
- Fully deterministic
- Easy to unit test
- No extra API cost

Cons:

- More layout logic to maintain
- Requires careful heuristic tuning for mixed-language text

### Approach B: Force single-line subtitles globally

Render everything as one line and only split cues by timing.

Pros:

- Simple
- Aligns with the desired style for many cases

Cons:

- Fails badly on long subtitles
- Will overflow or create unreadable high-density cues
- Does not solve mixed-language token splitting by itself

### Approach C: Use an LLM pass to rewrite subtitles for readability

After translation, ask an LLM to re-segment and rewrite each cue for better presentation.

Pros:

- Potentially strong semantic judgment
- Flexible for many languages

Cons:

- Higher cost and latency
- Less deterministic
- Harder to test
- Can introduce hallucinated rewrites or timing drift

## Recommendation

Use Approach A now.

It solves the main problem in the current codebase with the least architectural disruption. The system already has a dedicated subtitle processing module, and the failure mode is mainly heuristic rather than missing infrastructure.

LLM-assisted refinement can be added later as an optional mode, but it should not be the default rendering path.

## Proposed Design

## 1. Add Protected Token Detection

Before chunking or wrapping, normalize the text into a sequence of tokens rather than raw characters.

The tokenizer should detect at least these categories:

- CJK text runs
- Latin word runs
- uppercase acronym runs
- numbers
- punctuation
- connector markers
- mixed technical terms such as `Node.js`, `OpenAI API`, `CI/CD`, `npm`, `Axios`

The output of this stage should preserve boundaries so the renderer knows what cannot be split.

### Expected Behavior

- `JavaScript开发者` may split between `JavaScript` and `开发者`, but never inside `JavaScript`
- `2026年3月31日` may split between phrase groups, but never into `2026` / `年`
- `HTTP请求` may split between `HTTP` and `请求`, but never into `H` / `TTP`

## 2. Replace Character-Based Compact Fallback

The current compact fallback splits by raw character count. That is the direct source of the worst artifacts in mixed-language subtitles.

Replace it with token-aware packing:

- pack protected tokens atomically
- allow CJK runs to split only at safe boundaries
- preserve punctuation with the phrase it closes

If a token is too long to fit on one line by itself, the renderer should still keep it intact and allow the line to exceed the soft limit rather than corrupt it.

## 3. Introduce Semantic Break Priorities

When a cue must wrap or split, prefer breakpoints in this order:

1. sentence-ending punctuation
2. clause punctuation
3. discourse connectors such as `但是`, `不过`, `然后`, `因此`
4. phrase boundaries between protected tokens and CJK text
5. fallback width-based split at safe token boundaries

Never use a raw midpoint split when a safe token boundary exists.

## 4. Make Single-Line the Default Layout Preference

Today the layout logic effectively wraps early for compact text.

The new behavior should be:

- attempt a single-line render first
- if density exceeds the soft limit, attempt a two-line semantic wrap
- if density still exceeds the hard limit, split into multiple cues

This changes the visual style from “always tightly wrapped” to “single line unless readability says otherwise”.

## 5. Introduce Duration-Aware Density Limits

Instead of one fixed `max_segment_units` and `max_line_units`, calculate soft and hard limits from cue duration.

Suggested policy:

- short cue: aggressive shortening or split
- medium cue: allow a moderate single line
- long cue: allow longer single-line or balanced two-line layout

A simple first version can use duration buckets rather than a full CPS model.

Example:

- under 1.5s: favor short cue text and early splitting
- 1.5s to 3.5s: normal limits
- above 3.5s: allow wider lines before forcing a split

## 6. Add a Glossary and Protected Phrase Layer

Introduce a small optional configuration source for term handling.

The first version only needs two lists:

- `protected_terms`
- `do_not_translate_terms`

Examples:

- `JavaScript`
- `TypeScript`
- `OpenAI API`
- `Axios`
- `Node.js`
- `CI/CD`

This should be applied before translation when relevant and again before subtitle layout to prevent bad wrapping.

## 7. Generate a Subtitle QA Report

For each composed job, write a machine-readable report next to the final SRT.

Suggested checks:

- cues exceeding soft density
- cues exceeding hard density
- wrapped cues count
- multi-cue sentence splits
- protected token split violations
- suspicious mixed-token outputs such as lowercase fragments after a split

This allows quality inspection without watching the full video every time.

## File-Level Impact

The expected implementation should stay mostly inside the current subtitle and compose path.

Primary files:

- `ytdub/media/subtitles.py`
- `tests/test_subtitles.py`
- `ytdub/pipeline/steps/compose.py`
- `tests/test_pipeline_runner.py`

Possible new modules if the subtitle logic grows further:

- `ytdub/media/subtitle_tokens.py`
- `ytdub/media/subtitle_qa.py`

The preferred direction is to split tokenization and QA into focused helper modules rather than keep all logic in one large file.

## Example Output Improvements

Examples of desired behavior:

Current:

```text
如果你是一名Java
Script开发者，
```

Desired:

```text
如果你是一名JavaScript开发者，
```

Current:

```text
js和浏览器中进行H
TTP请求的开发体验。
```

Desired:

```text
js和浏览器中进行HTTP请求的开发体验。
```

Current:

```text
今天是2026
年3月31日，
```

Desired:

```text
今天是2026年3月31日，
```

Current:

```text
因为它几乎肯定
会让你哭出来。
```

Desired:

```text
因为它几乎肯定会让你哭出来。
```

or, if the line is too dense:

```text
因为它几乎肯定，
会让你哭出来。
```

## External Project References

The direction in this proposal is informed by patterns used in similar open-source projects:

- `Huanshere/VideoLingo`
  - emphasizes high-quality subtitle segmentation, terminology consistency, and single-line subtitle style
- `jianchang512/pyvideotrans`
  - emphasizes operator control, editing checkpoints, and production workflow flexibility
- `R3gm/SoniTranslate`
  - emphasizes synchronized translation pipelines and resumable multi-stage processing
- `ThioJoe/Auto-Synced-Translated-Dubs`
  - emphasizes glossary-like controls, timing preservation, and configurable output rules

This project should borrow their quality principles, not their full product scope.

## Rollout Plan

Recommended implementation order:

1. Fix protected token splitting.
2. Switch compact fallback from character-based splitting to token-based splitting.
3. Change layout policy to single-line preferred.
4. Add duration-aware limits.
5. Add glossary support.
6. Add subtitle QA report.

## Success Criteria

The redesign is successful if:

- generated subtitles never split common English technical tokens mid-word
- mixed Chinese-English lines remain readable without obvious machine artifacts
- the number of unnecessary two-line cues drops substantially
- long sentences split at semantic boundaries instead of arbitrary character boundaries
- the new logic remains fully covered by deterministic unit tests

## Open Questions

- Should single-line preference be global, or configurable by target language?
- Should glossary support live in `configs/default.toml` or a dedicated glossary file?
- Should subtitle QA failures only report warnings, or optionally fail the compose step in strict mode?

## Outcome

The next quality milestone for this project should be a token-safe, semantic, duration-aware subtitle layout engine.

This is the highest-leverage improvement because it directly upgrades what users actually watch, while fitting cleanly into the current architecture.
