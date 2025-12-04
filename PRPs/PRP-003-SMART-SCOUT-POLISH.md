# PRP-003: Smart Price Scout UI Polish

## 1. Context & Objectives
**Goal:** Refine the Smart Price Scout UI to be more user-friendly and visually consistent, based on the browser agent's review.
**Problem:**
- "Agent Configuration" section is too technical (shows raw IP, bare checkbox).
- Distinction between "Quick Scout" (ad-hoc) and "Source URL" (scheduled) is not clear.
- The page lacks a cohesive "workspace" feel.
**Success Criteria:**
- [ ] "Agent Configuration" renamed to "Scheduled Sync Settings".
- [ ] Internal IP address hidden or moved to a "Debug" section.
- [ ] "Source URL" field labeled clearly as "Default Sync Target".
- [ ] Visual hierarchy improved.

## 2. Technical Approach
**Changes:**
- Modify `bimcalc/web/templates/crail4_config.html` to restructure the cards.
- Update labels and help text.
- Use badges or icons to distinguish sections.

## 3. Implementation Plan
### Phase 1: Restructuring
- [ ] Rename "Agent Configuration" -> "Scheduled Sync".
- [ ] Hide/Remove the IP address display (it's not useful for the user).
- [ ] Style the "Full Sync" checkbox as a modern toggle switch.

### Phase 2: Clarity
- [ ] Update "Source URL" label to "Scheduled Sync Target URL".
- [ ] Add help text explaining the difference between Quick Scout and Scheduled Sync.

## 4. Verification Strategy
- [ ] Browser Agent: Capture screenshot of the polished page.
