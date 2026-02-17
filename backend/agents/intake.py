"""
Intake Agent: Claude-powered request parsing
Extracts structured data from natural language request
"""
import time
import json
from anthropic import Anthropic
from models import IntakeResult, IntakeExtraction

# Lazy client creation to avoid import-time blocking
_client = None

def _get_client():
    """Create Anthropic client on first use (lazy initialization)"""
    global _client
    if _client is None:
        _client = Anthropic()
    return _client

def run_intake(request_text: str, requester_email: str, selected_dataset: str) -> IntakeResult:
    """
    Parse user request into structured fields
    Returns extraction + reasoning + confidence
    """
    print("\n" + "="*60)
    print("📥 INTAKE AGENT - Parsing request with Claude")
    print("="*60)
    print(f"👤 Requester: {requester_email}")
    print(f"📊 Dataset: {selected_dataset}")
    print(f"📝 Request: {request_text[:80]}...")
    
    start_time = time.time()
    
    # Claude prompt
    prompt = f"""You are an intake agent for a data access request system. Extract structured information from the user's request.

USER: {requester_email}
REQUEST: "{request_text}"
SELECTED DATASET: {selected_dataset}

Extract the following fields:
1. **requester** - The email address (already known: {requester_email})
2. **dataset** - The dataset name (already known: {selected_dataset})
3. **access_level** - One of: "read", "write", or "admin"
   - Infer from verbs: "analyze", "view", "query" → read
   - "update", "modify", "insert" → write
   - "manage", "configure", "admin" → admin
   - Default to "read" if unclear
4. **justification** - Brief business justification from the request
5. **urgency** - Optional: "high", "medium", "low" if mentioned
6. **confidence** - Your confidence in the extraction (0.0 to 1.0)

Also provide reasoning steps explaining your extraction logic.

Return JSON:
{{
  "extracted": {{
    "requester": "{requester_email}",
    "dataset": "{selected_dataset}",
    "access_level": "read|write|admin",
    "justification": "...",
    "urgency": "high|medium|low|null",
    "confidence": 0.0-1.0
  }},
  "reasoning": [
    "Step 1: ...",
    "Step 2: ..."
  ]
}}

Return ONLY the JSON, no explanation."""

    # Call Claude (lazy client creation)
    print(f"🤖 Calling Claude API...")
    print(f"   Model: claude-sonnet-4-20250514")
    print(f"   Max tokens: 1024")
    print(f"   Prompt length: {len(prompt)} characters")
    
    message = _get_client().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    
    tokens_used = message.usage.input_tokens + message.usage.output_tokens
    response_text = message.content[0].text.strip()
    
    print(f"✅ Claude API Response:")
    print(f"   Input tokens: {message.usage.input_tokens}")
    print(f"   Output tokens: {message.usage.output_tokens}")
    print(f"   Total tokens: {tokens_used}")
    print(f"   Response length: {len(response_text)} characters")
    
    # Parse response
    try:
        # Extract JSON if wrapped
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        result = json.loads(response_text)
        extracted_data = result.get("extracted", {})
        reasoning = result.get("reasoning", [])
        
    except json.JSONDecodeError:
        # Fallback if parsing fails
        extracted_data = {
            "requester": requester_email,
            "dataset": selected_dataset,
            "access_level": "read",
            "justification": request_text[:100],
            "urgency": None,
            "confidence": 0.5
        }
        reasoning = ["Fallback: JSON parse failed, using defaults"]
    
    # Build Pydantic model
    extraction = IntakeExtraction(**extracted_data)
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    print(f"📊 Extracted:")
    print(f"   • Access Level: {extraction.access_level}")
    print(f"   • Justification: {extraction.justification[:60]}...")
    print(f"   • Confidence: {extraction.confidence:.2f}")
    print(f"⏱️  Intake completed in {duration_ms}ms")
    print("="*60 + "\n")
    
    return IntakeResult(
        duration_ms=duration_ms,
        tokens=tokens_used,
        extracted=extraction,
        reasoning=reasoning
    )
