"""
Simple car insurance chatbot proof‑of‑concept.

This Streamlit application provides a very basic conversational
interface for answering common questions about car insurance
coverage and example policy plans.  It is deliberately minimal
and uses a small in‑memory data store with fictional plans to
demonstrate how an insurance agent could leverage a chatbot to
educate customers.  The chatbot does **not** rely on any
external API calls; all responses are produced locally based on
keywords found in the user's question.  The definitions for
insurance concepts were summarised from publicly available
Filipino car insurance resources【88305912757905†L115-L136】【388055955070738†L88-L110】.

To run locally:

```
pip install -r requirements.txt
streamlit run app.py
```

When deployed on Streamlit Cloud the requirements file must be
present in the same repository.  See the README in this
project's root for deployment instructions.
"""

import re
from pathlib import Path
import streamlit as st


# -----------------------------------------------------------------------------
# Data definitions
# -----------------------------------------------------------------------------

# Explanatory definitions for different types of coverage.  These strings are
# intentionally concise and paraphrased from reputable Filipino car insurance
# guides to give customers a high‑level overview.  See the cited
# articles for more detail.【88305912757905†L115-L136】【388055955070738†L88-L110】
COVERAGE_DEFINITIONS = {
    "ctpl": (
        "**Compulsory Third Party Liability (CTPL)** is the only form of car"
        " insurance required by law in the Philippines.  It pays for injuries or"
        " death you cause to someone outside your vehicle – for example a"
        " pedestrian, passenger in another car or a non‑family member.  The LTO"
        " requires CTPL before a vehicle can be registered and a standard"
        " policy typically covers up to PHP 100,000【388055955070738†L96-L110】."
    ),
    "own damage": (
        "**Own Damage** coverage pays to repair or replace your vehicle if it"
        " is damaged or stolen.  It is optional but strongly recommended"
        " because CTPL only covers third parties and will not pay for your own"
        " car【88305912757905†L115-L136】.  Policies often have a deductible you must"
        " pay before the insurer covers the remaining cost."
    ),
    "acts of god": (
        "**Acts of God (Acts of Nature)** coverage protects you from"
        " losses caused by natural calamities such as typhoons, floods or"
        " earthquakes【88305912757905†L138-L150】.  Some policies cover volcanic eruptions and"
        " landslides as well【388055955070738†L188-L204】.  Acts of God coverage is usually"
        " an optional add‑on and costs vary by vehicle value."
    ),
    "personal accident": (
        "**Personal Accident** coverage pays for medical expenses, disability"
        " benefits and accidental death benefits for the driver and passengers"
        " of the insured vehicle【88305912757905†L153-L161】.  Some policies specify a"
        " fixed benefit per passenger while others provide a lump sum."
    ),
    "malicious mischief": (
        "**Acts of Malicious Mischief** coverage pays to repair your car if it"
        " is intentionally damaged by someone else.  Examples include"
        " vandalism, keying the paint or damage caused by riots or civil unrest"
        "【88305912757905†L163-L172】."
    ),
    "roadside assistance": (
        "**Roadside Assistance** covers services such as towing, fuel delivery and"
        " jump‑starting your vehicle when it breaks down.  Some policies also"
        " include emergency medical evacuation【88305912757905†L174-L181】."
    ),
    "loss of use": (
        "**Loss of Use** coverage reimburses you for the cost of renting a"
        " replacement vehicle while your insured car is being repaired due to a"
        " covered accident or theft【88305912757905†L184-L191】.  Policies specify daily"
        " and maximum limits."
    ),
}


# Fictional policy plans.  Each entry contains a friendly name, premium,
# description and a list of included coverage types.  The premiums and
# coverage limits are purely illustrative and **not** actual quotations.
POLICY_PLANS = {
    "Basic": {
        "premium": 1800,
        "description": (
            "Our entry‑level plan provides legally required CTPL protection and"
            " offers affordable peace of mind for budget‑conscious drivers."
        ),
        "coverage": ["ctpl"],
        "limits": {
            "ctpl": 100_000,
        },
    },
    "Standard": {
        "premium": 7500,
        "description": (
            "A balanced plan that adds own damage and Acts of God coverage on top"
            " of CTPL.  Ideal for drivers who want broader protection without"
            " paying for all the bells and whistles."
        ),
        "coverage": ["ctpl", "own damage", "acts of god"],
        "limits": {
            "ctpl": 100_000,
            "own damage": 400_000,
            "acts of god": 300_000,
        },
    },
    "Premium": {
        "premium": 14000,
        "description": (
            "Our most comprehensive plan which includes all available coverage"
            " types.  Perfect for new or high‑value vehicles and for owners who"
            " want maximum peace of mind."
        ),
        "coverage": [
            "ctpl",
            "own damage",
            "acts of god",
            "personal accident",
            "malicious mischief",
            "roadside assistance",
            "loss of use",
        ],
        "limits": {
            "ctpl": 100_000,
            "own damage": 800_000,
            "acts of god": 600_000,
            "personal accident": 200_000,
            "malicious mischief": 300_000,
            "roadside assistance": 0,  # Service benefit rather than monetary limit
            "loss of use": 2_500,  # daily reimbursement limit
        },
    },
}


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

def format_currency(amount: int) -> str:
    """Return a string with the amount formatted as Philippine pesos."""
    return f"PHP {amount:,.0f}"


def plan_info(plan_name: str) -> str:
    """Construct a detailed description of a given policy plan."""
    plan = POLICY_PLANS[plan_name]
    lines = [f"**{plan_name} Plan**"]
    lines.append(plan["description"])
    lines.append("")
    # List included coverage
    coverage_list = [c.title() if c != "ctpl" else "CTPL" for c in plan["coverage"]]
    lines.append("Included coverage: " + ", ".join(coverage_list) + ".")
    # Premium
    lines.append(f"Annual premium: {format_currency(plan['premium'])}.")
    # Coverage limits
    limit_lines = []
    for cov, limit in plan["limits"].items():
        if cov == "roadside assistance":
            limit_lines.append("Roadside assistance: service included")
        elif cov == "loss of use":
            limit_lines.append(
                f"Loss of use: reimbursed up to {format_currency(limit)} per day"
            )
        else:
            limit_lines.append(f"{cov.title() if cov != 'ctpl' else 'CTPL'}: {format_currency(limit)} limit")
    lines.append("Coverage limits: " + "; ".join(limit_lines) + ".")
    return "\n".join(lines)


def answer_question(question: str) -> str:
    """Generate a response based on the user's question.

    The logic here is intentionally simple and keyword‑driven.  It scans the
    question for known plan names, coverage types and keywords such as 'price'
    or 'premium' and returns appropriate information.  If nothing matches it
    provides a friendly default response.
    """
    q = question.lower()
    # Check for definitions of coverage types
    for cov_key, definition in COVERAGE_DEFINITIONS.items():
        # Accept variations of the keyword (e.g. acts of god, act of god)
        pattern = cov_key.replace(" ", "|")  # simple variation
        if re.search(pattern, q):
            return definition
    # Check for plan names
    for plan_name in POLICY_PLANS:
        if plan_name.lower() in q:
            return plan_info(plan_name)
    # Check for price/cost queries
    if any(word in q for word in ["price", "cost", "premium", "rates"]):
        lines = ["Here are the annual premiums for our available plans:"]
        for name, plan in POLICY_PLANS.items():
            lines.append(f"- **{name} Plan**: {format_currency(plan['premium'])}")
        lines.append("\nAsk about a specific plan to see what it covers.")
        return "\n".join(lines)
    # General coverage query
    if any(word in q for word in ["coverage", "covered", "benefits"]):
        # Provide a high level summary of all coverage definitions
        lines = [
            "We offer several types of coverage.  Here's a quick overview:",
        ]
        for cov_key, definition in COVERAGE_DEFINITIONS.items():
            # Extract the first sentence before the first period as a summary
            summary = definition.split(".")[0] + "."
            lines.append(f"- {summary}")
        lines.append(
            "\nYou can ask about any of these coverage types for more information or"
            " inquire about a specific plan."
        )
        return "\n".join(lines)
    # Fallback
    return (
        "I'm sorry, I don't have an answer to that yet.  You can ask me about"
        " car insurance coverage, premiums or one of our plans (Basic, Standard"
        " or Premium)."
    )


# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------

def main() -> None:
    """Render the Streamlit application."""
    st.set_page_config(
        page_title="Car Insurance Chatbot Demo",
        page_icon="🚗",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Header image
    # Locate the header illustration relative to this script
    header_path = Path(__file__).parent / "static" / "header.png"
    if header_path.exists():
        st.image(str(header_path), use_column_width=False, width=350)
    st.title("Car Insurance Chatbot")
    st.write(
        "Ask me about car insurance coverage, example policy plans or premiums."
        "\nThis demo uses fictional data and should not be used as a real quote."
    )

    # Initialize session state for chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display existing messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    user_input = st.chat_input("Type your question here...")
    if user_input:
        # Append user's message to history
        st.session_state.messages.append({"role": "user", "content": user_input})
        # Generate reply
        reply = answer_question(user_input)
        st.session_state.messages.append({"role": "assistant", "content": reply})
        # Display user's message and reply immediately
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            st.markdown(reply)


if __name__ == "__main__":
    main()