from dataclasses import dataclass

DRIVERS = [
    "usage_decline",
    "high_ticket_volume",
    "unresolved_tickets",
    "champion_departed",
    "billing_dispute",
    "onboarding_incomplete",
    "price_sensitivity",
    "competitor_evaluation",
    "outage_impact",
    "expansion_interest",
    "low_seat_utilization",
]


@dataclass(frozen=True)
class Archetype:
    key: str
    risk: str
    satisfaction: str
    drivers: list[str]
    usage_trend: float
    tickets_per_month: float
    severity: str
    ticket_arcs: list[tuple[str, str, str]]
    qbr_paragraphs: list[tuple[str, str]]
    clause: str
    weight: int


ARCHETYPES: dict[str, Archetype] = {a.key: a for a in [
    Archetype(
        key="healthy_quiet", risk="low", satisfaction="happy", drivers=[],
        usage_trend=1.02, tickets_per_month=0.3, severity="low",
        ticket_arcs=[
            ("none", "Question about appointment reminders",
             "Quick question — can reminder texts go out 48 hours ahead instead of 24? "
             "No rush, the team is very happy with the scheduler overall."),
            ("none", "Report export column order",
             "The monthly production report exports columns in a different order than the "
             "on-screen view. Minor thing, everything else works great for us."),
        ],
        qbr_paragraphs=[
            ("none", "Front desk reports the system has been smooth all quarter; staff say "
             "scheduling is easier than their previous vendor and adoption is strong."),
            ("none", "No open escalations. Office manager praised the reminder feature and "
             "said patients love the confirmation texts."),
        ],
        clause="Renewal: this agreement renews automatically for successive one-year terms "
               "unless either party gives 60 days written notice.",
        weight=6),
    Archetype(
        key="stable_low_touch", risk="low", satisfaction="neutral", drivers=[],
        usage_trend=0.99, tickets_per_month=0.2, severity="low",
        ticket_arcs=[
            ("none", "Password reset for new hire",
             "We have a new hygienist starting Monday and need a login created. Thanks."),
            ("none", "Insurance code list update",
             "Is there a way to bulk-update the insurance fee schedule for the new year? "
             "We did it manually last time."),
        ],
        qbr_paragraphs=[
            ("none", "Quiet quarter. Usage steady, no complaints raised, though the office "
             "rarely responds to check-in emails."),
            ("none", "The practice uses core scheduling only; billing module remains unused. "
             "No issues reported."),
        ],
        clause="Renewal: annual term with automatic renewal unless cancelled with 30 days "
               "notice before the anniversary date.",
        weight=5),
    Archetype(
        key="expansion_candidate", risk="low", satisfaction="happy",
        drivers=["expansion_interest"],
        usage_trend=1.12, tickets_per_month=0.5, severity="low",
        ticket_arcs=[
            ("expansion_interest", "Adding a second location",
             "We are opening a second office in the spring and want to know how "
             "multi-location scheduling works and what additional seats would cost."),
            ("none", "Training session for new associates",
             "We hired two associates and would like a refresher training session. The team "
             "really likes the platform and wants everyone fluent on it."),
        ],
        qbr_paragraphs=[
            ("expansion_interest", "Practice is growing; owner asked about multi-location "
             "support and additional seats for a planned second office."),
            ("none", "Usage climbing month over month. Strong champion in the office manager, "
             "who demos features to the rest of the staff."),
        ],
        clause="Renewal: annual auto-renewal; additional seats may be added mid-term at the "
               "then-current per-seat rate, prorated.",
        weight=3),
    Archetype(
        key="usage_declining", risk="high", satisfaction="neutral",
        drivers=["usage_decline", "low_seat_utilization"],
        usage_trend=0.65, tickets_per_month=0.4, severity="low",
        ticket_arcs=[
            ("usage_decline", "Deactivating two user accounts",
             "Please deactivate the logins for our two departed front desk staff. We are "
             "running with a smaller team for now."),
            ("none", "Question on data export",
             "How do we export our full patient schedule history to CSV? We want a local "
             "copy of our records."),
        ],
        qbr_paragraphs=[
            ("usage_decline", "Logins have fallen steadily this quarter and several licensed "
             "seats have not been used in over sixty days."),
            ("low_seat_utilization", "The practice is paying for more seats than active "
             "users; office manager was noncommittal about plans for the unused licenses."),
        ],
        clause="Renewal: one-year term, auto-renews unless 60 days notice; seat count may "
               "only be reduced at renewal.",
        weight=4),
    Archetype(
        key="support_burned", risk="high", satisfaction="frustrated",
        drivers=["high_ticket_volume", "unresolved_tickets"],
        usage_trend=0.97, tickets_per_month=3.0, severity="high",
        ticket_arcs=[
            ("high_ticket_volume", "Claims sync failing again",
             "This is the third time reporting this — claims submitted through the portal "
             "are stuck in pending. This is unacceptable for a billing workflow we depend "
             "on daily. Please escalate."),
            ("unresolved_tickets", "Still waiting on ticket from last month",
             "Our calendar double-booking issue from last month is still not fixed. Staff "
             "have lost confidence in support and the front desk has given up on the "
             "waitlist feature entirely."),
            ("none", "Printer integration broken after update",
             "After the last update, route slips stopped printing. Workaround is manual "
             "printing which wastes time every single day."),
        ],
        qbr_paragraphs=[
            ("high_ticket_volume", "Difficult quarter: ticket volume roughly tripled and the "
             "office manager described support response times as extremely frustrating."),
            ("unresolved_tickets", "Two severity-high tickets remain open past thirty days. "
             "The practice administrator said they are evaluating alternatives if the sync "
             "issue is not resolved before renewal."),
        ],
        clause="Renewal: annual term with auto-renewal; customer may terminate for material "
               "breach uncured within 30 days of written notice.",
        weight=3),
    Archetype(
        key="champion_left", risk="high", satisfaction="neutral",
        drivers=["champion_departed", "usage_decline"],
        usage_trend=0.72, tickets_per_month=0.5, severity="normal",
        ticket_arcs=[
            ("champion_departed", "Admin transfer request",
             "Our office manager, who set up the system, has left the practice. Please "
             "transfer administrator rights to the new practice coordinator."),
            ("usage_decline", "Where are the training materials?",
             "The person who knew the system best is gone and the new staff cannot find the "
             "training guides. Usage of the reporting module has basically stopped."),
        ],
        qbr_paragraphs=[
            ("champion_departed", "The internal champion departed in the spring; the new "
             "coordinator inherited the system without training and has no relationship "
             "with our team."),
            ("usage_decline", "Feature usage narrowing to basic scheduling since the admin "
             "change; reporting and billing modules idle for two months."),
        ],
        clause="Renewal: auto-renews annually unless either party provides 45 days written "
               "notice prior to term end.",
        weight=3),
    Archetype(
        key="billing_dispute", risk="medium", satisfaction="frustrated",
        drivers=["billing_dispute"],
        usage_trend=1.0, tickets_per_month=1.0, severity="normal",
        ticket_arcs=[
            ("billing_dispute", "Overcharged on last invoice",
             "Our June invoice charged us for 12 seats but our contract says 10. This is "
             "the second billing error this year and we are disputing the charge until a "
             "credit is issued."),
            ("billing_dispute", "Credit memo still not applied",
             "The promised credit from the seat overcharge has not appeared on this month's "
             "statement. Frankly this is getting ridiculous and our bookkeeper is upset."),
        ],
        qbr_paragraphs=[
            ("billing_dispute", "Relationship strained by repeated invoicing errors; a "
             "disputed overcharge is still pending with accounts receivable."),
            ("none", "Product usage itself is healthy — the dispute is entirely about "
             "billing accuracy, not functionality."),
        ],
        clause="Fees: seat count is fixed at 10 for the term; overage billing requires a "
               "signed order form. Disputed amounts due within 15 days of resolution.",
        weight=3),
    Archetype(
        key="onboarding_stuck", risk="high", satisfaction="frustrated",
        drivers=["onboarding_incomplete", "low_seat_utilization"],
        usage_trend=0.6, tickets_per_month=1.5, severity="normal",
        ticket_arcs=[
            ("onboarding_incomplete", "Data migration still incomplete",
             "Six months in and our historical patient records are still not migrated. "
             "Half the staff refuse to use the system until their charts are in it."),
            ("low_seat_utilization", "Only two of nine staff logging in",
             "We bought nine seats but only the front desk actually uses the system. The "
             "onboarding sessions kept getting rescheduled and never finished."),
        ],
        qbr_paragraphs=[
            ("onboarding_incomplete", "Implementation stalled: migration of legacy records "
             "remains incomplete and the clinical staff never completed training."),
            ("low_seat_utilization", "Seat utilization is under a third; the practice owner "
             "questioned paying for licenses nobody uses."),
        ],
        clause="Onboarding: vendor shall complete data migration and two training sessions "
               "within 90 days of contract start.",
        weight=3),
    Archetype(
        key="price_sensitive", risk="medium", satisfaction="neutral",
        drivers=["price_sensitivity"],
        usage_trend=1.0, tickets_per_month=0.5, severity="low",
        ticket_arcs=[
            ("price_sensitivity", "Question about renewal pricing",
             "We received the renewal notice and the per-seat price went up 8 percent. As a "
             "small practice we need to understand what we are getting for the increase."),
            ("none", "Downgrade options",
             "Is there a cheaper tier without the billing module? We only use scheduling and "
             "reminders and are reviewing all our software costs this year."),
        ],
        qbr_paragraphs=[
            ("price_sensitivity", "Office manager flagged budget pressure and asked about "
             "the lower tier ahead of renewal; price increase letter did not land well."),
            ("none", "Product satisfaction is fine; the conversation is entirely about "
             "cost justification."),
        ],
        clause="Fees: pricing may increase up to 8% at renewal with 90 days notice.",
        weight=4),
    Archetype(
        key="feature_gap_shopper", risk="medium", satisfaction="neutral",
        drivers=["competitor_evaluation"],
        usage_trend=0.95, tickets_per_month=0.8, severity="normal",
        ticket_arcs=[
            ("competitor_evaluation", "Does the platform support online intake forms?",
             "Patients keep asking to fill forms before arriving. A rep from a competitor "
             "demoed digital intake to us last week and we want to know your roadmap."),
            ("competitor_evaluation", "Two-way patient texting timeline",
             "We have asked about two-way texting for a year. We are comparing options "
             "before our renewal and this feature gap is the main sticking point."),
        ],
        qbr_paragraphs=[
            ("competitor_evaluation", "The practice is actively comparing us against a "
             "competitor that offers digital intake and two-way texting; renewal decision "
             "hinges on the roadmap conversation."),
            ("none", "Core scheduling usage remains steady and staff are comfortable with "
             "the current workflows."),
        ],
        clause="Renewal: annual term, 60 days notice to cancel; no exclusivity obligations.",
        weight=3),
    Archetype(
        key="outage_affected", risk="medium", satisfaction="frustrated",
        drivers=["outage_impact"],
        usage_trend=0.92, tickets_per_month=1.2, severity="normal",
        ticket_arcs=[
            ("outage_impact", "System down during Monday clinic hours",
             "The scheduler was unreachable for three hours on our busiest morning. We had "
             "to run the front desk on paper. What is the plan to make sure this outage "
             "never happens again?"),
            ("outage_impact", "Requesting SLA credit for outage",
             "Per our agreement we are requesting the service credit for last month's "
             "downtime. Staff confidence took a real hit and patients noticed."),
        ],
        qbr_paragraphs=[
            ("outage_impact", "The March outage dominated the review; the practice asked for "
             "the incident report and the SLA credit and wants uptime commitments in "
             "writing."),
            ("none", "Aside from the incident, feature usage is normal and staff remain "
             "generally productive on the platform."),
        ],
        clause="Service levels: 99.5% monthly uptime; credits of 5% of monthly fees per "
               "full hour of unscheduled downtime, capped at 30%.",
        weight=2),
    Archetype(
        key="silent_churn", risk="medium", satisfaction="neutral",
        drivers=["usage_decline"],
        usage_trend=0.75, tickets_per_month=0.1, severity="low",
        ticket_arcs=[
            ("usage_decline", "How to archive old schedules",
             "We are tidying up our records. How do we archive last year's schedules? "
             "Also, is there a data export option?"),
            ("none", "Update billing contact",
             "Please change the billing contact email to our accountant's address."),
        ],
        qbr_paragraphs=[
            ("usage_decline", "Engagement is drifting down and the practice has gone quiet — "
             "no response to the last two check-in attempts, logins down by a quarter."),
            ("none", "No support burden at all, which combined with falling usage may "
             "indicate disengagement rather than health."),
        ],
        clause="Renewal: auto-renews for one-year terms unless 30 days notice is given.",
        weight=3),
]}
