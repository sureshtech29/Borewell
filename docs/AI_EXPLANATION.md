# AI report explanation

## What it does

The report page includes an optional AI action that explains an existing Borewell Water Finder analysis in plain English or Telugu. The AI receives a restricted subset of the report: potential classification, confidence, factors, nearby evidence, documented depth evidence, data gaps, recommendations, warnings, source metadata, data mode, and report timestamp.

The API removes exact latitude/longitude and unrelated fields before sending the prompt to the configured provider. The API key stays on the backend and is never exposed to browser code. Requests are limited to eight per client per hour.

## Configure a provider

The implementation uses the OpenAI-compatible `/chat/completions` API shape. Set these values in the server-side `.env` file:

```dotenv
AI_PROVIDER=openai-compatible
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
AI_API_KEY=your-server-side-api-key
```

Use a provider/model that supports this API shape. `AI_BASE_URL` may be changed for a compatible provider. Never put the secret in a `VITE_` variable, source control, or frontend code.

Restart the API:

```bash
docker compose up --build -d api
```

Without `AI_API_KEY`, the endpoint reports `not_configured` and the UI explains that the administrator must configure it.

## Accuracy and safety limits

- AI explains the existing analytical result; it does not recalculate the groundwater score or make a new site prediction.
- It cannot validate a source dataset, measure groundwater, identify a fracture, or confirm that a borewell will succeed.
- It must not invent drilling depth, discharge/yield, water level, water quality, dates, source citations, or success probabilities.
- Confidence in the report is evidence coverage/quality, not the probability of finding water.
- Demo-mode reports must be explicitly described as synthetic and unsuitable for drilling decisions.
- AI output can still be mistaken. Have a qualified hydrogeologist review consequential decisions.

Prediction accuracy depends on authentic and current data, appropriate spatial resolution, hydrogeological calibration, and validation against independent real borewell outcomes—not on adding a language model.
