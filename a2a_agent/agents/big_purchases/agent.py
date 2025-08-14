from google.adk.agents import LlmAgent

# Import data science agent to be a sub-agent
from ..data_science import root_agent as data_science_agent


def _make_sub_agents():
    selector = LlmAgent(
        name="bp_selector",
        model="gemini-2.5-flash",
        description="Identifies if the query concerns big purchases and classifies the purchase type.",
        instruction=(
            "You detect if a user is asking about large purchases (cars, appliances, home upgrades, tuition)."
            " If yes, classify the purchase type and surface key factors (budget, financing, timeline)."
        ),
    )

    advisor = LlmAgent(
        name="bp_advisor",
        model="gemini-2.5-flash",
        description="Provides guidance on budgeting, financing, and timing for big purchases.",
        instruction=(
            "Provide concise advice on budgeting, saving strategies, financing options, and timing for large purchases."
            " Use clear bullet points and short guidance."
        ),
    )

    return selector, advisor


_sub_selector, _sub_advisor = _make_sub_agents()

root_agent = LlmAgent(
    name="big_purchases_agent",
    model="gemini-2.5-flash",
    description="Coordinates sub-agents to help plan and evaluate big purchases with data analysis capabilities.",
    instruction=(
        "You orchestrate big purchase planning with data analysis support."
        " You have access to these sub-agents:"
        " 1. 'bp_selector': Identifies if queries concern big purchases and classifies purchase type."
        " 2. 'bp_advisor': Provides budgeting, financing, and timing guidance for large purchases."
        " 3. 'db_ds_multiagent': Handles data analysis, SQL queries, and data science tasks."
        " "
        " For big purchase questions: use bp_selector first, then bp_advisor for guidance."
        " For data analysis, reporting, or SQL queries: delegate to 'db_ds_multiagent'."
        " Keep responses concise and actionable."
    ),
    sub_agents=[_sub_selector, _sub_advisor, data_science_agent],
)


