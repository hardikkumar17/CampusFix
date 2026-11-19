
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq


# --------------------------------
# 1. Load project configuration
# --------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

if not os.getenv("GROQ_API_KEY"):
    raise ValueError("GROQ_API_KEY is missing from .env")


# --------------------------------
# 2. Initialize the LLM
# --------------------------------

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    reasoning_format="hidden"
)


# --------------------------------
# 3. Diagnosis Agent
# --------------------------------

def diagnosis_agent(state: dict) -> dict:

    complaint = state["complaint"]
    retrieved_cases = state["retrieved_cases"]

    context = ""

    for index, case in enumerate(retrieved_cases, start=1):

        context += f"""
        Historical Case {index}:

        Record: {case['document']}

        Category: {case['metadata']['category']}
        Cause: {case['metadata']['cause']}
        Resolution: {case['metadata']['resolution']}
        Urgency: {case['metadata']['urgency']}
        """

    prompt = f"""
    You are the Diagnosis Agent of CampusFix AI.

    Your responsibility is to diagnose campus maintenance
    complaints using retrieved historical evidence.

    USER COMPLAINT:
    {complaint}

    RETRIEVED HISTORICAL CASES:
    {context}

    YOUR TASK:

    1. Identify possible causes of the complaint.
    2. Use historical cases as supporting evidence.
    3. Explain why the evidence is relevant.
    4. Do not invent facts or claim certainty without evidence.
    5. If evidence is insufficient, clearly mention it.
    6. Flag potentially dangerous situations.

    Return your response in this format:

    LIKELY CAUSE:
    SUPPORTING EVIDENCE:
    CONFIDENCE: High / Medium / Low
    SAFETY CONCERN:
    """

    response = llm.invoke(prompt)

    return {
        "diagnosis": response.content
    }





# --------------------------------
# 4. Recommendation Agent
# --------------------------------

def recommendation_agent(state: dict) -> dict:

    complaint = state["complaint"]
    diagnosis = state["diagnosis"]
    retrieved_cases = state["retrieved_cases"]

    context = ""

    for index, case in enumerate(retrieved_cases, start=1):

        metadata = case["metadata"]

        context += f"""
        Historical Case {index}:
        {case['document']}

        Estimated Cost: Rs. {metadata.get('estimated_cost', 'Unknown')}
        Repair Time: {metadata.get('repair_time_hours', 'Unknown')} hours
        Urgency: {metadata.get('urgency', 'Unknown')}
        Resolution: {metadata.get('resolution', 'Unknown')}
        """

    prompt = f"""
    You are the Recommendation Agent of CampusFix AI.

    USER COMPLAINT:
    {complaint}

    DIAGNOSIS FROM DIAGNOSIS AGENT:
    {diagnosis}

    HISTORICAL MAINTENANCE RECORDS:
    {context}

    YOUR TASK:
    1. Recommend practical next steps based on the diagnosis.
    2. Use historical records as supporting evidence.
    3. Estimate cost and repair time only when supported
       by retrieved records.
    4. Mention urgency based on the available evidence.
    5. Never invent costs, repair times or resolutions.
    6. For electrical hazards, recommend a qualified
       professional. Do not instruct unqualified users
       to open electrical equipment.

    Return your response using this format:

    RECOMMENDED ACTION:
    SUPPORTING HISTORICAL CASES:
    ESTIMATED COST:
    ESTIMATED REPAIR TIME:
    URGENCY:
    SAFETY PRECAUTIONS:
    """

    response = llm.invoke(prompt)

    return {
        "recommendation": response.content
    }
