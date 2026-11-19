
import re
from typing import TypedDict, List, Dict, Any

from langgraph.graph import StateGraph, START, END

from app.agents import diagnosis_agent, recommendation_agent
from app.rag import retrieve_cases


# --------------------------------
# 1. Shared agent state
# --------------------------------

class CampusState(TypedDict):
    complaint: str
    retrieved_cases: List[Dict[str, Any]]
    diagnosis: str
    recommendation: str
    activities: List[Dict[str, Any]]
    decision: Dict[str, Any]


# --------------------------------
# 2. Retrieval node
# --------------------------------

def retrieval_node(state: CampusState):

    activities = list(state.get("activities", []))

    cases = retrieve_cases(state["complaint"])

    activities.append({
        "stage": "RAG Retrieval",
        "status": "completed",
        "details": (
            f"Retrieved {len(cases)} historical maintenance "
            "cases from ChromaDB."
        )
    })

    return {
        "retrieved_cases": cases,
        "activities": activities
    }


# --------------------------------
# 3. Diagnosis node
# --------------------------------

def diagnosis_node(state: CampusState):

    activities = list(state.get("activities", []))

    activities.append({
        "stage": "Diagnosis Agent",
        "status": "running",
        "details": "Analysing the complaint using historical evidence."
    })

    result = diagnosis_agent(state)

    activities[-1]["status"] = "completed"
    activities[-1]["details"] = (
        "Diagnosis generated successfully by Groq."
    )

    return {
        "diagnosis": result["diagnosis"],
        "activities": activities
    }


# --------------------------------
# 4. Recommendation node
# --------------------------------

def recommendation_node(state: CampusState):

    activities = list(state.get("activities", []))

    activities.append({
        "stage": "Recommendation Agent",
        "status": "running",
        "details": "Generating maintenance recommendations."
    })

    result = recommendation_agent(state)

    activities[-1]["status"] = "completed"
    activities[-1]["details"] = (
        "Recommendation generated successfully by Groq."
    )

    return {
        "recommendation": result["recommendation"],
        "activities": activities
    }


# --------------------------------
# 5. Decision Engine
# --------------------------------

def decision_node(state: CampusState):

    activities = list(state.get("activities", []))

    recommendation = state.get("recommendation", "")
    complaint = state.get("complaint", "").lower()

    # --------------------------------
    # Check for explicit immediate danger
    # --------------------------------

    emergency_phrases = [
        "electric shock",
        "is receiving an electric shock",
        "sparking",
        "is sparking",
        "smoke is coming",
        "smoke coming from",
        "active fire",
        "fire has started",
        "exposed live wire",
        "live wire exposed",
        "burning smell",
        "flames coming from"
    ]

    confirmed_emergency = any(
        phrase in complaint for phrase in emergency_phrases
    )

    if confirmed_emergency:

        urgency = "Critical"
        priority = "Emergency"
        action = (
            "Potential immediate safety hazard reported. "
            "Restrict access to the affected area and contact "
            "qualified maintenance personnel immediately."
        )

    else:

        # --------------------------------
        # Detect possible hazards in original complaint
        # --------------------------------

        possible_hazard_phrases = [
            "fire hazard",
            "potential fire",
            "may pose a fire hazard",
            "risk of fire",
            "possible fire",
            "suspected overheating",
            "overheating",
            "faulty power supply",
            "possible electrical fault",
            "electrical hazard",
            "could cause a fire",
            "consider temporarily removing",
            "burning smell",
            "electrical fault",
            "power supply smoking",
            "equipment is hot",
            "sparking",
            "smoke coming from"
        ]

        possible_hazard = any(
            phrase in complaint
            for phrase in possible_hazard_phrases
        )

        # --------------------------------
        # Remove Markdown formatting
        # --------------------------------

        clean_recommendation = re.sub(
            r"[*_`#]",
            "",
            recommendation
        )

        # --------------------------------
        # Read recommendation urgency
        # Supports:
        # URGENCY: Medium
        # URGENCY: - Medium
        # URGENCY - Medium
        # URGENCY High
        # --------------------------------

        urgency_match = re.search(
            r"\burgency\b\s*:?\s*[-–—]?\s*"
            r"(critical|high|medium|low)\b",
            clean_recommendation,
            re.IGNORECASE
        )

        detected_urgency = (
            urgency_match.group(1).lower()
            if urgency_match
            else None
        )

        # --------------------------------
        # Assign priority
        # --------------------------------

        if detected_urgency == "critical":

            urgency = "Critical"
            priority = "Emergency"
            action = (
                "Critical issue identified. Contact qualified "
                "maintenance personnel immediately and verify "
                "the reported hazard."
            )

        elif detected_urgency == "high":

            urgency = "High"
            priority = "High Priority"
            action = (
                "Prioritise maintenance inspection and arrange "
                "qualified staff to investigate the issue."
            )

        elif detected_urgency == "medium":

            urgency = "Medium"
            priority = "Normal Priority"
            action = (
                "Schedule maintenance within normal working hours."
            )

        elif detected_urgency == "low":

            urgency = "Low"
            priority = "Low Priority"
            action = (
                "Add this complaint to routine maintenance."
            )

        else:

            urgency = "Needs Review"
            priority = "Manual Review"
            action = (
                "Ask maintenance staff to review the complaint "
                "and confirm its urgency."
            )

        # --------------------------------
        # Possible hazards require review
        # --------------------------------

        if possible_hazard:

            urgency = "Needs Review"
            priority = "Manual Review"
            action = (
                "A possible safety concern was identified. "
                "Ask qualified maintenance staff to inspect "
                "the equipment and verify the suspected hazard "
                "before returning it to service."
            )

    # --------------------------------
    # Final decision
    # --------------------------------

    decision = {
        "urgency": urgency,
        "priority": priority,
        "next_action": action,
        "human_intervention_required": urgency in [
            "Critical",
            "High",
            "Needs Review"
        ]
    }

    activities.append({
        "stage": "Decision Engine",
        "status": "completed",
        "details": (
            f"Priority: {priority}. "
            f"Next action: {action}"
        )
    })

    return {
        "decision": decision,
        "activities": activities
    }


# --------------------------------
# 6. Build LangGraph workflow
# --------------------------------

workflow = StateGraph(CampusState)

workflow.add_node("retrieval", retrieval_node)
workflow.add_node("diagnosis", diagnosis_node)
workflow.add_node("recommendation", recommendation_node)
workflow.add_node("decision", decision_node)

workflow.add_edge(START, "retrieval")
workflow.add_edge("retrieval", "diagnosis")
workflow.add_edge("diagnosis", "recommendation")
workflow.add_edge("recommendation", "decision")
workflow.add_edge("decision", END)

app = workflow.compile()


# --------------------------------
# 7. Test complete workflow
# --------------------------------

if __name__ == "__main__":

    complaint = "The projector in my classroom is not turning on."

    result = app.invoke({
        "complaint": complaint,
        "activities": []
    })

    print("\n========== CAMPUSFIX AI ==========")

    print("\nUSER COMPLAINT:")
    print(complaint)

    print("\nAI ACTIVITIES:")

    for activity in result["activities"]:
        print(f"\n{activity['stage']}")
        print(f"Status: {activity['status']}")
        print(f"Details: {activity['details']}")

    print("\nFINAL DECISION:")
    print(result["decision"])

    print("\nDIAGNOSIS AGENT:")
    print(result["diagnosis"])

    print("\nRECOMMENDATION AGENT:")
    print(result["recommendation"])

    print("\n==================================")
