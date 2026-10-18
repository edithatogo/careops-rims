"""Local reference logic for institutional dates and subscription matching.

No tenant writes, calendar invitations or notifications. Holiday coverage and
institutional lead times must be supplied by a versioned institutional policy.
"""
from datetime import date, timedelta
import hashlib
import re

SUBSCRIPTION_SCOPES = {'opportunity', 'category', 'funder'}


def _identity(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{label} must be a non-empty string')
    if value != value.strip():
        raise ValueError(f'{label} must not have surrounding whitespace')
    return value


def institutional_deadline(external_date, lead_days, *, business_days=True, holidays=()):
    """Return a proposed date; partial/unknown source dates remain unknown."""
    if type(lead_days) is not int or not 0 <= lead_days <= 3660:
        raise ValueError('Lead days must be an integer from zero to 3660')
    if type(business_days) is not bool:
        raise ValueError('Business day policy must be boolean')
    if not isinstance(external_date, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', external_date):
        return None
    try:
        target = date.fromisoformat(external_date)
    except ValueError:
        return None
    try:
        if not isinstance(holidays, (list, tuple, set)):
            raise ValueError
        if any(not isinstance(day, str) for day in holidays):
            raise ValueError
        parsed_holidays = [date.fromisoformat(day) for day in holidays]
        if len(parsed_holidays) != len(set(parsed_holidays)):
            raise ValueError
        excluded = set(parsed_holidays)
    except (TypeError, ValueError):
        raise ValueError('holidays must contain unique ISO date strings') from None
    remaining = lead_days
    while remaining:
        target -= timedelta(days=1)
        if not business_days or (target.weekday() < 5 and target not in excluded):
            remaining -= 1
    return target.isoformat()


def subscribers(opportunity, subscriptions, *, current_user_key: str):
    """Return whether the current user matches, without selecting recipients."""
    if not isinstance(opportunity, dict):
        raise ValueError('opportunity must be an object')
    current_user_key = _identity(current_user_key, 'current_user_key')
    if not isinstance(subscriptions, (list, tuple, set)):
        raise ValueError('subscriptions must be a collection of rules')
    opportunity_key = opportunity.get('OpportunityKey')
    opportunity_key = _identity(opportunity_key, 'opportunity OpportunityKey')
    category_keys = opportunity.get('CategoryKeys', [])
    if not isinstance(category_keys, (list, tuple, set)):
        raise ValueError('opportunity CategoryKeys must be a collection of non-empty keys')
    category_keys = [_identity(key, 'opportunity CategoryKeys value') for key in category_keys]
    funder_key = opportunity.get('FunderKey', '')
    if not isinstance(funder_key, str):
        raise ValueError('opportunity FunderKey must be a string when supplied')
    if funder_key:
        funder_key = _identity(funder_key, 'opportunity FunderKey')
    targets = {'opportunity': {opportunity_key},
               'category': set(category_keys),
               'funder': {funder_key} if funder_key else set()}
    matched = False
    for rule in subscriptions:
        if not isinstance(rule, dict):
            raise ValueError('subscription rule must be an object')
        scope = rule.get('Scope')
        user_key = rule.get('UserKey')
        target_key = rule.get('TargetKey')
        scope = _identity(scope, 'subscription Scope')
        user_key = _identity(user_key, 'subscription UserKey')
        target_key = _identity(target_key, 'subscription TargetKey')
        if scope not in SUBSCRIPTION_SCOPES:
            raise ValueError('subscription requires a supported scope, user key and target key')
        if rule.get('Active') is not True and rule.get('Active') is not False:
            raise ValueError('subscription Active must be boolean')
        if rule.get('Active') is True and user_key == current_user_key and target_key in targets[scope]:
            matched = True
    return [current_user_key] if matched else []


def validate_policy(policy):
    """Validate a versioned institutional date policy without approving it."""
    if not isinstance(policy, dict):
        return False
    required = ('PolicyKey', 'Version', 'OrganisationKey', 'AnchorKind', 'LeadDays',
                'HolidayCalendarVersion', 'EffectiveFrom')
    string_required = ('PolicyKey', 'Version', 'OrganisationKey', 'AnchorKind',
                       'HolidayCalendarVersion', 'EffectiveFrom')
    if any(
        not isinstance(policy.get(key), str)
        or not policy[key].strip()
        or policy[key] != policy[key].strip()
        for key in string_required
    ):
        return False
    if policy.get('LeadDays') in (None, ''):
        return False
    if 'EffectiveTo' in policy:
        if policy['EffectiveTo'] is not None and not isinstance(policy['EffectiveTo'], str):
            return False
        if policy['EffectiveTo'] == '' or policy['EffectiveTo'] != policy['EffectiveTo'].strip():
            return False
    if type(policy['LeadDays']) is not int or not 0 <= policy['LeadDays'] <= 3660:
        return False
    if policy.get('CalendarOrBusinessDays') not in ('calendar', 'business'):
        return False
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', policy['EffectiveFrom']):
        return False
    if policy.get('EffectiveTo') and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', policy['EffectiveTo']):
        return False
    try:
        effective_from = date.fromisoformat(policy['EffectiveFrom'])
        effective_to = date.fromisoformat(policy['EffectiveTo']) if policy.get('EffectiveTo') else None
    except ValueError:
        return False
    if effective_to and effective_to < effective_from:
        return False
    holidays = policy.get('HolidayDates', ())
    if not isinstance(holidays, (list, tuple, set)):
        return False
    if any(not isinstance(day, str) or day != day.strip() for day in holidays):
        return False
    try:
        parsed_holidays = [date.fromisoformat(day) for day in holidays]
    except (TypeError, ValueError):
        return False
    if len(parsed_holidays) != len(set(parsed_holidays)):
        return False
    return True


def delivery_event_key(user_key, opportunity_key, event_type, revision, offset_days, channel, *, current_user_key: str):
    """Stable idempotency key for a future delivery ledger; no delivery occurs here."""
    fields = tuple(_identity(value, 'delivery event identity fields') for value in (user_key, opportunity_key, event_type, revision, channel))
    current_user_key = _identity(current_user_key, 'current_user_key')
    if user_key != current_user_key:
        raise ValueError('delivery event user must match current_user_key')
    if type(offset_days) is not int or not -3660 <= offset_days <= 3660:
        raise ValueError('delivery event offset_days must be an integer from -3660 to 3660')
    basis = '|'.join(fields[:4]) + f'|{offset_days}|' + fields[4]
    return 'EVENT:' + hashlib.sha256(basis.encode('utf-8')).hexdigest()[:24]
