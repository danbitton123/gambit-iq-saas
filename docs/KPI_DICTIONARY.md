# GAMBIT IQ — Official KPI Dictionary

**Version:** 1.0  
**Effective date:** 2026-08-04  
**Scope:** Casino live tables + sportsbook demo platform  
**Currency:** USD  
**Time convention:** UTC for storage and reporting until an operator timezone is configured

This document is the business source of truth for GAMBIT IQ. Dashboard labels, SQL marts, exports and model monitoring must use these definitions. A change to a definition requires a version update and approval from Data, Finance and the relevant business owner.

## Global conventions

- Reporting periods are half-open intervals: `event_timestamp >= period_start AND event_timestamp < period_end`.
- Only completed gaming events are included. The synthetic MVP treats every row in `sessions` and `sports_bets` as settled.
- Monetary KPI use the operator reporting currency and must not mix currencies without conversion.
- Approved deposits and withdrawals use `transaction_status = 'Approved'` only.
- Player counts always use `COUNT(DISTINCT player_id)`.
- Casino GGR and sportsbook GGR may be shown separately; Total GGR is their sum.
- Observed outcomes and model predictions must never share the same label. For example, **Retention D30** is observed, while **Predicted retention** is `1 − churn_probability`.
- Country, channel, device and VIP filters are based on the player's current attributes in this MVP. Production should use slowly changing dimensions when historical attribution matters.

## KPI definitions

### 1. Gross Gaming Revenue — GGR

**Business question:** How much gaming revenue did the operator retain before bonuses, taxes, fees and adjustments?

**Official formula**

```text
Casino GGR     = settled casino bets − settled casino payouts
Sportsbook GGR = settled sportsbook stakes − settled sportsbook payouts
Total GGR      = Casino GGR + Sportsbook GGR
```

**SQL source:** `sessions.total_bet_amount`, `sessions.total_payout_amount`, `sports_bets.stake`, `sports_bets.payout`. The stored `casino_ggr` and `sportsbook_ggr` fields must reconcile to these formulas.

**Grain/additivity:** Additive by day, game, sport, market and player. Negative values are valid at detailed grain.

**Exclusions:** Deposits and withdrawals are cash movements, not revenue, and must never enter GGR.

**Owner:** Finance / Gaming Operations. **Refresh:** Daily. **Status:** Validated.

### 2. Net Gaming Revenue — NGR

**Business question:** What gaming revenue remains after direct gaming deductions?

**Official formula**

```text
NGR = GGR − bonuses consumed − gaming taxes − payment processing fees
      − jackpot contributions − chargebacks ± approved adjustments
```

**Current MVP implementation:** `GGR − approved processing fees − 6.5% bonus provision − 9.5% gaming-tax provision`.

**Important limitation:** The MVP has no bonus ledger, tax table, jackpot ledger, chargeback table or adjustment ledger. The displayed NGR is therefore a **demo estimate**, not an accounting KPI. Production validation requires these sources.

**Owner:** Finance. **Refresh:** Daily with month-end restatement. **Status:** Provisional.

### 3. GGR Margin

**Business question:** What percentage of wagered money became operator GGR?

```text
GGR Margin = Total GGR / Total settled wagers
Total settled wagers = casino bets + sportsbook stakes
```

Use `NULLIF(total_wagers, 0)`. The ratio must be recomputed from summed numerator and denominator; never average row-level margins.

**Owner:** Finance / Trading. **Refresh:** Daily. **Status:** Validated.

### 4. Active Players

**Business question:** How many unique players generated qualifying gaming activity during the selected period?

```text
Active Players = distinct players with ≥1 settled casino session or settled sportsbook bet
```

A player active in both products is counted once. Deposits, logins and registrations alone do not create an active player.

**Owner:** Product Analytics. **Refresh:** Daily. **Status:** Validated.

### 5. First-Time Depositors — FTD

**Business question:** How many players made their first-ever successful deposit during the selected period?

```text
FTD date = MIN(transaction_date) over all approved Deposit transactions per player
FTD count = distinct players whose FTD date falls inside the reporting period
```

Declined, pending and reversed deposits are excluded. A returning depositor can never become an FTD again.

**Owner:** Growth / Finance. **Refresh:** Daily. **Status:** Validated.

### 6. FTD Conversion D30

**Business question:** What share of mature new registrations completed an approved first deposit within 30 days?

```text
FTD Conversion D30 = registrations with FTD between registration and registration + 30 days
                     / registrations eligible for a complete 30-day observation window
```

Denominator: players registered in the selected acquisition cohort with `registration_date <= as_of_date − 30 days`. Report immature cohorts separately, never as failures.

**Owner:** Growth. **Refresh:** Daily by registration cohort. **Status:** Validated definition; dashboard query requires alignment.

### 7. Average Deposit

**Business question:** What is the average size of an approved deposit transaction?

```text
Average Deposit = SUM(approved deposit amount) / COUNT(approved deposit transactions)
```

This is not average deposit per depositor. If that metric is required, label it **Deposit Amount per Depositor** and divide by distinct depositing players.

**Owner:** Payments / Finance. **Refresh:** Daily. **Status:** Validated.

### 8. Retention D30

**Business question:** What share of activated players returned to play around their 30th day?

```text
Eligible cohort = players whose first gaming activity occurred at least 37 days before as_of_date
Retained D30 = eligible players with ≥1 settled gaming event on days 30–36 after first activity
Retention D30 = Retained D30 / Eligible cohort
```

The seven-day window reduces time-zone and sparse-activity noise. Registration-based retention may be reported separately but must be labelled explicitly.

**Owner:** Product / CRM. **Refresh:** Daily by activation cohort. **Status:** Validated definition; dashboard query requires alignment.

### 9. Actual RTP

**Business question:** What percentage of casino wagers was returned to players?

```text
Actual RTP = SUM(settled casino payouts) / SUM(settled casino bets)
```

Compute at the requested aggregate grain using ratio of sums. Never average session RTP. Sportsbook does not use RTP; use Hold instead.

**Owner:** Casino Operations. **Refresh:** Daily, with minimum sample-size monitoring. **Status:** Validated.

### 10. RTP Variance

**Business question:** How far is observed payout behavior from the game's theoretical RTP?

```text
RTP Variance (percentage points) = Actual RTP − Theoretical RTP
```

Positive variance means players received more than theoretical expectation and operator margin was lower. Negative variance means players received less. For multiple games, calculate expected theoretical payout weighted by bets:

```text
Weighted theoretical RTP = SUM(bets × game theoretical RTP) / SUM(bets)
```

Always display sample size and wager volume; a variance is not automatically an anomaly.

**Owner:** Casino Operations / Risk. **Refresh:** Daily. **Status:** Validated; current dashboard sign requires alignment.

### 11. Churn Probability

**Business question:** What is the estimated probability that an eligible active player will have no gaming activity during the next 30 days?

**Model population:** Players with at least one settled gaming event in the 90-day observation window before scoring.  
**Target:** No settled casino session or sportsbook bet in the following 30 days.  
**Output:** Calibrated probability from 0 to 1.  
**Suggested bands:** Low `<0.40`; Watch `0.40–<0.70`; High `≥0.70`.

The current synthetic model uses a 35-day outcome window and a broader registered-player population. It is technically functional but must be retrained to this official definition before production use.

**Owner:** Data Science / CRM. **Refresh:** Daily or weekly. **Status:** Demo model — alignment required.

### 12. Predicted LTV 90D

**Business question:** What net contribution is a player expected to generate over the next 90 days?

```text
Predicted LTV 90D = expected 90-day NGR
                    − expected player-specific variable servicing costs
```

It is a currency prediction, not a probability. The current MVP target extrapolates positive future GGR from 35 days to 90 days and therefore represents a **GGR proxy**, not true net LTV.

**Owner:** Data Science / Finance / CRM. **Refresh:** Weekly. **Status:** Demo proxy — new target sources required.

### 13. Fraud Risk

**Business question:** What is the estimated probability of a confirmed fraud/abuse event within the next 30 days?

**Official target:** A confirmed case outcome from fraud operations, not merely a declined payment.  
**Output:** Calibrated probability from 0 to 1.  
**Suggested operational threshold:** `≥0.55` enters manual review; it must not automatically block or close an account.

The synthetic MVP uses transaction-decline behavior as a proxy label. It must not be described as proven fraud.

**Owner:** Fraud Operations / Data Science. **Refresh:** Daily or near real time. **Status:** Demo proxy — confirmed labels required.

### 14. Responsible-Gaming Risk — RG Risk

**Business question:** What is the estimated probability that behavioral indicators require a player-protection review?

**Official target:** A validated safer-gambling outcome or intervention based on approved behavioral features.  
**Output:** Probability from 0 to 1.  
**Suggested threshold:** `≥0.55` triggers human review and marketing suppression pending review.

This score is not a diagnosis and must never be optimized for revenue. The MVP uses future duration, deposits and activity intensity as proxy labels.

**Owner:** Responsible Gaming / Compliance / Data Science. **Refresh:** Daily or near real time. **Status:** Demo proxy — governance validation required.

## Validation and governance checklist

1. Finance approves GGR, NGR and currency treatment.
2. Growth approves FTD cohort eligibility and conversion window.
3. Product/CRM approves the Retention D30 activation event and return window.
4. Casino Operations approves the RTP variance sign convention.
5. Data Science documents feature windows, target windows, exclusions, calibration and thresholds.
6. Fraud and RG teams own labels and manual-review outcomes.
7. Dashboard labels include `Observed`, `Predicted` or `Estimated` where ambiguity is possible.
8. Every production data mart includes `metric_date`, `operator_id`, `currency`, `updated_at` and definition version.

## Required dashboard corrections

- Replace the current acquisition conversion with cohort-based **FTD Conversion D30**.
- Replace modelled `1 − churn probability` labelled as retention with observed **Retention D30**.
- Reverse the current casino variance calculation to `Actual RTP − Theoretical RTP`.
- Label current NGR as **Estimated NGR** until deduction ledgers exist.
- Label current LTV as **Predicted 90D GGR Proxy** until true NGR and servicing costs exist.
- Label fraud and RG outputs as **risk scores for review**, not confirmed outcomes.

The executable SQL definitions are maintained in `sql/kpi_reference.sql`.
