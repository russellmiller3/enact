"""
Discovery Agent: Claude-powered dataset catalog search
Matches user request against available datasets
"""
import time
import json
from anthropic import Anthropic
from utils import load_datasets
from models import DiscoveryResult, DatasetMatch

# Lazy client creation to avoid import-time blocking
_client = None

def _get_client():
    """Create Anthropic client on first use (lazy initialization)"""
    global _client
    if _client is None:
        _client = Anthropic()
    return _client

def run_discovery(request_text: str, selected_dataset: str = None) -> DiscoveryResult:
    """
    Search dataset catalog for matches
    Returns full dataset objects for frontend modal rendering
    """
    print("\n" + "="*60)
    print("🔍 DISCOVERY AGENT - Starting dataset search")
    print("="*60)
    print(f"📝 Request: {request_text[:80]}...")
    
    start_time = time.time()
    
    datasets = load_datasets()
    print(f"📂 Loaded {len(datasets)} datasets from catalog")
    
    # If user pre-selected a dataset (exact match), skip LLM
    if selected_dataset and selected_dataset in datasets:
        print(f"✓ Pre-selected dataset: {selected_dataset} (skipping LLM)")
        dataset = datasets[selected_dataset]
        match = _build_dataset_match(selected_dataset, dataset, 1.0, dataset.get("keywords", []))
        
        duration_ms = int((time.time() - start_time) * 1000)
        print(f"⏱️  Discovery completed in {duration_ms}ms (no LLM call)")
        return DiscoveryResult(
            duration_ms=duration_ms,
            tokens=0,
            matches=[match],
            match_count=1
        )
    
    # Build catalog summary for Claude
    catalog_entries = []
    for dataset_name, dataset in datasets.items():
        catalog_entries.append({
            "name": dataset_name,
            "id": dataset.get("id"),
            "description": dataset.get("description"),
            "keywords": dataset.get("keywords", []),
            "classification": dataset.get("classification")
        })
    
    # Claude prompt
    prompt = f"""You are a dataset discovery agent. Match the user's request against the dataset catalog.

USER REQUEST: "{request_text}"

DATASET CATALOG:
{json.dumps(catalog_entries, indent=2)}

Instructions:
1. Identify which datasets are relevant to the user's request
2. Score each match from 0.0 to 1.0 (1.0 = perfect match)
3. Return only datasets with score >= 0.7
4. List which keywords matched
5. Sort by score descending

Return JSON array with this structure:
[
  {{
    "dataset_name": "fraud_detection_models",
    "match_score": 0.95,
    "matched_keywords": ["fraud", "models"]
  }}
]

If no good matches (all < 0.7), return empty array [].
Return ONLY the JSON array, no explanation."""

    # Call Claude (lazy client creation)
    print(f"🤖 Calling Claude API...")
    print(f"   Model: claude-sonnet-4-20250514")
    print(f"   Max tokens: 1024")
    print(f"   Searching {len(datasets)} datasets for relevant matches...")
    
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
    
    # Parse Claude's response
    try:
        # Extract JSON if wrapped in markdown
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        matches_data = json.loads(response_text)
    except json.JSONDecodeError:
        # Fallback: no matches
        matches_data = []
    
    # Build full DatasetMatch objects
    matches = []
    for match_data in matches_data:
        dataset_name = match_data.get("dataset_name")
        if dataset_name in datasets:
            dataset = datasets[dataset_name]
            match = _build_dataset_match(
                dataset_name,
                dataset,
                match_data.get("match_score", 0.8),
                match_data.get("matched_keywords", [])
            )
            matches.append(match)
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    print(f"📊 Found {len(matches)} matches (score >= 0.7)")
    for m in matches[:3]:  # Show top 3
        print(f"   • {m.dataset} (score: {m.match_score:.2f})")
    print(f"⏱️  Discovery completed in {duration_ms}ms")
    print("="*60 + "\n")
    
    return DiscoveryResult(
        duration_ms=duration_ms,
        tokens=tokens_used,
        matches=matches,
        match_count=len(matches)
    )

def _build_dataset_match(dataset_name: str, dataset: dict, score: float, matched_kw: list) -> DatasetMatch:
    """Build DatasetMatch with full dataset details for frontend modal"""
    return DatasetMatch(
        dataset=dataset_name,
        id=dataset.get("id", ""),
        description=dataset.get("description", ""),
        classification=dataset.get("classification", "Unknown"),
        row_count=dataset.get("row_count", "0"),
        column_count=dataset.get("column_count", 0),
        owner=dataset.get("owner", "Unknown"),
        last_updated=dataset.get("last_updated", ""),
        contains_pii=dataset.get("contains_pii", False),
        contains_mnpi=dataset.get("contains_mnpi", False),
        pii_contractor_restriction=dataset.get("pii_contractor_restriction", False),
        keywords=dataset.get("keywords", []),
        match_score=score,
        matched_keywords=matched_kw,
        columns=dataset.get("columns")  # Include column metadata for modal
    )
