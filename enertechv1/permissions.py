import frappe


def lead_query(user=None):
    user = user or frappe.session.user

    # System Manager sees everything
    if "System Manager" in frappe.get_roles(user):
        return ""

    user = frappe.db.escape(user)

    return f"""
        (
            `tabLead`.`lead_owner` = {user}

            OR

            EXISTS (
                SELECT 1
                FROM `tabOpportunity` opp
                INNER JOIN `tabToDo` todo
                    ON todo.reference_type = 'Opportunity'
                    AND todo.reference_name = opp.name
                WHERE
                    opp.opportunity_from = 'Lead'
                    AND opp.party_name = `tabLead`.name
                    AND todo.allocated_to = {user}
                    AND todo.status != 'Cancelled'
            )
        )
    """