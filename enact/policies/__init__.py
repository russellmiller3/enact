"""Built-in reusable policy functions."""

from enact.policies.email import no_mass_emails, no_repeat_emails
from enact.policies.cloud_storage import dont_delete_without_human_ok
