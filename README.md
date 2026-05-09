# Fact-Check Agent

Fact-Check Agent is a Streamlit web app for automated PDF fact-checking. It acts as a lightweight "truth layer" for marketing documents, reports, pitch decks, and other PDFs that may contain outdated, unsupported, or hallucinated statistics.

Users upload a PDF, the app extracts factual claims, searches live web evidence, and produces a claim-by-claim report with verdicts, sources, and corrected facts where possible.

## Project Objective

Marketing content often includes claims such as:

- "The market is worth $500 billion in 2024."
- "The product has 99.9% uptime."
- "The company has 20 million users."
- "Revenue grew 45% year over year."
- "This standard was released in 2023."

These claims can become stale or may be fabricated. This app helps identify those risks by checking the PDF against live web data.

## Core Features

- Upload a PDF through a simple web interface.
- Extract claims containing statistics, dates, financial figures, and technical figures.
- Generate targeted search queries for each extracted claim.
- Search the live web for corroborating evidence.
- Compare PDF values against values found in search evidence.
- Classify each claim as `Verified`, `Inaccurate`, or `False`.
- Show supporting links and snippets for every checked claim.
- Provide corrected or closest matching facts when the PDF claim appears inaccurate.
- Download a CSV report.
- View a machine-readable JSON report.

## Verdict Definitions

| Verdict | Meaning |
| --- | --- |
| `Verified` | The claim value in the PDF matches evidence found online. |
| `Inaccurate` | Related evidence exists, but the PDF value does not match the live web evidence. |
| `False` | No useful corroborating evidence was found for the claim. |

## Tech Stack

- Python
- Streamlit
- pypdf
- Requests
- BeautifulSoup
- DuckDuckGo HTML search fallback
- Optional Tavily Search API integration

## Project Structure

```text
.
├── app.py                  # Main Streamlit application
├── requirements.txt        # Python dependencies
├── README.md               # Project documentation
├── render.yaml             # Render deployment config
├── Procfile                # Process file for web deployment platforms
├── runtime.txt             # Python runtime version for deployment
├── .gitignore              # Files ignored by git
└── .streamlit/
    └── config.toml         # Streamlit config
```

## How It Works

### 1. PDF Text Extraction

The app reads the uploaded PDF using `pypdf`. It extracts selectable text from up to 25 pages by default.

Current limitation: scanned image-only PDFs require OCR, which is not included in this lightweight version.

### 2. Claim Extraction

The app scans PDF sentences and selects claims that contain measurable values, including:

- Percentages
- Money values
- Millions, billions, and trillions
- Years and quarters
- User, customer, employee, revenue, and download figures

Examples of extracted claim types:

- `financial`
- `statistic`
- `date`
- `technical`
- `figure`

### 3. Web Verification

For each claim, the app builds a search query from:

- Important keywords in the claim
- Numeric values in the claim
- Context terms such as `official source latest`

The app first uses Tavily if `TAVILY_API_KEY` is configured. If no Tavily key is present, it falls back to DuckDuckGo HTML search.

### 4. Evidence Comparison

The app extracts values from search result titles and snippets, then compares them with the PDF values.

The comparison supports:

- Exact textual matches
- Numeric matches with small tolerance
- Equivalent scaled numbers such as million, billion, trillion, `m`, `bn`, and `k`

### 5. Report Generation

The app displays:

- Extracted claims table
- Verdict counts
- Claim-level explanation
- Evidence links
- Search query used
- Correct or closest matching fact when available
- CSV download
- JSON output

## Run Locally

### Run the Streamlit app locally

From the project folder, install the Streamlit dependencies:

```bash
cd /Users/uttamyadav/Desktop/assignmentttt
python3 -m pip install -r requirements-streamlit.txt
python3 -m streamlit run app.py
```

Open the app in your browser:

```text
http://localhost:8501
```

If Streamlit chooses another port, use the URL printed in the terminal.

### Run the Vercel version locally

The Vercel deployment uses the static frontend in `public/index.html` and the serverless API in `api/factcheck.py`.

Install the Vercel dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Then use the Vercel CLI:

```bash
npx vercel dev
```

The local Vercel URL is usually `http://localhost:3000`.

## Environment Variables

The app works without paid API keys by using DuckDuckGo fallback search.

For semantic contradiction reasoning, set a Gemini API key. The semantic verifier uses Gemini only.

Gemini:

```bash
FACTCHECK_LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MAX_TOKENS=1600
FACTCHECK_MAX_WORKERS=1
```

For better and more reliable search results, set:

```bash
TAVILY_API_KEY=your_tavily_api_key
```

On Streamlit Cloud, add this under app secrets:

```toml
FACTCHECK_LLM_PROVIDER = "gemini"
GEMINI_API_KEY = "your_gemini_api_key"
GEMINI_MAX_TOKENS = "1600"
FACTCHECK_MAX_WORKERS = "1"
TAVILY_API_KEY = "your_tavily_api_key"
```

## Deployment

Deployment is mandatory for the assignment. The app is prepared for both Streamlit Community Cloud and Render.

### Deploy on Streamlit Community Cloud

1. Push this project to a GitHub repository.
2. Go to <https://share.streamlit.io/>.
3. Click `New app`.
4. Select the repository.
5. Set the main file path to:

```text
app.py
```

6. Deploy the app.
7. Optional: add `TAVILY_API_KEY` in Streamlit secrets for stronger live search.

### Deploy on Render

This repository includes `render.yaml`, `Procfile`, and `runtime.txt`.

Manual Render settings:

```text
Build Command: pip install -r requirements-streamlit.txt
Start Command: streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

The included `render.yaml` uses:

```yaml
services:
  - type: web
    name: fact-check-agent
    env: python
    plan: free
    buildCommand: pip install -r requirements-streamlit.txt
    startCommand: streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

### Deploy on Vercel

This project also includes a Vercel-compatible implementation:

- `public/index.html` provides the upload interface.
- `api/factcheck.py` provides the Python serverless fact-check API.
- `vercel.json` routes `/api/factcheck` to the API and all other paths to the frontend.

Deploy with:

```bash
npx vercel --prod
```

Set `TAVILY_API_KEY` in Vercel project environment variables for stronger live search.
Set `GEMINI_API_KEY` plus `FACTCHECK_LLM_PROVIDER=gemini` to enable Gemini semantic contradiction detection.

## Usage Guide

1. Open the deployed app URL.
2. Upload a PDF.
3. Review the extracted claims table.
4. Click `Run live fact-check`.
5. Review the verdict summary.
6. Expand each claim to inspect evidence and source links.
7. Download the CSV report if needed.

## Example Output

For each claim, the app returns a structured result similar to:

```json
{
  "verdict": "Inaccurate",
  "confidence": "Medium",
  "page": 2,
  "claim": "The company generated $50 billion in revenue in 2024.",
  "type": "financial",
  "pdf_values": "$50 billion, 2024",
  "reason": "Related sources were found, but the specific value in the PDF did not match the web evidence.",
  "correct_fact": "Closest values found online: $42.1 billion, 2024.",
  "sources": ["https://example.com/source"]
}
```

## Evaluation Notes

The evaluator can test the app with a "Trap Document" containing false or outdated claims. The app is designed to flag suspicious claims by:

- Extracting measurable statements from the PDF.
- Searching current web evidence.
- Comparing numeric and date values.
- Highlighting mismatches instead of silently accepting the PDF.

The best trap-document results will come from claims with public web evidence, such as company revenue, market size, launch dates, user counts, or technical specifications.

## Limitations

- The app does not perform OCR on scanned PDFs.
- Search snippets may be incomplete or unavailable depending on the source.
- DuckDuckGo fallback search can be less reliable than a dedicated search API.
- Some claims require human judgment or full-page source reading.
- The app uses deterministic heuristics rather than a paid LLM by default.
- Highly ambiguous claims may be marked `False` if search results do not contain enough supporting context.

## Recommended Improvements

For a production-grade version:

- Add OCR with Tesseract or a cloud OCR service.
- Add LLM-based claim extraction and evidence adjudication.
- Fetch and parse full source pages, not only snippets.
- Prefer official sources and government or company filings.
- Add citation ranking and source trust scoring.
- Add authentication and persistent report history.
- Add background jobs for large PDFs.

## Why This Approach

This implementation avoids mandatory paid APIs while still delivering a complete deployed web workflow. It is suitable for assignment evaluation because it provides:

- A working upload interface.
- Automated claim extraction.
- Live web verification.
- Clear verdict labels.
- Evidence links.
- Downloadable reporting.

For stronger accuracy in deployed testing, configure `TAVILY_API_KEY` so the app has more reliable search evidence than the free fallback.
