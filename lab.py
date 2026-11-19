"""Teaching-only discovery markers. Never use these as production security controls."""
from flask import g, request

FLAGS = {
    'INFO-01': 'COMMON{private_email_public_response}',
    'INFO-02': 'COMMON{backups_are_not_public_assets}',
    'INFO-03': 'COMMON{tracebacks_tell_secrets}',
    'BAC-01': 'COMMON{a_hidden_post_is_not_a_locked_post}',
    'BAC-02': 'COMMON{your_session_someone_elses_profile}',
    'BAC-03': 'COMMON{member_to_admin_with_one_field}',
    'BAC-04': 'COMMON{not_your_post_to_delete}',
    'BAC-05': 'COMMON{not_a_member_still_in_the_chat}',
    'BAC-06': 'COMMON{staff_api_without_staff_role}',
}


def award(exercise):
    """Call only after the relevant disclosure or successful state change."""
    flag = FLAGS[exercise]
    if request.method == 'HEAD':
        return flag  # No response body was disclosed; do not award a read flag.
    flags = g.setdefault('lab_flags', [])
    if flag not in flags:
        flags.append(flag)
    return flag


def hidden_post(post):
    return post['visibility'] != 'public' and post['user_id'] != g.user['id']


def flag_response(response):
    flags = g.get('lab_flags', [])
    if flags:
        response.headers['X-Lab-Flags'] = ', '.join(flags)
        if response.is_json:
            payload = response.get_json()
            # Preserve existing array contracts for comments and staff reports.
            if isinstance(payload, dict):
                payload['flags'] = flags
                response.set_data(response.json_module.dumps(payload) + '\n')
    return response
