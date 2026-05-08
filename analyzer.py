"""
AI Analyzer — supports multiple providers.
Default: Google Gemini (FREE, 1500 requests/day, no card needed)
Fallback options: Groq (free), Claude (paid but cheap)
"""

import json
import re

_gemini_client  = None
_groq_client    = None
_claude_client  = None
_provider       = "gemini"


def init_client(api_key: str, provider: str = "gemini"):
    """
    provider options:
      "gemini" — Google Gemini 1.5 Flash. FREE: 15 req/min, 1500/day forever.
                 Get key: aistudio.google.com  (no card needed)
      "groq"   — Groq Llama 3.1. FREE: generous daily limits, very fast.
                 Get key: console.groq.com     (no card needed)
      "claude" — Anthropic Claude Haiku. ~$0.001/run. Best quality.
                 Get key: console.anthropic.com
    """
    global _gemini_client, _groq_client, _claude_client, _provider
    _provider = provider

    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        _gemini_client = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.3,
                "response_mime_type": "application/json",
            }
        )

    elif provider == "groq":
        from groq import Groq
        _groq_client = Groq(api_key=api_key)

    elif provider == "claude":
        import anthropic
        _claude_client = anthropic.Anthropic(api_key=api_key)

    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'gemini', 'groq', or 'claude'.")


def _call_ai(system_prompt: str, user_prompt: str) -> str:
    if _provider == "gemini":
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response = _gemini_client.generate_content(full_prompt)
        return response.text

    elif _provider == "groq":
        response = _groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1500,
        )
        return response.choices[0].message.content

    elif _provider == "claude":
        import anthropic
        response = _claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text

    raise RuntimeError("No AI client initialized. Call init_client() first.")


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw.strip())


SINGLE_SYSTEM = """You are an expert video ad script analyst for audio drama/podcast apps.
You receive a script text and its real Meta Ads performance data from a Facebook/Instagram campaign.
Your job: explain exactly WHY this script performed the way it did, using specific lines/moments as evidence.

Return ONLY valid JSON (no markdown, no extra text) with this exact structure:
{
  "overall_score": <0-100 integer>,
  "verdict": "<one punchy sentence>",
  "hook_score": <0-100>,
  "hook_finding": "<what works or fails in the first 5 seconds, cite specific lines>",
  "hook_recommendation": "<one concrete fix>",
  "pacing_score": <0-100>,
  "pacing_finding": "<how the pacing relates to the retention funnel data>",
  "pacing_recommendation": "<one concrete fix>",
  "emotional_arc_score": <0-100>,
  "emotional_arc_finding": "<how emotional tension builds or collapses, with evidence from script>",
  "emotional_arc_recommendation": "<one concrete fix>",
  "cta_score": <0-100>,
  "cta_finding": "<how effective the call to action is given the CTI data>",
  "cta_recommendation": "<one concrete fix>",
  "retention_correlation": "<paragraph connecting script moments to V0-25, V25-50, V50-75, V75-95 numbers>",
  "why_it_performed": "<paragraph: overall explanation using both script and data>",
  "top_3_improvements": ["<fix 1>", "<fix 2>", "<fix 3>"],
  "writer_feedback": "<one paragraph of direct, honest feedback for the writer>"
}"""

COMPARE_SYSTEM = """You are an expert video ad strategist for audio drama/podcast apps.
You receive analysis results for 2-4 scripts along with their real Meta Ads data.
Identify patterns — what structural, narrative, or stylistic differences explain the performance gaps.

Return ONLY valid JSON (no markdown, no extra text) with this structure:
{
  "winner": "<adset code of best performer>",
  "winner_reason": "<one sentence: core reason this script outperformed>",
  "ranking": [{"code": "<adset_code>", "score": <overall_score>, "one_line": "<why it ranked here>"}],
  "pattern_insights": "<2-3 paragraphs on structural patterns that correlate with better retention/CTR/installs>",
  "hook_pattern": "<what the best-performing hooks have in common vs worst>",
  "writer_pattern": "<if multiple writers, what style differences correlate with performance>",
  "what_to_replicate": ["<element to copy 1>", "<element to copy 2>", "<element to copy 3>"],
  "what_to_avoid": ["<stop doing 1>", "<stop doing 2>", "<stop doing 3>"],
  "next_test_recommendation": "<what the team should test next>"
}"""


def analyze_single(script_text: str, metrics_text: str, adset_code: str) -> dict:
    user_prompt = f"""ADSET CODE: {adset_code}

SCRIPT TEXT:
{script_text}

META ADS PERFORMANCE DATA:
{metrics_text}

Analyze this script's performance. Cite actual lines from the script when explaining retention drops or spikes."""
    return _parse_json(_call_ai(SINGLE_SYSTEM, user_prompt))


def compare_scripts(analyses: dict, metrics_map: dict) -> dict:
    payload = [
        {"adset_code": code, "analysis": analysis, "metrics": metrics_map.get(code, "")}
        for code, analysis in analyses.items()
    ]
    user_prompt = f"Compare these {len(payload)} scripts and identify what drove performance differences.\n\n{json.dumps(payload, indent=2)}"
    return _parse_json(_call_ai(COMPARE_SYSTEM, user_prompt))

