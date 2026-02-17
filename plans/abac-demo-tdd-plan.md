# TDD Plan: ABAC Policy Agent Demo Redesign

## Goal
Redesign [`demo-prototype.html`](demo-prototype.html:1) Policy Agent card to show **deterministic ABAC matching** instead of vague policy checks. Make the decision-making process transparent and auditable.

## Current State Problems
1. Policy checks show `"Read + valid justification (62 chars)"` implying justification quality affects decision
2. Audit trail is raw JSON (not human-readable)
3. No visibility into *why* auto-approval happened (what user attributes matched what requirements?)
4. UI implies LLM makes policy decisions when it should be deterministic ABAC rules

## Target State
1. Policy Agent card shows **requirements → user attributes** matching side-by-side
2. Justification text is logged but NOT scored (explicit note stating this)
3. Audit trail is human-readable prose with clear decision reasoning
4. Demo reinforces "AI at the intake, rules at the core" narrative from [`live-vs-mock-strategy.md`](live-vs-mock-strategy.md:1)

---

## Data Structures

### User Attributes (from IAM/HR system)
```javascript
const USERS = {
  "analyst@visa.com": {
    name: "Sarah Chen",
    role: "Senior Data Analyst",
    employee_type: "FTE",
    org: "Risk Analytics",
    clearance_level: 3,
    training_completed: ["PII_Handling_2026", "InfoSec_Annual_2026"],
    training_dates: {"InfoSec_Annual_2026": "2026-01-15"},
    manager: "mike.foster@visa.com"
  },
  "scientist@visa.com": {
    name: "James Rodriguez",
    role: "Staff Data Scientist",
    employee_type: "FTE",
    org: "Data Science",
    clearance_level: 4,
    training_completed: ["PII_Handling_2026", "InfoSec_Annual_2026"],
    training_dates: {"InfoSec_Annual_2026": "2026-01-10"},
    manager: "director@visa.com"
  },
  "unknown@visa.com": {
    name: "Unknown User",
    role: null,
    employee_type: null,
    org: null,
    clearance_level: 0,
    training_completed: [],
    training_dates: {},
    manager: null
  }
};
```

### Dataset Requirements
```javascript
const DATASETS = {
  "fraud_detection_models": {
    id: "DS-001",
    classification: "Internal",
    contains_pii: false,
    contains_mnpi: false,
    read_roles: ["Data Analyst", "Senior Data Analyst", "Data Scientist", "Staff Data Scientist"],
    write_roles: ["Staff Data Scientist", "Principal Data Scientist"],
    admin_roles: ["Principal Data Scientist", "Director of Data Science"],
    min_clearance: 2,
    required_training: ["InfoSec_Annual_2026"]
  },
  "customer_pii_cardholder_data": {
    id: "DS-002",
    classification: "Restricted",
    contains_pii: true,
    contains_mnpi: false,
    read_roles: ["Senior Data Analyst", "Data Scientist", "Staff Data Scientist"],
    write_roles: ["Staff Data Scientist", "Principal Data Scientist"],
    admin_roles: ["Principal Data Scientist"],
    min_clearance: 3,
    required_training: ["PII_Handling_2026", "InfoSec_Annual_2026"],
    pii_contractor_restriction: true  // Contractors need manager approval even for read
  }
};
```

### ABAC Policy Rules (8 checks)
```javascript
const ABAC_POLICIES = [
  {
    name: "Role Authorization",
    check: (user, dataset, access_level) => {
      const roles_map = {read: dataset.read_roles, write: dataset.write_roles, admin: dataset.admin_roles};
      const required_roles = roles_map[access_level];
      return {
        requirement: `One of: [${required_roles.join(', ')}]`,
        user_value: user.role || "No role in system",
        match: required_roles.includes(user.role)
      };
    }
  },
  {
    name: "Clearance Level",
    check: (user, dataset) => ({
      requirement: `Minimum: Level ${dataset.min_clearance}`,
      user_value: `Level ${user.clearance_level} (verified)`,
      match: user.clearance_level >= dataset.min_clearance
    })
  },
  {
    name: "Access Level Restriction",
    check: (user, dataset, access_level) => {
      const auto_approve = (access_level === "read");
      return {
        requirement: `READ requests: auto-approve eligible`,
        user_value: `Requesting ${access_level.toUpperCase()} access`,
        match: auto_approve
      };
    }
  },
  {
    name: "PII Restriction",
    check: (user, dataset) => {
      if (!dataset.contains_pii) {
        return {requirement: "No PII in dataset", user_value: "N/A", match: true};
      }
      if (dataset.pii_contractor_restriction && user.employee_type === "Contractor") {
        return {
          requirement: "FTE only for PII datasets",
          user_value: "Contractor (requires manager approval)",
          match: false
        };
      }
      const has_training = user.training_completed.includes("PII_Handling_2026");
      return {
        requirement: "PII training required",
        user_value: has_training ? "Completed PII_Handling_2026" : "Missing PII training",
        match: has_training
      };
    }
  },
  {
    name: "Training Requirements",
    check: (user, dataset) => {
      const missing = dataset.required_training.filter(t => !user.training_completed.includes(t));
      if (missing.length === 0) {
        const latest = dataset.required_training[0];
        const date = user.training_dates[latest];
        return {
          requirement: dataset.required_training.join(", "),
          user_value: `Completed ${date}`,
          match: true
        };
      }
      return {
        requirement: dataset.required_training.join(", "),
        user_value: `Missing: ${missing.join(", ")}`,
        match: false
      };
    }
  },
  {
    name: "Employment Type",
    check: (user) => {
      const valid = ["FTE", "Contractor"].includes(user.employee_type);
      return {
        requirement: "FTE or approved contractor",
        user_value: user.employee_type ? `${user.employee_type} (verified via HR system)` : "No employment record",
        match: valid
      };
    }
  },
  {
    name: "MNPI Blackout",
    check: (user, dataset) => ({
      requirement: "Dataset not tagged MNPI",
      user_value: dataset.contains_mnpi ? "MNPI dataset (manual review required)" : `N/A - Dataset is ${dataset.classification}`,
      match: !dataset.contains_mnpi
    })
  },
  {
    name: "Time-Limited Access",
    check: () => ({
      requirement: "All access expires in 90 days",
      user_value: "Expiry will be set to LIVE_EXPIRE_SHORT",
      match: true
    })
  }
];
```

---

## Kent Beck TDD Cycles

### Cycle 1: Display ABAC checks instead of old policy rows

**Test 1.1:** Policy Agent card shows "ABAC Policy Engine" badge
```javascript
// GIVEN scenario is loaded
// WHEN policy card renders
// THEN card header shows "ABAC Policy Engine" tag instead of "Rule Engine"
```

**Test 1.2:** Each ABAC check shows requirement → user format
```javascript
// GIVEN Sarah Chen scenario (approve)
// WHEN policy checks render
// THEN each row shows:
//   Requirement: [what's needed] → User: [what user has] ✓
```

**Test 1.3:** Match indicator is visual (✓ vs ✗)
```javascript
// GIVEN check passes: match: true
// THEN shows green ✓
// GIVEN check fails: match: false
// THEN shows red ✗
```

---

### Cycle 2: Add justification note below ABAC checks

**Test 2.1:** Note explains justification is logged not scored
```javascript
// GIVEN ABAC checks rendered
// WHEN policy card complete
// THEN shows info box: "Justification text is logged for audit but not scored. Decision based on ABAC matching above."
```

**Test 2.2:** Note has info-box styling (blue background, icon)
```javascript
// GIVEN note box
// THEN has blue gradient background
// AND info icon (ⓘ)
// AND distinct from policy check rows
```

---

### Cycle 3: Human-readable audit trail

**Test 3.1:** Audit shows prose not JSON
```javascript
// GIVEN workflow completes
// WHEN audit trail renders
// THEN each entry formatted as:
//   "06:25:00 UTC | IntakeAgent | Parsed request (847 tokens, 320ms)"
//   "06:25:01 UTC | ABACPolicyEngine | Evaluated 8 policies → APPROVED (8/8 checks passed)"
```

**Test 3.2:** Failed checks show in audit
```javascript
// GIVEN deny scenario
// THEN audit shows:
//   "ABACPolicyEngine | Evaluated 8 policies → DENIED (Role Authorization: FAIL, Clearance Level: FAIL, Training: FAIL)"
```

---

### Cycle 4: Update scenario data structures

**Test 4.1:** Scenarios use abac_checks instead of policies
```javascript
// GIVEN approve scenario
// THEN has: abac_checks: [{policy, req, user, match, badge}...]
// NOT: policies: [["g","PASS","Policy Name","Description"]]
```

**Test 4.2:** All scenarios have justification_note
```javascript
// GIVEN each scenario (approve, escalate, deny)
// THEN has justification_note field with explanation text
```

---

### Cycle 5: Render ABAC checks in UI

**Test 5.1:** ABAC row shows requirement → user
```javascript
// GIVEN check: {policy:"Role Authorization", req:"One of: [...]", user:"Senior Data Analyst", match:true}
// WHEN rendered
// THEN shows: 
//   <div class="abac-row">
//     <div class="abac-req">One of: [Data Analyst, Senior Data Analyst, Data Scientist]</div>
//     <div class="abac-arrow">→</div>
//     <div class="abac-user">Senior Data Analyst <span class="check">✓</span></div>
//   </div>
```

**Test 5.2:** Failed checks show red styling
```javascript
// GIVEN match: false
// THEN user value has red ✗
// AND row has subtle red background
```

**Test 5.3:** N/A checks show gray
```javascript
// GIVEN user: "N/A"
// THEN shows gray text, no checkmark
```

---

### Cycle 6: CSS for ABAC layout

**Test 6.1:** 3-column grid (req | arrow | user)
```css
.abac-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 12px;
  padding: 8px 0;
}
```

**Test 6.2:** Requirement has subtle background
```css
.abac-req {
  background: #f9fafb;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 12px;
}
```

**Test 6.3:** Color classes for match states
```css
.abac-user.pass { color: var(--green); }
.abac-user.fail { color: var(--red); }
.abac-user.na { color: var(--text-3); }
```

---

### Cycle 7: Audit trail formatting

**Test 7.1:** Audit entry div (not pre block)
```javascript
// GIVEN audit_trail array
// WHEN render
// THEN creates <div class="audit-entry"> for each
// NOT <pre> with JSON
```

**Test 7.2:** Timestamp | agent | action format
```javascript
// GIVEN entry: {timestamp, agent, action, details}
// THEN renders: "06:25:00 UTC | IntakeAgent | parse_request (847 tokens)"
```

**Test 7.3:** Monospace timestamp alignment
```css
.audit-entry {
  font-family: var(--mono);
  font-size: 11px;
  padding: 4px 0;
  color: var(--text-2);
}
.audit-time { color: var(--text-3); }
.audit-agent { font-weight: 600; color: var(--text); }
```

---

## Edge Cases to Handle

### Edge 1: User not in USERS
```javascript
// GIVEN unknown@visa.com
// WHEN lookup user
// THEN return: {role: null, clearance_level: 0, training_completed: []}
// AND all checks show "No user record found"
```

### Edge 2: Dataset not in DATASETS
```javascript
// GIVEN dataset: "all_datasets" (not in catalog)
// WHEN lookup
// THEN intake shows error: "Dataset not in catalog"
// AND policy checks disabled
```

### Edge 3: Access level = write (escalate)
```javascript
// GIVEN access_level: "write"
// WHEN check "Access Level Restriction"
// THEN match: false
// AND requirement: "Write/Admin require manager approval"
```

### Edge 4: PII + Contractor
```javascript
// GIVEN user.employee_type: "Contractor" AND dataset.contains_pii: true
// WHEN check PII Restriction
// THEN match: false
// AND user_value: "Contractor (requires manager approval)"
```

### Edge 5: Missing training
```javascript
// GIVEN user.training_completed: []
// WHEN check Training Requirements
// THEN match: false
// AND user_value: "Missing: InfoSec_Annual_2026"
```

---

## Implementation Order (TDD Red-Green-Refactor)

### Phase 1: Data Structures (30 min)
1. Test: USERS object loads correctly → Red
2. Impl: Create USERS in demo-prototype.html → Green
3. Test: DATASETS object loads → Red
4. Impl: Create DATASETS → Green
5. Refactor: Comment structure, add lookup functions

### Phase 2: ABAC Engine Logic (45 min)
6. Test: Role Authorization check returns {req, user, match} → Red
7. Impl: Write checkRoleAuthorization() → Green
8. Test: All 8 checks return correct structure → Red (one at a time)
9. Impl: Write all 8 check functions → Green
10. Refactor: DRY up check patterns

### Phase 3: Update Scenario Data (30 min)
11. Test: approve scenario has abac_checks array → Red
12. Impl: Replace policies with abac_checks → Green
13. Test: All 3 scenarios updated → Red
14. Impl: Update escalate and deny scenarios → Green
15. Refactor: Verify all scenarios consistent

### Phase 4: UI Rendering (1 hour)
16. Test: ABAC row renders with 3 columns → Red
17. Impl: Build HTML structure → Green
18. Test: Checkmark/X appears based on match → Red
19. Impl: Add conditional rendering → Green
20. Test: All 8 checks display → Red
21. Impl: Loop through abac_checks → Green
22. Test: Justification note appears → Red
23. Impl: Add note box → Green
24. Refactor: Clean up CSS classes

### Phase 5: Audit Trail (30 min)
25. Test: Audit shows prose not JSON → Red
26. Impl: Format as string "time | agent | action" → Green
27. Test: Policy decision shows pass/fail details → Red
28. Impl: Add decision summary → Green
29. Refactor: Extract formatAuditEntry()

### Phase 6: Integration & Polish (30 min)
30. Test: Sarah Chen end-to-end → Red
31. Impl: Wire all pieces together → Green
32. Test: James Rodriguez (escalate) → Red
33. Impl: Verify escalation logic → Green
34. Test: Unknown user (deny) → Red
35. Impl: Verify deny logic → Green
36. Final refactor: Remove old code, comments, consistency

---

## Acceptance Criteria

### ✅ Policy Agent Card
- [ ] Shows "ABAC Policy Engine" tag
- [ ] 8 checks in requirement → user format
- [ ] Visual match indicators (✓/✗)
- [ ] Justification note with clear explanation
- [ ] Color coding: green/red/gray

### ✅ Audit Trail
- [ ] Human-readable prose (not JSON)
- [ ] Format: timestamp | agent | action
- [ ] Shows pass/fail details
- [ ] Monospace alignment

### ✅ Data Accuracy
- [ ] Sarah Chen: 8/8 checks pass → APPROVE
- [ ] James Rodriguez: PII check fails → ESCALATE
- [ ] Unknown user: Role, clearance, training fail → DENY
- [ ] Justification logged but not scored

### ✅ Code Quality
- [ ] Data-driven (USERS, DATASETS, ABAC_POLICIES)
- [ ] Clear separation: data/logic/UI
- [ ] No dead code
- [ ] Comments explain ABAC logic

---

## Success Metrics

1. **Narrative alignment**: Reinforces "AI at the intake, rules at the core" from [`live-vs-mock-strategy.md`](live-vs-mock-strategy.md:60)
2. **Demo clarity**: Viewer sees deterministic matching, not black-box decisions
3. **Auditability**: Every decision traceable to specific ABAC rule
4. **Interview credibility**: Shows Russell understands when NOT to use AI

---

## Files to Modify

1. [`plans/demo-prototype.html`](demo-prototype.html:1)
   - Add USERS/DATASETS objects (~lines 460-540)
   - Replace `policies` with `abac_checks` in SCENARIOS (~lines 483-630)
   - Update policy card rendering (~lines 800-830)
   - Update audit trail rendering (~lines 920-935)
   - Add CSS for abac-row, audit-entry

2. [`PLAN.md`](../PLAN.md:1)
   - Update API response to show ABAC structure
   - Add section on ABAC decision flow
   - Document "AI at edges, rules at core" architecture

3. [`VISA-DEMO-PROGRESS.md`](../VISA-DEMO-PROGRESS.md:1)
   - Update Screen 1 description to mention ABAC
   - Add design decision: "ABAC matching (not AI policy decisions)"

---

## Next Steps

1. ✅ Complete this TDD plan
2. ⏭️ Send to Red Team for review
3. ⏭️ Implement Phase 1-6 (one cycle at a time)
4. ⏭️ Update PLAN.md
5. ⏭️ Screenshot before/after for docs
