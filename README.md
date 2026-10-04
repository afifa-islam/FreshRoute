# FreshRoute

B2B solution that connects farmers holding perishable surplus produce with
refrigerated or insulated drivers who are returning empty along highways.

For each truck, FreshRoute checks vehicle compatibility, capacity, detour,
availability and the shelf life left at delivery, then ranks the valid
matches. AI (Groq) explains the result but never overrides it.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit secrets.toml and add your GROQ_API_KEY

streamlit run app.py
```

The app works without a Groq key. Only the AI report, assistant and voice
features are disabled.

## App layout

| Tab | Purpose |
|-----|---------|
| Home | How FreshRoute works and live counts |
| Farmers | Shipment form (type or speak), truck matches, summary, map |
| Drivers | Truck registration form (type or speak), list of registered trucks |
| Assistant | Chat about the current shipment result |
| About | Plain-language explanation for users |

Both the farmer and driver forms accept an optional voice message in
English, Urdu or Roman Urdu. The message is converted to text, which fills
the form for the user to review before submitting.

## Project layout

| File | Purpose |
|------|---------|
| `app.py` | Streamlit interface (tabs, forms, results, map) |
| `core.py` | Shelf-life model, matching and scoring (no network, easy to test) |
| `services.py` | Geocoding, weather, routing, Groq LLM and speech |
| `tests/test_core.py` | Tests for the core logic: `python tests/test_core.py` |
| `.streamlit/config.toml` | Theme and server settings |

## How a match is judged

- **Detour** = truck to farm + farm to buyer + buyer to the truck's own
  destination, minus the truck's original direct trip. Limit: 15 km.
- **Shelf life** = what remains today, minus time spent waiting for pickup
  (ambient temperature) and in transit (vehicle temperature). At least
  4 hours must remain at delivery.
- **Score** = detour 30%, shelf life preserved 25%, truck fill 20%,
  temperature suitability 15%, reliability 10%.

## Limitations

The shelf-life model is a heuristic, not a validated food-safety system.
Locations are geocoded to place centres, so detours are approximate. The
public OSRM server is for prototypes; when it is unreachable, FreshRoute
falls back to clearly labelled straight-line estimates.
