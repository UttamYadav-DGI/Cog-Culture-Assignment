from __future__ import annotations

import concurrent.futures
import csv
import io
import json
from datetime import datetime

import streamlit as st

from factcheck_core import (
    GEMINI_MODEL,
    MAX_CLAIMS,
    MAX_PAGES,
    Claim,
    configured_provider,
    extract_claims,
    extract_pdf_text,
    llm_available,
    serialize_result,
    verification_worker_count,
    verify_claim,
)


def badge(verdict: str) -> str:
    colors = {"Verified": "#0f7b3a", "Inaccurate": "#b45f06", "False": "#b00020"}
    return (
        f"<span style='background:{colors.get(verdict, '#555')};color:white;"
        f"padding:0.2rem 0.55rem;border-radius:999px;font-size:0.82rem'>{verdict}</span>"
    )


def render_fact_box(title: str, fact: dict) -> None:
    if not fact:
        return
    lines = []
    for key in ["subject", "relationship", "object", "time", "quantity"]:
        value = fact.get(key)
        if value:
            lines.append(f"**{key.title()}**: {value}")
    qualifiers = fact.get("qualifiers")
    if qualifiers:
        lines.append(f"**Qualifiers**: {', '.join(str(item) for item in qualifiers)}")
    if lines:
        st.markdown(f"**{title}**")
        st.markdown("  \n".join(lines))


def render_result(result: dict) -> None:
    with st.container(border=True):
        st.markdown(f"{badge(result['verdict'])} **Claim {result['id']}**", unsafe_allow_html=True)
        st.write(result["claim"])
        st.caption(
            f"Page {result['page']} | {result['type']} | Confidence: {result['confidence']} | "
            f"Semantic relation: {result.get('semantic_relation', 'unknown')} | "
            f"LLM used: {'yes' if result.get('llm_used') else 'no'}"
        )
        st.write(result["reason"])
        contradictions = result.get("contradictions") or []
        if contradictions:
            st.warning("\n".join(f"- {item}" for item in contradictions))
        if result["verdict"] != "Verified":
            st.info(result["correct_fact"])
        with st.expander("Semantic analysis"):
            render_fact_box("Claim fact", result.get("claim_fact", {}))
            render_fact_box("Evidence fact", result.get("evidence_fact", {}))
            st.markdown("**Weak matching signals, not final verdict logic**")
            st.json(result.get("weak_matching_signals", {}))
        with st.expander("Evidence and query"):
            st.code(result["search_query"], language="text")
            if not result["sources"]:
                st.write("No sources returned.")
            for source in result["sources"]:
                st.markdown(f"- [{source.title}]({source.url})  \n  `{source.source}` - {source.snippet}")


def csv_export(results: list[dict]) -> bytes:
    rows = []
    for result in results:
        rows.append(
            {
                "verdict": result["verdict"],
                "confidence": result["confidence"],
                "semantic_relation": result.get("semantic_relation", ""),
                "llm_used": result.get("llm_used", False),
                "page": result["page"],
                "claim": result["claim"],
                "type": result["type"],
                "pdf_values": result["values_found_in_pdf"],
                "reason": result["reason"],
                "contradictions": " | ".join(result.get("contradictions") or []),
                "correct_fact": result["correct_fact"],
                "sources": " | ".join(source.url for source in result["sources"]),
            }
        )
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()) if rows else [])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def run_verification(claims: list[Claim]) -> list[dict]:
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=verification_worker_count()) as executor:
        futures = {executor.submit(verify_claim, claim): claim for claim in claims}
        for future in concurrent.futures.as_completed(futures):
            claim = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(
                    {
                        "id": claim.id,
                        "page": claim.page,
                        "claim": claim.text,
                        "type": claim.kind,
                        "values_found_in_pdf": ", ".join(claim.values),
                        "search_query": claim.query,
                        "verdict": "False",
                        "confidence": "Low",
                        "semantic_relation": "no_support",
                        "claim_fact": {},
                        "evidence_fact": {},
                        "contradictions": [f"Verification failed: {exc}"],
                        "reason": f"Verification failed: {exc}",
                        "correct_fact": "No supported replacement fact found.",
                        "llm_used": False,
                        "weak_matching_signals": {},
                        "sources": [],
                    }
                )
    return sorted(results, key=lambda item: item["id"])


def main() -> None:
    st.set_page_config(page_title="Fact-Check Agent", page_icon="✓", layout="wide")
    st.title("Fact-Check Agent")
    st.caption("Upload a PDF. The app extracts factual claims, searches live web evidence, and uses semantic contradiction reasoning.")

    with st.sidebar:
        st.header("Settings")
        st.write(f"Checks up to {MAX_PAGES} pages and {MAX_CLAIMS} claims per PDF.")
        st.write("Set `GEMINI_API_KEY` for Gemini semantic adjudication.")
        st.write("Optional: set `TAVILY_API_KEY` for stronger live search.")
        st.divider()
        st.write("Semantic verifier")
        st.write(f"Provider: `{configured_provider()}`")
        st.write(f"LLM enabled: {'yes' if llm_available() else 'no'}")
        st.write(f"Gemini model: `{GEMINI_MODEL}`")
        st.divider()
        st.write("Verdicts")
        st.write("Verified: evidence entails the full claim.")
        st.write("Inaccurate: evidence shows a related but materially wrong or outdated claim.")
        st.write("False: evidence contradicts the claim or does not support it.")

    uploaded = st.file_uploader("PDF to fact-check", type=["pdf"])
    if not uploaded:
        st.stop()

    with st.spinner("Reading PDF and extracting claims..."):
        pages = extract_pdf_text(uploaded)
        claims = extract_claims(pages)

    if not pages:
        st.error("No selectable text was found in this PDF. OCR is not enabled in this lightweight deployment.")
        st.stop()
    if not claims:
        st.warning("No checkable statistical, date, financial, or technical claims were found.")
        st.stop()

    st.subheader("Extracted Claims")
    st.dataframe(
        [{"id": c.id, "page": c.page, "type": c.kind, "claim": c.text, "values": ", ".join(c.values)} for c in claims],
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Run semantic fact-check", type="primary"):
        progress = st.progress(0)
        status = st.empty()
        results: list[dict] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=verification_worker_count()) as executor:
            futures = {executor.submit(verify_claim, claim): claim for claim in claims}
            for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
                claim = futures[future]
                status.write(f"Semantically verifying claim {claim.id}/{len(claims)}...")
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append(
                        {
                            "id": claim.id,
                            "page": claim.page,
                            "claim": claim.text,
                            "type": claim.kind,
                            "values_found_in_pdf": ", ".join(claim.values),
                            "search_query": claim.query,
                            "verdict": "False",
                            "confidence": "Low",
                            "semantic_relation": "no_support",
                            "claim_fact": {},
                            "evidence_fact": {},
                            "contradictions": [f"Verification failed: {exc}"],
                            "reason": f"Verification failed: {exc}",
                            "correct_fact": "No supported replacement fact found.",
                            "llm_used": False,
                            "weak_matching_signals": {},
                            "sources": [],
                        }
                    )
                progress.progress(index / len(claims))
        st.session_state["results"] = sorted(results, key=lambda item: item["id"])
        status.write("Verification complete.")

    if "results" in st.session_state:
        results = st.session_state["results"]
        counts = {verdict: sum(1 for result in results if result["verdict"] == verdict) for verdict in ["Verified", "Inaccurate", "False"]}
        cols = st.columns(3)
        cols[0].metric("Verified", counts.get("Verified", 0))
        cols[1].metric("Inaccurate", counts.get("Inaccurate", 0))
        cols[2].metric("False", counts.get("False", 0))

        st.download_button(
            "Download CSV report",
            data=csv_export(results),
            file_name=f"fact_check_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

        st.subheader("Report")
        for result in results:
            render_result(result)

        st.subheader("Machine-readable JSON")
        st.code(json.dumps([serialize_result(result) for result in results], indent=2), language="json")


if __name__ == "__main__":
    main()
