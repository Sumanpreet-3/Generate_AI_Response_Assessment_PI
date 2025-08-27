# Example dictionary mapping (control_id, asset_type) to questionnaire and summary
example_dict = {
	("Control-1.1.1", "Firewall"): {
		"questionnaire": [
			{
				"text": "Do you have a documented policy or procedure for requesting, approving, and implementing firewall or router configuration changes?",
				"userResponse": "Yes, we maintain a documented Firewall and Network Change Management Policy in our Information Security Management System (ISMS). It outlines the steps for requesting, approving, testing, and implementing changes."
			},
			{
				"text": "When was this process last reviewed or updated?",
				"userResponse": "Reviewed and updated in February 2025 as part of our annual PCI DSS compliance review."
			},
			{
				"text": "How do you initiate a firewall rule change request?",
				"userResponse": "Requests are initiated through our IT Service Management (ITSM) platform, where the requester must provide business justification, source/destination details, ports, and duration."
			},
			{
				"text": "Who is authorized to approve firewall configuration changes?",
				"userResponse": "Approvals are granted by both the Network Security Manager and the Head of IT Operations."
			},
			{
				"text": "Is there a requirement for dual approval (security + network teams) before implementation?",
				"userResponse": "Yes, all firewall changes require approval from both the security and network teams to ensure alignment with compliance and operational needs."
			},
			{
				"text": "How are business justifications for rule changes recorded?",
				"userResponse": "Business justifications are included in the ITSM change ticket and stored for a minimum of 12 months for audit purposes."
			},
			{
				"text": "How are firewall configuration changes tested before being deployed to production?",
				"userResponse": "All changes are tested in our staging environment, which mirrors production. We validate connectivity, performance impact, and compliance requirements before deployment."
			},
			{
				"text": "Do you perform security impact assessments for proposed changes?",
				"userResponse": "Yes, every change undergoes a risk assessment by the security team, which includes evaluating potential vulnerabilities."
			},
			{
				"text": "Are there rollback plans prepared in case a change introduces issues?",
				"userResponse": "Yes, a rollback plan is mandatory in the change request, and backup configurations are taken prior to implementation."
			},
			{
				"text": "How do you ensure that all firewall changes comply with PCI DSS and other relevant frameworks (e.g., ISO 27001)?",
				"userResponse": "Each request is reviewed against PCI DSS 1.2.1 and ISO 27001 Annex A control requirements to ensure security and compliance."
			},
			{
				"text": "Are new rules reviewed against security baselines or standards before approval?",
				"userResponse": "Yes, they are checked against our internal baseline rule set and compliance checklist."
			},
			{
				"text": "Are all configuration changes logged in a change management system?",
				"userResponse": "Yes, every change is logged in the ITSM tool with detailed records, including the approvers, testing evidence, and implementation notes."
			},
			{
				"text": "How long are change records retained?",
				"userResponse": "Change records are retained for 13 months to align with PCI DSS requirements."
			},
			{
				"text": "Can you provide examples of recent firewall changes with associated approvals?",
				"userResponse": "Yes, we can provide change ticket IDs with attached approvals and test results from the last three months."
			},
			{
				"text": "How often are firewall configurations reviewed to ensure they reflect approved changes only?",
				"userResponse": "Firewall configurations are reviewed quarterly by the security team."
			},
			{
				"text": "Do you have a process for identifying and removing stale or expired rules?",
				"userResponse": "Yes, expired rules are automatically flagged in our rule database and removed during quarterly reviews."
			}
		],
		"summary": """
The organization has a documented and regularly reviewed firewall change management process that requires formal requests, 
dual approvals, security impact assessments, testing in a staging environment, rollback plans, and compliance validation 
against PCI DSS and ISO 27001. All changes are logged in the ITSM system, retained for 13 months, and reviewed quarterly 
to remove stale rules. Evidence of recent approved changes supports that the process is consistently followed. 
Control 1.1.1 appears to be in place.
"""
	}
}
