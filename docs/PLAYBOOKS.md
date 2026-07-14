# Category Manager Playbooks

Short operating guides to embed ProcureIQ into weekly/monthly rhythms.

---

## Playbook A — Weekly compliance huddle (20 min)

1. Open **Executive Trend** → note off-contract and maverick deltas MoM.
2. Open **Spend Cube** → filter Indirect first (usually higher maverick).
3. Export top off-contract suppliers → assign owners.
4. Action standard: move next requisition to preferred catalog / contract.

**Success metric:** +2–3 pts contract compliance in 2 quarters.

---

## Playbook B — Rate leakage deep dive (45 min)

1. Open **Leakage & TCO** → opportunity stack.
2. Rank suppliers by `rate_leakage`.
3. Validate sample invoices: paid price vs contract rate card.
4. Split root causes: system price not updated / freights rolled in / wrong UOM / true market move.
5. Feed confirmed leakage into negotiation agenda.

**Success metric:** Recover ≥30% of positive rate leakage within 2 renewal cycles.

---

## Playbook C — Should-cost challenge (Strategic Sourcing)

1. Sort categories by `should_cost_gap`.
2. Compare engineering model confidence vs spend concentration.
3. For high gap + high confidence → RFx or redesign.
4. For high gap + low confidence → refresh should-cost inputs (commodity indices).

---

## Playbook D — Supplier risk review

1. Scatter: risk score vs spend.
2. Prioritize **High risk + High spend**.
3. Dual-source plan for concentration risk; QBRs for operational risk; commercial cleanup for leakage-driven risk.

---

## Playbook E — Ask before you ticket

Before opening an analytics ticket, try **Ask ProcureIQ**:

- “What is contract compliance?”
- “Where is rate leakage highest?”
- “Which suppliers are high risk?”

If the semantic answer isn’t enough, escalate with the SQL the tool already generated — cuts analyst back-and-forth.