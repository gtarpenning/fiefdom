# Task 9: North-Star Conversation Behavior (NYC Scenario)

## Objective
Validate that Cupbearer behaves as a smart, interesting assistant in a realistic planning conversation without implementing downstream task systems locally.

## Scope
- Define NYC planning conversation scenario as an agent-layer acceptance behavior.
- Verify the assistant:
  - asks clarifying constraints
  - keeps tone witty/playful but task-focused
  - proposes options with tradeoffs
  - requests confirmation for high-impact actions
  - calls external endpoints when execution is required
- Keep this as conversation quality + orchestration proof, not local workflow engine logic.

## Deliverables
- Scenario spec and fixtures for NYC conversation flow.
- Policy/persona assertions for response quality.
- Endpoint-call assertions for execution steps.

## Acceptance Criteria
- Scenario demonstrates personality + utility consistently.
- Action-taking steps are routed through external endpoints only.
- All outputs and actions remain traceable to source events and policy decisions.
