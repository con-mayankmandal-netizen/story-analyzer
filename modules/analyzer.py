import json
import re

_gemini_client  = None
_groq_client    = None
_claude_client  = None
_provider       = "gemini"


def init_client(api_key, provider="gemini"):
    global _gemini_client, _groq_client, _claude_client, _provider
    _provider = provider
    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        _gemini_client = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={"temperature": 0.3, "response_mime_type": "application/json"}
        )
    elif provider == "groq":
        from groq import Groq
        _groq_client = Groq(api_key=api_key)
    elif provider == "claude":
        import anthropic
        _claude_client = anthropic.Anthropic(api_key=api_key)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'gemini', 'groq', or 'claude'.")


def _call_ai(system_prompt, user_prompt):
    if _provider == "gemini":
        return _gemini_client.generate_content(f"{system_prompt}\n\n{user_prompt}").text
    elif _provider == "groq":
        response = _groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.3, max_tokens=2000)
        return response.choices[0].message.content
    elif _provider == "claude":
        import anthropic
        response = _claude_client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=2000, system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}])
        return response.content[0].text
    raise RuntimeError("No AI client initialized.")


def _parse_json(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw.strip())


SINGLE_SYSTEM = """You are an expert video ad script analyst for audio drama/podcast apps.
Return ONLY valid JSON with this structure:
{"overall_score":0,"verdict":"","hook_score":0,"hook_finding":"","hook_recommendation":"","pacing_score":0,"pacing_finding":"","pacing_recommendation":"","emotional_arc_score":0,"emotional_arc_finding":"","emotional_arc_recommendation":"","cta_score":0,"cta_finding":"","cta_recommendation":"","retention_correlation":"","why_it_performed":"","top_3_improvements":[],"writer_feedback":""}"""

COMPARE_SYSTEM = """You are an expert video ad strategist for audio drama/podcast apps.
Return ONLY valid JSON:
{"winner":"","winner_reason":"","ranking":[],"pattern_insights":"","hook_pattern":"","writer_pattern":"","what_to_replicate":[],"what_to_avoid":[],"next_test_recommendation":""}"""


def analyze_single(script_text, metrics_text, adset_code):
    prompt = f"ADSET CODE: {adset_code}\nSCRIPT:\n{script_text}\nPERFORMANCE:\n{metrics_text}"
    return _parse_json(_call_ai(SINGLE_SYSTEM, prompt))


def compare_scripts(analyses, metrics_map):
    payload = [{"adset_code": c, "analysis": a, "metrics": metrics_map.get(c, "")} for c, a in analyses.items()]
    return _parse_json(_call_ai(COMPARE_SYSTEM, f"Compare {len(payload)} scripts:\n{json.dumps(payload)}"))
