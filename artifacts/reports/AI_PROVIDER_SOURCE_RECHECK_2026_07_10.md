# AI Provider Source Re-check

Generated: 2026-07-10

Status: **RG-08 CLOSED FOR PRE-PAID-BENCHMARK PLANNING — NO PROVIDER RUNS AUTHORIZED**

## Scope

This report closes the primary-source lookup gap for OpenAI GPT-5.6 pricing and Gemini
3.x context/pricing assumptions before any paid benchmark run. It does not configure
credentials, run a model, approve paid spend, or change the mock/null-provider default.

## Primary Sources Checked

- OpenAI official GPT-5.6 preview page:
  `https://openai.com/index/previewing-gpt-5-6-sol/`
- OpenAI official pricing/business availability page:
  `https://openai.com/business/pricing/`
- Google AI Developers Gemini 3 guide:
  `https://ai.google.dev/gemini-api/docs/gemini-3`
- Google AI Developers Gemini API pricing:
  `https://ai.google.dev/gemini-api/docs/pricing`
- Google AI Developers Gemini API models page:
  `https://ai.google.dev/gemini-api/docs/models`

## Captured Facts

| Provider | Model family | Primary-source planning fact |
|---|---|---|
| OpenAI | GPT-5.6 | Official OpenAI release page lists GPT-5.6 Sol, Terra, and Luna per-1M-token API pricing as Sol `$5 input / $30 output`, Terra `$2.50 / $15`, and Luna `$1 / $6`. It also records cache-write billing at `1.25x` uncached input and cached-input reads at a `90%` discount. |
| OpenAI | GPT-5.6 | Official OpenAI business pricing page shows GPT-5.6 Sol/Sol Pro/Terra/Luna availability as flexible for Business and Enterprise plans. |
| Google | Gemini 3 / 3.1 | Official Gemini 3 guide lists context windows and pricing examples: `gemini-3.1-flash-lite` `1M / 64k`, `gemini-3.1-pro-preview` `1M / 64k`, `gemini-3-flash-preview` `1M / 64k`, and image-preview variants with smaller windows. |
| Google | Gemini API | Official pricing page lists paid-tier rates for multiple Gemini 3.x SKUs, including `gemini-3.1-pro-preview` tiering at prompts `<= 200k` and `> 200k`, plus context-caching and Google Search grounding rates. |
| Google | Gemini API models | Official models page records deprecation/shutdown handling for previous models and points users to newer models before shutdown. |

## Constraints Kept

- No `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GOOGLE_API_KEY` is configured.
- No real-provider benchmark run is authorized.
- Mock/null-provider mode remains the default.
- Pricing/model availability must be rechecked immediately before any paid run because
  pricing, model IDs, access tiers, and deprecation status are time-sensitive.

## Result

RG-08 is closed for the current planning purpose. The next blocker for T-011-05 remains
credential/spend authority plus human review, not lack of primary-source pricing/context
data.
