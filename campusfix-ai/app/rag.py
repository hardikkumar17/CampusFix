
import os
import chromadb

from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# --------------------------------
# 1. Project configuration
# --------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY is missing from .env")


# --------------------------------
# 2. Connect to ChromaDB
# --------------------------------

client = chromadb.PersistentClient(
    path=str(BASE_DIR / "chroma_db")
)

collection = client.get_or_create_collection(
    name="campus_maintenance"
)


# --------------------------------
# 3. Initialize Groq LLM
# --------------------------------

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0,
    reasoning_format="hidden"
)


# --------------------------------
# 4. Retrieve relevant records
# --------------------------------

def retrieve_cases(query, results_count=3):

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(results_count, collection.count())
    )

    retrieved_cases = []

    for i, document in enumerate(results["documents"][0]):

        metadata = results["metadatas"][0][i]

        retrieved_cases.append({
            "document": document,
            "metadata": metadata
        })

    return retrieved_cases


# --------------------------------
# 5. Generate grounded answer
# --------------------------------

def generate_answer(query):

    cases = retrieve_cases(query)

    if not cases:
        return "No relevant maintenance records found."

    context = ""

    for index, case in enumerate(cases, start=1):

        context += f"""
        Case {index}:
        {case['document']}

        Estimated cost: ₹{case['metadata']['estimated_cost']}
        Repair time: {case['metadata']['repair_time_hours']} hours
        Urgency: {case['metadata']['urgency']}
        """

    prompt = f"""
    You are CampusFix AI, a campus maintenance assistant.

    A user has reported this issue:
    {query}

    Here are historical maintenance records retrieved
    from the campus maintenance knowledge base:

    {context}

    Instructions:
    1. Analyze the retrieved records.
    2. Identify the most relevant evidence.
    3. Suggest a possible cause based on that evidence.
    4. Recommend a suitable next action.
    5. Mention estimated cost and repair time only as
       historical estimates, not guaranteed quotes.
    6. If the records do not provide enough evidence,
       clearly say so.
    7. Never invent maintenance history.
    8. For electrical hazards, advise isolation of the
       affected area and qualified professional inspection.

    Format your answer with:
    - Likely cause
    - Supporting evidence
    - Recommended action
    - Estimated cost and time
    - Urgency
    """

    response = llm.invoke(prompt)

    return response.content


# --------------------------------
# 6. Test the complete RAG pipeline
# --------------------------------

if __name__ == "__main__":

    complaint = "The projector in my classroom is not turning on."

    print("\nUSER COMPLAINT:")
    print(complaint)

    print("\nGENERATING RAG RESPONSE...")

    answer = generate_answer(complaint)

    print("\nCAMPUSFIX AI RESPONSE:")
    print(answer)
